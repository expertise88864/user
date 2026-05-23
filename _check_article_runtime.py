#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verify every blog article loads the blog-shared runtime script.

Without `<script src="/blog/blog-shared.js" defer>` (or the `.min.js`
variant), the article loses everything that hydrates from DN:

- dn-nav-link / 漢堡選單 / 語言切換 / 主題 toggle
- DN.applyTextOnly() — EN visitors stuck on ZH
- DN.bindArticleHub() — relateds don't render
- Site search (Ctrl+K)

This bug bit twice in May 2026 (semaglutide-hair-loss + photodynamic-
therapy-overview). Both manifested as a broken header + frozen language
toggle. This check catches the regression at build time, not after a
user opens the article and sees the broken layout.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
BLOG = ROOT / "blog"
EN_BLOG = ROOT / "en" / "blog"

# Match `<script ... src="/blog/blog-shared.js..." ...>` or `.min.js`
RUNTIME_RE = re.compile(
    r'<script\b[^>]*\bsrc="[^"]*?/blog/blog-shared(?:\.min)?\.js[^"]*"[^>]*>',
    re.IGNORECASE,
)

# Articles that don't need the runtime (e.g., index pages, topic map)
# blog/index.html and blog/topics.html load it themselves elsewhere
SKIP_FILES = {"blog/index.html", "blog/topics.html"}


def check_article(path: Path) -> str | None:
    rel = path.relative_to(ROOT).as_posix()
    if rel in SKIP_FILES:
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    # Skip if noindex (admin / placeholder pages may not need the runtime)
    if re.search(r'<meta\s+name="robots"\s+content="[^"]*noindex', text, re.I):
        return None
    if not RUNTIME_RE.search(text):
        return f"{rel}: missing <script src=\"/blog/blog-shared(.min).js\">"
    return None


def main() -> int:
    errors: list[str] = []
    for folder in (BLOG, EN_BLOG):
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.html")):
            err = check_article(path)
            if err:
                errors.append(err)
    if errors:
        for e in errors:
            print(f"  {e}")
        print(f"\n[FAIL] Article runtime audit: {len(errors)} article(s) missing blog-shared script.")
        print("Fix: add <script src=\"/blog/blog-shared.min.js?v=ASSET_VERSION\" defer></script>")
        print("     + <script>document.addEventListener('DOMContentLoaded',function(){if(window.DN)DN.initBlog({});});</script>")
        print("     before <!-- dn-spec-rules --> at the end of <body>.")
        return 1
    print("[OK] Article runtime audit passed (all articles load blog-shared script)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
