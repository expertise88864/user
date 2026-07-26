#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit target=_blank links for reverse-tabnabbing/privacy rel tokens."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _html_scan import attributes, iter_tags, tag_name  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "__pycache__"}
REQUIRED_REL = ("noopener", "noreferrer")

# CODE_REVIEW TD-56 — anti-vacuity floor. A reverse-tabnabbing audit that
# silently stops finding links is worse than none, so the number of
# target=_blank anchors actually inspected has to stay plausible.
MIN_BLANK_LINKS = 300


def main() -> int:
    errors: list[str] = []
    checked = 0
    for pattern in ("*.html", "*.js"):
        for path in sorted(ROOT.rglob(pattern)):
            if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                continue
            rel = path.relative_to(ROOT).as_posix()
            src = path.read_text(encoding="utf-8", errors="replace")
            # Quote-aware tag walk rather than `<a[^>]*target=..._blank[^>]*>`:
            # that pattern ends the tag at the first `>`, and 379 tags on this
            # site carry a bilingual attribute whose VALUE contains one. An
            # anchor whose data-zh precedes target=_blank would not match at
            # all — the link would go unchecked instead of being reported.
            for _start, tag in iter_tags(src):
                if tag_name(tag) != "a":
                    continue
                attrs = attributes(tag)
                if attrs.get("target", "").lower() != "_blank":
                    continue
                checked += 1
                tokens = set(attrs.get("rel", "").lower().split())
                missing = [t for t in REQUIRED_REL if t not in tokens]
                if missing:
                    line = src.count("\n", 0, _start) + 1
                    errors.append(
                        f"{rel}:{line}: target=_blank link missing {'/'.join(missing)}"
                    )

    if checked < MIN_BLANK_LINKS:
        errors.append(
            f"only {checked} target=_blank link(s) inspected (expected >= "
            f"{MIN_BLANK_LINKS}) — link discovery is broken, so a pass would mean nothing"
        )

    if errors:
        print("[FAIL] External link audit found issues:")
        for error in errors[:160]:
            print(" - " + error)
        if len(errors) > 160:
            print(f" ... {len(errors) - 160} more")
        return 1
    print(f"[OK] External link audit passed ({checked} target=_blank links carry "
          f"{'+'.join(REQUIRED_REL)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
