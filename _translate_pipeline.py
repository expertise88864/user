#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Translation pipeline — extract Chinese text needing translation, inject EN.

Usage:
  python _translate_pipeline.py extract <article-slug>
    → writes data/translations/<slug>.json with {"strings": [{"zh": "...", "en": ""}, ...]}

  python _translate_pipeline.py inject <article-slug>
    → reads the JSON (after you fill "en" fields), writes data-en into the HTML

The script targets:
  - <h1>, <h2>, <h3>, <h4> heading text
  - <p> paragraphs (only top-level body paragraphs, not nested)
  - <strong>, <em> inline emphasis
  - <li> list items
  - <figcaption>, <summary> details/figure captions

Skips:
  - <script>, <style>, <nav>, <footer>
  - tags that already have data-en
  - tags inside JSON-LD blocks

This lets you do article translations in bulk without manually editing HTML.
Pair with an LLM batch-translate run on the JSON file.
"""
import os, re, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
BLOG = os.path.join(ROOT, 'blog')
DATA = os.path.join(ROOT, 'data', 'translations')

TRANSLATABLE_TAGS = ('h1', 'h2', 'h3', 'h4', 'p', 'li', 'strong', 'em',
                     'figcaption', 'summary', 'span', 'small', 'th', 'td')

def has_chinese(text):
    return bool(re.search(r'[一-鿿]', text))

def strip_html(html):
    return re.sub(r'<[^>]+>', '', html).strip()

def extract(slug):
    path = os.path.join(BLOG, slug + '.html')
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    # Strip JSON-LD scripts to avoid extracting from there
    no_json = re.sub(r'<script type="application/ld\+json">[\s\S]*?</script>', '', html)
    no_json = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', no_json)
    no_json = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', no_json)

    found = {}
    for tag in TRANSLATABLE_TAGS:
        pat = re.compile(r'<' + tag + r'\b([^>]*)>([^<]+?)</' + tag + r'>', re.IGNORECASE)
        for m in pat.finditer(no_json):
            attrs = m.group(1)
            text = m.group(2).strip()
            if 'data-en=' in attrs:
                continue
            if not has_chinese(text):
                continue
            if len(text) < 2:
                continue
            # dedupe
            if text not in found:
                found[text] = {'zh': text, 'en': '', 'tag': tag}
    out_path = os.path.join(DATA, slug + '.json')
    os.makedirs(DATA, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'slug': slug, 'strings': list(found.values())}, f,
                  ensure_ascii=False, indent=2)
    print(f'Extracted {len(found)} unique strings → {out_path}')

def _segment_outside_attrs(html):
    """Yield (offset, segment) pairs covering everything in `html` that is NOT
    inside a tag's attribute value. Substring positions returned in segments
    map back to absolute offsets via `offset`.

    Implemented as a tiny state machine: outside-of-tag is OUTSIDE; inside a
    `<...>` is TAG; inside an attribute value (`"..."` or `'...'` within a tag)
    is ATTRVAL. We yield OUTSIDE segments so the inject regex never matches a
    `<strong>X</strong>` string that lives inside another tag's data-zh value.
    """
    out = []
    i = 0
    n = len(html)
    while i < n:
        # OUTSIDE — collect until next '<'
        j = html.find('<', i)
        if j < 0:
            out.append((i, html[i:]))
            break
        if j > i:
            out.append((i, html[i:j]))
        # We're at a '<' — walk through the tag, skipping any quoted attr values
        i = j
        if i + 1 < n and html[i+1] in ('!', '?'):
            # Comment, CDATA, doctype, processing instruction — skip to next '>'
            k = html.find('>', i)
            i = (k + 1) if k > 0 else n
            continue
        # Real tag: walk forward, tracking quote state
        in_quote = None
        i += 1  # past '<'
        while i < n:
            c = html[i]
            if in_quote:
                if c == in_quote:
                    in_quote = None
                i += 1
                continue
            if c == '"' or c == "'":
                in_quote = c
                i += 1
                continue
            if c == '>':
                i += 1
                break
            i += 1
    return out


def inject(slug):
    path = os.path.join(BLOG, slug + '.html')
    json_path = os.path.join(DATA, slug + '.json')
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    n = 0
    for entry in data['strings']:
        zh = entry['zh']; en = entry['en']
        if not en or not zh:
            continue
        # Build a fresh attr-aware segmentation each round (because injects mutate html)
        segments = _segment_outside_attrs(html)
        # For each OUTSIDE segment, do the regex sub locally; reassemble.
        new_parts = []
        last_end = 0
        for offset, seg in segments:
            new_parts.append(html[last_end:offset])
            seg_changed = seg
            for tag in TRANSLATABLE_TAGS:
                pat = re.compile(
                    r'(<' + tag + r'\b)((?:(?!data-en=)[^>])*)(>)' + re.escape(zh) + r'(</' + tag + r'>)',
                    re.IGNORECASE
                )
                seg_changed, count = pat.subn(
                    lambda m: m.group(1) + m.group(2) + ' data-zh="' + zh.replace('"', '&quot;') +
                              '" data-en="' + en.replace('"', '&quot;') + '"' + m.group(3) + zh + m.group(4),
                    seg_changed
                )
                n += count
            new_parts.append(seg_changed)
            last_end = offset + len(seg)
        new_parts.append(html[last_end:])
        html = ''.join(new_parts)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Injected {n} data-en attributes into {slug}.html')

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(0)
    cmd = sys.argv[1]; slug = sys.argv[2]
    if cmd == 'extract': extract(slug)
    elif cmd == 'inject': inject(slug)
    else: print('Unknown command:', cmd)

if __name__ == '__main__':
    main()
