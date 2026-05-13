#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit duplicate metadata on indexable public pages."""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
SKIP_FILES = {"404.html", "offline.html", "reset-sw.html"}
FIELDS = {
    "title": re.compile(r"<title>([\s\S]*?)</title>", re.I),
    "description": re.compile(r'<meta\s+name="description"\s+content="([^"]*)"', re.I),
    "og:title": re.compile(r'<meta\s+property="og:title"\s+content="([^"]*)"', re.I),
    "og:description": re.compile(r'<meta\s+property="og:description"\s+content="([^"]*)"', re.I),
    "og:url": re.compile(r'<meta\s+property="og:url"\s+content="([^"]*)"', re.I),
    "canonical": re.compile(r'<link\s+rel="canonical"\s+href="([^"]*)"', re.I),
}


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def is_noindex(src: str) -> bool:
    return bool(re.search(r'<meta\s+name="robots"\s+content="[^"]*\bnoindex\b', src, re.I))


def iter_html() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.html"):
        rel_parts = path.relative_to(ROOT).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if path.name in SKIP_FILES:
            continue
        if rel_parts[0] == "admin":
            continue
        files.append(path)
    return files


def main() -> int:
    errors: list[str] = []
    values: dict[str, dict[str, list[str]]] = {field: defaultdict(list) for field in FIELDS}

    for path in iter_html():
        rel = path.relative_to(ROOT).as_posix()
        src = path.read_text(encoding="utf-8")
        if is_noindex(src):
            continue
        for field, pattern in FIELDS.items():
            match = pattern.search(src)
            if not match:
                continue
            values[field][normalize(match.group(1))].append(rel)

    for field, grouped in values.items():
        for value, paths in grouped.items():
            if len(paths) <= 1:
                continue
            if field == "canonical":
                errors.append(f'duplicate canonical "{value}" used by {len(paths)} pages: {paths[:6]}')
            elif field == "og:url":
                errors.append(f'duplicate og:url "{value}" used by {len(paths)} pages: {paths[:6]}')
            elif len(paths) > 2:
                errors.append(f'duplicate {field} on {len(paths)} indexable pages: {value[:120]} :: {paths[:6]}')

    if errors:
        print("[FAIL] Metadata uniqueness audit found issues:")
        for error in errors[:160]:
            print(" - " + error)
        if len(errors) > 160:
            print(f" ... {len(errors) - 160} more")
        return 1
    print("[OK] Metadata uniqueness audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
