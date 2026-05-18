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

SEARCH_LINK = (
    '<link rel="search" type="application/opensearchdescription+xml" '
    'title="ChenDermatologist" href="/opensearch.xml" />'
)

EXISTING_RE = re.compile(
    r'<link[^>]+rel="search"[^>]*>',
    re.IGNORECASE,
)

SKIP_NAMES = {"404.html", "offline.html", "reset-sw.html", "admin.html"}
SKIP_DIRS = {".git", "node_modules", "pagefind", "admin"}


def inject_one(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    if EXISTING_RE.search(src):
        return False  # already injected
    # Insert right before </head> for natural grouping with other links
    head_close = src.find("</head>")
    if head_close == -1:
        return False
    next_src = src[:head_close] + SEARCH_LINK + src[head_close:]
    if next_src == src:
        return False
    path.write_text(next_src, encoding="utf-8")
    return True


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
