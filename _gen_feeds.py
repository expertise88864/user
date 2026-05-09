#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Auto-regenerate sitemap.xml + blog/feed.xml + blog/atom.xml from DN.ARTICLES (in blog/blog-shared.js).
Run after adding/removing articles. Idempotent.
"""
import os, re, glob, html
from datetime import datetime, timezone

DOMAIN = 'https://chendermatologist.com'
SITE_NAME = 'ChenDermatologist · 皮膚科衛教筆記'
AUTHOR = '陳翊嘉 醫師'
EMAIL = 'expertise88864@gmail.com'

# ── Parse DN.ARTICLES from blog/blog-shared.js ──
with open('blog/blog-shared.js', 'r', encoding='utf-8') as f:
    js = f.read()
m = re.search(r'DN\.ARTICLES\s*=\s*\[(.*?)\];', js, re.DOTALL)
articles = []
if m:
    block = m.group(1)
    for line in block.split('\n'):
        slug_m = re.search(r"slug:'([^']+)'", line)
        title_m = re.search(r"title:'([^']+)'", line)
        tag_m = re.search(r"tag:'([^']+)'", line)
        date_m = re.search(r"date:'([^']+)'", line)
        cat_m = re.search(r"cat:'([^']+)'", line)
        if slug_m and title_m:
            articles.append({
                'slug': slug_m.group(1),
                'title': title_m.group(1),
                'tag': tag_m.group(1) if tag_m else '',
                'date': date_m.group(1) if date_m else '2026-01-01',
                'cat': cat_m.group(1) if cat_m else 'myth',
            })

# Sort by date desc
articles.sort(key=lambda a: a['date'], reverse=True)

# ── Static pages ──
STATIC_PAGES = [
    {'url': '/', 'priority': '1.0', 'changefreq': 'weekly'},
    {'url': '/about', 'priority': '0.8', 'changefreq': 'monthly'},
    {'url': '/blog/', 'priority': '0.9', 'changefreq': 'weekly'},
    {'url': '/blog/topics', 'priority': '0.7', 'changefreq': 'monthly'},
    {'url': '/tools', 'priority': '0.8', 'changefreq': 'monthly'},
    {'url': '/glossary', 'priority': '0.7', 'changefreq': 'monthly'},
    {'url': '/dashboard', 'priority': '0.5', 'changefreq': 'monthly'},
    {'url': '/notes', 'priority': '0.5', 'changefreq': 'monthly'},
    {'url': '/privacy', 'priority': '0.3', 'changefreq': 'yearly'},
]

# ── sitemap.xml ──
def build_sitemap():
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1" xmlns:xhtml="http://www.w3.org/1999/xhtml">']

    def emit_url(zh_url, en_url, lastmod, changefreq, priority, image=None, image_title=None):
        out.append('  <url>')
        out.append(f'    <loc>{DOMAIN}{zh_url}</loc>')
        out.append(f'    <lastmod>{lastmod}</lastmod>')
        out.append(f'    <changefreq>{changefreq}</changefreq>')
        out.append(f'    <priority>{priority}</priority>')
        # hreflang annotations (Google sitemap-extension format)
        out.append(f'    <xhtml:link rel="alternate" hreflang="zh-Hant-TW" href="{DOMAIN}{zh_url}"/>')
        out.append(f'    <xhtml:link rel="alternate" hreflang="en" href="{DOMAIN}{en_url}"/>')
        out.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{DOMAIN}{zh_url}"/>')
        if image:
            # XML-escape & in URLs (e.g., /api/og?title=...&tag=...)
            image_xml = image.replace('&', '&amp;')
            out.append('    <image:image>')
            out.append(f'      <image:loc>{image_xml}</image:loc>')
            if image_title:
                out.append(f'      <image:title>{html.escape(image_title)}</image:title>')
            out.append('    </image:image>')
        out.append('  </url>')

    for p in STATIC_PAGES:
        zh = p["url"]
        en = '/en/' if zh == '/' else ('/en' + zh)
        emit_url(zh, en, today, p["changefreq"], p["priority"])
    # Resolve OG image for each article: use static /assets/og/{slug}.png
    # if that file exists; otherwise read the article HTML and use whatever
    # the page declares in <meta property="og:image"> (typically /api/og?...).
    import os, re
    def resolve_og(slug):
        static_path = os.path.join('assets', 'og', f'{slug}.png')
        if os.path.exists(static_path):
            return f'{DOMAIN}/assets/og/{slug}.png'
        # Fallback: parse the article HTML for the actual og:image meta
        try:
            with open(os.path.join('blog', f'{slug}.html'), encoding='utf-8') as f:
                page = f.read()
            m = re.search(r'<meta property="og:image" content="([^"]+)"', page)
            if m:
                return m.group(1)
        except FileNotFoundError:
            pass
        return None  # image:image block will be skipped if None

    for a in articles:
        og = resolve_og(a["slug"])
        emit_url(
            f'/blog/{a["slug"]}',
            f'/en/blog/{a["slug"]}',
            a["date"], 'monthly', '0.8',
            image=og,
            image_title=a["title"]
        )

    # Also include /en/ URLs as their own entries (Google reads sitemap-multi-language better with both)
    for p in STATIC_PAGES:
        zh = p["url"]
        en = '/en/' if zh == '/' else ('/en' + zh)
        out.append('  <url>')
        out.append(f'    <loc>{DOMAIN}{en}</loc>')
        out.append(f'    <lastmod>{today}</lastmod>')
        out.append(f'    <changefreq>{p["changefreq"]}</changefreq>')
        out.append(f'    <priority>{float(p["priority"]) - 0.1:.1f}</priority>')
        out.append(f'    <xhtml:link rel="alternate" hreflang="zh-Hant-TW" href="{DOMAIN}{zh}"/>')
        out.append(f'    <xhtml:link rel="alternate" hreflang="en" href="{DOMAIN}{en}"/>')
        out.append('  </url>')
    for a in articles:
        out.append('  <url>')
        out.append(f'    <loc>{DOMAIN}/en/blog/{a["slug"]}</loc>')
        out.append(f'    <lastmod>{a["date"]}</lastmod>')
        out.append('    <changefreq>monthly</changefreq>')
        out.append('    <priority>0.7</priority>')
        out.append(f'    <xhtml:link rel="alternate" hreflang="zh-Hant-TW" href="{DOMAIN}/blog/{a["slug"]}"/>')
        out.append(f'    <xhtml:link rel="alternate" hreflang="en" href="{DOMAIN}/en/blog/{a["slug"]}"/>')
        out.append('  </url>')

    out.append('</urlset>')
    return '\n'.join(out) + '\n'

# ── feed.xml (RSS 2.0) ──
def build_rss():
    today = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/">',
           '  <channel>',
           f'    <title>{html.escape(SITE_NAME)}</title>',
           f'    <link>{DOMAIN}/</link>',
           '    <description>陳翊嘉醫師(皮膚科)整理的皮膚科衛教與學習筆記。</description>',
           '    <language>zh-Hant-TW</language>',
           f'    <lastBuildDate>{today}</lastBuildDate>',
           f'    <atom:link href="{DOMAIN}/blog/feed.xml" rel="self" type="application/rss+xml"/>',
           f'    <generator>DermNotes auto-feed v1</generator>']
    for a in articles[:30]:  # latest 30
        # Convert date to RFC822
        d = datetime.strptime(a['date'], '%Y-%m-%d').replace(tzinfo=timezone.utc)
        rfc822 = d.strftime('%a, %d %b %Y 00:00:00 +0000')
        out.append('    <item>')
        out.append(f'      <title>{html.escape(a["title"])}</title>')
        out.append(f'      <link>{DOMAIN}/blog/{a["slug"]}</link>')
        out.append(f'      <guid isPermaLink="true">{DOMAIN}/blog/{a["slug"]}</guid>')
        out.append(f'      <pubDate>{rfc822}</pubDate>')
        out.append(f'      <dc:creator>{AUTHOR}</dc:creator>')
        out.append(f'      <category>{html.escape(a["tag"])}</category>')
        out.append(f'      <description>{html.escape(a["title"])} — 陳翊嘉醫師(皮膚科)的衛教文章。</description>')
        out.append('    </item>')
    out.append('  </channel>')
    out.append('</rss>')
    return '\n'.join(out) + '\n'

# ── atom.xml ──
def build_atom():
    today = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
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
           '  <generator uri="https://chendermatologist.com">DermNotes auto-feed v1</generator>']
    for a in articles[:30]:
        d = datetime.strptime(a['date'], '%Y-%m-%d').replace(tzinfo=timezone.utc)
        iso = d.strftime('%Y-%m-%dT00:00:00Z')
        out.append('  <entry>')
        out.append(f'    <title>{html.escape(a["title"])}</title>')
        out.append(f'    <link href="{DOMAIN}/blog/{a["slug"]}" rel="alternate"/>')
        out.append(f'    <id>{DOMAIN}/blog/{a["slug"]}</id>')
        out.append(f'    <updated>{iso}</updated>')
        out.append(f'    <published>{iso}</published>')
        out.append(f'    <category term="{html.escape(a["tag"])}"/>')
        out.append(f'    <summary>{html.escape(a["title"])} — 陳翊嘉醫師(皮膚科)的衛教文章。</summary>')
        out.append('  </entry>')
    out.append('</feed>')
    return '\n'.join(out) + '\n'

# ── Write files ──
with open('sitemap.xml', 'w', encoding='utf-8') as f:
    f.write(build_sitemap())
print(f'Wrote sitemap.xml ({len(articles)} articles + {len(STATIC_PAGES)} static)')

os.makedirs('blog', exist_ok=True)
with open('blog/feed.xml', 'w', encoding='utf-8') as f:
    f.write(build_rss())
print(f'Wrote blog/feed.xml ({min(30, len(articles))} items)')

with open('blog/atom.xml', 'w', encoding='utf-8') as f:
    f.write(build_atom())
print(f'Wrote blog/atom.xml ({min(30, len(articles))} items)')
