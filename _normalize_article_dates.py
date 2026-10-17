#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Show both article dates in the header pill above each article's <h1>.

Owner's decision (2026-10-17): the header reads
  內容更新 <content date> · 醫師審閱 <review date>
  Content updated <content date> · Physician reviewed <review date>

The two dates are different claims and come from different ledgers:
- content date = _content_dates.json, which _normalize_date_modified.py keeps
  tied to a hash of the physician-authored prose and writes to JSON-LD
  dateModified. This script reads it after that step and never writes it.
- review date = _review_dates.json, the physician's own declaration that only
  _record_review.py writes (TD-74), published as JSON-LD lastReviewed. This
  script only reads it; nothing here may move a review claim.

The header used to carry ONE hand-typed "更新 YYYY-MM-DD" date that nothing
maintained: nhi-derm-drugs kept "更新 2026-05-05" after its NHI 115/9/22
rewrite moved dateModified to 2026-10-16, so readers concluded the NHI rules
had not been updated. That stale single-date text is removed here; a guideline
attribution sharing the same pill ("依 TDA 2024 共識 · 更新 …") keeps its
attribution and loses only the date.

The pill sits in the eyebrow <div> before <h1>, outside the prose that
_normalize_date_modified.py hashes, so writing it never moves the content
date. The eyebrow's own data-zh/data-en (if any) moves onto a <span> wrapping
its label: an element carrying data-en has its whole content replaced by
_gen_en_pages.py and by the runtime language switch, which used to drop the
date pill from the English mirror entirely.

Idempotent: the pill is marked data-dn-article-dates and rewritten in place.
Runs after _normalize_date_modified.py and before _gen_en_pages.py so the
English mirror inherits the data-en text.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
BLOG = ROOT / "blog"
CONTENT_DATES_FILE = ROOT / "_content_dates.json"
REVIEW_DATES_FILE = ROOT / "_review_dates.json"
SKIP = {"index.html", "topics.html"}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PILL_CLASS = ("ml-3 inline-block px-2 py-0.5 rounded-full bg-mint-100 text-teal-700 "
              "text-[10.5px] font-semibold normal-case tracking-normal")
MARKER = "data-dn-article-dates"

# The eyebrow is the uppercase label <div> immediately before the article <h1>.
# Its content is text and inline <span>s only, never another <div>.
EYEBROW_RE = re.compile(
    r'<div(?P<attrs>\s+class="text-\[11px\] uppercase[^"]*"[^>]*)>'
    r'(?P<inner>(?:(?!</?div\b)[\s\S])*?)</div>')
PILL_RE = re.compile(
    r'(?P<lead>\s*)<span(?P<attrs>\s+class="[^"]*\brounded-full\b[^"]*"[^>]*)>'
    r'(?P<inner>[^<]*)</span>')
DATES_PILL_RE = re.compile(
    rf'\s*<span\b[^>]*\b{MARKER}=""[^>]*>(?:<span\b[^>]*>[^<]*</span>|[^<])*</span>')
ATTR_RE = r'\s{name}="(?P<v>[^"]*)"'
# The retired single-date wording, at the end of a pill's text. A guideline
# attribution before it ("依 TDA 2024 共識 · ") is kept.
OLD_DATE_ZH = re.compile(r"(?:\s*·\s*)?更新(?:日期)?\s*(?:·\s*)?\d{4}-\d{2}-\d{2}\s*$")
OLD_DATE_EN = re.compile(r"(?:\s*·\s*)?Updated\s*(?:·\s*)?\d{4}-\d{2}-\d{2}\s*$", re.I)


def dates_pill(content: str, reviewed: str) -> str:
    """One pill, two non-breaking halves: on a phone it wraps at " · ", never
    inside a date ("2026-05-" / "04"). Each half carries its own data-zh /
    data-en; the outer pill carries none, so data-en rendering keeps both."""
    halves = ((f"內容更新 {content}", f"Content updated {content}"),
              (f"醫師審閱 {reviewed}", f"Physician reviewed {reviewed}"))
    inner = " · ".join(f'<span style="white-space:nowrap" data-zh="{zh}" '
                       f'data-en="{en}">{zh}</span>' for zh, en in halves)
    return f'<span class="{PILL_CLASS}" {MARKER}="">{inner}</span>'


def _ledger(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise SystemExit(f"[article-dates] cannot read {path.name}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"[article-dates] {path.name} is not an object")
    return {slug: entry["date"] for slug, entry in data.items()
            if not slug.startswith("_") and isinstance(entry, dict)
            and DATE_RE.match(str(entry.get("date", "")))}


def page_date_modified(src: str) -> str | None:
    """dateModified of the node that claims to BE this page (its canonical)."""
    canonical = re.search(r'<link\s+rel="canonical"\s+href="([^"]*)"', src, re.I)
    for m in re.finditer(r'<script type="application/ld\+json">([\s\S]*?)</script>', src):
        try:
            doc = json.loads(m.group(1))
        except ValueError:
            continue
        for node in (doc.get("@graph") or [doc]) if isinstance(doc, dict) else []:
            if not isinstance(node, dict):
                continue
            if node.get("@type") not in ("MedicalWebPage", "MedicalScholarlyArticle"):
                continue
            if canonical and node.get("mainEntityOfPage") != canonical.group(1):
                continue
            value = str(node.get("dateModified") or "")[:10]
            if DATE_RE.match(value):
                return value
    return None


def _attr(attrs: str, name: str) -> str | None:
    m = re.search(ATTR_RE.format(name=name), attrs)
    return m.group("v") if m else None


def _strip_old_date(text: str) -> str:
    return OLD_DATE_EN.sub("", OLD_DATE_ZH.sub("", text)).strip()


def _clean_pill(m: re.Match[str]) -> str:
    """Drop the old date from one pill; drop the pill if nothing else is left."""
    attrs, inner = m.group("attrs"), m.group("inner")
    zh, en = _attr(attrs, "data-zh"), _attr(attrs, "data-en")
    new_zh = _strip_old_date(zh) if zh is not None else None
    new_en = _strip_old_date(en) if en is not None else None
    new_inner = _strip_old_date(inner)
    if (new_zh, new_en, new_inner) == (zh, en, inner.strip()):
        return m.group(0)
    if not new_inner and not new_zh and not new_en:
        return ""
    if zh is not None:
        attrs = re.sub(ATTR_RE.format(name="data-zh"), f' data-zh="{new_zh}"', attrs, count=1)
    if en is not None:
        attrs = re.sub(ATTR_RE.format(name="data-en"), f' data-en="{new_en}"', attrs, count=1)
    if not new_inner:
        new_inner = new_zh or new_en or ""
    return f'{m.group("lead")}<span{attrs}>{new_inner}</span>'


def rewrite_eyebrow(src: str, content: str, reviewed: str) -> tuple[str, str | None]:
    """Return (new source, error). The source is unchanged when error is set."""
    h1 = re.search(r"<h1\b", src)
    if not h1:
        return src, "no <h1>"
    eyebrow = None
    for m in EYEBROW_RE.finditer(src, 0, h1.start()):
        eyebrow = m
    if eyebrow is None or src[eyebrow.end():h1.start()].strip():
        return src, "no eyebrow <div> directly before <h1>"
    attrs = eyebrow.group("attrs")
    inner = DATES_PILL_RE.sub("", eyebrow.group("inner"))  # re-emitted below

    zh, en = _attr(attrs, "data-zh"), _attr(attrs, "data-en")
    if zh is not None or en is not None:
        # Move the eyebrow's translation onto its label so the pills beside
        # it survive data-en rendering (see module docstring).
        cut = inner.find("<span")
        label = inner if cut == -1 else inner[:cut]
        if "<" in label:
            return src, "eyebrow label with markup cannot be wrapped"
        rest = "" if cut == -1 else inner[cut:]
        lang = "".join(f' data-{k}="{v}"' for k, v in (("zh", zh), ("en", en)) if v is not None)
        inner = f"<span{lang}>{label.strip()}</span> " + rest
        attrs = re.sub(r'\s+data-(?:zh|en)="[^"]*"', "", attrs)

    inner = PILL_RE.sub(_clean_pill, inner).rstrip()
    new_div = f"<div{attrs}>{inner} {dates_pill(content, reviewed)}</div>"
    return src[:eyebrow.start()] + new_div + src[eyebrow.end():], None


def main() -> int:
    content_dates = _ledger(CONTENT_DATES_FILE)
    review_dates = _ledger(REVIEW_DATES_FILE)
    changed = kept = 0
    problems: list[str] = []
    for fp in sorted(BLOG.glob("*.html")):
        if fp.name in SKIP:
            continue
        src = fp.read_text(encoding="utf-8")
        page_modified = page_date_modified(src)
        content = content_dates.get(fp.stem)
        if content is None:
            # _normalize_date_modified.py fell back to git history for a page
            # whose prose it could not extract; JSON-LD holds that answer.
            content = page_modified
        elif page_modified is not None and page_modified != content:
            problems.append(f"{fp.name}: {CONTENT_DATES_FILE.name} says {content} but "
                            f"JSON-LD dateModified is {page_modified}")
            continue
        reviewed = review_dates.get(fp.stem)
        if not content or not reviewed:
            problems.append(f"{fp.name}: missing "
                            f"{'content date' if not content else 'review date'}")
            continue
        new, error = rewrite_eyebrow(src, content, reviewed)
        if error:
            problems.append(f"{fp.name}: {error}")
            continue
        if new != src:
            fp.write_text(new, encoding="utf-8")
            changed += 1
        else:
            kept += 1
    print(f"[article-dates] header dates rewritten on {changed} article(s); "
          f"{kept} already current")
    for problem in problems:
        print(f"[article-dates] ERROR {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
