#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Catch unescaped `<` followed by space/digit before CI does.

GH Actions html5validator runs after we push and fails on patterns like
`< 2 cm` or `< 1%` because the validator parses `<` followed by a non-tag
character as a malformed start-tag.

This check scans all HTML files for the same pattern and fails locally,
so the dev can fix it before pushing. Runs in _run_quality.py build phase
alongside the other lint checks.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "__pycache__", "pagefind"}

# CODE_REVIEW TD-55 — what actually counts as a violation.
# HTML5 "tag open state": after `<`, anything that is not an ASCII letter, `/`,
# `!` or `?` is an invalid-first-character-of-tag-name parse error and the `<`
# is emitted as text. The old rule only looked for `< ` and `<digit`, so `<=`,
# `<%`, `<&` and friends — equally rejected by html5validator — went unseen.
# Verified: the broadened rule reports 0 violations on the current site.
TAG_START_CHARS = "/!?"


SCRIPT_BLOCK_RE = re.compile(
    r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL
)
STYLE_BLOCK_RE = re.compile(
    r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL
)
# CODE_REVIEW TD-60 — textarea and title are RCDATA: inside them a bare `<` is
# ordinary text, not a parse error, so `<textarea>目標值 < 2 cm</textarea>` is
# perfectly valid HTML. Without blanking them this audit would have failed the
# build on valid markup — and admin.html does use <textarea>.
RCDATA_BLOCK_RE = re.compile(
    r"<(textarea|title)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
)


def strip_script_style(text: str) -> str:
    """Replace `<script>`, `<style>` and RCDATA (`<textarea>`, `<title>`)
    content with blanks of equal length so line/column numbers stay accurate
    but the interior text (which may legally contain a bare `<`) isn't
    scanned."""
    def blank_keep_newlines(m: re.Match) -> str:
        s = m.group(0)
        return re.sub(r"[^\n]", " ", s)

    text = SCRIPT_BLOCK_RE.sub(blank_keep_newlines, text)
    text = STYLE_BLOCK_RE.sub(blank_keep_newlines, text)
    text = RCDATA_BLOCK_RE.sub(blank_keep_newlines, text)
    return text


def scan_text(text: str) -> list[tuple[int, int, str]]:
    """Positions of `<` a parser would treat as stray text, walking the document.

    CODE_REVIEW TD-55 — replaces a per-line quote-parity heuristic that decided
    "is this inside an attribute value?" by counting quotes from the start of
    the line. Prose apostrophes broke it: in

        <p>Bowen's disease shows lesions < 2 cm across</p>

    the apostrophe flipped the parity, so everything after it looked like it
    sat inside an attribute and the genuine `< 2` was suppressed. This repo's
    HTML is minified onto very long lines, so ONE apostrophe could blind an
    entire page — in the checker whose whole job is to pre-empt the CI
    html5validator failure.

    Quotes only delimit attribute values INSIDE a tag, so that is what is
    tracked here: whether we are between `<name` and its `>`. Comments are
    skipped whole, and the scan runs over the entire document so a tag or an
    attribute spanning several lines stays correctly understood.
    """
    issues: list[tuple[int, int, str]] = []
    i, n = 0, len(text)
    line_no, line_start = 1, 0
    in_tag = False
    quote = ""
    while i < n:
        ch = text[i]
        if ch == "\n":
            line_no += 1
            line_start = i + 1
            i += 1
            continue
        if in_tag:
            if quote:
                if ch == quote:
                    quote = ""
            elif ch in "\"'":
                quote = ch
            elif ch == ">":
                in_tag = False
            i += 1
            continue
        if ch == "<":
            if text.startswith("<!--", i):
                end = text.find("-->", i + 4)
                if end == -1:
                    break
                line_no += text.count("\n", i, end)
                i = end + 3
                continue
            nxt = text[i + 1] if i + 1 < n else ""
            # CODE_REVIEW TD-60 — ASCII only. str.isalpha() is True for CJK, so
            # on this Chinese-language site `<中文說明>` read as an opening tag:
            # the violation went unreported AND the scanner entered tag mode,
            # suppressing everything after it until the next `>`. HTML5's
            # tag-open state accepts ASCII letters only.
            if ("A" <= nxt <= "Z") or ("a" <= nxt <= "z") or nxt in TAG_START_CHARS:
                in_tag = True
                i += 1
                continue
            line_end = text.find("\n", i)
            if line_end == -1:
                line_end = n
            ctx = text[max(line_start, i - 25):min(line_end, i + 26)]
            issues.append((line_no, i - line_start + 1, ctx))
        i += 1
    return issues


def scan_file(path: Path) -> list[tuple[int, int, str]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return scan_text(strip_script_style(raw))


# CODE_REVIEW TD-55 — anti-vacuity floor, same reasoning as _check_html_balance.
MIN_FILES_SCANNED = 100


def main() -> int:
    total = 0
    err_files = 0
    scanned = 0
    for pattern in ("**/*.html",):
        for path in sorted(ROOT.glob(pattern)):
            if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                continue
            scanned += 1
            issues = scan_file(path)
            if issues:
                err_files += 1
                rel = path.relative_to(ROOT).as_posix()
                for lineno, col, ctx in issues:
                    print(f"  {rel}:{lineno}:{col}: unescaped '<' — ...{ctx}...")
                    total += 1

    if scanned < MIN_FILES_SCANNED:
        print(f"  only {scanned} HTML file(s) scanned (expected >= {MIN_FILES_SCANNED}) "
              f"— file discovery is broken, so a pass here would mean nothing")
        total += 1

    if total:
        print(f"\n[FAIL] HTML escape audit: {total} unescaped '<' in {err_files} files.")
        print("Fix: replace `< 2 cm` with `&lt; 2 cm` (same for `< 1%`, `<= 5`, `<2cm`, etc.)")
        return 1

    print(f"[OK] HTML escape audit passed "
          f"({scanned} files; no stray '<' outside a tag)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
