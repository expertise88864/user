#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pre-build full-text search index -> assets/search-index.json."""

from __future__ import annotations

import html as html_lib
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from _sync_hub_catalog import load_catalog


if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
BLOG = os.path.join(ROOT, "blog")
OUT = os.path.join(ROOT, "assets", "search-index.json")

SKIP = {"index.html", "topics.html", "feed.xml", "atom.xml"}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(value)).strip()


class VisibleTextExtractor(HTMLParser):
    """Extract visible heading and paragraph text without reading attributes."""

    TEXT_TAGS = {"h1", "h2", "h3", "p"}
    SKIP_TAGS = {"script", "style", "svg", "noscript", "template", "textarea", "title"}
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
                 "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.current: list[object] | None = None
        self.items: list[tuple[str, str]] = []
        self.noindex = False

    def _is_hidden(self, tag: str, attrs: list[tuple[str, str | None]]) -> bool:
        attr_map = {name.lower(): (value or "") for name, value in attrs}
        style = attr_map.get("style", "").replace(" ", "").lower()
        return (
            tag in self.SKIP_TAGS
            or "display:none" in style
            or "hidden" in attr_map
            or attr_map.get("aria-hidden", "").lower() == "true"
        )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == 'meta' and not self.skip_depth:
            values = {name.lower(): (value or '') for name, value in attrs}
            names = [(value or '').lower() for name, value in attrs if name.lower() == 'name']
            if set(names) & {'robots', 'googlebot'}:
                # Browsers keep the first duplicate attribute, while dict()
                # keeps the last. Ambiguous author visibility must not leak.
                if len(names) != 1 or sum(name.lower() == 'content' for name, _ in attrs) != 1:
                    self.noindex = True
                directives = set(re.split(r'[\s,]+', values.get('content', '').lower()))
                self.noindex |= bool(directives & {'noindex', 'none'})
        if tag in self.VOID_TAGS:
            return
        if self.skip_depth:
            self.skip_depth += 1
            return
        if self._is_hidden(tag, attrs):
            self.skip_depth = 1
            return
        if tag in self.TEXT_TAGS and self.current is None:
            self.current = [tag, []]

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.VOID_TAGS:
            return
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if self.current and tag == self.current[0]:
            text = clean_text("".join(self.current[1]))  # type: ignore[arg-type]
            if text:
                self.items.append((tag, text))
            self.current = None

    def handle_data(self, data: str) -> None:
        if not self.skip_depth and self.current is not None:
            self.current[1].append(data)  # type: ignore[index,union-attr]

    def handle_entityref(self, name: str) -> None:
        if not self.skip_depth and self.current is not None:
            self.current[1].append(f"&{name};")  # type: ignore[index,union-attr]

    def handle_charref(self, name: str) -> None:
        if not self.skip_depth and self.current is not None:
            self.current[1].append(f"&#{name};")  # type: ignore[index,union-attr]


def extract(page_html: str) -> dict[str, object]:
    out: dict[str, object] = {}
    parser = VisibleTextExtractor()
    parser.feed(page_html)
    parser.close()
    if parser.noindex:
        return out

    title = next((text for tag, text in parser.items if tag == "h1"), "")
    if title:
        out["title"] = title[:120]

    headings = [text for tag, text in parser.items if tag in {"h2", "h3"} and len(text) <= 80]
    if headings:
        out["h"] = headings[:20]

    snippet = next((text for tag, text in parser.items if tag == "p" and len(text) >= 40), "")
    if snippet:
        out["snippet"] = snippet[:200]

    date_match = re.search(r'datetime="(\d{4}-\d{2}-\d{2})"', page_html) or re.search(r"(\d{4}-\d{2}-\d{2})", page_html)
    if date_match:
        out["date"] = date_match.group(1)
    return out


def get_unpublished_slugs() -> set[str]:
    """Use the same trusted catalog semantics as CMS, hub cards, and feeds.

    Invalid/missing author visibility data stops generation before output writes.
    A JS-literal reader supports both quotes and multiline CMS catalog entries.
    """
    return {item['slug'] for item in load_catalog(Path(ROOT)) if item.get('unpublished')}


def main() -> None:
    unpublished = get_unpublished_slugs()
    if unpublished:
        print(f"Skipping unpublished slugs: {sorted(unpublished)}")
    entries: list[dict[str, object]] = []
    for filename in sorted(os.listdir(BLOG)):
        if not filename.endswith(".html") or filename in SKIP:
            continue
        slug = filename[:-5]
        if slug in unpublished:
            continue
        path = os.path.join(BLOG, filename)
        with open(path, "r", encoding="utf-8") as f:
            page_html = f.read()
        data = extract(page_html)
        if not data.get("title"):
            continue
        entries.append({
            "slug": slug,
            "title": data["title"],
            "h": data.get("h", []),
            "snippet": data.get("snippet", ""),
            "date": data.get("date", ""),
            "url": "/blog/" + slug,
        })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(OUT)
    print(f"Wrote {len(entries)} entries -> assets/search-index.json ({size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
