# -*- coding: utf-8 -*-
"""Redraw the Hamilton-Norwood SVG — top-down view with hand-tuned
hairline profiles for each stage. This replaces all my earlier attempts
which the user said remained 圖片有誤.

Each stage defines an explicit 7-point hairline profile (left temple
→ forehead → right temple) in fractions of the head radius. The hair
region is then drawn as: hairline path + arc around the back of the
head to close. Vertex bald spots for stages IV-V are dashed circles.
"""
from pathlib import Path
import re


SKIN = '#f4dab6'
HAIR = '#1f1208'
OUTLINE = '#8b6f3d'
BALD_RING = '#a85a2a'

# Hairline profiles (left temple → forehead → right temple).
# Each (x_frac, y_frac) is relative to head center. Negative y = forehead side.
PROFILES = {
    1: [(-0.96,-0.28), (-0.78,-0.62), (-0.55,-0.85), (-0.30,-0.93), (0,-0.96), (0.30,-0.93), (0.55,-0.85), (0.78,-0.62), (0.96,-0.28)],
    2: [(-0.94,-0.10), (-0.78,-0.40), (-0.55,-0.65), (-0.30,-0.78), (0,-0.88), (0.30,-0.78), (0.55,-0.65), (0.78,-0.40), (0.94,-0.10)],
    3: [(-0.90,0.10),  (-0.78,-0.18), (-0.55,-0.40), (-0.28,-0.62), (0,-0.75), (0.28,-0.62), (0.55,-0.40), (0.78,-0.18), (0.90,0.10)],
    4: [(-0.90,0.10),  (-0.78,-0.18), (-0.50,-0.36), (-0.22,-0.55), (0,-0.66), (0.22,-0.55), (0.50,-0.36), (0.78,-0.18), (0.90,0.10)],
    5: [(-0.88,0.22),  (-0.72,-0.05), (-0.42,-0.22), (-0.18,-0.42), (0,-0.50), (0.18,-0.42), (0.42,-0.22), (0.72,-0.05), (0.88,0.22)],
    6: [(-0.80,0.40),  (-0.62,0.22),  (-0.38,0.15),  (-0.15,0.10),  (0,0.10),  (0.15,0.10),  (0.38,0.15),  (0.62,0.22),  (0.80,0.40)],
    7: [(-0.72,0.58),  (-0.55,0.48),  (-0.35,0.44),  (-0.15,0.42),  (0,0.42),  (0.15,0.42),  (0.35,0.44),  (0.55,0.48),  (0.72,0.58)],
}

LABELS = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII']
DESCS = [
    '髮際線正常',
    '輕微 M 型',
    '明顯 M 型',
    '頂部開始稀疏',
    '前髮 + 頂連通',
    '大範圍稀疏',
    '只剩兩側馬蹄狀',
]


def head_svg(stage, x, y):
    cx = x + 65
    cy = y + 62
    r = 40
    parts = []

    # Base head circle (skin)
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{SKIN}" '
        f'stroke="{OUTLINE}" stroke-width="1.6"/>'
    )

    # Build hair path: hairline from left temple → forehead → right temple,
    # then arc around the BACK of the head (sweep through bottom) to close.
    pts = PROFILES[stage]
    px0, py0 = pts[0]
    d = f'M {cx + px0*r:.1f} {cy + py0*r:.1f}'
    for px, py in pts[1:]:
        d += f' L {cx + px*r:.1f} {cy + py*r:.1f}'
    # Arc closes the shape via back-of-head (long arc if temples above center,
    # short arc if temples below center — both go clockwise visually).
    large_arc = 1 if py0 < 0 else 0
    d += f' A {r-1} {r-1} 0 {large_arc} 1 {cx + px0*r:.1f} {cy + py0*r:.1f} Z'
    parts.append(f'<path d="{d}" fill="{HAIR}"/>')

    # Vertex bald spot for stages IV and V (dashed circle drawn on top of hair)
    if stage == 4:
        parts.append(
            f'<circle cx="{cx}" cy="{cy + r*0.35}" r="{r*0.18}" '
            f'fill="{SKIN}" stroke="{BALD_RING}" stroke-width="0.9" '
            f'stroke-dasharray="2.5 2"/>'
        )
    elif stage == 5:
        parts.append(
            f'<ellipse cx="{cx}" cy="{cy + r*0.28}" rx="{r*0.32}" ry="{r*0.24}" '
            f'fill="{SKIN}" stroke="{BALD_RING}" stroke-width="0.9" '
            f'stroke-dasharray="2.5 2"/>'
        )

    # Forehead arrow indicator above head
    parts.append(
        f'<text x="{cx}" y="{y + 12}" text-anchor="middle" '
        f'font-family="Inter,sans-serif" font-size="10" fill="#94a3b8">前額 ↑</text>'
    )

    # Stage badge (rounded rect with Roman numeral)
    label = LABELS[stage - 1]
    parts.append(
        f'<rect x="{cx-16}" y="{y+114}" width="32" height="22" rx="11" fill="#0c5159"/>'
    )
    parts.append(
        f'<text x="{cx}" y="{y+130}" text-anchor="middle" '
        f'font-family="Inter,sans-serif" font-size="12" font-weight="800" fill="#fff">{label}</text>'
    )

    # Description label
    parts.append(
        f'<text x="{cx}" y="{y+150}" text-anchor="middle" '
        f'font-family="Noto Sans TC,sans-serif" font-size="11" fill="#5e574e">{DESCS[stage-1]}</text>'
    )

    return ''.join(parts)


def build_svg():
    panel_w = 130
    panel_h = 168

    row1 = ''.join(head_svg(i + 1, 20 + i * panel_w, 50) for i in range(4))
    row2 = ''.join(head_svg(i + 5, 85 + i * panel_w, 50 + panel_h) for i in range(3))

    width = 20 + 4 * panel_w
    height = 50 + 2 * panel_h + 30

    return (
        f'<figure class="dn-med-fig">'
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'aria-labelledby="norwood-svg-title">'
        f'<title id="norwood-svg-title">男性雄性禿 Hamilton-Norwood 分級（頭頂俯視）</title>'
        f'<rect width="{width}" height="{height}" fill="#faf7f2" rx="10"/>'
        f'<text x="{width/2}" y="22" text-anchor="middle" '
        f'font-family="Noto Serif TC,Georgia,serif" font-size="18" font-weight="700" '
        f'fill="#0c5159">男性雄性禿 Hamilton-Norwood 7 階分級</text>'
        f'<text x="{width/2}" y="40" text-anchor="middle" '
        f'font-family="Inter,sans-serif" font-size="12" fill="#5e574e">'
        f'頭頂俯視 — 深色為頭髮、橘色虛線圓為頂部禿斑</text>'
        + row1 + row2 +
        f'<text x="{width/2}" y="{height-8}" text-anchor="middle" '
        f'font-family="Inter,sans-serif" font-size="11" fill="#8b8378" '
        f'font-style="italic">Source: Hamilton 1951 / Norwood 1975 — male AGA staging</text>'
        f'</svg>'
        f'<figcaption>圖：男性雄性禿 Hamilton-Norwood 7 階分級。'
        f'I = 正常 → VII = 嚴重剩兩側馬蹄狀。</figcaption>'
        f'</figure>'
    )


def main():
    svg = build_svg()
    for fp in ['blog/hairloss-myths.html', 'en/blog/hairloss-myths.html']:
        p = Path(fp)
        if not p.exists():
            continue
        src = p.read_text(encoding='utf-8')
        old = re.search(
            r'<figure class="dn-med-fig"><svg viewBox="[^"]+" xmlns="[^"]+" aria-labelledby="norwood-svg-title">.*?</figcaption></figure>',
            src, re.DOTALL,
        )
        if old:
            src = src[:old.start()] + svg + src[old.end():]
            p.write_text(src, encoding='utf-8')
            print(f'{fp}: Norwood SVG redrawn (top-down, 9-point hand-tuned profiles)')
        else:
            print(f'{fp}: Norwood figure NOT FOUND')


if __name__ == '__main__':
    main()
