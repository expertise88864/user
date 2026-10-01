"""Retire the known legacy cross-document fade without changing a11y or prose.

Article navigation uses ordinary document links. Older pages opt into a fade
that is not shared by newer destinations; native browsers can skip it. The
actual Chrome journey reports that skip even with author JavaScript disabled.
Only the legacy marker's real head stylesheet is normalized, never examples,
script literals, other stylesheets or author content.
"""
from pathlib import Path

from _html_scan import _element_spans, blank_script_style, iter_tags, mask_inert_regions, tag_name

ROOT = Path(__file__).resolve().parent
MARKER = '<!-- a11y-vt-applied -->'
META = '<meta name="view-transition" content="same-origin">'
RULES = (
    '@view-transition{navigation:auto}',
    '::view-transition-old(root),::view-transition-new(root){animation-duration:.25s}',
    '@media(prefers-reduced-motion:reduce){::view-transition-old(root),::view-transition-new(root){animation:none}}',
)


def normalize(src: str) -> str:
    tags = list(iter_tags(mask_inert_regions(blank_script_style(src))))
    head = next((i for i, tag in tags if tag_name(tag) == 'head' and not tag.startswith('</')), None)
    end = next((i for i, tag in tags if tag_name(tag) == 'head' and tag.startswith('</')), None)
    if head is None or end is None or end <= head:
        return src
    result = src
    view = mask_inert_regions(src)
    for start, stop in reversed(_element_spans(view, 'script')):
        view = view[:start] + ''.join('\n' if char == '\n' else ' ' for char in view[start:stop]) + view[stop:]
    for start, stop in reversed(_element_spans(view, 'style')):
        if not head < start < stop <= end:
            continue
        prefix = MARKER + META
        begin = start - len(prefix)
        if begin < head or src[begin:start] != prefix:
            prefix = MARKER
            begin = start - len(prefix)
        if begin < head or src[begin:start] != prefix:
            continue
        style = src[start:stop]
        for rule in RULES:
            style = style.replace(rule, '')
        result = result[:begin] + MARKER + style + result[stop:]
    return result


def main() -> None:
    # Exact public source roots; do not recurse into local audit reports.
    paths = list(ROOT.glob('*.html')) + list((ROOT / 'blog').glob('*.html'))
    paths += list((ROOT / 'en').glob('*.html')) + list((ROOT / 'en' / 'blog').glob('*.html'))
    changed = 0
    for path in sorted(paths):
        source = path.read_text(encoding='utf-8')
        updated = normalize(source)
        if updated != source:
            path.write_text(updated, encoding='utf-8')
            changed += 1
    print(f'Native navigation: normalized {changed} public documents')


if __name__ == '__main__':
    main()
