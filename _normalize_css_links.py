#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Normalize local CSS links to CSP-friendly stylesheet links."""

from __future__ import annotations

import os
import re
import html
from _html_scan import iter_tags, tag_name, attributes, blank_script_style, mask_inert_regions


ROOT = os.path.dirname(os.path.abspath(__file__))
ASSET_VERSION = "202609061500"


def normalize_font_loading(src: str) -> str:
    """Web fonts enhance the system-font page without blocking its first paint."""
    src = re.sub(r'<noscript><link\b[^>]*data-dn-fonts-fallback[^>]*></noscript>', '', src)
    src = re.sub(r'<script\b[^>]*src="/assets/inline/font-loader\.js(?:\?v=\d+)?"[^>]*></script>', '', src)
    edits = []
    for offset, tag in iter_tags(mask_inert_regions(blank_script_style(src))):
        attrs = attributes(tag)
        if tag_name(tag) != 'link' or attrs.get('rel') != 'stylesheet':
            continue
        url = html.unescape(attrs.get('href', ''))
        if not url.startswith('https://fonts.googleapis.com/css2?'):
            continue
        attrs['media'] = 'print'
        attrs['data-dn-fonts'] = ''
        rendered = '<link' + ''.join(
            f' {key}="{html.escape(html.unescape(value), quote=True)}"'
            for key, value in attrs.items()) + '>'
        rendered += ('<noscript><link rel="stylesheet" href="'
                     + html.escape(url, quote=True) + '" data-dn-fonts-fallback=""></noscript>')
        edits.append((offset, offset + len(tag), rendered))
    for start, end, replacement in reversed(edits):
        src = src[:start] + replacement + src[end:]
    if edits:
        loader = f'<script defer src="/assets/inline/font-loader.js?v={ASSET_VERSION}"></script>'
        src = src.replace('</head>', loader + '</head>', 1)
    return src

PRELOAD_TW_MINI_RE = re.compile(
    r'<link\s+rel="preload"\s+as="style"\s+href="([^"]*tw-mini\.css[^"]*)"\s+'
    r'onload="this\.onload=null;this\.rel=\'stylesheet\'"\s*/?>'
    r'\s*<noscript><link\s+rel="stylesheet"\s+href="\1"\s*/?></noscript>',
    re.IGNORECASE,
)
PRELOAD_TW_MINI_SINGLE_RE = re.compile(
    r'<link\s+rel="preload"\s+as="style"\s+href="([^"]*tw-mini\.css[^"]*)"\s+'
    r'onload="this\.onload=null;this\.rel=\'stylesheet\'"\s*/?>',
    re.IGNORECASE,
)
PRELOAD_GOOGLE_FONTS_RE = re.compile(
    r'\s*<link\s+rel="preload"\s+as="style"\s+href="https://fonts\.googleapis\.com/css2\?[^"]+"\s*/?>',
    re.IGNORECASE,
)
FONT_PRECONNECT_RE = re.compile(
    r'<link\s+rel="preconnect"\s+href="https://fonts\.(?:googleapis|gstatic)\.com"(?:\s+crossorigin)?\s*/?>',
    re.IGNORECASE,
)
PRELOAD_BLOG_SHARED_RE = re.compile(
    r'\s*<link\s+rel="(?:modulepreload|preload)"(?:\s+as="script")?\s+href="[^"]*blog-shared(?:\.min)?\.js[^"]*"\s*/?>',
    re.IGNORECASE,
)
BLOG_SHARED_SCRIPT_RE = re.compile(
    r'\s*<script\s+src="[^"]*/blog/blog-shared(?:\.min)?\.js[^"]*"\s+defer></script>',
    re.IGNORECASE,
)
BLOG_SHARED_SRC_RE = re.compile(r'(/blog/blog-shared\.min\.js)(?:\?v=\d+)?')
SHARED_CSS_SRC_RE = re.compile(r'(/assets/dn-(?:below-fold|print)\.css)(?:\?v=\d+)?')


def html_files() -> list[str]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in {'.git', 'node_modules'}]
        for filename in filenames:
            if filename.endswith('.html'):
                files.append(os.path.join(dirpath, filename))
    return files


def normalize_file(path: str) -> bool:
    with open(path, 'r', encoding='utf-8') as fp:
        src = fp.read()
    next_src = PRELOAD_TW_MINI_RE.sub(
        lambda m: f'<link rel="stylesheet" href="{m.group(1)}">',
        src,
    )
    next_src = PRELOAD_TW_MINI_SINGLE_RE.sub(
        lambda m: f'<link rel="stylesheet" href="{m.group(1)}">',
        next_src,
    )
    next_src = PRELOAD_GOOGLE_FONTS_RE.sub("", next_src)
    next_src = normalize_font_loading(next_src)
    tags = list(iter_tags(mask_inert_regions(blank_script_style(next_src))))
    is_article = any(tag_name(tag) == 'article' and not tag.startswith('</') for _, tag in tags)
    has_shared_css = any(tag_name(tag) == 'link' and
                         attributes(tag).get('href', '').split('?')[0] == '/assets/dn-below-fold.css'
                         for _, tag in tags)
    if is_article and not has_shared_css:
        next_src = next_src.replace('</head>',
            f'<link rel="stylesheet" href="/assets/dn-below-fold.css?v={ASSET_VERSION}" id="dn-below-fold-css"></head>', 1)
    next_src = PRELOAD_BLOG_SHARED_RE.sub("", next_src)
    next_src = BLOG_SHARED_SRC_RE.sub(rf"\1?v={ASSET_VERSION}", next_src)
    next_src = SHARED_CSS_SRC_RE.sub(rf"\1?v={ASSET_VERSION}", next_src)
    # 2026-05-25 — old heuristic was: "if DN.initBlog is not in the HTML
    # source, the blog-shared.min.js script must be unused, so strip it."
    # That broke after audit follow-up E extracted the inline DN.initBlog
    # bootstrap to /assets/inline/dn-init.js — `DN.initBlog`
    # is now in the external file, not the HTML, so this heuristic
    # silently stripped blog-shared.min.js from 80+ articles.
    # New rule: only strip blog-shared.min.js if NEITHER `DN.initBlog`
    # NOR the inline DN-init bootstrap reference appears. The extracted
    # bootstrap file MUST be the same name shipped from
    # _extract_inline_scripts (rename it together with this check).
    has_dn_init = (
        "DN.initBlog" in next_src
        or "/assets/inline/dn-init.js" in next_src
    )
    if not has_dn_init:
        next_src = BLOG_SHARED_SCRIPT_RE.sub("", next_src)
    seen_fonts: set[str] = set()

    def keep_first_font_preconnect(match: re.Match[str]) -> str:
        tag = match.group(0)
        key = "gstatic" if "fonts.gstatic.com" in tag else "googleapis"
        if key in seen_fonts:
            return ""
        seen_fonts.add(key)
        return tag

    next_src = FONT_PRECONNECT_RE.sub(keep_first_font_preconnect, next_src)
    if next_src == src:
        return False
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(next_src)
    return True


JS_LOADER_RE = re.compile(
    r"(/blog/blog-(?:shared|hub|article-reading|diagrams|calculators|article-visuals|article-footer)\.min\.js\?v=)(\d+)"
)


def normalize_js_loaders() -> int:
    """Bump ?v= asset version inside JS source files that issue dynamic <script> tags.

    Without this, HTML (normalized above) and JS sources can drift, which
    _check_runtime_smoke.py blocks. Targets both .js and .min.js so a partial
    minify state doesn't leave the .min.js stale.
    """
    targets = [
        os.path.join(ROOT, 'blog', name)
        for name in (
            'blog-shared.js',
            'blog-shared.min.js',
            'blog-article-reading.js',
            'blog-article-reading.min.js',
        )
    ]
    changed = 0
    for path in targets:
        if not os.path.exists(path):
            continue
        with open(path, 'r', encoding='utf-8') as fp:
            src = fp.read()
        next_src = JS_LOADER_RE.sub(lambda m: m.group(1) + ASSET_VERSION, src)
        if next_src != src:
            with open(path, 'w', encoding='utf-8') as fp:
                fp.write(next_src)
            changed += 1
    return changed


def main() -> None:
    changed = sum(1 for path in html_files() if normalize_file(path))
    print(f'Normalized CSS links in {changed} files')
    js_changed = normalize_js_loaders()
    if js_changed:
        print(f'Normalized JS dynamic-loader asset-version in {js_changed} files')


if __name__ == '__main__':
    main()
