#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared HTML scanning primitives for the gate's checkers.

CODE_REVIEW TD-56 — three checkers independently matched tags with
`<tag[^>]*>`. That stops at the FIRST `>`, and on this site 379 tags carry a
bilingual attribute whose VALUE contains one:

    <div class="disclaimer" data-zh="<strong>提醒 ·</strong> …" onclick="…">

Everything after that embedded `>` fell outside the match, so an attribute
later in the same tag was never inspected. Rather than fix the same bug three
times (and let the three copies drift), the quote-aware walk lives here.
"""
from __future__ import annotations

import re
from typing import Iterator

SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[\s\S]*?</\1>", re.I)
TAG_NAME_RE = re.compile(r"</?([A-Za-z][-\w:.]*)")
# One attribute: a name, then optionally `= value` with the value consumed
# whole. Consuming the value is the point — it is why prose inside data-zh
# cannot be mistaken for an attribute name.
ATTR_RE = re.compile(r"""\s*([^\s=/>]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s>]*))?""")


def blank_script_style(text: str) -> str:
    """Blank <script>/<style> bodies, preserving length and newlines.

    Length-preserving on purpose: callers report line numbers from offsets
    into the returned text, so deleting instead of blanking would silently
    shift every reported position.
    """
    return SCRIPT_STYLE_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def iter_tags(dom: str) -> Iterator[tuple[int, str]]:
    """Yield (start_offset, tag_text) for each element tag.

    Quote-aware: a `>` inside a quoted attribute value does not end the tag.
    """
    i, n = 0, len(dom)
    while i < n:
        ch = dom[i]
        if ch != "<" or i + 1 >= n or not (dom[i + 1].isalpha() or dom[i + 1] == "/"):
            i += 1
            continue
        start = i
        j = i + 1
        quote = ""
        while j < n:
            c = dom[j]
            if quote:
                if c == quote:
                    quote = ""
            elif c in "\"'":
                quote = c
            elif c == ">":
                break
            j += 1
        yield start, dom[start:j + 1]
        i = j + 1


def tag_name(tag: str) -> str:
    m = TAG_NAME_RE.match(tag)
    return m.group(1).lower() if m else ""


def attribute_spans(tag: str) -> dict[str, tuple[int, int, str, str]]:
    """Attribute name -> (start, end, value, quote) offsets within `tag`.

    Needed by normalizers that must REWRITE one attribute in place without
    reformatting the rest of the tag. First occurrence wins, matching how a
    browser resolves a duplicated attribute.
    """
    m = TAG_NAME_RE.match(tag)
    if not m:
        return {}
    pos = m.end()
    end = len(tag) - 1 if tag.endswith(">") else len(tag)
    out: dict[str, tuple[int, int, str, str]] = {}
    while pos < end:
        am = ATTR_RE.match(tag, pos)
        if am is None or am.end() == pos:
            pos += 1
            continue
        raw = am.group(2) or ""
        quote = ""
        value = raw
        if len(raw) >= 2 and raw[0] in "\"'" and raw[-1] == raw[0]:
            quote, value = raw[0], raw[1:-1]
        name = am.group(1).lower()
        if name not in out:
            out[name] = (am.start(1), am.end(), value, quote)
        pos = am.end()
    return out


def attributes(tag: str) -> dict[str, str]:
    """Attribute name -> unquoted value, parsed positionally.

    Parsing rather than pattern-matching the whole tag is what keeps prose in
    a bilingual value (`data-zh="寫成 onclick= 只是文字"`) from being read as an
    attribute name.
    """
    m = TAG_NAME_RE.match(tag)
    if not m:
        return {}
    pos = m.end()
    end = len(tag) - 1 if tag.endswith(">") else len(tag)
    out: dict[str, str] = {}
    while pos < end:
        am = ATTR_RE.match(tag, pos)
        if am is None or am.end() == pos:
            pos += 1
            continue
        value = am.group(2) or ""
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        out.setdefault(am.group(1).lower(), value)
        pos = am.end()
    return out
