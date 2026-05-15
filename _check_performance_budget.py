#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Static performance guardrails for first-paint/CWV-sensitive assets."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", ".next", "out", "dist", "__pycache__"}
ASSET_VERSION = "202605120530"

BLOG_SHARED_PRELOAD_RE = re.compile(
    r'<link\s+rel="(?:modulepreload|preload)"(?:\s+as="script")?\s+href="[^"]*blog-shared(?:\.min)?\.js',
    re.I,
)
BLOG_SHARED_SCRIPT_RE = re.compile(
    r'<script\b[^>]+\bsrc="[^"]*/blog/blog-shared(?:\.min)?\.js[^"]*"[^>]*></script>',
    re.I,
)
BLOG_SHARED_VERSION_RE = re.compile(r'/blog/blog-shared\.min\.js\?v=(\d+)')
BLOG_DIAGRAMS_EAGER_RE = re.compile(
    r'<(?:script|link)\b[^>]+\b(?:src|href)="[^"]*/blog/blog-diagrams(?:\.min)?\.js[^"]*"',
    re.I,
)
BLOG_CALCULATORS_EAGER_RE = re.compile(
    r'<(?:script|link)\b[^>]+\b(?:src|href)="[^"]*/blog/blog-calculators(?:\.min)?\.js[^"]*"',
    re.I,
)
BLOG_HUB_EAGER_RE = re.compile(
    r'<(?:script|link)\b[^>]+\b(?:src|href)="[^"]*/blog/blog-hub(?:\.min)?\.js[^"]*"',
    re.I,
)
BLOG_ARTICLE_READING_EAGER_RE = re.compile(
    r'<(?:script|link)\b[^>]+\b(?:src|href)="[^"]*/blog/blog-article-reading(?:\.min)?\.js[^"]*"',
    re.I,
)
BLOG_ARTICLE_VISUALS_EAGER_RE = re.compile(
    r'<(?:script|link)\b[^>]+\b(?:src|href)="[^"]*/blog/blog-article-visuals(?:\.min)?\.js[^"]*"',
    re.I,
)
BLOG_ARTICLE_FOOTER_EAGER_RE = re.compile(
    r'<(?:script|link)\b[^>]+\b(?:src|href)="[^"]*/blog/blog-article-footer(?:\.min)?\.js[^"]*"',
    re.I,
)
PRELOAD_GOOGLE_FONTS_RE = re.compile(
    r'<link\s+rel="preload"\s+as="style"\s+href="https://fonts\.googleapis\.com/css2\?[^"]+"',
    re.I,
)
FONT_PRECONNECT_RE = re.compile(
    r'<link\s+rel="preconnect"\s+href="https://fonts\.(googleapis|gstatic)\.com"',
    re.I,
)


def iter_html_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.html"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        files.append(path)
    return files


def main() -> int:
    errors: list[str] = []

    minified = ROOT / "blog" / "blog-shared.min.js"
    if minified.exists():
        size_kb = minified.stat().st_size / 1024
        if size_kb > 72:
            errors.append(f"blog/blog-shared.min.js is {size_kb:.1f}KB; keep the shared runtime under 72KB or split features")

    sw_path = ROOT / "sw.js"
    if sw_path.exists():
        sw_src = sw_path.read_text(encoding="utf-8")
        for bundle in (
            "blog-hub",
            "blog-article-reading",
            "blog-diagrams",
            "blog-calculators",
            "blog-article-visuals",
            "blog-article-footer",
        ):
            if f"'/blog/{bundle}.min.js'" in sw_src or f'"/blog/{bundle}.min.js"' in sw_src:
                errors.append(f"sw.js: {bundle}.min.js should be runtime-cached on demand, not precached during install")

    for path in iter_html_files():
        rel = path.relative_to(ROOT).as_posix()
        src = path.read_text(encoding="utf-8")
        if BLOG_SHARED_PRELOAD_RE.search(src):
            errors.append(f"{rel}: do not head-preload the large deferred blog-shared runtime")
        for version in BLOG_SHARED_VERSION_RE.findall(src):
            if version != ASSET_VERSION:
                errors.append(f"{rel}: blog-shared asset version is {version}, expected {ASSET_VERSION}")
        if BLOG_DIAGRAMS_EAGER_RE.search(src):
            errors.append(f"{rel}: blog-diagrams should stay dynamically loaded only on article pages that need it")
        if BLOG_CALCULATORS_EAGER_RE.search(src):
            errors.append(f"{rel}: blog-calculators should stay dynamically loaded only when calculators are injected")
        if BLOG_HUB_EAGER_RE.search(src):
            errors.append(f"{rel}: blog-hub should stay dynamically loaded only on hub/spotlight pages")
        if BLOG_ARTICLE_READING_EAGER_RE.search(src):
            errors.append(f"{rel}: blog-article-reading should stay dynamically loaded only on article pages")
        if BLOG_ARTICLE_VISUALS_EAGER_RE.search(src):
            errors.append(f"{rel}: blog-article-visuals should stay dynamically loaded only on article pages")
        if BLOG_ARTICLE_FOOTER_EAGER_RE.search(src):
            errors.append(f"{rel}: blog-article-footer should stay dynamically loaded only on article pages")
        if PRELOAD_GOOGLE_FONTS_RE.search(src):
            errors.append(f"{rel}: Google Fonts CSS preload is unused unless the same URL is applied as a stylesheet")
        font_hints: dict[str, int] = {}
        for hint in FONT_PRECONNECT_RE.findall(src):
            font_hints[hint] = font_hints.get(hint, 0) + 1
        for host, count in font_hints.items():
            if count > 1:
                errors.append(f"{rel}: duplicate fonts.{host}.com preconnect appears {count} times")
        script_count = len(BLOG_SHARED_SCRIPT_RE.findall(src))
        is_noindex = bool(re.search(r'<meta\s+name="robots"\s+content="[^"]*\bnoindex\b', src, re.I))
        if script_count > 1:
            errors.append(f"{rel}: blog-shared runtime is loaded {script_count} times")
        if is_noindex and "blog-shared.min.js" in src and "DN.initBlog" not in src:
            errors.append(f"{rel}: noindex page references blog-shared without using DN.initBlog")

    if errors:
        print("[FAIL] Performance budget audit found issues:")
        for error in errors[:160]:
            print(" - " + error)
        if len(errors) > 160:
            print(f" ... {len(errors) - 160} more")
        return 1

    print("[OK] Performance budget audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
