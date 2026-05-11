# -*- coding: utf-8 -*-
"""Redraw the Hamilton-Norwood SVG cleanly — top-down view of scalp showing
progressive hair loss patterns. Simple and clinically accurate.
"""
from pathlib import Path
import re


def head_top_view(x, y, stage):
    """
    Top-down view of a scalp at stage 1-7.
    Forehead at top of circle, occiput at bottom.
    Hair color #2a1a0a (dark brown), skin/bald = #f4d6b3.
    """
    SKIN = '#f4d6b3'
    HAIR = '#2a1a0a'
    OUTLINE = '#92400e'

    cx = x + 60
    cy = y + 60
    r = 50  # head radius

    # Step 1: full scalp outline (skin color)
    scalp = f'<ellipse cx="{cx}" cy="{cy}" rx="{r}" ry="{r*0.95}" fill="{SKIN}" stroke="{OUTLINE}" stroke-width="1.4"/>'

    # Hair coverage — described as fill region(s)
    # Forehead arrow indicator
    forehead_arrow = f'<text x="{cx}" y="{y-2}" text-anchor="middle" font-size="9" fill="#94a3b8" font-family="Inter,sans-serif">↑ 前額</text>'

    # Hair patterns by stage (drawn on top of scalp ellipse)
    if stage == 1:
        # Full coverage — hair circle slightly larger than scalp
        hair = (
            f'<ellipse cx="{cx}" cy="{cy}" rx="{r}" ry="{r*0.95}" fill="{HAIR}" stroke="none"/>'
            # Slight forehead hairline (subtle curve at top)
        )
    elif stage == 2:
        # Slight temporal recession — small notches at front-left and front-right
        hair = (
            f'<path d="M {cx-r+4} {cy} '
            f'Q {cx-r+8} {cy-r*0.4} {cx-22} {cy-r*0.65} '
            f'Q {cx-10} {cy-r*0.85} {cx} {cy-r*0.9} '
            f'Q {cx+10} {cy-r*0.85} {cx+22} {cy-r*0.65} '
            f'Q {cx+r-8} {cy-r*0.4} {cx+r-4} {cy} '
            f'A {r} {r*0.95} 0 0 1 {cx-r+4} {cy} Z" fill="{HAIR}" stroke="none"/>'
        )
    elif stage == 3:
        # Clear M — bigger temporal notches
        hair = (
            f'<path d="M {cx-r+6} {cy+2} '
            f'Q {cx-r+12} {cy-r*0.2} {cx-26} {cy-r*0.45} '
            f'Q {cx-12} {cy-r*0.75} {cx} {cy-r*0.85} '
            f'Q {cx+12} {cy-r*0.75} {cx+26} {cy-r*0.45} '
            f'Q {cx+r-12} {cy-r*0.2} {cx+r-6} {cy+2} '
            f'A {r} {r*0.95} 0 0 1 {cx-r+6} {cy+2} Z" fill="{HAIR}" stroke="none"/>'
        )
    elif stage == 4:
        # M + small vertex thinning (small bald circle at top-back)
        hair = (
            f'<path d="M {cx-r+6} {cy+2} '
            f'Q {cx-r+14} {cy-r*0.1} {cx-30} {cy-r*0.35} '
            f'Q {cx-12} {cy-r*0.7} {cx-2} {cy-r*0.8} '
            f'L {cx+2} {cy-r*0.8} '
            f'Q {cx+12} {cy-r*0.7} {cx+30} {cy-r*0.35} '
            f'Q {cx+r-14} {cy-r*0.1} {cx+r-6} {cy+2} '
            f'A {r} {r*0.95} 0 0 1 {cx-r+6} {cy+2} Z" fill="{HAIR}" stroke="none"/>'
            # Vertex bald spot at top-back
            f'<ellipse cx="{cx}" cy="{cy+r*0.2}" rx="14" ry="11" fill="{SKIN}" stroke="{OUTLINE}" stroke-width="0.6" stroke-dasharray="2 2"/>'
        )
    elif stage == 5:
        # M deepens + vertex bald grows, narrowing bridge between them
        hair = (
            f'<path d="M {cx-r+8} {cy+5} '
            f'Q {cx-r+18} {cy} {cx-32} {cy-r*0.25} '
            f'Q {cx-8} {cy-r*0.55} {cx-1} {cy-r*0.65} '
            f'L {cx+1} {cy-r*0.65} '
            f'Q {cx+8} {cy-r*0.55} {cx+32} {cy-r*0.25} '
            f'Q {cx+r-18} {cy} {cx+r-8} {cy+5} '
            f'A {r} {r*0.95} 0 0 1 {cx-r+8} {cy+5} Z" fill="{HAIR}" stroke="none"/>'
            # Larger vertex bald
            f'<ellipse cx="{cx}" cy="{cy+r*0.15}" rx="22" ry="16" fill="{SKIN}" stroke="{OUTLINE}" stroke-width="0.6" stroke-dasharray="2 2"/>'
        )
    elif stage == 6:
        # M + vertex merged into single large bald area on top
        hair = (
            f'<path d="M {cx-r+8} {cy+10} '
            f'Q {cx-r+22} {cy+5} {cx-r+10} {cy-r*0.05} '
            f'A {r*0.85} {r*0.85} 0 0 0 {cx+r-10} {cy-r*0.05} '
            f'Q {cx+r-22} {cy+5} {cx+r-8} {cy+10} '
            f'A {r} {r*0.95} 0 0 1 {cx-r+8} {cy+10} Z" fill="{HAIR}" stroke="none"/>'
        )
    else:  # stage 7
        # Only horseshoe of hair around sides and back
        hair = (
            f'<path d="M {cx-r+8} {cy+18} '
            f'Q {cx-r+25} {cy+15} {cx-r+20} {cy+5} '
            f'L {cx-r+20} {cy+r*0.5} '
            f'A {r*0.7} {r*0.7} 0 0 0 {cx+r-20} {cy+r*0.5} '
            f'L {cx+r-20} {cy+5} '
            f'Q {cx+r-25} {cy+15} {cx+r-8} {cy+18} '
            f'A {r} {r*0.95} 0 0 1 {cx-r+8} {cy+18} Z" fill="{HAIR}" stroke="none"/>'
        )

    # Eyes/ears markers — placed at sides indicating "front=eyes" orientation
    eyes = f'<circle cx="{cx-r*0.45}" cy="{cy-r*0.92}" r="2.4" fill="#1e293b"/><circle cx="{cx+r*0.45}" cy="{cy-r*0.92}" r="2.4" fill="#1e293b"/>'

    # Stage label
    label = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII'][stage - 1]
    descs = ['髮際線正常', '輕微 M 型', '明顯 M 型', '頂部開始稀疏', '前髮 + 頂連通', '大範圍稀疏', '只剩兩側馬蹄狀']
    txt = (f'<text x="{cx}" y="{y+130}" text-anchor="middle" font-family="Inter,sans-serif" font-size="16" font-weight="800" fill="#0c5159">{label}</text>'
           f'<text x="{cx}" y="{y+152}" text-anchor="middle" font-family="Noto Sans TC,sans-serif" font-size="11.5" fill="#5e574e">{descs[stage-1]}</text>')

    return forehead_arrow + scalp + hair + eyes + txt


def build_svg():
    panel_w = 130
    # 4 in row 1, 3 in row 2 centered
    row1 = ''.join(head_top_view(20 + i * panel_w, 40, i + 1) for i in range(4))
    row2 = ''.join(head_top_view(85 + i * panel_w, 220, i + 5) for i in range(3))

    width = 20 + 4 * panel_w
    height = 410
    return (
        f'<figure class="dn-med-fig"><svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" aria-labelledby="norwood-svg-title">'
        f'<title id="norwood-svg-title">男性雄性禿 Hamilton-Norwood 分級（頭頂俯視圖）</title>'
        f'<rect width="{width}" height="{height}" fill="#faf7f2" rx="10"/>'
        f'<text x="{width/2}" y="22" text-anchor="middle" font-family="Noto Serif TC,Georgia,serif" font-size="18" font-weight="700" fill="#0c5159">男性雄性禿 Hamilton-Norwood 7 階分級</text>'
        f'<text x="{width/2}" y="40" text-anchor="middle" font-family="Inter,sans-serif" font-size="12" fill="#5e574e">頭頂俯視圖 — 深色為頭髮、淺色為頭皮 / 髮際後退區</text>'
        + row1 + row2 +
        f'<text x="{width/2}" y="{height-8}" text-anchor="middle" font-family="Inter,sans-serif" font-size="11" fill="#8b8378" font-style="italic">Source: Hamilton 1951 / Norwood 1975 — male AGA staging</text>'
        f'</svg><figcaption>圖：男性雄性禿 Hamilton-Norwood 7 階分級。I = 正常 → VII = 嚴重剩兩側馬蹄狀。</figcaption></figure>'
    )


def main():
    svg = build_svg()
    for fp in ['blog/hairloss-myths.html', 'en/blog/hairloss-myths.html']:
        p = Path(fp)
        if not p.exists():
            continue
        src = p.read_text(encoding='utf-8')
        # Replace existing Norwood figure
        old = re.search(
            r'<figure class="dn-med-fig"><svg viewBox="[^"]+" xmlns="[^"]+" aria-labelledby="norwood-svg-title">.*?</figcaption></figure>',
            src, re.DOTALL
        )
        if old:
            src = src[:old.start()] + svg + src[old.end():]
            p.write_text(src, encoding='utf-8')
            print(f'{fp}: redrawn Norwood SVG (top-down view, cleaner geometry)')
        else:
            print(f'{fp}: existing Norwood figure NOT FOUND')


if __name__ == '__main__':
    main()
