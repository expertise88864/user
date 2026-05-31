#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Add scope="col" to every <th> inside a <thead> across blog/*.html and
en/blog/*.html (and any root *.html with .dn tables).

WCAG 1.3.1 (Info and Relationships): a <th> without scope leaves screen
readers guessing whether it heads a column or a row. All comparison tables
in this site use the pattern <thead><tr><th>...</th></tr></thead><tbody>...
so every <thead> <th> is a column header → scope="col". Idempotent: skips
<th> that already has a scope= attribute. Body <th> (row headers) are left
alone (the site has none currently).

Safe: adds an attribute only; never changes text, layout, or behavior.
Run as part of the build (REGEN) so it persists across regenerations.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
THEAD_RE = re.compile(r'<thead\b[^>]*>(.*?)</thead>', re.DOTALL | re.IGNORECASE)
# a <th ...> opening tag that does NOT already contain scope=
TH_OPEN_RE = re.compile(r'<th(?![^>]*\bscope\s*=)([^>]*)>', re.IGNORECASE)


def fix_thead(m: re.Match) -> str:
    inner = m.group(1)
    new_inner = TH_OPEN_RE.sub(lambda t: '<th scope="col"' + t.group(1) + '>', inner)
    return m.group(0).replace(inner, new_inner) if new_inner != inner else m.group(0)


def process(fp: Path) -> int:
    s = fp.read_text(encoding='utf-8')
    if '<thead' not in s:
        return 0
    new = THEAD_RE.sub(fix_thead, s)
    if new != s:
        fp.write_text(new, encoding='utf-8', newline='')
        return new.count('scope="col"') - s.count('scope="col"')
    return 0


def main() -> int:
    total_added = 0
    files_changed = 0
    targets = list((ROOT / 'blog').glob('*.html')) + list((ROOT / 'en' / 'blog').glob('*.html'))
    for name in ('tools.html', 'glossary.html', 'en/tools.html', 'en/glossary.html'):
        p = ROOT / name
        if p.exists():
            targets.append(p)
    for fp in targets:
        added = process(fp)
        if added:
            files_changed += 1
            total_added += added
    print(f"[th-scope] added scope=col to {total_added} <th> across {files_changed} files")
    return 0


if __name__ == '__main__':
    sys.exit(main())
