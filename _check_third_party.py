#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit third-party analytics/ads loading policy."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
EAGER_CLARITY_RE = re.compile(r'<script\s+type="text/javascript">[\s\S]*?www\.clarity\.ms/tag/[\s\S]*?</script>', re.I)
THIRD_PARTY_RE = re.compile(r'pagead2\.googlesyndication\.com/pagead/js/adsbygoogle\.js|googletagmanager\.com/gtag/js|www\.clarity\.ms/tag', re.I)


def main() -> int:
    errors: list[str] = []
    for path in sorted(ROOT.rglob("*.html")):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        src = path.read_text(encoding="utf-8")
        is_noindex = bool(re.search(r'<meta\s+name="robots"\s+content="[^"]*\bnoindex\b', src, re.I))
        if is_noindex and THIRD_PARTY_RE.search(src):
            errors.append(f"{rel}: noindex/internal page should not load analytics or ads")
            continue
        if EAGER_CLARITY_RE.search(src):
            errors.append(f"{rel}: eager Clarity script found; use idle third-party loader only")
        if re.search(r'<link\s+rel="(?:dns-prefetch|preconnect)"\s+href="(?:https?:)?//(?:pagead2\.googlesyndication\.com|www\.googletagmanager\.com|www\.clarity\.ms)"', src, re.I):
            errors.append(f"{rel}: third-party dns-prefetch/preconnect should not compete with critical rendering")
        if "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" in src:
            has_local_guard = "function isLocalStaticHost()" in src or "localhost|127\\.0\\.0\\.1" in src
            if not has_local_guard:
                errors.append(f"{rel}: third-party loader missing localhost guard")
            if "isBot() || isLocalStaticHost()" not in src and "localhost|127\\.0\\.0\\.1" not in src:
                errors.append(f"{rel}: third-party load() should skip localhost/static tests")

    if errors:
        print("[FAIL] Third-party loading audit found issues:")
        for error in errors[:160]:
            print(" - " + error)
        if len(errors) > 160:
            print(f" ... {len(errors) - 160} more")
        return 1

    print("[OK] Third-party loading audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
