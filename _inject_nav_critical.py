#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inline the critical sticky-nav CSS into every page's <head>.

WHY THIS EXISTS (2026-05-26):
  The sticky header nav (`.dn-nav`, `.dn-nav-link`, `.dn-nav-icon`,
  `.dn-nav-burger`) is the most above-the-fold element on every page,
  yet its CSS used to live ONLY in the external, separately-versioned
  `assets/dn-below-fold.css`. Twice the homepage nav rendered as an
  unstyled run-together blob because the browser/SW served a cached
  copy of that CSS that predated the dn-nav rules (the file content was
  edited 2026-05-24 without bumping its `?v=` query string, so the
  cache-first SW never re-fetched it). HTML and its critical nav CSS had
  independent cache lifetimes and could desync.

  Fix: ship the nav layout CSS INSIDE the HTML document as an inline
  `<style id="dn-nav-critical">`. Now the nav markup and its critical
  styling are atomic — same document, same cache entry — and can never
  desync from an external file's version. `dn-below-fold.css` still
  carries the full styling (transitions, hover refinements); this inline
  block carries only the layout-critical subset needed to render the nav
  correctly with zero external dependency, on both desktop and mobile.

Run after any nav markup/CSS change, and as part of `_run_quality.py build`.
Idempotent: replaces the existing block in place.

Usage:
  python _inject_nav_critical.py
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent

# Layout-critical nav CSS — faithful minified subset of the dn-nav rules
# in assets/dn-below-fold.css (desktop block + mobile @media). var()
# fallbacks (#4d6358 / #dcd5c8 / #eaf6f3) make it self-sufficient even
# before the article/root :root variables are parsed.
NAV_CSS = (
    ".dn-nav{display:flex;align-items:center;gap:6px;flex-shrink:0;margin-left:auto}"
    ".dn-nav-link{display:inline-flex;align-items:center;padding:6px 12px;border-radius:9999px;"
    "font-size:12.5px;font-weight:600;color:var(--teal-deep,#4d6358);text-decoration:none;white-space:nowrap}"
    ".dn-nav-link:hover{background:var(--mint-soft,#eaf6f3);color:#0e7c86}"
    ".dn-nav .dn-nav-divider{width:1px;height:20px;background:var(--border,#dcd5c8);margin:0 4px}"
    ".dn-nav-icon{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;"
    "border-radius:9999px;color:var(--teal-deep,#4d6358);background:transparent;border:0;cursor:pointer;"
    "font-size:15px;line-height:1;padding:0}"
    ".dn-nav-icon:hover{background:var(--mint-soft,#eaf6f3)}"
    '.dn-nav-icon[id="dn-nav-support"]{color:#0c5159}'
    ".dn-nav .lang-select{margin:0 0 0 6px;padding:6px 22px 6px 10px;min-height:32px;font-size:11.5px}"
    ".dn-nav-burger{display:none;align-items:center;justify-content:center;width:38px;height:38px;"
    "border-radius:9999px;color:var(--teal-deep,#4d6358);background:transparent;border:0;cursor:pointer;"
    "flex-shrink:0;margin-left:auto}"
    "@media(max-width:768px){"
    ".dn-nav{display:none;position:fixed;top:64px;right:0;left:0;background:rgba(250,247,242,.98);"
    "flex-direction:column;align-items:stretch;padding:14px 18px;border-bottom:1px solid var(--border,#dcd5c8);gap:2px}"
    ".dn-nav.open,.dn-nav.dn-nav-open{display:flex}"
    ".dn-nav-link{padding:11px 14px;font-size:14px;border-radius:10px;justify-content:flex-start}"
    ".dn-nav-icon{width:auto;height:auto;padding:11px 14px;border-radius:10px;justify-content:flex-start;gap:10px;font-size:14px}"
    ".dn-nav .dn-nav-divider{display:none}"
    ".dn-nav-burger{display:inline-flex}"
    "}"
)

BLOCK = f'<style id="dn-nav-critical">{NAV_CSS}</style>'

# Idempotency: strip any prior injection before re-inserting.
BLOCK_RE = re.compile(r'<style id="dn-nav-critical">.*?</style>', re.DOTALL)

SKIP_DIRS = {".git", "node_modules", "__pycache__", "astro-rewrite"}
# Pages with no sticky dn-nav header — skip to avoid dead CSS.
SKIP_FILES = {"offline.html", "404.html", "reset-sw.html"}


def has_nav(html: str) -> bool:
    return 'class="dn-nav"' in html or "class='dn-nav'" in html


def process(fp: Path) -> bool:
    html = fp.read_text(encoding="utf-8")
    if "</head>" not in html:
        return False
    if not has_nav(html):
        # No sticky nav on this page (e.g. admin shells) — strip any stale
        # block but don't add one.
        stripped = BLOCK_RE.sub("", html)
        if stripped != html:
            fp.write_text(stripped, encoding="utf-8")
            return True
        return False
    # Remove any prior block, then inject right before </head>.
    cleaned = BLOCK_RE.sub("", html)
    new = cleaned.replace("</head>", BLOCK + "</head>", 1)
    if new != html:
        fp.write_text(new, encoding="utf-8")
        return True
    return False


def main() -> int:
    changed = 0
    scanned = 0
    for fp in ROOT.rglob("*.html"):
        if any(part in SKIP_DIRS for part in fp.parts):
            continue
        if fp.name in SKIP_FILES:
            continue
        scanned += 1
        if process(fp):
            changed += 1
    print(f"[nav-critical] injected/updated inline nav CSS in {changed} of {scanned} HTML files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
