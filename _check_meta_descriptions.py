#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit <meta name="description"> across every indexable page.

Why: Google uses the meta description to render SERP snippets. A
description that's too short (under ~70 chars / 35 CJK) gets ignored
and Google auto-generates from body text — usually less compelling.
Too long (over ~160 chars / 80 CJK) gets truncated mid-sentence,
killing CTR. Duplicate descriptions across pages hurt because
Google may dedupe or downrank.

Length thresholds (Chinese-aware):
  - ZH content: 60-110 CJK chars (sweet spot for `description`
    field; SERP allows up to ~95 CJK chars before truncation)
  - EN content: 110-155 ASCII chars
  - Mixed content (typical): treat each CJK char as 2 width
    units for budget calculation.

Output groups:
  ⚠ TOO_SHORT — under threshold
  ⚠ TOO_LONG  — over threshold
  ⚠ DUPLICATE — exact match shared by 2+ pages
  ⚠ MISSING   — no description at all
  ✅ HEALTHY   — passes all checks

Usage:
    python _check_meta_descriptions.py            # full report
    python _check_meta_descriptions.py --problems # only problems
    python _check_meta_descriptions.py --json     # machine-readable
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent

# Thresholds (in CJK-aware "width units" — 1 ASCII = 1 unit, 1 CJK = 2)
WIDTH_MIN = 120   # ~60 CJK or ~120 ASCII chars
WIDTH_MAX = 220   # ~110 CJK or ~220 ASCII chars

META_DESC_RE = re.compile(
    r'<meta\s+name="description"\s+content="([^"]*)"', re.IGNORECASE
)
NOINDEX_RE = re.compile(
    r'<meta\s+name="robots"[^>]*content="[^"]*noindex', re.IGNORECASE
)


def cjk_width(s: str) -> int:
    """Return CJK-aware width: each ASCII char = 1, each CJK char = 2.
    Approximates SERP rendering width better than raw char count.
    """
    w = 0
    for ch in s:
        if "一" <= ch <= "鿿" or "　" <= ch <= "〿":
            w += 2
        elif "＀" <= ch <= "￯":  # full-width forms
            w += 2
        else:
            w += 1
    return w


def collect_pages() -> list[dict]:
    """Walk all .html files; return [{path, desc, width, noindex}]."""
    out: list[dict] = []
    for fp in ROOT.rglob("*.html"):
        # Skip 3rd-party / generated assets
        rel = fp.relative_to(ROOT).as_posix()
        if any(seg in rel for seg in [
            "node_modules/", "pagefind/", "admin/", ".git/",
            "_run_quality", "ONBOARDING", "404.html", "offline.html",
            "reset-sw.html",
        ]):
            continue
        src = fp.read_text(encoding="utf-8", errors="replace")
        noindex = bool(NOINDEX_RE.search(src))
        m = META_DESC_RE.search(src)
        desc = m.group(1) if m else ""
        out.append({
            "path": rel,
            "desc": desc,
            "width": cjk_width(desc),
            "noindex": noindex,
        })
    return out


def main() -> int:
    only_problems = "--problems" in sys.argv
    json_mode = "--json" in sys.argv

    pages = collect_pages()
    # Only indexable pages count for SERP audit
    indexable = [p for p in pages if not p["noindex"]]

    # Find duplicates among indexable pages
    desc_to_paths: dict[str, list[str]] = defaultdict(list)
    for p in indexable:
        if p["desc"]:
            desc_to_paths[p["desc"]].append(p["path"])
    duplicates = {d: paths for d, paths in desc_to_paths.items()
                  if len(paths) > 1}

    # Classify each indexable page
    problems: list[dict] = []
    healthy_count = 0
    for p in indexable:
        flags = []
        if not p["desc"]:
            flags.append("MISSING")
        elif p["width"] < WIDTH_MIN:
            flags.append("TOO_SHORT")
        elif p["width"] > WIDTH_MAX:
            flags.append("TOO_LONG")
        if p["desc"] and p["desc"] in duplicates:
            flags.append("DUPLICATE")
        if flags:
            p["flags"] = flags
            problems.append(p)
        else:
            healthy_count += 1

    if json_mode:
        print(json.dumps({
            "summary": {
                "indexable_pages": len(indexable),
                "healthy": healthy_count,
                "problems": len(problems),
                "duplicate_groups": len(duplicates),
            },
            "problems": problems,
            "duplicates": duplicates,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"\n=== Meta-description audit ({len(indexable)} indexable pages) ===\n")
    print(f"Healthy:  {healthy_count}")
    print(f"Problems: {len(problems)}")
    print(f"Duplicate groups: {len(duplicates)}")
    print(f"Length window: {WIDTH_MIN}-{WIDTH_MAX} width-units")
    print(f"  (1 ASCII = 1 unit, 1 CJK = 2; so ~{WIDTH_MIN//2}-{WIDTH_MAX//2} CJK chars)")
    print()

    if duplicates:
        print("⚠ DUPLICATES:")
        for desc, paths in duplicates.items():
            print(f'  shared by {len(paths)} pages: "{desc[:70]}..."')
            for p in paths:
                print(f"    - {p}")
        print()

    if not problems and not only_problems:
        print("✅ All indexable pages have descriptions in the target window.")
        return 0

    problems.sort(key=lambda p: (",".join(p["flags"]), p["width"]))
    print("Per-page issues:")
    for p in problems:
        flag_str = ",".join(p["flags"])
        print(f"  [{flag_str:<22}] w={p['width']:>4}  {p['path']:<50}")
        if p["desc"]:
            print(f"      {p['desc'][:80]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
