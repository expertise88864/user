#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate _dashboard.md — single-page SEO health snapshot.

Concentrates everything that affects impressions + CTR into one
review-able markdown file:

  - Per-article scorecard: word count, reading time, incoming internal
    links, last-modified date, schema completeness
  - Site totals: by section, by language, indexable vs noindex
  - Editorial prompts: isolated pages, content coverage and source review age
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
import json
from html.parser import HTMLParser
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from _sync_hub_catalog import load_catalog, public_catalog

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
    """Use the same trusted literal reader as the public cards and generators."""
    return load_catalog(ROOT)


class PageMetadata(HTMLParser):
    """Read real anchors, robots directives and JSON-LD, excluding text lookalikes."""

    def __init__(self):
        super().__init__()
        self.links = []
        self.meta = {}
        self.noindex = False
        self.schemas = []
        self.json_script = None

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        elif tag == "meta":
            name = (attrs.get("name") or attrs.get("property") or "").lower()
            content = attrs.get("content") or ""
            self.meta[name] = content
            if name in {"robots", "googlebot"}:
                self.noindex |= "noindex" in re.split(r"[\s,]+", content.lower())
        elif tag == "script":
            self.json_script = [] if (attrs.get("type") or "").lower() == "application/ld+json" else None

    def handle_data(self, value):
        if self.json_script is not None:
            self.json_script.append(value)

    def handle_endtag(self, tag):
        if tag == "script" and self.json_script is not None:
            try:
                self.schemas.append(json.loads("".join(self.json_script)))
            except (ValueError, TypeError):
                pass  # Missing/malformed metadata stays unknown, never a fabricated zero.
            self.json_script = None


def schema_nodes(value):
    if isinstance(value, list):
        for item in value:
            yield from schema_nodes(item)
    elif isinstance(value, dict):
        yield value
        yield from schema_nodes(value.get("@graph", []))


def article_schema(page: PageMetadata, slug: str) -> dict:
    expected = DOMAIN + "/blog/" + slug
    for value in page.schemas:
        for node in schema_nodes(value):
            kinds = node.get("@type", [])
            kinds = [kinds] if isinstance(kinds, str) else kinds
            if not isinstance(kinds, list) or not any(kind in {
                "Article", "BlogPosting", "MedicalWebPage", "MedicalScholarlyArticle", "WebPage"
            } for kind in kinds if isinstance(kind, str)):
                continue
            identity = node.get("url") or node.get("@id")
            if isinstance(identity, str) and identity.split("#", 1)[0].removesuffix(".html") == expected:
                return node
    return {}


def incoming_link_counts(blog_dir: Path, public_slugs: list[str]) -> dict[str, int]:
    """Read each public page once; count each linking source once per destination."""
    counts = {slug: 0 for slug in public_slugs}
    for source_slug in public_slugs:
        page = PageMetadata()
        page.feed((blog_dir / (source_slug + ".html")).read_text(encoding="utf-8"))
        destinations = [urlsplit(urljoin(DOMAIN + "/blog/" + source_slug, href)) for href in page.links]
        linked = {url.path.rstrip("/").removesuffix(".html").removeprefix("/blog/")
                  for url in destinations if url.scheme in {"http", "https"}
                  and url.netloc == urlsplit(DOMAIN).netloc}
        for target in linked & counts.keys():
            if target != source_slug:
                counts[target] += 1
    return counts


def article_metrics(slug: str) -> dict:
    """Extract per-article SEO metrics from its HTML."""
    fp = ROOT / "blog" / f"{slug}.html"
    if not fp.exists():
        return {}
    src = fp.read_text(encoding="utf-8", errors="replace")
    page = PageMetadata()
    page.feed(src)
    node = article_schema(page, slug)
    count = node.get("wordCount")
    count = count if type(count) is int and count >= 0 else None
    duration = node.get("timeRequired")
    minutes = re.fullmatch(r"PT(\d+)M", duration) if isinstance(duration, str) else None
    modified = node.get("dateModified")
    return {
        "wordCount": count,
        "minutes": int(minutes[1]) if minutes else None,
        "dateModified": modified if isinstance(modified, str) else "",
        "size_kb": round(fp.stat().st_size / 1024, 1),
        "has_section": bool(node.get("articleSection")),
        "has_keywords": bool(node.get("keywords")),
        "has_speakable": bool(node.get("speakable")),
        "has_og_article": bool(page.meta.get("article:published_time")),
        "has_twitter_label": bool(page.meta.get("twitter:label1")),
        "has_dn_spec": "speculationrules" in src,
        "noindex": page.noindex,
    }


def en_indexable_count(public_slugs: list[str]) -> int:
    """How many /en/blog/*.html are indexable (no noindex)?"""
    en_dir = ROOT / "en" / "blog"
    if not en_dir.exists():
        return 0
    n = 0
    for slug in public_slugs:
        fp = en_dir / (slug + ".html")
        if not fp.is_file():
            continue
        page = PageMetadata()
        page.feed(fp.read_text(encoding="utf-8"))
        if not page.noindex:
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
    registered = parse_articles()
    articles = public_catalog(registered, ROOT)
    public_slugs = [a["slug"] for a in articles]
    blog_dir = ROOT / "blog"
    incoming_counts = incoming_link_counts(blog_dir, public_slugs)

    rows = []
    flags = {
        "orphan": [],          # no incoming links from other public articles
        "short": [],           # descriptive length inventory, never a ranking target
        "stale": [],           # recorded update age, not a prompt to alter dates
        "missing_signals": [], # any SEO signal missing
        "noindex": [a["slug"] for a in registered if not a.get("unpublished") and a["slug"] not in public_slugs],
    }
    section_counts: Counter = Counter()
    minute_total = 0
    word_total = 0
    incoming_total = 0

    for a in articles:
        m = article_metrics(a["slug"])
        if not m:
            continue
        incoming = incoming_counts[a["slug"]]
        rows.append([
            a["slug"],
            CAT_LABEL.get(a["cat"], a["cat"]),
            m["wordCount"] if m["wordCount"] is not None else "—",
            m["minutes"] if m["minutes"] is not None else "—",
            incoming,
            m["dateModified"][:10] if m["dateModified"] else a["date"],
            "✓" if (m["has_section"] and m["has_og_article"]
                     and m["has_twitter_label"]) else "✗",
        ])
        section_counts[CAT_LABEL.get(a["cat"], "Other")] += 1
        minute_total += m["minutes"] or 0
        word_total += m["wordCount"] or 0
        incoming_total += incoming
        if incoming == 0:
            flags["orphan"].append((a["slug"], incoming))
        if m["wordCount"] is not None and 0 < m["wordCount"] < 1500:
            flags["short"].append((a["slug"], m["wordCount"]))
        if m["dateModified"]:
            try:
                d = dt.date.fromisoformat(m["dateModified"][:10])
                if (today - d).days > 30:
                    flags["stale"].append((a["slug"], (today - d).days))
            except ValueError:
                pass
        if not (m["has_section"] and m["has_og_article"]
                  and m["has_twitter_label"]):
            missing = []
            if not m["has_section"]: missing.append("section")
            if not m["has_og_article"]: missing.append("og:article")
            if not m["has_twitter_label"]: missing.append("twitter:label")
            flags["missing_signals"].append((a["slug"], missing))

    rows.sort(key=lambda r: (r[4], -(r[2] if isinstance(r[2], int) else 0)))

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
    md_lines.append(f"- **EN indexable mirrors:** {en_indexable_count(public_slugs)}")
    md_lines.append(f"- **Sitemap URLs:** {sitemap_url_count()}")
    md_lines.append(f"- **Known source metadata totals:** {word_total:,} wordCount units · "
                    f"{minute_total} min reading estimate (missing metadata shown as —)")
    md_lines.append("- Metadata, length and age are diagnostics, not ranking or traffic scores.")
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
        md_lines.append(f"### Articles with no incoming public-article links "
                         f"— {len(flags['orphan'])}")
        md_lines.append("")
        md_lines.append("Review whether another public article answers a related next question. "
                        "Add a useful contextual link only when it helps the reader; do not add arbitrary topic groups.")
        md_lines.append("")
        for slug, n_in in flags["orphan"][:15]:
            md_lines.append(f"- `{slug}` ({n_in} links)")
        md_lines.append("")

    if flags["short"]:
        md_lines.append(f"### Length inventory (source wordCount <1500) "
                         f"— {len(flags['short'])}")
        md_lines.append("")
        md_lines.append("Google has no preferred word count. Check whether the reader's question is answered; "
                        "do not pad content to reach a threshold. New clinical text still requires physician approval.")
        md_lines.append("")
        for slug, wc in flags["short"][:15]:
            md_lines.append(f"- `{slug}` ({wc:,} words)")
        md_lines.append("")

    if flags["stale"]:
        md_lines.append(f"### Recorded update age (dateModified >30 days) "
                         f"— {len(flags['stale'])}")
        md_lines.append("")
        md_lines.append("Age alone does not make an article incorrect or require a rewrite. "
                        "Review its sources and record actual substantive updates; do not change dates to imply freshness.")
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
    md_lines.append("## Interpretation references")
    md_lines.append("")
    md_lines.append("- [Google: people-first content and word-count/date cautions](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)")
    md_lines.append("- [Google: publication and modification dates](https://developers.google.com/search/docs/appearance/publication-dates)")
    md_lines.append("")

    out = "\n".join(md_lines) + "\n"
    (ROOT / "_dashboard.md").write_text(out, encoding="utf-8")
    print(f"Wrote _dashboard.md ({n} articles scored)")
    if flags["orphan"]:
        print(f"  {len(flags['orphan'])} articles have no incoming public-article links")
    if flags["short"]:
        print(f"  {len(flags['short'])} entries in the descriptive length inventory")
    if flags["stale"]:
        print(f"  {len(flags['stale'])} entries in the recorded-update-age inventory")
    if flags["missing_signals"]:
        print(f"  ⚠  {len(flags['missing_signals'])} articles missing SEO signals")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
