#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Add explicit type=button to non-submit UI buttons."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _html_scan import attributes, iter_tags, tag_name  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "__pycache__"}


def normalize(src: str) -> str:
    """Insert type="button" on every <button> that has no type attribute.

    CODE_REVIEW TD-57 — the previous implementation was
    `<button\\b(?![^>]*\\btype\\s*=)([^>]*)>`. Both the lookahead and the capture
    stop at the FIRST `>`, and on this site a `>` routinely appears INSIDE a
    quoted attribute value (379 tags carry bilingual values such as
    data-zh="<strong>提醒 ·</strong> …"). For

        <button data-zh="看 <b>這</b>" type="button" class="x">

    the lookahead never reached the real `type=`, so the normalizer inserted a
    SECOND one and emitted a duplicate-attribute tag — invalid HTML, and
    invisible to _check_button_types, which stopped at the same `>` and saw the
    injected type first. No such button exists today (measured: 0), so this is
    a latent fix; the tag shape that triggers it is common everywhere else.
    """
    out: list[str] = []
    cursor = 0
    for start, tag in iter_tags(src):
        if tag_name(tag) != "button" or tag.startswith("</"):
            continue
        if "type" in attributes(tag):
            continue
        out.append(src[cursor:start])
        out.append('<button type="button"' + tag[len("<button"):])
        cursor = start + len(tag)
    out.append(src[cursor:])
    return "".join(out)


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
