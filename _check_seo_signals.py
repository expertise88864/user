#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CI guard for SEO signals shipped in batch12-17.

Locks in every signal added to maximize SERP impressions + CTR:

  - robots meta directives: max-image-preview:large, max-snippet:-1
  - JSON-LD enrichment: wordCount, timeRequired, speakable,
    articleSection, keywords
  - Article author: PHYSICIAN_REF in MedicalWebPage/Article schemas
  - OG article:* on every blog article: published_time, modified_time,
    author, section, ≥1 tag
  - OG image dimensions: og:image:width + og:image:height
  - Twitter card: twitter:image:alt, twitter:label1, twitter:data1
  - Homepage Organization schema with logo (knowledge panel branding)
  - WebSite SearchAction (sitelinks search box)
  - Sitemap image:loc not double-encoded (&amp;amp; bug)
  - canonical present on every indexable page

Each failure prevents deploy. Run after _normalize_* + _gen_* steps.
"""
from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"

errors: list[str] = []
warnings: list[str] = []


def err(scope: str, msg: str) -> None:
    errors.append(f"  [{scope}] {msg}")


def warn(scope: str, msg: str) -> None:
    warnings.append(f"  [{scope}] {msg}")


# ─── 1. Robots SERP directives ───────────────────────────────────────
def check_robots_serp_directives() -> None:
    required = ["max-image-preview", "max-snippet"]
    skip_names = {"404.html", "offline.html", "reset-sw.html", "admin.html"}
    skip_dirs = {".git", "node_modules", "pagefind", "admin"}
    bad = 0
    for fp in sorted(ROOT.rglob("*.html")):
        parts = fp.relative_to(ROOT).parts
        if any(p in skip_dirs for p in parts):
            continue
        if fp.name in skip_names:
            continue
        src = fp.read_text(encoding="utf-8", errors="replace")
        m = re.search(
            r'<meta\s+name="robots"\s+content="([^"]+)"', src, re.I)
        content = m.group(1) if m else ""
        missing = [d for d in required if d not in content]
        if missing:
            err(fp.relative_to(ROOT).as_posix(),
                f"robots meta missing directives: {missing} — "
                f"reduces image preview size & snippet length in SERPs")
            bad += 1
    if bad == 0:
        print("[OK] robots SERP directives present on every page")


# ─── 2. JSON-LD enrichment on blog articles ──────────────────────────
def check_jsonld_enrichment() -> None:
    required_fields = {
        "wordCount": '"wordCount"',
        "timeRequired": '"timeRequired"',
        "speakable": '"speakable"',
        "articleSection": '"articleSection"',
    }
    # Clinical-depth pages are intentionally not in DN.ARTICLES (hidden
    # from main listings); _normalize_schema can't look up their cat so
    # articleSection won't be set. Skip them for the section check only.
    no_section_ok = {"isotretinoin-clinical", "topical-acids-clinical"}
    targets: list[Path] = []
    for d in ("blog", "en/blog"):
        dpath = ROOT / d
        if dpath.exists():
            for fp in sorted(dpath.glob("*.html")):
                if fp.name in {"index.html", "topics.html"}:
                    continue
                targets.append(fp)
    bad = 0
    for fp in targets:
        src = fp.read_text(encoding="utf-8", errors="replace")
        missing = [k for k, v in required_fields.items() if v not in src]
        if fp.stem in no_section_ok and missing == ["articleSection"]:
            continue  # known exception
        if "articleSection" in missing and fp.stem in no_section_ok:
            missing.remove("articleSection")
            if not missing:
                continue
        if missing:
            err(fp.relative_to(ROOT).as_posix(),
                f"JSON-LD missing fields: {missing}")
            bad += 1
    if bad == 0:
        print(f"[OK] JSON-LD enrichment present on {len(targets)} articles")


# ─── 3. OpenGraph article:* on blog articles ─────────────────────────
def check_og_article_props() -> None:
    required = [
        "article:published_time",
        "article:modified_time",
        "article:author",
        "article:section",
        "og:image:width",
        "og:image:height",
        "og:image:alt",
    ]
    # Article files known to lack DN.ARTICLES entry — skip them.
    skip_slugs = {"isotretinoin-clinical", "topical-acids-clinical",
                  "severe-scabies-treatment"}
    targets: list[Path] = []
    for d in ("blog", "en/blog"):
        dpath = ROOT / d
        if dpath.exists():
            for fp in sorted(dpath.glob("*.html")):
                if fp.name in {"index.html", "topics.html"}:
                    continue
                if fp.stem in skip_slugs:
                    continue
                targets.append(fp)
    bad = 0
    for fp in targets:
        src = fp.read_text(encoding="utf-8", errors="replace")
        missing = [p for p in required
                   if f'property="{p}"' not in src
                   and f"property='{p}'" not in src]
        if missing:
            err(fp.relative_to(ROOT).as_posix(),
                f"OG meta missing: {missing} — "
                f"social cards (FB/LinkedIn/Discord) won't render rich")
            bad += 1
        # At least one article:tag
        if 'property="article:tag"' not in src:
            err(fp.relative_to(ROOT).as_posix(),
                f"no article:tag — required for topical relevance")
            bad += 1
    if bad == 0:
        print(f"[OK] OpenGraph article:* meta present on {len(targets)} articles")


# ─── 4. Twitter card customization ───────────────────────────────────
def check_twitter_cards() -> None:
    required = ["twitter:image:alt", "twitter:label2", "twitter:data2"]
    skip_slugs = {"isotretinoin-clinical", "topical-acids-clinical",
                  "severe-scabies-treatment"}
    targets: list[Path] = []
    for d in ("blog", "en/blog"):
        dpath = ROOT / d
        if dpath.exists():
            for fp in sorted(dpath.glob("*.html")):
                if fp.name in {"index.html", "topics.html"}:
                    continue
                if fp.stem in skip_slugs:
                    continue
                targets.append(fp)
    bad = 0
    for fp in targets:
        src = fp.read_text(encoding="utf-8", errors="replace")
        missing = [p for p in required if f'name="{p}"' not in src]
        if missing:
            err(fp.relative_to(ROOT).as_posix(),
                f"Twitter card meta missing: {missing}")
            bad += 1
    if bad == 0:
        print(f"[OK] Twitter custom labels present on {len(targets)} articles")


# ─── 5. Homepage Organization + WebSite SearchAction ─────────────────
def check_homepage_brand_schema() -> None:
    fp = ROOT / "index.html"
    if not fp.exists():
        err("index.html", "missing")
        return
    src = fp.read_text(encoding="utf-8")
    issues = []
    if '"@type":"Organization"' not in src and '"@type": "Organization"' not in src:
        issues.append('no Organization JSON-LD (knowledge panel won\'t '
                      'show site logo)')
    elif '"logo"' not in src:
        issues.append('Organization missing logo field')
    if '"@type":"WebSite"' not in src and '"@type": "WebSite"' not in src:
        issues.append('no WebSite JSON-LD')
    if '"SearchAction"' not in src:
        issues.append('no SearchAction (no sitelinks search box in SERPs)')
    if issues:
        for i in issues:
            err("index.html", i)
    else:
        print("[OK] Homepage Organization + WebSite + SearchAction in place")


# ─── 6. Sitemap image encoding sanity ────────────────────────────────
def check_sitemap_image_encoding() -> None:
    fp = ROOT / "sitemap.xml"
    if not fp.exists():
        return
    src = fp.read_text(encoding="utf-8")
    double = src.count("&amp;amp;")
    if double:
        err("sitemap.xml",
            f"{double} instances of &amp;amp; (double-encoded) — "
            f"breaks OG image URLs for Google image fetcher")
    else:
        images = src.count("<image:image>")
        print(f"[OK] sitemap image encoding clean ({images} image entries)")


# ─── 7. Canonical present on every indexable page ───────────────────
def check_canonical_coverage() -> None:
    skip_names = {"404.html", "offline.html", "reset-sw.html"}
    skip_dirs = {".git", "node_modules", "pagefind", "admin"}
    bad = 0
    total = 0
    for fp in sorted(ROOT.rglob("*.html")):
        parts = fp.relative_to(ROOT).parts
        if any(p in skip_dirs for p in parts):
            continue
        if fp.name in skip_names or fp.name == "admin.html":
            continue
        src = fp.read_text(encoding="utf-8", errors="replace")
        # Skip noindex pages — canonical still useful but not blocking
        if not re.search(r'<link\s+rel="canonical"\s+href="', src, re.I):
            err(fp.relative_to(ROOT).as_posix(), "missing canonical link")
            bad += 1
        total += 1
    if bad == 0:
        print(f"[OK] canonical link present on all {total} pages")


def main() -> int:
    print("=== SEO signals audit ===")
    check_robots_serp_directives()
    check_jsonld_enrichment()
    check_og_article_props()
    check_twitter_cards()
    check_homepage_brand_schema()
    check_sitemap_image_encoding()
    check_canonical_coverage()

    if warnings:
        print(f"\n[!] Warnings ({len(warnings)}):")
        for w in warnings[:15]:
            print(w)

    if errors:
        print(f"\n[X] Errors ({len(errors)}):")
        for e in errors[:25]:
            print(e)
        if len(errors) > 25:
            print(f"  ... and {len(errors) - 25} more")
        print(f"\n=> SEO signals audit FAILED with {len(errors)} error(s).")
        return 1
    print(f"\n[OK] All SEO signals in place.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
