#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Remove leftover eczema-myths intro <section> from the 4 AD article files.

Each atopic-dermatitis-* article was cloned from eczema-myths.html, then we
replaced the <article>...</article> body with new content. But the OUTER
<section class="pt-12 sm:pt-14 pb-6"> that contains the eczema-myths kicker
+ H1 + intro paragraph was NEVER removed. Result: each AD article shows
"異位性皮膚炎 6 大迷思" at the top, then the correct AD body below.

This script finds the first <section class="pt-12...">...</section> and
removes it (only on the 4 AD article files).
"""
import os, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
AD_FILES = [
    'blog/atopic-dermatitis-overview.html',
    'blog/atopic-dermatitis-topical.html',
    'blog/atopic-dermatitis-systemic.html',
    'blog/atopic-dermatitis-comorbidity.html',
]

def remove_leftover_section(html):
    """Match the eczema-myths pre-article <section>: starts with `pt-12 sm:pt-14`
    and contains the "迷思澄清" kicker + the OLD h1.
    Walk balanced <section>...</section>."""
    # Find opening
    m = re.search(r'<section\s+class="pt-12 sm:pt-14[^"]*"[^>]*>', html)
    if not m:
        return None
    open_start = m.start()
    open_end = m.end()
    # Walk forward to balanced </section>
    depth = 1
    i = open_end
    while i < len(html) and depth > 0:
        no = html.find('<section', i)
        nc = html.find('</section>', i)
        if nc < 0: break
        if no >= 0 and no < nc:
            depth += 1; i = no + 8
        else:
            depth -= 1; i = nc + 10
    end = i
    return html[:open_start] + html[end:]

for fname in AD_FILES:
    p = os.path.join(ROOT, fname)
    if not os.path.exists(p):
        print(f'SKIP {fname}: not found')
        continue
    with open(p, 'r', encoding='utf-8') as f:
        src = f.read()
    new = remove_leftover_section(src)
    if new and new != src:
        with open(p, 'w', encoding='utf-8') as f:
            f.write(new)
        print(f'FIXED {fname}: {len(src)} -> {len(new)} bytes')
    else:
        print(f'OK    {fname}: no leftover section found')
