#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SSG-inject a visible reading-time badge directly under the article H1.

We already compute `timeRequired` in JSON-LD via _normalize_schema.py.
This script reads that value back out and writes a tiny <p> element
right after </h1> so:
  - Users see "閱讀時間約 7 分鐘 · 約 1861 字" at a glance
  - Google can attach the time to search snippets (HTML signal in addition to JSON-LD)
  - The text is bilingual via data-zh/data-en, so EN visitors see "~ 7 min read · 1861 words"

Idempotent: detects existing `<p class="dn-reading-time"` and replaces it.
Skips articles where timeRequired is not yet in JSON-LD (run _normalize_schema.py first).

Run as part of REGEN_STEPS in _run_quality.py, after _normalize_schema.py.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"

# Matches existing badge so re-runs are clean.
EXISTING_BADGE_RE = re.compile(
    r'\s*<p\s+class="dn-reading-time"[\s\S]*?</p>',
    re.IGNORECASE,
)

# Pull timeRequired + wordCount from any JSON-LD block on the page.
TIME_REQUIRED_RE = re.compile(r'"timeRequired":"PT(\d+)M"')
WORD_COUNT_RE = re.compile(r'"wordCount":(\d+)')

# Find the first </h1> in the document (article title) to anchor injection.
H1_CLOSE_RE = re.compile(r'</h1>', re.IGNORECASE)


def build_badge(minutes: int, word_count: int) -> str:
    """Build a bilingual reading-time + word-count badge.

    Visual: small muted line under the H1, similar in weight to the existing
    article meta line ("陳翊嘉醫師 · 更新 2026-...").
    """
    zh = f"閱讀時間約 {minutes} 分鐘 · 約 {word_count:,} 字"
    en = f"{minutes} min read · {word_count:,} words"
    # Tailwind classes match the rest of the article meta typography.
    return (
        '<p class="dn-reading-time mt-3 mb-2 text-[12.5px] text-ink-500" '
        'aria-label="Estimated reading time">'
        f'<time datetime="PT{minutes}M" data-zh="{zh}" data-en="{en}">{zh}</time>'
        '</p>'
    )


def inject_one(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    tr_m = TIME_REQUIRED_RE.search(src)
    wc_m = WORD_COUNT_RE.search(src)
    if not tr_m or not wc_m:
        return False
    minutes = int(tr_m.group(1))
    word_count = int(wc_m.group(1))
    badge = build_badge(minutes, word_count)

    # Strip any prior injection so re-runs are idempotent.
    cleaned = EXISTING_BADGE_RE.sub("", src)

    h1_m = H1_CLOSE_RE.search(cleaned)
    if not h1_m:
        return False
    # Insert right after the first </h1>
    insert_at = h1_m.end()
    next_src = cleaned[:insert_at] + badge + cleaned[insert_at:]
    if next_src == src:
        return False
    path.write_text(next_src, encoding="utf-8")
    return True


def main() -> int:
    targets: list[Path] = []
    for d in (ROOT / "blog", ROOT / "en" / "blog"):
        if d.exists():
            for fp in sorted(d.glob("*.html")):
                if fp.name in {"index.html", "topics.html"}:
                    continue
                targets.append(fp)

    changed = 0
    skipped_no_metric = 0
    for fp in targets:
        try:
            if inject_one(fp):
                changed += 1
        except Exception as exc:
            print(f"[!] {fp.relative_to(ROOT)} failed: {exc}")
    print(f"Injected reading-time badge into {changed} of {len(targets)} articles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
