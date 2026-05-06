#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F2 — Convert all JPG/PNG images to AVIF + WebP for faster LCP.

Strategy:
  1. Find every JPG / PNG / JPEG under assets/, blog/, etc.
  2. Generate sibling .webp (quality 82) and .avif (quality 60) if missing
  3. Rewrite <img src="…/photo.jpg"> → <picture>…</picture> in HTML files
     to serve AVIF first, then WebP, then original as fallback

Setup once:
    pip install Pillow pillow-avif-plugin

Re-run after adding new images. Idempotent: skips already-converted files
and HTML <img> already wrapped in <picture>.
"""
import os, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))

try:
    from PIL import Image
    import pillow_avif  # noqa: F401  — registers AVIF support
    HAS_AVIF = True
except ImportError as e:
    print(f'WARN: {e} — install with: pip install Pillow pillow-avif-plugin')
    HAS_AVIF = False
    try:
        from PIL import Image
    except ImportError:
        print('Pillow missing — pip install Pillow')
        sys.exit(1)

WEBP_QUALITY = 82
AVIF_QUALITY = 60
SOURCE_EXTS = {'.jpg', '.jpeg', '.png'}

def convert_image(src_path):
    """Generate sibling .webp + .avif. Returns (webp_made, avif_made)."""
    base, ext = os.path.splitext(src_path)
    webp_path = base + '.webp'
    avif_path = base + '.avif'
    webp_made = False
    avif_made = False
    src_mtime = os.path.getmtime(src_path)
    try:
        img = Image.open(src_path)
        if img.mode in ('RGBA', 'LA') and ext.lower() in ('.jpg', '.jpeg'):
            img = img.convert('RGB')
        # Generate WebP
        if not os.path.exists(webp_path) or os.path.getmtime(webp_path) < src_mtime:
            img.save(webp_path, 'WEBP', quality=WEBP_QUALITY, method=6)
            webp_made = True
        # Generate AVIF
        if HAS_AVIF and (not os.path.exists(avif_path) or os.path.getmtime(avif_path) < src_mtime):
            img.save(avif_path, 'AVIF', quality=AVIF_QUALITY)
            avif_made = True
    except Exception as e:
        print(f'  ! skip {src_path}: {e}')
    return webp_made, avif_made

def find_images(root):
    out = []
    for d, _, fs in os.walk(root):
        if any(x in d for x in ['.git', 'node_modules', '__pycache__', 'astro-rewrite', '_bin', 'pagefind', '/en/']):
            continue
        for f in fs:
            ext = os.path.splitext(f)[1].lower()
            if ext in SOURCE_EXTS:
                out.append(os.path.join(d, f))
    return out

# ─── HTML rewriter: <img src=…> → <picture>... ───
IMG_TAG_RE = re.compile(r'<img\s+([^>]*?)/?>', re.IGNORECASE)
SRC_ATTR_RE = re.compile(r'\bsrc\s*=\s*"([^"]+\.(?:jpg|jpeg|png))"', re.IGNORECASE)

def rewrite_html_imgs(html, image_set):
    """Wrap <img src="…jpg"> in <picture> serving AVIF / WebP / original."""
    def repl(m):
        attrs = m.group(1)
        # Skip if already wrapped or in picture
        if 'data-no-picture' in attrs:
            return m.group(0)
        sm = SRC_ATTR_RE.search(attrs)
        if not sm:
            return m.group(0)
        src = sm.group(1)
        # Convert local-path src to fs path for existence check
        fs_path = src.lstrip('/').replace('/', os.sep)
        # Resolve relative to root
        if not os.path.isabs(fs_path):
            fs_path = os.path.join(ROOT, fs_path)
        base, ext = os.path.splitext(src)
        webp = base + '.webp'
        avif = base + '.avif'
        webp_fs = os.path.splitext(fs_path)[0] + '.webp'
        avif_fs = os.path.splitext(fs_path)[0] + '.avif'
        sources = []
        if os.path.exists(avif_fs):
            sources.append(f'<source srcset="{avif}" type="image/avif">')
        if os.path.exists(webp_fs):
            sources.append(f'<source srcset="{webp}" type="image/webp">')
        if not sources:
            return m.group(0)
        return '<picture>' + ''.join(sources) + '<img ' + attrs + '></picture>'
    return IMG_TAG_RE.sub(repl, html)

def main():
    print('=== Step 1: convert images ===')
    imgs = find_images(ROOT)
    print(f'Found {len(imgs)} JPG/PNG files')
    n_webp = n_avif = 0
    for p in imgs:
        w, a = convert_image(p)
        n_webp += int(w)
        n_avif += int(a)
    print(f'Generated {n_webp} new WebP, {n_avif} new AVIF')

    if not imgs:
        return

    print('\n=== Step 2: rewrite <img> in HTML to <picture> ===')
    image_set = set(imgs)
    n_html = 0
    for d, _, fs in os.walk(ROOT):
        if any(x in d for x in ['.git', 'node_modules', '__pycache__', 'astro-rewrite', '_bin']):
            continue
        for f in fs:
            if not f.endswith('.html'):
                continue
            p = os.path.join(d, f)
            with open(p, 'r', encoding='utf-8') as fp:
                src = fp.read()
            new = rewrite_html_imgs(src, image_set)
            if new != src:
                with open(p, 'w', encoding='utf-8') as fp:
                    fp.write(new)
                n_html += 1
    print(f'Rewrote {n_html} HTML files to use <picture>')

if __name__ == '__main__':
    main()
