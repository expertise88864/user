#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit buttons for explicit type attributes."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _html_scan import attributes, iter_tags, tag_name  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "__pycache__"}
CREATE_BUTTON_RE = re.compile(
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:document|[A-Za-z_$][\w$]*)\.createElement\((['\"])button\2\)",
)

# CODE_REVIEW TD-57 — anti-vacuity floor: the old pass line reported nothing,
# so a tag pattern that stopped matching would look identical to a clean site.
MIN_BUTTONS_SCANNED = 200


def main() -> int:
    errors: list[str] = []
    buttons = 0
    for pattern in ("*.html", "*.js"):
        for path in sorted(ROOT.rglob(pattern)):
            if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                continue
            rel = path.relative_to(ROOT).as_posix()
            src = path.read_text(encoding="utf-8")
            # Quote-aware walk, not `<button\b([^>]*)>`: that stops at the first
            # `>`, which on this site can sit inside a bilingual attribute
            # value. It made the audit read the wrong slice of the tag — the
            # mirror image of the duplicate-type bug fixed in
            # _normalize_button_types (TD-57).
            for start, tag in iter_tags(src):
                if tag_name(tag) != "button" or tag.startswith("</"):
                    continue
                buttons += 1
                if "type" not in attributes(tag):
                    line = src.count("\n", 0, start) + 1
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

    if buttons < MIN_BUTTONS_SCANNED:
        errors.append(
            f"only {buttons} <button> tag(s) inspected (expected >= "
            f"{MIN_BUTTONS_SCANNED}) — tag discovery is broken, so a pass means nothing"
        )

    if errors:
        print("[FAIL] Button type audit found issues:")
        for error in errors[:160]:
            print(" - " + error)
        if len(errors) > 160:
            print(f" ... {len(errors) - 160} more")
        return 1
    print(f"[OK] Button type audit passed ({buttons} buttons carry an explicit type)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
