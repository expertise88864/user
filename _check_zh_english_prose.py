#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Keep English sentences out of the text a Chinese page actually displays.

WHY THIS EXISTS
===============
In 2026-05 the one-shot translator _fix_proseen_cjk.py (now retired) did a
whole-file str.replace(Chinese, English) on the zh SOURCE pages instead of only
adding data-en values. The /en mirror looked right, so nothing noticed for five
months: 233 visible places in 53 articles — lead paragraphs, TL;DRs, Q&A
answers, figure captions, kicker chips — showed English (or half-English
sentences like "triggers 累積到一個閾值 before a flare occurs") on the Chinese
site, plus seven corrupted data-zh attributes. Restored 2026-10-17
(branch codex/zh-text-restore).

The bilingual contract: the Chinese page shows Chinese; English for the /en
mirror lives in data-en (see _gen_en_pages.py DataEnRenderer). This check
fails when a zh page's visible prose contains an English SENTENCE, which is
the footprint that translator left behind.

WHAT COUNTS AS AN ENGLISH SENTENCE
==================================
Text is taken per block element (p, li, td, h1-h6, figcaption, …) as a reader
sees it, then cut at every CJK character. A remaining run is flagged when it
has at least 6 English words, at least 2 English function words (the, of, is,
and, to, …) and at least 3 lowercase content words. The last condition keeps
Title-Case proper names out ("Journal of the American Academy of Dermatology",
"Letter from the Editor"), bibliographic runs are skipped (author initials,
et al., PMID/doi, volume;issue), and short term glosses never reach 6 words
("Severity of Alopecia Tool", "reverse causation / confounding by indication").
Measured on 2026-10-17: 0 hits on the restored site; 68 hits in 32 pages on
the pre-restore pages (git show a4b39e05:<page>), so it would have caught the
original incident. Short fragments (kicker chips like "Patient guide · FAQ")
are below the sentence threshold and are not this check's job.

NOT CHECKED (English is legitimate there)
=========================================
<head>, script/style/code/pre, the hidden #proseEn mirror, anything hidden
(hidden attribute, display:none), <cite> and .cite/.references blocks, the
reference list after a 參考資料/References heading, the site footer, and any
element marked lang="en" (use that for a deliberate English quotation).
Out of scope: the /en mirror and /exam/** (board-exam notes are written
English-first by decision D-18), admin/dashboard tools.
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
BLOCK = frozenset("p li td th h1 h2 h3 h4 h5 h6 dd dt figcaption blockquote summary caption "
                  "div section article aside header nav main ul ol table tr details figure "
                  "label button option text title".split())
SKIP_TAGS = frozenset("head script style noscript template code pre cite footer".split())
SKIP_CLASS = re.compile(r"\b(references|cite|citation|ref-list|refs|mag-footer|mag-disc[\w-]*)\b")
REF_HEADING = re.compile(r"參考|文獻|References", re.I)
CJK_SPLIT = re.compile(r"[　-〿㐀-鿿豈-﫿＀-￯]+")
WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
FUNCTION_WORDS = frozenset("""the a an and or but of to in on at by for with from as into than
is are was were be been being has have had do does did not no can may might should would will
it its this that these those which who whom whose what when where why how if so such
your you we our they their there here also only most more less very""".split())
MIN_WORDS, MIN_FUNCTION, MIN_LOWER_CONTENT = 6, 2, 3
# Bibliographic runs (author initials, et al., PMID/doi, "1994;19(3)") are
# English by nature even outside a reference list (inline citations, figure sources).
CITATION = re.compile(r"\bet al\b|\bPMID\b|\bdoi\b|\d{4}\s*;\s*\d|\b[A-Z][a-z]+ [A-Z]{1,2}[.,]")
# Anti-vacuity floor (same idea as _check_hant_only.py): blog articles + root pages.
MIN_FILES = 55


def english_sentences(text: str) -> list[str]:
    hits = []
    for run in CJK_SPLIT.split(text):
        words = WORD.findall(run)
        if len(words) < MIN_WORDS or CITATION.search(run):
            continue
        func = sum(1 for w in words if w.lower() in FUNCTION_WORDS)
        lower_content = sum(1 for w in words if w[0].islower() and w.lower() not in FUNCTION_WORDS)
        if func >= MIN_FUNCTION and lower_content >= MIN_LOWER_CONTENT:
            hits.append(re.sub(r"\s+", " ", run).strip())
    return hits


class Scanner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[dict] = []
        self.refs_level: int | None = None
        self.hits: list[tuple[int, str]] = []

    def _skipped(self) -> bool:
        return self.refs_level is not None or any(f["skip"] for f in self.stack)

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        a = dict(attrs)
        if re.fullmatch(r"h[1-6]", tag) and self.refs_level is not None and int(tag[1]) <= self.refs_level:
            self.refs_level = None
        skip = (tag in SKIP_TAGS
                or a.get("id") == "proseEn"
                or "hidden" in a
                or (a.get("lang") or "").lower().startswith("en")
                or re.search(r"display\s*:\s*none", a.get("style") or "") is not None
                or SKIP_CLASS.search(a.get("class") or "") is not None
                or "prose-en" in (a.get("class") or "").split())
        self.stack.append({"tag": tag, "skip": skip, "buf": [], "line": self.getpos()[0],
                           "id": a.get("id") or ""})

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                while len(self.stack) > i:
                    self._close(self.stack.pop())
                return

    def _close(self, frame):
        text = "".join(frame["buf"])
        tag = frame["tag"]
        if re.fullmatch(r"h[1-6]", tag) and (REF_HEADING.search(text) or re.match(r"(en-)?refs?\b", frame["id"])):
            self.refs_level = int(tag[1])
        if tag in BLOCK:
            for hit in english_sentences(text):
                self.hits.append((frame["line"], hit))
            if self.stack:
                self.stack[-1]["buf"].append(" ")
        elif self.stack:
            self.stack[-1]["buf"].append(text)

    def handle_data(self, data):
        if self.stack and not self._skipped():
            self.stack[-1]["buf"].append(data)

    def close(self):
        super().close()
        while self.stack:
            self._close(self.stack.pop())


def scan(src: str) -> list[tuple[int, str]]:
    s = Scanner()
    s.feed(src)
    s.close()
    return s.hits


def zh_pages(root: Path = ROOT) -> list[Path]:
    pages = sorted((root / "blog").glob("*.html"))
    pages += [p for p in sorted(root.glob("*.html")) if p.name not in ("admin.html", "dashboard.html")]
    out = []
    for p in pages:
        head = p.read_text(encoding="utf-8", errors="replace")[:600]
        m = re.search(r'<html\b[^>]*lang="([^"]*)"', head, re.I)
        if m and m.group(1).lower().startswith("zh"):
            out.append(p)
    return out


def main() -> int:
    files = zh_pages()
    errors = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        for line, hit in scan(path.read_text(encoding="utf-8", errors="replace")):
            errors.append(f"{rel}:{line}: English sentence on a zh page: {hit[:160]}")
    if len(files) < MIN_FILES:
        errors.append(f"only {len(files)} zh page(s) found (expected >= {MIN_FILES}) — discovery is broken")
    if errors:
        print(f"[FAIL] {len(errors)} English sentence(s) in visible Chinese-page text "
              "(put English in data-en, mark a deliberate quotation lang=\"en\"):")
        for e in errors[:30]:
            print(f"  - {e}")
        if len(errors) > 30:
            print(f"  … and {len(errors) - 30} more")
        return 1
    print(f"[OK] no English sentences in visible text of {len(files)} zh pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
