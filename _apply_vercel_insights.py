#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F12 — Inject Vercel Speed Insights script tag into all HTML files.

Vercel Speed Insights gathers real-user Core Web Vitals (LCP / INP / CLS)
from the production deployment. The free tier covers ~25k page views / month
which is plenty for a personal medical blog.

The injected tag is just `<script defer src="/_vercel/speed-insights/script.js"></script>`
and Vercel auto-serves the script when the project has Speed Insights enabled
in the dashboard. No npm install needed.

Idempotent: skips files already containing the sentinel.
"""
import os, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
SENTINEL = '/_vercel/speed-insights/'
TAG = '<script defer src="/_vercel/speed-insights/script.js"></script>'

def patch(html):
    if SENTINEL in html:
        return html, False
    if '</head>' not in html:
        return html, False
    return html.replace('</head>', TAG + '</head>', 1), True

def main():
    n = 0
    for d, _, fs in os.walk(ROOT):
        if any(x in d for x in ['.git', 'node_modules', '__pycache__', 'astro-rewrite', '_bin']):
            continue
        for f in fs:
            if not f.endswith('.html'):
                continue
            p = os.path.join(d, f)
            with open(p, 'r', encoding='utf-8') as fp:
                src = fp.read()
            new, changed = patch(src)
            if changed:
                with open(p, 'w', encoding='utf-8') as fp:
                    fp.write(new)
                n += 1
    print(f'Injected Vercel Speed Insights into {n} HTML files')

if __name__ == '__main__':
    main()
