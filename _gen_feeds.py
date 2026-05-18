#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regenerate sitemap.xml plus RSS / Atom feeds.

The sitemap is derived from actual public HTML files and DN.ARTICLES metadata.
That prevents stale /en/ URLs and articles missing from the JS catalog from
drifting out of the sitemap.
"""

from __future__ import annotations

import html
import os
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).parent
DOMAIN = 'https://chendermatologist.com'
SITE_NAME = 'ChenDermatologist · 皮膚科衛教筆記'
AUTHOR = '陳翊嘉 醫師'
EMAIL = 'expertise88864@gmail.com'


def clean_text(src: str) -> str:
    src = re.sub(r'<[^>]+>', ' ', src)
    return re.sub(r'\s+', ' ', html.unescape(src)).strip()


def route_for_file(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    if rel == 'index.html':
        return '/'
    if rel.endswith('/index.html'):
        return '/' + rel[:-10].rstrip('/')
    return '/' + rel[:-5]


def file_for_route(route: str) -> Path:
    if route == '/':
        return ROOT / 'index.html'
    if route.endswith('/'):
        return ROOT / route.strip('/') / 'index.html'
    rel = route.strip('/')
    html_file = ROOT / (rel + '.html')
    return html_file if html_file.exists() else ROOT / rel / 'index.html'


def html_meta(path: Path) -> dict[str, str]:
    src = path.read_text(encoding='utf-8')
    title = clean_text(re.search(r'<title>([\s\S]*?)</title>', src, re.I).group(1)) if re.search(r'<title>([\s\S]*?)</title>', src, re.I) else ''
    desc_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', src, re.I)
    desc = html.unescape(desc_m.group(1)).strip() if desc_m else ''
    date_m = re.search(r'"date(?:Published|Modified)"\s*:\s*"(\d{4}-\d{2}-\d{2})"', src)
    og_m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', src, re.I)
    return {
        'title': title,
        'description': desc,
        'date': date_m.group(1) if date_m else datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'og': og_m.group(1) if og_m else '',
    }


def is_indexable(path: Path) -> bool:
    if not path.exists():
        return False
    src = path.read_text(encoding='utf-8')
    robots_m = re.search(r'<meta\s+name="robots"\s+content="([^"]*)"', src, re.I)
    return not (robots_m and 'noindex' in robots_m.group(1).lower())


def parse_article_catalog() -> dict[str, dict[str, str]]:
    js_path = ROOT / 'blog' / 'blog-shared.js'
    src = js_path.read_text(encoding='utf-8')
    m = re.search(r'DN\.ARTICLES\s*=\s*\[(.*?)\];', src, re.DOTALL)
    out: dict[str, dict[str, str]] = {}
    if not m:
        return out
    for line in m.group(1).splitlines():
        slug_m = re.search(r"slug:'([^']+)'", line)
        title_m = re.search(r"title:'([^']+)'", line)
        if not (slug_m and title_m):
            continue
        slug = slug_m.group(1)
        # Skip articles marked {unpublished:true} in the catalog — they
        # shouldn't appear in sitemap.xml, blog/feed.xml, blog/atom.xml,
        # or any other public listing.
        if re.search(r'\bunpublished\s*:\s*true\b', line):
            continue
        tag_m = re.search(r"tag:'([^']+)'", line)
        date_m = re.search(r"date:'([^']+)'", line)
        cat_m = re.search(r"cat:'([^']+)'", line)
        out[slug] = {
            'slug': slug,
            'title': title_m.group(1),
            'tag': tag_m.group(1) if tag_m else '',
            'date': date_m.group(1) if date_m else '2026-01-01',
            'cat': cat_m.group(1) if cat_m else 'myth',
        }
    return out


def get_unpublished_slugs() -> set[str]:
    """Read blog-shared.js and return slugs marked unpublished:true."""
    js_path = ROOT / 'blog' / 'blog-shared.js'
    src = js_path.read_text(encoding='utf-8')
    m = re.search(r'DN\.ARTICLES\s*=\s*\[(.*?)\];', src, re.DOTALL)
    if not m:
        return set()
    unpublished: set[str] = set()
    for line in m.group(1).splitlines():
        if not re.search(r'\bunpublished\s*:\s*true\b', line):
            continue
        slug_m = re.search(r"slug:'([^']+)'", line)
        if slug_m:
            unpublished.add(slug_m.group(1))
    return unpublished


def discover_articles() -> list[dict[str, str]]:
    catalog = parse_article_catalog()
    unpublished = get_unpublished_slugs()
    blog_dir = ROOT / 'blog'
    slugs = sorted(
        p.stem for p in blog_dir.glob('*.html')
        if p.name not in {'index.html', 'topics.html'}
    )
    articles = []
    for slug in slugs:
        if slug in unpublished:
            continue  # admin marked this {unpublished:true}; skip from feeds/sitemap
        meta = html_meta(blog_dir / f'{slug}.html')
        row = catalog.get(slug, {
            'slug': slug,
            'title': meta['title'].split('|')[0].strip() or slug,
            'tag': '',
            'date': meta['date'],
            'cat': 'article',
        })
        if not row.get('date'):
            row['date'] = meta['date']
        articles.append(row)
    articles.sort(key=lambda a: a['date'], reverse=True)
    return articles


ARTICLES = discover_articles()

STATIC_PAGES = [
    {'url': '/', 'priority': '1.0', 'changefreq': 'weekly'},
    {'url': '/about', 'priority': '0.8', 'changefreq': 'monthly'},
    {'url': '/blog', 'priority': '0.9', 'changefreq': 'weekly'},
    {'url': '/blog/topics', 'priority': '0.7', 'changefreq': 'monthly'},
    {'url': '/tools', 'priority': '0.8', 'changefreq': 'monthly'},
    {'url': '/glossary', 'priority': '0.7', 'changefreq': 'monthly'},
    {'url': '/support', 'priority': '0.5', 'changefreq': 'monthly'},
    {'url': '/dashboard', 'priority': '0.5', 'changefreq': 'monthly'},
    {'url': '/notes', 'priority': '0.5', 'changefreq': 'monthly'},
    {'url': '/privacy', 'priority': '0.3', 'changefreq': 'yearly'},
]


def en_route_for(zh_url: str) -> str | None:
    en = '/en/' if zh_url == '/' else '/en' + zh_url
    en_file = file_for_route(en)
    return en if is_indexable(en_file) else None


def resolve_og(slug: str) -> str | None:
    static_path = ROOT / 'assets' / 'og' / f'{slug}.png'
    if static_path.exists():
        return f'{DOMAIN}/assets/og/{slug}.png'
    meta = html_meta(ROOT / 'blog' / f'{slug}.html')
    return meta['og'] or None


def emit_url(out: list[str], loc: str, lastmod: str, changefreq: str, priority: str,
             alternates: dict[str, str] | None = None, image: str | None = None,
             image_title: str | None = None) -> None:
    out.append('  <url>')
    out.append(f'    <loc>{DOMAIN}{loc}</loc>')
    out.append(f'    <lastmod>{lastmod}</lastmod>')
    out.append(f'    <changefreq>{changefreq}</changefreq>')
    out.append(f'    <priority>{priority}</priority>')
    if alternates:
        for lang, href in alternates.items():
            out.append(f'    <xhtml:link rel="alternate" hreflang="{lang}" href="{DOMAIN}{href}"/>')
    if image:
        out.append('    <image:image>')
        # First unescape any HTML entities in the source (og:image content
        # already has &amp; encoded), then re-encode for XML. Without the
        # unescape step we double-encode `&` → `&amp;amp;` which breaks
        # the OG image URL when Google's image fetcher parses it.
        clean_image = html.unescape(image).replace('&', '&amp;')
        out.append(f'      <image:loc>{clean_image}</image:loc>')
        if image_title:
            out.append(f'      <image:title>{html.escape(image_title)}</image:title>')
        out.append('    </image:image>')
    out.append('  </url>')


def alternates_for(zh_url: str, en_url: str | None) -> dict[str, str]:
    alts = {'zh-Hant-TW': zh_url, 'x-default': zh_url}
    if en_url:
        alts['en'] = en_url
    return alts


def build_sitemap() -> str:
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]

    for p in STATIC_PAGES:
        zh = p['url']
        if not file_for_route(zh).exists():
            continue
        en = en_route_for(zh)
        emit_url(out, zh, today, p['changefreq'], p['priority'], alternates_for(zh, en))

    for a in ARTICLES:
        zh = f'/blog/{a["slug"]}'
        en = en_route_for(zh)
        emit_url(
            out, zh, a['date'], 'monthly', '0.8',
            alternates_for(zh, en),
            image=resolve_og(a['slug']),
            image_title=a['title'],
        )

    for p in STATIC_PAGES:
        zh = p['url']
        en = en_route_for(zh)
        if not en:
            continue
        emit_url(out, en, today, p['changefreq'], f'{max(float(p["priority"]) - 0.1, 0.1):.1f}', alternates_for(zh, en))

    for a in ARTICLES:
        zh = f'/blog/{a["slug"]}'
        en = en_route_for(zh)
        if not en:
            continue
        emit_url(out, en, a['date'], 'monthly', '0.7', alternates_for(zh, en))

    out.append('</urlset>')
    return '\n'.join(out) + '\n'


def build_rss() -> str:
    today = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/">',
        '  <channel>',
        f'    <title>{html.escape(SITE_NAME)}</title>',
        f'    <link>{DOMAIN}/</link>',
        '    <description>皮膚科衛教與學習筆記，整理常見皮膚疾病、治療選項與醫學指引。</description>',
        '    <language>zh-Hant-TW</language>',
        f'    <lastBuildDate>{today}</lastBuildDate>',
        f'    <atom:link href="{DOMAIN}/blog/feed.xml" rel="self" type="application/rss+xml"/>',
        '    <generator>DermNotes auto-feed</generator>',
    ]
    for a in ARTICLES[:30]:
        d = datetime.strptime(a['date'], '%Y-%m-%d').replace(tzinfo=timezone.utc)
        rfc822 = d.strftime('%a, %d %b %Y 00:00:00 +0000')
        out += [
            '    <item>',
            f'      <title>{html.escape(a["title"])}</title>',
            f'      <link>{DOMAIN}/blog/{a["slug"]}</link>',
            f'      <guid isPermaLink="true">{DOMAIN}/blog/{a["slug"]}</guid>',
            f'      <pubDate>{rfc822}</pubDate>',
            f'      <dc:creator>{AUTHOR}</dc:creator>',
            f'      <category>{html.escape(a.get("tag", ""))}</category>',
            f'      <description>{html.escape(a["title"])} | ChenDermatologist 皮膚科衛教筆記</description>',
            '    </item>',
        ]
    out += ['  </channel>', '</rss>']
    return '\n'.join(out) + '\n'


def build_atom() -> str:
    today = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="zh-Hant-TW">',
        f'  <title>{html.escape(SITE_NAME)}</title>',
        f'  <link href="{DOMAIN}/" rel="alternate"/>',
        f'  <link href="{DOMAIN}/blog/atom.xml" rel="self"/>',
        f'  <id>{DOMAIN}/</id>',
        f'  <updated>{today}</updated>',
        '  <author>',
        f'    <name>{AUTHOR}</name>',
        f'    <email>{EMAIL}</email>',
        '  </author>',
        '  <generator uri="https://chendermatologist.com">DermNotes auto-feed</generator>',
    ]
    for a in ARTICLES[:30]:
        d = datetime.strptime(a['date'], '%Y-%m-%d').replace(tzinfo=timezone.utc)
        iso = d.strftime('%Y-%m-%dT00:00:00Z')
        out += [
            '  <entry>',
            f'    <title>{html.escape(a["title"])}</title>',
            f'    <link href="{DOMAIN}/blog/{a["slug"]}" rel="alternate"/>',
            f'    <id>{DOMAIN}/blog/{a["slug"]}</id>',
            f'    <updated>{iso}</updated>',
            f'    <published>{iso}</published>',
            f'    <category term="{html.escape(a.get("tag", ""))}"/>',
            f'    <summary>{html.escape(a["title"])} | ChenDermatologist 皮膚科衛教筆記</summary>',
            '  </entry>',
        ]
    out.append('</feed>')
    return '\n'.join(out) + '\n'


(ROOT / 'sitemap.xml').write_text(build_sitemap(), encoding='utf-8')
print(f'Wrote sitemap.xml ({len(ARTICLES)} articles + {len(STATIC_PAGES)} static candidates)')

(ROOT / 'blog').mkdir(exist_ok=True)
(ROOT / 'blog' / 'feed.xml').write_text(build_rss(), encoding='utf-8')
print(f'Wrote blog/feed.xml ({min(30, len(ARTICLES))} items)')

(ROOT / 'blog' / 'atom.xml').write_text(build_atom(), encoding='utf-8')
print(f'Wrote blog/atom.xml ({min(30, len(ARTICLES))} items)')
