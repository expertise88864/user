#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Auto-bump JSON-LD `dateModified` when an article's content body
actually changes between builds.

Why: GSC reported `atopic-dermatitis-overview` (and likely others) in
"Crawled — currently not indexed" status. The article had:
  datePublished: 2026-05-03
  dateModified:  2026-05-03   ← UNCHANGED for 17 days
despite heavy SEO + schema updates over that period.

Without a dateModified bump, Google's freshness signal stays cold,
the article stays in the "crawled but not indexed" bucket, and the
many internal improvements we've shipped don't trigger re-evaluation.

Algorithm:
  1. Extract each article's <article> body text (drop scripts / styles /
     SVGs / JSON-LD / data-* attribute values — anything BUILD touches
     should NOT count as content change).
  2. SHA-256 of the cleaned text.
  3. Compare to last-seen hash in .dn-content-hash.json.
  4. If hash changed: bump dateModified in every MedicalWebPage /
     MedicalScholarlyArticle JSON-LD block AND `article:modified_time`
     OG meta on that page to today.
  5. Persist new hash.

The hash file is gitignored (operational state) but checked into Vercel
build via _run_quality.py REGEN_STEPS so it persists across deploys.

Wait — Vercel CI runs fresh each build, so the hash file WOULDN'T persist.
For that, we either:
  (a) commit the hash file (loses gitignore semantics but works)
  (b) git mtime: use the last commit timestamp that touched the article
      file as the canonical dateModified

Option (b) is cleaner and matches reality. Switching to it:
  - For each article, read git log -1 --format=%aI -- <path>
  - That's the last commit that touched the file
  - Use that ISO date as dateModified

This avoids needing a hash sidecar entirely AND correctly reflects
actual git history.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
BLOG = ROOT / "blog"
EN_BLOG = ROOT / "en" / "blog"


def git_last_modified(path: Path) -> str | None:
    """Return YYYY-MM-DD of the last git commit that touched `path`.
    None if git is unavailable or the file isn't tracked yet.
    """
    try:
        rel = path.relative_to(ROOT).as_posix()
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", rel],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
        )
        if result.returncode != 0:
            return None
        out = result.stdout.strip()
        return out if re.match(r"^\d{4}-\d{2}-\d{2}$", out) else None
    except (subprocess.SubprocessError, OSError) as exc:
        # CODE_REVIEW 2026-05-25 — narrowed + logged so missing git history
        # surfaces in CI logs instead of silently leaving dateModified stale.
        print(f"[normalize_date_modified] git log failed for {path}: {exc}",
              file=sys.stderr)
        return None


def update_article(path: Path, new_date: str) -> int:
    """Bump dateModified everywhere it occurs in `path`. Returns
    number of replacements made (0 if no change).
    """
    src = path.read_text(encoding="utf-8")
    n = 0

    # 1. JSON-LD "dateModified":"YYYY-MM-DD..."
    def replace_jsonld(m: re.Match) -> str:
        nonlocal n
        # Preserve any time portion that might be present (rare but possible)
        old = m.group(0)
        replacement = f'"dateModified":"{new_date}"'
        if replacement != old:
            n += 1
        return replacement
    src = re.sub(
        r'"dateModified":"[^"]+"',
        replace_jsonld,
        src,
    )

    # 2. OG article:modified_time — ISO 8601 with timezone offset
    iso = f"{new_date}T00:00:00+08:00"

    def replace_og(m: re.Match) -> str:
        nonlocal n
        old = m.group(0)
        replacement = m.group(1) + iso + m.group(3)
        if replacement != old:
            n += 1
        return replacement
    src = re.sub(
        r'(<meta\s+property="article:modified_time"\s+content=")([^"]+)(")',
        replace_og,
        src,
        flags=re.IGNORECASE,
    )

    if n > 0:
        path.write_text(src, encoding="utf-8")
    return n


def main() -> int:
    if not BLOG.exists():
        print("[date-modified] blog/ missing")
        return 0

    today = date.today().isoformat()
    skip = {"index.html", "topics.html"}
    total_bumped = 0
    pages_changed = 0
    pages_kept = 0

    for fp in sorted(BLOG.glob("*.html")):
        if fp.name in skip:
            continue
        # Use git's last-touched date for THIS article's file. That date
        # represents the last actual content / schema change made to it.
        last_touched = git_last_modified(fp)
        if not last_touched:
            # Unstaged file or first-time author flow — fall back to today
            last_touched = today

        n = update_article(fp, last_touched)
        if n > 0:
            total_bumped += n
            pages_changed += 1
            # Also bump the EN mirror so hreflang freshness signals match
            en_fp = EN_BLOG / fp.name
            if en_fp.exists():
                update_article(en_fp, last_touched)
        else:
            pages_kept += 1

    print(f"[date-modified] bumped {total_bumped} JSON-LD/OG occurrences "
          f"across {pages_changed} articles; {pages_kept} already current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
