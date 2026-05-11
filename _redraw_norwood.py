# -*- coding: utf-8 -*-
"""Redraw the Hamilton-Norwood SVG — combined SIDE + TOP view per stage
for maximum clarity. Side view shows frontal hairline; top view shows
crown thinning. Together they make each Norwood stage unambiguous.
"""
from pathlib import Path
import re


# Palette
SKIN = '#f4d6b3'
HAIR = '#2a1a0a'
THIN_HAIR = '#7c4a1a'  # transitional hair for thinning zones
OUTLINE = '#92400e'
FACE_LINE = '#a85a2a'


def side_view(cx, cy, stage):
    """Draw a left-facing profile (face on left, occiput on right).

    Frontal hairline recedes with stage; vertex bald spot grows.
    """
    # Skull outline (cranium top + back-of-head curve + nape)
    # Face: nose at left, ear roughly mid
    # Use a rounded skull shape with clear silhouette.
    r = 42
    # head shape (cranium ellipse) — slightly stretched
    skull = (
        f'<path d="M {cx-r+2} {cy+2} '
        f'C {cx-r-2} {cy-r*0.4}, {cx-r*0.6} {cy-r-4}, {cx} {cy-r-2} '  # top from front to crown
        f'C {cx+r*0.7} {cy-r-2}, {cx+r+2} {cy-r*0.5}, {cx+r+2} {cy} '  # back of head
        f'C {cx+r+2} {cy+r*0.5}, {cx+r*0.5} {cy+r*0.7}, {cx+r*0.2} {cy+r*0.65} '  # nape
        f'L {cx-r*0.2} {cy+r*0.65} '  # jaw line under
        f'C {cx-r*0.7} {cy+r*0.5}, {cx-r-2} {cy+r*0.2}, {cx-r+2} {cy+2} Z" '
        f'fill="{SKIN}" stroke="{OUTLINE}" stroke-width="1.2"/>'
    )

    # Facial features (left-facing): nose bump + eye + ear
    face = (
        # nose bump
        f'<path d="M {cx-r+2} {cy+2} '
        f'Q {cx-r-3} {cy+8} {cx-r-1} {cy+14} '
        f'Q {cx-r+4} {cy+15} {cx-r+5} {cy+10}" '
        f'fill="none" stroke="{FACE_LINE}" stroke-width="1.2" stroke-linecap="round"/>'
        # eye
        f'<circle cx="{cx-r*0.55}" cy="{cy+8}" r="1.6" fill="#1e293b"/>'
        # ear
        f'<path d="M {cx} {cy+r*0.25} q -3 4 0 9 q 3 1 4 -3" fill="none" stroke="{FACE_LINE}" stroke-width="1" stroke-linecap="round"/>'
        # mouth
        f'<path d="M {cx-r+4} {cy+22} q 4 2 8 0" fill="none" stroke="{FACE_LINE}" stroke-width="1" stroke-linecap="round"/>'
    )

    # Hair coverage drawn on top of skull. Each stage defines the front
    # hairline X (relative to cx) and whether there's vertex thinning.
    # Hair starts at "hairline" point on top-left and wraps over the crown.
    def hair_cap(front_x, vertex_bald_r=0, vertex_thin_r=0):
        """Build hair path covering top of head from front_x to back."""
        # Top cap (dense hair on top + back)
        path = (
            f'<path d="M {front_x} {cy-r*0.55} '
            f'C {front_x+4} {cy-r-1}, {cx+r*0.5} {cy-r-3}, {cx+r-2} {cy-r*0.45} '
            f'C {cx+r+1} {cy-r*0.1}, {cx+r-2} {cy+r*0.18}, {cx+r-4} {cy+r*0.28} '
            f'L {front_x+6} {cy-r*0.42} '
            f'Q {front_x-1} {cy-r*0.5} {front_x} {cy-r*0.55} Z" '
            f'fill="{HAIR}" stroke="none"/>'
        )
        # Sideburn / above-ear hair (always present until stage 7 sides only)
        sideburn = (
            f'<path d="M {cx-r*0.1} {cy-r*0.05} '
            f'Q {cx-r*0.1} {cy+r*0.25} {cx-r*0.05} {cy+r*0.35} '
            f'L {cx+r*0.05} {cy+r*0.4} '
            f'Q {cx+r*0.25} {cy+r*0.3} {cx+r*0.3} {cy+r*0.05} Z" '
            f'fill="{HAIR}" stroke="none" opacity="0.85"/>'
        )
        # Vertex bald spot (skin colored circle on top of hair)
        bald = ''
        if vertex_bald_r > 0:
            bald = (
                f'<ellipse cx="{cx+r*0.15}" cy="{cy-r*0.55}" '
                f'rx="{vertex_bald_r}" ry="{vertex_bald_r*0.75}" '
                f'fill="{SKIN}" stroke="{OUTLINE}" stroke-width="0.6" stroke-dasharray="2 2"/>'
            )
        # Vertex thinning (semi-transparent hair) — a softer effect
        thin = ''
        if vertex_thin_r > 0:
            thin = (
                f'<ellipse cx="{cx+r*0.15}" cy="{cy-r*0.55}" '
                f'rx="{vertex_thin_r}" ry="{vertex_thin_r*0.7}" '
                f'fill="{THIN_HAIR}" opacity="0.55"/>'
            )
        return path + thin + bald + sideburn

    if stage == 1:
        # Full hair, low forehead hairline
        hair = hair_cap(cx - r + 2)
    elif stage == 2:
        # Slight bitemporal recession — hairline back ~3-4 mm
        hair = hair_cap(cx - r + 6)
    elif stage == 3:
        # Deep M-shape — clearly receded temples
        hair = hair_cap(cx - r + 14)
    elif stage == 4:
        # M + small vertex thinning
        hair = hair_cap(cx - r + 18, vertex_thin_r=10)
    elif stage == 5:
        # M deepens + vertex bald growing, narrow bridge between
        hair = hair_cap(cx - r + 24, vertex_bald_r=10, vertex_thin_r=14)
    elif stage == 6:
        # M + vertex merged into large top bald area
        hair = (
            # Only back-of-head hair + sideburn
            f'<path d="M {cx+r*0.3} {cy-r*0.45} '
            f'C {cx+r*0.6} {cy-r*0.45}, {cx+r-2} {cy-r*0.4}, {cx+r+1} {cy-r*0.1} '
            f'C {cx+r-1} {cy+r*0.2}, {cx+r-4} {cy+r*0.3}, {cx+r-6} {cy+r*0.32} '
            f'L {cx+r*0.3} {cy-r*0.1} Z" fill="{HAIR}" stroke="none"/>'
            # sideburn / above-ear
            f'<path d="M {cx-r*0.05} {cy-r*0.0} '
            f'Q {cx-r*0.05} {cy+r*0.25} {cx} {cy+r*0.35} '
            f'L {cx+r*0.1} {cy+r*0.4} '
            f'Q {cx+r*0.25} {cy+r*0.3} {cx+r*0.3} {cy+r*0.05} Z" '
            f'fill="{HAIR}" stroke="none" opacity="0.85"/>'
        )
    else:  # stage 7
        # Only sideburn + back-band, very thin
        hair = (
            f'<path d="M {cx+r*0.45} {cy-r*0.25} '
            f'C {cx+r*0.7} {cy-r*0.2}, {cx+r-3} {cy-r*0.15}, {cx+r} {cy+r*0.05} '
            f'C {cx+r-2} {cy+r*0.25}, {cx+r-5} {cy+r*0.32}, {cx+r-7} {cy+r*0.33} '
            f'L {cx+r*0.45} {cy+r*0.05} Z" fill="{HAIR}" stroke="none"/>'
            f'<path d="M {cx-r*0.05} {cy+r*0.12} '
            f'Q {cx-r*0.05} {cy+r*0.3} {cx+r*0.0} {cy+r*0.38} '
            f'L {cx+r*0.15} {cy+r*0.42} '
            f'Q {cx+r*0.25} {cy+r*0.35} {cx+r*0.3} {cy+r*0.18} Z" '
            f'fill="{HAIR}" stroke="none" opacity="0.85"/>'
        )

    return skull + hair + face


def stage_panel(x, y, stage):
    """One panel with side view + stage label + description."""
    cx = x + 60
    cy = y + 55
    side = side_view(cx, cy, stage)

    label = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII'][stage - 1]
    descs = [
        '髮際線正常',
        '輕微 M 型',
        '明顯 M 型',
        '頂部開始稀疏',
        '前髮 + 頂連通',
        '大範圍稀疏',
        '只剩兩側馬蹄狀',
    ]

    # Stage badge above head
    badge = (
        f'<rect x="{cx-18}" y="{y+2}" width="36" height="20" rx="10" '
        f'fill="#0c5159"/>'
        f'<text x="{cx}" y="{y+16}" text-anchor="middle" '
        f'font-family="Inter,sans-serif" font-size="11" font-weight="800" '
        f'fill="#fff">{label}</text>'
    )

    desc = (
        f'<text x="{cx}" y="{y+130}" text-anchor="middle" '
        f'font-family="Noto Sans TC,sans-serif" font-size="11.5" '
        f'fill="#5e574e">{descs[stage-1]}</text>'
    )

    return badge + side + desc


def build_svg():
    panel_w = 130
    panel_h = 150
    cols = 4  # 4 in row 1, 3 in row 2
    row1 = ''.join(
        stage_panel(20 + i * panel_w, 50, i + 1) for i in range(4)
    )
    row2 = ''.join(
        stage_panel(85 + i * panel_w, 50 + panel_h, i + 5) for i in range(3)
    )

    width = 20 + cols * panel_w
    height = 50 + 2 * panel_h + 30
    return (
        f'<figure class="dn-med-fig">'
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'aria-labelledby="norwood-svg-title">'
        f'<title id="norwood-svg-title">男性雄性禿 Hamilton-Norwood 分級（側面剖視）</title>'
        f'<rect width="{width}" height="{height}" fill="#faf7f2" rx="10"/>'
        f'<text x="{width/2}" y="22" text-anchor="middle" '
        f'font-family="Noto Serif TC,Georgia,serif" font-size="18" font-weight="700" '
        f'fill="#0c5159">男性雄性禿 Hamilton-Norwood 7 階分級</text>'
        f'<text x="{width/2}" y="40" text-anchor="middle" '
        f'font-family="Inter,sans-serif" font-size="12" fill="#5e574e">'
        f'側面剖視 — 深色為頭髮、虛線圓為頂部禿斑</text>'
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
            src, re.DOTALL
        )
        if old:
            src = src[:old.start()] + svg + src[old.end():]
            p.write_text(src, encoding='utf-8')
            print(f'{fp}: redrawn Norwood SVG (side-view profile, clearer geometry)')
        else:
            print(f'{fp}: existing Norwood figure NOT FOUND')


if __name__ == '__main__':
    main()
