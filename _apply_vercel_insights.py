#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F12 — Inject Vercel Speed Insights into deployed content pages.

Vercel Speed Insights gathers real-user Core Web Vitals (LCP / INP / CLS)
from the production deployment. Availability and usage limits depend on the
project's current Vercel plan and dashboard configuration.

The injected tag is just `<script defer src="/_vercel/speed-insights/script.js"></script>`
and Vercel auto-serves the script when the project has Speed Insights enabled
in the dashboard. No npm install needed.

Idempotent: skips files already containing the sentinel. Private evidence,
backups and internal utility pages are outside this maintenance operation.
"""
from pathlib import Path
import sys

from _site_html import site_html_files

ROOT = Path(__file__).resolve().parent
SENTINEL = '/_vercel/speed-insights/'
TAG = '<script defer src="/_vercel/speed-insights/script.js"></script>'
EXCLUDE = {'admin.html', 'offline.html', 'reset-sw.html',
           'en/admin.html', 'en/offline.html', 'en/reset-sw.html'}

def patch(html):
    if SENTINEL in html:
        return html, False
    if '</head>' not in html:
        return html, False
    return html.replace('</head>', TAG + '</head>', 1), True

def main():
    # Inventory validation and UTF-8 decoding finish before the first write.
    # A bad later source must not leave an earlier page partially maintained.
    root = Path(ROOT).resolve()
    sources = []
    for path in site_html_files(root):
        relative = path.relative_to(root).as_posix()
        if relative in EXCLUDE or relative.startswith('admin/'):
            continue
        with path.open('r', encoding='utf-8', newline='') as fp:
            sources.append((path, fp.read()))

    n = 0
    for path, src in sources:
        new, changed = patch(src)
        if not changed:
            continue
        with path.open('w', encoding='utf-8', newline='') as fp:
            fp.write(new)
        n += 1
    print(f'Injected Vercel Speed Insights into {n} HTML files')
    return 0

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
