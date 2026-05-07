#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Mirror updated <article> bodies from blog/*.html → en/blog/*.html.

Both zh and en sides use paired data-zh / data-en attributes; the JS lang
toggle reads <html lang> to decide which to show. Inline default text is
already Chinese on both sides, so swapping the article body verbatim is
safe — JS will render English on the en/ pages.

Preserves the en file's <head>, <header>, <footer>, JSON-LD, and any
content outside <article>. Only the inner article body is replaced.
"""
import os, re, sys, io, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))

SLUGS = [
    'urticaria-myths', 'vitiligo',
    'psoriasis-myths', 'nhi-derm-drugs',
    'acne-myths', 'acne-scar-treatment',
    'isotretinoin-patient', 'isotretinoin-clinical',
    'topical-acids-patient', 'topical-acids-clinical',
]

# Cutoff — anything mtime > this is "agent-edited"
CUTOFF_TS = datetime.datetime(2026, 5, 7, 20, 30).timestamp()

ART_RE = re.compile(r'(<article\b[^>]*>)(.*?)(</article>)', re.DOTALL)

def replace_article_body(en_html: str, new_body: str) -> tuple[str, bool]:
    """Replace inner content of <article>…</article> in en_html. Keep open/close tags."""
    m = ART_RE.search(en_html)
    if not m:
        return en_html, False
    new_html = en_html[:m.start(2)] + new_body + en_html[m.end(2):]
    return new_html, True

def extract_article_body(zh_html: str) -> str | None:
    m = ART_RE.search(zh_html)
    return m.group(2) if m else None

ok = 0
skipped = 0
for slug in SLUGS:
    zh_path = os.path.join(ROOT, 'blog', f'{slug}.html')
    en_path = os.path.join(ROOT, 'en', 'blog', f'{slug}.html')
    if not os.path.exists(zh_path) or not os.path.exists(en_path):
        print(f'  {slug}: missing file, skip'); skipped += 1; continue

    zh_mt = os.path.getmtime(zh_path)
    if zh_mt < CUTOFF_TS:
        print(f'  {slug}: zh not modified by agents (mtime {datetime.datetime.fromtimestamp(zh_mt)}), skip')
        skipped += 1; continue

    with open(zh_path, 'r', encoding='utf-8') as f: zh = f.read()
    with open(en_path, 'r', encoding='utf-8') as f: en = f.read()

    body = extract_article_body(zh)
    if body is None:
        print(f'  {slug}: no <article> in zh, skip'); skipped += 1; continue

    new_en, ok_replace = replace_article_body(en, body)
    if not ok_replace:
        print(f'  {slug}: no <article> in en, skip'); skipped += 1; continue

    if new_en == en:
        print(f'  {slug}: en already in sync')
        skipped += 1; continue

    with open(en_path, 'w', encoding='utf-8') as f: f.write(new_en)
    new_size = os.path.getsize(en_path) / 1024
    print(f'  ✓ {slug}: en updated ({new_size:.1f} KB)')
    ok += 1

print(f'\nDone — {ok} mirrored, {skipped} skipped')
