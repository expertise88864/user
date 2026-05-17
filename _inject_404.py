#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Refresh 404.html's "popular articles" list with the 6 newest from DN.ARTICLES.

The 404 page previously hardcoded 6 article slugs that drift out of sync
as new content is published. This injector runs every build and keeps
the list pointing at the 6 newest articles by date desc (excluding
unpublished). Same script style as _inject_related.py.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent


def parse_articles() -> list[dict]:
    js = (ROOT / "blog" / "blog-shared.js").read_text(encoding="utf-8")
    m = re.search(r"DN\.ARTICLES\s*=\s*\[([\s\S]*?)\];", js)
    if not m:
        raise SystemExit("DN.ARTICLES not found")
    block = m.group(1)
    articles = []
    for entry_m in re.finditer(r"\{[^{}]*?slug:\s*'([a-z0-9-]+)'[^{}]*?\}", block):
        e = entry_m.group(0)
        slug = entry_m.group(1)

        def get(field):
            mm = re.search(rf"{field}:\s*'([^']*)'", e)
            return mm.group(1) if mm else None

        is_unpub = bool(re.search(r"\bunpublished\s*:\s*true\b", e))
        articles.append({
            "slug": slug,
            "title": get("title") or "",
            "title_en": get("title_en") or "",
            "date": get("date") or "",
            "unpublished": is_unpub,
        })
    return articles


def build_list(articles: list[dict], n: int = 6) -> str:
    top = sorted(
        [a for a in articles if not a["unpublished"]],
        key=lambda a: a["date"] or "",
        reverse=True,
    )[:n]
    return "\n".join(
        f'<li><a href="/blog/{a["slug"]}"><span class="dot"></span>'
        f'<span data-zh="{a["title"]}" data-en="{a["title_en"] or a["title"]}">{a["title"]}</span></a></li>'
        for a in top
    )


def main() -> int:
    articles = parse_articles()
    new_list = build_list(articles, n=6)

    p = ROOT / "404.html"
    if not p.exists():
        print("[404] 404.html not found")
        return 0
    src = p.read_text(encoding="utf-8")
    m = re.search(r'<ul class="popular">([\s\S]*?)</ul>', src)
    if not m:
        print("[404] <ul class='popular'> not found")
        return 0
    new_src = src.replace(m.group(0), f'<ul class="popular">{new_list}</ul>')
    if new_src == src:
        print("[404] popular list already up to date")
        return 0
    p.write_text(new_src, encoding="utf-8")
    print(f"[404] refreshed popular list with 6 newest articles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
