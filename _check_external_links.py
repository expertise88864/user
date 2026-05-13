#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit target=_blank links for reverse-tabnabbing/privacy rel tokens."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
TARGET_BLANK_A_RE = re.compile(r"<a\b[^>]*\btarget=(['\"])_blank\1[^>]*>", re.I)
REL_RE = re.compile(r"\brel=(['\"])(.*?)\1", re.I)


def main() -> int:
    errors: list[str] = []
    for pattern in ("*.html", "*.js"):
        for path in sorted(ROOT.rglob(pattern)):
            if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                continue
            rel = path.relative_to(ROOT).as_posix()
            src = path.read_text(encoding="utf-8")
            for match in TARGET_BLANK_A_RE.finditer(src):
                tag = match.group(0)
                rel_match = REL_RE.search(tag)
                tokens = set(rel_match.group(2).lower().split()) if rel_match else set()
                missing = [token for token in ("noopener", "noreferrer") if token not in tokens]
                if missing:
                    line = src.count("\n", 0, match.start()) + 1
                    errors.append(f"{rel}:{line}: target=_blank link missing {'/'.join(missing)}")

    if errors:
        print("[FAIL] External link audit found issues:")
        for error in errors[:160]:
            print(" - " + error)
        if len(errors) > 160:
            print(f" ... {len(errors) - 160} more")
        return 1
    print("[OK] External link audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
