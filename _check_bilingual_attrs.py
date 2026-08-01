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
     mirror keeps the Chinese (the D-11 failure class), and DN.translate()
     falls back to the zh value, so the toggle cannot switch it either.
     Measured: 0 across both locales.

  2. one side of a pair empty while the other is not — a translation lost
     rather than never written. Both directions break something, and neither
     is theoretical: an empty data-en makes _gen_en_pages.py replace the
     element's contents with the empty string (verified — DataEnRenderer emits
     `<p data-en=""></p>`), and an empty data-zh does the same at runtime,
     because DN.translate() returns "" rather than falling through, "" being
     not-null. A cell blank in BOTH languages is fine and does occur (an
     intentionally empty <td>), so emptiness alone is not the test; asymmetry
     is. Measured: 0 across both locales.

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

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _html_scan import attributes, iter_tags, mask_inert_regions  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKIP_DIRS = {".git", "node_modules", "__pycache__", "pagefind"}
SKIP_NAMES = {"404.html", "offline.html", "admin.html", "reset-sw.html"}

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


def main() -> int:
    errors: list[str] = []
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
                en_only += 1
                continue
            pairs += 1
            if bool(zh.strip()) != bool(en.strip()):
                missing = "data-en" if zh.strip() else "data-zh"
                errors.append(
                    f"{rel}: {missing} is empty while its counterpart is not — "
                    f"a translation was lost: {tag[:120]}")

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
          f"{pairs} pairs, {en_only} elements whose own text is the Chinese)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
