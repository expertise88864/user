#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit HTML for inline event handler attributes such as onclick/onload."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _html_scan import attributes, blank_script_style, iter_tags  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "__pycache__"}
EVENT_NAME_RE = re.compile(r"on[a-z]+\Z", re.I)

# CODE_REVIEW TD-56 — anti-vacuity floors. The old pass line carried no count,
# so a broken glob, an over-eager skip list or a tag parser that stopped
# matching would print exactly the same "[OK]".
MIN_FILES_SCANNED = 100
MIN_TAGS_SCANNED = 5000


def event_attrs(tag: str) -> list[str]:
    return [name for name in attributes(tag) if EVENT_NAME_RE.match(name)]


def main() -> int:
    errors: list[str] = []
    scanned = 0
    tags = 0
    for path in sorted(ROOT.rglob("*.html")):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        scanned += 1
        rel = path.relative_to(ROOT).as_posix()
        # Blanked, not deleted: offsets stay valid so the reported line number
        # is the real one (the previous version counted newlines in the
        # ORIGINAL text using an offset into the STRIPPED text).
        dom = blank_script_style(path.read_text(encoding="utf-8"))
        for start, tag in iter_tags(dom):
            tags += 1
            handlers = event_attrs(tag)
            if handlers:
                line = dom.count("\n", 0, start) + 1
                errors.append(
                    f"{rel}:{line}: inline event handler "
                    f"{', '.join(handlers)} is not CSP-friendly: {tag[:160]}"
                )

    if scanned < MIN_FILES_SCANNED or tags < MIN_TAGS_SCANNED:
        errors.append(
            f"only {scanned} file(s) / {tags} tag(s) scanned "
            f"(expected >= {MIN_FILES_SCANNED} / {MIN_TAGS_SCANNED}) — discovery or tag "
            f"parsing is broken, so a pass here would mean nothing"
        )

    if errors:
        print("[FAIL] Inline event audit found issues:")
        for error in errors[:160]:
            print(" - " + error)
        if len(errors) > 160:
            print(f" ... {len(errors) - 160} more")
        return 1
    print(f"[OK] Inline event audit passed ({scanned} files, {tags} tags)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
