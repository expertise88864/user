#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inject `desc` + `desc_en` fields into DN.ARTICLES entries from each
article's <meta name="description"> tag.

Why: blog-hub.js renders dynamic article-list cards from DN.ARTICLES,
but the catalog only carries slug/title/cat/tag fields — no
description. The static SSG card template used to include a <p> with
the article description; the dynamic renderer needs the same data so
every card shows a subtitle.

Source of truth: the ZH file's <meta name="description"> (SEO-tuned,
~100-170 chars). EN counterpart pulled from en/blog/<slug>.html if
present; falls back to ZH desc otherwise.

Idempotent: matches `desc:'...'` / `desc_en:'...'` and replaces if
present, inserts after `tag_en:'...'` if absent.

Run as part of REGEN_STEPS, after _normalize_schema (which canonicalizes
meta description) and before _normalize_css_links / minify.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SHARED = ROOT / "blog" / "blog-shared.js"
BLOG = ROOT / "blog"
EN_BLOG = ROOT / "en" / "blog"


def extract_description(html_path: Path) -> str:
    """Pull the meta description content from an article HTML. Returns
    empty string if not found or unparseable.
    """
    if not html_path.exists():
        return ""
    try:
        src = html_path.read_text(encoding="utf-8")
    except Exception:
        return ""
    m = re.search(
        r'<meta\s+name="description"\s+content="([^"]+)"',
        src, re.I,
    )
    return m.group(1).strip() if m else ""


def js_string_escape(value: str) -> str:
    """Prepare a description for storage in DN.ARTICLES.

    Constraints — the value must survive:
      1. JS single-quoted literal in blog-shared.js (no raw `'`)
      2. HTML attribute value in `<p data-zh="...">` (no raw `"`)
      3. HTML inner text in `<p>...</p>` (no raw `<` or `&`)

    Approach: decode HTML entities (some source meta descriptions
    have `&quot;`, `&amp;gt;`, etc. from the HTML escape pass), then
    replace dangerous chars with typographic equivalents that read
    well in prose.
    """
    import html as html_lib
    decoded = html_lib.unescape(value)
    return (
        decoded
        .replace("\\", "\\\\")
        .replace("'", "’")  # ASCII apostrophe -> right single quote
        .replace('"', '”')  # ASCII double quote -> right double quote
        .replace("<", "‹")  # tag-open -> guillemet (rarely needed)
        .replace(">", "›")
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
    )


def main() -> int:
    if not SHARED.exists():
        print("[articles-desc] blog/blog-shared.js missing — skipping")
        return 0

    src = SHARED.read_text(encoding="utf-8")
    m_block = re.search(r"DN\.ARTICLES\s*=\s*\[([\s\S]*?)\];", src)
    if not m_block:
        print("[articles-desc] DN.ARTICLES catalog not found")
        return 1

    catalog_start = m_block.start(1)
    catalog_end = m_block.end(1)
    catalog = m_block.group(1)

    entries = list(re.finditer(
        r"\{[^{}]*?slug:'([a-z0-9-]+)'[^{}]*?\}",
        catalog,
    ))
    if not entries:
        print("[articles-desc] no entries parsed")
        return 1

    updated = catalog
    n_changed = 0
    n_skipped_missing = 0

    # Iterate in reverse so positions inside `updated` stay valid as we splice.
    for entry_m in reversed(entries):
        slug = entry_m.group(1)
        entry_text = entry_m.group(0)
        entry_start = entry_m.start(0)
        entry_end = entry_m.end(0)

        zh_desc = extract_description(BLOG / f"{slug}.html")
        en_desc = extract_description(EN_BLOG / f"{slug}.html") or zh_desc

        if not zh_desc:
            n_skipped_missing += 1
            continue

        zh_esc = js_string_escape(zh_desc)
        en_esc = js_string_escape(en_desc)

        new_entry = entry_text
        # Update or insert desc
        if re.search(r"\bdesc:'[^']*'", new_entry):
            new_entry = re.sub(
                r"\bdesc:'[^']*'",
                "desc:'" + zh_esc + "'",
                new_entry,
                count=1,
            )
        else:
            # Insert AFTER tag_en:'...' if it exists, else after tag:'...',
            # else right before the closing `}`.
            anchor = re.search(r"(\btag_en:'[^']*')", new_entry)
            if anchor:
                pos = anchor.end()
                new_entry = (
                    new_entry[:pos]
                    + ", desc:'" + zh_esc + "'"
                    + new_entry[pos:]
                )
            else:
                # before final `}` (drop trailing comma if present)
                idx = new_entry.rfind("}")
                new_entry = (
                    new_entry[:idx].rstrip(", ")
                    + ", desc:'" + zh_esc + "' "
                    + new_entry[idx:]
                )

        if re.search(r"\bdesc_en:'[^']*'", new_entry):
            new_entry = re.sub(
                r"\bdesc_en:'[^']*'",
                "desc_en:'" + en_esc + "'",
                new_entry,
                count=1,
            )
        else:
            anchor = re.search(r"(\bdesc:'[^']*')", new_entry)
            if anchor:
                pos = anchor.end()
                new_entry = (
                    new_entry[:pos]
                    + ", desc_en:'" + en_esc + "'"
                    + new_entry[pos:]
                )

        if new_entry != entry_text:
            updated = updated[:entry_start] + new_entry + updated[entry_end:]
            n_changed += 1

    if updated != catalog:
        new_src = src[:catalog_start] + updated + src[catalog_end:]
        SHARED.write_text(new_src, encoding="utf-8")
    print(f"[articles-desc] updated {n_changed} entries; "
          f"skipped {n_skipped_missing} with no <meta description>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
