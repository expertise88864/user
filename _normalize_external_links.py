#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Harden target=_blank links with noopener+noreferrer."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
TARGET_BLANK_A_RE = re.compile(r"<a\b[^>]*\btarget=(['\"])_blank\1[^>]*>", re.I)
REL_RE = re.compile(r"\brel=(['\"])(.*?)\1", re.I)


def normalize_anchor(tag: str) -> str:
    rel_match = REL_RE.search(tag)
    required = ["noopener", "noreferrer"]
    if rel_match:
        quote = rel_match.group(1)
        tokens = rel_match.group(2).split()
        lowered = {token.lower() for token in tokens}
        for token in required:
            if token not in lowered:
                tokens.append(token)
        return tag[:rel_match.start()] + f"rel={quote}{' '.join(tokens)}{quote}" + tag[rel_match.end():]

    target_match = re.search(r"\btarget=(['\"])_blank\1", tag, re.I)
    if not target_match:
        return tag
    insert_at = target_match.end()
    return tag[:insert_at] + ' rel="noopener noreferrer"' + tag[insert_at:]


def normalize(src: str) -> str:
    return TARGET_BLANK_A_RE.sub(lambda match: normalize_anchor(match.group(0)), src)


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
                print("normalized external links", path.relative_to(ROOT).as_posix())
    print(f"Normalized external links in {changed} files")


if __name__ == "__main__":
    main()
