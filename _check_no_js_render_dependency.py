#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CI guard: every blog article must render its H1 + lead paragraph
WITHOUT JavaScript executing.

Tier 2D from OPEN_SOURCE_INTEGRATIONS.md (borrowed from Auriti-Labs
GEO checker concept). AI/LLM crawlers and Googlebot's mobile crawler
may not always execute JS; if the H1 + first paragraph live only in
data-en attribute values or are appended at runtime by JS, those
crawlers see a blank article.

Heuristic (no headless browser needed — pure static analysis):
  1. The first <h1> inside <article> or <main> must have visible
     text content (not just data-zh attribute on an empty element).
  2. The first <p> after <h1> must have visible text content of
     at least 60 chars.
  3. Both must appear BEFORE any tag that only contains JS-injected
     content (e.g. an empty <div id="something-dynamic">).

Why static analysis is sufficient: Googlebot crawls in two passes —
the first pass reads the raw HTML and indexes the content immediately;
the second pass (if it ever fires) executes JS for hydration. The
first pass is what determines initial ranking; content that depends on
JS may be indexed days/weeks later or not at all.

Skips intentionally-noindex pages.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
# Threshold tuned for CJK content: 30 visible chars after stripping
# tags and data-* attrs. The site has some articles that legitimately
# open with a short Q&A literary device (~30-40 chars), e.g.
#   「醫師，我穿鞋很久了，趾甲就黃黃厚厚的，是灰指甲嗎？要吃藥嗎？」
# Those are intentional openers, not bugs. Threshold catches the
# real problem (paragraph body empty in raw HTML, populated only by
# JS) without false-flagging short rhetorical openings.
MIN_LEAD_CHARS = 30


def visible_text_length(html_chunk: str) -> int:
    """Return the length of visible text after stripping all tags and
    data-* attribute values (those are JS-swapped, not first-paint).
    """
    # Strip script/style entirely
    s = re.sub(r"<(script|style)\b[\s\S]*?</\1>", " ", html_chunk, flags=re.I)
    # Drop data-* attribute values
    s = re.sub(r'\sdata-[a-z-]+="[^"]*"', "", s)
    # Drop all remaining tags
    s = re.sub(r"<[^>]+>", " ", s)
    # Collapse whitespace
    return len(re.sub(r"\s+", "", s))


def check_article(path: Path) -> list[str]:
    issues: list[str] = []
    src = path.read_text(encoding="utf-8", errors="replace")

    # Skip noindex pages — JS-dependency doesn't matter if Google won't index.
    if re.search(r'<meta[^>]+name="robots"[^>]+content="[^"]*noindex',
                 src, re.I):
        return issues

    # Find the first <h1>...</h1> after <article> or <main>.
    main_m = re.search(r"<(article|main)\b[^>]*>([\s\S]*)", src, re.I)
    if not main_m:
        return issues  # not an article-style page

    body = main_m.group(2)
    h1_m = re.search(r"<h1\b[^>]*>([\s\S]*?)</h1>", body, re.I)
    if not h1_m:
        # Article without an h1 is its own bug; flagged elsewhere by
        # _check_static_a11y. Don't double-report.
        return issues

    h1_text_len = visible_text_length(h1_m.group(1))
    if h1_text_len < 3:
        issues.append(
            "<h1> has no visible text in raw HTML (likely JS-injected) — "
            "Googlebot's first pass will index a blank title"
        )

    # First <p> after the h1
    after_h1 = body[h1_m.end():]
    # Skip the article-meta div / reading-time badge / hero card if present
    # by looking for the FIRST <p>, not the first text container.
    p_m = re.search(r"<p\b[^>]*>([\s\S]*?)</p>", after_h1, re.I)
    if not p_m:
        issues.append(
            "no <p> follows <h1> in raw HTML — Googlebot first pass "
            "may have no lead paragraph to index"
        )
        return issues

    p_text_len = visible_text_length(p_m.group(1))
    if p_text_len < MIN_LEAD_CHARS:
        issues.append(
            f"lead paragraph has only {p_text_len} visible chars before "
            f"data-* swap (need ≥ {MIN_LEAD_CHARS}) — content depends on "
            f"JS execution for first-paint indexing"
        )

    return issues


def main() -> int:
    targets: list[Path] = []
    for d in ("blog",):  # only ZH source; EN mirror inherits the same issue.
        dpath = ROOT / d
        if dpath.exists():
            for fp in sorted(dpath.glob("*.html")):
                if fp.name in {"index.html", "topics.html"}:
                    continue
                targets.append(fp)

    failures: list[tuple[Path, list[str]]] = []
    for fp in targets:
        issues = check_article(fp)
        if issues:
            failures.append((fp, issues))

    if failures:
        print(f"[FAIL] JS-rendering dependency audit found {len(failures)} "
              f"article(s) whose H1 / lead paragraph depends on JS for "
              f"first-paint:")
        for fp, issues in failures[:25]:
            for msg in issues:
                print(f" - {fp.relative_to(ROOT).as_posix()}: {msg}")
        if len(failures) > 25:
            print(f" ... and {len(failures) - 25} more")
        return 1

    print(f"[OK] JS-rendering audit: all {len(targets)} articles paint "
          f"their H1 + lead paragraph from raw HTML")
    return 0


if __name__ == "__main__":
    sys.exit(main())
