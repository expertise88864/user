#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Static performance guardrails for first-paint/CWV-sensitive assets."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", ".next", "out", "dist", "__pycache__"}
# Single source of truth: _normalize_css_links.ASSET_VERSION. Mirrored here
# because this checker runs standalone in CI. Import to stay in sync.
try:
    from _normalize_css_links import ASSET_VERSION  # type: ignore
except Exception:
    ASSET_VERSION = "202605170800"  # fallback if import path is broken

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
# Pages that actually fetch the Google Fonts stylesheet. Only those owe the
# hints; nothing else should be nagged into adding them.
GOOGLE_FONTS_CSS_RE = re.compile(
    r'<link\b[^>]+href="https://fonts\.googleapis\.com/css2\?[^"]*"[^>]*rel="stylesheet"'
    r'|<link\b[^>]+rel="stylesheet"[^>]*href="https://fonts\.googleapis\.com/css2\?[^"]*"',
    re.I,
)
# The gstatic hint is worthless without crossorigin: font files are fetched in
# CORS mode, so a hint that opens a non-CORS connection warms the wrong socket
# and the browser opens a second one anyway.
GSTATIC_PRECONNECT_RE = re.compile(
    r'<link\s+rel="preconnect"\s+href="https://fonts\.gstatic\.com"([^>]*)>', re.I)


# Anti-vacuity floor. Measured 2026-08-01: the tree serves 134 HTML files
# (both locales plus the utility pages). 100 leaves room for pages being
# retired without the floor firing spuriously, while still catching a scan
# that has stopped finding the corpus.
MIN_HTML_FILES = 100


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
        # CODE_REVIEW Phase 5 — measure the DEPLOYED byte size. git stores LF
        # and Vercel/CI serve LF, but a local Windows checkout (and _minify's
        # text-mode write) leaves CRLF on disk, where each \r inflates
        # stat().st_size by ~1.4 KB for this file — enough to fail the budget on
        # bytes that never ship. Normalize CRLF→LF before measuring so the gate
        # reflects the served artifact and matches CI (already LF).
        size_kb = len(minified.read_bytes().replace(b"\r\n", b"\n")) / 1024
        # 2026-05-19 — bumped 72→75 KB after CODE_REVIEW refactor batch
        # added:
        #   - initCmdK bootstrap (idle-queue pre-binding, ~0.4 KB)
        #   - 5× ensure*Bundle promise-reset catch handlers (~0.5 KB)
        #   - LCP/CLS/INP observer disconnect tracking (~0.4 KB)
        #   - MutationObserver scope narrowing (~0.3 KB)
        #   - SW update timer rewrite + warn-on-fail catches (~0.6 KB)
        # All necessary for INP / memory-leak / race fixes. Still 25 %
        # under the 100 KB shared-runtime threshold that meaningfully
        # impacts mobile cold start.
        if size_kb > 75:
            errors.append(f"blog/blog-shared.min.js is {size_kb:.1f}KB; keep the shared runtime under 75KB or split features")

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

    html_files = iter_html_files()
    for path in html_files:
        rel = path.relative_to(ROOT).as_posix()
        src = path.read_text(encoding="utf-8")
        if BLOG_SHARED_PRELOAD_RE.search(src):
            errors.append(f"{rel}: do not head-preload the large deferred blog-shared runtime")
        for version in BLOG_SHARED_VERSION_RE.findall(src):
            if version != ASSET_VERSION:
                errors.append(f"{rel}: blog-shared asset version is {version}, expected {ASSET_VERSION}")
        # …and the same one-sided hole as the font hints below: the loop above
        # can only complain about a version it FOUND. Three articles referenced
        # /blog/blog-shared.js — the unminified bundle, 120KB against 77KB, with
        # no ?v= at all — so the version check never ran on them and a returning
        # reader could hold that copy indefinitely. _normalize_css_links.py
        # cannot stamp them either: BLOG_SHARED_SRC_RE requires `.min.js`.
        for tag in BLOG_SHARED_SCRIPT_RE.findall(src):
            if not BLOG_SHARED_VERSION_RE.search(tag):
                errors.append(
                    f"{rel}: loads blog-shared without the versioned minified "
                    f"URL — use /blog/blog-shared.min.js?v={ASSET_VERSION}; "
                    f"got {tag.strip()[:80]}")
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
        # This check used to fire only on count > 1, so ZERO hints passed in
        # silence — which is how blog/ai-dermatology-roles.html shipped loading
        # the Google Fonts stylesheet with no preconnect at all while the other
        # 129 pages had both. A one-sided guard reads as coverage it does not
        # have. Measured before locking: 130 pages load the stylesheet, 128 had
        # both hints, 0 were missing crossorigin.
        if GOOGLE_FONTS_CSS_RE.search(src):
            for host in ("googleapis", "gstatic"):
                if not font_hints.get(host):
                    errors.append(
                        f"{rel}: loads the Google Fonts stylesheet with no "
                        f"preconnect to fonts.{host}.com — the render-blocking "
                        f"request pays for DNS and TLS it could have overlapped")
            for attrs in GSTATIC_PRECONNECT_RE.findall(src):
                if "crossorigin" not in attrs.lower():
                    errors.append(
                        f"{rel}: fonts.gstatic.com preconnect is missing "
                        f"crossorigin — font files are fetched in CORS mode, so "
                        f"this warms a connection the browser cannot reuse")
        script_count = len(BLOG_SHARED_SCRIPT_RE.findall(src))
        is_noindex = bool(re.search(r'<meta\s+name="robots"\s+content="[^"]*\bnoindex\b', src, re.I))
        if script_count > 1:
            errors.append(f"{rel}: blog-shared runtime is loaded {script_count} times")
        if is_noindex and "blog-shared.min.js" in src and "DN.initBlog" not in src:
            errors.append(f"{rel}: noindex page references blog-shared without using DN.initBlog")

    # CODE_REVIEW 2026-08-01 — every per-page rule above lives inside that one
    # loop, and nothing recorded how many pages it actually saw. If discovery
    # ever returns nothing, `errors` stays empty and this prints [OK]: a broken
    # scan would read as a clean audit. Every other guard in this file was just
    # made two-sided; the scan itself was still one-sided.
    if len(html_files) < MIN_HTML_FILES:
        errors.append(
            f"only {len(html_files)} HTML file(s) discovered (expected >= "
            f"{MIN_HTML_FILES}) — the scan is broken, so a pass here would "
            f"mean nothing")

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
