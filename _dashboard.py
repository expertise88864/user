#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate _dashboard.md — single-page SEO health snapshot.

Concentrates everything that affects impressions + CTR into one
review-able markdown file:

  - Per-article scorecard: word count, reading time, incoming internal
    links, last-modified date, schema completeness
  - Site totals: by section, by language, indexable vs noindex
  - Opportunity flags: orphan articles, short articles, stale dates
  - SEO signal coverage matrix (robots / OG / Twitter / JSON-LD)
  - Pipeline health: sitemap entries, IndexNow log, last build

Run `python _dashboard.py` anytime. Output goes to _dashboard.md
(gitignored — operational, not source).

Most useful workflow:
  1. Before opening a content session, scan the Opportunity flags
     section to pick the next article to enrich.
  2. After a content/SEO commit, re-run to confirm metrics improved.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"

CAT_LABEL = {
    "rx": "Treatment & Therapy",
    "myth": "Myths & Facts",
    "note": "Clinical Notes",
    "research": "Research Summary",
    "product": "Products & Drugs",
}


def parse_articles() -> list[dict]:
    src = (ROOT / "blog" / "blog-shared.js").read_text(encoding="utf-8")
    m = re.search(r"DN\.ARTICLES\s*=\s*\[([\s\S]*?)\];", src)
    if not m:
        return []
    out: list[dict] = []
    for entry_m in re.finditer(r"\{[^{}]*?slug:'([a-z0-9-]+)'[^{}]*?\}",
                                m.group(1)):
        e = entry_m.group(0)
        unpub = bool(re.search(r"\bunpublished\s*:\s*true\b", e))

        def field(name: str) -> str:
            mm = re.search(rf"\b{name}:'([^']*)'", e)
            return mm.group(1) if mm else ""

        out.append({
            "slug": entry_m.group(1),
            "title": field("title"),
            "date": field("date"),
            "cat": field("cat"),
            "tag": field("tag"),
            "tag_en": field("tag_en"),
            "unpublished": unpub,
        })
    return out


def count_incoming_links(slug: str, blog_dir: Path) -> int:
    """Count blog/*.html that contain a link to /blog/<slug>, excluding self."""
    n = 0
    for fp in blog_dir.glob("*.html"):
        if fp.stem == slug:
            continue
        if f"/blog/{slug}" in fp.read_text(encoding="utf-8", errors="replace"):
            n += 1
    return n


def article_metrics(slug: str) -> dict:
    """Extract per-article SEO metrics from its HTML."""
    fp = ROOT / "blog" / f"{slug}.html"
    if not fp.exists():
        return {}
    src = fp.read_text(encoding="utf-8", errors="replace")
    wc_m = re.search(r'"wordCount":(\d+)', src)
    tr_m = re.search(r'"timeRequired":"PT(\d+)M"', src)
    dm_m = re.search(r'"dateModified":"([^"]+)"', src)
    has_section = '"articleSection"' in src
    has_keywords = '"keywords"' in src
    has_speakable = '"speakable"' in src
    has_og_article = 'property="article:published_time"' in src
    has_twitter_label = 'name="twitter:label1"' in src
    has_dn_spec = 'speculationrules' in src
    noindex = 'name="robots" content="noindex' in src
    return {
        "wordCount": int(wc_m.group(1)) if wc_m else 0,
        "minutes": int(tr_m.group(1)) if tr_m else 0,
        "dateModified": dm_m.group(1) if dm_m else "",
        "size_kb": round(len(src) / 1024, 1),
        "has_section": has_section,
        "has_keywords": has_keywords,
        "has_speakable": has_speakable,
        "has_og_article": has_og_article,
        "has_twitter_label": has_twitter_label,
        "has_dn_spec": has_dn_spec,
        "noindex": noindex,
    }


def en_indexable_count() -> int:
    """How many /en/blog/*.html are indexable (no noindex)?"""
    en_dir = ROOT / "en" / "blog"
    if not en_dir.exists():
        return 0
    n = 0
    for fp in en_dir.glob("*.html"):
        if fp.name in {"index.html", "topics.html"}:
            continue
        src = fp.read_text(encoding="utf-8", errors="replace")
        if 'content="noindex' not in src:
            n += 1
    return n


def sitemap_url_count() -> int:
    sm = ROOT / "sitemap.xml"
    if not sm.exists():
        return 0
    return sm.read_text(encoding="utf-8").count("<loc>")


def js_bundle_sizes() -> dict[str, float]:
    out: dict[str, float] = {}
    for fp in sorted((ROOT / "blog").glob("blog-*.min.js")):
        out[fp.name] = round(fp.stat().st_size / 1024, 1)
    return out


def build_table_rows(rows: list[list[str]], headers: list[str]) -> str:
    sep = "|" + "|".join("---:" if h.startswith("(") else "---"
                          for h in headers) + "|"
    out = ["| " + " | ".join(headers) + " |", sep]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def main() -> int:
    today = dt.date.today()
    articles = [a for a in parse_articles() if not a["unpublished"]]
    blog_dir = ROOT / "blog"

    rows = []
    flags = {
        "orphan": [],          # incoming < 5
        "short": [],           # wordCount < 1500
        "stale": [],           # dateModified > 30 days ago
        "missing_signals": [], # any SEO signal missing
        "noindex": [],
    }
    section_counts: Counter = Counter()
    minute_total = 0
    word_total = 0
    incoming_total = 0

    for a in articles:
        m = article_metrics(a["slug"])
        if not m:
            continue
        incoming = count_incoming_links(a["slug"], blog_dir)
        rows.append([
            a["slug"],
            CAT_LABEL.get(a["cat"], a["cat"]),
            m["wordCount"],
            m["minutes"],
            incoming,
            m["dateModified"][:10] if m["dateModified"] else a["date"],
            "✓" if (m["has_section"] and m["has_og_article"]
                     and m["has_twitter_label"] and m["has_speakable"]) else "✗",
        ])
        section_counts[CAT_LABEL.get(a["cat"], "Other")] += 1
        minute_total += m["minutes"]
        word_total += m["wordCount"]
        incoming_total += incoming
        if incoming < 5:
            flags["orphan"].append((a["slug"], incoming))
        if m["wordCount"] < 1500 and m["wordCount"] > 0:
            flags["short"].append((a["slug"], m["wordCount"]))
        if m["dateModified"]:
            try:
                d = dt.date.fromisoformat(m["dateModified"][:10])
                if (today - d).days > 30:
                    flags["stale"].append((a["slug"], (today - d).days))
            except ValueError:
                pass
        if not (m["has_section"] and m["has_og_article"]
                 and m["has_twitter_label"] and m["has_speakable"]):
            missing = []
            if not m["has_section"]: missing.append("section")
            if not m["has_og_article"]: missing.append("og:article")
            if not m["has_twitter_label"]: missing.append("twitter:label")
            if not m["has_speakable"]: missing.append("speakable")
            flags["missing_signals"].append((a["slug"], missing))
        if m["noindex"]:
            flags["noindex"].append(a["slug"])

    rows.sort(key=lambda r: (r[4], -r[2]))  # by incoming asc, wordCount desc

    n = len(articles)
    md_lines: list[str] = []
    md_lines.append(f"# SEO health dashboard")
    md_lines.append(f"")
    md_lines.append(f"_Generated {today.isoformat()} · {n} published articles_")
    md_lines.append(f"")
    # Companion artifacts (Round 2 J/K from OPEN_SOURCE_INTEGRATIONS.md)
    md_lines.append(f"## Companion artifacts")
    md_lines.append(f"")
    md_lines.append(f"- [assets/dn-site-graph.svg](assets/dn-site-graph.svg) — "
                    f"force-directed visualization of the internal-link graph "
                    f"(nodes sized by in-degree, coloured by cat). "
                    f"Re-run `python _gen_site_graph.py` after content changes.")
    md_lines.append(f"- [_readability.md](_readability.md) — Chinese readability "
                    f"score per article. Re-run `python _check_readability.py` "
                    f"after content edits.")
    md_lines.append(f"")

    # ─── Site totals ───
    md_lines.append("## Site totals")
    md_lines.append(f"")
    md_lines.append(f"- **Published articles:** {n}")
    md_lines.append(f"- **EN indexable mirrors:** {en_indexable_count()}")
    md_lines.append(f"- **Sitemap URLs:** {sitemap_url_count()}")
    md_lines.append(f"- **Total content:** {word_total:,} words · "
                    f"{minute_total} min total reading time")
    md_lines.append(f"- **Internal links (avg per article):** "
                    f"{incoming_total / max(n, 1):.1f}")
    md_lines.append(f"")
    md_lines.append("### By section")
    md_lines.append("")
    for sec, c in section_counts.most_common():
        md_lines.append(f"- {sec}: {c}")
    md_lines.append("")

    # ─── JS bundle sizes ───
    md_lines.append("## JS bundle sizes (KB)")
    md_lines.append("")
    sizes = js_bundle_sizes()
    if sizes:
        md_lines.append("| Bundle | Size |")
        md_lines.append("|---|---:|")
        for k, v in sorted(sizes.items()):
            md_lines.append(f"| {k} | {v} |")
        md_lines.append("")

    # ─── Opportunity flags ───
    md_lines.append("## Opportunity flags")
    md_lines.append("")
    flags["orphan"].sort(key=lambda x: x[1])
    flags["short"].sort(key=lambda x: x[1])
    flags["stale"].sort(key=lambda x: -x[1])

    if flags["orphan"]:
        md_lines.append(f"### Orphan articles (<5 incoming links) "
                         f"— {len(flags['orphan'])}")
        md_lines.append("")
        md_lines.append("Add to more `DN.TAG_CATEGORIES` groups in blog-hub.js "
                        "to lift their score in `_inject_related.py`.")
        md_lines.append("")
        for slug, n_in in flags["orphan"][:15]:
            md_lines.append(f"- `{slug}` ({n_in} links)")
        md_lines.append("")

    if flags["short"]:
        md_lines.append(f"### Short articles (<1500 words) "
                         f"— {len(flags['short'])}")
        md_lines.append("")
        md_lines.append("Short content underperforms in long-form medical queries. "
                        "Consider expanding with FAQ / case examples / references.")
        md_lines.append("")
        for slug, wc in flags["short"][:15]:
            md_lines.append(f"- `{slug}` ({wc:,} words)")
        md_lines.append("")

    if flags["stale"]:
        md_lines.append(f"### Stale articles (dateModified >30 days) "
                         f"— {len(flags['stale'])}")
        md_lines.append("")
        md_lines.append("Refreshing `dateModified` (even with light edits) is a "
                        "ranking signal Google reads.")
        md_lines.append("")
        for slug, days in flags["stale"][:15]:
            md_lines.append(f"- `{slug}` ({days} days)")
        md_lines.append("")

    if flags["missing_signals"]:
        md_lines.append(f"### Missing SEO signals "
                         f"— {len(flags['missing_signals'])}")
        md_lines.append("")
        for slug, missing in flags["missing_signals"][:10]:
            md_lines.append(f"- `{slug}`: missing {', '.join(missing)}")
        md_lines.append("")

    if flags["noindex"]:
        md_lines.append(f"### noindex articles — {len(flags['noindex'])}")
        md_lines.append("")
        for slug in flags["noindex"]:
            md_lines.append(f"- `{slug}`")
        md_lines.append("")

    # ─── Per-article scorecard ───
    md_lines.append("## Per-article scorecard")
    md_lines.append("")
    md_lines.append("Sorted by incoming links ascending (orphans first), "
                    "then by word count desc.")
    md_lines.append("")
    md_lines.append(build_table_rows(
        rows,
        ["slug", "section", "(words)", "(min)", "(links)", "modified", "signals"],
    ))
    md_lines.append("")

    out = "\n".join(md_lines) + "\n"
    (ROOT / "_dashboard.md").write_text(out, encoding="utf-8")
    print(f"Wrote _dashboard.md ({n} articles scored)")
    if flags["orphan"]:
        print(f"  ⚠  {len(flags['orphan'])} orphan articles need link boost")
    if flags["short"]:
        print(f"  ⚠  {len(flags['short'])} short articles to consider expanding")
    if flags["stale"]:
        print(f"  ⚠  {len(flags['stale'])} stale articles (refresh dateModified)")
    if flags["missing_signals"]:
        print(f"  ⚠  {len(flags['missing_signals'])} articles missing SEO signals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
