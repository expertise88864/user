"""Render article navigation before paint; keep optional metadata in a disclosure."""
from __future__ import annotations

import html
import re
from pathlib import Path

from _html_scan import attributes, blank_script_style, iter_tags, mask_inert_regions, tag_name

ROOT = Path(__file__).resolve().parent
BLOCK = re.compile(r'<!-- dn-reading-shell:(?:toc|meta) -->.*?<!-- /dn-reading-shell -->', re.S)


def normalize(src: str, english: bool = False) -> str:
    src = BLOCK.sub('', src)
    tags = list(iter_tags(mask_inert_regions(blank_script_style(src))))
    article = next(((pos, tag) for pos, tag in tags
                    if tag_name(tag) == 'article' and not tag.startswith('</')), None)
    if article is None:
        return src
    start, opening = article
    end = next((pos for pos, tag in tags if pos > start and tag.lower() == '</article>'), None)
    if end is None:
        return src
    containers = {}
    for i, (pos, tag) in enumerate(tags):
        ident = attributes(tag).get('id')
        if not start < pos < end or ident not in {'proseZh', 'proseEn'}:
            continue
        depth = 1
        for close, closing in tags[i + 1:]:
            if tag_name(closing) == tag_name(tag):
                depth += -1 if closing.startswith('</') else 1
            if depth == 0:
                if src[pos + len(tag):close].strip():
                    containers[ident] = (pos + len(tag), close)
                break
    preferred = ('proseEn', 'proseZh') if english else ('proseZh',)
    prose = next((containers[key] for key in preferred if key in containers), None)
    if prose is None:
        return src
    headings = []
    for i, (pos, tag) in enumerate(tags):
        if not prose[0] <= pos < prose[1] or tag_name(tag) != 'h2' or tag.startswith('</'):
            continue
        ident = attributes(tag).get('id')
        close = next((p for p, t in tags[i + 1:] if t.lower() == '</h2>'), None)
        if not ident or close is None or close > prose[1]:
            continue
        text = src[pos + len(tag):close]
        # Strip actual tags, preserving quoted > characters and visible entities.
        for offset, child in reversed(list(iter_tags(text))):
            text = text[:offset] + text[offset + len(child):]
        headings.append((html.unescape(ident), html.unescape(text).strip()))
    edits = []
    if len(headings) >= 3:
        links = ''.join('<li><a href="#' + html.escape(ident, quote=True)
                        + '" data-toc-inline="' + html.escape(ident, quote=True) + '">'
                        + html.escape(title) + '</a></li>' for ident, title in headings)
        title = 'In this article' if english else '本篇大綱'
        toc = ('<!-- dn-reading-shell:toc --><details id="dn-inline-toc" '
               'class="dn-article-details dn-static-toc"><summary>' + title + '</summary><ol>'
               + links + '</ol></details><!-- /dn-reading-shell -->')
        insertion = start + len(opening)
        # Preserve an article-owned H1 as the first heading.
        h1_end = next((pos + len(tag) for pos, tag in tags
                       if start < pos < end and tag.lower() == '</h1>'), None)
        edits.append((h1_end or insertion, toc))
    if not any(attributes(tag).get('id') == 'dn-secondary-meta' for _, tag in tags):
        title = 'Cover and reading information' if english else '封面與閱讀資訊'
        meta = ('<!-- dn-reading-shell:meta --><section class="max-w-3xl mx-auto px-5 sm:px-8">'
                '<details id="dn-secondary-meta" class="dn-article-details"><summary>'
                + title + '</summary></details></section><!-- /dn-reading-shell -->')
        edits.append((start, meta))
    for position, block in sorted(edits, reverse=True):
        src = src[:position] + block + src[position:]
    return src


def main() -> None:
    changed = 0
    for directory in (ROOT / 'blog', ROOT / 'en' / 'blog'):
        for path in sorted(directory.glob('*.html')):
            source = path.read_text(encoding='utf-8')
            result = normalize(source, directory.parent.name == 'en')
            if source != result:
                path.write_text(result, encoding='utf-8')
                changed += 1
    print(f'Normalized reading shells in {changed} articles')


if __name__ == '__main__':
    main()
