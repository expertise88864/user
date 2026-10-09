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

# NOTE: there is deliberately no `<(script|style)\b…</\1>` regex here any more.
# Every private copy of it in this repo was wrong the same two ways — it does
# not close on `</script >`, and `\b` lets `<script-template>` through — so it
# was removed rather than left around to be copied again. Use
# blank_script_style(); _check_index_boundaries and _check_static_a11y now do.
TAG_NAME_RE = re.compile(r"</?([A-Za-z][-\w:.]*)")
COMMENT_END_RE = re.compile(r"--!?>")
# One attribute: a name, then optionally `= value` with the value consumed
# whole. Consuming the value is the point — it is why prose inside data-zh
# cannot be mistaken for an attribute name.
ATTR_RE = re.compile(r"""\s*([^\s=/>]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s>]*))?""")


def blank_script_style(text: str) -> str:
    """Blank real script/style elements while preserving source offsets."""
    return _mask_regions(text, {'script', 'style'})


def _element_spans(view: str, name: str) -> list[tuple[int, int]]:
    """Return whole raw-text element spans, excluding quoted examples."""
    return [(start, stop) for kind, start, _, _, stop in _raw_regions(view)
            if kind == name]


def is_ascii_alpha(ch: str) -> bool:
    """True only for A-Z / a-z.

    CODE_REVIEW TD-60 — `str.isalpha()` is True for CJK, and this is a
    Taiwanese site whose prose is mostly Chinese. `<中文說明>` would have been
    taken for an opening tag, putting the walker into tag mode and making it
    skip to the next `>` — which is the end of a REAL tag, so that tag is never
    yielded and whatever it carries goes uninspected. HTML5's tag-open state
    accepts ASCII letters only, so that is what is matched.
    """
    return ("A" <= ch <= "Z") or ("a" <= ch <= "z")


# CODE_REVIEW TD-60 — RCDATA elements. Their contents are TEXT to a parser, so
# `<button onclick="x">` typed inside a <textarea> is not a tag at all.
# Skipping their interiors matters most for the NORMALIZERS built on this walk:
# without it they would rewrite markup a user is merely looking at in the admin
# editor's textarea.
# script/style are deliberately NOT here. Their bodies are not markup either,
# but this repo's inline <script> blocks build DOM from template strings, and
# _check_button_types / _normalize_button_types are meant to reach those
# (that is also why they scan *.js at all). Skipping script here dropped the
# inspected counts from 436 buttons / 521 links to 423 / 519 — a silent
# coverage loss. Consumers that do want script bodies out of the way call
# blank_script_style() themselves, as _check_inline_events does.
RCDATA_ELEMENTS = ("textarea", "title")


def iter_tags(dom: str) -> Iterator[tuple[int, str]]:
    """Yield (start_offset, tag_text) for each element tag.

    Quote-aware: a `>` inside a quoted attribute value does not end the tag.
    RCDATA interiors are skipped — see RCDATA_ELEMENTS.
    """
    i, n = 0, len(dom)
    while i < n:
        ch = dom[i]
        if ch != "<" or i + 1 >= n or not (is_ascii_alpha(dom[i + 1]) or dom[i + 1] == "/"):
            i += 1
            continue
        start = i
        stop = _tag_stop(dom, start)
        if stop == -1:
            stop = n
        tag = dom[start:stop]
        yield start, tag
        i = stop
        name = tag_name(tag)
        if not tag.startswith("</") and not tag.rstrip().endswith("/>") and name in RCDATA_ELEMENTS:
            close = re.compile(rf"</{name}\s*>", re.I).search(dom, i)
            if close is not None:
                i = close.start()


# HTML5 "script data end tag name state": `</script` only closes the element
# when the next character is whitespace, `/` or `>`. The same characters are
# the only ones that END a tag name, so `<script` is an opening <script> tag
# under exactly the same condition.
#
# CODE_REVIEW TD-64 — the two script recognizers in this file used two
# different, both-wrong approximations of that rule: _script_spans() rejected
# only an ASCII letter, so the valid custom element `<script-template>` was
# read as a <script> whose `</script-template>` never closes it, blanking the
# rest of the document and hiding every following handler and claim from both
# callers. This is now one constant used by both.
_SCRIPT_END_FOLLOWERS = "\t\n\f\r />"


def _opens(text: str, start: int, name: str) -> bool:
    """True if `<name` at `start` really opens that element.

    CODE_REVIEW TD-64 — <style> had the same hole <script> did one round
    earlier, via `<style\\b` in a regex: `\\b` sits between `e` and `-`, so
    `<style-template>` was read as a <style> and blanked through to the next
    real `</style>`, hiding everything between from both blocking checkers.
    One rule, both elements.
    """
    after = start + 1 + len(name)
    return after >= len(text) or text[after] in _SCRIPT_END_FOLLOWERS


def _opens_script(text: str, start: int) -> bool:
    """True if `<script` at `start` is a <script> tag and not <scripture>."""
    return _opens(text, start, "script")

# Regions where a `<script>` is TEXT, not markup: HTML comments and RCDATA.
# CODE_REVIEW TD-04 — without masking these, `<textarea><script>example</textarea>`
# sitting before a real inline script made the scanner treat the inert text as an
# opening tag, consume the REAL script's closing tag, and hash a phantom body
# spanning both — leaving the real script unhashed and therefore blocked in
# production. _minify.py deliberately preserves textarea contents, and admin.html
# is built on textareas, so this is reachable. Masking is length-preserving so
# every body outside the masked region stays byte-identical.
def _mask_regions(html: str, names: set[str]) -> str:
    pieces = []
    pos = 0
    for name, start, _, _, stop in _raw_regions(html):
        if name in names:
            pieces.append(html[pos:start])
            pieces.append(re.sub(r"[^\n]", " ", html[start:stop]))
            pos = stop
    pieces.append(html[pos:])
    return ''.join(pieces)


def mask_comments(html: str) -> str:
    """Blank HTML comments, preserving quoted examples and raw script text."""
    return _mask_regions(html, {'#comment'})


def mask_inert_regions(html: str) -> str:
    """Blank HTML comments and RCDATA elements without shifting source offsets."""
    return _mask_regions(html, {'#comment', 'textarea', 'title'})


def _find_end_tag(lowered: str, start: int, name: str) -> int:
    """Index of the `</name` that really closes the element, or -1.

    CODE_REVIEW TD-04 — a plain `find("</script")` also matches the prefix of
    `</scripture>`, which is ordinary text inside a script to a browser. The
    body would then be hashed truncated while the browser hashes the whole
    thing, and the script would be silently blocked in production — with the
    checker agreeing, because it shares this scanner.
    """
    needle = "</" + name
    pos = start
    while True:
        idx = lowered.find(needle, pos)
        if idx == -1:
            return -1
        nxt = idx + len(needle)
        if nxt >= len(lowered) or lowered[nxt] in _SCRIPT_END_FOLLOWERS:
            return idx
        pos = nxt


def _find_script_end(lowered: str, start: int) -> int:
    return _find_end_tag(lowered, start, "script")


def _tag_stop(html: str, start: int) -> int:
    """Exclusive tag end, honoring quoted values rather than stray quotes."""
    if (html.startswith(('<!', '<?'), start)
            or (html.startswith('</', start)
                and (start + 2 >= len(html) or not is_ascii_alpha(html[start + 2])))):
        end = html.find('>', start + 2)
        return end + 1 if end != -1 else -1

    # In unquoted values and attribute names, quotes are ordinary characters.
    # Only a quote that starts the value after '=' protects a following '>'.
    quote = ''
    state = 'name'
    for pos in range(start + 1, len(html)):
        char = html[pos]
        if state == 'quoted':
            if char == quote:
                state = 'after_quote'
            continue
        if char == '>':
            return pos + 1
        space = char in '\t\n\f\r '
        if state == 'name':
            if space or char == '/':
                state = 'before_attribute'
        elif state in ('before_attribute', 'after_attribute', 'after_quote'):
            if space:
                continue
            if char == '/':
                state = 'before_attribute'
                continue
            if char == '=' and state == 'after_attribute':
                state = 'before_value'
            else:
                state = 'attribute'
        elif state == 'attribute':
            if space:
                state = 'after_attribute'
            elif char == '/':
                state = 'before_attribute'
            elif char == '=':
                state = 'before_value'
        elif state == 'before_value':
            if space:
                continue
            if char in "\"'":
                quote = char
                state = 'quoted'
            else:
                state = 'unquoted'
        elif state == 'unquoted' and space:
            state = 'before_attribute'
    return -1


def _raw_regions(html: str):
    """Yield comment/raw-text spans while skipping whole quoted markup tags."""
    # Unicode lower() can expand U+0130 and shift subsequent source offsets.
    lowered = html.translate(str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))
    pos = 0
    while pos < len(html):
        start = html.find('<', pos)
        if start == -1:
            return
        if html.startswith('<!--', start):
            content = start + 4
            if html.startswith('>', content):
                end, stop = content, content + 1
            elif html.startswith('->', content):
                end, stop = content, content + 2
            else:
                close = COMMENT_END_RE.search(html, content)
                end = close.start() if close else -1
                stop = close.end() if close else len(html)
            yield '#comment', start, start + 4, end, stop
            pos = stop
            continue
        if start + 1 == len(html):
            return
        if not is_ascii_alpha(html[start + 1]) and html[start + 1] not in '/!?':
            pos = start + 1
            continue
        opening_stop = _tag_stop(html, start)
        if opening_stop == -1:
            return
        tag = html[start:opening_stop]
        name = tag_name(tag)
        pos = opening_stop
        if (tag.startswith('</') or name not in ('script', 'style', 'textarea', 'title')
                or not _opens(lowered, start, name)):
            continue
        end = _find_end_tag(lowered, opening_stop, name)
        stop = _tag_stop(html, end) if end != -1 else -1
        if stop == -1:
            yield name, start, opening_stop, -1, len(html)
            return
        yield name, start, opening_stop, end, stop
        pos = stop


def iter_inline_scripts(html: str):
    """Yield attributes and exact original bodies of real inline scripts."""
    for name, start, opening_stop, end, _ in _raw_regions(html):
        if name != 'script' or end == -1:
            continue
        attrs = attributes(html[start:opening_stop])
        if 'src' not in attrs:
            yield attrs, html[opening_stop:end]


def selftest() -> list[str]:
    """Fixtures for iter_inline_scripts, run from the gate.

    CODE_REVIEW TD-04 — this scanner decides which bodies get a CSP hash, and
    the generator and the checker BOTH use it, so a regression here makes them
    agree on the wrong answer and silently blocks a script in production. There
    is no unit-test harness in this repo (TD-15), so the fixtures live here and
    _check_deployment.py runs them as part of the gate. Each case is a bug that
    was actually found and fixed, not a hypothetical.
    """
    q = chr(34)
    cases = [
        # (html, expected [(type, body)], label)
        ("<script>run()</script>", [("", "run()")], "plain"),
        ("<script src=/a.js></script><script>x()</script>", [("", "x()")],
         "external skipped"),
        ("<script data-src=" + q + "x" + q + ">run()</script>", [("", "run()")],
         "data-src is not src"),
        ("<script data-type=" + q + "application/ld+json" + q + ">run()</script>",
         [("", "run()")], "data-type is not type"),
        ("<script type=" + q + "application/ld+json" + q + ">{}</script>",
         [("application/ld+json", "{}")], "ld+json keeps its type"),
        ("<script>const x = " + q + "</scripture>" + q + ";</script>",
         [("", "const x = " + q + "</scripture>" + q + ";")],
         "</scripture> is not a close tag"),
        ("<script-template>x</script-template><script>real()</script>",
         [("", "real()")], "<script-template> is not a script"),
        ("<script2>x</script2><script>real()</script>", [("", "real()")],
         "a digit continues the tag name too"),
        ("<script>a=1</script >b<script>c=2</script>", [("", "a=1"), ("", "c=2")],
         "close tag with a space"),
        ("<textarea><script>example</textarea><script>real()</script>",
         [("", "real()")], "inert <script> inside a textarea"),
        ("<!-- <script>x</script> --><script>real()</script>", [("", "real()")],
         "inert <script> inside a comment"),
        ("<title><script>t</script></title><script>real()</script>",
         [("", "real()")], "inert <script> inside a title"),
        ('<div data-en="<script>example()</script>"></div><script>real()</script>',
         [("", "real()")], "quoted attribute examples are not scripts"),
        ('<p>\u0130</p><script>real()</script>',
         [("", "real()")], "Unicode case folding must not shift script offsets"),
        ('<style>.x{content:"<script>example()</script>"}</style><script>real()</script>',
         [("", "real()")], "script text inside CSS is not a script element"),
        ('<textarea data-x="> </textarea>"><script>example()</script></textarea>'
         '<script>real()</script>', [("", "real()")], "RCDATA opener respects quoted greater-than"),
        ("<img alt=Patient's src=/a.png><script>real()</script>",
         [("", "real()")], "quote inside an unquoted attribute is not a delimiter"),
        ("x <y it's</p><script>real()</script>",
         [("", "real()")], "stray attribute-name quote must not hide later scripts"),
        ('<!-- example --!><script>real()</script><!-- tail -->',
         [("", "real()")], "comment end bang does not hide a live script"),
        ('<!--><script>real()</script>', [("", "real()")], "abrupt comment end"),
        ('<!---><script>real()</script>', [("", "real()")], "abrupt dashed comment end"),
    ]
    failures = []
    for html, want, label in cases:
        got = [(a.get("type", ""), b) for a, b in iter_inline_scripts(html)]
        if got != want:
            failures.append(f"_html_scan selftest [{label}]: expected {want!r}, got {got!r}")

    # blank_script_style / mask_* — CODE_REVIEW TD-64. iter_inline_scripts
    # honoured the HTML5 end-tag rule while blank_script_style did not, so the
    # module gave two answers to "where does this script end". Every case below
    # is a form the old regex got wrong.
    blank_cases = [
        ("<script>keep_me()</script >after", "keep_me", False, "close tag with a space"),
        ("<script>keep_me()</script>after", "keep_me", False, "exact close tag"),
        ("<script>a=" + q + "</scripture>" + q + ";keep_me()</script>", "keep_me", False,
         "</scripture> does not end the script early"),
        ("<style>.keep_me{}</style >x", "keep_me", False, "style close tag with a space"),
        ("<scripture>keep_me</scripture>", "keep_me", True,
         "<scripture> is not a script — its text survives"),
        ("<script-template>x</script-template><p>keep_me</p>", "keep_me", True,
         "<script-template> is a custom element, not a script"),
        ("<style-template><p>keep_me</p></style-template><style>.a{}</style>",
         "keep_me", True, "<style-template> is a custom element, not a style"),
        ("<style2>keep_me</style2><style>.a{}</style>", "keep_me", True,
         "a digit continues the tag name for <style> too"),
        ("<p>keep_me</p>", "keep_me", True, "ordinary markup is untouched"),
        # CODE_REVIEW TD-64 round 5 — an inert <script> inside a comment looked
        # like a real UNCLOSED script and blanked the rest of the document, so
        # _check_inline_events stopped seeing the handlers after it.
        ("<!-- Example: <script> --> <button onclick=" + q + "keep_me()" + q + ">",
         "keep_me", True, "a <script> inside a comment must not blank the rest"),
        ("<textarea><script></textarea><button onclick=" + q + "keep_me()" + q + ">",
         "keep_me", True, "a <script> inside a textarea must not blank the rest"),
        ('<div data-en="<script>"></div><button onclick="keep_me()">Click</button>'
         '<script>real()</script>', "keep_me", True, "quoted script opener must not hide a handler"),
        ('<script data-x="before > </script>">keep_me()</script>',
         "keep_me", False, "quoted closing script text is part of the opener"),
        ("<!-- <style> --><button onclick=" + q + "keep_me()" + q + "><style>.a{}</style>",
         "keep_me", True, "a <style> inside a comment must not swallow real markup"),
    ]
    for html, needle, want_present, label in blank_cases:
        out = blank_script_style(html)
        if (needle in out) != want_present:
            failures.append(
                f"_html_scan selftest [blank_script_style: {label}]: expected "
                f"{needle!r} {'kept' if want_present else 'blanked'}, got {out!r}"
            )
        if len(out) != len(html):
            failures.append(
                f"_html_scan selftest [blank_script_style: {label}]: length changed "
                f"{len(html)} -> {len(out)}; callers report offsets into this string"
            )

    mask_cases = [
        (mask_comments, "<!--<title>x</title>--><title>keep_me</title>", "keep_me", True,
         "mask_comments leaves a real <title> readable"),
        (mask_comments, "<!-- keep_me --><p>y</p>", "keep_me", False,
         "mask_comments blanks comment text"),
        (mask_inert_regions, "<!-- keep_me --><title>keep_me</title>", "keep_me", False,
         "mask_inert_regions blanks both"),
        (mask_comments, '<div data-en="<!-- keep_me -->">Text</div>', 'keep_me', True,
         'comment example inside an attribute is not a comment'),
        (mask_inert_regions, '<script>const s="<textarea>keep_me</textarea>";</script>',
         'keep_me', True, 'script strings must not become RCDATA elements'),
    ]
    for fn, html, needle, want_present, label in mask_cases:
        out = fn(html)
        if (needle in out) != want_present:
            failures.append(
                f"_html_scan selftest [{label}]: expected {needle!r} "
                f"{'kept' if want_present else 'blanked'}, got {out!r}"
            )
        if len(out) != len(html):
            failures.append(
                f"_html_scan selftest [{label}]: length changed {len(html)} -> {len(out)}"
            )
    return failures


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
