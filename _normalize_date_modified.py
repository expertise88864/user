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
  - For each article, read the latest non-auto-regen git commit that
    touched the file
  - Use that ISO date as dateModified

This avoids needing a hash sidecar entirely AND correctly reflects
actual git history.
"""
from __future__ import annotations

import hashlib
import io
import json
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
AUTO_REGEN_SUBJECT_RE = (
    r"^auto-regen (canonical generated files|/en/ mirror \+ feeds \+ runtime bundles)"
)

sys.path.insert(0, str(ROOT))
from _html_scan import blank_script_style, mask_inert_regions  # noqa: E402

# CODE_REVIEW SEO-3 — the date used to come from `git log -1` with auto-regen
# commits filtered out BY SUBJECT PREFIX. Any site-wide maintenance commit that
# was not literally titled "auto-regen …" therefore reset every article's
# freshness at once: d5e34076 ("seo: fix invalid ProfilePage dateModified +
# breadcrumb trailing-slash") touched 56 files and left all 55 articles
# claiming they were updated on 2026-07-06. One date shared by the whole
# corpus is not a freshness signal, it is noise — and it contradicted
# sitemap.xml, which was still emitting the per-article publication dates.
#
# The question "did the content change?" is now answered from the content
# rather than from a commit subject: the article's headline and Chinese prose
# are hashed, and the date only moves when that hash moves. The answers live
# in a committed ledger so a build needs no git history and no network, and so
# the decision is auditable in review rather than re-derived on every machine.
CONTENT_DATES = ROOT / "_content_dates.json"
TAG_RE = re.compile(r"<[^>]+>")

# Below this, extraction is broken rather than the article being short: a
# silently empty prose block would hash identically for every page and freeze
# every date at whatever the ledger already held.
MIN_PROSE_CHARS = 400


def _tag_start(dom: str, attr_index: int) -> int:
    """Index of the `<` opening the tag that `attr_index` points inside."""
    if attr_index == -1:
        return -1
    return dom.rfind("<", 0, attr_index)


def article_prose(src: str) -> str:
    """The physician-authored part of the page: headline + Chinese body.

    Deliberately NOT the whole document. Injected regions — related-article
    lists, reading time, the /en mirror — change when other articles are
    published, and letting those move a date would recreate the same
    everything-updated-at-once signal this replaced.
    """
    dom = blank_script_style(mask_inert_regions(src))
    heading = re.search(r"<h1\b[\s\S]*?</h1>", dom, re.I)
    # CODE_REVIEW TD-01 — the TL;DR sits between </h1> and the prose container,
    # so it was outside the hash and adding one to 29 articles did not register
    # as a content change. It is authored text about THIS article and changes
    # only when someone rewrites this article's summary — unlike the related-
    # article list or reading time, which move when OTHER articles are
    # published and are excluded for exactly that reason. Owner's call
    # (2026-08-01): a new summary counts as a content update.
    tldr = re.search(r'<div[^>]*class="dn-tldr"[\s\S]*?</div>', dom, re.I)
    start = _tag_start(dom, dom.find('id="proseZh"'))
    if start != -1:
        # CODE_REVIEW SEO-5 round 3 — both boundaries used to land INSIDE the
        # opening tag, on the `id="…"` attribute, so the rest of that tag came
        # through as text: TAG_RE cannot strip a fragment with no `<`, and the
        # hash literally contained `id="proseZh"class="prose"`. Editing the
        # container's CSS class then looked like a content change and restamped
        # the article. Both ends now cut at the tag itself.
        end = _tag_start(dom, dom.find('id="proseEn"', start))
        if end == -1:
            end = dom.find("</article>", start)
    else:
        # A few articles predate the bilingual split and have a single
        # <article class="prose"> instead. The related-article list is emitted
        # AFTER </article>, so this stays free of injected content.
        start = dom.find("<article")
        if start == -1:
            return ""
        end = dom.find("</article>", start)
    body = dom[start:end if end != -1 else len(dom)]
    text = ((heading.group(0) if heading else "")
            + (tldr.group(0) if tldr else "")
            + body)

    # Tags collapse to NOTHING and every space is dropped. Wrapping a phrase in
    # a <span> to hang a data-en translation on it is not an edit the reader
    # sees, but replacing each tag with a space made it look like one: the
    # first seeding run dated half the corpus to the day of the EN translation
    # sweep. What survives here is the character sequence a reader reads.
    return re.sub(r"\s+", "", TAG_RE.sub("", text))


def prose_hash(src: str) -> str | None:
    text = article_prose(src)
    if len(text) < MIN_PROSE_CHARS:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_ledger() -> dict[str, dict[str, str]]:
    if not CONTENT_DATES.exists():
        return {}
    try:
        data = json.loads(CONTENT_DATES.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        print(f"[date-modified] ledger unreadable ({exc}); falling back to git",
              file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def save_ledger(ledger: dict[str, dict[str, str]]) -> None:
    CONTENT_DATES.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def git_last_modified(path: Path) -> str | None:
    """Return YYYY-MM-DD of the last git commit that touched `path`.
    None if git is unavailable or the file isn't tracked yet.
    """
    try:
        rel = path.relative_to(ROOT).as_posix()
        result = subprocess.run(
            [
                "git", "log", "-1", "--format=%cs",
                "--extended-regexp", "--invert-grep",
                f"--grep={AUTO_REGEN_SUBJECT_RE}",
                "--", rel,
            ],
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
    ledger = load_ledger()
    ledger_before = json.dumps(ledger, sort_keys=True)
    content_moved: list[str] = []
    no_prose: list[str] = []

    for fp in sorted(BLOG.glob("*.html")):
        if fp.name in skip:
            continue

        digest = prose_hash(fp.read_text(encoding="utf-8"))
        if digest is None:
            # Extraction failed — do not guess. The old git-derived date is a
            # worse answer than before, but silently hashing an empty string
            # would freeze this article's date forever and look like success.
            no_prose.append(fp.name)
            last_touched = git_last_modified(fp) or today
        else:
            entry = ledger.get(fp.stem)
            if entry and entry.get("hash") == digest and entry.get("date"):
                last_touched = entry["date"]
            else:
                # First sighting, or the prose actually changed. Either way
                # today is when this text became what it is.
                last_touched = today
                if entry:
                    content_moved.append(fp.stem)
                ledger[fp.stem] = {"hash": digest, "date": today}

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

    if json.dumps(ledger, sort_keys=True) != ledger_before:
        save_ledger(ledger)

    print(f"[date-modified] bumped {total_bumped} JSON-LD/OG occurrences "
          f"across {pages_changed} articles; {pages_kept} already current")
    if content_moved:
        print(f"[date-modified] prose changed, dated {today}: "
              f"{', '.join(sorted(content_moved))}")
    if no_prose:
        print(f"[date-modified] WARN no #proseZh body found in "
              f"{len(no_prose)} page(s), fell back to git: "
              f"{', '.join(no_prose[:6])}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
