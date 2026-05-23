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

# Pattern: `<` followed by a space or digit, but NOT inside an attribute value.
# We do a simple line-by-line scan: ignore lines that look like tag/attr.
# The key sentinel is "< " or "<digit-not-followed-by-letter".
# Real HTML tags always have <letter or </letter or <!-- or <?
# So `<` + space + char is always an unescaped less-than sign.
PATTERN = re.compile(r"<(?= )")
# Also `<` followed directly by a digit (e.g. `<2 cm`)
PATTERN_DIGIT = re.compile(r"<(?=\d)")


SCRIPT_BLOCK_RE = re.compile(
    r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL
)
STYLE_BLOCK_RE = re.compile(
    r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL
)


def strip_script_style(text: str) -> str:
    """Replace `<script>...</script>` and `<style>...</style>` content with
    blanks of equal length so line/column numbers stay accurate but the
    interior code (which may contain legal `<` comparisons in JS / CSS
    selectors) isn't scanned."""
    def blank_keep_newlines(m: re.Match) -> str:
        s = m.group(0)
        return re.sub(r"[^\n]", " ", s)

    text = SCRIPT_BLOCK_RE.sub(blank_keep_newlines, text)
    text = STYLE_BLOCK_RE.sub(blank_keep_newlines, text)
    return text


def _inside_attribute_value(line: str, pos: int) -> bool:
    """Return True if char at `pos` is inside an HTML attribute value.

    Heuristic: walk through the line tracking quote state. A `<` inside
    `data-zh="..."`, `title="..."`, etc. is a legal text character (the
    attribute parser delimits by quotes, not by `<`). Only `<` outside
    quote-delimited attribute values can confuse html5validator.
    """
    in_dq = False
    in_sq = False
    i = 0
    while i < pos:
        ch = line[i]
        if ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "'" and not in_dq:
            in_sq = not in_sq
        i += 1
    return in_dq or in_sq


def scan_file(path: Path) -> list[tuple[int, int, str]]:
    issues = []
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = strip_script_style(raw)
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in PATTERN.finditer(line):
            if _inside_attribute_value(line, m.start()):
                continue
            col = m.start() + 1
            ctx = line[max(0, m.start() - 25): m.end() + 25]
            issues.append((lineno, col, ctx))
        for m in PATTERN_DIGIT.finditer(line):
            if _inside_attribute_value(line, m.start()):
                continue
            col = m.start() + 1
            ctx = line[max(0, m.start() - 25): m.end() + 25]
            issues.append((lineno, col, ctx))
    return issues


def main() -> int:
    total = 0
    err_files = 0
    for pattern in ("**/*.html",):
        for path in sorted(ROOT.glob(pattern)):
            if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                continue
            issues = scan_file(path)
            if issues:
                err_files += 1
                rel = path.relative_to(ROOT).as_posix()
                for lineno, col, ctx in issues:
                    print(f"  {rel}:{lineno}:{col}: unescaped '<' — ...{ctx}...")
                    total += 1

    if total:
        print(f"\n[FAIL] HTML escape audit: {total} unescaped '<' in {err_files} files.")
        print("Fix: replace `< 2 cm` with `&lt; 2 cm` (same for `< 1%`, `< 0.05`, etc.)")
        return 1

    print("[OK] HTML escape audit passed (no unescaped '<' followed by space/digit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
