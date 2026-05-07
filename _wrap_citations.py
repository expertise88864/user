#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Wrap inline parenthesised author-year citations in <span class="cite">…</span>
so the .cite CSS rule (smaller, muted) renders them like journal-style refs.

Matches:
    (Sabroe 2021, BJD)
    (Reynolds 2024, JAAD)
    (Werfel 2024 S3)
    (NICE NG198 2024)        — guideline-style
    (TDA 2024)               — society + year
    (JACI 2019)              — journal-only + year
    (Hill 2014)              — bare author + year
Year is restricted to 1800-2099 to avoid false positives like (Fraxel 1550).

Skips:
- Anything inside <script> (any type — JSON-LD might already have refs but
  wrapping inside JSON would break the JSON syntax).
- Already-wrapped citations (idempotent).
- data-en attribute values (English content has its own ref style).
"""
import os, re, sys, io, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Citation regex: opening (, author/society/journal, year (4 digits 1800-2099),
# optional journal name after comma, closing ).
CITE_RE = re.compile(
    r'\((?!<span)('  # negative lookahead so we don't double-wrap
    + r'[A-Z][A-Za-z]+(?:\s+(?:&|et\s+al\.?))?'      # name or org/journal
    + r'(?:\s+[A-Z]+\d*)?'                            # optional 2nd uppercase token (NG198, NEJM, S3)
    + r'\s+(?:1[89]\d\d|20[0-3]\d)'                  # year 1800-2030
    + r'(?:[，,]?\s*[A-Z][A-Za-z\s\d]+(?:\s+\d+)?)?' # optional journal/issue
    + r')\)'
)

# Skip <script> blocks entirely (preserve)
SCRIPT_RE = re.compile(r'(<script\b[^>]*>.*?</script>)', re.DOTALL | re.IGNORECASE)
# Stash data-en attribute values
DATA_EN_RE = re.compile(r'data-en="[^"]*"')

def wrap(html: str) -> tuple[str, int]:
    saved = []
    def save(m):
        saved.append(m.group(0))
        return f'\x00C{len(saved)-1}\x00'
    stripped = SCRIPT_RE.sub(save, html)
    en_saved = []
    def save_en(m):
        en_saved.append(m.group(0))
        return f'\x00E{len(en_saved)-1}\x00'
    stripped = DATA_EN_RE.sub(save_en, stripped)

    n = 0
    def replace(m):
        nonlocal n
        n += 1
        return f'(<span class="cite">{m.group(1)}</span>)'
    stripped = CITE_RE.sub(replace, stripped)

    # Restore
    stripped = re.sub(r'\x00E(\d+)\x00', lambda m: en_saved[int(m.group(1))], stripped)
    final = re.sub(r'\x00C(\d+)\x00', lambda m: saved[int(m.group(1))], stripped)
    return final, n

total_files = 0
total_wraps = 0
for path in glob.glob('blog/*.html') + glob.glob('en/blog/*.html'):
    if any(skip in path for skip in ['_pdf_extracts', '_bin', 'pagefind']):
        continue
    with open(path, 'r', encoding='utf-8') as f: src = f.read()
    new, n = wrap(src)
    if n:
        with open(path, 'w', encoding='utf-8') as f: f.write(new)
        total_files += 1
        total_wraps += n
        print(f'  {path}: {n} citations wrapped')

print(f'\nTotal: {total_wraps} citations wrapped in {total_files} files')
