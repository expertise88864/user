#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pre-build full-text search index -> assets/search-index.json."""

from __future__ import annotations

import html as html_lib
import io
import json
import os
import re
import sys
from html.parser import HTMLParser


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.abspath(__file__))
BLOG = os.path.join(ROOT, "blog")
OUT = os.path.join(ROOT, "assets", "search-index.json")

SKIP = {"index.html", "topics.html", "feed.xml", "atom.xml"}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(value)).strip()


class VisibleTextExtractor(HTMLParser):
    """Extract visible heading and paragraph text without reading attributes."""

    TEXT_TAGS = {"h1", "h2", "h3", "p"}
    SKIP_TAGS = {"script", "style", "svg", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.current: list[object] | None = None
        self.items: list[tuple[str, str]] = []

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


def main() -> None:
    entries: list[dict[str, object]] = []
    for filename in sorted(os.listdir(BLOG)):
        if not filename.endswith(".html") or filename in SKIP:
            continue
        path = os.path.join(BLOG, filename)
        with open(path, "r", encoding="utf-8") as f:
            page_html = f.read()
        data = extract(page_html)
        if not data.get("title"):
            continue
        slug = filename[:-5]
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
