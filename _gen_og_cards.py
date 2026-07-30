#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Render the missing static Open Graph cards, matching the ones already shipped.

WHY THIS EXISTS
===============
28 of 57 articles pointed `og:image` at `/api/og?title=…`, and api/og.js:147
serves `Content-Type: image/svg+xml`. No major platform renders an SVG as a
share card — Facebook, X and LINE all want a raster image — so those articles
shared with no preview at all. The file's own header even says a PNG fallback
"would require a rasterization step (NOT yet implemented)", while claiming the
three platforms accept SVG. They do not.

The other 29 articles already had a hand-made 1200x630 PNG under assets/og/,
so the fix is to finish that set rather than add a rasterizer at the edge: a
committed PNG costs nothing at request time, caches like any other asset, and
is a stable URL that Google can also use for structured data.

MATCHING THE EXISTING CARDS
===========================
The background is not reconstructed from guesswork. Every shipped card carries
the identical four-band backdrop, so the plate is recovered as the per-pixel
MODE across all of them: text differs card to card and is voted away, the
backdrop is unanimous and survives. That makes a new card share the old ones'
background exactly, including the curved band edges, with no geometry to guess.

Type is Noto Sans TC — the family api/og.js already names — which is SIL OFL,
so the rendered cards carry no proprietary-font question. Positions, sizes and
colours below were measured off assets/og/acne-myths.png.

USAGE
=====
    python _gen_og_cards.py             # render only the cards that are missing
    python _gen_og_cards.py --check     # exit 1 if any article has no card
    python _gen_og_cards.py --force     # re-render everything (rebuilds the set)

This is a local authoring tool, not a gate step: the cards are committed
assets, and CI has no CJK font. _check_seo_signals asserts the coverage.
"""
from __future__ import annotations

import argparse
import collections
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BLOG = ROOT / "blog"
OG_DIR = ROOT / "assets" / "og"

sys.path.insert(0, str(ROOT))
from _html_scan import iter_tags, tag_name  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CARD_W, CARD_H = 1200, 630

# Measured off the shipped cards (assets/og/acne-myths.png).
MARGIN_X = 60
BRAND = "ChenDermatologist"
BRAND_SUB = "陳翊嘉醫師 · 皮膚科衛教筆記"
INK_BRAND = (77, 99, 88)        # also the pill stroke and the top/bottom bars
INK_MUTED = (94, 87, 78)        # subtitle and date
INK_TITLE = (42, 38, 32)

BRAND_SIZE, BRAND_TOP = 28, 55
SUB_SIZE, SUB_TOP = 21, 89
PILL_TOP, PILL_H, PILL_PAD, PILL_TEXT_SIZE = 200, 39, 18, 20
TITLE_SIZE, TITLE_TOP, TITLE_LEADING = 56, 280, 76
TITLE_MAX_LINES = 2
DATE_SIZE, DATE_TOP = 22, 534

FONT_CANDIDATES = (
    ROOT / "assets" / "fonts" / "NotoSansTC-VF.ttf",
    Path("C:/Windows/Fonts/NotoSansTC-VF.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansTC-VF.ttf"),
    Path("/System/Library/Fonts/PingFang.ttc"),
)

# A plate voted from fewer cards than this is not trustworthy: with too few
# samples a glyph can win a pixel and bake someone else's text into every
# card this tool renders from then on.
MIN_PLATE_SAMPLES = 8


def load_font(size: int, weight: str):
    from PIL import ImageFont

    for path in FONT_CANDIDATES:
        if path.exists():
            font = ImageFont.truetype(str(path), size)
            try:
                font.set_variation_by_name(weight)
            except Exception:
                pass        # static font, or no variation support — fine
            return font
    raise SystemExit(
        "[FAIL] no CJK font found. Install Noto Sans TC, or drop NotoSansTC-VF.ttf "
        "into assets/fonts/. Tried: " + ", ".join(str(p) for p in FONT_CANDIDATES)
    )


# Regions whose content differs card to card. Everything else — the bars, the
# four-band backdrop, the brand block, the document motif — is identical on
# every shipped card, so the vote below reproduces it exactly and this tool
# never redraws it. That is deliberate: not redrawing the brand line is one
# fewer thing that can drift from the cards already in production.
VARIABLE_BOXES = (
    (55, 196, 460, 244),      # tag pill
    (55, 274, 900, 412),      # title, up to two lines
    (55, 530, 300, 560),      # date
)


def _band_edges(row: list[tuple[int, int, int]]) -> list[tuple[int, tuple[int, int, int]]]:
    """(x where the colour changes, colour that starts there) for one plate row."""
    edges = [(0, row[0])]
    for x in range(1, len(row)):
        if row[x] != row[x - 1]:
            edges.append((x, row[x]))
    return edges


def _repair(plate) -> None:
    """Repaint the variable boxes with backdrop interpolated from clean rows.

    The backdrop is four vertical bands whose edges curve slowly, so an edge
    moves only a few pixels across the ~40 rows a box spans. Taking the edge
    positions from the nearest clean row above and below and interpolating
    between them rebuilds the box exactly, without having to model the curve.
    """
    px = plate.load()
    width, height = plate.size
    for x0, y0, x1, y1 in VARIABLE_BOXES:
        above = max(y0 - 6, 1)
        below = min(y1 + 6, height - 2)
        # Scan only as far right as the box reaches: past it sits the document
        # motif, whose own edges would otherwise be counted as band edges.
        limit = min(x1 + 1, width)
        top = _band_edges([px[x, above] for x in range(limit)])
        bot = _band_edges([px[x, below] for x in range(limit)])
        if len(top) != len(bot):
            # Edge count differs — a box was mis-measured and a clean row is
            # not clean. Refuse rather than smear a wrong backdrop over it.
            raise SystemExit(
                f"[FAIL] backdrop repair for box {(x0, y0, x1, y1)}: rows {above} "
                f"and {below} have {len(top)} vs {len(bot)} band edges"
            )
        span = below - above
        for y in range(y0, y1 + 1):
            t = (y - above) / span
            edges = [
                (round(tx + (bx - tx) * t), tc)
                for (tx, tc), (bx, _bc) in zip(top, bot)
            ]
            for i, (ex, colour) in enumerate(edges):
                nxt = edges[i + 1][0] if i + 1 < len(edges) else limit
                for x in range(max(ex, x0), min(nxt, x1 + 1)):
                    px[x, y] = colour


def background_plate():
    """The shipped cards' backdrop, recovered by per-pixel majority vote."""
    from PIL import Image

    paths = sorted(OG_DIR.glob("*.png"))
    if len(paths) < MIN_PLATE_SAMPLES:
        raise SystemExit(
            f"[FAIL] only {len(paths)} existing card(s); need >= {MIN_PLATE_SAMPLES} "
            f"to vote a clean background plate"
        )
    stacks = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        if im.size != (CARD_W, CARD_H):
            continue
        stacks.append(list(im.getdata()))
    if len(stacks) < MIN_PLATE_SAMPLES:
        raise SystemExit(f"[FAIL] only {len(stacks)} card(s) at {CARD_W}x{CARD_H}")

    plate = []
    for pixels in zip(*stacks):
        colour, votes = collections.Counter(pixels).most_common(1)[0]
        plate.append(colour if votes * 2 > len(pixels) else pixels[0])
    out = Image.new("RGB", (CARD_W, CARD_H))
    out.putdata(plate)
    _repair(out)
    return out


def wrap_cjk(text: str, font, max_width: int, max_lines: int) -> list[str]:
    """Greedy wrap that breaks between CJK glyphs and on spaces for Latin runs."""
    tokens: list[str] = []
    buf = ""
    for ch in text:
        if ord(ch) > 0x2E80:                       # CJK and friends: break anywhere
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
        elif ch.isspace():
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(" ")
        else:
            buf += ch
    if buf:
        tokens.append(buf)

    lines: list[str] = []
    cur = ""
    for tok in tokens:
        trial = cur + tok
        if cur and font.getlength(trial.strip()) > max_width:
            lines.append(cur.strip())
            cur = "" if tok == " " else tok
            if len(lines) == max_lines:
                break
        else:
            cur = trial
    if cur.strip() and len(lines) < max_lines:
        lines.append(cur.strip())

    consumed = sum(len(x) for x in lines)
    if consumed < len(text.replace(" ", "")) and lines:
        last = lines[-1]
        while last and font.getlength(last + "…") > max_width:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines or [text[:20]]


BLOCK_SPAN_RE = re.compile(r'<span[^>]*display\s*:\s*block', re.I)


def _headline_parts(inner: str) -> tuple[str, str]:
    """Split an <h1>'s inner HTML into headline and subtitle.

    Most articles separate the two with <br/>. about.html instead uses two
    `display:block` spans, which render on separate lines but concatenate when
    tags are stripped — the card for that page read
    "陳翊嘉 醫師Chen, Yi-Jia, M.D." with no space. Both forms are handled, and
    the subtitle is returned rather than discarded because the portrait card
    below has room to show it.
    """
    parts = re.split(r"<br\s*/?>", inner, maxsplit=1)
    if len(parts) == 2:
        return parts[0], parts[1]

    starts = [m.start() for m in BLOCK_SPAN_RE.finditer(inner)]
    if len(starts) >= 2:
        return inner[starts[0]:starts[1]], inner[starts[1]:]
    return inner, ""


def strip_tags(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


TAG_ENTRY_RE = re.compile(r"'([^']+)'\s*:\s*\[([^\]]*)\]")
HUB_CATALOG = BLOG / "blog-hub.js"

# Fallback for the articles DN.TAG_CATEGORIES does not list yet. The cards are
# Chinese-language artefacts, so an English pill would read as a defect; every
# term here is one the site already uses elsewhere (the topic-chip vocabulary
# in blog-hub.js, and the 衛教 · 迷思澄清 eyebrow on the myth articles) rather
# than a translation invented for this file.
SECTION_ZH = {
    "Treatment & Therapy": "治療",
    "Myths & Facts": "迷思澄清",
    "Research Summary": "最新研究",
    "Products & Drugs": "藥物",
}


def topic_tags() -> dict[str, str]:
    """slug -> the site's own short Chinese topic label.

    The shipped cards carry a Chinese pill (痘痘), not the English
    `article:section` (Myths & Facts), so the label is taken from the same
    DN.TAG_CATEGORIES the topic hub renders from. A compound label such as
    '痘痘 / 痘疤' is shortened to its first term, which is what the existing
    cards show.
    """
    if not HUB_CATALOG.exists():
        return {}
    src = HUB_CATALOG.read_text(encoding="utf-8", errors="replace")
    start = src.find("DN.TAG_CATEGORIES")
    if start == -1:
        return {}
    block = src[start:src.find("\n  ];", start)]
    mapping: dict[str, str] = {}
    for label, slugs in TAG_ENTRY_RE.findall(block):
        short = label.split("/")[0].strip()
        for slug in re.findall(r"'([a-z0-9-]+)'", slugs):
            mapping.setdefault(slug, short)
    return mapping


def article_fields(path: Path, tags: dict[str, str] | None = None) -> dict[str, str] | None:
    """title / tag / date for one article, read from the page itself."""
    src = path.read_text(encoding="utf-8", errors="replace")

    # CODE_REVIEW SEO-1 — this was `<h1\b([^>]*)>`, and blog/index.html carries
    # a `>` INSIDE its data-zh value, so the attribute list was cut in half and
    # the card rendered raw markup as its headline. _html_scan is the repo's
    # quote-aware walker and exists precisely so this shape is not re-derived.
    h1_open = h1_end = None
    for start, tag in iter_tags(src):
        if tag_name(tag) == "h1":
            h1_open, h1_end = tag, start + len(tag)
            break
    if h1_open is None:
        return None
    close = src.lower().find("</h1", h1_end)
    inner = src[h1_end:close if close != -1 else len(src)]

    # Most H1s are a headline and a subtitle split by <br/>. Only the headline
    # goes on the card — stripping tags without honouring the break ran the two
    # together as 異位性皮膚炎外用治療完整衛教保濕、類固醇…
    #
    # The title is the RENDERED text of that headline rather than any data-zh
    # attribute. Chinese is what the page serves by default, so the two agree
    # wherever both exist, and the rendered text is right in the cases they do
    # not: blog/index.html keeps markup inside data-zh, and blog/topics.html
    # splits 皮膚科衛教 / 主題地圖 across two spans of which only one carries
    # data-zh.
    head, tail = _headline_parts(inner)
    title = strip_tags(head).rstrip(" —–-·、,")
    subtitle = strip_tags(tail).rstrip(" —–-·、,")

    tag = (tags or {}).get(path.stem, "")
    if not tag:
        tm = re.search(r'<meta\s+property="article:section"\s+content="([^"]*)"',
                       src, re.I)
        if tm:
            section = html.unescape(tm.group(1))
            tag = SECTION_ZH.get(section, section)

    date = ""
    dm = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', src)
    if dm:
        date = dm.group(1)

    return {"title": title.strip(), "subtitle": subtitle.strip(),
            "tag": tag.strip(), "date": date}


# CODE_REVIEW TD-70 — about.html shared its 800x1199 studio portrait directly.
# Share cards are landscape: Facebook and X centre-crop to roughly 1.91:1, which
# on a portrait that tall slices a band across the chest and cuts the head off
# entirely — the one thing the picture is there for. Upscaling it is not an
# option either; 800px is the largest original, and 800->1200 is visibly soft.
#
# So the photo goes on a landscape card at its own resolution or below, beside
# the name. That keeps the face — which is the whole E-E-A-T point of an author
# page — and fixes the ratio without inventing pixels.
PORTRAIT_PAGES = {"about": ROOT / "blog" / "SUNN1327-800.jpg"}
PORTRAIT_X = 800                 # photo occupies x 800..1200
PORTRAIT_TITLE_TOP = 300
PORTRAIT_SUBTITLE_GAP = 74
SUBTITLE_SIZE = 26


def render_portrait_card(fields: dict[str, str], plate, photo_path: Path):
    from PIL import Image, ImageDraw

    im = plate.copy()
    photo = Image.open(photo_path).convert("RGB")
    box_w, box_h = CARD_W - PORTRAIT_X, CARD_H

    # Crop the source to the panel's aspect, then scale DOWN into it. Biased
    # slightly above centre so the crop keeps the head rather than the coat.
    target = box_w / box_h
    src_w, src_h = photo.size
    if src_w / src_h > target:
        crop_w = int(src_h * target)
        left = (src_w - crop_w) // 2
        photo = photo.crop((left, 0, left + crop_w, src_h))
    else:
        crop_h = int(src_w / target)
        top = int((src_h - crop_h) * 0.18)
        photo = photo.crop((0, top, src_w, top + crop_h))
    if photo.size[0] < box_w or photo.size[1] < box_h:
        raise SystemExit(
            f"[FAIL] {photo_path.name} is {photo.size[0]}x{photo.size[1]} after "
            f"cropping, smaller than the {box_w}x{box_h} panel — scaling it up "
            f"would ship a blurred portrait"
        )
    im.paste(photo.resize((box_w, box_h), Image.LANCZOS), (PORTRAIT_X, 0))

    d = ImageDraw.Draw(im)
    f_title = load_font(TITLE_SIZE, "Medium")
    f_sub = load_font(SUBTITLE_SIZE, "Regular")
    lines = wrap_cjk(fields["title"], f_title, PORTRAIT_X - MARGIN_X * 2,
                     TITLE_MAX_LINES)
    for i, line in enumerate(lines):
        d.text((MARGIN_X, PORTRAIT_TITLE_TOP + i * TITLE_LEADING), line,
               font=f_title, fill=INK_TITLE)
    if fields.get("subtitle"):
        d.text((MARGIN_X, PORTRAIT_TITLE_TOP + len(lines) * TITLE_LEADING
                + PORTRAIT_SUBTITLE_GAP - TITLE_LEADING),
               fields["subtitle"], font=f_sub, fill=INK_MUTED)
    # Redraw the top/bottom rules across the photo so the frame stays unbroken.
    bar = plate.getpixel((5, 2))
    d.rectangle((PORTRAIT_X, 0, CARD_W - 1, 5), fill=bar)
    d.rectangle((PORTRAIT_X, CARD_H - 6, CARD_W - 1, CARD_H - 1), fill=bar)
    return im


def render_card(fields: dict[str, str], plate):
    from PIL import ImageDraw

    im = plate.copy()
    d = ImageDraw.Draw(im)

    f_pill = load_font(PILL_TEXT_SIZE, "Regular")
    f_title = load_font(TITLE_SIZE, "Medium")
    f_date = load_font(DATE_SIZE, "Regular")

    # The brand block is NOT drawn here — it comes through the plate, identical
    # to the cards already in production.
    if fields["tag"]:
        w = f_pill.getlength(fields["tag"])
        d.rounded_rectangle(
            (MARGIN_X, PILL_TOP, MARGIN_X + w + PILL_PAD * 2, PILL_TOP + PILL_H),
            radius=PILL_H // 2, outline=INK_BRAND, width=2,
        )
        d.text((MARGIN_X + PILL_PAD, PILL_TOP + 7), fields["tag"],
               font=f_pill, fill=INK_BRAND)

    lines = wrap_cjk(fields["title"], f_title, CARD_W - MARGIN_X * 2 - 180,
                     TITLE_MAX_LINES)
    for i, line in enumerate(lines):
        d.text((MARGIN_X, TITLE_TOP + i * TITLE_LEADING), line,
               font=f_title, fill=INK_TITLE)

    if fields["date"]:
        d.text((MARGIN_X, DATE_TOP), fields["date"], font=f_date, fill=INK_MUTED)

    return im


# Public top-level pages that were sharing a 512x512 logo — or, in
# support.html's case, the SVG endpoint. about.html is deliberately absent: it
# shares a real portrait, which beats a generated card. The rest of the root
# (404, offline, admin, reset-sw) is not a share target.
TOP_LEVEL_PAGES = ("index", "tools", "glossary", "notes", "privacy",
                   "support", "dashboard", "about")


def card_slug(path: Path) -> str:
    """Card filename stem for a page.

    Articles keep their bare slug so the 30 cards already in production are
    untouched. Top-level pages take a `page-` prefix, because blog/index.html
    and index.html would otherwise both want index.png.
    """
    if path.parent == BLOG:
        return path.stem
    return "page-home" if path.stem == "index" else f"page-{path.stem}"


def card_targets() -> list[Path]:
    pages = list(sorted(BLOG.glob("*.html")))
    pages += [ROOT / f"{name}.html" for name in TOP_LEVEL_PAGES]
    return [p for p in pages if p.exists()]


def slugs_needing_cards(force: bool) -> list[Path]:
    # The two blog hub pages get cards too: topics.html was pointing at the SVG
    # endpoint and index.html at the 512x512 site logo, so both shared
    # without a usable preview.
    return [p for p in card_targets()
            if force or not (OG_DIR / f"{card_slug(p)}.png").exists()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report missing cards and exit 1; render nothing")
    ap.add_argument("--force", action="store_true",
                    help="re-render every article's card, not just the missing ones")
    args = ap.parse_args()

    todo = slugs_needing_cards(args.force)
    if args.check:
        missing = slugs_needing_cards(False)
        if missing:
            print(f"[FAIL] {len(missing)} article(s) have no OG card:")
            for p in missing[:20]:
                print(f"  - assets/og/{card_slug(p)}.png")
            return 1
        print(f"[OK] every article has an OG card "
              f"({len(list(OG_DIR.glob('*.png')))} cards)")
        return 0

    if not todo:
        print("[OK] nothing to render — every article already has a card")
        return 0

    plate = background_plate()
    tags = topic_tags()
    if not tags:
        print("[WARN] no DN.TAG_CATEGORIES parsed from blog/blog-hub.js — cards "
              "will fall back to the English article:section for the pill")
    written = 0
    skipped = []
    for path in todo:
        fields = article_fields(path, tags)
        if not fields or not fields["title"]:
            skipped.append(path.stem)
            continue
        # CODE_REVIEW TD-70 — `photo and photo.exists()` collapsed two
        # different situations into one: "this page has no portrait" and "this
        # page is CONFIGURED to have a portrait and the file is gone". The
        # second silently produced a generic text card, and every gate would
        # still pass — landscape, right size, dimensions matching — while the
        # physician's face had quietly dropped off his own author page. A
        # configured source that is missing is a failure, not a fallback.
        photo = PORTRAIT_PAGES.get(path.stem)
        if photo is not None and not photo.exists():
            raise SystemExit(
                f"[FAIL] {path.name} is configured to use the portrait "
                f"{photo.relative_to(ROOT).as_posix()}, which does not exist. "
                f"Restore it, or remove the page from PORTRAIT_PAGES if the "
                f"card is meant to be text only."
            )
        card = (render_portrait_card(fields, plate, photo) if photo
                else render_card(fields, plate))
        slug = card_slug(path)
        png = OG_DIR / f"{slug}.png"
        card.save(png, format="PNG", optimize=True)
        card.save(OG_DIR / f"{slug}.webp", format="WEBP", quality=88, method=6)
        written += 1
        print(f"  + {png.relative_to(ROOT).as_posix()}  {fields['title'][:34]}")

    print(f"[OK] rendered {written} card(s) (+ webp)")
    if skipped:
        print(f"[WARN] skipped {len(skipped)} page(s) with no usable <h1>: "
              f"{', '.join(skipped[:8])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
