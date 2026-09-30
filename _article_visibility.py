"""Prepare reversible catalog / robots visibility changes on trusted source.

Never replace public prose with an unfinished draft when unpublishing. Source
URLs, markup, artwork and unrelated catalog entries remain unchanged.
"""
from __future__ import annotations

import html
from html.parser import HTMLParser
from pathlib import Path
import re

from _prepare_article_candidate import CATALOG, catalog_literal


def catalog_ranges(source: str) -> list[tuple[int, int]]:
    """Locate top-level object literals without counting quoted braces/comments."""
    matches = list(re.finditer(r"DN\.ARTICLES\s*=\s*\[", source))
    if len(matches) != 1:
        raise ValueError("Catalog assignment is ambiguous")
    index, arrays, braces, start = matches[0].end(), 1, 0, None
    ranges = []
    while index < len(source):
        char = source[index]
        if char in "'\"":
            quote = char
            index += 1
            while index < len(source):
                if source[index] == "\\":
                    index += 2
                elif source[index] == quote:
                    index += 1
                    break
                else:
                    index += 1
            else:
                raise ValueError("Unterminated catalog string")
            continue
        if source.startswith("//", index):
            end = source.find("\n", index + 2)
            index = len(source) if end < 0 else end + 1
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end < 0:
                raise ValueError("Unterminated catalog comment")
            index = end + 2
            continue
        if char in "`/":
            raise ValueError("Unsupported template/regex catalog literal")
        if char == "[":
            arrays += 1
        elif char == "]":
            arrays -= 1
            if arrays == 0:
                if braces:
                    raise ValueError("Unbalanced catalog object")
                return ranges
        elif char == "{":
            if braces == 0 and arrays == 1:
                start = index
            braces += 1
        elif char == "}":
            braces -= 1
            if braces < 0:
                raise ValueError("Unbalanced catalog object")
            if braces == 0 and start is not None:
                ranges.append((start, index + 1))
                start = None
        index += 1
    raise ValueError("Unterminated article catalog")


class Robots(HTMLParser):
    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.lines = [0] + [match.end() for match in re.finditer("\n", source)]
        self.head = False
        self.head_count = 0
        self.head_closed = 0
        self.inert = 0
        self.tags = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag == "head":
            self.head_count += 1
            self.head = True
        elif tag == "body":
            self.head = False
        if tag in {"template", "noscript"}:
            self.inert += 1
        if tag != "meta" or not any(key == "name" and isinstance(value, str) and value.lower() == "robots" for key, value in attrs):
            return
        names = [key for key, _ in attrs]
        if not self.head or self.inert or names.count("name") != 1 or names.count("content") != 1:
            raise ValueError("Ambiguous robots metadata")
        content = dict(attrs)["content"]
        if not isinstance(content, str) or re.search(r"[^a-zA-Z0-9,:_ \-]", content):
            raise ValueError("Unsupported robots directives")
        row, column = self.getpos()
        start = self.lines[row - 1] + column
        self.tags.append((start, start + len(self.get_starttag_text()), content))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "head":
            self.head = False
            self.head_closed += 1
        if tag in {"template", "noscript"}:
            self.inert = max(0, self.inert - 1)

    def one(self) -> tuple[int, int, str]:
        if self.head_count != 1 or self.head_closed != 1 or len(self.tags) != 1:
            raise ValueError("Expected one robots meta in one article head")
        return self.tags[0]


def unpublish_plan(root: Path, file: str, source: bytes, slug: str) -> dict[str, bytes]:
    if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or len(slug) > 100 or slug in {"index", "topics", "charts"} or file != "blog/" + slug + ".html":
        raise ValueError("Invalid article visibility target")
    from _sync_hub_catalog import load_catalog
    entries = load_catalog(root)
    indexes = [index for index, item in enumerate(entries) if item["slug"] == slug]
    if len(indexes) != 1:
        raise ValueError("Article is missing from the public catalog")
    item = entries[indexes[0]]
    if item.get("unpublished"):
        raise ValueError("Article is already unpublished; no new visibility candidate")
    if "cms_robots_before" in item:
        raise ValueError("Previous visibility recovery policy needs manual review")
    article, directives = unpublish_article(source)
    original = (root / CATALOG).read_bytes().decode("utf-8")
    spans = catalog_ranges(original)
    if len(spans) != len(entries):
        raise ValueError("Catalog entry locations do not match parsed metadata")
    left, right = spans[indexes[0]]
    # Keep the prior policy for a separately approved republish operation. An
    # originally noindex article must remain noindex if its visibility returns.
    replacement = catalog_literal({**item, "unpublished": True, "cms_robots_before": directives})
    catalog = (original[:left] + replacement + original[right:]).encode("utf-8")
    return {file: article, CATALOG: catalog}


def unpublish_article(source: bytes) -> tuple[bytes, str]:
    """Change only the indexing directive, retaining exact published prose."""
    text = source.decode("utf-8")
    start, end, directives = Robots(text).one()
    parts = [part.strip() for part in directives.split(",") if part.strip() and part.strip().lower() != "index"]
    if not any(part.lower() == "noindex" for part in parts):
        parts.insert(0, "noindex")
    tag = robots_content(text[start:end], ",".join(parts))
    return (text[:start] + tag + text[end:]).encode("utf-8"), directives


def robots_content(tag: str, directives: str) -> str:
    # Match complete attribute tokens, so a quoted data attribute containing
    # text such as "content=..." cannot be mistaken for the real attribute.
    opening = re.match(r"<meta\b", tag, re.I)
    if not opening:
        raise ValueError("Expected a robots meta tag")
    tokens = re.finditer(r'''\s+([^\s/=<>]+)\s*(?:=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?''', tag[opening.end():])
    content = [token for token in tokens if token[1].lower() == "content"]
    if len(content) != 1:
        raise ValueError("Robots content location is ambiguous")
    token = content[0]
    group = next((group for group in (2, 3, 4) if token[group] is not None), None)
    if group is None:
        raise ValueError("Missing robots content value")
    left, right = (point + opening.end() for point in token.span(group))
    value = html.escape(directives, quote=True)
    if group == 4:
        value = '"' + value + '"'
    return tag[:left] + value + tag[right:]
