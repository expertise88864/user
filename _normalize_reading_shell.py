"""Render article navigation before paint; keep optional metadata in a disclosure."""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path

from _html_scan import attribute_spans, attributes, blank_script_style, iter_tags, mask_inert_regions, tag_name

ROOT = Path(__file__).resolve().parent
BLOCK = re.compile(r'<!-- dn-reading-shell:(?:toc|meta) -->.*?<!-- /dn-reading-shell -->', re.S)


class HeadingText(HTMLParser):
    """Visible heading text, excluding inert examples and markup attributes."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.inert = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'template', 'textarea'}:
            self.inert += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'template', 'textarea'}:
            self.inert = max(0, self.inert - 1)

    def handle_data(self, text):
        if not self.inert:
            self.parts.append(text)


def heading_text(fragment: str) -> str:
    parser = HeadingText()
    parser.feed(fragment)
    return ''.join(parser.parts).strip()


def heading_slug(title: str, index: int) -> str:
    # Match existing desktop runtime fragments, including its 40-character cap.
    # Python's default \w accepts more Unicode than JavaScript's ASCII \w.
    return re.sub(r'[^a-z0-9_一-鿿]+', '-', title.lower()).strip('-')[:40] or f'h2-{index}'


def normalize(src: str, english: bool = False) -> str:
    src = BLOCK.sub('', src)
    view = mask_inert_regions(blank_script_style(src))
    tags = []
    template_depth = 0
    for pos, tag in iter_tags(view):
        if tag_name(tag) == 'template':
            template_depth += -1 if tag.startswith('</') else 1
            continue
        if template_depth == 0:
            tags.append((pos, tag))
    article = next(((pos, tag) for pos, tag in tags
                    if tag_name(tag) == 'article' and not tag.startswith('</')), None)
    if article is None:
        return src
    start, opening = article
    end = next((pos for pos, tag in tags if pos > start and tag.lower() == '</article>'), None)
    if end is None:
        return src
    containers = {}
    class_prose = []
    for i, (pos, tag) in enumerate(tags):
        attrs = attributes(tag)
        ident = attrs.get('id')
        if not start < pos < end or tag.startswith('</'):
            continue
        if ident not in {'proseZh', 'proseEn'} and 'prose' not in attrs.get('class', '').split():
            continue
        depth = 1
        for close, closing in tags[i + 1:]:
            if tag_name(closing) == tag_name(tag):
                depth += -1 if closing.startswith('</') else 1
            if depth == 0:
                if close < end and heading_text(src[pos + len(tag):close]):
                    span = (pos + len(tag), close)
                    if ident in {'proseZh', 'proseEn'}:
                        containers[ident] = span
                    else:
                        class_prose.append(span)
                break
    preferred = ('proseEn', 'proseZh') if english else ('proseZh',)
    prose = next((containers[key] for key in preferred if key in containers), None)
    if prose is None and ('prose' in attributes(opening).get('class', '').split()
                          or attributes(opening).get('id') in preferred):
        prose = (start + len(opening), end)
    if prose is None and class_prose:
        prose = class_prose[0]
    if prose is None:
        return src
    headings = []
    for i, (pos, tag) in enumerate(tags):
        if not prose[0] <= pos < prose[1] or tag_name(tag) != 'h2' or tag.startswith('</'):
            continue
        ident = html.unescape(attributes(tag).get('id', ''))
        close = next((p for p, t in tags[i + 1:] if t.lower() == '</h2>'), None)
        if close is None or close > prose[1]:
            continue
        title = heading_text(src[pos + len(tag):close])
        generated = html.unescape(attributes(tag).get('data-dn-heading-id', ''))
        headings.append((pos, tag, ident, title, generated))
    edits = []
    if len(headings) >= 3:
        regenerated = {pos for pos, _, _, _, generated in headings if english and generated}
        used = {html.unescape(attributes(tag).get('id', ''))
                for pos, tag in tags if pos not in regenerated}
        links_data = []
        for index, (pos, tag, ident, title, generated) in enumerate(headings):
            # Source-generated IDs retain their provenance when copied into an
            # English mirror. Authored IDs remain unchanged in either locale.
            if not ident or (english and generated):
                base = heading_slug(title, index)
                ident, suffix = base, 2
                while ident in used:
                    ident, suffix = f'{base}-{suffix}', suffix + 1
                used.add(ident)
                attr = 'id="' + html.escape(ident, quote=True) + '"'
                span = attribute_spans(tag).get('id')
                replacement = (tag[:span[0]] + attr + tag[span[1]:]) if span else tag[:-1] + ' ' + attr + '>'
                if not generated:
                    replacement = replacement[:-1] + ' data-dn-heading-id="' + html.escape(ident, quote=True) + '">'
                if replacement != tag:
                    edits.append((pos, pos + len(tag), replacement))
            links_data.append((ident, title or f'Section {index + 1}'))
        links = ''.join('<li><a href="#' + html.escape(ident, quote=True)
                        + '" data-toc-inline="' + html.escape(ident, quote=True) + '">'
                        + html.escape(title) + '</a></li>' for ident, title in links_data)
        title = 'In this article' if english else '本篇大綱'
        toc = ('<!-- dn-reading-shell:toc --><details id="dn-inline-toc" '
               'class="dn-article-details dn-static-toc" data-pagefind-ignore><summary>' + title + '</summary><ol>'
               + links + '</ol></details><!-- /dn-reading-shell -->')
        insertion = start + len(opening)
        # Preserve an article-owned H1 as the first heading.
        h1_end = next((pos + len(tag) for pos, tag in tags
                       if start < pos < end and tag.lower() == '</h1>'), None)
        edits.append((h1_end or insertion, h1_end or insertion, toc))
    if not any(attributes(tag).get('id') == 'dn-secondary-meta' for _, tag in tags):
        title = 'Cover and reading information' if english else '封面與閱讀資訊'
        meta = ('<!-- dn-reading-shell:meta --><section class="max-w-3xl mx-auto px-5 sm:px-8">'
                '<details id="dn-secondary-meta" class="dn-article-details"><summary>'
                + title + '</summary></details></section><!-- /dn-reading-shell -->')
        edits.append((start, start, meta))
    for position, stop, block in sorted(edits, reverse=True):
        src = src[:position] + block + src[stop:]
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
