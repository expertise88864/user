"""One-shot color palette migration for 3 new articles.

Goal: match the warm-beige + sage-green palette used by all other DermNotes
articles. Three articles (perioral-dermatitis-guide, toenail-mechanical-disorders,
dermatologic-oral-examination) were written using a cool-mint palette from an
outdated scaffolder template; this fixes them.

Maps:
- CSS vars (:root) and any inline references to those colors
- rgba() usages for gradients and shadows
- Callout box backgrounds (.tldr/.key-points/.advanced) to warm-compatible variants
"""

import re
import pathlib

FILES = [
    'blog/perioral-dermatitis-guide.html',
    'blog/toenail-mechanical-disorders.html',
    'blog/dermatologic-oral-examination.html',
]

# Direct hex color mapping (cool-mint -> warm-sage).
HEX_MAP = {
    '#0e7c86': '#7a9285',   # --teal
    '#0c5159': '#4d6358',   # --teal-deep
    '#14b8a6': '#a4b5a8',   # --teal-bright
    '#f5fbfa': '#faf7f2',   # --bg
    '#0f172a': '#2a2620',   # --ink
    '#334155': '#5e574e',   # --ink-2
    '#64748b': '#8b8378',   # --muted
    '#d4f1ee': '#dcd9d1',   # --mint-soft
    '#d4eae6': '#dcd5c8',   # --border
    '#e5f3ef': '#ebe4d8',   # --line
    '#fbffff': '#fbf9f4',   # body gradient stop (cool white -> warm white)
    '#ecfeff': '#f5f0e6',   # key-points bg
    '#a5f3fc': '#d4c8b3',   # key-points border
}

# rgba() substring replacements.
RGBA_MAP = {
    'rgba(20,184,166,.14)': 'rgba(164,181,168,.18)',
    'rgba(20,184,166,.16)': 'rgba(164,181,168,.20)',
    'rgba(20,184,166,.6)': 'rgba(164,181,168,.6)',
    'rgba(12,81,89,.18)': 'rgba(77,99,88,.18)',
    'rgba(12,81,89,.12)': 'rgba(77,99,88,.12)',
    'rgba(12,81,89,.25)': 'rgba(77,99,88,.25)',
    'rgba(245,251,250,.92)': 'rgba(250,247,242,.92)',
}


def patch(text: str) -> str:
    for k, v in RGBA_MAP.items():
        text = text.replace(k, v)
    for k, v in HEX_MAP.items():
        text = re.sub(re.escape(k), v, text, flags=re.IGNORECASE)
    return text


def main() -> None:
    root = pathlib.Path(__file__).parent
    for rel in FILES:
        p = root / rel
        if not p.exists():
            print(f'skip (missing): {rel}')
            continue
        before = p.read_text(encoding='utf-8')
        after = patch(before)
        if before == after:
            print(f'unchanged: {rel}')
            continue
        p.write_text(after, encoding='utf-8')
        print(f'patched: {rel}')


if __name__ == '__main__':
    main()
