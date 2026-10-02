#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Remove static cards / list items pointing to deleted article slugs.

Targets:
  - blog/index.html, en/blog/index.html: <a class="article-list-item" href="/blog/$slug">…</a>
  - blog/topics.html, en/blog/topics.html: <li><a href="/blog/$slug">…</a></li>

The historical candidates below are removed only when both article sources
are absent. Restored articles keep their navigation links.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent

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

def missing_slugs(root=ROOT):
    """Do not treat a historical deletion list as current publishing state."""
    root = Path(root)
    return [slug for slug in DEAD
            if not any((root / prefix / f'{slug}.html').is_file()
                       for prefix in ('blog', 'en/blog'))]


def clean(path, root=ROOT):
    with open(path, 'r', encoding='utf-8') as f:
        s = f.read()
    orig = s
    for slug in missing_slugs(root):
        s, _ = strip_article_list_item(s, slug)
        s, _ = strip_li(s, slug)
    if s != orig:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(s)
        return True
    return False

def main():
    for name in ['blog/index.html', 'en/blog/index.html', 'blog/topics.html', 'en/blog/topics.html']:
        changed = clean(ROOT / name, ROOT)
        print(f'  {name}: {"changed" if changed else "no change"}')


if __name__ == '__main__':
    main()
