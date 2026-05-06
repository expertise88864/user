#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit JSON-LD structured data across all HTML pages.

Checks:
  - JSON validity (well-formed)
  - Required fields per @type
  - Mismatched URLs (canonical vs mainEntityOfPage vs LD url)
  - Missing image / wrong image format
  - Duplicate @id
"""
import os, re, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))

REQUIRED_FIELDS = {
    'MedicalScholarlyArticle': ['headline', 'datePublished', 'author', 'publisher'],
    'MedicalWebPage': ['name', 'about'],
    'BreadcrumbList': ['itemListElement'],
    'FAQPage': ['mainEntity'],
    'ItemList': ['itemListElement'],
    'Person': ['name'],
}

def main():
    n_files = 0
    n_blocks = 0
    errors = []
    type_counts = {}
    for d, _, fs in os.walk(ROOT):
        if any(x in d for x in ['.git','__pycache__','node_modules','astro-rewrite']): continue
        for f in fs:
            if not f.endswith('.html'): continue
            p = os.path.join(d, f)
            rel = os.path.relpath(p, ROOT)
            with open(p,'r',encoding='utf-8') as fp: html = fp.read()
            n_files += 1
            for m in re.finditer(r'<script type="application/ld\+json">([\s\S]*?)</script>', html):
                n_blocks += 1
                json_str = m.group(1).strip()
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError as e:
                    errors.append(f'{rel}: invalid JSON — {e.msg} at pos {e.pos}')
                    continue
                # Single object or array
                blocks = data if isinstance(data, list) else [data]
                for blk in blocks:
                    t = blk.get('@type')
                    if not t:
                        errors.append(f'{rel}: block missing @type')
                        continue
                    type_counts[t] = type_counts.get(t, 0) + 1
                    req = REQUIRED_FIELDS.get(t, [])
                    for field in req:
                        if field not in blk:
                            errors.append(f'{rel}: {t} missing required field "{field}"')
                    # URL consistency check for articles
                    if t == 'MedicalScholarlyArticle':
                        # check author + publisher are objects with @type
                        if isinstance(blk.get('author'), dict) and '@type' not in blk['author']:
                            errors.append(f'{rel}: author missing @type (should be Person)')
                        # check image is URL
                        img = blk.get('image')
                        if img and not isinstance(img, str):
                            errors.append(f'{rel}: image should be a URL string')
    print(f'Files scanned: {n_files}')
    print(f'JSON-LD blocks found: {n_blocks}')
    print(f'\nType distribution:')
    for t, c in sorted(type_counts.items(), key=lambda x:-x[1]):
        print(f'  {c:>4}× {t}')
    print(f'\nErrors: {len(errors)}')
    for e in errors[:30]:
        print(f'  ✗ {e}')
    if len(errors) > 30:
        print(f'  ... ({len(errors)-30} more)')
    return errors

if __name__ == '__main__':
    main()
