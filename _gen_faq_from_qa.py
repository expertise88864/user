#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Emit FAQPage JSON-LD for articles whose FAQ section uses the `.qa` pattern.

Most articles hand-author a FAQPage block. The newer research-summary
articles (spironolactone, jaki) instead build their FAQ as a sequence of
`<div class="qa"><h3>Q…</h3><p>A…</p></div>` under `<h2 id="faq">`, and never
got a FAQPage block — so they miss the Google FAQ rich-result entirely
(2 articles × 8 Q&A). This generates the matching schema from the rendered
DOM text.

Scope: ONLY the FAQ section (from `<h2 id="faq"` to the next `<h2 `), so the
adjacent `<h2 id="myths">` section (which also uses `.qa`) is not swept in.

Runs on blog/*.html AND en/blog/*.html. The EN mirror already has English
visible text swapped in (via _gen_en_pages), so the EN FAQPage comes out in
English automatically.

Idempotent: marks its output `data-faq-auto` and strips any prior one before
re-injecting. Skips any article that already has a (hand-authored) FAQPage
block without the data-faq-auto marker, to avoid duplicate FAQPage schema.

Safe: only adds a JSON-LD <script> in <head>; no visible/layout change.
"""
from __future__ import annotations
import io, re, json, sys, html
from pathlib import Path

ROOT = Path(__file__).resolve().parent

QA_RE = re.compile(r'<div class="qa">(.*?)</div>', re.DOTALL)
H3_RE = re.compile(r'<h3\b[^>]*>(.*?)</h3>', re.DOTALL | re.IGNORECASE)
P_RE = re.compile(r'<p\b[^>]*>(.*?)</p>', re.DOTALL | re.IGNORECASE)
OLD_RE = re.compile(
    r'<script\s+type="application/ld\+json"\s+data-faq-auto[^>]*>.*?</script>\s*',
    re.DOTALL | re.IGNORECASE,
)


def clean(s: str) -> str:
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)
    return re.sub(r'\s+', ' ', s).strip()


def faq_scope(src: str) -> str | None:
    """Return the HTML between <h2 id="faq" ...> and the next <h2 , or None."""
    m = re.search(r'<h2\b[^>]*\bid="faq"[^>]*>', src, re.IGNORECASE)
    if not m:
        return None
    start = m.end()
    nxt = re.search(r'<h2\b', src[start:], re.IGNORECASE)
    return src[start:start + nxt.start()] if nxt else src[start:]


def extract(src: str) -> list[dict]:
    scope = faq_scope(src)
    if not scope:
        return []
    out: list[dict] = []
    for block in QA_RE.findall(scope):
        hm = H3_RE.search(block)
        if not hm:
            continue
        q = clean(hm.group(1))
        # answer = all <p> after the h3, concatenated
        ans_html = block[block.find('</h3>') + 5:] if '</h3>' in block else block
        a = ' '.join(clean(p) for p in P_RE.findall(ans_html)).strip()
        if not q or len(a) < 10:
            continue
        if any(x['q'] == q for x in out):
            continue
        out.append({'q': q, 'a': a})
    return out


def process(fp: Path) -> int:
    src = fp.read_text(encoding='utf-8')
    # Respect a hand-authored FAQPage (no data-faq-auto marker): don't double up.
    if 'FAQPage' in src and 'data-faq-auto' not in src:
        return 0
    faqs = extract(src)
    if not faqs:
        # nothing to emit; strip any stale auto block
        new = OLD_RE.sub('', src)
        if new != src:
            fp.write_text(new, encoding='utf-8', newline='')
        return 0
    schema = {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': [
            {'@type': 'Question', 'name': f['q'],
             'acceptedAnswer': {'@type': 'Answer', 'text': f['a'][:5000]}}
            for f in faqs
        ],
    }
    block = ('<script type="application/ld+json" data-faq-auto>'
             + json.dumps(schema, ensure_ascii=False, separators=(',', ':'))
             + '</script>')
    new = OLD_RE.sub('', src)
    if '</head>' not in new:
        return 0
    new = new.replace('</head>', block + '</head>', 1)
    if new != src:
        fp.write_text(new, encoding='utf-8', newline='')
        return len(faqs)
    return 0


def main() -> int:
    total_q = 0
    files = 0
    targets = list((ROOT / 'blog').glob('*.html')) + list((ROOT / 'en' / 'blog').glob('*.html'))
    for fp in targets:
        n = process(fp)
        if n:
            files += 1
            total_q += n
            print(f'  {fp.relative_to(ROOT)}: {n} Q&A')
    print(f'[faq-from-qa] FAQPage injected into {files} files ({total_q} Q&A total)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
