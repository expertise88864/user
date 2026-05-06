#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F10 — Mark the FIRST <img> on each page as LCP candidate.

Web vitals: the largest image above-the-fold is the most likely LCP element.
Browsers can only fetchpriority="high" for explicitly marked images; without
this hint the browser guesses (often wrong → slow LCP).

This pass:
  1. Finds the first <img> in each HTML file (typically logo / hero / first article image)
  2. Adds fetchpriority="high" + loading="eager"
  3. Adds decoding="async" (still useful — only loading is eager)
  4. All other <img> elements: ensures they have loading="lazy" + decoding="async"

Idempotent: only modifies <img> tags that lack the attributes.
"""
import os, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))

IMG_RE = re.compile(r'<img\s+([^>]+?)/?>', re.IGNORECASE)

def patch_attrs(attrs, is_first):
    """Patch a single <img>'s attribute string."""
    has_lazy = re.search(r'\bloading\s*=', attrs, re.I)
    has_decode = re.search(r'\bdecoding\s*=', attrs, re.I)
    has_fetchprio = re.search(r'\bfetchpriority\s*=', attrs, re.I)
    out = attrs.rstrip()
    if is_first:
        # Force eager + high priority
        if has_lazy:
            out = re.sub(r'\bloading\s*=\s*"[^"]*"', 'loading="eager"', out, flags=re.I)
        else:
            out += ' loading="eager"'
        if has_fetchprio:
            out = re.sub(r'\bfetchpriority\s*=\s*"[^"]*"', 'fetchpriority="high"', out, flags=re.I)
        else:
            out += ' fetchpriority="high"'
    else:
        if not has_lazy:
            out += ' loading="lazy"'
    if not has_decode:
        out += ' decoding="async"'
    return out

def patch_html(html):
    """Replace <img> tags. First one gets eager+high; rest get lazy."""
    seen_first = [False]   # mutable closure
    def repl(m):
        attrs = m.group(1)
        # Skip if it's an SVG icon, decorative, or has fetchpriority already set explicitly
        is_decorative = ('aria-hidden="true"' in attrs) and ('width="1"' in attrs or 'tracking' in attrs.lower())
        if is_decorative:
            return m.group(0)
        new_attrs = patch_attrs(attrs, not seen_first[0])
        seen_first[0] = True
        return '<img ' + new_attrs + '>'
    new_html = IMG_RE.sub(repl, html)
    return new_html, new_html != html

def main():
    n = 0
    total_imgs = 0
    for d, _, fs in os.walk(ROOT):
        if any(x in d for x in ['.git', 'node_modules', '__pycache__', 'astro-rewrite', '_bin']):
            continue
        for f in fs:
            if not f.endswith('.html'):
                continue
            p = os.path.join(d, f)
            with open(p, 'r', encoding='utf-8') as fp:
                src = fp.read()
            new, changed = patch_html(src)
            if changed:
                with open(p, 'w', encoding='utf-8') as fp:
                    fp.write(new)
                n += 1
                total_imgs += len(IMG_RE.findall(src))
    print(f'Patched {n} HTML files ({total_imgs} <img> tags processed)')

if __name__ == '__main__':
    main()
