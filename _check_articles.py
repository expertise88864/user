#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Validate DN.ARTICLES array structure."""
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('blog/blog-shared.js', 'r', encoding='utf-8') as f:
    src = f.read()

m = re.search(r'DN\.ARTICLES\s*=\s*(\[[\s\S]*?\]);', src)
if not m:
    print('DN.ARTICLES not found')
    sys.exit(1)

arr_str = m.group(1)

# Strip strings to count delimiters
out = []
i = 0
n = len(arr_str)
while i < n:
    c = arr_str[i]
    if c == "'":
        j = i + 1
        while j < n:
            if arr_str[j] == "\\":
                j += 2
                continue
            if arr_str[j] == "'":
                j += 1
                break
            j += 1
        i = j
        continue
    if c == '"':
        j = i + 1
        while j < n:
            if arr_str[j] == "\\":
                j += 2
                continue
            if arr_str[j] == '"':
                j += 1
                break
            j += 1
        i = j
        continue
    out.append(c)
    i += 1

stripped = ''.join(out)
print(f'DN.ARTICLES inner stripped of strings: {len(stripped)} chars')
print(f'  braces: {{ {stripped.count("{")} / }} {stripped.count("}")}')
print(f'  brackets: [ {stripped.count("[")} / ] {stripped.count("]")}')

# Look for issues
if ',,' in arr_str:
    print('!!  double comma found')
if re.search(r'\}\s*\{', stripped):
    print('!!  adjacent objects without comma — SYNTAX ERROR')
    pos = re.search(r'\}\s*\{', stripped).start()
    print(f'    near offset {pos}: ...{arr_str[max(0,pos-50):pos+50]}...')
