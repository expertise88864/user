#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit HTML for inline event handler attributes such as onclick/onload."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[\s\S]*?</\1>", re.I)
TAG_RE = re.compile(r"<[A-Za-z][^>]*>")
INLINE_EVENT_RE = re.compile(r"\son[a-z]+\s*=", re.I)


def main() -> int:
    errors: list[str] = []
    for path in sorted(ROOT.rglob("*.html")):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        raw = path.read_text(encoding="utf-8")
        dom = SCRIPT_STYLE_RE.sub("", raw)
        for match in TAG_RE.finditer(dom):
            tag = match.group(0)
            if INLINE_EVENT_RE.search(tag):
                line = raw.count("\n", 0, match.start()) + 1
                errors.append(f"{rel}:{line}: inline event handler is not CSP-friendly: {tag[:160]}")

    if errors:
        print("[FAIL] Inline event audit found issues:")
        for error in errors[:160]:
            print(" - " + error)
        if len(errors) > 160:
            print(f" ... {len(errors) - 160} more")
        return 1
    print("[OK] Inline event audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
