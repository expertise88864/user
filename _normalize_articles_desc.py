#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Emit a DN.ARTICLES_DESC dictionary into blog-hub.js so /blog/ card
renderer can show subtitle text without bloating the shared runtime.

Why split: blog/blog-shared.js loads on EVERY page (article, glossary,
tools, homepage). The 13 KB of CJK description text only matters on
/blog/ + homepage where article-list cards render. Putting desc into
DN.ARTICLES on the shared bundle bloated it from ~73 KB to ~96 KB.

Split design:
  - DN.ARTICLES (in blog-shared.js): unchanged — slug/title/cat/tag/etc.
  - DN.ARTICLES_DESC (in blog-hub.js): { 'slug': {desc, desc_en} }
    Only paid when blog-hub bundle loads (/blog/ index + homepage).

Source of truth: the ZH file's <meta name="description"> (SEO-tuned,
~100-170 chars). EN counterpart pulled from en/blog/<slug>.html if
present; falls back to ZH desc otherwise.

Idempotent: replaces the whole `// dn-articles-desc:start ... :end`
marker block on each run.

Run as part of REGEN_STEPS, after _normalize_schema (which canonicalizes
meta description) and before _normalize_css_links / minify.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SHARED = ROOT / "blog" / "blog-shared.js"
HUB = ROOT / "blog" / "blog-hub.js"
BLOG = ROOT / "blog"
EN_BLOG = ROOT / "en" / "blog"

# Marker comment block in blog-hub.js — strip + re-insert on each run.
MARKER_START = "// dn-articles-desc:start"
MARKER_END = "// dn-articles-desc:end"
BLOCK_RE = re.compile(
    re.escape(MARKER_START) + r"[\s\S]*?" + re.escape(MARKER_END),
    re.MULTILINE,
)


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


def parse_slugs_from_shared() -> list[str]:
    """Read DN.ARTICLES from blog-shared.js, return slug list (in source
    order)."""
    if not SHARED.exists():
        return []
    src = SHARED.read_text(encoding="utf-8")
    m = re.search(r"DN\.ARTICLES\s*=\s*\[([\s\S]*?)\];", src)
    if not m:
        return []
    return re.findall(r"slug:'([a-z0-9-]+)'", m.group(1))


def strip_desc_from_shared() -> int:
    """One-time cleanup: remove `desc:'...'` and `desc_en:'...'` fields
    that an earlier version of this script wrote into blog-shared.js
    DN.ARTICLES entries. They moved to DN.ARTICLES_DESC in blog-hub.js.
    Returns number of changes made.
    """
    if not SHARED.exists():
        return 0
    src = SHARED.read_text(encoding="utf-8")
    # Strip ", desc:'...'" and ", desc_en:'...'" (with or without leading comma)
    new_src = re.sub(r",\s*desc(?:_en)?:'[^']*'", "", src)
    if new_src != src:
        SHARED.write_text(new_src, encoding="utf-8")
        return src.count("desc:") - new_src.count("desc:")
    return 0


def build_desc_block(descs: dict[str, dict[str, str]]) -> str:
    """Render the DN.ARTICLES_DESC dictionary as a tight JS literal.

    Skips empty descriptions. Sorts by slug for stable diffs.
    Uses JSON.dumps internally for proper escaping then converts the
    JSON-string-keyed dict into JS object syntax that re-uses our
    js_string_escape rules.
    """
    lines = [MARKER_START, "  DN.ARTICLES_DESC = {"]
    for slug in sorted(descs.keys()):
        d = descs[slug]
        if not d.get("desc"):
            continue
        lines.append(
            f"    '{slug}': {{desc:'{d['desc']}',desc_en:'{d.get('desc_en') or d['desc']}'}},"
        )
    lines.append("  };")
    lines.append("  " + MARKER_END)
    return "\n".join(lines)


def main() -> int:
    if not HUB.exists():
        print("[articles-desc] blog/blog-hub.js missing — skipping")
        return 0

    # One-time cleanup: pull desc/desc_en out of blog-shared.js if a
    # previous build wrote them there.
    n_stripped = strip_desc_from_shared()
    if n_stripped:
        print(f"[articles-desc] removed {n_stripped} legacy desc fields from blog-shared.js")

    slugs = parse_slugs_from_shared()
    descs: dict[str, dict[str, str]] = {}
    skipped = 0
    for slug in slugs:
        zh = extract_description(BLOG / f"{slug}.html")
        en = extract_description(EN_BLOG / f"{slug}.html") or zh
        if not zh:
            skipped += 1
            continue
        descs[slug] = {
            "desc": js_string_escape(zh),
            "desc_en": js_string_escape(en),
        }

    hub_src = HUB.read_text(encoding="utf-8")
    new_block = build_desc_block(descs)

    if BLOCK_RE.search(hub_src):
        # CODE_REVIEW Phase 8A — lambda replacement: `new_block` carries
        # js_string_escape()d descriptions, so an escaped backslash (`\\`) would
        # be collapsed by re.sub's replacement processing and write a broken JS
        # string literal into blog-hub.js (runtime SyntaxError). See TD-40.
        new_hub = BLOCK_RE.sub(lambda _m: new_block, hub_src, count=1)
    else:
        # First-time insert: place right before the final `})();` IIFE close
        close_idx = hub_src.rfind("})();")
        if close_idx == -1:
            print("[articles-desc] could not find IIFE close in blog-hub.js")
            return 1
        new_hub = hub_src[:close_idx] + new_block + "\n\n" + hub_src[close_idx:]

    if new_hub != hub_src:
        HUB.write_text(new_hub, encoding="utf-8")
        print(f"[articles-desc] wrote DN.ARTICLES_DESC ({len(descs)} entries) to blog-hub.js")
    else:
        print(f"[articles-desc] DN.ARTICLES_DESC already up-to-date ({len(descs)} entries)")
    if skipped:
        print(f"[articles-desc] skipped {skipped} with no <meta description>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
