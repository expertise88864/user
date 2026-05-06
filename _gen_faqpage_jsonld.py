#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E11 — Bulk-extract <details><summary> Q&A from articles and inject FAQPage JSON-LD.

Why: Google rewards FAQPage rich result. ~80% of articles already have
"常見問題 (Common Questions)" sections using <details><summary>. We just need to
emit the matching schema.org JSON-LD so Google can render the rich result.

Idempotent: removes any prior auto-generated <script data-faq-auto>
before injecting the fresh version.
"""
import os, re, json, sys, io, html
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
BLOG = os.path.join(ROOT, 'blog')

DETAILS_RE = re.compile(r'<details[^>]*>([\s\S]*?)</details>', re.IGNORECASE)
SUMMARY_RE = re.compile(r'<summary[^>]*>([\s\S]*?)</summary>', re.IGNORECASE)

def strip_html(s):
    """Strip tags and decode entities; collapse whitespace."""
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def extract_faqs(html_text):
    """Return list of {q, a} from <details><summary> blocks in main article."""
    # Limit search to inside <article> if present, else whole body
    art_m = re.search(r'<article\b[^>]*>([\s\S]*?)</article>', html_text)
    scope = art_m.group(1) if art_m else html_text
    out = []
    for m in DETAILS_RE.finditer(scope):
        body = m.group(1)
        sm = SUMMARY_RE.search(body)
        if not sm:
            continue
        q = strip_html(sm.group(1))
        # answer = body minus summary
        ans = body[:sm.start()] + body[sm.end():]
        a = strip_html(ans)
        if not q or not a:
            continue
        if len(a) < 10:
            continue
        # dedupe
        if any(x['q'] == q for x in out):
            continue
        out.append({'q': q, 'a': a})
    return out

def remove_old(html_text):
    """Strip prior auto-generated FAQPage JSON-LD."""
    return re.sub(
        r'<script\s+type="application/ld\+json"\s+data-faq-auto[^>]*>[\s\S]*?</script>\s*',
        '',
        html_text
    )

def inject(html_text, faqs):
    if not faqs:
        return html_text, False
    schema = {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': [
            {'@type': 'Question', 'name': f['q'],
             'acceptedAnswer': {'@type': 'Answer', 'text': f['a'][:5000]}}
            for f in faqs
        ]
    }
    block = '<script type="application/ld+json" data-faq-auto>' + \
            json.dumps(schema, ensure_ascii=False, separators=(',', ':')) + \
            '</script>'
    new = remove_old(html_text)
    if '</head>' in new:
        new = new.replace('</head>', block + '</head>', 1)
    else:
        return new, False
    return new, True

def main():
    n_files = 0
    n_faqs = 0
    skipped = 0
    for f in sorted(os.listdir(BLOG)):
        if not f.endswith('.html'):
            continue
        p = os.path.join(BLOG, f)
        with open(p, 'r', encoding='utf-8') as fp:
            src = fp.read()
        faqs = extract_faqs(src)
        if not faqs:
            skipped += 1
            continue
        new, changed = inject(src, faqs)
        if changed and new != src:
            with open(p, 'w', encoding='utf-8') as fp:
                fp.write(new)
            n_files += 1
            n_faqs += len(faqs)
            print(f'  {f}: {len(faqs)} FAQs')
    print(f'\nInjected FAQPage JSON-LD into {n_files} articles ({n_faqs} Q&A total)')
    print(f'Skipped (no <details><summary>): {skipped} files')

if __name__ == '__main__':
    main()
