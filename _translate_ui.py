#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract and inject data-en for the non-article pages.

WHY THIS EXISTS ALONGSIDE _translate_pipeline.py
================================================
_translate_pipeline.py handles blog articles. It finds work with
`<tag ...>([^<]+?)</tag>`, which by construction only matches elements with no
child elements, and it reads only blog/<slug>.html.

That is fine for article prose and useless here. Measured on the two pages this
targets, the Chinese sits in elements that DO have children: 91% of it on
tools.html (li, strong, td, div.tool-warn, h3) and 77% on glossary.html
(div.gloss-def and friends). Extending the regex was not an option — the thing
it cannot do is exactly the thing needed.

So this parses with _html_scan (quote-aware, nesting-aware) and works on any
page, not just blog/.

WHAT A STRING IS
================
data-en on an element replaces that element's whole inner HTML on the /en
mirror, so the unit of translation is an element's inner HTML, markup included.
That is already the site's convention — existing values look like
`data-en="<strong>Reminder ·</strong> This article is …"`.

Elements are eligible when they are in TARGETS, contain Han, and carry no
data-en. Of those, only the OUTERMOST is emitted: putting data-en on both a
container and something inside it means the inner value can never render, since
the container's value replaces it wholesale.

USAGE
=====
    python _translate_ui.py extract tools.html glossary.html
        -> data/translations/ui-<page>.json, {"zh": "...", "en": ""}

    (fill the "en" fields — by hand, or with _ai_translate.py)

    python _translate_ui.py inject tools.html
        -> writes data-en into the page for every filled entry

    python _translate_ui.py status tools.html
        -> how much is translated, and what is left

inject is idempotent and refuses to write an entry whose "en" is empty or still
contains Han, so a half-finished file cannot ship Chinese into data-en (the
defect TD-77 was filed for).
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _html_scan import attributes, blank_script_style, iter_tags, mask_comments, tag_name  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA = ROOT / "data" / "translations"
HAN = re.compile(r"[一-鿿]")
VOID = {"meta", "img", "input", "br", "hr", "link", "source", "area", "col"}

# Only these carry translatable UI copy. Deliberately a list rather than "any
# element with Chinese": the outermost-qualifying rule would otherwise climb to
# <body> and propose the page as one string.
TARGET_TAGS = {"h1", "h2", "h3", "h4", "h5", "p", "li", "td", "th",
               "strong", "em", "figcaption", "summary", "option", "caption"}
TARGET_CLASSES = {"gloss-def", "gloss-term", "gloss-cat", "gloss-link",
                  "tool-warn", "ans", "tool-note"}

# The language switcher labels its Chinese option "中文" — correctly, in both
# locales. Excluded by ancestor rather than by matching the string, so it holds
# if the widget is reworded, and so the same rule covers the button variant.
SKIP_ANCESTOR_CLASSES = {"lang-select", "lang-toggle"}


def eligible(tag: str) -> bool:
    attrs = attributes(tag)
    if "data-en" in attrs:
        return False
    if tag_name(tag) in TARGET_TAGS:
        return True
    return bool(TARGET_CLASSES & set((attrs.get("class") or "").split()))


def find_end(src: str, open_end: int, name: str) -> int | None:
    """Index of the matching close tag's start, honouring nesting."""
    depth = 1
    pos = open_end
    for start, tag in iter_tags(src[open_end:]):
        start += open_end
        if tag_name(tag) != name:
            continue
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return start
        elif not tag.rstrip().endswith("/>") and name not in VOID:
            depth += 1
        pos = start
    return None


def units(path: Path):
    """(open_tag_start, open_tag, inner_start, inner_end, inner_html) per unit."""
    # newline="" on the READ as well as the write. Without it, read_text does
    # universal-newline translation and the CRLF these pages use comes back as
    # LF, so writing them out rewrites every line ending in the file — a
    # whole-file diff hiding the handful of attributes actually added.
    raw = path.read_text(encoding="utf-8", errors="replace", newline="")
    view = blank_script_style(mask_comments(raw))

    # Regions whose contents are never translatable, whatever they contain.
    skip_spans = []
    for start, tag in iter_tags(view):
        if tag.startswith("</") or tag_name(tag) in VOID:
            continue
        if SKIP_ANCESTOR_CLASSES & set((attributes(tag).get("class") or "").split()):
            end = find_end(view, start + len(tag), tag_name(tag))
            if end is not None:
                skip_spans.append((start, end))

    out = []
    covered_to = 0
    for start, tag in iter_tags(view):
        if start < covered_to or tag.startswith("</"):
            continue
        if any(a <= start < b for a, b in skip_spans):
            continue
        name = tag_name(tag)
        if name in VOID or tag.rstrip().endswith("/>"):
            continue
        if not eligible(tag):
            continue
        inner_start = start + len(tag)
        inner_end = find_end(view, inner_start, name)
        if inner_end is None:
            continue
        inner = raw[inner_start:inner_end]
        if not HAN.search(html.unescape(re.sub(r"<[^>]*>", "", inner))):
            continue
        out.append((start, tag, inner_start, inner_end, inner))
        covered_to = inner_end          # outermost only
    return raw, out


def store(page: str) -> Path:
    return DATA / ("ui-%s.json" % Path(page).stem)


def cmd_extract(pages: list[str]) -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    for page in pages:
        path = ROOT / page
        if not path.exists():
            print("[FAIL] no such page: %s" % page)
            return 1
        _raw, found = units(path)
        dest = store(page)
        previous = {}
        if dest.exists():
            previous = {s["zh"]: s.get("en", "")
                        for s in json.loads(dest.read_text(encoding="utf-8"))["strings"]}
        seen, strings = set(), []
        for _s, _t, _a, _b, inner in found:
            zh = inner.strip()
            if zh in seen:
                continue
            seen.add(zh)
            strings.append({"zh": zh, "en": previous.get(zh, "")})
        dest.write_text(json.dumps({"page": page, "strings": strings},
                                   ensure_ascii=False, indent=2),
                        encoding="utf-8")
        kept = sum(1 for s in strings if s["en"])
        print("%-18s %4d unique string(s) -> %s%s"
              % (page, len(strings), dest.relative_to(ROOT).as_posix(),
                 "  (%d existing translation(s) kept)" % kept if kept else ""))
    return 0


def cmd_status(pages: list[str]) -> int:
    for page in pages:
        dest = store(page)
        if not dest.exists():
            print("%-18s not extracted yet" % page)
            continue
        strings = json.loads(dest.read_text(encoding="utf-8"))["strings"]
        done = [s for s in strings if s["en"].strip()]
        bad = [s for s in done if HAN.search(s["en"])]
        print("%-18s %d/%d translated%s"
              % (page, len(done), len(strings),
                 "  — %d still contain Chinese and will be refused" % len(bad) if bad else ""))
    return 0


def cmd_inject(pages: list[str]) -> int:
    for page in pages:
        path = ROOT / page
        dest = store(page)
        if not dest.exists():
            print("[FAIL] %s: run extract first" % page)
            return 1
        table = {s["zh"]: s["en"].strip()
                 for s in json.loads(dest.read_text(encoding="utf-8"))["strings"]}
        raw, found = units(path)
        edits, skipped_empty, refused = [], 0, []
        for start, tag, _a, _b, inner in found:
            en = table.get(inner.strip(), "")
            if not en:
                skipped_empty += 1
                continue
            if HAN.search(en):
                refused.append(en[:50])
                continue
            new_tag = tag[:-1].rstrip()
            if new_tag.endswith("/"):
                new_tag = new_tag[:-1].rstrip()
            new_tag += ' data-en="%s">' % html.escape(en, quote=True)
            edits.append((start, start + len(tag), new_tag))
        out = raw
        for s, e, new in sorted(edits, reverse=True):
            out = out[:s] + new + out[e:]
        if edits:
            path.write_text(out, encoding="utf-8", newline="")
        print("%-18s injected %d, still blank %d%s"
              % (page, len(edits), skipped_empty,
                 ", REFUSED %d (English value still contains Chinese)" % len(refused)
                 if refused else ""))
        for value in refused[:5]:
            print("      refused: %s" % value)
    return 0


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    mode, pages = sys.argv[1], sys.argv[2:]
    if mode == "extract":
        return cmd_extract(pages)
    if mode == "inject":
        return cmd_inject(pages)
    if mode == "status":
        return cmd_status(pages)
    print("[FAIL] unknown mode %r (extract | inject | status)" % mode)
    return 2


if __name__ == "__main__":
    sys.exit(main())
