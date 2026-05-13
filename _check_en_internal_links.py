#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Ensure /en/ pages keep local page links inside the /en/ mirror."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EN_ROOT = ROOT / "en"
HREF_RE = re.compile(r'<a\b[^>]*\bhref=["\']([^"\']+)["\']', re.I)
SKIP = {"404.html", "offline.html", "admin.html", "dashboard.html", "notes.html", "reset-sw.html"}


def local_html_for_path(path: str) -> Path | None:
    clean = path.split("?", 1)[0].split("#", 1)[0]
    if clean == "/":
        candidate = ROOT / "index.html"
        return candidate if candidate.exists() else None
    if clean.endswith("/"):
        candidate = ROOT / clean.strip("/") / "index.html"
        return candidate if candidate.exists() else None
    rel = clean.lstrip("/")
    for candidate in (ROOT / f"{rel}.html", ROOT / rel / "index.html"):
        if candidate.exists():
            return candidate
    return None


def en_mirror_expected(path: str) -> bool:
    clean = path.split("?", 1)[0].split("#", 1)[0]
    if clean == "/":
        return True
    if clean.startswith("/en/"):
        return True
    if clean.endswith("/"):
        return (ROOT / clean.strip("/") / "index.html").exists()
    rel = clean.lstrip("/")
    if rel.endswith(".html"):
        rel = rel[:-5]
    source_file = f"{rel}.html"
    if "/" not in rel:
        return (ROOT / source_file).exists() and source_file not in SKIP
    if rel.startswith("blog/"):
        return (ROOT / "blog" / f"{rel.split('/', 1)[1]}.html").exists()
    return False


def should_check(href: str) -> bool:
    return href.startswith("/") and not href.startswith("//") and not href.startswith("/en/")


def main() -> int:
    errors: list[str] = []
    if not EN_ROOT.exists():
        print("[OK] English internal-link audit skipped; en/ not found")
        return 0

    for path in sorted(EN_ROOT.rglob("*.html")):
        src = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        for match in HREF_RE.finditer(src):
            href = match.group(1)
            if not should_check(href):
                continue
            if local_html_for_path(href) is not None and en_mirror_expected(href):
                errors.append(f"{rel}: local page link should stay in /en/: {href}")

    if errors:
        print("[FAIL] English internal-link audit found issues:")
        for error in errors[:160]:
            print(" - " + error)
        if len(errors) > 160:
            print(f" ... {len(errors) - 160} more")
        return 1

    print("[OK] English internal-link audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
