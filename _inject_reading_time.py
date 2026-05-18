#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Strip any SSG-injected reading-time badge from blog articles.

History: I tried SSG-injecting a visible "閱讀時間約 X 分鐘 · 約 Y 字"
badge right after </h1> to give Googlebot the metric without needing
JS execution. Two problems surfaced immediately:

  1. The original dedup regex was `class="dn-reading-time"` (literal
     closing quote) but the inserted markup used additional Tailwind
     classes (`class="dn-reading-time mt-3 ..."`), so re-runs never
     stripped the prior badge — every regen accumulated another copy.

  2. DN.addReadingMeta() already injects a styled "hero card" at
     runtime with its own reading-time + word-count counter. The SSG
     badge appeared in addition to it AND used a different counting
     method (longer count because it includes references/footer),
     producing TWO different reading-time numbers visible on the same
     page (e.g. "9 分鐘" in the hero + "17 分鐘" in the SSG badge).

The JSON-LD `wordCount` + `timeRequired` set by _normalize_schema.py
already carries the SEO signal Google needs (and it shows up in the
indexed page metadata regardless of JS). So we don't need a visible
SSG badge at all — let DN.addReadingMeta own the on-page UI.

This script now exists purely to STRIP any badge a prior run left
behind. It runs after _normalize_schema.py in REGEN_STEPS so future
templates that try to add their own dn-reading-time tag get cleaned.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent

# Strip BOTH the original buggy form (any number of repeats) and the
# corrected form so a single pass cleans every previously-injected copy.
# `class="dn-reading-time[^"]*"` matches the class regardless of extra
# Tailwind utility classes appended after the name.
BADGE_RE = re.compile(
    r'\s*<p\s+class="dn-reading-time[^"]*"[^>]*>[\s\S]*?</p>',
    re.IGNORECASE,
)


def strip_one(path: Path) -> int:
    src = path.read_text(encoding="utf-8")
    stripped = BADGE_RE.sub("", src)
    if stripped == src:
        return 0
    # Count how many copies we removed for the summary log.
    removed = len(BADGE_RE.findall(src))
    path.write_text(stripped, encoding="utf-8")
    return removed


def main() -> int:
    targets: list[Path] = []
    for d in (ROOT / "blog", ROOT / "en" / "blog"):
        if d.exists():
            for fp in sorted(d.glob("*.html")):
                if fp.name in {"index.html", "topics.html"}:
                    continue
                targets.append(fp)

    files_changed = 0
    total_removed = 0
    for fp in targets:
        try:
            removed = strip_one(fp)
            if removed:
                files_changed += 1
                total_removed += removed
        except Exception as exc:
            print(f"[!] {fp.relative_to(ROOT)} failed: {exc}")
    print(
        f"Stripped {total_removed} stale dn-reading-time badge(s) "
        f"from {files_changed} articles "
        f"(JSON-LD wordCount/timeRequired still in place for SEO)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
