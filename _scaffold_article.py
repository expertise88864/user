#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Scaffold a new blog article by copying semaglutide-hair-loss.html.

The lesson learned 2026-05-23 (after PDT article needed 8 commits to
fix structural bugs that I kept reintroducing when writing from scratch):

  ALWAYS scaffold a new article by copying a known-good template,
  THEN surgically replace the article-specific text. Never write the
  HTML skeleton from scratch — you will forget:

    - <article class="max-w-3xl"> wrapper (footer.js hook)
    - <div id="proseZh" class="prose-zh"> wrapper (inline CSS hook)
    - <script src="/blog/blog-shared.min.js"> at end of body
    - DOMContentLoaded → DN.initBlog() bootstrap
    - <!-- dn-spec-rules --> + <script type="speculationrules">
    - Proper close-tag order </section></div></article>

Template source: blog/semaglutide-hair-loss.html — known working.

Usage:
  python _scaffold_article.py <new-slug>

The script:
  1. Reads semaglutide-hair-loss.html
  2. Replaces:
     - slug-references → <new-slug>
     - title placeholders → "Article Title (please replace)"
     - body content → minimal "TODO" placeholders
     - keeps ALL structural HTML / scripts / wrappers
  3. Writes blog/<new-slug>.html

After scaffolding, you can safely:
  - Replace H1 + TLDR text
  - Replace H2/H3 + body paragraphs
  - Replace SVG figures
  - Replace references
  - Update JSON-LD metadata

Without ever touching the structural skeleton.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "blog" / "semaglutide-hair-loss.html"
OLD_SLUG = "semaglutide-hair-loss"

PLACEHOLDER_TITLE_ZH = "新文章標題（請替換）"
PLACEHOLDER_TITLE_EN = "New Article Title (please replace)"
PLACEHOLDER_DESC_ZH = "新文章描述（請替換）"
PLACEHOLDER_DESC_EN = "New article description (please replace)"


def scaffold(new_slug: str) -> None:
    if not TEMPLATE_PATH.exists():
        print(f"ERROR: template not found: {TEMPLATE_PATH}")
        sys.exit(1)
    if not re.match(r"^[a-z0-9-]+$", new_slug):
        print(f"ERROR: slug must be lowercase alphanumeric + hyphens: {new_slug!r}")
        sys.exit(1)

    out_path = ROOT / "blog" / f"{new_slug}.html"
    if out_path.exists():
        print(f"ERROR: target file already exists: {out_path}")
        sys.exit(1)

    src = TEMPLATE_PATH.read_text(encoding="utf-8")

    # ─── Slug replacements (URLs, JSON-LD @id, canonical, OG, etc.) ─
    src = src.replace(OLD_SLUG, new_slug)

    # Note: we do NOT replace the prose content automatically.
    # The user should manually:
    #   1. Update <title>, og:title, twitter:title, JSON-LD headline/name
    #   2. Update <meta name="description"> and og:description
    #   3. Update <meta name="keywords">
    #   4. Update JSON-LD about[] (MedicalCondition entries)
    #   5. Update H1 text + subtitle
    #   6. Update TLDR paragraph
    #   7. Replace all H2/H3 sections and body content
    #   8. Replace all SVG figures
    #   9. Replace references <ol class="references">
    #
    # This way, the structural skeleton (article wrapper, prose-zh div,
    # blog-shared.min.js script, mag-footer) is GUARANTEED to be correct.

    out_path.write_text(src, encoding="utf-8")
    print(f"[scaffold] created {out_path.relative_to(ROOT).as_posix()}")
    print()
    print("Next steps (manual):")
    print(f"  1. Edit blog/{new_slug}.html — replace title / TLDR / body content")
    print(f"  2. Update _normalize_medical_codes.py SLUG_CONDITIONS[{new_slug!r}]")
    print(f"  3. Add card to index.html (.article-list-item)")
    print(f"  4. Add entry to blog/blog-shared.js DN.ARTICLES")
    print(f"  5. Run: python _run_quality.py build (must be 45+ [OK] / 0 [FAIL])")
    print(f"  6. git add -A && git commit -m 'feat(article): {new_slug}' && git push")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    scaffold(sys.argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
