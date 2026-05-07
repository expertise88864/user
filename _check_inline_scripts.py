#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick brace/paren balance check for inline <script> tags in index.html."""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('index.html', 'r', encoding='utf-8') as f:
    src = f.read()

script_blocks = re.findall(r'<script(?![^>]*src=)[^>]*>([\s\S]*?)</script>', src)
print(f'{len(script_blocks)} inline script blocks')

def strip_for_balance(s):
    # Remove string literals and comments
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == '"' or c == "'" or c == '`':
            q = c
            i += 1
            while i < n:
                if s[i] == '\\':
                    i += 2
                    continue
                if s[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c == '/' and i + 1 < n and s[i+1] == '*':
            j = s.find('*/', i+2)
            i = (j + 2) if j != -1 else n
            continue
        if c == '/' and i + 1 < n and s[i+1] == '/':
            j = s.find('\n', i+2)
            i = j if j != -1 else n
            continue
        out.append(c)
        i += 1
    return ''.join(out)

for i, block in enumerate(script_blocks):
    s = strip_for_balance(block)
    o, c, pl, pr = s.count('{'), s.count('}'), s.count('('), s.count(')')
    ok = (o == c) and (pl == pr)
    status = 'OK' if ok else '** UNBALANCED **'
    print(f'  block {i+1}: braces {o}/{c} parens {pl}/{pr} ({len(block)} chars) - {status}')
