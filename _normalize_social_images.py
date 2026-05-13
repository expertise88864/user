#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Normalize article og:image / twitter:image values.

Prefer existing static OG assets. Fall back to a clean dynamic /api/og URL built
from the page title, never from raw data-* attributes that may contain HTML.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).parent
DOMAIN = 'https://chendermatologist.com'
BLOG = ROOT / 'blog'
OG_DIR = ROOT / 'assets' / 'og'


def clean_text(src: str) -> str:
    src = re.sub(r'<[^>]+>', ' ', src)
    return re.sub(r'\s+', ' ', html.unescape(src)).strip()


def title_from_page(src: str, slug: str) -> str:
    title_m = re.search(r'<title>([\s\S]*?)</title>', src, re.I)
    if title_m:
        title = clean_text(title_m.group(1))
        title = re.split(r'\s*[|]\s*ChenDermatologist', title, maxsplit=1)[0]
        title = re.split(r'\s*[·]\s*陳翊嘉', title, maxsplit=1)[0]
        if title:
            return title[:80]
    h1_m = re.search(r'<h1\b[^>]*>([\s\S]*?)</h1>', src, re.I)
    if h1_m:
        title = clean_text(h1_m.group(1))
        if title:
            return title[:80]
    return slug.replace('-', ' ').title()


def date_from_page(src: str) -> str:
    m = re.search(r'"date(?:Published|Modified)"\s*:\s*"(\d{4}-\d{2}-\d{2})"', src)
    return m.group(1) if m else ''


def image_for(slug: str, src: str) -> str:
    for ext in ('png', 'webp'):
        if (OG_DIR / f'{slug}.{ext}').exists():
            return f'{DOMAIN}/assets/og/{slug}.{ext}'
    qs = {'title': title_from_page(src, slug), 'tag': '皮膚科衛教'}
    date = date_from_page(src)
    if date:
        qs['date'] = date
    return f'{DOMAIN}/api/og?' + urllib.parse.urlencode(qs)


def patch_meta(src: str, image_url: str) -> str:
    for attr in ('property="og:image"', 'name="twitter:image"'):
        src = re.sub(
            rf'(<meta\s+{attr}\s+content=")[^"]*(")',
            lambda m: m.group(1) + html.escape(image_url, quote=True) + m.group(2),
            src,
            count=1,
            flags=re.I,
        )
    return src


def main() -> None:
    n = 0
    for path in sorted(BLOG.glob('*.html')):
        if path.name in {'index.html', 'topics.html'}:
            continue
        src = path.read_text(encoding='utf-8')
        image_url = image_for(path.stem, src)
        next_src = patch_meta(src, image_url)
        if next_src != src:
            path.write_text(next_src, encoding='utf-8')
            n += 1
            print('normalized social image', path.relative_to(ROOT).as_posix())
    print(f'Normalized social images in {n} files')


if __name__ == '__main__':
    main()
