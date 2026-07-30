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
    # CODE_REVIEW TD-51 — this used to skip three slugs WHOLESALE because they
    # lacked a DN.ARTICLES entry. Two problems: severe-scabies-treatment is in
    # the catalog and carries every property, so its exemption hid nothing but
    # cost coverage; and the two clinical pages are indexable, sitemapped and
    # internally linked, so blanket-skipping them meant nothing noticed they
    # had NO og-extras block at all. _normalize_og_article_meta now injects the
    # catalog-independent fields there, so the exemption is narrowed to exactly
    # the two properties that genuinely need a catalog record (cat -> section,
    # tag -> article:tag) and everything else is enforced everywhere.
    catalog_only_props = {"article:section", "article:tag"}
    no_catalog_slugs = {"isotretinoin-clinical", "topical-acids-clinical"}
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
        exempt = catalog_only_props if fp.stem in no_catalog_slugs else set()
        missing = [p for p in required
                   if p not in exempt
                   and f'property="{p}"' not in src
                   and f"property='{p}'" not in src]
        if missing:
            err(fp.relative_to(ROOT).as_posix(),
                f"OG meta missing: {missing} — "
                f"social cards (FB/LinkedIn/Discord) won't render rich")
            bad += 1
        # At least one article:tag
        if ("article:tag" not in exempt
                and 'property="article:tag"' not in src):
            err(fp.relative_to(ROOT).as_posix(),
                f"no article:tag — required for topical relevance")
            bad += 1
    if bad == 0:
        print(f"[OK] OpenGraph article:* meta present on {len(targets)} articles")


# ─── 4. Twitter card customization ───────────────────────────────────
def check_twitter_cards() -> None:
    # CODE_REVIEW TD-51 — none of these labels need a DN.ARTICLES record
    # (label2/data2 are constants, image:alt falls back to <title>), so the
    # three-slug exemption that used to sit here bought nothing and only
    # removed coverage. All three now carry every property; enforced for all.
    required = ["twitter:image:alt", "twitter:label2", "twitter:data2"]
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


# ─── 8. Schema uniqueness — no duplicate MedicalWebPage per article ──
def check_no_duplicate_medical_webpage() -> None:
    """CODE_REVIEW C1: every article must have exactly ONE MedicalWebPage
    JSON-LD block. Earlier normalize_schema bug left 46/48 articles with
    duplicates — now deduped in _normalize_schema.dedupe_jsonld_type.
    """
    import json
    pattern = re.compile(
        r'<script\s+type="application/ld\+json"[^>]*>([\s\S]*?)</script>',
        re.I)
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
        count = 0
        for m in pattern.finditer(src):
            try:
                obj = json.loads(m.group(1))
            except json.JSONDecodeError as _exc:
                # CODE_REVIEW 2026-05-25 — narrowed + logged.
                print(f"[check_seo_signals] skip malformed JSON-LD in {fp}: {_exc.msg}",
                      file=__import__('sys').stderr)
                continue
            if isinstance(obj, dict) and obj.get("@type") == "MedicalWebPage":
                count += 1
        if count > 1:
            err(fp.relative_to(ROOT).as_posix(),
                f"{count} MedicalWebPage JSON-LD blocks found — should be 1. "
                f"Run _normalize_schema.py to dedupe.")
            bad += 1
    if bad == 0:
        print(f"[OK] no duplicate MedicalWebPage blocks ({len(targets)} articles)")


# ─── 9. Speakable cssSelector must reference real DOM ────────────────
def check_speakable_selectors_resolve() -> None:
    """CODE_REVIEW C4: every selector in speakable.cssSelector must
    match at least one element on the page. Empty selectors leave
    Google Assistant TTS with no audio source.
    """
    import json
    pattern = re.compile(
        r'<script\s+type="application/ld\+json"[^>]*>([\s\S]*?)</script>',
        re.I)
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
        selectors: list[str] = []
        for m in pattern.finditer(src):
            try:
                obj = json.loads(m.group(1))
            except json.JSONDecodeError as _exc:
                # CODE_REVIEW 2026-05-25 — narrowed + logged.
                print(f"[check_seo_signals] skip malformed JSON-LD in {fp}: {_exc.msg}",
                      file=__import__('sys').stderr)
                continue
            if not isinstance(obj, dict):
                continue
            sp = obj.get("speakable")
            if isinstance(sp, dict):
                sel = sp.get("cssSelector")
                if isinstance(sel, list):
                    selectors.extend(sel)
        if not selectors:
            continue  # not all pages have speakable
        unresolved: list[str] = []
        for sel in selectors:
            # Lightweight check on the ROOT term of each selector. Strips
            # combinators (>, +, ~, ' ') and pseudo (:first-of-type, etc.)
            # before testing — we just want to detect "selector targets a
            # completely missing concept" (e.g., itemprop=description when
            # nothing on site uses itemprop). Exact CSS resolution would
            # require parsing the DOM.
            root = re.split(r'\s|>|\+|~', sel.strip(), maxsplit=1)[0]
            root = root.split(':', 1)[0]  # drop pseudo-class
            ok = False
            if root.startswith('#'):
                ok = f'id="{root[1:]}"' in src
            elif root.startswith('.'):
                cls = root[1:]
                ok = (f'class="{cls}"' in src
                      or f'class="{cls} ' in src
                      or f' {cls}"' in src
                      or f' {cls} ' in src)
            elif root.startswith('['):
                am = re.match(r"\[([a-zA-Z-]+)=['\"]([^'\"]+)['\"]\]", root)
                if am:
                    ok = f'{am.group(1)}="{am.group(2)}"' in src
            elif re.match(r'^[a-z][a-z0-9]*$', root):
                # Tag selector — h1, h2, p, div, etc.
                ok = f'<{root}' in src
            if not ok:
                unresolved.append(sel)
        # Spec allows multiple cssSelector entries — Google uses
        # whichever matches. Only flag if NONE resolve (which is the
        # original C4 bug). Partial overlap is fine and expected
        # across heterogeneous article templates.
        if unresolved and len(unresolved) == len(selectors):
            err(fp.relative_to(ROOT).as_posix(),
                f"NO speakable.cssSelector entries resolve to DOM: "
                f"{unresolved}")
            bad += 1
    if bad == 0:
        print(f"[OK] speakable selectors resolve on every article")


# ─── 10. llms-full.txt — no raw data-* attribute bleed ────────────────
def check_llms_full_clean() -> None:
    """CODE_REVIEW C2: llms-full.txt is the AI/LLM corpus. Any raw
    data-en / data-zh / data-cat attribute strings leaking into it
    confuse RAG ingestion (the LLM sees broken HTML in 'clean text').
    """
    fp = ROOT / "llms-full.txt"
    if not fp.exists():
        return
    src = fp.read_text(encoding="utf-8")
    issues = []
    for attr in ("data-en", "data-zh", "data-cat", "data-tag-en"):
        count = src.count(f'{attr}=')
        if count:
            issues.append(f"{count}× {attr}=")
    if issues:
        err("llms-full.txt",
            f"raw HTML attribute strings bleed into RAG corpus: {issues}. "
            f"Update _gen_llms_full.extract_clean_body to strip attrs "
            f"before tag stripping.")
    else:
        print(f"[OK] llms-full.txt has no raw attribute leakage")


# ─── 11. Hreflang reciprocity — every cross-link must round-trip ─────
def check_hreflang_reciprocity() -> None:
    """CODE_REVIEW: every ZH article that advertises `hreflang="en"`
    pointing at /en/blog/<slug> must have the EN counterpart on disk
    AND that EN page must back-link with `hreflang="zh-Hant"` to the
    ZH canonical. Google flags one-way hreflang clusters as broken
    and quietly drops them from the language alternate index.
    """
    zh_dir = ROOT / "blog"
    en_dir = ROOT / "en" / "blog"
    if not (zh_dir.exists() and en_dir.exists()):
        return
    bad = 0
    pairs_checked = 0
    for zh_fp in sorted(zh_dir.glob("*.html")):
        if zh_fp.name in {"index.html", "topics.html"}:
            continue
        zh_src = zh_fp.read_text(encoding="utf-8", errors="replace")
        # Look for the EN hreflang advertisement
        en_link_m = re.search(
            r'<link\s+rel="alternate"\s+hreflang="en"\s+href="([^"]+)"',
            zh_src, re.I)
        if not en_link_m:
            continue  # this article doesn't claim an EN mirror — fine
        en_url = en_link_m.group(1)
        # Resolve EN URL → local file
        if not en_url.startswith(f"{DOMAIN}/en/blog/"):
            err(zh_fp.relative_to(ROOT).as_posix(),
                f"hreflang en points outside /en/blog/: {en_url}")
            bad += 1
            continue
        en_slug = en_url[len(f"{DOMAIN}/en/blog/"):].rstrip("/")
        en_fp = en_dir / f"{en_slug}.html"
        if not en_fp.exists():
            err(zh_fp.relative_to(ROOT).as_posix(),
                f"hreflang en points at {en_url} but file missing on disk")
            bad += 1
            continue
        en_src = en_fp.read_text(encoding="utf-8", errors="replace")
        # EN must back-link
        zh_back = re.search(
            r'<link\s+rel="alternate"\s+hreflang="zh(?:-Hant(?:-TW)?)?"\s+href="([^"]+)"',
            en_src, re.I)
        if not zh_back:
            err(en_fp.relative_to(ROOT).as_posix(),
                f"missing back-link hreflang=zh-* to ZH source "
                f"{zh_fp.relative_to(ROOT).as_posix()}")
            bad += 1
            continue
        pairs_checked += 1
    if bad == 0:
        print(f"[OK] hreflang reciprocity verified on {pairs_checked} ZH→EN pairs")


# ─── 11b. hreflang must not point to a noindex page ──────────────────
def check_hreflang_targets_indexable() -> None:
    """SEO_AUDIT A4 (CI codification): if a ZH page advertises
    hreflang="en" pointing at /en/blog/<slug>, the EN file must
    NOT be noindex. Google's hreflang docs say noindex pages
    should not be part of an alternate cluster — including them
    causes Google to silently drop the cluster.

    This guard catches the regression mode where a ZH article gets
    a stale hreflang en link to a noindex EN counterpart.
    """
    zh_dir = ROOT / "blog"
    en_dir = ROOT / "en" / "blog"
    if not (zh_dir.exists() and en_dir.exists()):
        return
    bad = 0
    for zh_fp in sorted(zh_dir.glob("*.html")):
        if zh_fp.name in {"index.html", "topics.html"}:
            continue
        zh_src = zh_fp.read_text(encoding="utf-8", errors="replace")
        en_link_m = re.search(
            r'<link\s+rel="alternate"\s+hreflang="en"\s+href="([^"]+)"',
            zh_src, re.I)
        if not en_link_m:
            continue  # no advertised cluster, fine
        en_url = en_link_m.group(1)
        if not en_url.startswith(f"{DOMAIN}/en/blog/"):
            continue
        en_slug = en_url[len(f"{DOMAIN}/en/blog/"):].rstrip("/")
        en_fp = en_dir / f"{en_slug}.html"
        if not en_fp.exists():
            continue  # caught by check_hreflang_reciprocity
        en_src = en_fp.read_text(encoding="utf-8", errors="replace")
        if re.search(r'<meta[^>]+name="robots"[^>]+content="[^"]*noindex',
                     en_src, re.I):
            err(zh_fp.relative_to(ROOT).as_posix(),
                f"hreflang en advertises noindex page: {en_url} — "
                f"Google will drop the alternate cluster. Either make "
                f"the EN page indexable OR remove the hreflang en line "
                f"from the ZH source.")
            bad += 1
    if bad == 0:
        print(f"[OK] no hreflang en pointing to noindex EN pages")


# ─── 12. Mojibake detector — no literal '????' bleed in data-* attrs ──
def check_no_mojibake_in_data_attrs() -> None:
    """CODE_REVIEW (post-launch) — detected on 2026-05-19 that
    blog/index.html + en/blog/index.html each carried one hand-injected
    article card where every CJK char in data-zh / text content was
    replaced with literal '?' (likely from a cp950 console paste or
    an ASCII-coerced copy step).

    Heuristic: any `data-(zh|en|cat|tag)="...??...??..."` value with
    3+ consecutive '?' chars is almost certainly mojibake, not real
    content. Catches both pre-baked cards in index files and any
    future hand-edits.

    The dynamic loader in blog-hub.js renders cards from DN.ARTICLES
    (which carries proper UTF-8), so stray static cards are usually
    duplicates anyway — best to delete rather than repair.
    """
    skip_dirs = {".git", "node_modules", "pagefind", "admin"}
    skip_names = {"404.html", "offline.html", "reset-sw.html",
                  "admin.html", "CODE_REVIEW.md"}
    bad = 0
    # Match `data-WHATEVER="...???..."` or chip body with 3+ literal ?s
    mojibake_attr_re = re.compile(
        r'data-(?:zh|en|cat|tag|tag-en|emoji)="[^"]*\?{3,}[^"]*"',
        re.IGNORECASE,
    )
    for fp in sorted(ROOT.rglob("*.html")):
        parts = fp.relative_to(ROOT).parts
        if any(p in skip_dirs for p in parts):
            continue
        if fp.name in skip_names:
            continue
        src = fp.read_text(encoding="utf-8", errors="replace")
        m = mojibake_attr_re.search(src)
        if m:
            err(fp.relative_to(ROOT).as_posix(),
                f"mojibake in data-* attribute (3+ consecutive '?' literals): "
                f"{m.group(0)[:80]}... — likely cp950/ASCII coercion damage. "
                f"Delete the offending card if it's a hand-injected duplicate "
                f"of a DN.ARTICLES entry; the dynamic loader will render it.")
            bad += 1
    if bad == 0:
        print(f"[OK] no mojibake '????' literals detected in data-* attrs")


# ─── 13. Drug schema MUST BE ABSENT (GSC WNC-10030322 fix 2026-05-23) ─
def check_drug_schema_present() -> None:
    """INVERTED 2026-05-23: Drug schema was retracted because Google
    Search Console started flagging the blocks as "Product snippets"
    requiring offers / review / aggregateRating (WNC-10030322).

    Now we check the OPPOSITE: no article should carry a dn-drug-schema
    block. If one drifts back in (e.g., from a half-reverted commit or
    a stale local edit), the build should fail until cleaned.
    """
    blog = ROOT / "blog"
    en_blog = ROOT / "en" / "blog"
    stray = 0
    for base in (blog, en_blog):
        if not base.exists():
            continue
        for fp in sorted(base.glob("*.html")):
            src = fp.read_text(encoding="utf-8", errors="replace")
            if 'id="dn-drug-schema"' in src:
                err(fp.relative_to(ROOT).as_posix(),
                    "carries <script id=\"dn-drug-schema\"> block — "
                    "Drug schema was retracted 2026-05-23 to fix GSC "
                    "Product-snippet validation error. Re-run "
                    "_normalize_drug_schema.py to strip.")
                stray += 1
    if stray == 0:
        print("[OK] Drug schema correctly absent (GSC WNC-10030322 fix)")


# ─── 14. Citations @graph present on every blog article ──────────────
def check_citations_block_present() -> None:
    """Every indexable blog article must carry `<script id="dn-citations">`
    with a non-empty ScholarlyArticle @graph. Locks in the 673 Vancouver
    refs auto-parsed and shipped 2026-05-21.
    Skip articles where the references section is intentionally empty
    (FAQ pages, NHI policy summaries)."""
    skip = {"dermatology-faq", "nhi-derm-drugs"}
    blog = ROOT / "blog"
    if not blog.exists():
        return
    missing = 0
    for fp in sorted(blog.glob("*.html")):
        if fp.stem in skip or fp.name in {"index.html", "topics.html"}:
            continue
        src = fp.read_text(encoding="utf-8", errors="replace")
        if 'id="dn-citations"' not in src:
            # Check whether the article has a references section at all
            if '<ol class="references"' in src:
                err(fp.relative_to(ROOT).as_posix(),
                    "has <ol class=\"references\"> but no "
                    "<script id=\"dn-citations\"> block — re-run "
                    "_normalize_citations.py")
                missing += 1
    if missing == 0:
        print(f"[OK] Citation @graph blocks present on all articles with references")


# ─── 15. Glossary DefinedTermSet populated (≥50 entries) ─────────────
def check_glossary_termset_populated() -> None:
    """Both glossary pages must carry a DefinedTermSet with at least 50
    hasDefinedTerm entries. Catches legacy-stub regression (the page
    historically shipped a `DefinedTermSet` block with `hasDefinedTerm:
    []` — empty schema is worse than no schema)."""
    import json as _json
    for rel in ("glossary.html", "en/glossary.html"):
        fp = ROOT / rel
        if not fp.exists():
            continue
        src = fp.read_text(encoding="utf-8", errors="replace")
        found = False
        for m in re.finditer(
            r'<script type="application/ld\+json">([\s\S]*?)</script>',
            src,
        ):
            try:
                obj = _json.loads(m.group(1))
            except _json.JSONDecodeError:
                continue
            if obj.get("@type") != "DefinedTermSet":
                continue
            terms = obj.get("hasDefinedTerm") or []
            if not isinstance(terms, list) or len(terms) < 50:
                err(rel,
                    f"DefinedTermSet has only {len(terms) if isinstance(terms, list) else 0} "
                    f"hasDefinedTerm entries (≥50 required) — re-run "
                    f"_normalize_glossary_schema.py")
                continue
            found = True
            break
        if not found:
            err(rel, "no populated DefinedTermSet found")
    if not any('glossary' in e for e in errors[-2:]):
        print(f"[OK] Glossary DefinedTermSet populated (≥50 entries on each locale)")


# ─── 16. WebApplication @graph on /tools (≥10 apps) ──────────────────
def check_tools_schema_present() -> None:
    """tools.html (+ EN mirror) must carry a populated WebApplication
    @graph (≥10 apps) — one per calculator. Lower count = regression
    on the 2026-05-21 calculator-schema shipment."""
    import json as _json
    for rel in ("tools.html", "en/tools.html"):
        fp = ROOT / rel
        if not fp.exists():
            continue
        src = fp.read_text(encoding="utf-8", errors="replace")
        m = re.search(
            r'<script type="application/ld\+json" id="dn-tools-schema">'
            r'([\s\S]*?)</script>',
            src,
        )
        if not m:
            err(rel, "no <script id=\"dn-tools-schema\"> block found — "
                     "re-run _normalize_tools_schema.py")
            continue
        try:
            obj = _json.loads(m.group(1))
        except _json.JSONDecodeError:
            err(rel, "dn-tools-schema block is not valid JSON")
            continue
        graph = obj.get("@graph") or []
        if len(graph) < 10:
            err(rel,
                f"dn-tools-schema @graph has {len(graph)} apps (≥10 required)")
    if not any('tools' in e for e in errors[-2:]):
        print(f"[OK] Tools WebApplication @graph populated (≥10 apps on each locale)")


# ─── 17. Article metadata: keywords + lastReviewed + audience ────────
def check_article_metadata_fields() -> None:
    """Every MedicalWebPage block on a blog article must carry the
    three fields shipped on 2026-05-21:
      - keywords (string)
      - lastReviewed (YYYY-MM-DD)
      - audience.audienceType (Patient or [Patient,Clinician])
    Missing any of these = regression on _normalize_article_metadata.py
    """
    import json as _json
    blog = ROOT / "blog"
    if not blog.exists():
        return
    skip = {"index.html", "topics.html"}
    bad = 0
    for fp in sorted(blog.glob("*.html")):
        if fp.name in skip:
            continue
        src = fp.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(
            r'<script type="application/ld\+json">([\s\S]*?)</script>',
            src,
        ):
            try:
                obj = _json.loads(m.group(1))
            except _json.JSONDecodeError:
                continue
            if obj.get("@type") != "MedicalWebPage":
                continue
            missing = []
            if not obj.get("keywords"):
                missing.append("keywords")
            if not obj.get("lastReviewed"):
                missing.append("lastReviewed")
            aud = obj.get("audience")
            if not (isinstance(aud, dict) and aud.get("audienceType")):
                missing.append("audience.audienceType")
            if missing:
                err(fp.relative_to(ROOT).as_posix(),
                    f"MedicalWebPage missing field(s): {', '.join(missing)} — "
                    f"re-run _normalize_article_metadata.py")
                bad += 1
            break
    if bad == 0:
        print(f"[OK] Article keywords + lastReviewed + audience fields present")


def check_no_ad_placeholder_text() -> None:
    """CODE_REVIEW TD-49 — SEO_AUDIT A2 stripped the visible '廣告位 · AdSense'
    placeholder from ad-slot divs so Googlebot stops indexing empty ad inventory,
    but nothing asserted the result. `_normalize_ad_slots.py` fails soft (it just
    reports how many it cleared and returns 0), so if its anchors ever stop
    matching, the placeholder text quietly returns to indexable pages with a
    green gate. This is the missing product-side control for that generator.
    """
    # Scoped to ad-slot elements so prose that legitimately discusses AdSense is
    # never flagged. The placeholder forms are enumerated INDEPENDENTLY of
    # _normalize_ad_slots.PLACEHOLDER_BODY_RE on purpose — same rule as
    # _check_robots.REQUIRED_BLOCKED: importing the generator's pattern would let
    # a future narrowing of the stripper silently narrow this guard with it.
    # Keep this list a superset of what the stripper handles.
    # Match ANY element whose class token list contains ad-slot, with either
    # quote style — not just `<div class="...">`. Copying the normalizer's
    # narrower anchor would inherit its blind spots (e.g. `<section>` or
    # single-quoted attributes) and defeat the point of an independent product
    # assertion. The body is compared after stripping nested tags so
    # `<span>AdSense</span>` inside the slot is still caught.
    # Match only the OPENING tag, then read forward to its closing tag. Matching
    # the whole element in one regex looks tidier but silently misses nested
    # slots: an enclosing `<div class="prose">…` matches first and finditer
    # resumes after it, swallowing the ad-slot inside. (Caught by testing a slot
    # inserted into a real article rather than a bare string.)
    slot_open_re = re.compile(
        r"""<(?P<tag>[a-z][\w-]*)\b[^>]*\bclass\s*=\s*(?P<q>["'])(?P<cls>[^"']*)(?P=q)[^>]*>""",
        re.I,
    )
    placeholder_body_re = re.compile(
        r'^\s*(?:廣告位\s*[·•]?\s*AdSense|廣告位|Ad\s+slot[^<]*|Ad\s+placement[^<]*|AdSense)\s*$',
        re.I,
    )
    # Either quote style, to match slot_open_re — a single-quoted
    # data-zh='廣告位' is just as invisible to a reader of the rendered page.
    placeholder_attr_re = re.compile(
        r"""\bdata-(?:zh|en)\s*=\s*(?P<aq>["'])\s*"""
        r"""(?:廣告位|Ad\s+slot|Ad\s+placement|AdSense)[^"']*(?P=aq)""",
        re.I,
    )
    bad = 0
    for fp in sorted(ROOT.rglob("*.html")):
        rel = fp.relative_to(ROOT).as_posix()
        if any(part in {".git", "node_modules", "pagefind"} for part in fp.relative_to(ROOT).parts):
            continue
        src = fp.read_text(encoding="utf-8", errors="replace")
        if re.search(r'<meta\s+name="robots"\s+content="[^"]*noindex', src, re.I):
            continue
        for m in slot_open_re.finditer(src):
            if "ad-slot" not in m.group("cls").split():
                continue
            # Depth-balanced close: taking the FIRST </tag> would stop at a
            # same-tag child, e.g. `<div class="ad-slot"><div/>AdSense</div>`
            # would yield only the inner div and miss the visible placeholder.
            # Same counting approach as _normalize_schema._extract_prose_container.
            tag = m.group("tag")
            tag_re = re.compile(rf"<(?P<slash>/?){re.escape(tag)}\b[^>]*>", re.I)
            depth, pos, end = 1, m.end(), None
            while depth > 0:
                nxt = tag_re.search(src, pos)
                if not nxt:
                    break
                depth += -1 if nxt.group("slash") else 1
                pos = nxt.end()
                if depth == 0:
                    end = nxt.start()
            body = src[m.end():end] if end is not None else src[m.end():m.end() + 300]
            rendered = re.sub(r"<[^>]+>", "", body)
            if placeholder_body_re.match(rendered) or placeholder_attr_re.search(m.group(0)):
                err(rel, "indexable page still renders ad-slot placeholder text/attrs "
                         "— re-run _normalize_ad_slots.py")
                bad += 1
                break
    if bad == 0:
        print("[OK] No ad-slot placeholder text on indexable pages")


# ─── 20. Share images are rasters, sized, and per-page ───────────────
# CODE_REVIEW SEO-1/2/4 — every rule below is a defect that shipped, not a
# hypothetical. og:image pointed at /api/og on 28 articles and on support.html,
# and that endpoint answers image/svg+xml, which Facebook, X and LINE all
# ignore: those pages shared with no preview card at all, for months, while
# every checker here reported success. The homepage shared a 512x512 logo.
# Ten pages declared no dimensions. And the JSON-LD `image` on 55 articles was
# the site logo, so Search and Discover drew the same thumbnail for all of them.
SHARE_PAGE_SKIP = {"404.html", "offline.html", "admin.html", "reset-sw.html"}
RASTER_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
MIN_SHARE_PAGES = 55
MIN_SITEMAP_ARTICLES = 50      # a noindex article is legitimately not listed
MIN_CARD_EDGE = 600            # Facebook/X want >=600px on the short side


def _share_pages() -> list[Path]:
    pages = [p for p in sorted(ROOT.glob("*.html")) if p.name not in SHARE_PAGE_SKIP]
    pages += [p for p in sorted((ROOT / "blog").glob("*.html"))]
    return pages


def _local_asset(url: str) -> Path | None:
    if not url.startswith(DOMAIN + "/"):
        return None
    return ROOT / url[len(DOMAIN) + 1:].split("?")[0]


def check_share_images() -> None:
    from _normalize_social_images import image_size

    pages = _share_pages()
    bad = 0
    sized = 0
    for fp in pages:
        rel = fp.relative_to(ROOT).as_posix()
        src = fp.read_text(encoding="utf-8", errors="replace")
        # CODE_REVIEW SEO-5 round 2 — twitter:image used to get the suffix
        # tests but never the does-it-exist test, so pointing it at
        # https://example.com/nope.png passed. Both fields now go through the
        # same resolution, and they must agree: two different share images for
        # one page is a defect whichever one is wrong.
        urls: dict[str, str] = {}
        for prop, attr in (("og:image", "property"), ("twitter:image", "name")):
            found = re.findall(rf'<meta\s+{attr}="{prop}"\s+content="([^"]+)"',
                               src, re.I)
            if not found:
                err(rel, f"no {prop} — the page has no share card")
                bad += 1
                continue
            # CODE_REVIEW SEO-5 round 3 — this used re.search and looked at the
            # first match only, so 44 articles carrying TWO twitter:image tags
            # passed. They agreed at the time, which is precisely why nobody
            # would notice until they stopped agreeing and a crawler took the
            # stale one.
            if len(found) > 1:
                err(rel, f"{len(found)} {prop} tags — a page has one share "
                         f"image, and a crawler may pick either: {sorted(set(found))}")
                bad += 1
            url = found[0]
            urls[prop] = url
            if "/api/og" in url:
                err(rel, f"{prop} points at /api/og, which serves image/svg+xml; "
                         f"no major platform renders an SVG share card")
                bad += 1
            elif not url.lower().endswith(RASTER_SUFFIXES):
                err(rel, f"{prop} is not a raster image: {url}")
                bad += 1
            elif "logo-512" in url:
                err(rel, f"{prop} is the 512x512 site logo, not a card for this "
                         f"page — run: python _gen_og_cards.py")
                bad += 1
            else:
                asset = _local_asset(url)
                if asset is None or not asset.exists():
                    err(rel, f"{prop} does not resolve to a committed file: {url}")
                    bad += 1
        if len(urls) == 2 and urls["og:image"] != urls["twitter:image"]:
            err(rel, f"og:image and twitter:image disagree: "
                     f"{urls['og:image']} vs {urls['twitter:image']}")
            bad += 1

        og_url = urls.get("og:image")
        if not og_url:
            continue
        asset = _local_asset(og_url)
        if asset is None or not asset.exists():
            continue                    # already reported above
        size = image_size(asset)
        if size is None:
            # CODE_REVIEW SEO-5 round 2 — an unparsed file used to fall
            # straight into the success branch: a WebP or a truncated PNG
            # skipped BOTH the dimension match and the minimum-edge test, so a
            # corrupt share image would have been reported as verified.
            err(rel, f"share image cannot be decoded, so its dimensions cannot "
                     f"be verified: {og_url}")
            bad += 1
            continue
        declared = {}
        for key in ("og:image:width", "og:image:height"):
            dm = re.search(rf'<meta\s+property="{key}"\s+content="(\d+)"', src, re.I)
            declared[key] = int(dm.group(1)) if dm else None
        if declared["og:image:width"] is None or declared["og:image:height"] is None:
            err(rel, "og:image:width / og:image:height missing")
            bad += 1
        elif (declared["og:image:width"], declared["og:image:height"]) != size:
            err(rel, f"og:image dimensions declared "
                     f"{declared['og:image:width']}x{declared['og:image:height']} "
                     f"but the file is {size[0]}x{size[1]}")
            bad += 1
        else:
            sized += 1
        if max(size) < MIN_CARD_EDGE:
            err(rel, f"share image is only {size[0]}x{size[1]}; platforms want at "
                     f"least {MIN_CARD_EDGE}px on the long side")
            bad += 1

    if len(pages) < MIN_SHARE_PAGES:
        err("share-images", f"only {len(pages)} page(s) inspected (expected >= "
                            f"{MIN_SHARE_PAGES}) — discovery is broken")
    elif bad == 0:
        print(f"[OK] share images: {len(pages)} pages carry a per-page raster card, "
              f"{sized} with dimensions matching the file on disk")


def check_article_jsonld_image() -> None:
    """The article's structured-data image is its own card, not the site logo."""
    import json

    targets = [p for p in sorted((ROOT / "blog").glob("*.html"))
               if p.name not in {"index.html", "topics.html"}]
    bad = 0
    checked = 0
    # CODE_REVIEW SEO-5 round 2 — a node with no `image` used to be skipped,
    # and the global floor stayed satisfied by the other 61 blocks, so
    # DELETING an article's image passed the gate. Coverage is now per PAGE:
    # every article must carry at least one article node with a good image.
    for fp in targets:
        rel = fp.relative_to(ROOT).as_posix()
        src = fp.read_text(encoding="utf-8", errors="replace")
        good_on_page = 0
        nodes_on_page = 0
        for m in re.finditer(r'<script type="application/ld\+json">([\s\S]*?)</script>',
                             src):
            try:
                doc = json.loads(m.group(1))
            except ValueError:
                continue
            for node in (doc.get("@graph") or [doc]):
                if node.get("@type") not in ("MedicalWebPage", "MedicalScholarlyArticle"):
                    continue
                nodes_on_page += 1
                image = node.get("image")
                if image is None:
                    continue
                checked += 1
                url = image.get("url") if isinstance(image, dict) else image
                if not url or "logo-512" in str(url):
                    err(rel, f"{node.get('@type')} image is the site logo — Search "
                             f"and Discover pick their thumbnail from this field")
                    bad += 1
                elif f"/assets/og/{fp.stem}." not in str(url):
                    err(rel, f"{node.get('@type')} image is not this article's own "
                             f"card: {url}")
                    bad += 1
                else:
                    good_on_page += 1
        if nodes_on_page == 0:
            err(rel, "no MedicalWebPage / MedicalScholarlyArticle block at all")
            bad += 1
        elif good_on_page == 0:
            err(rel, "no article node carries this page's own card as its image — "
                     "Search and Discover have no thumbnail to pick")
            bad += 1
    if checked < MIN_SHARE_PAGES:
        err("article-jsonld-image",
            f"only {checked} article image field(s) seen (expected >= "
            f"{MIN_SHARE_PAGES}) — the scan found nothing to check")
    elif bad == 0:
        print(f"[OK] every article's JSON-LD image is its own card "
              f"({len(targets)} pages, {checked} blocks)")


def check_lastmod_matches_datemodified() -> None:
    """One freshness answer per URL, not two.

    CODE_REVIEW SEO-3 — <lastmod> was emitted from DN.ARTICLES' PUBLICATION
    date while the page's own dateModified said something else, so 54 of 57
    URLs carried two contradictory freshness claims.
    """
    sitemap = ROOT / "sitemap.xml"
    if not sitemap.exists():
        err("sitemap.xml", "missing")
        return
    entries = dict(re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>",
                              sitemap.read_text(encoding="utf-8", errors="replace")))
    bad = 0
    compared = 0
    for fp in sorted((ROOT / "blog").glob("*.html")):
        if fp.name in {"index.html", "topics.html"}:
            continue
        src = fp.read_text(encoding="utf-8", errors="replace")
        rel = fp.relative_to(ROOT).as_posix()
        # CODE_REVIEW SEO-5 round 2 — an article missing from sitemap.xml used
        # to be silently skipped, so DELETING URLs from the sitemap — the
        # failure that removes a page from discovery entirely — kept the gate
        # green. An indexable article must be listed; a noindex one must not.
        robots = re.search(r'<meta\s+name="robots"\s+content="([^"]*)"', src, re.I)
        indexable = not (robots and "noindex" in robots.group(1).lower())
        lastmod = entries.get(f"{DOMAIN}/blog/{fp.stem}")
        if indexable and not lastmod:
            err(rel, "indexable article is absent from sitemap.xml")
            bad += 1
            continue
        if not indexable and lastmod:
            err(rel, "noindex article is listed in sitemap.xml")
            bad += 1
            continue
        dm = re.search(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})', src)
        if not lastmod:
            continue                    # noindex, correctly unlisted
        if not dm:
            err(rel, "listed in sitemap.xml but the page has no dateModified")
            bad += 1
            continue
        compared += 1
        if not lastmod.startswith(dm.group(1)):
            err(fp.relative_to(ROOT).as_posix(),
                f"sitemap lastmod {lastmod} disagrees with dateModified "
                f"{dm.group(1)}")
            bad += 1
    # Lower than MIN_SHARE_PAGES on purpose: a noindex article is correctly
    # absent from the sitemap, so the two counts are not meant to agree.
    if compared < MIN_SITEMAP_ARTICLES:
        err("sitemap-lastmod", f"only {compared} URL(s) compared (expected >= "
                               f"{MIN_SITEMAP_ARTICLES}) — the sitemap or the scan "
                               f"is broken")
    elif bad == 0:
        print(f"[OK] sitemap lastmod agrees with dateModified on all {compared} articles")


PHYSICIAN_ID = f"{DOMAIN}/about#physician"
REVIEW_DATES_FILE = ROOT / "_review_dates.json"


def _review_dates() -> dict[str, str]:
    import json
    try:
        data = json.loads(REVIEW_DATES_FILE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


REVIEW_DATES = _review_dates()


def check_article_fields_current() -> None:
    """An article node's fields must match the page they are derived from.

    CODE_REVIEW TD-66 — presence was never the problem. _normalize_schema
    rewrites an article block INTO a MedicalWebPage and so never matches its
    own output again; from then on a second, shorter list of fields owned it.
    `headline`, `publisher` and `mainEntityOfPage` were only in the first list,
    so they FROZE at whatever value the block held when it was converted —
    present, well-formed, and silently stale. Three articles were still
    publishing a headline the page had stopped using.

    Checking the value against its source is what makes that visible; checking
    that the key exists would not have.
    """
    import json

    targets = [p for p in sorted((ROOT / "blog").glob("*.html"))
               if p.name not in {"index.html", "topics.html"}]
    bad = 0
    checked = 0
    for fp in targets:
        rel = fp.relative_to(ROOT).as_posix()
        src = fp.read_text(encoding="utf-8", errors="replace")
        tm = re.search(r"<title>([\s\S]*?)</title>", src, re.I)
        cm = re.search(r'<link\s+rel="canonical"\s+href="([^"]*)"', src, re.I)
        if not tm or not cm:
            err(rel, "no <title> or no canonical — cannot verify article fields")
            bad += 1
            continue
        expected_title = re.sub(r"\s+", " ", tm.group(1)).split("|")[0].strip()
        canonical = cm.group(1)
        for m in re.finditer(r'<script type="application/ld\+json">([\s\S]*?)</script>',
                             src):
            try:
                doc = json.loads(m.group(1))
            except ValueError:
                continue
            for node in (doc.get("@graph") or [doc]):
                if node.get("@type") not in ("MedicalWebPage", "MedicalScholarlyArticle"):
                    continue
                # The primary node is the one that claims to BE the page.
                if node.get("mainEntityOfPage") != canonical:
                    continue
                checked += 1
                if node.get("name") != expected_title:
                    err(rel, f"JSON-LD name is stale: {node.get('name')!r} vs the "
                             f"page's own title {expected_title!r}")
                    bad += 1
                if node.get("headline") != expected_title:
                    err(rel, f"JSON-LD headline is stale: {node.get('headline')!r} "
                             f"vs {expected_title!r}")
                    bad += 1
                for field in ("author", "publisher", "reviewedBy"):
                    value = node.get(field)
                    if not isinstance(value, dict) or value.get("@id") != PHYSICIAN_ID:
                        err(rel, f"{field} is not the physician reference: {value!r}")
                        bad += 1
                # CODE_REVIEW TD-74 — lastReviewed is a claim that a physician
                # REVIEWED this page on that date. It must equal what the
                # physician recorded, and must not be derived from anything the
                # pipeline can move on its own.
                #
                # An earlier version of this rule required
                # lastReviewed == dateModified. That was itself the bug: an
                # automated edit to the prose moves dateModified, so the rule
                # was enforcing "editing the text counts as a medical review".
                # The gate has to compare against the declaration.
                reviewed = str(node.get("lastReviewed") or "")[:10]
                declared = REVIEW_DATES.get(fp.stem)
                if declared and reviewed != declared:
                    err(rel, f"lastReviewed {reviewed!r} does not match the "
                             f"recorded review date {declared!r} — nothing in "
                             f"the pipeline may move a medical review claim")
                    bad += 1
                elif not declared:
                    err(rel, f"no review date recorded in "
                             f"{REVIEW_DATES_FILE.name} for this article")
                    bad += 1
    if checked < MIN_SHARE_PAGES:
        err("article-fields", f"only {checked} primary article node(s) found "
                              f"(expected >= {MIN_SHARE_PAGES}) — every article "
                              f"should have exactly one")
    elif bad == 0:
        print(f"[OK] article JSON-LD fields match their page ({checked} primary nodes)")


def main() -> int:
    print("=== SEO signals audit ===")
    check_robots_serp_directives()
    check_jsonld_enrichment()
    check_og_article_props()
    check_twitter_cards()
    check_homepage_brand_schema()
    check_sitemap_image_encoding()
    check_canonical_coverage()
    check_no_duplicate_medical_webpage()
    check_speakable_selectors_resolve()
    check_llms_full_clean()
    check_hreflang_reciprocity()
    check_hreflang_targets_indexable()
    check_no_mojibake_in_data_attrs()
    check_drug_schema_present()
    check_citations_block_present()
    check_glossary_termset_populated()
    check_tools_schema_present()
    check_article_metadata_fields()
    check_no_ad_placeholder_text()
    check_share_images()
    check_article_jsonld_image()
    check_lastmod_matches_datemodified()
    check_article_fields_current()

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
