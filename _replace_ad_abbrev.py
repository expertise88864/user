#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Replace standalone "AD" abbreviation with "異位性皮膚炎" in Chinese content
of atopic-dermatitis-overview.html (and en mirror).

Skips:
- data-en="..." attribute values (English content where "AD" is fine)
- Journal/society abbreviations: JAAD, AAD, BAD (matched by word-boundary \bAD\b)
- IDs / classes / lowercase 'ad' (case-sensitive match)

Also collapses redundant introduction "(AD)" after 異位性皮膚炎.
"""
import re, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PATHS = [
    'blog/atopic-dermatitis-overview.html',
    'en/blog/atopic-dermatitis-overview.html',
]

DATA_EN_RE = re.compile(r'data-en="([^"]*)"')
AD_RE      = re.compile(r'\bAD\b')

for path in PATHS:
    with open(path, 'r', encoding='utf-8') as f: s = f.read()

    # Step 1: stash all data-en values behind sentinels
    saved = []
    def save(m):
        saved.append(m.group(0))
        return f'\x00DATAEN{len(saved)-1}\x00'
    stripped = DATA_EN_RE.sub(save, s)

    # Step 2: kill the redundant "(AD)" / "（AD）" right after 異位性皮膚炎
    n_def = 0
    new, k = re.subn(r'異位性皮膚炎\s*[（(]\s*AD\s*[)）]', '異位性皮膚炎', stripped)
    n_def += k
    stripped = new

    # Step 3: replace standalone \bAD\b → 異位性皮膚炎 in zh content
    new, n_ad = AD_RE.subn('異位性皮膚炎', stripped)
    stripped = new

    # Step 4: restore data-en values
    def restore(m):
        return saved[int(m.group(1))]
    final = re.sub(r'\x00DATAEN(\d+)\x00', restore, stripped)

    with open(path, 'w', encoding='utf-8') as f: f.write(final)
    print(f'  {path}: removed {n_def} (AD) defs, replaced {n_ad} bare AD → 異位性皮膚炎')
