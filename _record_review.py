#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Record that the physician has re-read an article.

WHY THIS IS A TOOL AND NOT A PIPELINE STEP
==========================================
`lastReviewed` in the articles' JSON-LD is a claim that a doctor read the page
on that date. Nothing automated can know that, so nothing automated may write
it — see TD-74, where the field was derived from git and every rebuild silently
asserted a medical review that never happened.

So the date lives in _review_dates.json, the build only reads it, and this is
the one thing that writes it. Running it IS the act of recording the review.

WHAT THE SEEDED DATES MEAN
==========================
Every entry started as `source: "published"` — the day the article went live,
which the physician demonstrably reviewed because he wrote it. That is a floor,
not a reading: it is chosen to UNDERSTATE, because an understated review date
costs a little freshness while an overstated one is a false medical claim on a
YMYL page.

Recording a real re-read with this tool sets `source: "reviewed"`, and
--list shows what is still sitting on the floor.

USAGE
=====
    python _record_review.py --list                 # what still needs a read
    python _record_review.py acne-myths             # reviewed today
    python _record_review.py acne-myths 2026-07-15  # reviewed on that date
    python _record_review.py --all 2026-07-15       # a full sweep of every article

After recording, run `python _run_quality.py build` so the pages pick it up.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone

# The site's dates are Taiwan dates: the physician records a review in Taipei,
# but CI runs the gate on ubuntu-latest with no TZ configured, i.e. UTC. A
# review recorded between 00:00 and 08:00 Taipei carries tomorrow's date as far
# as UTC is concerned, and _check_seo_signals.py rejects it as future-dated —
# blocking deployment for up to eight hours over a date that is perfectly
# correct. A fixed offset rather than ZoneInfo("Asia/Taipei"): Taiwan has had no
# DST since 1979, so +08:00 is exact, and it needs no tzdata on Windows.
TAIPEI = timezone(timedelta(hours=8))


def taipei_today() -> date:
    return datetime.now(TAIPEI).date()
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "_review_dates.json"
BLOG = ROOT / "blog"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load() -> dict:
    if not LEDGER.exists():
        raise SystemExit(f"[FAIL] {LEDGER.name} is missing")
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    LEDGER.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def article_slugs() -> set[str]:
    return {p.stem for p in BLOG.glob("*.html")
            if p.stem not in ("index", "topics")}


def published_on(slug: str) -> str | None:
    path = BLOG / f"{slug}.html"
    if not path.exists():
        return None
    m = re.search(r'"datePublished":"(\d{4}-\d{2}-\d{2})',
                  path.read_text(encoding="utf-8", errors="replace"))
    return m.group(1) if m else None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Record a physician review date for one article or all.")
    ap.add_argument("slug", nargs="?", help="article slug, or --all")
    ap.add_argument("when", nargs="?", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--all", action="store_true",
                    help="record the same date for every article")
    ap.add_argument("--list", action="store_true",
                    help="show which articles have never had a real review recorded")
    args = ap.parse_args()

    data = load()
    slugs = article_slugs()

    if args.list:
        floor = sorted(s for s in slugs
                       if data.get(s, {}).get("source") != "reviewed")
        done = sorted(s for s in slugs
                      if data.get(s, {}).get("source") == "reviewed")
        print(f"reviewed and recorded: {len(done)}")
        for s in done:
            print(f"   {s:<44} {data[s]['date']}")
        print(f"\nstill on the published-date floor: {len(floor)}")
        for s in floor:
            print(f"   {s:<44} {data.get(s, {}).get('date', '—')}")
        if floor:
            print("\nRecord one with:  python _record_review.py <slug> [YYYY-MM-DD]")
        return 0

    # CODE_REVIEW TD-75 — `--all 2026-07-15`, the form printed in this file's
    # own usage, put the date into the SLUG position and left `when` unset, so
    # it recorded TODAY for all 55 articles. A tool built to stop false review
    # claims was quietly writing one. With --all the sole positional IS the
    # date; anything else is ambiguous and refused rather than guessed at.
    raw_when = args.when
    if args.all:
        if args.slug and args.when:
            raise SystemExit(f"[FAIL] --all takes only a date, got "
                             f"{args.slug!r} and {args.when!r}")
        raw_when = args.when or args.slug
        targets = sorted(slugs)
    elif args.slug:
        if args.slug not in slugs:
            raise SystemExit(f"[FAIL] no article blog/{args.slug}.html")
        targets = [args.slug]
    else:
        ap.print_help()
        return 2

    # Parsed, not pattern-matched: 2026-06-31 satisfies the regex and is not a
    # day that exists. Comparisons are between date objects for the same
    # reason — string ordering only happens to work while both are valid.
    today = taipei_today()
    if raw_when is None:
        when_d = today
    else:
        if not DATE_RE.match(str(raw_when)):
            raise SystemExit(f"[FAIL] {raw_when!r} is not YYYY-MM-DD")
        try:
            when_d = date.fromisoformat(raw_when)
        except ValueError as exc:
            raise SystemExit(f"[FAIL] {raw_when} is not a real date ({exc})")
    if when_d > today:
        raise SystemExit(f"[FAIL] {when_d} is in the future — a review that has "
                         f"not happened yet cannot be recorded")
    when = when_d.isoformat()

    changed = 0
    for slug in targets:
        published = published_on(slug)
        if published and when_d < date.fromisoformat(published):
            raise SystemExit(
                f"[FAIL] {slug} was published on {published}; it cannot have "
                f"been reviewed on {when}")
        if data.get(slug, {}) != {"date": when, "source": "reviewed"}:
            data[slug] = {"date": when, "source": "reviewed"}
            changed += 1
            print(f"  recorded {slug} reviewed {when}")
    if changed:
        save(data)
    print(f"[OK] recorded {changed} review(s) in {LEDGER.name}. "
          f"Run `python _run_quality.py build` to publish them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
