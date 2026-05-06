#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Convert half-width punctuation to full-width in Chinese contexts.

Rule: punctuation immediately preceded OR followed by a Chinese char becomes full-width.
Skips: <script>, <style>, JSON-LD, code blocks, attributes (href / src / data-*).

Conservative approach — only converts when at least one neighbor is CJK.
Safe for mixed-language paragraphs.
"""
import os, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))

# Half→Full mappings for punctuation only
H2F = {
    ',': '，',
    '.': '。',
    ':': '：',
    ';': '；',
    '?': '？',
    '!': '！',
    '(': '（',
    ')': '）',
}
CJK = r'一-鿿㐀-䶿'  # Han + Han ext A

def convert_chinese_punct(text):
    """Convert half-width punct that has CJK char on either side to full-width.
    Special handling for periods (avoid converting decimal points / URLs / version numbers)."""
    out = list(text)
    n = len(out)
    for i in range(n):
        c = out[i]
        if c not in H2F:
            continue
        prev_c = out[i-1] if i > 0 else ''
        next_c = out[i+1] if i+1 < n else ''
        prev_is_cjk = bool(re.match(rf'[{CJK}]', prev_c))
        next_is_cjk = bool(re.match(rf'[{CJK}]', next_c))
        # Period special case — only convert if both sides CJK (avoid 1.5, U.S., e.g.)
        if c == '.' and not (prev_is_cjk and next_is_cjk):
            continue
        # Parens — convert ( only if next is CJK; ) only if prev is CJK
        if c == '(' and not next_is_cjk:
            continue
        if c == ')' and not prev_is_cjk:
            continue
        # General rule for ,?!:;
        if prev_is_cjk or next_is_cjk:
            out[i] = H2F[c]
    return ''.join(out)

# Regex to skip protected regions
PROTECTED_PATTERN = re.compile(
    r'(<script[\s\S]*?</script>|<style[\s\S]*?</style>|<code[\s\S]*?</code>|'
    r'<pre[\s\S]*?</pre>|<!--[\s\S]*?-->|<[^>]+>)'
)

def process_html(html):
    """Walk through HTML, convert text nodes only (skip tags + scripts + style)."""
    parts = []
    last = 0
    for m in PROTECTED_PATTERN.finditer(html):
        # text before this protected block
        text = html[last:m.start()]
        parts.append(convert_chinese_punct(text))
        # the protected block itself — DO NOT convert, but DO convert
        # certain attributes (data-zh / alt with CJK)
        block = m.group(0)
        # Only attribute values data-zh / alt / title / aria-label / placeholder
        block = re.sub(
            r'((?:data-zh|alt|title|aria-label|placeholder)\s*=\s*")([^"]*)(")',
            lambda mm: mm.group(1) + convert_chinese_punct(mm.group(2)) + mm.group(3),
            block
        )
        parts.append(block)
        last = m.end()
    parts.append(convert_chinese_punct(html[last:]))
    return ''.join(parts)

def process_js(js):
    """For JS files — only convert content inside string literals that contain CJK.
    Skip comments + identifiers + regexes."""
    # Conservative: scan single-quoted, double-quoted, and template literal strings
    out = []
    i, n = 0, len(js)
    while i < n:
        c = js[i]
        if c in ('"', "'", '`'):
            q = c
            j = i + 1
            while j < n:
                if js[j] == '\\':
                    j += 2; continue
                if js[j] == q:
                    j += 1; break
                if q != '`' and js[j] == '\n':
                    break
                j += 1
            literal = js[i:j]
            # Convert if contains CJK
            if re.search(rf'[{CJK}]', literal):
                inner = literal[1:-1]
                inner = convert_chinese_punct(inner)
                out.append(literal[0] + inner + literal[-1])
            else:
                out.append(literal)
            i = j
            continue
        if c == '/' and js[i+1:i+2] == '/':
            # line comment — skip but preserve
            j = js.find('\n', i)
            if j < 0: j = n
            out.append(js[i:j])
            i = j
            continue
        if c == '/' and js[i+1:i+2] == '*':
            j = js.find('*/', i+2)
            if j < 0: break
            j += 2
            out.append(js[i:j])
            i = j
            continue
        out.append(c)
        i += 1
    return ''.join(out)

def main():
    n_html = 0
    n_js = 0
    n_chars = 0
    for d, _, fs in os.walk(ROOT):
        if any(x in d for x in ['.git', '__pycache__', 'node_modules', 'astro-rewrite']):
            continue
        for f in fs:
            p = os.path.join(d, f)
            if f.endswith('.html'):
                with open(p, 'r', encoding='utf-8') as fp:
                    src = fp.read()
                new = process_html(src)
                if new != src:
                    with open(p, 'w', encoding='utf-8') as fp:
                        fp.write(new)
                    n_html += 1
                    n_chars += sum(1 for a, b in zip(src, new) if a != b)
            elif f == 'blog-shared.js':
                with open(p, 'r', encoding='utf-8') as fp:
                    src = fp.read()
                new = process_js(src)
                if new != src:
                    with open(p, 'w', encoding='utf-8') as fp:
                        fp.write(new)
                    n_js += 1
                    n_chars += sum(1 for a, b in zip(src, new) if a != b)
    print(f'HTML files modified: {n_html}')
    print(f'JS files modified: {n_js}')
    print(f'Characters changed: {n_chars}')

if __name__ == '__main__':
    main()
