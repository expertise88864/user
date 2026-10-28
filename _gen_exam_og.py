#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Render the /exam/** share cards (assets/og/exam/<name>.png, 1200x630).

_gen_exam.py decides which card every exam page uses and writes the card text
to data/exam/og_cards.json: one card per chapter page (「Ch.52 天疱瘡」, the
English title, 「考題 17 題 · 重點整理」), one per year paper and per other-book
page, one shared by the hub, practice and review pages and one shared by the
考點 hub and its part pages. This script draws those cards on the same
backdrop and fonts as the article cards (_gen_og_cards.py) and records what
it rendered in data/exam/og_rendered.json: the hash of the card text and of
the PNG.

USAGE
    python _gen_exam_og.py           # render only missing or out-of-date cards
    python _gen_exam_og.py --force   # re-render every card
    python _gen_exam_og.py --check   # exit 1 unless every card is present and current

Rendering needs Pillow and a CJK font (local authoring work, like the article
cards; the PNG bytes depend on the Pillow/FreeType build, so CI never
re-renders). The build runs this script without arguments: when every card is
current it does nothing and imports nothing, and when a new chapter page has
no card yet it renders one locally, or fails with this message where Pillow
is missing. --check validates without Pillow: every card named in
og_cards.json exists, is an intact 1200x630 PNG, matches the recorded hash and
was rendered from the current text, and no stray card is left behind.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPECS = ROOT / "data" / "exam" / "og_cards.json"
RECORD = ROOT / "data" / "exam" / "og_rendered.json"
OUT = ROOT / "assets" / "og" / "exam"
FIELDS = ("kicker", "title", "subtitle", "foot")
PALETTE = 64           # colours after quantizing: keeps each card ~15-25 KB
MAX_BYTES = 60_000

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def text_hash(fields: dict) -> str:
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def stale_cards(specs: dict, record: dict) -> list[str]:
    """Cards whose PNG is missing, differs from its record, or was drawn from older text."""
    out = []
    for name, fields in sorted(specs.items()):
        rec = record.get(name)
        if (not isinstance(rec, dict) or rec.get("text") != text_hash(fields)
                or rec.get("png") is None or rec.get("png") != file_hash(OUT / f"{name}.png")):
            out.append(name)
    return out


def check(specs: dict, record: dict) -> list[str]:
    from _normalize_social_images import image_size

    errors = []
    if not specs:
        errors.append("data/exam/og_cards.json is missing or empty (run python _gen_exam.py)")
    for name, fields in sorted(specs.items()):
        if not isinstance(fields, dict) or set(fields) != set(FIELDS) or not fields["title"]:
            errors.append(f"{name}: card text must have exactly {FIELDS} and a title")
    for name in stale_cards(specs, record):
        errors.append(f"assets/og/exam/{name}.png is missing or out of date (run python _gen_exam_og.py)")
    for name in sorted(set(specs) & set(record)):
        path = OUT / f"{name}.png"
        if not path.is_file():
            continue
        size = image_size(path)
        if size != (1200, 630):
            errors.append(f"assets/og/exam/{name}.png is {size or 'not an intact image'}, not 1200x630")
        if path.stat().st_size > MAX_BYTES:
            errors.append(f"assets/og/exam/{name}.png is {path.stat().st_size} bytes (limit {MAX_BYTES})")
    for extra in sorted(set(record) - set(specs)):
        errors.append(f"og_rendered.json records {extra}, which no exam page uses")
    if OUT.is_dir():
        for path in sorted(OUT.iterdir()):
            if path.suffix != ".png" or path.stem not in specs:
                errors.append(f"assets/og/exam/{path.name} is not a card any exam page uses")
    return errors


def render(fields: dict, plate):
    """One card: kicker pill, title, English subtitle and foot line on the article
    cards' backdrop (the brand block comes with the plate)."""
    from PIL import Image, ImageDraw

    import _gen_og_cards as og

    im = plate.copy()
    d = ImageDraw.Draw(im)
    pill = og.load_font(og.PILL_TEXT_SIZE, "Regular")
    w = pill.getlength(fields["kicker"])
    d.rounded_rectangle((og.MARGIN_X, og.PILL_TOP, og.MARGIN_X + w + og.PILL_PAD * 2, og.PILL_TOP + og.PILL_H),
                        radius=og.PILL_H // 2, outline=og.INK_BRAND, width=2)
    d.text((og.MARGIN_X + og.PILL_PAD, og.PILL_TOP + 7), fields["kicker"], font=pill, fill=og.INK_BRAND)

    width = og.CARD_W - og.MARGIN_X * 2 - 180
    # A long Chinese chapter name steps down in size before it is cut.
    for size, leading in ((og.TITLE_SIZE, og.TITLE_LEADING), (48, 64), (42, 56)):
        font = og.load_font(size, "Medium")
        lines = og.wrap_cjk(fields["title"], font, width, 2)
        if not lines[-1].endswith("…"):
            break
    y = og.TITLE_TOP
    for line in lines:
        d.text((og.MARGIN_X, y), line, font=font, fill=og.INK_TITLE)
        y += leading
    if fields["subtitle"]:
        sub = og.load_font(28, "Regular")
        for line in og.wrap_cjk(fields["subtitle"], sub, width, 2 if len(lines) == 1 else 1):
            d.text((og.MARGIN_X, y + 6), line, font=sub, fill=og.INK_MUTED)
            y += 40
    if fields["foot"]:
        foot = og.load_font(24, "Medium")
        d.text((og.MARGIN_X, og.DATE_TOP), fields["foot"], font=foot, fill=og.INK_BRAND)
    return im.quantize(colors=PALETTE, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="validate only; render nothing")
    ap.add_argument("--force", action="store_true", help="re-render every card")
    args = ap.parse_args(argv)
    specs = load_json(SPECS)
    record = load_json(RECORD)
    if args.check:
        errors = check(specs, record)
        for error in errors[:30]:
            print(f"[FAIL] {error}")
        if errors:
            return 1
        print(f"[OK] {len(specs)} exam share cards present, intact and rendered from the current text")
        return 0
    todo = sorted(specs) if args.force else stale_cards(specs, record)
    stray = [p for p in OUT.glob("*.png") if p.stem not in specs] if OUT.is_dir() else []
    for path in stray:
        path.unlink()
    record = {k: v for k, v in record.items() if k in specs}
    if not todo:
        if stray:
            RECORD.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"[OK] {len(specs)} exam share cards current" + (f"; removed {len(stray)} unused" if stray else ""))
        return 0
    try:
        import PIL  # noqa: F401
    except ImportError:
        print(f"[FAIL] {len(todo)} exam share card(s) need rendering ({', '.join(todo[:5])}) and Pillow is "
              "not installed. Run python _gen_exam_og.py locally and commit assets/og/exam/ and "
              "data/exam/og_rendered.json.")
        return 1
    import _gen_og_cards as og

    plate = og.background_plate()
    OUT.mkdir(parents=True, exist_ok=True)
    for name in todo:
        path = OUT / f"{name}.png"
        render(specs[name], plate).save(path, format="PNG", optimize=True)
        record[name] = {"text": text_hash(specs[name]), "png": file_hash(path)}
    RECORD.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"[OK] rendered {len(todo)} exam share card(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
