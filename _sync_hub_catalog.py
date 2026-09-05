"""Keep public article cards in raw HTML; JavaScript only enhances navigation.

Preserve existing editorial cards and artwork. Fill missing cards from the
catalog's existing bilingual titles, and remove unpublished cards from hubs.
Run before EN generation. --check verifies both language mirrors without writes.
"""
from __future__ import annotations

import argparse
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
HUBS = {"index.html": "dn-article-list", "blog/index.html": "articleList"}


def load_catalog(root: Path = ROOT) -> list[dict]:
    # Parse the trusted repository's JS literal with JS string semantics, so
    # escaped apostrophes and Unicode are not truncated by a regex field parser.
    script = """
const fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
const match = source.match(/DN\\.ARTICLES\\s*=\\s*(\\[[\\s\\S]*?\\]);/);
if (!match) throw Error('Missing DN.ARTICLES');
process.stdout.write(JSON.stringify(vm.runInNewContext('(' + match[1] + ')', {}, {timeout: 1000})));
"""
    result = subprocess.run(
        ["node", "-e", script, str(root / "blog/blog-shared.js")],
        check=True, capture_output=True, encoding="utf-8", timeout=10,
    )
    catalog = json.loads(result.stdout)
    if not isinstance(catalog, list) or not catalog:
        raise ValueError("Empty or invalid article catalog")
    seen = set()
    for item in catalog:
        slug = item.get("slug", "")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or slug in seen:
            raise ValueError(f"Invalid or duplicate catalog slug: {slug}")
        seen.add(slug)
        if not item.get("title") or not item.get("title_en"):
            raise ValueError(f"Missing bilingual title: {slug}")
    return catalog


class CardList(HTMLParser):
    """Locate the actual list and its direct card children, preserving bytes."""

    def __init__(self, source: str, element_id: str):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.element_id = element_id
        self.lines = [0]
        for match in re.finditer("\n", source):
            self.lines.append(match.end())
        self.depth = 0
        self.start = self.end = None
        self.card_start = None
        self.cards = []
        self.feed(source)
        if self.start is None or self.end is None or self.card_start is not None:
            raise ValueError(f"Missing or malformed article list: {element_id}")

    def source_offset(self):
        row, col = self.getpos()
        return self.lines[row - 1] + col

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            if attrs.get("id") == self.element_id:
                if self.start is not None:
                    raise ValueError(f"Duplicate list: {self.element_id}")
                self.start = self.source_offset() + len(self.get_starttag_text())
                self.depth = 1
            elif self.depth:
                self.depth += 1
        if tag == "a" and self.depth == 1:
            if self.card_start is not None:
                raise ValueError("Nested article card")
            if "article-list-item" not in attrs.get("class", "").split():
                raise ValueError("Unexpected link inside article list")
            match = re.fullmatch(r"/(?:en/)?blog/([a-z0-9-]+)", attrs.get("href", ""))
            if not match:
                raise ValueError("Noncanonical article card URL")
            self.card_start = self.source_offset()
            self.slug = match[1]

    def handle_endtag(self, tag):
        if tag == "a" and self.card_start is not None:
            end = self.source_offset() + len("</a>")
            self.cards.append((self.slug, self.card_start, end))
            self.card_start = None
        if tag == "div" and self.depth:
            self.depth -= 1
            if not self.depth:
                self.end = self.source_offset()


def public_catalog(catalog: list[dict], root: Path) -> list[dict]:
    published = []
    for item in catalog:
        if item.get("unpublished"):
            continue
        path = root / "blog" / (item["slug"] + ".html")
        source = path.read_text(encoding="utf-8")
        # Use parsed attributes; noindex may be beyond the first 5 KB.
        class Robots(HTMLParser):
            noindex = False

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "meta" and attrs.get("name", "").lower() in {"robots", "googlebot"}:
                    self.noindex |= "noindex" in re.split(r"[\s,]+", attrs.get("content", "").lower())

        robots = Robots()
        robots.feed(source)
        if not robots.noindex:
            published.append(item)
    if not published:
        raise ValueError("No public articles; refusing to empty hubs")
    return published


def render_card(item: dict) -> str:
    slug, title, english = (html.escape(item[key], quote=True) for key in ("slug", "title", "title_en"))
    category = html.escape(item.get("cat") or "note", quote=True)
    tag_en = html.escape(item.get("tag_en") or "", quote=True)
    date = html.escape(item.get("date") or "", quote=True)
    return (
        f'<a href="/blog/{slug}" class="article-list-item" data-cat="{category}" data-tag-en="{tag_en}">'
        f'<div class="al-body"><div class="al-meta"><time datetime="{date}">{date}</time></div>'
        f'<h2 data-zh="{title}" data-en="{english}">{title}</h2></div>'
        '<div class="al-arrow" aria-hidden="true">→</div></a>'
    )


def sync_source(source: str, element_id: str, articles: list[dict]) -> str:
    parsed = CardList(source, element_id)
    existing = set()
    wanted = {item["slug"] for item in articles}
    removals = []
    for slug, start, end in parsed.cards:
        # Legacy hubs can contain a second minimal card for the same article.
        # Keep the first editorial card; --check still rejects duplicate output.
        if slug not in wanted or slug in existing:
            removals.append((start, end))
        else:
            existing.add(slug)
    # Retain the editorial order and artwork. Runtime filtering can sort cards;
    # static readers still receive every published link exactly once.
    additions = "".join(render_card(item) for item in articles if item["slug"] not in existing)
    updated = source[:parsed.end] + additions + source[parsed.end:]
    for start, end in reversed(removals):
        updated = updated[:start] + updated[end:]
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    articles = public_catalog(load_catalog(), ROOT)
    expected = {item["slug"] for item in articles}
    pending = []
    for relative, element_id in HUBS.items():
        path = ROOT / relative
        with path.open(encoding="utf-8", newline="") as stream:
            source = stream.read()
        updated = sync_source(source, element_id, articles)
        pending.append((path, updated, source != updated))
        if args.check:
            for target in (path, ROOT / "en" / relative):
                parsed = CardList(target.read_text(encoding="utf-8"), element_id)
                slugs = [slug for slug, _, _ in parsed.cards]
                if set(slugs) != expected or len(slugs) != len(expected):
                    raise ValueError(f"{target.relative_to(ROOT)}: stale public article cards")
    # Validate every target before writing any of them.
    if not args.check:
        for path, updated, changed in pending:
            if changed:
                with path.open("w", encoding="utf-8", newline="") as stream:
                    stream.write(updated)
    print(f"[OK] Public hub cards: {len(expected)} articles, {'verified ZH + EN' if args.check else 'synced ZH'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
