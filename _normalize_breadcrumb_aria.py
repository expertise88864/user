#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Add aria-label="Breadcrumb" to the breadcrumb <nav> on article pages.

WCAG 1.3.6 / ARIA landmark practice: when a page has more than one <nav>
landmark, each must have a unique accessible name so screen-reader users can
tell them apart in the landmarks list. Article pages have TWO <nav>s:
  - the breadcrumb (首頁 / 衛教文章 / …) — currently UNLABELED
  - the related-articles nav — already aria-label="Related articles"
This labels the breadcrumb to match the existing English-label convention.

Target is the exact breadcrumb opening tag used across all articles:
  <nav style="font-size:12.5px; color:var(--muted); margin-bottom:18px;">
Idempotent (skips a nav that already has aria-label). Additive only — no
text/layout/behavior change. Runs on blog/*.html + en/blog/*.html and root
pages that carry the same breadcrumb tag.
"""
from __future__ import annotations
import io, sys
from pathlib import Path

# CODE_REVIEW TD-53 — no forced newline on write. This repo runs
# core.autocrlf=true with no .gitattributes, so every other worktree file is
# CRLF; forcing LF here left the generated file permanently reported as
# modified after every build (measured: 6 files, byte-identical content).
# git still normalises to LF in the blob, so the DEPLOYED bytes are unchanged.
# Same decision already documented in _gen_llms_full.py.

ROOT = Path(__file__).resolve().parent

OLD = '<nav style="font-size:12.5px; color:var(--muted); margin-bottom:18px;">'
NEW = '<nav aria-label="Breadcrumb" style="font-size:12.5px; color:var(--muted); margin-bottom:18px;">'


def process(fp: Path) -> int:
    s = fp.read_text(encoding='utf-8')
    if OLD not in s:
        return 0
    s2 = s.replace(OLD, NEW)
    if s2 != s:
        fp.write_text(s2, encoding='utf-8')
        return s.count(OLD)
    return 0


def main() -> int:
    changed = files = 0
    targets = (list((ROOT / 'blog').glob('*.html'))
               + list((ROOT / 'en' / 'blog').glob('*.html'))
               + [p for p in ROOT.glob('*.html')]
               + [p for p in (ROOT / 'en').glob('*.html')])
    seen = set()
    for fp in targets:
        if fp in seen:
            continue
        seen.add(fp)
        n = process(fp)
        if n:
            files += 1
            changed += n
    print(f"[breadcrumb-aria] labeled {changed} breadcrumb nav(s) across {files} files")
    return 0


if __name__ == '__main__':
    sys.exit(main())
