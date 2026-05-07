#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Scan blog-shared.js for duplicated-key residue from automated edits.

Looks for the pattern: ']: [' — i.e. an array value immediately followed by
another colon and array, which is invalid JS object-literal syntax. This is
the exact shape that broke us in the AD consolidation run.
"""
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('blog/blog-shared.js', 'r', encoding='utf-8') as f:
    s = f.read()

suspects = []
for i, line in enumerate(s.splitlines(), 1):
    if re.search(r'\]:\s*\[', line):
        suspects.append((i, line.strip()[:120]))

print(f'Lines with `]: [` pattern: {len(suspects)}')
for ln, t in suspects[:10]:
    print(f'  line {ln}: {t}')

if not suspects:
    print('PASS — no duplicated-key residue.')
    sys.exit(0)
sys.exit(1)
