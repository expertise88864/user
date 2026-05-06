#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Apply E12 (a11y skip-link + main landmark) + E6 (view transitions) +
E5 (resource hints补强) to all HTML files in the site.

Idempotent: skips files that already have the patches applied.
"""
import os, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))

# Marker we add to <head> indicating the patch is applied
SENTINEL = '<!-- a11y-vt-applied -->'

# 1) Meta + style for view transitions, skip link styling
HEAD_PATCH = (
    SENTINEL +
    '<meta name="view-transition" content="same-origin">'
    '<style>'
    # Skip-link
    '.skip-to-main{position:absolute;left:-9999px;top:auto;width:1px;height:1px;overflow:hidden;z-index:9999}'
    '.skip-to-main:focus{position:fixed;left:12px;top:12px;width:auto;height:auto;background:#0c5159;color:#fff;padding:10px 18px;border-radius:8px;font-weight:700;font-size:14px;text-decoration:none;box-shadow:0 4px 12px rgba(0,0,0,.2)}'
    # Focus visible (replaces default browser ring with branded teal)
    '*:focus-visible{outline:2px solid #0c5159;outline-offset:2px;border-radius:4px}'
    # View transitions
    '@view-transition{navigation:auto}'
    '::view-transition-old(root),::view-transition-new(root){animation-duration:.25s}'
    '@media(prefers-reduced-motion:reduce){::view-transition-old(root),::view-transition-new(root){animation:none}}'
    '</style>'
)

# 2) Skip-link to inject right after <body...>
SKIP_LINK = '<a href="#main-content" class="skip-to-main" data-zh="跳至主要內容" data-en="Skip to main content">跳至主要內容</a>'


def patch_html(html):
    """Returns (new_html, modified_bool)."""
    if SENTINEL in html:
        return html, False

    # 1) Inject HEAD_PATCH right before </head>
    if '</head>' not in html:
        return html, False
    new = html.replace('</head>', HEAD_PATCH + '</head>', 1)

    # 2) Inject skip-link right after <body...>
    body_match = re.search(r'(<body[^>]*>)', new)
    if body_match:
        new = new[:body_match.end()] + SKIP_LINK + new[body_match.end():]

    # 3) Add id="main-content" + role="main" to first <main> if not present
    # (most articles use <main>, fallback to first <article>)
    if '<main' in new and 'id="main-content"' not in new:
        new = re.sub(r'<main\b([^>]*)>', lambda m: f'<main id="main-content" role="main"{m.group(1)}>' if 'id=' not in m.group(1) else m.group(0), new, count=1)
    elif '<main' not in new and 'id="main-content"' not in new:
        # Find first <article> or fallback to first <section>
        m = re.search(r'<article\b([^>]*)>', new)
        if m and 'id=' not in m.group(1):
            new = new[:m.start()] + f'<article id="main-content"{m.group(1)}>' + new[m.end():]

    return new, True


def main():
    n = 0
    for d, _, fs in os.walk(ROOT):
        if any(x in d for x in ['.git', '__pycache__', 'node_modules', 'astro-rewrite']):
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
    print(f'Patched {n} HTML files with a11y + view-transitions')

if __name__ == '__main__':
    main()
