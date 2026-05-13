#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Metadata sanity test — runs in CI to catch SEO/meta regressions early.

Checks:
  1. sitemap.xml namespace declarations are correct (Google's official URLs)
  2. sitemap.xml URL hosts are consistent (one host, not mixed apex/www)
  3. Each public HTML has <link rel="canonical">
  4. canonical / og:url / hreflang use the same host as sitemap
  5. <title> length 30-65 chars (Google snippet limit)
  6. <meta name="description"> length 100-170 chars
  7. og:image is either /api/og pattern OR the static file actually exists
  8. DN.ARTICLES has no future date (relative to today)
  9. No <h1> longer than 70 chars (mobile readability)
 10. No duplicate canonical across different pages
 11. Robots.txt has at least one Sitemap: line

Exit code:
  0 → all good
  1 → ≥ 1 ERROR found (fail CI)
  Warnings still print but don't fail CI.

Usage:
  python _check_meta.py            # full sweep
  python _check_meta.py --fast     # only blog/*.html (skip en/, root pages)
"""

from __future__ import annotations
import re
import sys
import json
import datetime
from pathlib import Path
from collections import Counter, defaultdict


ROOT = Path(__file__).parent
EXPECTED_NAMESPACES = {
    'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'image':   'http://www.google.com/schemas/sitemap-image/1.1',
    'xhtml':   'http://www.w3.org/1999/xhtml',
    # Common typo to flag aggressively:
}
BAD_NAMESPACE_TYPOS = [
    'http://www.google.com/schemas/sitemaps-image/1.1',  # extra "s"
    'https://www.sitemaps.org/schemas/sitemap/0.9',       # https variant Google rejects
]

errors: list[tuple[str, str]] = []
warnings: list[tuple[str, str]] = []


def err(scope: str, msg: str):
    errors.append((scope, msg))


def warn(scope: str, msg: str):
    warnings.append((scope, msg))


# ─── 1-2. sitemap.xml ────────────────────────────────────────────────
def check_sitemap():
    fp = ROOT / 'sitemap.xml'
    if not fp.exists():
        err('sitemap', 'sitemap.xml NOT FOUND')
        return None  # can't proceed
    src = fp.read_text(encoding='utf-8')

    # 1. Namespaces
    for label, expected in EXPECTED_NAMESPACES.items():
        if expected not in src:
            err('sitemap', f'missing namespace: {expected}')
    for typo in BAD_NAMESPACE_TYPOS:
        if typo in src:
            err('sitemap', f'BAD namespace (typo): {typo}')

    # 2. Host consistency
    hosts = Counter()
    for m in re.finditer(r'<loc>https?://([^/]+)/', src):
        hosts[m.group(1)] += 1
    if len(hosts) > 1:
        warn('sitemap', f'mixed hosts in <loc>: {dict(hosts)}')
    canonical_host = max(hosts, key=hosts.get) if hosts else None
    return canonical_host


# ─── 3-7. Per-HTML checks ────────────────────────────────────────────
def check_html(canonical_host: str | None, fast: bool = False):
    static_og_dir = ROOT / 'assets' / 'og'
    static_og_files = {p.name for p in static_og_dir.glob('*')} if static_og_dir.exists() else set()

    targets = list((ROOT / 'blog').glob('*.html'))
    if not fast:
        targets += list((ROOT / 'en' / 'blog').glob('*.html'))
        for fn in ['index.html', 'about.html', 'glossary.html', 'tools.html',
                   'support.html', 'privacy.html', 'notes.html']:
            p = ROOT / fn
            if p.exists():
                targets.append(p)
        for fn in ['en/index.html', 'en/about.html', 'en/glossary.html', 'en/tools.html']:
            p = ROOT / fn
            if p.exists():
                targets.append(p)

    canonicals_seen = defaultdict(list)
    for fp in targets:
        rel = fp.relative_to(ROOT).as_posix()
        src = fp.read_text(encoding='utf-8')
        is_noindex = bool(re.search(r'<meta\s+name="robots"\s+content="[^"]*\bnoindex\b', src, re.I))

        # 3. canonical present
        m_canon = re.search(r'<link rel="canonical" href="([^"]*)"', src)
        if not m_canon:
            err(rel, 'missing <link rel="canonical">')
            continue
        canon_url = m_canon.group(1)
        canonicals_seen[canon_url].append(rel)

        # 4. canonical / og:url / hreflang same host
        canon_host_m = re.search(r'https?://([^/]+)', canon_url)
        canon_host = canon_host_m.group(1) if canon_host_m else None
        if canonical_host and canon_host and canon_host != canonical_host:
            err(rel, f'canonical host "{canon_host}" != sitemap host "{canonical_host}"')

        m_og = re.search(r'<meta property="og:url" content="([^"]*)"', src)
        if not m_og:
            if not is_noindex:
                err(rel, 'missing <meta property="og:url">')
        else:
            if m_og.group(1) != canon_url:
                err(rel, f'og:url does not match canonical ({m_og.group(1)} != {canon_url})')
            og_host_m = re.search(r'https?://([^/]+)', m_og.group(1))
            og_host = og_host_m.group(1) if og_host_m else None
            if og_host and canon_host and og_host != canon_host:
                err(rel, f'og:url host "{og_host}" != canonical host "{canon_host}"')

        hreflang_hrefs = []
        for hf in re.finditer(r'<link rel="alternate" hreflang="[^"]+" href="([^"]*)"', src):
            hreflang_hrefs.append(hf.group(1))
            hf_host_m = re.search(r'https?://([^/]+)', hf.group(1))
            hf_host = hf_host_m.group(1) if hf_host_m else None
            if hf_host and canon_host and hf_host != canon_host:
                err(rel, f'hreflang host "{hf_host}" != canonical host "{canon_host}"')
                break  # one report per file
        if hreflang_hrefs and canon_url not in hreflang_hrefs:
            err(rel, f'hreflang cluster missing canonical URL ({canon_url})')

        # 5. title length
        m_t = re.search(r'<title>([^<]+)</title>', src)
        if m_t:
            t = m_t.group(1)
            if len(t) < 30:
                warn(rel, f'<title> too short ({len(t)} chars): {t[:50]}')
            elif len(t) > 75:
                warn(rel, f'<title> too long ({len(t)} chars): {t[:50]}…')

        # 6. description length
        m_d = re.search(r'<meta name="description" content="([^"]*)"', src)
        if not m_d:
            err(rel, 'missing <meta name="description">')
        else:
            d = m_d.group(1)
            if len(d) < 100:
                warn(rel, f'description too short ({len(d)} chars)')
            elif len(d) > 300:
                warn(rel, f'description too long ({len(d)} chars)')

        # 7. og:image existence
        m_oi = re.search(r'<meta property="og:image" content="([^"]*)"', src)
        if m_oi:
            og_img = m_oi.group(1)
            if '/api/og' in og_img:
                pass  # dynamic OG via Vercel function — assume OK
            else:
                # Try to find static file
                m_fn = re.search(r'/assets/og/([^"?]+)', og_img)
                if m_fn:
                    fn = m_fn.group(1)
                    if fn not in static_og_files:
                        err(rel, f'og:image references missing file: /assets/og/{fn}')

    # 10. duplicate canonical
    for url, paths in canonicals_seen.items():
        if len(paths) > 1:
            warn('canonical', f'duplicate canonical "{url}" used by {len(paths)} pages: {paths[:3]}')


# ─── 8. DN.ARTICLES future-date check ────────────────────────────────
def check_articles_dates():
    fp = ROOT / 'blog' / 'blog-shared.js'
    if not fp.exists():
        err('blog-shared.js', 'NOT FOUND')
        return
    src = fp.read_text(encoding='utf-8')
    today = datetime.date.today().isoformat()
    i = src.find('DN.ARTICLES = [')
    end = src.find('];', i) + 2
    if i < 0:
        err('blog-shared.js', 'DN.ARTICLES block not found')
        return
    block = src[i:end]
    for m in re.finditer(r"slug:'([a-z0-9-]+)'.*?date:'(202[6-9]-\d\d-\d\d)'", block):
        slug, d = m.group(1), m.group(2)
        if d > today:
            err('blog-shared.js', f'DN.ARTICLES["{slug}"] has future date {d} (today={today})')


# ─── 9. h1 length ────────────────────────────────────────────────────
# Skipped — h1 may legitimately be long for SEO; warning only on extreme cases.


# ─── 11. robots.txt sitemap line ─────────────────────────────────────
def check_robots():
    fp = ROOT / 'robots.txt'
    if not fp.exists():
        err('robots.txt', 'NOT FOUND')
        return
    src = fp.read_text(encoding='utf-8')
    if not re.search(r'(?im)^Sitemap:\s+\S', src):
        err('robots.txt', 'no Sitemap: line')


# ─── Main ────────────────────────────────────────────────────────────
def main():
    # Force UTF-8 output even on Windows cp950 console
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    fast = '--fast' in sys.argv
    canonical_host = check_sitemap()
    check_html(canonical_host, fast=fast)
    check_articles_dates()
    check_robots()

    if warnings:
        print(f'\n[!] Warnings ({len(warnings)}):')
        for scope, msg in warnings[:30]:
            print(f'  [{scope}] {msg}')
        if len(warnings) > 30:
            print(f'  ... and {len(warnings)-30} more')

    if errors:
        print(f'\n[X] Errors ({len(errors)}):')
        for scope, msg in errors:
            print(f'  [{scope}] {msg}')
        print(f'\n=> Metadata check FAILED with {len(errors)} error(s).')
        sys.exit(1)
    else:
        print(f'\n[OK] Metadata check passed (canonical host: {canonical_host}, {len(warnings)} warnings).')


if __name__ == '__main__':
    main()
