#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Parse <ol class="references"> Vancouver citations and emit a
top-level JSON-LD `citation` block (ScholarlyArticle @graph).

Why: Google + AI crawlers (Perplexity, ChatGPT, Claude) actively use
schema.org citation graphs to:
  • Assess E-E-A-T (Experience, Expertise, Authoritativeness, Trust)
  • Trace medical claims to peer-reviewed sources (YMYL ranking factor)
  • Surface "Sources: this article cites N publications" in SERPs
  • Disambiguate medical claims via PMID/DOI cross-reference

Each <li> in <ol class="references"> is parsed for:
  - PMID (regex `PMID:\\s*\\d+`)
  - DOI (from <a href="https://doi.org/..."> or doi.org/... text)
  - Journal name (from <em>...</em>)
  - Publication year (4-digit after journal)
  - Title (heuristic: text between authors and journal)

Emits a new <script type="application/ld+json" id="dn-citations">
block before </head>. Idempotent.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent


# --- Parsing helpers --------------------------------------------------------

OL_RE = re.compile(
    r'<ol class="references">(.*?)</ol>', re.DOTALL | re.IGNORECASE,
)
# An <li> that DOES have the category-header marker (list-style:none) is a
# heading like "**Diagnosis and classification**" — skip it.
#
# NOTE: data-zh / data-en attributes can contain UNESCAPED <strong>...</strong>
# (e.g. `data-zh="<strong>診斷</strong>"`). Naïve `<li[^>]*>` matches up to
# the first `>` even inside quoted attrs, breaking attribute parsing. The
# quote-aware alternation `[^>"]|"[^"]*"` skips over `>` characters that
# appear inside quoted attribute values.
LI_RE = re.compile(
    r'<li(?P<attrs>(?:[^>"]|"[^"]*")*)>(?P<body>.*?)</li>',
    re.DOTALL | re.IGNORECASE,
)
PMID_RE = re.compile(r'PMID:\s*(\d{4,9})', re.IGNORECASE)
DOI_HREF_RE = re.compile(
    r'href="https?://(?:dx\.)?doi\.org/([^"#?\s]+)"', re.IGNORECASE,
)
DOI_TEXT_RE = re.compile(
    r'\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b', re.IGNORECASE,
)
EM_RE = re.compile(r'<em>(.*?)</em>', re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r'<[^>]+>')
YEAR_RE = re.compile(r'\b(19[5-9]\d|20\d{2})\b')


def strip_tags(s: str) -> str:
    """Remove HTML tags and collapse whitespace; decode common entities."""
    s = TAG_RE.sub('', s)
    s = (s.replace('&amp;', '&')
          .replace('&lt;', '<')
          .replace('&gt;', '>')
          .replace('&quot;', '"')
          .replace('&#39;', "'")
          .replace('&nbsp;', ' '))
    return re.sub(r'\s+', ' ', s).strip()


def parse_citation(li_html: str) -> dict | None:
    """Parse a single <li>...</li> body into a ScholarlyArticle dict.

    Returns None for category headers (list-style:none rows)."""
    text = strip_tags(li_html)
    if not text or len(text) < 20:
        return None
    # Category header — short bold label, drop
    if text.endswith(':') or len(text) < 30:
        return None

    citation: dict = {
        "@type": "ScholarlyArticle",
        "name": text[:500],
    }

    em = EM_RE.search(li_html)
    if em:
        journal = strip_tags(em.group(1))
        if journal:
            citation["isPartOf"] = {
                "@type": "Periodical",
                "name": journal,
            }

    pmid = PMID_RE.search(text)
    doi_href = DOI_HREF_RE.search(li_html)
    doi_text = None if doi_href else DOI_TEXT_RE.search(text)

    identifiers: list[dict] = []
    same_as: list[str] = []
    if pmid:
        identifiers.append({
            "@type": "PropertyValue",
            "propertyID": "PMID",
            "value": pmid.group(1),
        })
        same_as.append(f"https://pubmed.ncbi.nlm.nih.gov/{pmid.group(1)}/")
    if doi_href:
        doi_value = doi_href.group(1).rstrip('/')
        identifiers.append({
            "@type": "PropertyValue",
            "propertyID": "DOI",
            "value": doi_value,
        })
        same_as.append(f"https://doi.org/{doi_value}")
    elif doi_text:
        doi_value = doi_text.group(1).rstrip('.').rstrip(',')
        identifiers.append({
            "@type": "PropertyValue",
            "propertyID": "DOI",
            "value": doi_value,
        })
        same_as.append(f"https://doi.org/{doi_value}")
    if identifiers:
        citation["identifier"] = identifiers if len(identifiers) > 1 else identifiers[0]
    if same_as:
        citation["sameAs"] = same_as

    year = YEAR_RE.search(text)
    if year:
        citation["datePublished"] = year.group(1)

    return citation


def extract_citations(html: str) -> list[dict]:
    """Find <ol class="references"> and parse each <li> into a citation."""
    out: list[dict] = []
    for ol in OL_RE.finditer(html):
        body = ol.group(1)
        for li in LI_RE.finditer(body):
            attrs = li.group('attrs') or ''
            # Skip category-header rows (have list-style:none in style)
            if 'list-style:none' in attrs:
                continue
            parsed = parse_citation(li.group('body'))
            if parsed:
                out.append(parsed)
    return out


# --- Injection --------------------------------------------------------------

EXISTING_RE = re.compile(
    r'<script type="application/ld\+json" id="dn-citations">.*?</script>\s*',
    re.DOTALL,
)


def serialize_citations(citations: list[dict]) -> str:
    graph = {
        "@context": "https://schema.org",
        "@graph": citations,
    }
    body = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
    return (
        '<script type="application/ld+json" id="dn-citations">'
        f'{body}'
        '</script>\n'
    )


def inject_citations(html: str, citations: list[dict]) -> tuple[str, bool]:
    if not citations:
        # Strip any stale block
        if EXISTING_RE.search(html):
            return EXISTING_RE.sub('', html), True
        return html, False
    new_block = serialize_citations(citations)
    if EXISTING_RE.search(html):
        new_html = EXISTING_RE.sub(new_block, html, count=1)
        return new_html, new_html != html
    head_close = html.find("</head>")
    if head_close == -1:
        return html, False
    new_html = html[:head_close] + new_block + html[head_close:]
    return new_html, True


# --- Main -------------------------------------------------------------------

def process_file(fp: Path) -> tuple[bool, int]:
    src = fp.read_text(encoding="utf-8")
    citations = extract_citations(src)
    new_src, changed = inject_citations(src, citations)
    if changed:
        fp.write_text(new_src, encoding="utf-8")
    return changed, len(citations)


def main() -> int:
    blog = ROOT / "blog"
    en_blog = ROOT / "en" / "blog"
    total_changed = 0
    total_citations = 0
    files_with_citations = 0
    for base in (blog, en_blog):
        if not base.exists():
            continue
        for fp in sorted(base.glob("*.html")):
            changed, n = process_file(fp)
            if changed:
                total_changed += 1
            if n:
                total_citations += n
                files_with_citations += 1
    print(f"[citations] parsed {total_citations} Vancouver refs from "
          f"{files_with_citations} articles; modified {total_changed} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
