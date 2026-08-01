#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard the bilingual attribute pairs structurally, not by memorised copy.

WHY THIS REPLACES A NORMALIZER
==============================
_normalize_bilingual_attrs.py was a one-shot migration that carried hardcoded
copies of four blocks — an <h1>, two disclaimers, a key-insight paragraph — and
rewrote pages back to them. The migration finished long ago and it now changes
zero files, but it stayed wired into REGEN_STEPS, so the moment the physician
reworded one of those blocks the next build would silently revert him. A
protection that quietly overwrites the author is worse than no protection.

What it was really protecting is the bilingual contract, and that can be
checked structurally instead of by remembering four paragraphs of copy.

THE CONTRACT, AS THE SITE ACTUALLY USES IT
===========================================
Two things read these attributes, and it is worth being exact about which,
because the obvious answer is wrong. The language TOGGLE was switched to full
navigation on 2026-05-24 (see the comment above DN.bindLangToggle) — but
DN.applyTextOnly(), the in-place swap it used to drive, is still live: 404.html
calls it on load, and blog-shared.js calls it again after every dynamic
injection (related articles, comments, word count). So both values are read at
runtime, not only by _gen_en_pages.py when it builds the /en mirror.

  1. data-zh without data-en — nothing can render this element in English.
     _gen_en_pages.py rewrites an element only when it carries data-en, so the
     mirror keeps the Chinese, and DN.translate() falls back to the zh value,
     so the toggle cannot switch it either. Measured: 0 across both locales.
     (This is NOT decision D-11 — an earlier draft of this docstring said so
     and was wrong. D-11 is the single analytics entry point, DECISIONS.md:52.)

  2. one side of a pair empty while the other is not — a translation lost
     rather than never written. Both directions break something, and neither
     is theoretical: an empty data-en makes _gen_en_pages.py replace the
     element's contents with the empty string (verified — DataEnRenderer emits
     `<p data-en=""></p>`), and an empty data-zh does the same at runtime,
     because DN.translate() returns "" rather than falling through, "" being
     not-null. A cell blank in BOTH languages is fine and does occur (an
     intentionally empty <td>), so emptiness alone is not the test; asymmetry
     is. Measured: 0 across both locales.

  3. an element carrying data-en and NO data-zh — its own text is the Chinese
     and data-en is the whole translation — must not have an empty data-en, for
     the same reason as invariant 2. There are 1,002 of these and the first
     draft of this checker waved every one of them through. Found by external
     review, reproduced before fixing.

  4. data-en repeating data-zh verbatim while holding Chinese — a translation
     that fell back to its own source. This is the shape that shipped: three
     renderers label a card `a.title_en || a.title`, and 26 of the 53 entries in
     DN.ARTICLES had no title_en, so 182 data-en values across 88 pages were the
     Chinese title. Fixed at the root (every entry now carries title_en, taken
     from the English og:title the site already publishes for that article, not
     from a translation written here) and locked at both ends: invariant 4 on
     the rendered attributes, check_article_catalog() on the source they come
     from. Measured after the fix: 0 of 17,051 pairs.

     Chinese inside an English value is NOT the test — plenty of the English
     copy legitimately quotes a Chinese term ("Rosacea (commonly called 酒糟肌)",
     Taiwanese brand names). Those differ from data-zh, so they never trip it.
     Nine such values exist and none is flagged.

WHAT THIS CANNOT CHECK, AND NOTHING ELSE DOES EITHER
====================================================
data-en being DELETED outright from one of those 1,002 elements. Afterwards it
carries no bilingual attribute at all, which is indistinguishable from ordinary
Chinese prose that was never meant to be translated — there is no structural
signal left to fire on. The consequence is real (that element stays Chinese on
the /en mirror), and no other gate covers it: nothing in the pipeline asserts
that the /en tree is free of Han characters. Recorded here rather than papered
over; closing it needs a per-element inventory, which is a different design.

WHAT THIS DELIBERATELY DOES NOT CHECK
=====================================
Whether data-zh still matches the element's own visible text. It often does
not: measured across the 70 zh-Hant pages, 11,291 of 11,757 agree and 125
differ in wording — stale citations, sentences added to the prose but not to
the attribute. That drift is expected and already handled. Edits saved through
admin.html land in the visible text without being pushed back into the
attributes, and applyTextOnly()'s Case C exists precisely to trust the visible
text instead of reverting it to the data-zh boilerplate on every page load
(that reversion was the 2026-05-14 incident). Enforcing equality here would
re-create the bug the Case C branch was written to fix.

Both hold today, which is what makes them worth locking: this checker fails the
moment either stops being true, and it cannot fail for a legitimate edit to the
wording — which is exactly what the normalizer got wrong.
"""
from __future__ import annotations

import json
import re
import sys
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _html_scan import attributes, iter_tags, mask_inert_regions  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKIP_DIRS = {".git", "node_modules", "__pycache__", "pagefind"}
SKIP_NAMES = {"404.html", "offline.html", "admin.html", "reset-sw.html"}

HAN = re.compile(r"[一-鿿]")

# The article catalog three components read to label a card or a chip.
SHARED_JS = ROOT / "blog" / "blog-shared.js"
CATALOG_ENTRY = re.compile(r"\{[^{}]*\}")
CATALOG_SLUG = re.compile(r"""slug\s*:\s*(['"])(.*?)\1""")
# Measured 2026-08-01: 53 published entries. 40 leaves room for retirement
# without the floor firing on ordinary editing.
MIN_CATALOG_ENTRIES = 40

# blog/*.html that are legitimately not catalog entries: two hub pages, and the
# two clinician-facing companions to patient articles, which are reached from
# their patient version rather than listed as separate reading.
NON_CATALOG_PAGES = {"index", "topics",
                     "isotretinoin-clinical", "topical-acids-clinical"}


def article_catalog() -> list[tuple[str, str]]:
    """(slug, entry-source) for each real article in DN.ARTICLES.

    Objects without a quoted slug are function bodies and short-lived literals
    that happen to live in the same region — `{ slug: a.slug, date: ... }` — not
    catalog entries, so they are skipped rather than counted or validated.
    """
    src = SHARED_JS.read_text(encoding="utf-8", errors="replace")
    start = src.find("DN.ARTICLES = [")
    if start < 0:
        return []
    end = src.find("\n  ];", start)
    if end < 0:
        return []
    out = []
    for match in CATALOG_ENTRY.finditer(src[start:end]):
        slug = CATALOG_SLUG.search(match.group(0))
        if slug:
            out.append((slug.group(2), match.group(0)))
    return out


def check_article_catalog() -> list[str]:
    """Every card label must have an English form that is actually English.

    blog-article-footer.js, blog-hub.js (twice) all render an English label as
    `a.title_en || a.title`, so a missing title_en silently emits the Chinese
    title into data-en and the /en mirror shows Chinese. That is exactly how 182
    Chinese data-en values reached production across 88 pages. The fallbacks are
    left in place as defensive code; this makes them unreachable.
    """
    errors: list[str] = []
    entries = article_catalog()
    for slug, entry in entries:
        for field in ("title_en", "tag_en"):
            m = re.search(field + r"""\s*:\s*(['"])((?:[^'"\\]|\\.)*)\1""", entry)
            if not m:
                errors.append(
                    f"blog/blog-shared.js: article {slug!r} has no {field} — "
                    f"the card renderers fall back to the Chinese title, which "
                    f"lands in data-en and ships Chinese to the /en mirror")
            elif not m.group(2).strip():
                errors.append(
                    f"blog/blog-shared.js: article {slug!r} has an empty {field}")
            elif HAN.search(m.group(2)):
                errors.append(
                    f"blog/blog-shared.js: article {slug!r} has a Chinese "
                    f"{field}: {m.group(2)[:50]!r}")
    if len(entries) < MIN_CATALOG_ENTRIES:
        errors.append(
            f"only {len(entries)} catalog entr(ies) parsed from DN.ARTICLES "
            f"(expected >= {MIN_CATALOG_ENTRIES}) — the parse is broken, so a "
            f"pass here would mean nothing")

    # A floor cannot see one missing row: delete a single entry and 52 still
    # clears 40. Compare against the article files instead, which is an exact
    # relationship rather than a threshold — measured, every catalog slug has a
    # page and every page outside NON_CATALOG_PAGES has an entry. An article
    # dropped from the catalog vanishes from search, from the /blog listing
    # blog-hub.js completes at runtime, and from every recommendation, while the
    # page itself still serves.
    catalog_slugs = {slug for slug, _ in entries}
    on_disk = {p.stem for p in (ROOT / "blog").glob("*.html")}
    for slug in sorted(catalog_slugs - on_disk):
        errors.append(
            f"blog/blog-shared.js: catalog lists {slug!r} but blog/{slug}.html "
            f"does not exist")
    for slug in sorted(on_disk - catalog_slugs - NON_CATALOG_PAGES):
        errors.append(
            f"blog/blog-shared.js: blog/{slug}.html exists but no DN.ARTICLES "
            f"entry — the page still serves, yet it is absent from search, from "
            f"the /blog listing and from every recommendation")
    return errors

# Anti-vacuity floor. The site carries ~17,000 pairs; if a scan ever reports a
# few hundred, discovery broke and a pass would mean nothing.
MIN_PAIRS = 10000


def pages() -> list[Path]:
    out = []
    for path in sorted(ROOT.rglob("*.html")):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.name in SKIP_NAMES:
            continue
        out.append(path)
    return out


def glossary_terms(path: Path) -> int:
    """How many DefinedTerms this glossary page publishes."""
    if not path.exists():
        return -1
    for match in re.finditer(
            r'<script type="application/ld\+json">([\s\S]*?)</script>',
            path.read_text(encoding="utf-8", errors="replace")):
        try:
            obj = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("@type") == "DefinedTermSet":
            return len(obj.get("hasDefinedTerm") or [])
    return -1


def check_glossary_parity() -> list[str]:
    """The two glossaries must publish the same number of terms.

    CODE_REVIEW 2026-08-01 — a data-en added while translating the glossary
    landed on a <div> that turned out to enclose nine <div class="gloss-card">
    blocks. Since data-en replaces an element's inner HTML wholesale, those
    cards ceased to exist on the mirror: 64 DefinedTerms became 55, and
    _normalize_mentions.py — which reads the term list out of the glossary —
    then dropped those terms from the JSON-LD of thirty-odd articles. Every
    gate stayed green, because nothing compared the two pages.

    A general "the mirror must not lose elements" rule is not available: 55
    pages legitimately have fewer, because prefer_static_english_blocks() drops
    the Chinese body when an English one exists. This is the narrow version,
    aimed at the structure that actually broke and that other files depend on.
    """
    zh = glossary_terms(ROOT / "glossary.html")
    en = glossary_terms(ROOT / "en" / "glossary.html")
    if zh < 1:
        return ["glossary.html: no DefinedTermSet found — the schema "
                "normalizer did not run, so parity here would mean nothing"]
    if en < 0:
        return ["en/glossary.html: no DefinedTermSet found"]
    if zh != en:
        return [f"glossary term count differs: glossary.html has {zh}, "
                f"en/glossary.html has {en} — a data-en on a container has "
                f"most likely swallowed whole gloss-card blocks on the mirror"]
    return []


def main() -> int:
    errors: list[str] = check_article_catalog() + check_glossary_parity()
    pairs = 0
    en_only = 0
    files = pages()

    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        src = mask_inert_regions(path.read_text(encoding="utf-8", errors="replace"))
        for _start, tag in iter_tags(src):
            attrs = attributes(tag)
            zh, en = attrs.get("data-zh"), attrs.get("data-en")
            if zh is None and en is None:
                continue
            if en is None:
                errors.append(
                    f"{rel}: data-zh with no data-en — the /en mirror will keep "
                    f"this Chinese: {tag[:120]}")
                continue
            if zh is None:
                # The element's own text is the Chinese; data-en translates it.
                # The value still has to say something. _gen_en_pages.py
                # replaces the element's contents with whatever data-en holds,
                # so an empty one blanks it on the mirror exactly as it does in
                # a pair — verified: `<a data-en="">首頁</a>` renders as
                # `<a data-en=""></a>`.
                en_only += 1
                if not en.strip():
                    errors.append(
                        f"{rel}: data-en is empty on an element whose own text "
                        f"is the Chinese — the /en mirror will render it "
                        f"blank: {tag[:120]}")
                continue
            pairs += 1
            if bool(zh.strip()) != bool(en.strip()):
                missing = "data-en" if zh.strip() else "data-zh"
                errors.append(
                    f"{rel}: {missing} is empty while its counterpart is not — "
                    f"a translation was lost: {tag[:120]}")
            elif (unescape(zh) == unescape(en)) and HAN.search(unescape(en)):
                errors.append(
                    f"{rel}: data-en repeats data-zh verbatim and is Chinese — "
                    f"this is a translation that fell back to the source, not a "
                    f"translation: {unescape(en)[:70]}")

    if pairs < MIN_PAIRS:
        errors.append(
            f"only {pairs} bilingual pair(s) inspected across {len(files)} file(s) "
            f"(expected >= {MIN_PAIRS}) — discovery is broken, so a pass here "
            f"would mean nothing")

    if errors:
        print(f"[FAIL] bilingual attribute audit found {len(errors)} issue(s):")
        for line in errors[:25]:
            print(f"  - {line}")
        if len(errors) > 25:
            print(f"  … and {len(errors) - 25} more")
        return 1

    print(f"[OK] bilingual attributes consistent ({len(files)} files, "
          f"{pairs} pairs, {en_only} elements whose own text is the Chinese, "
          f"{len(article_catalog())} catalog entries with an English label)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
