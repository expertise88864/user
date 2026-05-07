#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""G4 — Replace static og:image with dynamic /api/og?title=…&tag=…&date=… on
all article pages.

Skips:
  - Pages that already point to /api/og (idempotent)
  - Pages without an <h1> (we need the title)

Pulls from the page itself:
  - title:    first <h1> data-zh OR text content
  - tag:      .text-[11px].uppercase eyebrow OR <meta name="article:tag">
  - date:     JSON-LD datePublished / dateModified, or visible date

For non-article pages (about, /, etc.) we leave the og:image alone.
"""
import os, re, sys, io, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
BLOG = os.path.join(ROOT, 'blog')

OG_IMAGE_RE = re.compile(
    r'(<meta\s+property="og:image"\s+content=")([^"]+)(")',
    re.IGNORECASE
)
TWITTER_IMAGE_RE = re.compile(
    r'(<meta\s+name="twitter:image"\s+content=")([^"]+)(")',
    re.IGNORECASE
)

H1_DATAZH_RE = re.compile(r'<h1[^>]*\bdata-zh="([^"]+)"', re.IGNORECASE)
H1_TEXT_RE = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.IGNORECASE)
TITLE_TAG_RE = re.compile(r'<title>([^<]+)</title>', re.IGNORECASE)
KICKER_RE = re.compile(
    r'<div[^>]*class="[^"]*tracking-\[\.22em\][^"]*"[^>]*>([^<]+)</div>',
    re.IGNORECASE
)
DATE_PUB_RE = re.compile(r'"datePublished"\s*:\s*"([^"T]+)')
DATE_MOD_RE = re.compile(r'"dateModified"\s*:\s*"([^"T]+)')

def extract_meta(html):
    title = ''
    m = H1_DATAZH_RE.search(html)
    if m:
        title = m.group(1)
    else:
        m = H1_TEXT_RE.search(html)
        if m:
            inner = re.sub(r'<[^>]+>', '', m.group(1))
            title = re.sub(r'\s+', ' ', inner).strip()
    if not title:
        # Fall back to <title> minus the suffix
        m = TITLE_TAG_RE.search(html)
        if m:
            t = m.group(1)
            t = re.split(r'\s*[—|·]\s*Chen\s*Dermatologist', t, maxsplit=1)[0]
            t = re.split(r'\s*\|\s*', t, maxsplit=1)[0]
            title = t.strip()
    title = (title or '').replace('&nbsp;', ' ').strip()

    kicker = ''
    m = KICKER_RE.search(html)
    if m:
        kicker = re.sub(r'·.*$', '', m.group(1)).strip()

    date = ''
    m = DATE_PUB_RE.search(html) or DATE_MOD_RE.search(html)
    if m:
        date = m.group(1)

    return title, kicker, date

def build_og_url(title, kicker, date):
    qs = {'title': title}
    if kicker:
        qs['tag'] = kicker
    if date:
        qs['date'] = date
    return 'https://chendermatologist.com/api/og?' + urllib.parse.urlencode(qs)

def patch_html(html):
    title, kicker, date = extract_meta(html)
    if not title:
        return html, False
    og_url = build_og_url(title, kicker, date)
    new = OG_IMAGE_RE.sub(lambda m: m.group(1) + og_url + m.group(3), html, count=1)
    new = TWITTER_IMAGE_RE.sub(lambda m: m.group(1) + og_url + m.group(3), new, count=1)
    return new, new != html

def main():
    n = 0
    skipped = 0
    for f in sorted(os.listdir(BLOG)):
        if not f.endswith('.html') or f == 'index.html':
            continue
        p = os.path.join(BLOG, f)
        with open(p, 'r', encoding='utf-8') as fp:
            src = fp.read()
        new, changed = patch_html(src)
        if changed:
            with open(p, 'w', encoding='utf-8') as fp:
                fp.write(new)
            n += 1
        else:
            skipped += 1
    print(f'Patched {n} article pages with dynamic og:image')
    print(f'Skipped {skipped} (no <h1> or no og:image)')

if __name__ == '__main__':
    main()
