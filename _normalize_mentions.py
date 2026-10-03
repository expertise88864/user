#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Connect article text to existing glossary DefinedTerm identifiers.

Match glossary names against clean article text and emit at most ten mentions
in the page's JSON-LD. This connects descriptive metadata to canonical glossary
anchors; it is not a verified Google MedLM query-routing mechanism, authority
transfer, "topics covered" feature, or promise of citations by other services.
See https://developers.google.com/search/docs/appearance/structured-data/search-gallery

Existing matching, ranking by occurrence count, and the output cap are retained.
Schema must continue to describe the visible article, not additional topics.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from _json_html import script_json
from _normalize_reading_shell import BLOCK as READING_SHELL_BLOCK

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
BLOG = ROOT / "blog"
EN_BLOG = ROOT / "en" / "blog"
GLOSSARY_ZH = ROOT / "glossary.html"
GLOSSARY_EN = ROOT / "en" / "glossary.html"


# --- Body text extraction --------------------------------------------------

SCRIPT_RE = re.compile(r'<script\b[^>]*>[\s\S]*?</script>', re.IGNORECASE)
STYLE_RE = re.compile(r'<style\b[^>]*>[\s\S]*?</style>', re.IGNORECASE)
SVG_RE = re.compile(r'<svg\b[^>]*>[\s\S]*?</svg>', re.IGNORECASE)
TAG_RE = re.compile(r'<[^>]+>')


def extract_body_text(html: str) -> str:
    """Return the article's visible text content, with all scripts /
    styles / SVGs / HTML tags stripped. Used to match glossary terms
    against actual prose (not schema or markup)."""
    # Generated navigation repeats authored headings; it must not alter the
    # occurrence counts or ranking of actual glossary references.
    body = READING_SHELL_BLOCK.sub('', html)
    # Drop everything before <article…> or <main…> if either exists
    art = re.search(r'<article\b[^>]*>', body, re.IGNORECASE)
    if art:
        end = body.rfind('</article>')
        if end != -1:
            body = body[art.end():end]
    body = SCRIPT_RE.sub(' ', body)
    body = STYLE_RE.sub(' ', body)
    body = SVG_RE.sub(' ', body)
    body = TAG_RE.sub(' ', body)
    body = (body.replace('&amp;', '&')
                 .replace('&lt;', '<')
                 .replace('&gt;', '>')
                 .replace('&quot;', '"')
                 .replace('&#39;', "'")
                 .replace('&nbsp;', ' '))
    return re.sub(r'\s+', ' ', body)


# --- Glossary index ---------------------------------------------------------

def load_glossary_terms(glossary_path: Path) -> list[dict]:
    """Read the DefinedTermSet JSON-LD from a glossary file and return
    the term list verbatim."""
    if not glossary_path.exists():
        return []
    src = glossary_path.read_text(encoding="utf-8")
    for m in re.finditer(
        r'<script type="application/ld\+json">([\s\S]*?)</script>', src
    ):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if obj.get("@type") == "DefinedTermSet":
            terms = obj.get("hasDefinedTerm") or []
            if isinstance(terms, list):
                return terms
    return []


def is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def build_term_index(terms: list[dict]) -> list[dict]:
    """For each DefinedTerm, build a search entry:
      {term_id, name, tokens: [(pattern, kind)], slug}
    where `pattern` is either a compiled regex (ASCII word-boundary)
    or a literal substring (CJK).

    Tokens are deduplicated and noise-filtered:
      - Drop tokens <3 chars (too generic; "TE" "Q" etc.)
      - Drop pure-stop tokens (avoid stop words)
    """
    STOP = {"and", "or", "of", "the", "for", "with", "to"}
    # Match an ASCII drug-name prefix like "Dupilumab" / "Anti-IL-23"
    # at the start of a string. Used to extract the searchable token
    # from entries like "Dupilumab（杜避炎 / 異膚抗體）" where the full
    # `name` is too specific to match free prose. We extend matching
    # to include hyphens, periods, and numbers so terms like
    # "Anti-IL-17A" / "TNF-α" / "13-cis-RA" survive.
    ASCII_PREFIX_RE = re.compile(
        r'^([A-Za-z][A-Za-z0-9\-./]{2,}'
        r'(?:\s+[A-Za-z0-9][A-Za-z0-9\-./]*){0,3})'
    )
    out: list[dict] = []
    for term in terms:
        term_id = term.get("@id")
        if not term_id:
            continue
        primary = term.get("name", "") or ""
        alt = term.get("alternateName", "") or ""
        candidates: list[str] = []
        for s in (primary, alt):
            s = s.strip()
            if not s:
                continue
            # Skip very long full-name expansions (rare in body text)
            if len(s) > 60:
                continue
            if s.lower() in STOP:
                continue
            if len(s) < 2:
                continue
            if s not in candidates:
                candidates.append(s)
            # ALSO add the ASCII drug-name prefix as its own searchable
            # token when the full string is ASCII+CJK hybrid like
            # "Dupilumab（杜避炎）". Prefix-matching catches mentions of
            # just "Dupilumab" in prose.
            if s and s[0].isascii() and not s.isascii():
                pm = ASCII_PREFIX_RE.match(s)
                if pm:
                    prefix = pm.group(1).strip(' .-')
                    if (3 <= len(prefix) <= 40
                            and prefix.lower() not in STOP
                            and prefix not in candidates):
                        candidates.append(prefix)
        if not candidates:
            continue

        tokens: list[tuple] = []
        for c in candidates:
            if is_ascii(c):
                # Word-boundary regex, case-insensitive
                # Escape special chars (e.g. "&", "/")
                # Use lookarounds for CJK-safe boundary (avoid match
                # inside larger ASCII words)
                pat = re.compile(
                    r'(?<![A-Za-z0-9])'
                    + re.escape(c)
                    + r'(?![A-Za-z0-9])',
                    re.IGNORECASE,
                )
                tokens.append((pat, "regex"))
            else:
                # CJK: literal substring match (case-insensitive irrelevant)
                tokens.append((c, "literal"))

        out.append({
            "@id": term_id,
            "name": primary or alt,
            "alternateName": alt if alt and alt != primary else None,
            "tokens": tokens,
        })
    return out


# --- Mention extraction -----------------------------------------------------

def count_matches(body: str, tokens: list[tuple]) -> int:
    total = 0
    for tok, kind in tokens:
        if kind == "regex":
            total += len(tok.findall(body))
        else:
            # CJK literal: count non-overlapping occurrences
            total += body.count(tok)
    return total


def derive_mentions(body: str, index: list[dict], own_slug: str,
                    max_mentions: int = 10) -> list[dict]:
    """Return up to `max_mentions` DefinedTerm refs the article body
    actually references. Sorted by occurrence count desc, then by
    first-occurrence position asc as a stable tiebreaker.
    """
    scored: list[tuple] = []
    for entry in index:
        # Skip if this term's slug equals own_slug (article would be
        # the canonical home for that term)
        slug = entry["@id"].rsplit("#term-", 1)[-1]
        if slug == own_slug:
            continue
        n = count_matches(body, entry["tokens"])
        if n > 0:
            positions = []
            for token, kind in entry['tokens']:
                match = token.search(body) if kind == 'regex' else None
                position = (match.start() if match else -1) if kind == 'regex' else body.find(token)
                if position >= 0:
                    positions.append(position)
            scored.append((n, min(positions), entry))
    if not scored:
        return []
    scored.sort(key=lambda t: (-t[0], t[1]))
    mentions: list[dict] = []
    for _, _, entry in scored[:max_mentions]:
        m: dict = {
            "@type": "DefinedTerm",
            "@id": entry["@id"],
            "name": entry["name"],
        }
        if entry.get("alternateName"):
            m["alternateName"] = entry["alternateName"]
        mentions.append(m)
    return mentions


# --- JSON-LD block parsing + splicing ---------------------------------------

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


def update_article(fp: Path, index: list[dict]) -> bool:
    src = fp.read_text(encoding="utf-8")
    body = extract_body_text(src)
    own_slug = fp.stem
    mentions = derive_mentions(body, index, own_slug)

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

        if mentions:
            obj["mentions"] = mentions
        else:
            # No mentions detected — strip any stale field from prior runs
            obj.pop("mentions", None)

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
        return True
    return False


# --- Main -------------------------------------------------------------------

def main() -> int:
    zh_terms = load_glossary_terms(GLOSSARY_ZH)
    en_terms = load_glossary_terms(GLOSSARY_EN)
    zh_index = build_term_index(zh_terms)
    en_index = build_term_index(en_terms)
    print(f"[mentions] loaded {len(zh_index)} ZH terms, "
          f"{len(en_index)} EN terms from glossary")

    total_changed = 0
    total_mentions = 0
    for fp in sorted(BLOG.glob("*.html")):
        # Count mentions before write (for stats)
        src = fp.read_text(encoding="utf-8")
        body = extract_body_text(src)
        n = len(derive_mentions(body, zh_index, fp.stem))
        if update_article(fp, zh_index):
            total_changed += 1
        total_mentions += n
    for fp in sorted(EN_BLOG.glob("*.html")):
        src = fp.read_text(encoding="utf-8")
        body = extract_body_text(src)
        n = len(derive_mentions(body, en_index, fp.stem))
        if update_article(fp, en_index):
            total_changed += 1
        total_mentions += n
    print(f"[mentions] wrote {total_mentions} total DefinedTerm mention "
          f"refs across {total_changed} article files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
