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
    """Text of the element carrying `css_class`, matched to ITS closing tag.

    CODE_REVIEW TD-59 — the previous pattern was
    `<[a-z]+[^>]*class="X"[^>]*>([\\s\\S]*?)</[a-z]+>`: non-greedy to the first
    closing tag of ANY name. Glossary definitions are HTML-rich (the docstring
    says so), so the first `</strong>` or `</span>` inside a definition ended
    the capture. Measured on the live file: 48 of 64 `gloss-def` values were
    truncated in the emitted DefinedTerm schema — e.g. "皮膚病生活品質量表"
    instead of "皮膚病生活品質量表,10 題自評，0-30 分。生物製劑健保申請常見
    門檻 DLQI ≥ 10。" — so three quarters of the definition rich-cards this
    generator exists to produce shipped cut off. Depth-balanced now, matching
    the technique find_cards() above already uses.
    Class matching is token-aware and quote-agnostic so `class="gloss-def x"`
    or single quotes keep working.
    """
    open_re = re.compile(
        rf'<([a-z]+)\b[^>]*\bclass=(["\'])(?:[^"\']*\s)?{re.escape(css_class)}(?:\s[^"\']*)?\2',
        re.IGNORECASE,
    )
    m = open_re.search(card)
    if not m:
        return ""
    tag = m.group(1).lower()
    open_end = card.find(">", m.end())
    if open_end == -1:
        return ""
    open_end += 1

    open_tag_re = re.compile(rf"<{tag}\b", re.IGNORECASE)
    close_tag_re = re.compile(rf"</{tag}\s*>", re.IGNORECASE)
    pos = open_end
    depth = 1
    while pos < len(card) and depth > 0:
        nxt_open = open_tag_re.search(card, pos)
        nxt_close = close_tag_re.search(card, pos)
        if nxt_close is None:
            return strip_html(card[open_end:])
        if nxt_open is not None and nxt_open.start() < nxt_close.start():
            depth += 1
            pos = nxt_open.end()
        else:
            depth -= 1
            pos = nxt_close.end()
            if depth == 0:
                return strip_html(card[open_end:nxt_close.start()])
    return strip_html(card[open_end:])


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
    # EN-consolidation (DECISIONS D-17): EN glossary canonicals to ZH /glossary,
    # so its DefinedTermSet @id/url must reference /glossary (not /en/glossary)
    # to stay consistent with the canonical.
    set_url = CANONICAL_HOST + "/glossary"
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
            # EN-consolidation (DECISIONS D-17): the EN glossary's DefinedTerm
            # url points at the article that defines the term. The visible card
            # link stays /en/... (D-08, users browse EN), but the structured-data
            # url must reference the ZH canonical, so strip the /en prefix here.
            if lang == "en" and link.startswith("/en/"):
                link = link[3:]  # /en/blog/x#a -> /blog/x#a
            term["url"] = link if link.startswith('http') else CANONICAL_HOST + link
        terms.append(term)
    return terms


def build_termset(terms: list[dict], lang: str) -> dict:
    # EN-consolidation (DECISIONS D-17): EN glossary canonicals to ZH /glossary,
    # so its DefinedTermSet @id/url must reference /glossary (not /en/glossary)
    # to stay consistent with the canonical.
    set_url = CANONICAL_HOST + "/glossary"
    set_id = set_url + "#termset"
    # CODE_REVIEW TD-59 — count derived from the cards actually parsed.
    # It was hardcoded as 64 in both descriptions, so adding or removing a
    # glossary card would have left the structured data asserting a number
    # that no longer matched the page.
    count = len(terms)
    if lang == "en":
        name = "Dermatology glossary (Chinese-English)"
        description = (
            f"Hand-curated bilingual dictionary of {count} dermatology terms "
            "(scoring scales, drug classes, symptoms, procedures, "
            "anatomy) referenced across the site."
        )
    else:
        name = "皮膚科醫學詞彙 中英對照字典"
        description = (
            f"陳翊嘉醫師整理的 {count} 條皮膚科常用名詞中英對照 "
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

# Match a previous run's id-bearing block (if any) so we can clean it up.
ID_BEARING_RE = re.compile(
    r'<script type="application/ld\+json" id="dn-glossary-terms">.*?</script>\s*',
    re.DOTALL,
)


def find_all_definedtermset_blocks(html: str) -> list[tuple[int, int]]:
    """Return [(start, end)] of every <script ...>{...DefinedTermSet...}</script>
    using balanced-brace parsing (so JSON bodies containing literal '<'
    characters are still handled correctly — Chinese glossary entries
    like '< 12 = 控制不佳' broke the prior `[^<]*?` regex).
    """
    out: list[tuple[int, int]] = []
    i = 0
    while True:
        s = html.find('<script type="application/ld+json">', i)
        if s == -1:
            break
        body_start = html.find('>', s) + 1
        # Quick gate: only proceed if @type is DefinedTermSet in this script
        next_close = html.find('</script>', body_start)
        if next_close == -1:
            break
        # Need balanced-brace from body_start (skip whitespace)
        # First, find the opening `{`
        p = body_start
        while p < next_close and html[p] in ' \t\n\r':
            p += 1
        if p >= next_close or html[p] != '{':
            i = next_close + len('</script>')
            continue
        # Track braces to find matching `}` for top-level JSON object,
        # respecting string literals.
        depth = 0
        in_str = False
        escape = False
        end = -1
        for k in range(p, len(html)):
            ch = html[k]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = k + 1
                    break
        if end == -1:
            i = next_close + len('</script>')
            continue
        # Now end is just past the closing `}`. Expect `</script>` right after.
        # (Possibly trailing whitespace inside the tag.)
        tail = html.find('</script>', end)
        if tail == -1:
            i = end
            continue
        body = html[p:end]
        # Only count this block if its @type is DefinedTermSet.
        if '"@type":"DefinedTermSet"' in body:
            out.append((s, tail + len('</script>')))
        i = tail + len('</script>')
    return out


def inject(html: str, termset: dict) -> tuple[str, bool]:
    # JSON-encode and escape `<` to `<` so subsequent regex passes
    # (including any future LEGACY_STUB_RE pattern) can rely on the body
    # being `<`-free, AND to prevent any chance of </script> breakout
    # if a glossary description happened to contain '</script>' or '<!--'.
    body = json.dumps(termset, ensure_ascii=False, separators=(',', ':'))
    body = body.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    populated = f'<script type="application/ld+json">{body}</script>'

    # 1. Strip any old id="dn-glossary-terms" block from prior runs.
    new_html = ID_BEARING_RE.sub('', html)

    # 2. Find ALL existing DefinedTermSet blocks (could be many duplicates
    #    accumulated by earlier broken inject runs). Replace the FIRST
    #    one in place and DELETE the rest.
    blocks = find_all_definedtermset_blocks(new_html)
    if blocks:
        # Splice from end to start so positions stay valid.
        for start, end in reversed(blocks[1:]):
            new_html = new_html[:start] + new_html[end:]
        # Now replace the first block.
        first_start, first_end = blocks[0]
        new_html = new_html[:first_start] + populated + new_html[first_end:]
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
