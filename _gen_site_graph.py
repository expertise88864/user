#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate a force-directed SVG of the internal-link graph.

Round 2-K from OPEN_SOURCE_INTEGRATIONS.md (Python-only adaptation,
no D3 / Node dependency required).

Output: assets/dn-site-graph.svg + entry in _dashboard.md.

Each node = one published blog article. Edge = an internal /blog/<slug>
link from one article to another. Node colour reflects the cat field
(rx / myth / research / product / note). Node size scales with the
in-degree (more incoming = more visually prominent = topical hub).

Reads the catalog from DN.ARTICLES (slug + cat + tag_en) and the
edges from each article's HTML body. Idempotent.

Algorithm: simple Fruchterman-Reingold spring layout in pure Python
(~150 iterations on 45 nodes finishes in well under a second).
"""
from __future__ import annotations

import io
import math
import os
import random
import re
import sys
import xml.sax.saxutils as xml_escape
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent

# Distinct hues per category — match the site palette where possible.
CAT_COLOR = {
    "rx":       "#7a9285",   # sage green
    "myth":     "#d4a574",   # warm tan
    "research": "#4d6358",   # deep teal
    "product":  "#a4b5a8",   # light sage
    "note":     "#8b8378",   # muted brown
}
DEFAULT_COLOR = "#a4b5a8"


def parse_articles() -> list[dict]:
    src = (ROOT / "blog" / "blog-shared.js").read_text(encoding="utf-8")
    m = re.search(r"DN\.ARTICLES\s*=\s*\[([\s\S]*?)\];", src)
    if not m:
        return []
    out = []
    for em in re.finditer(r"\{[^{}]*?slug:'([a-z0-9-]+)'[^{}]*?\}", m.group(1)):
        e = em.group(0)
        if re.search(r"\bunpublished\s*:\s*true\b", e):
            continue
        out.append({
            "slug": em.group(1),
            "cat":  (re.search(r"cat:'([^']*)'", e) or [None, "note"])[1],
            "tag_en": (re.search(r"tag_en:'([^']*)'", e) or [None, ""])[1],
        })
    return out


def parse_edges(slugs: set[str]) -> list[tuple[str, str]]:
    blog = ROOT / "blog"
    edges = []
    for fp in blog.glob("*.html"):
        src_slug = fp.stem
        if src_slug not in slugs or fp.name in {"index.html", "topics.html"}:
            continue
        src = fp.read_text(encoding="utf-8", errors="replace")
        for em in re.finditer(r'href="/blog/([a-z0-9-]+)', src):
            dst = em.group(1)
            if dst in slugs and dst != src_slug:
                edges.append((src_slug, dst))
    return edges


def layout(nodes: list[str], edges: list[tuple[str, str]],
           width: float = 1200, height: float = 900,
           iterations: int = 200) -> dict[str, tuple[float, float]]:
    """Fruchterman-Reingold spring layout — pure Python, no NumPy."""
    random.seed(42)  # deterministic output
    n = len(nodes)
    if n == 0:
        return {}
    area = width * height
    k = math.sqrt(area / n)  # optimal node distance
    pos = {s: (random.uniform(0, width), random.uniform(0, height))
           for s in nodes}
    t = width / 10  # initial temperature

    edge_pairs = [(a, b) for a, b in edges if a in pos and b in pos]

    for _ in range(iterations):
        disp = {s: [0.0, 0.0] for s in nodes}
        # Repulsion between every pair
        slugs = list(pos.keys())
        for i in range(len(slugs)):
            for j in range(i + 1, len(slugs)):
                a, b = slugs[i], slugs[j]
                dx = pos[a][0] - pos[b][0]
                dy = pos[a][1] - pos[b][1]
                d = math.sqrt(dx * dx + dy * dy) or 0.01
                f = (k * k) / d
                disp[a][0] += (dx / d) * f
                disp[a][1] += (dy / d) * f
                disp[b][0] -= (dx / d) * f
                disp[b][1] -= (dy / d) * f
        # Attraction along edges
        for a, b in edge_pairs:
            dx = pos[a][0] - pos[b][0]
            dy = pos[a][1] - pos[b][1]
            d = math.sqrt(dx * dx + dy * dy) or 0.01
            f = (d * d) / k
            disp[a][0] -= (dx / d) * f
            disp[a][1] -= (dy / d) * f
            disp[b][0] += (dx / d) * f
            disp[b][1] += (dy / d) * f
        # Apply with temperature limit + keep in bounds
        for s in nodes:
            dx, dy = disp[s]
            mag = math.sqrt(dx * dx + dy * dy) or 0.01
            new_x = pos[s][0] + (dx / mag) * min(mag, t)
            new_y = pos[s][1] + (dy / mag) * min(mag, t)
            new_x = max(20, min(width - 20, new_x))
            new_y = max(20, min(height - 20, new_y))
            pos[s] = (new_x, new_y)
        t = max(t * 0.95, 1)  # cool down

    return pos


def render_svg(articles: list[dict], edges: list[tuple[str, str]],
               pos: dict[str, tuple[float, float]],
               width: float, height: float) -> str:
    # In-degree per node = visual size hint
    in_deg = {a["slug"]: 0 for a in articles}
    for _, dst in edges:
        in_deg[dst] = in_deg.get(dst, 0) + 1

    cat_by_slug = {a["slug"]: a["cat"] for a in articles}

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" '
        f'role="img" aria-label="DermNotes internal-link graph">',
        f'<rect width="100%" height="100%" fill="#faf7f2"/>',
        # Title
        f'<text x="{width/2:.0f}" y="36" text-anchor="middle" '
        f'font-family="\'Noto Serif TC\',Georgia,serif" font-size="20" '
        f'font-weight="700" fill="#2a2620">'
        f'ChenDermatologist · internal-link cluster map ({len(articles)} articles)'
        f'</text>',
    ]

    # Edges first (drawn under nodes)
    parts.append('<g stroke="#8b8378" stroke-opacity="0.30" stroke-width="0.8" fill="none">')
    for a, b in edges:
        if a in pos and b in pos:
            x1, y1 = pos[a]
            x2, y2 = pos[b]
            parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" '
                         f'x2="{x2:.1f}" y2="{y2:.1f}"/>')
    parts.append('</g>')

    # Nodes
    parts.append('<g>')
    for a in articles:
        slug = a["slug"]
        if slug not in pos:
            continue
        x, y = pos[slug]
        deg = in_deg.get(slug, 0)
        r = 4 + math.sqrt(deg) * 2.2  # node radius scales with in-degree
        color = CAT_COLOR.get(a["cat"], DEFAULT_COLOR)
        label = xml_escape.escape(slug)
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" '
            f'fill="{color}" stroke="#fff" stroke-width="1.5">'
            f'<title>{label} · in:{deg}</title></circle>'
        )
        # Label for nodes with high in-degree (cluster hubs)
        if deg >= 8:
            parts.append(
                f'<text x="{x:.1f}" y="{y - r - 4:.1f}" text-anchor="middle" '
                f'font-family="Inter,system-ui,sans-serif" font-size="9.5" '
                f'fill="#4d6358" font-weight="600">'
                f'{label[:24]}</text>'
            )
    parts.append('</g>')

    # Legend
    legend_x = width - 200
    legend_y = 60
    parts.append(f'<g transform="translate({legend_x},{legend_y})" '
                 f'font-family="Inter,system-ui,sans-serif" font-size="11" '
                 f'fill="#2a2620">')
    parts.append('<text x="0" y="0" font-weight="700">Category</text>')
    legend_items = [
        ("rx",       "Treatment & Therapy"),
        ("myth",     "Myths & Facts"),
        ("research", "Research Summary"),
        ("product",  "Products & Drugs"),
        ("note",     "Clinical Notes"),
    ]
    for i, (cat, label) in enumerate(legend_items):
        py = (i + 1) * 18
        parts.append(
            f'<circle cx="6" cy="{py}" r="6" '
            f'fill="{CAT_COLOR[cat]}" stroke="#fff" stroke-width="1.2"/>'
            f'<text x="18" y="{py + 4}">{xml_escape.escape(label)}</text>'
        )
    # Size hint
    parts.append(f'<text x="0" y="{len(legend_items) * 18 + 30}" '
                 f'font-size="10.5" fill="#5e574e" font-style="italic">'
                 f'larger circle = more incoming internal links</text>')
    parts.append('</g>')

    parts.append('</svg>')
    return "\n".join(parts)


def main() -> int:
    articles = parse_articles()
    slugs = {a["slug"] for a in articles}
    edges = parse_edges(slugs)

    pos = layout([a["slug"] for a in articles], edges)
    svg = render_svg(articles, edges, pos, width=1200, height=900)

    out = ROOT / "assets" / "dn-site-graph.svg"
    out.parent.mkdir(exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(f"[site-graph] {len(articles)} nodes · {len(edges)} edges · "
          f"wrote {out.relative_to(ROOT).as_posix()} "
          f"({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
