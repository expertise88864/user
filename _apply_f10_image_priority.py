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
import os, re
from pathlib import Path
from _site_html import site_html_files
from _html_scan import attribute_spans, attributes, blank_script_style, iter_tags, mask_inert_regions, tag_name

ROOT = os.path.dirname(os.path.abspath(__file__))

IMG_RE = re.compile(r'<img\s+([^>]+?)/?>', re.IGNORECASE)

def patch_attrs(attrs, is_first):
    """Patch a single <img>'s attribute string."""
    prefix = '<img '
    spans = attribute_spans(prefix + attrs + '>')
    out = attrs.rstrip()
    values = {'loading': 'eager', 'fetchpriority': 'high'} if is_first else {}
    if 'loading' not in spans and not is_first:
        values['loading'] = 'lazy'
    if 'decoding' not in spans:
        values['decoding'] = 'async'
    edits = [(spans[name][0] - len(prefix), spans[name][1] - len(prefix), name+'="'+value+'"')
             for name, value in values.items() if name in spans]
    for start, end, replacement in sorted(edits, reverse=True):
        out = out[:start] + replacement + out[end:]
    for name, value in values.items():
        if name not in spans:
            out += ' '+name+'="'+value+'"'
    return out

def patch_html(html):
    """Replace <img> tags. First one gets eager+high; rest get lazy."""
    seen_first = False
    edits = []
    template_depth = 0
    for offset, tag in iter_tags(mask_inert_regions(blank_script_style(html))):
        if tag_name(tag) == 'template':
            template_depth = max(0, template_depth - 1) if tag.startswith('</') else template_depth + 1
            continue
        if template_depth:
            continue
        if tag.startswith('</') or tag_name(tag) != 'img':
            continue
        spans = attribute_spans(tag)
        parsed = attributes(tag)
        is_decorative = parsed.get('aria-hidden') == 'true' and (parsed.get('width') == '1' or 'tracking' in parsed.get('src', '').lower())
        if is_decorative:
            continue
        # Preserve a self-closing marker, but never strip an unquoted URL slash.
        closing = len(tag) - 2
        self_closing = tag.endswith('/>') and not any(start <= closing < end for start, end, _, _ in spans.values())
        attrs = tag[4:-2] if self_closing else tag[4:-1]
        new_tag = '<img ' + patch_attrs(attrs.lstrip(), not seen_first) + (' />' if self_closing else '>')
        edits.append((offset, offset + len(tag), new_tag))
        seen_first = True
    new_html = html
    for start, end, replacement in reversed(edits):
        new_html = new_html[:start] + replacement + new_html[end:]
    return new_html, new_html != html

def main():
    n = 0
    total_imgs = 0
    for path in site_html_files(Path(ROOT)):
        src = path.read_text(encoding='utf8')
        new, changed = patch_html(src)
        if changed:
            path.write_text(new, encoding='utf8')
            n += 1
            total_imgs += sum(tag_name(tag) == 'img' and not tag.startswith('</')
                              for _, tag in iter_tags(mask_inert_regions(blank_script_style(src))))
    print(f'Patched {n} HTML files ({total_imgs} <img> tags processed)')

if __name__ == '__main__':
    main()
