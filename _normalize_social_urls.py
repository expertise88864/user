#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Normalize og:url to match each page canonical URL."""

from __future__ import annotations

import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "__pycache__"}


def canonical(src: str) -> str:
    match = re.search(r'<link\s+rel="canonical"\s+href="([^"]*)"', src, re.I)
    return match.group(1) if match else ""


def normalize(src: str) -> str:
    head_match = re.search(r"<head\b[^>]*>[\s\S]*?</head>", src, re.I)
    if not head_match:
        return src

    head = head_match.group(0)
    url = canonical(head)
    if not url:
        return src
    escaped = html.escape(url, quote=True)
    if re.search(r'<meta\s+property="og:url"\s+content="[^"]*"', head, re.I):
        next_head = re.sub(
            r'(<meta\s+property="og:url"\s+content=")[^"]*(")',
            lambda m: m.group(1) + escaped + m.group(2),
            head,
            count=1,
            flags=re.I,
        )
    elif '<meta property="og:title"' in head:
        next_head = head.replace(
            '<meta property="og:title"',
            f'<meta property="og:url" content="{escaped}" /><meta property="og:title"',
            1,
        )
    else:
        return src

    return src[: head_match.start()] + next_head + src[head_match.end() :]


def main() -> None:
    changed = 0
    for path in sorted(ROOT.rglob("*.html")):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        src = path.read_text(encoding="utf-8")
        next_src = normalize(src)
        if next_src != src:
            path.write_text(next_src, encoding="utf-8")
            changed += 1
            print("normalized og:url", path.relative_to(ROOT).as_posix())
    print(f"Normalized og:url in {changed} files")


if __name__ == "__main__":
    main()
