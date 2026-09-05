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
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _html_scan import attributes, blank_script_style, iter_tags, mask_comments, tag_name  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA = ROOT / "data" / "translations"
HAN = re.compile(r"[一-鿿]")
CRLF = chr(13) + chr(10)


def decoded(value: str) -> str:
    """The text a browser will actually show, entities resolved.

    CODE_REVIEW 2026-08-01 — the Han guard used to test the raw string, so
    `&#x4e2d;` sailed through: html.escape turns it into `&amp;#x4e2d;` in the
    attribute, Python's HTMLParser decodes attribute entities when
    _gen_en_pages.py reads it back, `&#x4e2d;` lands in the body, and the
    browser renders 中. Verified end to end before fixing. Unescaping repeats
    until stable so a double-encoded value cannot hide behind one round.
    """
    for _ in range(4):
        nxt = html.unescape(value)
        if nxt == value:
            break
        value = nxt
    return value


VOID = {"meta", "img", "input", "br", "hr", "link", "source", "area", "col"}

# Only these carry translatable UI copy. Deliberately a list rather than "any
# element with Chinese": the outermost-qualifying rule would otherwise climb to
# <body> and propose the page as one string.
TARGET_TAGS = {"h1", "h2", "h3", "h4", "h5", "p", "li", "td", "th",
               "strong", "em", "figcaption", "summary", "option", "caption",
               "a", "span", "button", "label"}
TARGET_CLASSES = {"gloss-def", "gloss-term", "gloss-cat", "gloss-link",
                  "gloss-en", "gloss-jump", "crumbs",
                  "tool-warn", "ans", "tool-note"}

# div and section are containers, so they qualify only when they are the
# INNERMOST block holding the Chinese — otherwise the outermost-eligible rule
# walks up to a page wrapper and offers half the document as one string.
BLOCK_TAGS = {"div", "section"}

# The language switcher labels its Chinese option "中文" — correctly, in both
# locales. Excluded by ancestor rather than by matching the string, so it holds
# if the widget is reworded, and so the same rule covers the button variant.
SKIP_ANCESTOR_CLASSES = {"lang-select", "lang-toggle"}


def eligible(tag: str, inner: str = "") -> bool:
    attrs = attributes(tag)
    if "data-en" in attrs:
        return False
    if tag_name(tag) in TARGET_TAGS:
        return True
    if TARGET_CLASSES & set((attrs.get("class") or "").split()):
        return True
    if tag_name(tag) in BLOCK_TAGS:
        # Only when the container holds Chinese in its OWN text. Requiring that
        # no descendant holds any was too strict: the glossary's closing note is
        # a <div> with its own prose plus an <a> inside, and that rule rejected
        # it, leaving the paragraph untranslated on the mirror.
        depth, pos, own = 0, 0, []
        for start, child in iter_tags(inner):
            if depth == 0:
                own.append(inner[pos:start])
            pos = start + len(child)
            name = tag_name(child)
            if name in VOID or child.rstrip().endswith("/>"):
                continue
            depth += -1 if child.startswith("</") else 1
            depth = max(depth, 0)
        if depth == 0:
            own.append(inner[pos:])
        return bool(HAN.search(html.unescape("".join(own))))
    return False


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


def uncovered(view: str, start: int, end: int) -> str:
    """The slice with already-translated descendants blanked out.

    A container whose Chinese lives entirely inside elements that already carry
    data-en needs nothing: those elements render themselves in English, and
    putting data-en on the container would replace them wholesale — anchors,
    hrefs and all.
    """
    out = list(view[start:end])
    pos = start
    for tag_start, tag in iter_tags(view[start:end]):
        tag_start += start
        if tag_start < pos or tag.startswith("</"):
            continue
        name = tag_name(tag)
        if name in VOID or tag.rstrip().endswith("/>"):
            continue
        if "data-en" not in attributes(tag):
            continue
        inner_end = find_end(view, tag_start + len(tag), name)
        if inner_end is None or inner_end > end:
            continue
        for i in range(tag_start - start, inner_end - start):
            out[i] = " "
        pos = inner_end
    return "".join(out)


def units(path: Path):
    """(open_tag_start, open_tag, inner_start, inner_end, inner_html) per unit."""
    # newline="" on the READ as well as the write. Without it, read_text does
    # universal-newline translation and the CRLF these pages use comes back as
    # LF, so writing them out rewrites every line ending in the file — a
    # whole-file diff hiding the handful of attributes actually added.
    # Path.read_text gained newline only in Python 3.13; CI runs 3.12.
    with path.open(encoding="utf-8", errors="replace", newline="") as source:
        raw = source.read()
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
        attrs = attributes(tag)
        if "data-en" in attrs:
            continue
        cheap = (name in TARGET_TAGS
                 or bool(TARGET_CLASSES & set((attrs.get("class") or "").split())))
        if not cheap and name not in BLOCK_TAGS:
            continue
        inner_start = start + len(tag)
        inner_end = find_end(view, inner_start, name)
        if inner_end is None:
            continue
        if not cheap and not eligible(tag, view[inner_start:inner_end]):
            continue
        # Units wrapping class-bearing markup are allowed, but only because
        # inject() refuses a translation that fails to reproduce those classes
        # — see classes_in() and cmd_inject. Rejecting them outright (the first
        # fix for the gloss-card incident) was too blunt: it also blocked the
        # <h1>, whose only offence is a presentational <span class="teal-text">.
        inner = raw[inner_start:inner_end]
        if not HAN.search(html.unescape(re.sub(r"<[^>]*>", "", uncovered(view, inner_start, inner_end)))):
            # Either no Chinese, or all of it sits inside descendants that are
            # already translated. The navigation lists are the second case:
            # <li> holds <a data-zh="首頁" data-en="Home">首頁</a>, and putting
            # data-en on the <li> would replace the anchor, href and all.
            continue
        out.append((start, tag, inner_start, inner_end, inner))
        covered_to = inner_end          # outermost only
    return raw, out


def classes_in(fragment: str) -> Counter:
    """Every class token in a fragment, with multiplicity.

    CODE_REVIEW 2026-08-01 — a data-en replaces its element's inner HTML
    wholesale, so a translation that drops the markup deletes it from the
    mirror. The glossary's closing note enclosed nine <div class="gloss-card">
    blocks; translating it as prose destroyed them, en/glossary.html fell from
    64 DefinedTerms to 55, and _normalize_mentions.py then dropped those terms
    from thirty-odd articles' JSON-LD — with every gate green. Comparing class
    tokens either side of the translation catches that, and unlike a blanket
    ban on class-bearing units it still allows an <h1> whose only child is a
    presentational <span class="teal-text">.
    """
    found: Counter = Counter()
    for _start, tag in iter_tags(fragment):
        if tag.startswith("</"):
            continue
        for token in (attributes(tag).get("class") or "").split():
            found[token] += 1
    return found


def store(page: str) -> Path:
    return DATA / ("ui-%s.json" % Path(page).stem)


# Preserve interactive elements even if they have no CSS class, and bind each
# functional attribute to its element (an id moved to another tag is not equal).
FUNCTIONAL_TAGS = {"a", "button", "input", "select", "option", "textarea",
                   "form", "img", "video", "audio", "source", "iframe"}
FUNCTIONAL_ATTRS = {"id", "href", "src", "srcset", "for", "name", "type",
                    "value", "action", "method", "target", "rel", "download",
                    "role", "aria-controls", "aria-labelledby", "aria-describedby"}


def link_identity(value: str) -> str:
    """Allow a translated mail subject; keep recipients and other parameters."""
    parts = urlsplit(value)
    if parts.scheme.lower() == "mailto":
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if k.lower() != "subject"]
        return urlunsplit((parts.scheme, parts.netloc, parts.path,
                           urlencode(sorted(query)), parts.fragment))
    # The EN generator also performs this same-site locale switch.
    if value == "/en" or value.startswith("/en/"):
        return value[3:] or "/"
    return value


def functional_markup(fragment: str) -> Counter:
    class Inventory(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.items: Counter = Counter()

        def handle_starttag(self, tag, attrs):
            keys = tuple(sorted(
                (key, link_identity(value or "") if key == "href" else value)
                for key, value in attrs
                if key in FUNCTIONAL_ATTRS or key.startswith("data-action")
            ))
            if tag in FUNCTIONAL_TAGS or keys:
                self.items[(tag, keys)] += 1

        handle_startendtag = handle_starttag

    parser = Inventory()
    parser.feed(fragment)
    parser.close()
    return parser.items


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
        # Entries already injected no longer turn up in the scan — they carry a
        # data-en now. Keep them anyway: this file is the record of what English
        # was written, which is what the physician reviews. Dropping them would
        # leave the translation visible only as an HTML attribute.
        for zh, en in previous.items():
            if en and zh not in seen:
                strings.append({"zh": zh, "en": en, "injected": True})
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
        bad = [s for s in done if HAN.search(decoded(s["en"]))]
        print("%-18s %d/%d translated%s"
              % (page, len(done), len(strings),
                 "  — %d still contain Chinese and will be refused" % len(bad) if bad else ""))
    return 0


def cmd_inject(pages: list[str]) -> int:
    failures = selftest()
    if failures:
        print("[FAIL] _translate_ui selftest — refusing to write:")
        for line in failures:
            print("  - " + line)
        return 1
    total_refused = 0
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
            why = refuse_reason(inner, en)
            if why:
                refused.append((why, en[:46]))
                continue
            new_tag = with_data_en(tag, en)
            edits.append((start, start + len(tag), new_tag))
        out = raw
        for s, e, new in sorted(edits, reverse=True):
            out = out[:s] + new + out[e:]
        if edits:
            path.write_text(out, encoding="utf-8", newline="")
        print("%-18s injected %d, still blank %d%s"
              % (page, len(edits), skipped_empty,
                 ", REFUSED %d" % len(refused) if refused else ""))
        for why, value in refused[:6]:
            print("      refused (%s): %s" % (why, value))
        total_refused += len(refused)
    # Empty entries may be deliberately unfinished. A filled but invalid entry
    # is an error, even when other valid entries were applied successfully.
    return 1 if total_refused else 0


def refuse_reason(zh_inner: str, en: str) -> str:
    """Why this translation must not be written, or "" if it may be.

    Both rules exist because something got through them:
      * Chinese in the English value — including entity-encoded Chinese, which
        the raw-string check missed until external review found it. Browsers
        resolve `&#x4e2d;` to 中, so the test has to look at decoded text.
      * a translation that drops class-bearing markup. data-en replaces the
        element's inner HTML wholesale, so prose offered for a container
        deletes whatever it wrapped — nine <div class="gloss-card"> blocks, in
        the incident that prompted this.
    """
    if HAN.search(decoded(en)):
        return "still Chinese"
    lost = classes_in(zh_inner) - classes_in(en)
    if lost:
        return "drops class(es) %s" % ",".join(sorted(lost))
    lost_functions = functional_markup(zh_inner) - functional_markup(en)
    if lost_functions:
        return "drops or changes functional markup: %s" % ",".join(
            sorted({tag for tag, _attrs in lost_functions}))
    return ""


def with_data_en(tag: str, en: str) -> str:
    """`tag` with a data-en attribute inserted, and nothing else touched.

    Inserted immediately before the closing '>'. An earlier version rstrip()ped
    the tag first, which consumed the space in `<p >` and the newline inside a
    multiline tag: line-ending counts changed and removing the attribute could
    no longer reconstruct the file. units() excludes void and self-closing
    tags, so tag[-1] is a plain '>'.
    """
    assert tag.endswith(">") and not tag[:-1].rstrip().endswith("/"), tag[:60]
    return tag[:-1] + ' data-en="%s"' % html.escape(en, quote=True) + ">"


def selftest() -> list[str]:
    """Fixtures for what inject() promises, run before every injection.

    They call refuse_reason() and with_data_en() — the functions inject() uses
    — rather than restating their logic. The first version of this selftest
    restated it, and passed with both fixes reverted.

    Every case below is a defect external review found in this file.
    """
    failures: list[str] = []

    def check(label, got, want):
        if got != want:
            failures.append("%s: expected %r, got %r" % (label, want, got))

    check("entity-encoded Chinese must be refused",
          refuse_reason("<p>x</p>", "&#x4e2d;&#x6587;"), "still Chinese")
    check("double-encoded Chinese must be refused",
          refuse_reason("<p>x</p>", "&amp;#x4e2d;"), "still Chinese")
    check("literal Chinese must be refused",
          refuse_reason("<p>x</p>", "still 中文"), "still Chinese")
    check("plain English must be accepted",
          refuse_reason("<p>x</p>", "plain English"), "")
    check("dropping a class-bearing child must be refused",
          refuse_reason('<span class="gloss-card">x</span>', "prose"),
          "drops class(es) gloss-card")
    check("keeping the class must be accepted",
          refuse_reason('<span class="gloss-card">x</span>',
                        '<span class="gloss-card">prose</span>'), "")

    for tag in ("<p >", "<li" + CRLF + '  class="a"' + CRLF + ">", "<td>",
                '<span  data-x="1" >'):
        rebuilt = with_data_en(tag, "EN")
        insert = ' data-en="EN"'
        if rebuilt.replace(insert, "", 1) != tag:
            failures.append(
                "data-en insertion moved other bytes in %r -> %r" % (tag, rebuilt))
    return failures


def main() -> int:
    if len(sys.argv) < 2 or (len(sys.argv) < 3 and sys.argv[1] != "selftest"):
        print(__doc__)
        return 2
    mode, pages = sys.argv[1], sys.argv[2:]
    if mode == "extract":
        return cmd_extract(pages)
    if mode == "inject":
        return cmd_inject(pages)
    if mode == "status":
        return cmd_status(pages)
    if mode == "selftest":
        failures = selftest()
        for line in failures:
            print("  - " + line)
        print("[%s] _translate_ui selftest" % ("FAIL" if failures else "OK"))
        return 1 if failures else 0
    print("[FAIL] unknown mode %r (extract | inject | status | selftest)" % mode)
    return 2


if __name__ == "__main__":
    sys.exit(main())
