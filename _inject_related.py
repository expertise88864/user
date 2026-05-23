#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SSG-inject the "你可能也會想看 / You might also like" related-articles section.

The original implementation lives in blog/blog-article-footer.js
(`DN.addRelatedArticles`) and runs client-side via JS injection. That works
for end users but Googlebot only sees what's in the static HTML, so 4
internal links per article × 47 articles = 188 internal links were
invisible to crawl-budget allocation.

This script pre-renders the same 4 cards into static HTML inside a
<nav id="dn-related-static"> block, then:
  - blog/blog-article-footer.js DN.addRelatedArticles() bails early if
    document.getElementById('dn-related-static') exists (no double-render)
  - Googlebot + readers with JS disabled both see the 4 internal links

Scoring algorithm: identical port of the JS logic — TAG_GROUPS shared
membership (×20) + same tag (×12) + same cat (×2) + token overlap
fallback for unrelated topics. Top 4 by score, tiebreak newer.

Run as part of the build pipeline (after blog-shared.js DN.ARTICLES is
the source of truth, before _gen_en_pages.py copies HTML).
"""
from __future__ import annotations

import html as html_lib
import io
import os
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"

# ─── 1. Parse DN.ARTICLES catalog from blog-shared.js ─────────────────────
def parse_articles() -> list[dict]:
    js = (ROOT / "blog" / "blog-shared.js").read_text(encoding="utf-8")
    m = re.search(r"DN\.ARTICLES\s*=\s*\[([\s\S]*?)\];", js)
    if not m:
        raise SystemExit("DN.ARTICLES not found in blog-shared.js")
    block = m.group(1)
    articles = []
    for entry_m in re.finditer(r"\{[^{}]*?slug:\s*'([a-z0-9-]+)'[^{}]*?\}", block):
        e = entry_m.group(0)
        slug = entry_m.group(1)

        def get(field):
            mm = re.search(rf"{field}:\s*'([^']*)'", e)
            return mm.group(1) if mm else None

        is_unpub = bool(re.search(r"\bunpublished\s*:\s*true\b", e))
        articles.append({
            "slug": slug,
            "title": get("title") or "",
            "title_en": get("title_en") or "",
            "cat": get("cat") or "",
            "tag": get("tag") or "",
            "tag_en": get("tag_en") or "",
            "date": get("date") or "",
            "unpublished": is_unpub,
        })
    return articles

# ─── 2. Reconstruct TAG_GROUPS the same way blog-hub.js does ──────────────
def parse_tag_categories() -> list[dict]:
    js = (ROOT / "blog" / "blog-hub.js").read_text(encoding="utf-8")
    m = re.search(r"DN\.TAG_CATEGORIES\s*=\s*\[([\s\S]*?)\n\s*\];", js)
    if not m:
        raise SystemExit("DN.TAG_CATEGORIES not found")
    # Parse each `tags: { 'name': ['slug', ...], ... }` block out.
    # Lightweight parse — we only need the leaf slug lists per tag name.
    text = m.group(1)
    cats = []
    for tags_block_m in re.finditer(r"tags:\s*\{([\s\S]*?)\n\s*\}", text):
        tb = tags_block_m.group(1)
        cat_tags = {}
        # Match `'tagname': ['slug', 'slug', ...]` OR `'tagname': { _from_cat: 'xxx' }`
        for entry_m in re.finditer(
            r"'([^']+)':\s*(\[[^\]]*\]|\{\s*_from_cat:\s*'([^']+)'\s*\})", tb
        ):
            name = entry_m.group(1)
            val_str = entry_m.group(2)
            from_cat = entry_m.group(3)
            if from_cat:
                cat_tags[name] = {"_from_cat": from_cat}
            else:
                slugs = re.findall(r"'([a-z0-9-]+)'", val_str)
                cat_tags[name] = slugs
        cats.append({"tags": cat_tags})
    return cats

def build_tag_groups(catalog: list[dict]) -> dict[str, list[str]]:
    cats = parse_tag_categories()
    flat: dict[str, list[str]] = {}
    for cat in cats:
        for name, val in cat["tags"].items():
            if isinstance(val, dict) and "_from_cat" in val:
                flat[name] = [a["slug"] for a in catalog if a["cat"] == val["_from_cat"]]
            else:
                flat[name] = val
    return flat

# ─── 3. Identical scoring port ─────────────────────────────────────────────
COMMON_TOKENS = {"皮膚", "完整", "衛教", "迷思", "治療", "藥物", "副作用", "常見"}
_CJK_TOKEN_RE = re.compile(r"[一-鿿]{2,}")

def tokens(a: dict) -> set[str]:
    text = (a["title"] + " " + (a["tag"] or "") + " " + (a["tag_en"] or "")).lower()
    words = {w for w in re.split(r"[\s/\-,()·]+", text) if len(w) > 1}
    words.update(_CJK_TOKEN_RE.findall(text))
    return words

def groups_containing(slug: str, TG: dict[str, list[str]]) -> list[str]:
    return [k for k, v in TG.items() if slug in (v or [])]

def score_related(cur: dict, all_articles: list[dict], TG: dict[str, list[str]]) -> list[dict]:
    cur_groups = set(groups_containing(cur["slug"], TG))
    cur_tok = tokens(cur)
    scored = []
    for a in all_articles:
        if a["slug"] == cur["slug"] or a["unpublished"]:
            continue
        a_groups = groups_containing(a["slug"], TG)
        shared = [g for g in a_groups if g in cur_groups]
        group_bonus = len(shared) * 20
        tag_bonus = 12 if a["tag"] == cur["tag"] else 0
        cat_bonus = 2 if a["cat"] == cur["cat"] else 0
        overlap = 0
        if not shared:
            a_tok = tokens(a)
            overlap = sum(1 for t in a_tok if t in cur_tok and t not in COMMON_TOKENS)
        s = group_bonus + tag_bonus + cat_bonus + overlap
        if s > 0:
            scored.append((s, a))
    # Sort by score desc, tiebreak by date desc (newer first)
    # CODE_REVIEW — was 3 sequential sorts where only the last one
    # (score desc) survived Python's stable-sort guarantee. Collapse
    # to a single composite-key sort: primary = score desc, secondary
    # = date desc (newer wins ties).
    scored.sort(key=lambda x: (-x[0], "" if not x[1]["date"] else x[1]["date"]),
                reverse=False)
    # Hack: secondary needs to be DESC but the primary is ASC via -x[0].
    # Use a tuple where date is negated by string-flipping. Simpler:
    # do one composite sort with two pass-through keys at proper polarity.
    scored.sort(key=lambda x: (-x[0], -_date_sort_key(x[1]["date"])))
    return [a for _, a in scored[:4]]


def _date_sort_key(date_str: str) -> int:
    """Return an int for date sorting (YYYY-MM-DD → YYYYMMDD)."""
    if not date_str:
        return 0
    try:
        return int(date_str.replace("-", ""))
    except ValueError:
        return 0

# ─── 4. Build the SSG HTML block (mirrors the JS-injected layout) ────────
def build_related_html(cur_slug: str, related: list[dict]) -> str:
    if not related:
        return ""
    cards = []
    for i, a in enumerate(related):
        badge = (
            '<span style="display:inline-block;padding:2px 7px;border-radius:9999px;'
            'background:#fef3c7;color:#854d0e;font-size:10px;font-weight:700;margin-left:auto" '
            'data-zh="最相關" data-en="Top match">最相關</span>'
        ) if i == 0 else ""
        title_escaped = html_lib.escape(a["title"], quote=True)
        title_en_escaped = html_lib.escape(a["title_en"] or a["title"], quote=True)
        tag_en = html_lib.escape(a["tag_en"] or a["tag"] or "")
        tag_zh = html_lib.escape(a["tag"] or "")
        cards.append(
            f'<a class="dn-related-card" href="/blog/{a["slug"]}" '
            f'style="display:flex;flex-direction:column;gap:8px;padding:16px;background:#fff;'
            f'border:1px solid var(--border);border-radius:12px;text-decoration:none;color:var(--ink);'
            f'transition:all .15s;box-shadow:0 1px 2px rgba(15,23,42,.04)">'
            f'<div style="display:flex;align-items:center;gap:6px">'
            f'<span style="font-size:10.5px;font-weight:700;letter-spacing:.18em;color:var(--teal-deep);'
            f'text-transform:uppercase">{tag_en}</span>{badge}</div>'
            f'<span data-zh="{title_escaped}" data-en="{title_en_escaped}" '
            f'style="font-size:14.5px;font-weight:700;line-height:1.4;'
            f'font-family:Noto Serif TC,Georgia,serif;color:var(--ink);'
            f'display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">'
            f'{html_lib.escape(a["title"])}</span>'
            f'<span style="font-size:11.5px;color:var(--muted);margin-top:auto">'
            f'{tag_zh} · {a["date"]}</span>'
            f'</a>'
        )

    # 2026-05-17 — id="dn-related-static" is the signal for
    # DN.addRelatedArticles() to bail early and not double-render.
    # Also embed an ItemList JSON-LD block so Googlebot sees the
    # related-articles structured data without needing to execute JS.
    import json
    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Related dermatology articles",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "url": f"{DOMAIN}/blog/{a['slug']}",
                "name": a["title"],
            }
            for i, a in enumerate(related)
        ],
    }
    jsonld = (
        '<script type="application/ld+json">'
        + json.dumps(item_list, ensure_ascii=False, separators=(",", ":"))
        + '</script>'
    )
    return (
        '\n<nav id="dn-related-static" class="max-w-3xl mx-auto px-5 sm:px-8 my-10" '
        'aria-label="Related articles">'
        # 2026-05-23 — explicit 2×2 grid (左上/右上/左下/右下) on desktop,
        # collapses to 1 column under 520px so cards stay readable on
        # mobile (320-414px typical phone viewport width).
        '<style>'
        '.dn-related-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}'
        '@media (max-width:520px){.dn-related-grid{grid-template-columns:1fr}}'
        '</style>'
        '<div style="border-top:1px solid var(--line);padding-top:28px">'
        '<div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:14px">'
        '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.22em;'
        'color:var(--teal-deep);font-weight:700" data-zh="你可能也會想看" '
        'data-en="You might also like">你可能也會想看</div>'
        '<a href="/blog/" style="font-size:11.5px;color:var(--teal-deep);text-decoration:none;'
        'font-weight:600" data-zh="瀏覽全部文章 →" data-en="Browse all →">瀏覽全部文章 →</a>'
        '</div>'
        '<div class="dn-related-grid">'
        + "".join(cards) +
        '</div></div>'
        + jsonld +
        '</nav>\n'
    )

# ─── 5. Inject into each blog/*.html right before </main> ─────────────────
RELATED_BLOCK_RE = re.compile(
    r'\n?<nav id="dn-related-static"[\s\S]*?</nav>\n?',
    re.IGNORECASE,
)
def inject(catalog: list[dict], TG: dict[str, list[str]]) -> tuple[int, int]:
    files_changed = 0
    cards_total = 0
    by_slug = {a["slug"]: a for a in catalog}
    blog_dir = ROOT / "blog"

    for fp in sorted(blog_dir.glob("*.html")):
        # Skip listing pages and the home page
        if fp.name in {"index.html", "topics.html"}:
            continue
        slug = fp.stem
        cur = by_slug.get(slug)
        if not cur or cur["unpublished"]:
            continue
        related = score_related(cur, catalog, TG)
        if not related:
            continue
        block = build_related_html(slug, related)

        src = fp.read_text(encoding="utf-8")
        # Remove any prior injection (so re-runs are idempotent)
        src = RELATED_BLOCK_RE.sub("", src)
        # Insert right before </main>
        if "</main>" not in src:
            continue
        new = src.replace("</main>", block + "</main>", 1)
        if new == src:
            continue
        fp.write_text(new, encoding="utf-8")
        files_changed += 1
        cards_total += len(related)

    return files_changed, cards_total


def main() -> int:
    catalog = parse_articles()
    TG = build_tag_groups(catalog)
    files_changed, cards_total = inject(catalog, TG)
    print(f"SSG-injected related cards: {cards_total} cards across {files_changed} articles")
    print(f"Average cards/article: {cards_total / max(files_changed, 1):.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
