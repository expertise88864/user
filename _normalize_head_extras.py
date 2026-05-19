#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inject head-level discovery links that aren't worth a dedicated normalizer.

Currently injects:

  <link rel="search" type="application/opensearchdescription+xml"
        title="ChenDermatologist" href="/opensearch.xml">

When Firefox / Edge / Brave / Vivaldi users browse to any page on the
site, the browser detects the OpenSearch descriptor and shows an
"Add Search Engine" affordance in the address bar. Adding the site
to the browser search bar gives readers a one-keystroke path back
to the site — recurring visits that wouldn't happen otherwise.

Idempotent via dn-search-link marker. Skips admin / 404 / offline /
reset-sw and any page where the link is already present.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent

# Pull current asset version from the canonical source so re-injects
# always stamp the latest cache-bust. Avoid hardcoding.
try:
    sys.path.insert(0, str(ROOT))
    from _normalize_css_links import ASSET_VERSION as _ASSET_VERSION
except Exception:
    _ASSET_VERSION = "202605191800"

SEARCH_LINK = (
    '<link rel="search" type="application/opensearchdescription+xml" '
    'title="ChenDermatologist" href="/opensearch.xml" />'
)

# CODE_REVIEW / Tier 1A — official web-vitals library (attribution build).
# Self-hosted at /assets/web-vitals.iife.js (12.5 KB unminified, ~3.5 KB
# brotli). Loaded with defer; exposes `window.webVitals` object whose
# onLCP/onCLS/onINP/onFCP/onTTFB callbacks include `.attribution` with
# the offending DOM element + breakdown timings.
#
# Wrapped in dn-vitals-loader marker so re-runs are idempotent.
VITALS_TAG = (
    '<!-- dn-vitals-loader -->'
    f'<script defer src="/assets/web-vitals.iife.js?v={_ASSET_VERSION}"></script>'
)

EXISTING_SEARCH_RE = re.compile(
    r'<link[^>]+rel="search"[^>]*>',
    re.IGNORECASE,
)
EXISTING_VITALS_RE = re.compile(
    r'<!--\s*dn-vitals-loader\s*-->\s*<script[^>]+web-vitals[^>]*></script>',
    re.IGNORECASE,
)
# Legacy non-canonical alias (older runs without the marker comment).
LEGACY_VITALS_RE = re.compile(
    r'<script[^>]+src="/assets/web-vitals(?:\.iife)?\.js[^"]*"[^>]*></script>',
    re.IGNORECASE,
)

SKIP_NAMES = {"404.html", "offline.html", "reset-sw.html", "admin.html"}
SKIP_DIRS = {".git", "node_modules", "pagefind", "admin"}


def inject_one(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    changed = False

    # 1. OpenSearch <link rel="search"> — once per page
    if not EXISTING_SEARCH_RE.search(src):
        head_close = src.find("</head>")
        if head_close != -1:
            src = src[:head_close] + SEARCH_LINK + src[head_close:]
            changed = True

    # 2. web-vitals attribution build — strip any prior version (old
    # cache-busted URL OR legacy non-marker tag), then re-insert with
    # current asset version.
    src = EXISTING_VITALS_RE.sub("", src)
    src = LEGACY_VITALS_RE.sub("", src)
    head_close = src.find("</head>")
    if head_close != -1:
        src = src[:head_close] + VITALS_TAG + src[head_close:]
        changed = True

    if changed:
        path.write_text(src, encoding="utf-8")
        return True
    return False


def main() -> int:
    targets: list[Path] = []
    for fp in sorted(ROOT.rglob("*.html")):
        parts = fp.relative_to(ROOT).parts
        if any(p in SKIP_DIRS for p in parts):
            continue
        if fp.name in SKIP_NAMES:
            continue
        targets.append(fp)
    changed = sum(1 for fp in targets if inject_one(fp))
    print(f"Injected <link rel='search'> into {changed} of {len(targets)} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
