#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit buttons for explicit type attributes."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
BUTTON_OPEN_RE = re.compile(r"<button\b([^>]*)>", re.I)
CREATE_BUTTON_RE = re.compile(
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:document|[A-Za-z_$][\w$]*)\.createElement\((['\"])button\2\)",
)


def main() -> int:
    errors: list[str] = []
    for pattern in ("*.html", "*.js"):
        for path in sorted(ROOT.rglob(pattern)):
            if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                continue
            rel = path.relative_to(ROOT).as_posix()
            src = path.read_text(encoding="utf-8")
            for match in BUTTON_OPEN_RE.finditer(src):
                attrs = match.group(1)
                if not re.search(r"\btype\s*=", attrs, re.I):
                    line = src.count("\n", 0, match.start()) + 1
                    errors.append(f"{rel}:{line}: button missing explicit type")

            if path.suffix == ".js":
                lines = src.splitlines()
                for index, line in enumerate(lines):
                    created = CREATE_BUTTON_RE.search(line)
                    if not created:
                        continue
                    name = created.group(1)
                    window = "\n".join(lines[index:index + 10])
                    has_type = (
                        re.search(rf"\b{re.escape(name)}\.type\s*=", window)
                        or re.search(rf"\b{re.escape(name)}\.setAttribute\((['\"])type\1", window)
                    )
                    if not has_type:
                        errors.append(f"{rel}:{index + 1}: createElement('button') result {name} missing explicit type")

    if errors:
        print("[FAIL] Button type audit found issues:")
        for error in errors[:160]:
            print(" - " + error)
        if len(errors) > 160:
            print(f" ... {len(errors) - 160} more")
        return 1
    print("[OK] Button type audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
