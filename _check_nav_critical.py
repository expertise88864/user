#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CI guard: every page with the sticky nav must inline its critical CSS.

WHY (2026-05-26): the sticky header nav (`class="dn-nav"`) is the most
above-the-fold element on every page. Its layout CSS used to live ONLY in
the externally-versioned assets/dn-below-fold.css, and twice the homepage
nav rendered as an unstyled run-together blob because a cached copy of that
CSS predated its dn-nav rules. The fix was `_inject_nav_critical.py`, which
inlines the nav layout CSS as `<style id="dn-nav-critical">` into every
page that has the nav — making markup + critical CSS atomic.

That inject step runs LAST in _run_quality.py's REGEN_STEPS. If anyone ever
reorders the build so a head-rewriting step runs after it (or removes the
step), the inline block would silently disappear and the exact stale-nav
bug would return with no error. This check makes that regression loud:
any HTML containing `class="dn-nav"` MUST also contain
`id="dn-nav-critical"`.

Run as part of CHECK_STEPS.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "__pycache__", "astro-rewrite"}


def main() -> int:
    missing: list[str] = []
    checked = 0
    for fp in ROOT.rglob("*.html"):
        if any(part in SKIP_DIRS for part in fp.parts):
            continue
        html = fp.read_text(encoding="utf-8", errors="replace")
        if 'class="dn-nav"' not in html:
            continue  # page has no sticky nav (e.g. simple-header articles, admin shells)
        checked += 1
        if 'id="dn-nav-critical"' not in html:
            missing.append(str(fp.relative_to(ROOT)).replace("\\", "/"))

    if missing:
        print("[FAIL] nav-critical audit: pages with class=\"dn-nav\" but no inline "
              "<style id=\"dn-nav-critical\"> block (run _inject_nav_critical.py):")
        for m in missing:
            print(f"  - {m}")
        return 1

    print(f"[OK] nav-critical audit passed ({checked} dn-nav pages all carry the inline block)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
