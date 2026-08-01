#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Keep simplified-only characters out of the Traditional Chinese pages.

HOW THIS WAS FOUND
==================
While measuring what a self-hosted CJK subset would need (TD-02), two of the
2,202 characters the site uses turned out to be absent from Noto Sans TC's
coverage: 湿 and 螨. Not a font gap — those are the SIMPLIFIED forms of 濕 and
蟎, on a zh-Hant-TW site. The site itself was inconsistent about it: 濕 appeared
438 times against 湿 twice, and 蟎 61 times against 螨 28.

WHY A LIST AND NOT A CONVERSION TABLE
=====================================
A general simplified/traditional detector needs a mapping of the whole script
and would have to decide what to do about characters that are correct in both,
and about genuinely simplified text quoted from a mainland source. That is a
lot of machinery and a lot of ways to produce a false positive on a medical
page.

This is the narrow version: a list of simplified forms whose traditional
counterpart THIS SITE ALREADY USES, so flagging them cannot be wrong — the site
has already made the choice, and the flagged character contradicts it. Add a
pair when one turns up; do not add pairs speculatively.

Scope: page content only. Text quoted inside JSON-LD (citation and reference
titles) is left alone, because a simplified journal title is quoted correctly.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# simplified -> traditional. Every pair here was found in the corpus with the
# traditional form already dominant.
SIMPLIFIED = {
    "湿": "濕",
    "螨": "蟎",
}

SKIP_DIRS = {".git", "node_modules", "__pycache__", "pagefind"}
LD_BLOCK = re.compile(r'<script type="application/ld\+json">[\s\S]*?</script>', re.I)

# Anti-vacuity floor: this must fail if page discovery breaks rather than pass
# on an empty scan.
# Measured: the site serves 70 zh-Hant pages (the rest of the tree is the
# lang="en" mirror). 60 leaves room for pages being retired without the
# floor firing spuriously, while still catching a broken scan.
MIN_FILES = 60


def zh_pages() -> list[Path]:
    """Pages served as Traditional Chinese — the EN mirror is out of scope."""
    out = []
    for path in sorted(ROOT.rglob("*.html")):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'<html\b[^>]*lang="([^"]*)"', src, re.I)
        if m and m.group(1).lower().startswith("zh"):
            out.append(path)
    return out


def main() -> int:
    errors: list[str] = []
    files = zh_pages()
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        src = path.read_text(encoding="utf-8", errors="replace")
        spans = [(m.start(), m.end()) for m in LD_BLOCK.finditer(src)]
        for simp, trad in SIMPLIFIED.items():
            for m in re.finditer(re.escape(simp), src):
                if any(a <= m.start() < b for a, b in spans):
                    continue        # quoted source, left as written
                ctx = re.sub(r"\s+", " ", src[max(0, m.start() - 24):m.end() + 24])
                errors.append(
                    f"{rel}: simplified {simp!r} on a zh-Hant page — this site "
                    f"writes {trad!r} …{ctx}…")

    if len(files) < MIN_FILES:
        errors.append(
            f"only {len(files)} zh-Hant page(s) found (expected >= {MIN_FILES}) "
            f"— discovery is broken, so a pass here would mean nothing")

    if errors:
        print(f"[FAIL] found {len(errors)} simplified-character issue(s):")
        for line in errors[:20]:
            print(f"  - {line}")
        if len(errors) > 20:
            print(f"  … and {len(errors) - 20} more")
        return 1

    print(f"[OK] no simplified-only characters on {len(files)} zh-Hant pages "
          f"({len(SIMPLIFIED)} pairs checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
