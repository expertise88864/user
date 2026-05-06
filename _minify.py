#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Conservative minifier:
  JS: strip block + line comments, collapse multi-blank-lines, trim trailing whitespace.
      Keeps all newlines + per-line indentation removed → ~30-40% savings, very safe.
  HTML: collapse inter-tag whitespace + strip non-build comments. Preserves
      <pre>/<textarea>/<script>/<style>/<code> contents verbatim. ~10-20% savings.

Usage: python _minify.py
Output: blog/blog-shared.min.js (preserve original); HTML files in-place (idempotent).
"""
import os, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────────────────────────────
# JS minifier — extremely conservative (only safe transforms)
# ─────────────────────────────────────────────────────────────────
def js_minify(src):
    """Strip comments + trim whitespace per line. Keep newlines for safety (avoids ASI bugs).

    Handles strings + regex literals so // inside an escaped-slash regex isn't read as comment.
    """
    out = []
    i, n = 0, len(src)
    # Track last non-whitespace char to decide if `/` starts a regex or is division.
    # Regex contexts: after operator chars, ( , ; : ! & | ? { } [ + - * % < > ~ ^, newline,
    # or start of file. Identifier/closing-) means it's division.
    last_signif = '\n'
    REGEX_PREV = set('=(,;:!&|?{}[+-*%<>~^\n')

    while i < n:
        c = src[i]
        nxt = src[i+1] if i+1 < n else ''
        # Preserve string literals verbatim
        if c in ('"', "'", '`'):
            quote = c
            j = i + 1
            while j < n:
                if src[j] == '\\':
                    j += 2; continue
                if src[j] == quote:
                    j += 1; break
                if quote != '`' and src[j] == '\n':
                    break  # broken string, bail
                j += 1
            out.append(src[i:j])
            i = j
            last_signif = quote
            continue
        # Line comment → strip up to (not including) newline
        if c == '/' and nxt == '/':
            j = src.find('\n', i)
            if j < 0:
                break
            i = j
            continue
        # Block comment → drop entirely (preserve license /*! ... */)
        if c == '/' and nxt == '*':
            j = src.find('*/', i+2)
            if j < 0:
                break
            if i+2 < n and src[i+2] == '!':
                out.append(src[i:j+2])
            i = j + 2
            continue
        # Regex literal: `/` after operator/start context, must close with unescaped `/`
        if c == '/' and last_signif in REGEX_PREV:
            j = i + 1
            in_cls = False
            ok = False
            while j < n:
                cj = src[j]
                if cj == '\\' and j + 1 < n:
                    j += 2; continue
                if cj == '[':
                    in_cls = True
                elif cj == ']':
                    in_cls = False
                elif cj == '/' and not in_cls:
                    j += 1
                    # consume regex flags (g, i, m, s, u, y, d)
                    while j < n and src[j] in 'gimsuyd':
                        j += 1
                    ok = True
                    break
                elif cj == '\n':
                    # broken regex — bail; treat original `/` as plain char
                    break
                j += 1
            if ok:
                out.append(src[i:j])
                i = j
                last_signif = '/'
                continue
            # else fall through to normal char handling
        out.append(c)
        if not c.isspace():
            last_signif = c
        i += 1
    s = ''.join(out)
    # Per-line: trim leading/trailing whitespace, drop pure-blank lines
    lines = []
    for line in s.split('\n'):
        line = line.rstrip()
        if line.strip():
            lines.append(line.strip())
    return '\n'.join(lines) + '\n'


# ─────────────────────────────────────────────────────────────────
# HTML minifier — preserve content blocks
# ─────────────────────────────────────────────────────────────────
PRESERVE_TAGS = ('pre', 'textarea', 'script', 'style', 'code')

def html_minify(src):
    placeholders = []
    def stash(m):
        placeholders.append(m.group(0))
        return f'\x00H{len(placeholders)-1}\x00'
    pat = re.compile(r'<(' + '|'.join(PRESERVE_TAGS) + r')\b[^>]*>[\s\S]*?</\1>', re.IGNORECASE)
    s = pat.sub(stash, src)
    # Strip HTML comments — keep IE conditional + build markers
    s = re.sub(r'<!--(?!\[if|<!\[|\s*build\s)[\s\S]*?-->', '', s)
    # Collapse whitespace between tags
    s = re.sub(r'>\s+<', '><', s)
    # Collapse runs of spaces (not newlines, to keep some structure)
    s = re.sub(r'[ \t]{2,}', ' ', s)
    # Collapse multiple newlines
    s = re.sub(r'\n[\s\n]+', '\n', s)
    s = s.strip() + '\n'
    for i, p in enumerate(placeholders):
        # Inside scripts/styles, also do a conservative whitespace collapse
        if p.lower().startswith('<script') or p.lower().startswith('<style'):
            inner_match = re.match(r'(<[^>]+>)([\s\S]*?)(</[^>]+>)$', p, re.IGNORECASE)
            if inner_match:
                start_tag, inner, end_tag = inner_match.groups()
                # For style: drop comments + collapse
                if p.lower().startswith('<style'):
                    inner = re.sub(r'/\*[\s\S]*?\*/', '', inner)
                    inner = re.sub(r'\s+', ' ', inner).strip()
                # For script: keep newlines, just trim per-line
                else:
                    new_lines = []
                    for ln in inner.split('\n'):
                        ln = ln.rstrip()
                        if ln.strip():
                            new_lines.append(ln.strip())
                    inner = '\n'.join(new_lines)
                p = start_tag + inner + end_tag
        s = s.replace(f'\x00H{i}\x00', p)
    return s


def main():
    # JS
    js_src_path = os.path.join(ROOT, 'blog', 'blog-shared.js')
    js_min_path = os.path.join(ROOT, 'blog', 'blog-shared.min.js')
    with open(js_src_path, 'r', encoding='utf-8') as f:
        src = f.read()
    minified = js_minify(src)
    with open(js_min_path, 'w', encoding='utf-8') as f:
        f.write(minified)
    print(f'JS: {len(src):,} → {len(minified):,} bytes ({len(minified)/len(src)*100:.1f}%) → blog/blog-shared.min.js')

    # HTML
    n_changed = 0
    total_in = total_out = 0
    for d, _, fs in os.walk(ROOT):
        if any(x in d for x in ['.git', '__pycache__', 'assets', '.github']):
            continue
        for f in fs:
            if not f.endswith('.html'):
                continue
            p = os.path.join(d, f)
            with open(p, 'r', encoding='utf-8') as fp:
                src = fp.read()
            minified = html_minify(src)
            total_in += len(src)
            total_out += len(minified)
            if len(minified) < len(src) * 0.97:
                with open(p, 'w', encoding='utf-8') as fp:
                    fp.write(minified)
                n_changed += 1
    print(f'HTML: {n_changed} files minified · total {total_in/1024:.0f} KB → {total_out/1024:.0f} KB ({total_out/total_in*100:.1f}%)')


if __name__ == '__main__':
    main()
