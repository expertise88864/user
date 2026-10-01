#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Link matching guideline citations via schema.org isBasedOn.

Derive links from the existing dn-citations graph using this module's guideline
name filters. A string match does not prove that a guideline supports a specific
clinical recommendation, and isBasedOn is not a documented automatic Google
E-E-A-T certification or ranking boost.
See https://developers.google.com/search/docs/appearance/structured-data/sd-policies

The existing filtering algorithm and citation data remain unchanged. Authors
must assess the relevance and currency of the cited clinical guidance.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from _json_html import script_json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
BLOG = ROOT / "blog"
EN_BLOG = ROOT / "en" / "blog"


# --- Guideline-detection regex ---------------------------------------------

# Treatment-oriented guideline phrasing
GUIDELINE_PHRASES = re.compile(
    r'(?i)\b(?:'
    r'guidelines? of care'
    r'|guidelines? for the management'
    r'|joint AAD-NPF guidelines?'
    r'|S[123]\s*[-]?\s*Guidelines?'
    r'|focused update'
    r'|consensus(?:\s+statement)?'
    r'|task force'
    r'|position paper'
    r'|management of'
    r'|recommendations? for'
    r'|EuroGuiDerm'
    r'|practice parameter'
    r')\b'
)

# Authority body acronyms / institutional names
AUTHORITY_BODIES = re.compile(
    r'(?i)\b(?:'
    r'AAD-NPF|AAD/NPF|AAD'
    r'|EADV|ETFAD'
    r'|EAACI|GA²LEN|GA2LEN'
    r'|British Association of Dermatologists'
    r'|Taiwanese Dermatological Association|TDA'
    r'|J\s?Dtsch\s?Dermatol\s?Ges'
    r')\b'
)

# Reject pure-methodology / non-treatment references
EXCLUDE_PHRASES = re.compile(
    r'(?i)\b(?:'
    r'clinical validation'
    r'|psychometric'
    r'|reliability and validity'
    r'|inter-?rater agreement'
    r'|cohort study'
    r')\b'
)


def is_authority_guideline(name: str) -> bool:
    if not name or len(name) < 20:
        return False
    if EXCLUDE_PHRASES.search(name):
        return False
    has_phrase = bool(GUIDELINE_PHRASES.search(name))
    has_body = bool(AUTHORITY_BODIES.search(name))
    return has_phrase or has_body


# --- Citation @graph reader ------------------------------------------------

CITATIONS_BLOCK_RE = re.compile(
    r'<script type="application/ld\+json" id="dn-citations">'
    r'([\s\S]*?)</script>',
)


def load_citations(src: str) -> list[dict]:
    m = CITATIONS_BLOCK_RE.search(src)
    if not m:
        return []
    try:
        obj = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    graph = obj.get("@graph") or []
    return graph if isinstance(graph, list) else []


def _dedup_key(name: str) -> str:
    """Normalize a citation name for dedup: first 80 chars, lowercase,
    whitespace + punctuation stripped. Catches same-paper-cited-twice
    cases where the title appears identically in two reference
    sub-sections.
    """
    s = name.lower()
    s = re.sub(r'[\s.,;:!?\-()/]+', ' ', s)
    return s.strip()[:80]


def build_is_based_on(graph: list[dict], cap: int = 5) -> list[dict]:
    """Filter the citation @graph to authority guidelines and emit a
    lean isBasedOn array (cap entries). Dedups by normalized name
    prefix so the same paper cited twice doesn't appear twice."""
    out: list[dict] = []
    seen: set[str] = set()
    for cit in graph:
        if not isinstance(cit, dict):
            continue
        name = cit.get("name") or ""
        if not is_authority_guideline(name):
            continue
        key = _dedup_key(name)
        if not key or key in seen:
            continue
        seen.add(key)
        entry: dict = {
            "@type": "ScholarlyArticle",
            "name": name[:300],
        }
        if cit.get("datePublished"):
            entry["datePublished"] = cit["datePublished"]
        if cit.get("isPartOf"):
            entry["isPartOf"] = cit["isPartOf"]
        same_as = cit.get("sameAs")
        if same_as:
            entry["sameAs"] = same_as
        ident = cit.get("identifier")
        if ident:
            entry["identifier"] = ident
        out.append(entry)
        if len(out) >= cap:
            break
    return out


# --- JSON-LD block walker --------------------------------------------------

LD_START_RE = re.compile(
    r'<script\s+type="application/ld\+json"[^>]*>',
    re.IGNORECASE,
)


def iter_jsonld_blocks(src: str):
    for m in LD_START_RE.finditer(src):
        body_start = m.end()
        close = src.find('</script>', body_start)
        if close == -1:
            continue
        yield m.start(), close + len('</script>'), src[body_start:close]


def update_article(fp: Path) -> tuple[bool, int]:
    """Inject isBasedOn into MedicalWebPage / MedicalScholarlyArticle
    blocks. Returns (changed, n_guidelines)."""
    src = fp.read_text(encoding="utf-8")
    graph = load_citations(src)
    if not graph:
        return False, 0
    based_on = build_is_based_on(graph)

    new_src = src
    offset_drift = 0
    blocks = list(iter_jsonld_blocks(src))
    for start, end, body_str in blocks:
        opening_tag_end = src.find('>', start) + 1
        opening_tag = src[start:opening_tag_end]
        try:
            obj = json.loads(body_str)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        typ = obj.get("@type")
        if typ not in {"MedicalWebPage", "MedicalScholarlyArticle"}:
            continue

        if based_on:
            obj["isBasedOn"] = based_on
        else:
            obj.pop("isBasedOn", None)

        new_body = script_json(obj)
        new_block = opening_tag + new_body + '</script>'
        new_src = (
            new_src[:start + offset_drift]
            + new_block
            + new_src[end + offset_drift:]
        )
        old_block_len = end - start
        offset_drift += len(new_block) - old_block_len

    if new_src != src:
        fp.write_text(new_src, encoding="utf-8")
        return True, len(based_on)
    return False, len(based_on)


# --- Main ------------------------------------------------------------------

def main() -> int:
    total_changed = 0
    total_guidelines = 0
    files_with = 0
    for base in (BLOG, EN_BLOG):
        if not base.exists():
            continue
        for fp in sorted(base.glob("*.html")):
            changed, n = update_article(fp)
            if changed:
                total_changed += 1
            if n > 0:
                files_with += 1
                total_guidelines += n
    print(f"[is-based-on] linked {total_guidelines} authority "
          f"guidelines as isBasedOn across {files_with} articles "
          f"(modified {total_changed} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
