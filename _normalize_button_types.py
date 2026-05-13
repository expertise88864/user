#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Add explicit type=button to non-submit UI buttons."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
BUTTON_OPEN_RE = re.compile(r"<button\b(?![^>]*\btype\s*=)([^>]*)>", re.I)


def normalize(src: str) -> str:
    return BUTTON_OPEN_RE.sub(lambda match: f'<button type="button"{match.group(1)}>', src)


def main() -> None:
    changed = 0
    for pattern in ("*.html", "*.js"):
        for path in sorted(ROOT.rglob(pattern)):
            if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                continue
            src = path.read_text(encoding="utf-8")
            next_src = normalize(src)
            if next_src != src:
                path.write_text(next_src, encoding="utf-8")
                changed += 1
                print("normalized button types", path.relative_to(ROOT).as_posix())
    print(f"Normalized button types in {changed} files")


if __name__ == "__main__":
    main()
