#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Mirror all top-level + blog/ HTML files to /en/ with English-default behavior.

Strategy:
  - Each /en/<file>.html is a derivative of the Chinese version
  - <html lang="en">
  - canonical → /en/<path>
  - hreflang alt → original Chinese path (zh-Hant-TW)
  - Auto-set DN.LANG_KEY['en'] preference via inline script BEFORE blog-shared.js
  - Inject a thin top banner: "Article body still in Chinese — full translation in progress"
  - Mirror /blog/* → /en/blog/* (same structure)
  - Skip: 404 / offline / admin / dashboard / notes (private/utility)
"""
import os, re, glob, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
DOMAIN = 'https://chendermatologist.com'

SKIP = {'404.html', 'offline.html', 'admin.html', 'dashboard.html', 'notes.html'}

# Per-page OG overrides for English mirrors.
# Key = source filename relative to ROOT (e.g. 'index.html', 'blog/acne-myths.html').
# Used to swap og:title / og:description / twitter:title to English so social
# previews (LinkedIn, X, FB) match the visitor's expected language.
EN_OG_OVERRIDES = {
    'index.html': {
        'title': 'Dr. Yi-Jia Chen — Dermatology Patient Education (Taiwan)',
        'desc':  'Plain-language dermatology articles by Dr. Chen: acne, sunscreen, eczema, melasma, hair loss, biologics, isotretinoin, topical steroids — evidence-based, ad-free.',
    },
    'about.html': {
        'title': 'About Dr. Yi-Jia Chen — Dermatologist (KMU / KMUH / CMUH)',
        'desc':  'Background of Dr. Chen, Yi-Jia, M.D.: KMU medical school, KMUH PGY, CMUH dermatology resident. Personal patient-education site.',
    },
    'tools.html': {
        'title': 'Dermatology Calculators (PASI / DLQI / SCORAD / SALT) — Dr. Chen',
        'desc':  'Free clinical scoring calculators for dermatology: PASI, DLQI, SCORAD, SALT, EASI, IGA, NRS, and more.',
    },
    'glossary.html': {
        'title': 'Dermatology Glossary in Plain Mandarin & English — Dr. Chen',
        'desc':  'Plain-language glossary mapping dermatology jargon (biologics, JAK inhibitors, phototherapy, etc.) to everyday words.',
    },
    'blog/index.html': {
        'title': 'Dermatology Articles Index — Dr. Yi-Jia Chen',
        'desc':  'Index of all dermatology articles: acne, sunscreen, eczema, melasma, isotretinoin, topical acids, steroids, biologics, hair loss, mpox.',
    },
}

# Banner injected after <main> opening tag (or after </header> as fallback)
EN_BANNER = '''<div id="dn-en-banner" style="background:linear-gradient(180deg,#fef3c7,#fde68a);border-bottom:1px solid #d4a015;padding:9px 18px;text-align:center;font-size:12.5px;color:#854d0e;font-family:Inter,system-ui,sans-serif;line-height:1.5;font-weight:500">
  🌐 You are reading the English-mode interface. Some article body content is currently Chinese-only — full translation in progress.
  <a href="#" id="dn-en-banner-zh" style="margin-left:8px;color:#7c2d12;font-weight:700;text-decoration:underline">Switch to 中文 ↗</a>
</div>'''

# Inline script to set lang preference BEFORE blog-shared.js loads
EN_LANG_BOOTSTRAP = '''<script>
// Force English mode for /en/ pages
try {
  localStorage.setItem('dn_lang', 'en');
  document.cookie = 'dn_lang=en;path=/;max-age=31536000;samesite=lax';
} catch (e) {}
document.addEventListener('DOMContentLoaded', function () {
  // Banner switch link → take user to Chinese version
  var sw = document.getElementById('dn-en-banner-zh');
  if (sw) sw.href = location.pathname.replace(/^\\/en\\//, '/').replace(/^\\/en$/, '/');
});
</script>'''


def derive_en_path(zh_path):
    """blog/acne-myths.html → en/blog/acne-myths.html"""
    rel = os.path.relpath(zh_path, ROOT).replace('\\', '/')
    return os.path.join(ROOT, 'en', rel.lstrip('./'))


def transform(html, zh_canonical_path, en_canonical_path, source_rel=None):
    s = html

    # OG override (per-page English social-preview titles)
    ov = EN_OG_OVERRIDES.get(source_rel) if source_rel else None
    if ov:
        if 'title' in ov:
            s = re.sub(
                r'(<meta\s+property="og:title"\s+content=")[^"]*(")',
                lambda m: m.group(1) + ov['title'].replace('\\', r'\\').replace('"', '&quot;') + m.group(2),
                s, count=1
            )
            s = re.sub(
                r'(<meta\s+name="twitter:title"\s+content=")[^"]*(")',
                lambda m: m.group(1) + ov['title'].replace('\\', r'\\').replace('"', '&quot;') + m.group(2),
                s, count=1
            )
        if 'desc' in ov:
            s = re.sub(
                r'(<meta\s+property="og:description"\s+content=")[^"]*(")',
                lambda m: m.group(1) + ov['desc'].replace('\\', r'\\').replace('"', '&quot;') + m.group(2),
                s, count=1
            )
    # 1. Set <html lang="en">
    s = re.sub(r'<html\s+lang="[^"]*"', '<html lang="en"', s, count=1)

    # 2. Update canonical
    new_canonical = f'{DOMAIN}{en_canonical_path}'
    s = re.sub(
        r'<link\s+rel="canonical"\s+href="[^"]*"\s*/?>',
        f'<link rel="canonical" href="{new_canonical}" />',
        s, count=1
    )

    # 3. Replace existing hreflang block — point en → self, zh-Hant-TW → original
    # Strategy: replace the run of <link rel="alternate" hreflang="..."> tags
    new_hreflang = (
        f'<link rel="alternate" hreflang="x-default" href="{DOMAIN}{zh_canonical_path}" />\n'
        f'<link rel="alternate" hreflang="zh-Hant" href="{DOMAIN}{zh_canonical_path}" />\n'
        f'<link rel="alternate" hreflang="zh-Hant-TW" href="{DOMAIN}{zh_canonical_path}" />\n'
        f'<link rel="alternate" hreflang="en" href="{DOMAIN}{en_canonical_path}" />'
    )
    s = re.sub(
        r'(<link\s+rel="alternate"\s+hreflang="[^"]*"\s+href="[^"]*"\s*/?>\s*)+',
        new_hreflang + '\n',
        s, count=1
    )

    # 4. Inject EN_LANG_BOOTSTRAP before <script src="/blog/blog-shared.js
    s = re.sub(
        r'(<script\s+src="/blog/blog-shared\.js[^"]*"[^>]*></script>)',
        EN_LANG_BOOTSTRAP + '\n\\1',
        s
    )

    # 5. Inject banner after <main id="main-content"> (or after </header>)
    if '<main id="main-content">' in s:
        s = s.replace('<main id="main-content">', '<main id="main-content">\n' + EN_BANNER, 1)
    else:
        s = re.sub(r'(</header>)', r'\1\n' + EN_BANNER, s, count=1)

    # 6. og:locale
    s = re.sub(r'<meta property="og:locale" content="[^"]*" ?/?>', '<meta property="og:locale" content="en_US" />', s, count=1)
    s = re.sub(r'<meta property="og:locale:alternate" content="[^"]*" ?/?>', '<meta property="og:locale:alternate" content="zh_TW" />', s, count=1)

    return s


def main():
    n = 0
    en_dir = os.path.join(ROOT, 'en')
    blog_en_dir = os.path.join(en_dir, 'blog')
    os.makedirs(blog_en_dir, exist_ok=True)

    # Top-level HTML
    top_files = [f for f in os.listdir(ROOT)
                 if f.endswith('.html') and f not in SKIP and not f.startswith('_')]
    for f in top_files:
        zh_path = os.path.join(ROOT, f)
        # Canonical zh path (clean URL: about.html → /about, index.html → /)
        if f == 'index.html':
            zh_canonical = '/'
            en_canonical = '/en/'
        else:
            stem = f[:-5]
            zh_canonical = '/' + stem
            en_canonical = '/en/' + stem
        en_path = os.path.join(en_dir, f)
        with open(zh_path, 'r', encoding='utf-8') as fp: html = fp.read()
        en_html = transform(html, zh_canonical, en_canonical, source_rel=f)
        with open(en_path, 'w', encoding='utf-8') as fp: fp.write(en_html)
        n += 1

    # Blog HTML
    blog_files = [f for f in os.listdir(os.path.join(ROOT, 'blog'))
                  if f.endswith('.html')]
    for f in blog_files:
        zh_path = os.path.join(ROOT, 'blog', f)
        if f == 'index.html':
            zh_canonical = '/blog/'
            en_canonical = '/en/blog/'
        else:
            stem = f[:-5]
            zh_canonical = '/blog/' + stem
            en_canonical = '/en/blog/' + stem
        en_path = os.path.join(blog_en_dir, f)
        with open(zh_path, 'r', encoding='utf-8') as fp: html = fp.read()
        en_html = transform(html, zh_canonical, en_canonical, source_rel='blog/' + f)
        with open(en_path, 'w', encoding='utf-8') as fp: fp.write(en_html)
        n += 1

    print(f'Generated {n} /en/ pages')

if __name__ == '__main__':
    main()
