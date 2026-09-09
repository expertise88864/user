"""Upgrade legacy article headers and keep the editor's new-article header current.

index.html owns the shared header. Existing standard article headers remain
editable; only legacy/missing headers are migrated. Article prose is untouched.
Run before English generation so its existing locale routing also covers the nav.
"""
from pathlib import Path
import json
import re

from _inject_nav_critical import BLOCK

ROOT = Path(__file__).resolve().parent
HEADER = re.compile(r'<header\b[^>]*>.*?</header>', re.S | re.I)
NAV_VERSION = '202609100440'
NAV_SCRIPT = f'<script defer src="/assets/inline/nav-burger.js?v={NAV_VERSION}"></script>'


def canonical_header(source: str) -> str:
    matches = HEADER.findall(source)
    if len(matches) != 1 or 'class="dn-nav"' not in matches[0]:
        raise ValueError('Expected one shared navigation header in index.html')
    return matches[0]


def migrate_article(source: str, header: str) -> str:
    matches = HEADER.findall(source)
    if len(matches) > 1:
        raise ValueError('Ambiguous article headers; preserve source for manual review')
    if matches and 'class="dn-nav"' in matches[0]:
        pass
    elif matches:
        source = HEADER.sub(lambda _: header, source, count=1)
    elif re.search(r'<main\b', source):
        source = re.sub(r'(?=<main\b)', lambda _: header, source, count=1)
    else:
        raise ValueError('Article has no main content')
    if '/assets/inline/nav-burger.js' not in source:
        source = source.replace('</body>', NAV_SCRIPT + '</body>', 1)
    if 'id="dn-nav-critical"' not in source:
        source = source.replace('</head>', BLOCK + '</head>', 1)
    return source


def update_editor(source: str, header: str) -> str:
    # JSON string literals keep markup outside the article body template and
    # cannot prematurely close the surrounding executable inline script.
    values = {'navigationHeader': header, 'navigationStyles': BLOCK}
    for name, value in values.items():
        literal = json.dumps(value, ensure_ascii=False).replace('<', r'\u003c')
        pattern = rf'const {name} = .*?; // generated navigation\n'
        source, count = re.subn(pattern, lambda _: f'const {name} = {literal}; // generated navigation\n', source)
        if count != 1:
            raise ValueError(f'Missing unique editor navigation slot: {name}')
    return source


def main() -> None:
    header = canonical_header((ROOT / 'index.html').read_text(encoding='utf-8'))
    changed = 0
    for path in sorted((ROOT / 'blog').glob('*.html')):
        source = path.read_text(encoding='utf-8')
        if '<article' not in source:
            continue
        result = migrate_article(source, header)
        if result != source:
            path.write_text(result, encoding='utf-8')
            changed += 1
    editor = ROOT / 'admin.html'
    original = editor.read_text(encoding='utf-8')
    updated = update_editor(original, header)
    if updated != original:
        editor.write_text(updated, encoding='utf-8')
    # The shared controller must bypass previously cached unversioned scripts.
    # Restrict generation to published page directories, never evidence/backups.
    for folder in ['', 'blog', 'en', 'en/blog', 'admin']:
        for path in (ROOT / folder).glob('*.html'):
            source = path.read_text(encoding='utf-8')
            updated = re.sub(r'(/assets/inline/nav-burger\.js)(?:\?v=\d+)?(["\'])',
                             lambda m: m[1] + '?v=' + NAV_VERSION + m[2], source)
            if updated != source:
                path.write_text(updated, encoding='utf-8')
    print(f'[article navigation] migrated {changed} headers; editor template synchronized')


if __name__ == '__main__':
    main()
