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

# Legacy articles whose structure pre-dates the proseZh / prose-zh wrapper
# requirement (they have their own bespoke CSS). Skip the prose-wrapper
# check for these. The blog-shared.min.js check still applies.
PROSE_WRAPPER_LEGACY_SKIP = {"blog/atopic-dermatitis-overview.html"}


ARTICLE_WRAPPER_RE = re.compile(
    r'<article\b[^>]*class="[^"]*\bmax-w-3xl\b[^"]*"', re.IGNORECASE
)
PROSE_WRAPPER_RE = re.compile(
    r'<div\b[^>]*\b(?:id="prose(?:Zh|En)"|class="[^"]*\bprose(?:-zh|-en|\b)[^"]*")',
    re.IGNORECASE,
)


def check_article(path: Path) -> list[str]:
    rel = path.relative_to(ROOT).as_posix()
    if rel in SKIP_FILES:
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    # Skip if noindex (admin / placeholder pages may not need the runtime)
    if re.search(r'<meta\s+name="robots"\s+content="[^"]*noindex', text, re.I):
        return []
    errs = []
    if not RUNTIME_RE.search(text):
        errs.append(f"{rel}: missing <script src=\"/blog/blog-shared(.min).js\">")
    # The <article class="max-w-3xl"> is the hook for blog-article-footer.js
    # (7 inject functions all use document.querySelector('article.max-w-3xl')).
    # Without it the related-articles, share toolbar, author bio, etc. all
    # silently fail to render.
    if not ARTICLE_WRAPPER_RE.search(text):
        errs.append(f"{rel}: missing <article class=\"max-w-3xl ...\"> wrapper")
    # The <div id="proseZh" class="prose-zh"> (or proseEn / prose-en for EN
    # mirrors) is the hook for the inline CSS rules `.prose-zh h2 {
    # border-left: ... }` etc. Without it the H2/H3 lose their distinctive
    # styling and look like body text.
    if rel not in PROSE_WRAPPER_LEGACY_SKIP and not PROSE_WRAPPER_RE.search(text):
        errs.append(f"{rel}: missing <div id=\"proseZh\" class=\"prose-zh\"> (or proseEn/prose-en) wrapper")
    # Order check: related-articles <nav> must come BEFORE <footer>, not
    # after. If after, the related-articles section appears at the very
    # bottom of the page (below the dark footer) which looks like a
    # broken layout. 2026-05-23 — PDT article shipped with footer before
    # related-nav until manually reordered.
    a = text.find('</article>')
    nav = text.find('<nav id="dn-related-static"')
    foot = text.find('<footer class="mag-footer"')
    if a > 0 and nav > 0 and foot > 0:
        if foot < nav:
            errs.append(
                f"{rel}: <footer class=\"mag-footer\"> appears BEFORE <nav id=\"dn-related-static\">. "
                f"Correct order is </article> → <nav related> → </main> → <footer>."
            )
    return errs


def main() -> int:
    errors: list[str] = []
    for folder in (BLOG, EN_BLOG):
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.html")):
            errors.extend(check_article(path))
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
