#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run after the 3 guideline-integration agents finish.

Bumps DN.ARTICLES `date` field to 2026-05-07 for every article whose HTML
was modified after a given mtime cutoff (the moment we kicked off the
agents). That way "近期更新" / "Recent" picks up only the articles that
actually got reworked, not random ones.

Usage:
    python _post_guideline_update.py [HH:MM cutoff time today]

If no cutoff given, uses 17:00 today.
"""
import os, re, sys, io, datetime, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))

# Cutoff: anything modified AFTER this counts as "touched by agents"
today = datetime.date.today()
hhmm = sys.argv[1] if len(sys.argv) > 1 else '17:00'
hh, mm = [int(x) for x in hhmm.split(':')]
cutoff = datetime.datetime(today.year, today.month, today.day, hh, mm).timestamp()
print(f'Cutoff: anything mtime > {datetime.datetime.fromtimestamp(cutoff)}')

# All blog HTML in zh + en
candidates = (
    glob.glob(os.path.join(ROOT, 'blog', '*.html'))
    + glob.glob(os.path.join(ROOT, 'en', 'blog', '*.html'))
)

# Map slug → was-touched
touched = set()
for path in candidates:
    if os.path.basename(path) in ('index.html', 'topics.html'):
        continue
    if os.path.getmtime(path) > cutoff:
        slug = os.path.basename(path).rsplit('.', 1)[0]
        touched.add(slug)

print(f'\nTouched slugs ({len(touched)}):')
for s in sorted(touched):
    print(f'  {s}')

if not touched:
    print('\nNothing touched — exiting without changes.')
    sys.exit(0)

# Update DN.ARTICLES: bump date for any matching slug
js_path = os.path.join(ROOT, 'blog', 'blog-shared.js')
with open(js_path, 'r', encoding='utf-8') as f:
    js = f.read()

new_date = today.strftime('%Y-%m-%d')
n_changed = 0
for slug in touched:
    # Match `slug:'foo', ... date:'2026-MM-DD'`  → bump date
    pat = re.compile(
        r"(slug:'" + re.escape(slug) + r"'[^}]*?date:')(\d{4}-\d{2}-\d{2})('[^}]*?\})",
        re.DOTALL,
    )
    new_js, n = pat.subn(r'\g<1>' + new_date + r'\g<3>', js, count=1)
    if n:
        js = new_js
        n_changed += 1

print(f'\nBumped DN.ARTICLES date for {n_changed} entries to {new_date}')
with open(js_path, 'w', encoding='utf-8') as f:
    f.write(js)
