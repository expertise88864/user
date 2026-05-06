#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E2 — Inline critical-CSS for above-the-fold rendering.

Strategy:
  1. Read the existing assets/tw-mini.css (the only big external stylesheet)
  2. Parse out rules whose selectors target ATF elements:
     - html, body, *
     - root CSS variables (:root)
     - layout primitives (.container, .max-w-*, .mx-auto, .px-*, .py-*)
     - typography (h1, h2, h3, .font-display, .font-body)
     - first-screen widgets (header, nav, .hero, .breadcrumb, .chip)
  3. Inline those rules in <style data-critical> right before </head>
  4. Convert the original <link rel="stylesheet" href="…tw-mini.css"> to a
     non-blocking preload pattern:
       <link rel="preload" as="style" href="…" onload="this.onload=null;this.rel='stylesheet'">
       <noscript><link rel="stylesheet" href="…"></noscript>

Idempotent: skips files already processed (look for `data-critical`).

Run after every CSS change:
  python _extract_critical_css.py
"""
import os, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
CSS_PATH = os.path.join(ROOT, 'assets', 'tw-mini.css')

CRITICAL_SELECTORS_RE = re.compile(
    r'^(?:'
    r'html|body|\*|::?(?:before|after)|'                      # globals
    r':root|'                                                  # CSS variables
    r'\.container\b|\.max-w-[a-z0-9-]+\b|\.mx-auto\b|'        # layout
    r'\.px-\d+\b|\.py-\d+\b|\.pt-\d+\b|\.pb-\d+\b|'           # spacing
    r'\.flex\b|\.grid\b|\.block\b|\.inline\b|\.hidden\b|'     # display
    r'\.items-[a-z]+\b|\.justify-[a-z-]+\b|\.gap-\d+\b|'      # flex
    r'h[1-6]\b|\.font-display\b|\.font-bold\b|\.font-semibold\b|\.font-medium\b|'  # typography
    r'\.text-[a-z0-9-]+\b|\.leading-[a-z-]+\b|'               # text
    r'header\b|nav\b|main\b|article\b|'                       # semantic
    r'\.chip\b|\.btn\b|\.btn-[a-z]+\b|'                       # buttons / chips
    r'\.skip-to-main\b|\.lang-toggle\b|'                      # a11y / lang
    r'\.bg-[a-z0-9-]+\b|\.border\b|\.border-\d+\b|\.border-[a-z0-9-]+\b|'  # bg/border
    r'\.rounded\b|\.rounded-[a-z0-9-]+\b|\.shadow\b|\.shadow-[a-z]+\b'     # shape
    r')'
)

def is_critical_selector(sel):
    """Test the FIRST selector segment (before any descendant combinator)."""
    sel = sel.strip()
    if not sel:
        return False
    # take the leading simple selector
    head = re.split(r'[\s>+~]', sel, 1)[0]
    head = head.split(':', 1)[0]   # drop pseudo
    head = head.split('[', 1)[0]   # drop attr
    return bool(CRITICAL_SELECTORS_RE.match(head))

def parse_css_rules(css):
    """Yield (full_selector_list, body_text) tuples for each top-level rule.
    Skip @media for now (would need recursive parser); keep @supports flat.
    """
    out = []
    i = 0
    n = len(css)
    while i < n:
        # skip whitespace and comments
        while i < n and css[i] in ' \t\n\r':
            i += 1
        if i >= n:
            break
        if css.startswith('/*', i):
            j = css.find('*/', i + 2)
            i = j + 2 if j != -1 else n
            continue
        # @-rules — keep nested or skip
        if css[i] == '@':
            # find matching closing brace OR semicolon (for at-rules without body)
            j = i
            brace = 0
            found_brace = False
            while j < n:
                c = css[j]
                if c == '{': brace += 1; found_brace = True
                elif c == '}':
                    brace -= 1
                    if brace == 0 and found_brace:
                        j += 1
                        break
                elif c == ';' and not found_brace:
                    j += 1
                    break
                j += 1
            block = css[i:j]
            # Try to parse @media / @supports content for critical selectors
            media_m = re.match(r'@(?:media|supports)\s+([^{]+)\{([\s\S]+)\}\s*$', block.strip())
            if media_m:
                cond = media_m.group(1).strip()
                inner = media_m.group(2)
                inner_rules = parse_css_rules(inner)
                # Keep only if any inner rule is critical
                kept = [(s, b) for s, b in inner_rules if any(is_critical_selector(x) for x in s.split(','))]
                if kept:
                    rebuilt = ' '.join(f'{s}{{{b}}}' for s, b in kept)
                    out.append((f'@media {cond}', '{' + rebuilt + '}'))
            i = j
            continue
        # Regular rule: selectors { body }
        brace = css.find('{', i)
        if brace == -1:
            break
        sel = css[i:brace]
        body_start = brace + 1
        depth = 1
        j = body_start
        while j < n and depth > 0:
            c = css[j]
            if c == '{': depth += 1
            elif c == '}': depth -= 1
            j += 1
        body = css[body_start:j-1]
        out.append((sel.strip(), body.strip()))
        i = j
    return out

def build_critical_css(css):
    rules = parse_css_rules(css)
    keep = []
    for sel, body in rules:
        if sel.startswith('@'):
            keep.append(sel + body)   # @media block already wrapped
            continue
        # Multi-selector list: keep only the matching ones
        parts = [s.strip() for s in sel.split(',')]
        kept_parts = [p for p in parts if is_critical_selector(p)]
        if kept_parts:
            keep.append(','.join(kept_parts) + '{' + body + '}')
    out = ''.join(keep)
    # Minify whitespace
    out = re.sub(r'\s+', ' ', out)
    out = re.sub(r'\s*([{}:;,])\s*', r'\1', out)
    return out.strip()

# ─── HTML patcher ───
SENTINEL = 'data-critical-css'
TWMINI_LINK_RE = re.compile(
    r'<link\s+rel="stylesheet"\s+href="([^"]*tw-mini\.css[^"]*)"\s*/?>',
    re.IGNORECASE
)

def patch_html(html, critical):
    if SENTINEL in html:
        return html, False
    # Find the link and replace with preload pattern
    m = TWMINI_LINK_RE.search(html)
    if not m:
        return html, False
    href = m.group(1)
    preload = (
        f'<link rel="preload" as="style" href="{href}" '
        f'onload="this.onload=null;this.rel=\'stylesheet\'">'
        f'<noscript><link rel="stylesheet" href="{href}"></noscript>'
    )
    html = html[:m.start()] + preload + html[m.end():]
    # Inject critical CSS right before </head>
    inline = f'<style {SENTINEL}>{critical}</style>'
    html = html.replace('</head>', inline + '</head>', 1)
    return html, True

def main():
    if not os.path.exists(CSS_PATH):
        print(f'WARN: {CSS_PATH} not found')
        return
    with open(CSS_PATH, 'r', encoding='utf-8') as f:
        css = f.read()
    critical = build_critical_css(css)
    print(f'Critical CSS: {len(critical)} bytes (from {len(css)})')
    if len(critical) > 14000:
        print(f'  WARN: critical CSS exceeds 14 KB (HTTP/2 initial CWND)')

    n = 0
    for d, _, fs in os.walk(ROOT):
        if any(x in d for x in ['.git', 'node_modules', '__pycache__', 'astro-rewrite']):
            continue
        for f in fs:
            if not f.endswith('.html'):
                continue
            p = os.path.join(d, f)
            with open(p, 'r', encoding='utf-8') as fp:
                src = fp.read()
            new, changed = patch_html(src, critical)
            if changed:
                with open(p, 'w', encoding='utf-8') as fp:
                    fp.write(new)
                n += 1
    print(f'Patched {n} HTML files with critical CSS inline')

if __name__ == '__main__':
    main()
