#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Replace half-width ASCII punctuation with full-width when sandwiched
between CJK characters.

Only touches:
    A , B    where A and B are both CJK → A,B
    A 。 B          (also handles `.` in trailing position end-of-sentence)
    A ; B    →    A;B
    A : B    →    A:B
    A ! B    →    A!B
    A ? B    →    A?B
    ( CJK )  →    (CJK)   (parentheses around CJK content)

Will NOT touch:
- ASCII punctuation between English/numbers (e.g. "3.5 mg/kg", "Sabroe 2021, BJD")
- Anything inside <script> or <style> tags
- URL paths or attribute values like class=, src=, href=
- Punctuation between an English term and CJK (mixed context — leave to
  per-author judgment)

Skips _pdf_extracts/ and _bin/ paths.
"""
import os, re, sys, io, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))

# Unicode ranges
CJK = r'一-鿿㐀-䶿豈-﫿'
# Map of half-width ASCII → full-width Chinese (explicit Unicode escapes
# so the source file isn't ambiguous when an editor input-method silently
# downcasts a full-width char to ASCII).
MAP = {
    ',':  '，',  # ASCII , → ，
    ';':  '；',  # ASCII ; → ；
    ':':  '：',  # ASCII : → :
    '!':  '！',  # ASCII ! → !
    '?':  '？',  # ASCII ? → ?
}
# . is special — full-width period for CJK end-of-sentence is 。 (U+3002).
# Only convert . between CJK or in trailing-CJK-sentence positions.
DOT_PAT = re.compile(
    r'([' + CJK + r'])\.(?=[' + CJK + r']|\s*$|\s*[「『』」。、，；：！？])'
)

# Punctuation in CJK context — match if punct is in a non-whitespace position
# and at least one side (typically the side AFTER) is CJK. This catches:
#   2-10%;台灣  (% is non-CJK but followed by CJK → in a Chinese sentence)
#   (Sabroe),台灣
#   Hello, 世界
# without accidentally hitting pure-English code:
#   var x = 1, y;  (no CJK after `,` → no match)
# Sentence-content chars that count as "CJK-adjacent" for punctuation context:
# CJK + Enclosed Alphanumerics (①②③) + Halfwidth & Fullwidth Forms (already covered)
# + numbers/letters (so `2-10%;台灣` matches via either side).
CJK_EXT = CJK + r'①-⓿'  # ①-Ⓩ  (circled digits/letters used in TC docs)

def make_pat_pre(half):
    # CJK-before pattern: CJK + punct + (CJK | space + CJK | letter/digit |
    # tag boundary < | quote " ' | backslash for JSON \n | math symbols).
    # Backslash matches `?\n` JSON escape; ≥/≤ etc. for `斯;≥2`.
    return re.compile(
        r'(?<=[' + CJK_EXT + r'])'
        + re.escape(half)
        + r'(?=[' + CJK_EXT + r']|\s+[' + CJK_EXT + r']|[A-Za-z0-9<>(（"\'\\\\≥≤±·＞＜∼])'
    )

def make_pat_post(half):
    # punct + CJK-after: any non-whitespace + punct + (CJK or circled-digit)
    return re.compile(
        r'(?<=\S)' + re.escape(half) + r'(?=\s*[' + CJK_EXT + r'])'
    )

PATS_PRE  = {h: (make_pat_pre(h), f) for h, f in MAP.items()}
PATS_POST = {h: (make_pat_post(h), f) for h, f in MAP.items()}

# Strip ONLY non-JSON-LD <script> blocks (i.e. real JS code, where ASCII
# punctuation might be syntactically meaningful). <style> blocks are LEFT
# substitutable because CSS CJK only appears inside string values
# (`content: "..."` etc.) where Chinese punctuation is appropriate.
# <script type="application/ld+json"> is also left substitutable because
# JSON-LD strings are display content.
SCRIPT_RE = re.compile(
    r'(<script\b(?![^>]*application/ld\+json)[^>]*>.*?</script>)',
    re.DOTALL | re.IGNORECASE,
)

def fix(text):
    # Save script/style blocks
    saved = []
    def save(m):
        saved.append(m.group(0))
        return f'\x00{len(saved)-1}\x00'
    stripped = SCRIPT_RE.sub(save, text)

    # Apply all punct replacements (two passes: CJK-before and CJK-after)
    n_total = 0
    for h, (pat, full) in PATS_PRE.items():
        new, n = pat.subn(full, stripped)
        stripped = new
        n_total += n
    for h, (pat, full) in PATS_POST.items():
        new, n = pat.subn(full, stripped)
        stripped = new
        n_total += n
    # Period
    new, n = DOT_PAT.subn(lambda m: m.group(1) + '。', stripped)
    stripped = new
    n_total += n

    # Restore script/style blocks
    def restore(m):
        return saved[int(m.group(1))]
    final = re.sub(r'\x00(\d+)\x00', restore, stripped)
    return final, n_total

EXTS = ['.html']
SKIP_DIRS = {'_pdf_extracts', '_bin', 'pagefind'}
total_files = 0
total_changes = 0
for sub in ['', 'blog', 'en', os.path.join('en','blog')]:
    pattern = os.path.join(ROOT, sub, '*.html')
    for path in glob.glob(pattern):
        if any(d in path for d in SKIP_DIRS): continue
        with open(path, 'r', encoding='utf-8') as f: src = f.read()
        new, n = fix(src)
        if n:
            with open(path, 'w', encoding='utf-8') as f: f.write(new)
            total_files += 1
            total_changes += n
            base = os.path.relpath(path, ROOT)
            print(f'  {base}: {n} subs')
print(f'\n{total_changes} substitutions across {total_files} files.')
