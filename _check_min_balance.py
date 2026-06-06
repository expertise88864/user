#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Balance check the minified JS using same walker as full check."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, 'blog', 'blog-shared.min.js'), 'r', encoding='utf-8') as f:
    src = f.read()

n = len(src)
i = 0
line = 1
col = 1
stacks = {'(': [], '[': [], '{': []}
pairs = {')': '(', ']': '[', '}': '{'}
last_signif = '\n'
errors = []

def adv(c):
    global line, col
    if c == '\n':
        line += 1; col = 1
    else:
        col += 1

while i < n:
    c = src[i]
    nx = src[i+1] if i+1 < n else ''
    if c == '/' and nx == '/':
        while i < n and src[i] != '\n':
            adv(src[i]); i += 1
        continue
    if c == '/' and nx == '*':
        adv(c); adv(nx); i += 2
        while i < n - 1 and not (src[i] == '*' and src[i+1] == '/'):
            adv(src[i]); i += 1
        if i < n - 1:
            adv(src[i]); adv(src[i+1]); i += 2
        continue
    if c in ('"', "'", '`'):
        q = c; sl, sc = line, col; adv(c); i += 1
        while i < n:
            if src[i] == '\\' and i + 1 < n:
                adv(src[i]); adv(src[i+1]); i += 2; continue
            if src[i] == q:
                adv(src[i]); i += 1; break
            if q != '`' and src[i] == '\n':
                errors.append(f'unterminated string at {sl}:{sc}'); break
            adv(src[i]); i += 1
        last_signif = q
        continue
    if c == '/' and last_signif in ('=', '(', ',', ';', ':', '!', '&', '|', '?', '{', '}', '[', '\n', '+', '-', '*', '%', '<', '>', '~', '^', 'n'):
        j = i + 1; in_cls = False; ok = False
        while j < n:
            ch = src[j]
            if ch == '\\' and j + 1 < n:
                j += 2; continue
            if ch == '[': in_cls = True
            elif ch == ']': in_cls = False
            elif ch == '/' and not in_cls:
                ok = True; j += 1
                while j < n and src[j].isalpha():
                    j += 1
                break
            elif ch == '\n':
                break
            j += 1
        if ok:
            while i < j:
                adv(src[i]); i += 1
            last_signif = '/'; continue
    if c in '([{':
        stacks[c].append((line, col))
    elif c in ')]}':
        match = pairs[c]
        if not stacks[match]:
            errors.append(f'unmatched {c} at {line}:{col}')
        else:
            stacks[match].pop()
    if not c.isspace():
        last_signif = c
    adv(c); i += 1

for op, st in stacks.items():
    if st:
        for l, co in st[:5]:
            errors.append(f'unmatched {op} at {l}:{co}')

print(f'minified size: {len(src):,} bytes')
if not errors:
    print('OK — minified file is balanced')
else:
    print(f'{len(errors)} issue(s):')
    for e in errors[:20]:
        print(' ', e)
