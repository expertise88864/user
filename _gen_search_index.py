#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pre-build full-text search index → /assets/search-index.json

Scans every blog/*.html, extracts:
  - title (from <h1>)
  - h2/h3 section headings (so users can search "第一線治療" etc.)
  - first <p> paragraph (~200 chars, gives context)
  - tag (from header chip span if present)
  - date (from data-pubdate or filename)

The Cmd+K search merges this with DN.ARTICLES at runtime so users find content,
not just titles. JSON is ~30-80 KB gzipped — a one-time cost on first search open.
"""
import os, re, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
BLOG = os.path.join(ROOT, 'blog')
OUT = os.path.join(ROOT, 'assets', 'search-index.json')

SKIP = {'index.html', 'topics.html', 'feed.xml', 'atom.xml'}

def strip_tags(s):
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def extract(html):
    out = {}
    m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.IGNORECASE)
    if m:
        out['title'] = strip_tags(m.group(1))[:120]
    headings = []
    for m in re.finditer(r'<h[23][^>]*>([\s\S]*?)</h[23]>', html, re.IGNORECASE):
        t = strip_tags(m.group(1))
        if t and len(t) <= 80:
            headings.append(t)
    if headings:
        out['h'] = headings[:20]
    pm = re.search(r'<p[^>]*>([\s\S]{40,400}?)</p>', html, re.IGNORECASE)
    if pm:
        out['snippet'] = strip_tags(pm.group(1))[:200]
    # date
    dm = re.search(r'datetime="(\d{4}-\d{2}-\d{2})"', html) or \
         re.search(r'(\d{4}-\d{2}-\d{2})', html)
    if dm:
        out['date'] = dm.group(1)
    return out

def main():
    entries = []
    for fn in sorted(os.listdir(BLOG)):
        if not fn.endswith('.html') or fn in SKIP:
            continue
        path = os.path.join(BLOG, fn)
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        data = extract(html)
        if not data.get('title'):
            continue
        slug = fn[:-5]
        entries.append({
            'slug': slug,
            'title': data['title'],
            'h': data.get('h', []),
            'snippet': data.get('snippet', ''),
            'date': data.get('date', ''),
            'url': '/blog/' + slug,
        })
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # Compact JSON (no indent) — saves ~40% bytes
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, separators=(',', ':'))
    size = os.path.getsize(OUT)
    print(f'Wrote {len(entries)} entries → assets/search-index.json ({size/1024:.1f} KB)')

if __name__ == '__main__':
    main()
