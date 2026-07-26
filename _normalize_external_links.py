#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Harden target=_blank links with noopener+noreferrer."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _html_scan import attribute_spans, iter_tags, tag_name  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "__pycache__"}
REQUIRED_REL = ("noopener", "noreferrer")


def normalize_anchor(tag: str) -> str:
    """Ensure this <a target="_blank"> carries noopener + noreferrer.

    CODE_REVIEW TD-57 — the previous matcher was
    `<a\\b[^>]*\\btarget=(['"])_blank\\1[^>]*>`, which ends the tag at the first
    `>`. On this site a `>` frequently sits INSIDE a quoted attribute value
    (379 tags carry bilingual values like data-zh="<strong>…</strong>"), so an
    anchor whose data-zh preceded target=_blank never matched — and the
    reverse-tabnabbing hardening was silently skipped on exactly the links the
    audit is meant to protect. `rel` is now located by parsing attributes, not
    by searching the tag text, so a literal `rel=` inside prose cannot be
    mistaken for the attribute.
    """
    spans = attribute_spans(tag)
    target = spans.get("target")
    if target is None or target[2].lower() != "_blank":
        return tag

    rel = spans.get("rel")
    if rel is not None:
        start, end, value, quote = rel
        quote = quote or '"'
        tokens = value.split()
        lowered = {t.lower() for t in tokens}
        for token in REQUIRED_REL:
            if token not in lowered:
                tokens.append(token)
        return tag[:start] + f"rel={quote}{' '.join(tokens)}{quote}" + tag[end:]

    insert_at = target[1]
    return tag[:insert_at] + f' rel="{" ".join(REQUIRED_REL)}"' + tag[insert_at:]


def normalize(src: str) -> str:
    out: list[str] = []
    cursor = 0
    for start, tag in iter_tags(src):
        if tag_name(tag) != "a" or tag.startswith("</"):
            continue
        fixed = normalize_anchor(tag)
        if fixed == tag:
            continue
        out.append(src[cursor:start])
        out.append(fixed)
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
                print("normalized external links", path.relative_to(ROOT).as_posix())
    print(f"Normalized external links in {changed} files")


if __name__ == "__main__":
    main()
