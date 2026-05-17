#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Normalize local CSS links to CSP-friendly stylesheet links."""

from __future__ import annotations

import os
import re


ROOT = os.path.dirname(os.path.abspath(__file__))
ASSET_VERSION = "202605171600"

PRELOAD_TW_MINI_RE = re.compile(
    r'<link\s+rel="preload"\s+as="style"\s+href="([^"]*tw-mini\.css[^"]*)"\s+'
    r'onload="this\.onload=null;this\.rel=\'stylesheet\'"\s*/?>'
    r'\s*<noscript><link\s+rel="stylesheet"\s+href="\1"\s*/?></noscript>',
    re.IGNORECASE,
)
PRELOAD_TW_MINI_SINGLE_RE = re.compile(
    r'<link\s+rel="preload"\s+as="style"\s+href="([^"]*tw-mini\.css[^"]*)"\s+'
    r'onload="this\.onload=null;this\.rel=\'stylesheet\'"\s*/?>',
    re.IGNORECASE,
)
PRELOAD_GOOGLE_FONTS_RE = re.compile(
    r'\s*<link\s+rel="preload"\s+as="style"\s+href="https://fonts\.googleapis\.com/css2\?[^"]+"\s*/?>',
    re.IGNORECASE,
)
FONT_PRECONNECT_RE = re.compile(
    r'<link\s+rel="preconnect"\s+href="https://fonts\.(?:googleapis|gstatic)\.com"(?:\s+crossorigin)?\s*/?>',
    re.IGNORECASE,
)
PRELOAD_BLOG_SHARED_RE = re.compile(
    r'\s*<link\s+rel="(?:modulepreload|preload)"(?:\s+as="script")?\s+href="[^"]*blog-shared(?:\.min)?\.js[^"]*"\s*/?>',
    re.IGNORECASE,
)
BLOG_SHARED_SCRIPT_RE = re.compile(
    r'\s*<script\s+src="[^"]*/blog/blog-shared(?:\.min)?\.js[^"]*"\s+defer></script>',
    re.IGNORECASE,
)
BLOG_SHARED_SRC_RE = re.compile(r'(/blog/blog-shared\.min\.js)(?:\?v=\d+)?')


def html_files() -> list[str]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in {'.git', 'node_modules'}]
        for filename in filenames:
            if filename.endswith('.html'):
                files.append(os.path.join(dirpath, filename))
    return files


def normalize_file(path: str) -> bool:
    with open(path, 'r', encoding='utf-8') as fp:
        src = fp.read()
    next_src = PRELOAD_TW_MINI_RE.sub(
        lambda m: f'<link rel="stylesheet" href="{m.group(1)}">',
        src,
    )
    next_src = PRELOAD_TW_MINI_SINGLE_RE.sub(
        lambda m: f'<link rel="stylesheet" href="{m.group(1)}">',
        next_src,
    )
    next_src = PRELOAD_GOOGLE_FONTS_RE.sub("", next_src)
    next_src = PRELOAD_BLOG_SHARED_RE.sub("", next_src)
    next_src = BLOG_SHARED_SRC_RE.sub(rf"\1?v={ASSET_VERSION}", next_src)
    if "DN.initBlog" not in next_src:
        next_src = BLOG_SHARED_SCRIPT_RE.sub("", next_src)
    seen_fonts: set[str] = set()

    def keep_first_font_preconnect(match: re.Match[str]) -> str:
        tag = match.group(0)
        key = "gstatic" if "fonts.gstatic.com" in tag else "googleapis"
        if key in seen_fonts:
            return ""
        seen_fonts.add(key)
        return tag

    next_src = FONT_PRECONNECT_RE.sub(keep_first_font_preconnect, next_src)
    if next_src == src:
        return False
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(next_src)
    return True


def main() -> None:
    changed = sum(1 for path in html_files() if normalize_file(path))
    print(f'Normalized CSS links in {changed} files')


if __name__ == '__main__':
    main()
