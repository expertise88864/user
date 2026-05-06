#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Self-host Google Fonts (Inter, Noto Sans TC, Noto Serif TC) — A7 optimization.

Steps performed by this script:
  1. Download woff2 files from google-webfonts-helper proxy
  2. Save to /assets/fonts/
  3. Generate @font-face CSS block
  4. Print HTML <link> replacement instructions

Run once: python _self_host_fonts.py
Then: manually replace the Google Fonts <link> in HTML <head> with the local CSS.
"""
import os, sys, io, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(ROOT, 'assets', 'fonts')
os.makedirs(FONTS_DIR, exist_ok=True)

# Use rsms.me/inter for Inter (MIT, no-redirect raw woff2)
# Use jsdelivr CDN for Noto fonts (most reliable mirror)
FONTS = [
    # (family_slug, weight, url, local_filename)
    ('inter', '400', 'https://rsms.me/inter/font-files/Inter-Regular.woff2', 'Inter-Regular.woff2'),
    ('inter', '600', 'https://rsms.me/inter/font-files/Inter-SemiBold.woff2', 'Inter-SemiBold.woff2'),
    ('inter', '700', 'https://rsms.me/inter/font-files/Inter-Bold.woff2', 'Inter-Bold.woff2'),
    # Noto Sans TC — use Google Fonts subset URL (CJK typically too large for full file)
    # Recommend: download manually from https://fonts.google.com/noto/specimen/Noto+Sans+TC
    # Save subset as: NotoSansTC-Regular.woff2, NotoSansTC-Medium.woff2
    # Noto Serif TC similarly
]

def download(url, dest):
    if os.path.exists(dest):
        print(f'  exists: {os.path.basename(dest)}')
        return True
    try:
        print(f'  downloading: {url}')
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
        with open(dest, 'wb') as f:
            f.write(data)
        print(f'  saved: {os.path.basename(dest)} ({len(data)//1024} KB)')
        return True
    except Exception as e:
        print(f'  failed: {e}')
        return False

print('=== A7. Self-host fonts ===')
ok = 0
for family, weight, url, fname in FONTS:
    dest = os.path.join(FONTS_DIR, fname)
    if download(url, dest):
        ok += 1
print(f'\nDownloaded {ok}/{len(FONTS)} Inter weights.')

print('''
=== Manual step required for CJK fonts ===
Download manually from https://fonts.google.com/noto/specimen/Noto+Sans+TC and
https://fonts.google.com/noto/specimen/Noto+Serif+TC, then place these files in
/assets/fonts/ :
  NotoSansTC-Regular.woff2
  NotoSansTC-Medium.woff2
  NotoSerifTC-SemiBold.woff2
  NotoSerifTC-Bold.woff2

Or use the variable-font versions for smaller total size:
  NotoSansTC[wght].woff2
  NotoSerifTC[wght].woff2
''')

# Generate the CSS block
CSS = '''/* ─── Self-hosted fonts (A7) — replaces Google Fonts CDN ─── */
/* Inter — Latin only, woff2 with unicode-range */
@font-face{font-family:'Inter';font-style:normal;font-weight:400;font-display:swap;
  src:url('/assets/fonts/Inter-Regular.woff2') format('woff2');
  unicode-range:U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0300-0301, U+0303-0304, U+0308-0309, U+0323, U+0329, U+2000-206F, U+2074, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;}
@font-face{font-family:'Inter';font-style:normal;font-weight:600;font-display:swap;
  src:url('/assets/fonts/Inter-SemiBold.woff2') format('woff2');
  unicode-range:U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0300-0301, U+0303-0304, U+0308-0309, U+0323, U+0329, U+2000-206F, U+2074, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;}
@font-face{font-family:'Inter';font-style:normal;font-weight:700;font-display:swap;
  src:url('/assets/fonts/Inter-Bold.woff2') format('woff2');
  unicode-range:U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0300-0301, U+0303-0304, U+0308-0309, U+0323, U+0329, U+2000-206F, U+2074, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;}

/* Noto Sans TC — Chinese (after manual download) */
@font-face{font-family:'Noto Sans TC';font-style:normal;font-weight:400;font-display:swap;
  src:url('/assets/fonts/NotoSansTC-Regular.woff2') format('woff2');
  unicode-range:U+4E00-9FFF, U+3000-303F, U+FF00-FFEF;}
@font-face{font-family:'Noto Sans TC';font-style:normal;font-weight:500;font-display:swap;
  src:url('/assets/fonts/NotoSansTC-Medium.woff2') format('woff2');
  unicode-range:U+4E00-9FFF, U+3000-303F, U+FF00-FFEF;}

/* Noto Serif TC */
@font-face{font-family:'Noto Serif TC';font-style:normal;font-weight:600;font-display:swap;
  src:url('/assets/fonts/NotoSerifTC-SemiBold.woff2') format('woff2');
  unicode-range:U+4E00-9FFF, U+3000-303F, U+FF00-FFEF;}
@font-face{font-family:'Noto Serif TC';font-style:normal;font-weight:700;font-display:swap;
  src:url('/assets/fonts/NotoSerifTC-Bold.woff2') format('woff2');
  unicode-range:U+4E00-9FFF, U+3000-303F, U+FF00-FFEF;}
'''

css_path = os.path.join(ROOT, 'assets', 'fonts.css')
with open(css_path, 'w', encoding='utf-8') as f:
    f.write(CSS)
print(f'CSS written → {css_path}')

print('''
=== Final HTML replacement ===
In all HTML <head>, replace:
  <link rel="preload" as="style" href="https://fonts.googleapis.com/css2?...">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?..." rel="stylesheet">
With:
  <link rel="preload" as="font" type="font/woff2" href="/assets/fonts/Inter-Regular.woff2" crossorigin>
  <link rel="preload" as="font" type="font/woff2" href="/assets/fonts/NotoSerifTC-Bold.woff2" crossorigin>
  <link rel="stylesheet" href="/assets/fonts.css?v=1">
''')
