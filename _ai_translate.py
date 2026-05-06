#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F14 — Bulk-translate the remaining 5 articles via Anthropic Claude API.

Usage:
    set ANTHROPIC_API_KEY=sk-ant-...
    python _ai_translate.py topical-acids-patient
    python _ai_translate.py --all                  # do all empty articles

Cost estimate: NT$30-50 per ~200-string article using claude-3-5-haiku.
Translates one batch (50 strings) per API call to keep latency low and
allow recovery from transient errors.

After translation, runs:
    python _translate_pipeline.py inject <slug>
to write data-en attributes into the actual HTML.
"""
import os, json, sys, io, time
import urllib.request, urllib.error
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'data', 'translations')
API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
MODEL = 'claude-3-5-haiku-20241022'
BATCH_SIZE = 50

SYSTEM_PROMPT = """You are translating Traditional Chinese (Taiwan) medical patient-education content to clinical English.

Rules:
1. Use medical English terminology (e.g., "atopic dermatitis", not "atopic eczema").
2. Keep formatting markers like <strong>, <em> intact.
3. Decimal numbers, ICD codes, lab values: keep verbatim.
4. Preserve em-dashes "—" and full-width punctuation in references.
5. For drug names: prefer generic INN (e.g., "tacrolimus") with brand in parentheses if present.
6. For Taiwan-specific concepts (健保 NHI, TDA, PTT/Dcard): translate as "NHI", "Taiwanese Dermatological Association", "online forums".
7. Keep brevity: aim within ±25% length of source.

Return ONLY the translated text, no quotes, no commentary, no markdown."""

def log(msg):
    print(msg, flush=True)

def call_claude(text):
    """One API call. Returns the translated string or raises."""
    if not API_KEY:
        raise RuntimeError('Set ANTHROPIC_API_KEY environment variable')
    body = json.dumps({
        'model': MODEL,
        'max_tokens': 2000,
        'system': SYSTEM_PROMPT,
        'messages': [{'role': 'user', 'content': text}],
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=body,
        headers={
            'Content-Type': 'application/json',
            'x-api-key': API_KEY,
            'anthropic-version': '2023-06-01',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        return data['content'][0]['text'].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'API HTTP {e.code}: {body[:200]}')

def translate_batch(items):
    """Send a batch of {zh, en, tag} items. Each line is numbered for parsing."""
    payload = '\n'.join(f'{i+1}. {x["zh"]}' for i, x in enumerate(items))
    out = call_claude(payload)
    # Parse numbered lines
    lines = out.split('\n')
    results = [''] * len(items)
    for ln in lines:
        m = ln.strip()
        if not m:
            continue
        # Match "1. translation" or "1) translation"
        for i in range(len(items), 0, -1):
            for prefix in (f'{i}. ', f'{i}) ', f'{i}: '):
                if m.startswith(prefix):
                    results[i-1] = m[len(prefix):].strip()
                    break
            if results[i-1]:
                break
    # Fall back: if exactly N lines and parsing failed, take them in order
    cleaned = [r for r in results if r]
    if len(cleaned) != len(items):
        nonempty = [l for l in lines if l.strip()]
        if len(nonempty) == len(items):
            for i, ln in enumerate(nonempty):
                if not results[i]:
                    # Strip leading numbering
                    s = ln.strip()
                    s = s.split('. ', 1)[-1] if s[0:2].rstrip('.').isdigit() else s
                    results[i] = s
    return results

def translate_file(slug):
    path = os.path.join(DATA, slug + '.json')
    if not os.path.exists(path):
        log(f'  ! not found: {path}')
        return
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    todo = [s for s in data['strings'] if not s.get('en', '').strip()]
    if not todo:
        log(f'  ✓ {slug}: already complete ({len(data["strings"])} strings)')
        return
    log(f'  → {slug}: {len(todo)} strings to translate (in batches of {BATCH_SIZE})')
    done = 0
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i+BATCH_SIZE]
        for retry in range(3):
            try:
                results = translate_batch(batch)
                for s, en in zip(batch, results):
                    if en:
                        s['en'] = en
                        done += 1
                break
            except Exception as e:
                log(f'    ⚠ batch {i//BATCH_SIZE+1} attempt {retry+1} failed: {e}')
                time.sleep(2 * (retry + 1))
        # Save after each batch to allow resume
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log(f'    saved batch {i//BATCH_SIZE+1} ({done}/{len(todo)})')
    log(f'  ✓ {slug}: {done}/{len(todo)} translated')

REMAINING = ['topical-acids-patient', 'biologics-overview', 'laser-dermatology',
             'nhi-derm-drugs', 'alopecia-areata']

def main():
    args = sys.argv[1:]
    if not args:
        print('Usage: python _ai_translate.py <slug> [<slug>...] | --all')
        return
    slugs = REMAINING if '--all' in args else [a for a in args if not a.startswith('-')]
    log(f'Starting AI translation for {len(slugs)} article(s)')
    if not API_KEY:
        log('  ! Set ANTHROPIC_API_KEY first')
        return
    for slug in slugs:
        translate_file(slug)
    log('\nDone. Now run:')
    log('  python _translate_pipeline.py inject <slug>')
    log('for each file to write data-en attributes into the HTML.')

if __name__ == '__main__':
    main()
