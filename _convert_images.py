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
import html as html_module
from html.parser import HTMLParser
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

ROOT = os.path.dirname(os.path.abspath(__file__))

# Importing the HTML helper must not require codecs or change stdout.
Image = None
HAS_AVIF = False


def load_image_backend():
    global Image, HAS_AVIF
    try:
        from PIL import Image
    except ImportError:
        raise SystemExit('Pillow missing — pip install Pillow')
    try:
        import pillow_avif  # noqa: F401 — registers AVIF support
        HAS_AVIF = True
    except ImportError:
        print('WARN: AVIF unavailable — install pillow-avif-plugin')

WEBP_QUALITY = 82
AVIF_QUALITY = 60
SOURCE_EXTS = {'.jpg', '.jpeg', '.png'}
SKIP_DIRS = {'.git', '.codex-review', 'node_modules', '__pycache__',
             'astro-rewrite', '_bin', 'pagefind'}

def convert_image(src_path):
    """Generate sibling .webp + .avif. Returns (webp_made, avif_made)."""
    if Image is None:
        load_image_backend()
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
    for d, dirs, fs in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS and name != 'en']
        for f in fs:
            ext = os.path.splitext(f)[1].lower()
            if ext in SOURCE_EXTS:
                out.append(os.path.join(d, f))
    return out

# ─── HTML rewriter: <img src=…> → <picture>... ───
class PictureRewriter(HTMLParser):
    """Edit only original img spans; never serialize the surrounding document."""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
            'meta', 'param', 'source', 'track', 'wbr'}
    EXCLUDED = {'picture', 'script', 'style', 'template', 'noscript',
                'textarea', 'title', 'svg', 'math'}

    def __init__(self, source, image_set, html_path):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.stack = []
        self.edits = []
        self.root = Path(ROOT).resolve()
        self.directory = Path(html_path).resolve().parent if html_path else self.root
        self.images = {Path(p).resolve() for p in image_set}
        self.line_starts = [0]
        for i, char in enumerate(source):
            if char == '\n':
                self.line_starts.append(i + 1)

    def handle_starttag(self, tag, attrs):
        if tag == 'img' and not self.EXCLUDED.intersection(self.stack):
            self.wrap_image(attrs)
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag == 'img' and not self.EXCLUDED.intersection(self.stack):
            self.wrap_image(attrs)

    def handle_endtag(self, tag):
        if tag in self.stack:
            index = len(self.stack) - 1 - self.stack[::-1].index(tag)
            del self.stack[index:]

    def wrap_image(self, attrs):
        values = dict(attrs)
        # Preserve explicit opt-outs and existing responsive-image choices.
        if any(key in values for key in ('data-no-picture', 'srcset', 'sizes')):
            return
        src = values.get('src')
        if not src or sum(key == 'src' for key, _ in attrs) != 1:
            return
        try:
            parsed = urlsplit(src)
        except ValueError:
            return
        if (parsed.scheme or parsed.netloc or '\\' in parsed.path
                or Path(parsed.path).suffix.lower() not in SOURCE_EXTS):
            return
        decoded = unquote(parsed.path)
        if '\\' in decoded or Path(decoded).suffix.lower() not in SOURCE_EXTS:
            return
        try:
            fs_path = ((self.root / decoded.lstrip('/')) if decoded.startswith('/')
                       else (self.directory / decoded)).resolve()
        except (ValueError, OSError, RuntimeError):
            return
        if not fs_path.is_relative_to(self.root) or fs_path not in self.images:
            return
        sources = []
        for suffix, mime in (('.avif', 'image/avif'), ('.webp', 'image/webp')):
            if fs_path.with_suffix(suffix).is_file():
                path = os.path.splitext(parsed.path)[0] + suffix
                url = urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))
                sources.append(f'<source srcset="{html_module.escape(url, quote=True)}" type="{mime}">')
        if not sources:
            return
        line, column = self.getpos()
        start = self.line_starts[line - 1] + column
        original = self.get_starttag_text()
        self.edits.append((start, start + len(original),
                           '<picture>' + ''.join(sources) + original + '</picture>'))


def rewrite_html_imgs(html, image_set, html_path=None):
    """Wrap eligible local images once, preserving all existing HTML bytes."""
    parser = PictureRewriter(html, image_set, html_path)
    parser.feed(html)
    parser.close()
    for start, end, replacement in reversed(parser.edits):
        html = html[:start] + replacement + html[end:]
    return html

def main():
    load_image_backend()
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
    for d, dirs, fs in os.walk(ROOT):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for f in fs:
            if not f.endswith('.html'):
                continue
            p = os.path.join(d, f)
            with open(p, 'r', encoding='utf-8') as fp:
                src = fp.read()
            new = rewrite_html_imgs(src, image_set, p)
            if new != src:
                with open(p, 'w', encoding='utf-8') as fp:
                    fp.write(new)
                n_html += 1
    print(f'Rewrote {n_html} HTML files to use <picture>')

if __name__ == '__main__':
    main()
