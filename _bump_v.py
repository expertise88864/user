#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Bump every `?v=NNN` cache-bust stamp in HTML files to a new value.

The SW is network-first on URLs containing `v=`, so changing the stamp
forces the browser to refetch instantly without waiting for SW activation.
"""
import os, re, sys, io, glob, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
NEW = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now().strftime('%Y%m%d%H%M')

# Match exact stamp 202606023000 (the previous one) AND any older stamp,
# so a single run normalises everything.
PAT = re.compile(r'(\?v=)(\d{6,14})')

def bump(path):
    with open(path, 'r', encoding='utf-8') as f:
        s = f.read()
    new_s, n = PAT.subn(lambda m: m.group(1) + NEW, s)
    if n:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_s)
    return n

total_files = 0
total_subs  = 0
for path in glob.glob(os.path.join(ROOT, '**', '*.html'), recursive=True):
    if os.sep + 'pagefind' + os.sep in path:
        continue
    if os.sep + '_bin' + os.sep in path:
        continue
    n = bump(path)
    if n:
        total_files += 1
        total_subs  += n

print(f'Bumped to v={NEW}: {total_subs} stamps in {total_files} files')
