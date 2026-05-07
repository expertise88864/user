#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Mirror just one article's <article> body from blog/ → en/blog/."""
import os, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

slug = sys.argv[1] if len(sys.argv) > 1 else 'atopic-dermatitis-overview'
zh_path = f'blog/{slug}.html'
en_path = f'en/blog/{slug}.html'

with open(zh_path, 'r', encoding='utf-8') as f: zh = f.read()
with open(en_path, 'r', encoding='utf-8') as f: en = f.read()

ART = re.compile(r'(<article\b[^>]*>)(.*?)(</article>)', re.DOTALL)
m_zh = ART.search(zh)
m_en = ART.search(en)
if not m_zh or not m_en:
    print('no <article> in one of the files'); sys.exit(1)

new_en = en[:m_en.start(2)] + m_zh.group(2) + en[m_en.end(2):]
with open(en_path, 'w', encoding='utf-8') as f: f.write(new_en)
print(f'  ✓ {en_path}: body synced from {zh_path} ({len(new_en):,} bytes)')
