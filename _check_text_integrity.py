#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Catch replacement characters, common mojibake, and duplicated title separators."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", ".github", "node_modules", "__pycache__", ".lighthouseci"}
EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

BAD_CHAR_RE = re.compile("\\ufffd")
MOJIBAKE_RE = re.compile(
    "(?:"
    "\\u00c3.|"
    "\\u00c2.|"
    "\\u00e2[\\u0080-\\uffff]{1,2}|"
    "[\\u00e4-\\u00e9][\\u0080-\\uffff]{1,3}"
    ")"
)
DOUBLE_TITLE_SEPARATOR_RE = re.compile(
    "<title>[^<]*\\u00b7\\s*\\u00b7[^<]*</title>",
    re.IGNORECASE,
)
QUESTION_MARK_TITLE_SEPARATOR_RE = re.compile(
    "<title>[^<]*\\s\\?\\s+(?:ChenDermatologist|[^<]*ChenDermatologist)[^<]*</title>",
    re.IGNORECASE,
)


def iter_files() -> list[Path]:
    paths: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() in EXTENSIONS:
            paths.append(path)
    return sorted(paths)


def line_col(src: str, index: int) -> tuple[int, int]:
    line = src.count("\n", 0, index) + 1
    last_break = src.rfind("\n", 0, index)
    col = index + 1 if last_break == -1 else index - last_break
    return line, col


def main() -> int:
    errors: list[str] = []

    for path in iter_files():
        rel = path.relative_to(ROOT).as_posix()
        try:
            src = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"{rel}: not valid UTF-8 ({exc})")
            continue

        for regex, label in (
            (BAD_CHAR_RE, "contains Unicode replacement character"),
            (MOJIBAKE_RE, "contains likely mojibake text"),
            (DOUBLE_TITLE_SEPARATOR_RE, "contains duplicated title separator"),
            (QUESTION_MARK_TITLE_SEPARATOR_RE, "contains likely corrupted title separator"),
        ):
            match = regex.search(src)
            if match:
                line, col = line_col(src, match.start())
                snippet = src[match.start() : match.end()].replace("\n", " ")[:80]
                errors.append(f"{rel}:{line}:{col}: {label}: {snippet!r}")

    if errors:
        print("[FAIL] Text integrity audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1

    print("[OK] Text integrity audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
