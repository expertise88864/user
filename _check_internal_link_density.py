#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Diagnose internal-link density across the blog catalog.

Why this matters: Google's PageRank-style internal weight follows
inbound links. Articles with 0 inbound links from other articles are
"orphans" — Googlebot reaches them only via sitemap, and their
authority signal is diluted. Articles with 1-2 inbound links are
"weakly linked." Both groups deserve manual link-injection from
related, indexable articles.

Two distinct link types are counted:
  1. **prose links** — <a href="/blog/<slug>"> inside an <article>
     body, EXCLUDING the auto-injected related-articles block
     (#dn-related-static). These are the editorial / "in-text"
     cross-references that carry real PageRank weight.
  2. **related-block links** — auto-injected by _inject_related.py
     into <nav id="dn-related-static">. These are uniform across
     articles (every article gets ~4) and contribute much less
     signal than prose links because they're algorithmic.

Output ranks articles by **prose inbound count** ascending —
the top of the list is the orphan/weak group needing attention.

Usage:
    python _check_internal_link_density.py            # full report
    python _check_internal_link_density.py --orphans  # only 0-inbound
    python _check_internal_link_density.py --json     # machine-readable
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
BLOG = ROOT / "blog"

# Pattern for any <a href="/blog/slug"> or "/blog/slug.html" or
# "/blog/slug#anchor" reference (whether absolute or root-relative)
LINK_RE = re.compile(
    r'<a[^>]+href="(?:https?://chendermatologist\.com)?/blog/([a-z0-9-]+)(?:\.html)?(?:#[^"]*)?"',
    re.IGNORECASE,
)

# Strip everything between <nav id="dn-related-static"> and </nav>
# so related-block links don't pollute the prose count.
RELATED_BLOCK_RE = re.compile(
    r'<nav id="dn-related-static"[\s\S]*?</nav>',
    re.IGNORECASE,
)


def collect_links() -> tuple[dict[str, list[str]], dict[str, int]]:
    """Return:
      - inbound_prose[slug]: list of slugs that link TO this slug from
        their prose body (excluding the related block).
      - outbound_prose[slug]: count of OUT links from this article's
        prose to other articles.
    """
    inbound: dict[str, list[str]] = defaultdict(list)
    outbound: dict[str, int] = {}

    for fp in sorted(BLOG.glob("*.html")):
        if fp.name in {"index.html", "topics.html"}:
            continue
        slug = fp.stem
        src = fp.read_text(encoding="utf-8", errors="replace")
        # Strip the related-block before counting prose links
        prose = RELATED_BLOCK_RE.sub("", src)
        # Count outbound links (deduplicated to other slugs only;
        # self-links don't count toward outbound either)
        targets = set()
        for m in LINK_RE.finditer(prose):
            tgt = m.group(1)
            if tgt == slug or tgt == "index" or tgt == "topics":
                continue
            targets.add(tgt)
        outbound[slug] = len(targets)
        for tgt in targets:
            inbound[tgt].append(slug)

    return dict(inbound), outbound


def slug_to_title(slug: str) -> str:
    """Best-effort lookup of an article's H1 from its file."""
    fp = BLOG / f"{slug}.html"
    if not fp.exists():
        return slug
    src = fp.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", src)
    if not m:
        return slug
    text = re.sub(r"<[^>]+>", " ", m.group(1))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:80] or slug


def is_unpublished(slug: str) -> bool:
    """Skip articles that are intentionally hidden."""
    fp = BLOG / f"{slug}.html"
    if not fp.exists():
        return True
    src = fp.read_text(encoding="utf-8", errors="replace")
    return "noindex" in src.lower()[:5000]


def main() -> int:
    only_orphans = "--orphans" in sys.argv
    json_mode = "--json" in sys.argv

    inbound, outbound = collect_links()

    # Collect all slugs (some have 0 inbound)
    all_slugs = sorted({fp.stem for fp in BLOG.glob("*.html")
                        if fp.name not in {"index.html", "topics.html"}})

    rows = []
    for slug in all_slugs:
        if is_unpublished(slug):
            continue
        in_count = len(inbound.get(slug, []))
        out_count = outbound.get(slug, 0)
        rows.append({
            "slug": slug,
            "title": slug_to_title(slug),
            "inbound_prose": in_count,
            "outbound_prose": out_count,
            "inbound_from": sorted(inbound.get(slug, [])),
        })

    rows.sort(key=lambda r: (r["inbound_prose"], r["slug"]))

    if json_mode:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print(f"\n=== Internal link density report ({len(rows)} articles) ===\n")
    orphans = [r for r in rows if r["inbound_prose"] == 0]
    weak = [r for r in rows if 1 <= r["inbound_prose"] <= 2]

    print(f"Orphans (0 prose inbound):  {len(orphans)} articles")
    print(f"Weakly linked (1-2):        {len(weak)} articles")
    print(f"Healthy (3+):               {len(rows) - len(orphans) - len(weak)} articles")
    print()

    show = orphans if only_orphans else rows
    for r in show:
        marker = "🔴" if r["inbound_prose"] == 0 else (
            "🟡" if r["inbound_prose"] <= 2 else "🟢"
        )
        print(f"{marker} in={r['inbound_prose']:>2}  out={r['outbound_prose']:>2}  "
              f"{r['slug']:<42}  {r['title'][:60]}")

    if only_orphans and orphans:
        print()
        print("Recommendation: add 1-2 inline cross-links to each orphan")
        print("from articles in its same topic cluster (see _gen_site_graph.py")
        print("clusters or DN.ARTICLES tags).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
