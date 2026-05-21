#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inject three high-ROI MedicalWebPage fields:

  1. `keywords` — comma-separated topic chain pulled from:
       a. The homepage card's data-tag-en (e.g. "Eczema", "Psoriasis")
       b. The MedicalCondition.alternateName already injected by
          _normalize_medical_codes.py (gives the Chinese disease name)
       c. Generic anchors: "dermatology", "patient education", site brand
     Bing + Yandex still use `keywords` for ranking; Google uses it as a
     topical-cluster signal even though it dropped meta-keywords years ago.

  2. `lastReviewed` — mirrors the git-derived dateModified that
     _normalize_date_modified.py already writes. Google's medical-content
     rich-result documentation specifically lists `lastReviewed` as the
     freshness signal for YMYL pages (different from dateModified, which
     can include trivial edits).

  3. `audience.audienceType` — differentiates Patient vs Clinician.
     Default Patient (most articles are patient-ed). Clinical-depth
     articles (slugs ending in -clinical / -systemic / -topical /
     -special-populations / -biologic-monitoring) get a dual
     ["Patient","Clinician"] audience so Google can surface them in
     professional dermatology SERPs too.

Runs LAST in REGEN_STEPS, after every other JSON-LD modifier, so the
fields it touches are stable.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
BLOG = ROOT / "blog"
EN_BLOG = ROOT / "en" / "blog"
INDEX = ROOT / "index.html"


# Articles whose slug suffix marks them as clinical-depth (intended for
# both patients AND clinicians). These get dual audience.
CLINICAL_SUFFIXES = (
    "-clinical",
    "-systemic",
    "-topical",
    "-special-populations",
    "-biologic-monitoring",
)


def slug_is_clinical(slug: str) -> bool:
    return any(slug.endswith(suf) for suf in CLINICAL_SUFFIXES)


# --- Homepage card metadata -------------------------------------------------

HOMEPAGE_CARD_RE = re.compile(
    r'<a[^>]*href="/blog/(?P<slug>[a-z0-9-]+)"'
    r'(?=[^>]*data-cat="(?P<cat>[^"]*)")'
    r'(?=[^>]*data-tag-en="(?P<tag_en>[^"]*)")'
    r'[^>]*class="article-list-item"',
    re.IGNORECASE,
)


def load_homepage_tags() -> dict[str, dict[str, str]]:
    """Return {slug: {cat, tag_en}} from index.html article-list cards."""
    if not INDEX.exists():
        return {}
    src = INDEX.read_text(encoding="utf-8")
    out: dict[str, dict[str, str]] = {}
    for m in HOMEPAGE_CARD_RE.finditer(src):
        out[m.group("slug")] = {
            "cat": m.group("cat"),
            "tag_en": m.group("tag_en"),
        }
    return out


# --- Git date helper (mirror of _normalize_date_modified.py) ----------------

def git_last_modified(path: Path) -> str | None:
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
    except Exception:
        return None


# --- JSON-LD block balanced-brace parser ------------------------------------

LD_START_RE = re.compile(
    r'<script\s+type="application/ld\+json"[^>]*>',
    re.IGNORECASE,
)


def iter_jsonld_blocks(src: str):
    """Yield (start_idx, end_idx, body) for each JSON-LD block."""
    for m in LD_START_RE.finditer(src):
        body_start = m.end()
        # Find matching </script>
        close = src.find('</script>', body_start)
        if close == -1:
            continue
        yield m.start(), close + len('</script>'), src[body_start:close]


def replace_jsonld_block(src: str, start: int, end: int,
                          opening_tag: str, new_obj: dict) -> str:
    body = json.dumps(new_obj, ensure_ascii=False, separators=(',', ':'))
    return src[:start] + opening_tag + body + '</script>' + src[end:]


# --- Keyword derivation -----------------------------------------------------

GENERIC_KEYWORDS_ZH = ["皮膚科", "衛教"]
GENERIC_KEYWORDS_EN = ["dermatology", "patient education"]


def derive_keywords(slug: str, tag_en: str,
                     about_value, is_en: bool) -> str:
    """Build a comma-separated keywords string for this article.

    Inputs:
      - tag_en: from homepage data-tag-en (may be empty)
      - about_value: the JSON-LD `about` field — either a single
        MedicalCondition dict, or a list of them. We harvest `name` +
        `alternateName` from each.
      - is_en: True for /en/blog/* mirror
    """
    parts: list[str] = []
    if tag_en:
        parts.append(tag_en)

    # Harvest names from existing MedicalCondition `about` field
    if about_value:
        if isinstance(about_value, dict):
            conds = [about_value]
        elif isinstance(about_value, list):
            conds = [c for c in about_value if isinstance(c, dict)]
        else:
            conds = []
        for cond in conds:
            if cond.get("@type") not in {"MedicalCondition", "MedicalProcedure"}:
                continue
            name = cond.get("name")
            if name and name not in parts:
                parts.append(name)
            alt = cond.get("alternateName")
            if isinstance(alt, list):
                for a in alt:
                    if a and a not in parts:
                        parts.append(a)
            elif isinstance(alt, str):
                if alt not in parts:
                    parts.append(alt)

    # Append generic anchors (locale-appropriate)
    if is_en:
        for g in GENERIC_KEYWORDS_EN:
            if g not in parts:
                parts.append(g)
    else:
        for g in GENERIC_KEYWORDS_ZH:
            if g not in parts:
                parts.append(g)
        # For ZH articles, also surface the English tag for cross-lingual
        # discoverability (Bing especially)
        if tag_en and not is_en:
            for g in GENERIC_KEYWORDS_EN:
                if g not in parts:
                    parts.append(g)

    return ", ".join(parts[:12])  # cap at 12 — over-stuffing penalizes ranking


# --- Single-article processor -----------------------------------------------

def process_article(fp: Path, homepage_tags: dict[str, dict[str, str]],
                     is_en: bool) -> bool:
    """Update MedicalWebPage block(s) in this article. Returns True if
    file was modified."""
    slug = fp.stem
    src = fp.read_text(encoding="utf-8")
    last_mod = git_last_modified(fp)

    tag_en = ""
    if slug in homepage_tags:
        tag_en = homepage_tags[slug].get("tag_en", "")

    clinical = slug_is_clinical(slug)

    new_src = src
    offset_drift = 0
    blocks = list(iter_jsonld_blocks(src))
    for start, end, body in blocks:
        opening_tag = src[start:src.find('>', start) + 1]
        try:
            obj = json.loads(body)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        typ = obj.get("@type")
        if typ not in {"MedicalWebPage", "MedicalScholarlyArticle"}:
            continue

        # ----- keywords -----
        keywords_str = derive_keywords(slug, tag_en, obj.get("about"), is_en)
        if keywords_str:
            obj["keywords"] = keywords_str

        # ----- lastReviewed -----
        if last_mod:
            obj["lastReviewed"] = last_mod

        # ----- audience differentiation -----
        if clinical:
            obj["audience"] = {
                "@type": "MedicalAudience",
                "audienceType": ["Patient", "Clinician"],
            }
        else:
            # Preserve existing audience but normalize to the schema.org
            # canonical form. _normalize_schema.py sets this; we just
            # ensure audienceType is present even on legacy blocks.
            existing = obj.get("audience")
            if not (isinstance(existing, dict)
                    and existing.get("audienceType")):
                obj["audience"] = {
                    "@type": "MedicalAudience",
                    "audienceType": "Patient",
                }

        # Splice the new block in, accounting for prior drift
        new_src = replace_jsonld_block(
            new_src,
            start + offset_drift,
            end + offset_drift,
            opening_tag,
            obj,
        )
        new_body = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
        new_block_len = len(opening_tag) + len(new_body) + len('</script>')
        old_block_len = end - start
        offset_drift += new_block_len - old_block_len

    if new_src != src:
        fp.write_text(new_src, encoding="utf-8")
        return True
    return False


# --- Main -------------------------------------------------------------------

def main() -> int:
    homepage_tags = load_homepage_tags()
    if not homepage_tags:
        print("[article-meta] WARN: no homepage cards parsed — keywords "
              "will fall back to MedicalCondition names only")
    total = 0
    for fp in sorted(BLOG.glob("*.html")):
        if process_article(fp, homepage_tags, is_en=False):
            total += 1
    for fp in sorted(EN_BLOG.glob("*.html")):
        if process_article(fp, homepage_tags, is_en=True):
            total += 1
    print(f"[article-meta] injected keywords + lastReviewed + audience "
          f"into {total} article files ({len(homepage_tags)} homepage "
          f"tags loaded)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
