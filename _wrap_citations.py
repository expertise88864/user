#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Wrap inline parenthesised author-year citations in <span class="cite">…</span>
so the .cite CSS rule (smaller, muted) renders them like journal-style refs.

Matches:
    (Sabroe 2021, BJD)
    (Reynolds 2024, JAAD)
    (Werfel 2024 S3)
    (NICE NG198 2024)        — guideline-style
    (TDA 2024)               — society + year
    (JACI 2019)              — journal-only + year
    (Hill 2014)              — bare author + year
Year is restricted to 1800-2099 to avoid false positives like (Fraxel 1550).

Skips:
- Inert examples, raw text, preformatted text and SVG/MathML.
- Already-wrapped citations (idempotent).
- All attributes; only visible text nodes can receive citation markup.
"""
import re
from html.parser import HTMLParser
from pathlib import Path
from _html_scan import mask_inert_regions

ROOT = Path(__file__).resolve().parent

# Citation regex: opening (, author/society/journal, year (4 digits 1800-2099),
# optional journal name after comma, closing ).
CITE_RE = re.compile(
    r'\((?!<span)('  # negative lookahead so we don't double-wrap
    + r'[A-Z][A-Za-z]+(?:\s+(?:&|et\s+al\.?))?'      # name or org/journal
    + r'(?:\s+[A-Z]+\d*)?'                            # optional 2nd uppercase token (NG198, NEJM, S3)
    + r'\s+(?:1[89]\d\d|20[0-3]\d)'                  # year 1800-2030
    + r'(?:[，,]?\s*[A-Z][A-Za-z\s\d]+(?:\s+\d+)?)?' # optional journal/issue
    + r')\)'
)

class CitationText(HTMLParser):
    """Locate replacements without serializing or changing existing HTML."""

    BLOCKED = {'script', 'style', 'template', 'noscript', 'textarea', 'title',
               'pre', 'code', 'kbd', 'svg', 'math'}
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
            'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.line_starts = [0]
        for match in re.finditer('\n', source):
            self.line_starts.append(match.end())
        self.stack = []
        self.edits = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            classes = (dict(attrs).get('class') or '').split()
            self.stack.append((tag, tag in self.BLOCKED or 'cite' in classes))

    def handle_startendtag(self, tag, attrs):
        # A self-closing element has no text and must not suppress following copy.
        pass

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if any(blocked for _, blocked in self.stack):
            return
        line, column = self.getpos()
        start = self.line_starts[line - 1] + column
        for match in CITE_RE.finditer(data):
            assert self.source[start + match.start():start + match.end()] == match.group(0)
            self.edits.append((start + match.start(), start + match.end(),
                               f'(<span class="cite">{match.group(1)}</span>)'))

def wrap(html: str) -> tuple[str, int]:
    parser = CitationText(html)
    parser.feed(mask_inert_regions(html))
    parser.close()
    for start, stop, replacement in reversed(parser.edits):
        html = html[:start] + replacement + html[stop:]
    return html, len(parser.edits)

def main():
    total_files = 0
    total_wraps = 0
    for folder in (ROOT / 'blog', ROOT / 'en/blog'):
        for path in sorted(folder.glob('*.html')):
            src = path.read_text(encoding='utf8')
            new, count = wrap(src)
            if count:
                path.write_text(new, encoding='utf8')
                total_files += 1
                total_wraps += count
                print(f'  {path.relative_to(ROOT)}: {count} citations wrapped')
    print(f'\nTotal: {total_wraps} citations wrapped in {total_files} files')


if __name__ == '__main__':
    main()
