#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inject a DefinedTermSet JSON-LD block into /glossary.html.

Why: /glossary.html has 64 hand-curated dermatology terms (scoring
scales, drug classes, symptoms, anatomy) but currently exposes only
generic MedicalWebPage + BreadcrumbList schema. Adding an explicit
DefinedTermSet with 64 DefinedTerm entries unlocks:

  • Google's "definition" rich-card in SERPs (very high CTR for
    medical-term queries: "PASI definition", "SCORAD scoring",
    "IL-17 inhibitor")
  • Anchor deep-linking — each DefinedTerm carries its #anchor so
    Google can scroll-to-text-fragment into the right card
  • LLM/AI-crawler entity disambiguation (Perplexity, ChatGPT)
  • Bing / Yandex definition surfacing

Source format (in glossary.html):
  <div class="gloss-card">
    <span class="gloss-cat" ...>量表</span>
    <div class="gloss-term">SCORAD</div>
    <div class="gloss-en">Severity Scoring of Atopic Dermatitis</div>
    <div class="gloss-def">...HTML-rich definition...</div>
    <a class="gloss-link" href="/blog/...#anchor">SCORAD 計算器 →</a>
  </div>

Idempotent: replaces existing #dn-glossary-terms block on each run.
Wired into REGEN_STEPS after _normalize_article_metadata.py.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
GLOSSARY = ROOT / "glossary.html"
EN_GLOSSARY = ROOT / "en" / "glossary.html"


# --- Balanced-div parser for .gloss-card blocks -----------------------------

def find_cards(src: str) -> list[str]:
    """Return the inner HTML of each <div class="gloss-card">…</div>.
    Uses balanced-div depth tracking so nested divs (rare) work."""
    out: list[str] = []
    i = 0
    while True:
        start = src.find('<div class="gloss-card"', i)
        if start == -1:
            break
        open_end = src.find('>', start) + 1
        pos = open_end
        depth = 1
        while pos < len(src) and depth > 0:
            d_open = src.find('<div', pos)
            d_close = src.find('</div>', pos)
            if d_close == -1:
                break
            if d_open != -1 and d_open < d_close:
                depth += 1
                pos = d_open + 4
            else:
                depth -= 1
                pos = d_close + len('</div>')
        out.append(src[open_end:pos - len('</div>')])
        i = pos
    return out


# --- Field extraction -------------------------------------------------------

TAG_RE = re.compile(r'<[^>]+>')


def strip_html(s: str) -> str:
    s = TAG_RE.sub('', s)
    s = (s.replace('&amp;', '&')
          .replace('&lt;', '<')
          .replace('&gt;', '>')
          .replace('&quot;', '"')
          .replace('&#39;', "'")
          .replace('&nbsp;', ' '))
    return re.sub(r'\s+', ' ', s).strip()


def slugify(s: str) -> str:
    """Convert a term to a URL-safe slug for the #anchor fragment."""
    s = s.lower()
    s = re.sub(r'[^a-z0-9一-鿿\-]+', '-', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return s


def extract_field(card: str, css_class: str) -> str:
    m = re.search(
        rf'<[a-z]+[^>]*class="{re.escape(css_class)}"[^>]*>([\s\S]*?)</[a-z]+>',
        card,
        re.IGNORECASE,
    )
    return strip_html(m.group(1)) if m else ""


def extract_link(card: str) -> str:
    m = re.search(
        r'<a[^>]+class="gloss-link"[^>]+href="([^"]+)"',
        card,
        re.IGNORECASE,
    )
    return m.group(1) if m else ""


# --- Build DefinedTerm objects ----------------------------------------------

CANONICAL_HOST = "https://chendermatologist.com"


def build_terms(cards: list[str], lang: str) -> list[dict]:
    """Return a list of DefinedTerm dicts.

    `lang` is 'zh' or 'en' — controls which fields become `name` vs
    `alternateName` and the localized inDefinedTermSet URL."""
    set_url = CANONICAL_HOST + ("/en/glossary" if lang == "en" else "/glossary")
    set_id = set_url + "#termset"

    terms: list[dict] = []
    for card in cards:
        zh = extract_field(card, "gloss-term")
        en = extract_field(card, "gloss-en")
        cat = extract_field(card, "gloss-cat")
        defn = extract_field(card, "gloss-def")
        link = extract_link(card)
        if not zh and not en:
            continue
        # For EN locale, prefer English term as the primary name
        primary = en if lang == "en" and en else zh
        alternate = zh if lang == "en" else en
        if not primary:
            primary = alternate
            alternate = ""

        slug = slugify(en or zh)
        term_id = set_url + "#term-" + slug

        term: dict = {
            "@type": "DefinedTerm",
            "@id": term_id,
            "name": primary,
            "inDefinedTermSet": set_id,
        }
        if alternate and alternate != primary:
            term["alternateName"] = alternate
        if defn:
            # Cap at 500 chars — Google's definition cards truncate anyway
            term["description"] = defn[:500]
        if cat:
            # Schema.org: termCode is the category/subject label
            term["termCode"] = cat
        if link:
            term["url"] = link if link.startswith('http') else CANONICAL_HOST + link
        terms.append(term)
    return terms


def build_termset(terms: list[dict], lang: str) -> dict:
    set_url = CANONICAL_HOST + ("/en/glossary" if lang == "en" else "/glossary")
    set_id = set_url + "#termset"
    if lang == "en":
        name = "Dermatology glossary (Chinese-English)"
        description = (
            "Hand-curated bilingual dictionary of 64 dermatology terms "
            "(scoring scales, drug classes, symptoms, procedures, "
            "anatomy) referenced across the site."
        )
    else:
        name = "皮膚科醫學詞彙 中英對照字典"
        description = (
            "陳翊嘉醫師整理的 64 條皮膚科常用名詞中英對照 "
            "(包含量表、藥物、症狀、手術、解剖)，每條附 5-30 字定義。"
        )
    return {
        "@context": "https://schema.org",
        "@type": "DefinedTermSet",
        "@id": set_id,
        "name": name,
        "description": description,
        "inLanguage": "en" if lang == "en" else "zh-Hant-TW",
        "hasDefinedTerm": terms,
    }


# --- Injection --------------------------------------------------------------

# Match the legacy empty/stub DefinedTermSet block emitted by an earlier
# version of _normalize_schema.py. We'll REPLACE this in-place rather
# than appending a duplicate.
LEGACY_STUB_RE = re.compile(
    r'<script type="application/ld\+json">'
    r'(\{[^<]*?"@type":"DefinedTermSet"[^<]*?\})'
    r'</script>',
    re.DOTALL,
)

# Match a previous run's id-bearing block (if any) so we can clean it up.
ID_BEARING_RE = re.compile(
    r'<script type="application/ld\+json" id="dn-glossary-terms">.*?</script>\s*',
    re.DOTALL,
)


def inject(html: str, termset: dict) -> tuple[str, bool]:
    body = json.dumps(termset, ensure_ascii=False, separators=(',', ':'))

    # 1. Strip any old id="dn-glossary-terms" block from prior runs.
    new_html = ID_BEARING_RE.sub('', html)

    # 2. Replace the legacy stub if present; otherwise prepend before </head>.
    populated = f'<script type="application/ld+json">{body}</script>'
    if LEGACY_STUB_RE.search(new_html):
        new_html = LEGACY_STUB_RE.sub(populated, new_html, count=1)
    else:
        head_close = new_html.find("</head>")
        if head_close == -1:
            return html, False
        new_html = new_html[:head_close] + populated + '\n' + new_html[head_close:]

    return new_html, new_html != html


# --- Main -------------------------------------------------------------------

def inject_card_ids(src: str, cards: list[str], lang: str) -> str:
    """Add id="term-<slug>" to each <div class="gloss-card"> so the
    DefinedTerm.@id anchors resolve. Without this, scroll-to-text-
    fragment from SERP definition cards lands on the page top
    instead of the right term.

    Iterates cards in document order; replaces only the FIRST naked
    `<div class="gloss-card">` for each iteration, so we never
    re-process already-id'd cards. Idempotent.
    """
    new_src = src
    cursor = 0
    for card in cards:
        zh = extract_field(card, "gloss-term")
        en = extract_field(card, "gloss-en")
        if not zh and not en:
            cursor += 1
            continue
        slug = slugify(en or zh)
        target_id = f"term-{slug}"
        # Find the next naked card from cursor onward
        naked = new_src.find('<div class="gloss-card">', cursor)
        if naked == -1:
            break
        end_of_tag = new_src.find('>', naked) + 1
        replacement = f'<div class="gloss-card" id="{target_id}">'
        new_src = new_src[:naked] + replacement + new_src[end_of_tag:]
        cursor = naked + len(replacement)
    return new_src


def process(fp: Path, lang: str) -> bool:
    if not fp.exists():
        return False
    src = fp.read_text(encoding="utf-8")
    cards = find_cards(src)
    if not cards:
        return False

    # Phase 1: ensure each card has an id matching DefinedTerm.@id
    src_with_ids = inject_card_ids(src, cards, lang)

    terms = build_terms(cards, lang)
    if not terms:
        if src_with_ids != src:
            fp.write_text(src_with_ids, encoding="utf-8")
            return True
        return False
    termset = build_termset(terms, lang)
    new_src, changed = inject(src_with_ids, termset)
    if new_src != src:
        fp.write_text(new_src, encoding="utf-8")
        return True
    return False


def main() -> int:
    changed_zh = process(GLOSSARY, "zh")
    changed_en = process(EN_GLOSSARY, "en")
    total = (1 if changed_zh else 0) + (1 if changed_en else 0)
    src = GLOSSARY.read_text(encoding="utf-8") if GLOSSARY.exists() else ""
    n_terms = len(find_cards(src))
    print(f"[glossary-schema] emitted DefinedTermSet with {n_terms} "
          f"DefinedTerm entries to {total} glossary file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
