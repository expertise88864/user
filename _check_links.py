#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Reproduce the CI link-check locally so we don't get spammed by failed builds."""
import os, re, glob, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

pages = set()
for p in glob.glob('**/*.html', recursive=True):
    if any(x in p for x in ['.git','node_modules']): continue
    path = p.replace(os.sep, '/')
    if path.endswith('/index.html'): pages.add('/' + path[:-10].rstrip('/') + '/')
    elif path == 'index.html': pages.add('/')
    else: pages.add('/' + path[:-5])

err = 0
broken_summary = {}
broken_examples = {}
for p in glob.glob('**/*.html', recursive=True):
    if any(x in p for x in ['.git','node_modules']): continue
    with open(p, encoding='utf-8') as f: s = f.read()
    for m in re.finditer(r'href="(/[^"#?]*)"', s):
        href = m.group(1)
        if href.startswith('//') or href.startswith('http'): continue
        if href.startswith('/blog/feed') or href.startswith('/blog/atom') or href.startswith('/sitemap') or href.startswith('/robots'): continue
        if any(c in href for c in ["'", "+", "${", "`"]): continue
        candidates = [
            href, href + '/', href + '.html',
            href[1:] if href.startswith('/') else href,
            href[1:] + '.html' if href.startswith('/') else href + '.html',
            (href[1:] + '/index.html') if href.startswith('/') else (href + '/index.html'),
        ]
        if any(os.path.exists(c) for c in candidates): continue
        if href in pages: continue
        if any(href.startswith(prefix) for prefix in ['/icon','/favicon','/apple-touch','/logo-','/blog/SUNN','/manifest','/assets','/ads']):
            continue
        broken_summary[href] = broken_summary.get(href, 0) + 1
        broken_examples.setdefault(href, []).append(p)
        err += 1

print(f'Total broken: {err}')
for href, n in sorted(broken_summary.items(), key=lambda x: -x[1])[:30]:
    examples = broken_examples[href][:2]
    print(f'  {n}x {href}  (e.g. {examples[0]})')
sys.exit(1 if err else 0)
