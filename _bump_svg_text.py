#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Bump SVG <text font-size="N"> to a readable minimum across all article HTMLs.

Many of the inline SVG diagrams use font-size="9" / "10" / "11" which on a
typical 600-800px viewport render at 11-13 px effective and are unreadable
on phones without zooming. We bump:

    font-size="6"   → font-size="11"   (annotations / superscripts)
    font-size="7"   → font-size="11"
    font-size="8"   → font-size="12"
    font-size="9"   → font-size="13"
    font-size="10"  → font-size="13"
    font-size="11"  → font-size="13"
    font-size="12"  → font-size="13"   (consistency)

Sizes ≥ 13 are left alone.
"""
import os, re, sys, io, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))

BUMP = {6: 11, 7: 11, 8: 12, 9: 13, 10: 13, 11: 13, 12: 13}

# Match font-size attribute on any SVG element (text, tspan, etc.)
PAT = re.compile(r'(font-size=")(\d+)(")')

def bump_html(path):
    with open(path, 'r', encoding='utf-8') as f:
        s = f.read()
    n = 0
    def sub(m):
        nonlocal n
        old = int(m.group(2))
        new = BUMP.get(old, old)
        if new != old:
            n += 1
            return m.group(1) + str(new) + m.group(3)
        return m.group(0)
    s2 = PAT.sub(sub, s)
    if n:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(s2)
    return n

total_files = 0
total_subs = 0
for path in glob.glob(os.path.join(ROOT, 'blog', '*.html')) + \
            glob.glob(os.path.join(ROOT, 'en', 'blog', '*.html')):
    if os.path.basename(path) in ('index.html', 'topics.html'):
        # These are list pages — typically no inline diagrams
        pass
    n = bump_html(path)
    if n:
        total_files += 1
        total_subs += n

print(f'Bumped {total_subs} font-size attributes in {total_files} files.')
