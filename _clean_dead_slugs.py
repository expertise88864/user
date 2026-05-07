#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Remove static cards / list items pointing to deleted article slugs.

Targets:
  - blog/index.html, en/blog/index.html: <a class="article-list-item" href="/blog/$slug">…</a>
  - blog/topics.html, en/blog/topics.html: <li><a href="/blog/$slug">…</a></li>

Slugs cleaned: atopic-dermatitis-comorbidity, eczema-myths.
(atopic-dermatitis-topical and atopic-dermatitis-systemic were already merged
in a previous round but their card residue lingers in topics.html — clean
those too while we're here.)
"""
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DEAD = ['atopic-dermatitis-comorbidity', 'eczema-myths',
        'atopic-dermatitis-topical', 'atopic-dermatitis-systemic']

def strip_article_list_item(html, slug):
    """Remove <a class="article-list-item" href="/blog/SLUG" …>…</a> exactly once."""
    pat = re.compile(
        r'<a\s+href="(?:/en)?/blog/' + re.escape(slug) + r'"\s+class="article-list-item"[^>]*>.*?</a>',
        re.DOTALL,
    )
    new = pat.sub('', html, count=1)
    return new, new != html

def strip_li(html, slug):
    """Remove <li><a href="…SLUG">…</a></li> exactly once."""
    pat = re.compile(
        r'<li>\s*<a\s+href="(?:/en)?/blog/' + re.escape(slug) + r'"[^>]*>[^<]*</a>\s*</li>',
        re.DOTALL,
    )
    new = pat.sub('', html, count=1)
    return new, new != html

def clean(path):
    with open(path, 'r', encoding='utf-8') as f:
        s = f.read()
    orig = s
    for slug in DEAD:
        s, _ = strip_article_list_item(s, slug)
        s, _ = strip_li(s, slug)
    if s != orig:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(s)
        return True
    return False

for path in ['blog/index.html', 'en/blog/index.html', 'blog/topics.html', 'en/blog/topics.html']:
    changed = clean(path)
    print(f'  {path}: {"changed" if changed else "no change"}')
