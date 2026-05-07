#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""I-series tech improvements applied to all HTML files:

I9  — LCP image preload (preload first <img> in head)
I12 — Enhanced skip-links (multiple landmarks: main, nav, footer)
I8  — Sentry browser SDK (only if SENTRY_DSN env baked in below)

Idempotent — uses sentinel `<!-- i-series-applied -->`.
"""
import os, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
SENTINEL = '<!-- i-series-applied -->'

# Set this to your Sentry DSN to enable error tracking.
# Empty = no Sentry script injected (zero overhead).
SENTRY_DSN = ''  # e.g., 'https://abc123@o12345.ingest.sentry.io/67890'

I9_PRELOAD_TEMPLATE = (
    '<link rel="preload" as="image" type="image/webp" '
    'href="{href}" fetchpriority="high">'
)

I12_SKIPLINKS = (
    '<style>'
    '.dn-skiplinks{position:absolute;left:-9999px;top:auto;z-index:9999}'
    '.dn-skiplinks:focus-within{position:fixed;top:8px;left:8px;display:flex;gap:6px}'
    '.dn-skiplinks a{background:#0c5159;color:#fff;padding:8px 14px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600;box-shadow:0 4px 12px rgba(0,0,0,.2)}'
    '.dn-skiplinks a:focus{outline:2px solid #fff;outline-offset:2px}'
    '</style>'
)
I12_SKIPLINKS_NAV = (
    '<nav class="dn-skiplinks" aria-label="Skip navigation">'
    '<a href="#main-content" data-zh="跳至主要內容" data-en="Skip to main content">跳至主要內容</a>'
    '<a href="#dn-related" data-zh="跳至相關文章" data-en="Skip to related">跳至相關文章</a>'
    '<a href="#dn-newsletter" data-zh="跳至訂閱" data-en="Skip to subscribe">跳至訂閱</a>'
    '</nav>'
)

I8_SENTRY = (
    '<script src="https://browser.sentry-cdn.com/8.7.0/bundle.tracing.min.js" '
    'integrity="sha384-PLACEHOLDER" crossorigin="anonymous" defer></script>'
    '<script>if(window.Sentry){Sentry.init({dsn:"{dsn}",tracesSampleRate:0.1,replaysSessionSampleRate:0,replaysOnErrorSampleRate:0});}</script>'
)

# Find first <img src="..."> on the page — uses webp version if available
IMG_SRC_RE = re.compile(r'<img\s+[^>]*?src="([^"]+\.(?:jpg|jpeg|png|webp))"', re.IGNORECASE)
# Source srcset (preferred): for picture/source webp
SOURCE_WEBP_RE = re.compile(r'<source[^>]+type="image/webp"[^>]+srcset="([^"]+?)"', re.IGNORECASE)

def first_image_url(html):
    """Pick the best LCP candidate URL — prefers webp from <source srcset>."""
    m = SOURCE_WEBP_RE.search(html)
    if m:
        # srcset can have "url 400w, url 800w" — take first URL
        return m.group(1).split(',')[0].strip().split(' ')[0]
    m = IMG_SRC_RE.search(html)
    return m.group(1) if m else None

def patch(html):
    if SENTINEL in html:
        return html, False
    if '</head>' not in html:
        return html, False
    inserts = [SENTINEL]
    # I9 preload
    img_url = first_image_url(html)
    if img_url:
        inserts.append(I9_PRELOAD_TEMPLATE.format(href=img_url))
    # I8 Sentry
    if SENTRY_DSN:
        inserts.append(I8_SENTRY.replace('{dsn}', SENTRY_DSN))
    head_block = ''.join(inserts)
    new = html.replace('</head>', head_block + '</head>', 1)
    # I12 skip-links — inject right after <body>
    if '<style' in I12_SKIPLINKS and 'dn-skiplinks' not in new:
        new = re.sub(r'(<body[^>]*>)', r'\1' + I12_SKIPLINKS + I12_SKIPLINKS_NAV, new, count=1)
    return new, True

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
    print(f'Applied I-series to {n} HTML files')

if __name__ == '__main__':
    main()
