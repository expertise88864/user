#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Normalize JSON-LD identity and medical page schema."""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path


# CODE_REVIEW — UTF-8 console on Windows (cp950 default crashes on CJK).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
DOMAIN = "https://chendermatologist.com"
PHYSICIAN_ID = f"{DOMAIN}/about#physician"


PHYSICIAN_REF = {
    "@type": "Physician",
    "@id": PHYSICIAN_ID,
    "name": "陳翊嘉 醫師",
}

# 2026-05-17: schema.org's MedicalScholarlyArticle is for peer-reviewed
# academic publications. Patient-education content (DN.ARTICLES cat in
# {rx, myth, product}) should use MedicalWebPage as the primary type;
# misuse risks Google de-ranking. Keep MedicalScholarlyArticle ONLY for
# the journal-club / research-summary articles (cat: 'research').
RESEARCH_SLUGS = {
    'dupilumab-long-term-maintenance',
    'psoriasis-biologic-monitoring',
    'ai-dermatology-roles',
    'spironolactone-dermatology-safety',
    'jaki-switching-alopecia-areata',
    'nail-psoriasis-topical-intralesional',
    'bimekizumab-hidradenitis-suppurativa',
}

def _slug_from_path(path: Path) -> str:
    return path.stem  # e.g. 'biologics-overview' from blog/biologics-overview.html

def _is_research_article(path: Path) -> bool:
    return _slug_from_path(path) in RESEARCH_SLUGS


def clean_text(src: str) -> str:
    src = re.sub(r"<script\b[\s\S]*?</script>", " ", src, flags=re.I)
    src = re.sub(r"<style\b[\s\S]*?</style>", " ", src, flags=re.I)
    src = re.sub(r"<[^>]+>", " ", src)
    return re.sub(r"\s+", " ", html.unescape(src)).strip()


def _extract_prose_container(src: str, prose_id: str) -> str | None:
    """Find <div id="proseZh"> (or proseEn) and return its inner HTML,
    correctly handling nested <div> blocks by counting open/close tags.

    A lazy regex match like `<div ...>([\\s\\S]*?)</div>` stops at the
    FIRST inner </div>, truncating the content to ~200 chars. We need
    the full prose body, so walk forward counting nesting depth.
    """
    open_m = re.search(rf'<div\b[^>]*\bid="{prose_id}"[^>]*>', src, re.I)
    if not open_m:
        return None
    pos = open_m.end()
    depth = 1
    div_re = re.compile(r'<(/?)div\b[^>]*>', re.I)
    while depth > 0:
        m = div_re.search(src, pos)
        if not m:
            return src[open_m.end():]  # unclosed — return rest of doc
        if m.group(1) == '/':
            depth -= 1
        else:
            depth += 1
        pos = m.end()
        if depth == 0:
            return src[open_m.end():m.start()]
    return None


def compute_metrics(src: str, lang: str = "zh") -> dict[str, int]:
    """Estimate wordCount + reading minutes from the main prose container.

    Mirrors DN.addReadingMeta() in blog/blog-article-reading.js so the
    JSON-LD signal matches what the on-page hero card shows to users:
      - prefer #proseZh / #proseEn over the whole <article> (skips
        references, footer ld+json, related cards, etc.)
      - reading speed: 350 CJK chars/min + 200 Latin/digit tokens/min
      - count [A-Za-z0-9]+ (same regex as the JS counter)
    """
    prose_id = "proseEn" if lang.startswith("en") else "proseZh"
    body_src = _extract_prose_container(src, prose_id)
    # 2026-05-31 — bilingual EN-mirror fix. These pages keep #proseEn as an
    # empty placeholder and store the real content in #proseZh with data-en=""
    # swaps (DN.applyTextOnly renders EN at runtime). Reading #proseEn for an
    # EN page therefore yielded an EMPTY body → wordCount:0 / timeRequired:PT2M
    # (false structured data flagged by audit). When the EN container is
    # missing or near-empty, fall back to #proseZh, whose data-en attributes
    # the lang=="en" branch below already harvests. Verified: jaki EN goes
    # 0 → 3331 words.
    if lang.startswith("en") and (body_src is None or len(clean_text(body_src)) < 200):
        zh = _extract_prose_container(src, "proseZh")
        if zh is not None and len(zh) > (len(body_src or "")):
            body_src = zh
    if body_src is None:
        article_m = re.search(r"<article\b[^>]*>([\s\S]*?)</article>", src, re.I)
        body_src = article_m.group(1) if article_m else src

    if lang.startswith("en"):
        data_en_text = " ".join(re.findall(r'data-en="([^"]*)"', body_src))
        visible_text = clean_text(re.sub(r'\sdata-en="[^"]*"', '', body_src))
        text = data_en_text + " " + visible_text
        tokens = len(re.findall(r"[A-Za-z0-9]+", text))
        minutes = max(2, round(tokens / 200))
        return {"wordCount": tokens, "readingMinutes": minutes}

    text = clean_text(body_src).replace(" ", "")
    cjk_chars = len(re.findall(r"[一-鿿]", text))
    tokens = len(re.findall(r"[A-Za-z0-9]+", text))
    minutes = max(2, round(cjk_chars / 350 + tokens / 200))
    return {"wordCount": cjk_chars + tokens, "readingMinutes": minutes}


# Speakable selectors target actual DOM and work on BOTH ZH and EN.
# Selector order (Google Assistant TTS uses first that matches):
#   1. `[data-speakable]` — opt-in marker authors can add to any
#      element (SEO_AUDIT D5; forward-compat without restructuring
#      class names)
#   2. `h1` — every article has one (universal)
#   3. `.prose p:first-of-type` — first paragraph in prose container
#      (44/50 ZH + EN articles use `.prose` class)
#   4. `.tldr` — explicit summary class on some articles
#   5. `.dn-tldr` — alternate summary class (atopic-dermatitis-overview)
SPEAKABLE_SPEC = {
    "@type": "SpeakableSpecification",
    "cssSelector": ["[data-speakable]", "h1", ".prose p:first-of-type", ".tldr", ".dn-tldr"],
}

# SEO_AUDIT D4 — accessibilityFeature signals that articles support
# multiple a11y modes. Aligns with WCAG AA + Google's accessibility
# scoring. Static across all blog articles (we set the same baseline
# in tw-mini.css + Speculation Rules + the bilingual data-zh/data-en
# system). Add to every MedicalWebPage + MedicalScholarlyArticle.
ACCESSIBILITY_FEATURES = [
    "alternativeText",          # all imgs have alt
    "highContrastDisplay",      # tw-mini has prefers-color-scheme:dark
    "largePrint",               # font-size adjuster (DN.addFontSizer)
    "readingOrder",             # semantic heading hierarchy
    "structuralNavigation",     # h2/h3/h4 + nav landmarks
    "tableOfContents",          # DN.addInlineTOC auto-generates
    "displayTransformability",  # prefers-reduced-motion respected
    "MathML",                   # no math content, but declares no proprietary
    "bilingualText",            # ZH ↔ EN swap via DN.applyTextOnly
]


def page_meta(src: str) -> dict[str, str]:
    title_m = re.search(r"<title>([\s\S]*?)</title>", src, re.I)
    desc_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', src, re.I)
    canon_m = re.search(r'<link\s+rel="canonical"\s+href="([^"]*)"', src, re.I)
    lang_m = re.search(r'<html\b[^>]*lang="([^"]*)"', src, re.I)
    image_m = re.search(r'<meta\s+property="og:image"\s+content="([^"]*)"', src, re.I)
    keywords_m = re.search(r'<meta\s+name="keywords"\s+content="([^"]*)"', src, re.I)
    return {
        "title": clean_text(title_m.group(1)) if title_m else "",
        "description": html.unescape(desc_m.group(1)).strip() if desc_m else "",
        "canonical": canon_m.group(1) if canon_m else "",
        "lang": lang_m.group(1) if lang_m else "zh-Hant-TW",
        "image": image_m.group(1) if image_m else f"{DOMAIN}/logo-512.png",
        "keywords": html.unescape(keywords_m.group(1)).strip() if keywords_m else "",
    }


# Map DN.ARTICLES cat field to human-friendly article section labels.
# Used as the `articleSection` field in JSON-LD so Google can group
# articles by topic in the SERP knowledge panel + topical clustering.
CAT_TO_SECTION = {
    "rx": "Treatment & Therapy",
    "myth": "Myths & Facts",
    "note": "Clinical Notes",
    "research": "Research Summary",
    "product": "Products & Drugs",
}


def _article_section_for_slug(slug: str) -> str | None:
    """Look up DN.ARTICLES catalog to map slug -> articleSection label."""
    catalog_path = ROOT / "blog" / "blog-shared.js"
    if not catalog_path.exists():
        return None
    src = catalog_path.read_text(encoding="utf-8")
    m = re.search(rf"\{{[^{{}}]*?slug:'{re.escape(slug)}'[^{{}}]*?\}}", src)
    if not m:
        return None
    cat_m = re.search(r"cat:'([^']+)'", m.group(0))
    if not cat_m:
        return None
    return CAT_TO_SECTION.get(cat_m.group(1))


def physician_schema(existing: dict | None = None) -> dict:
    obj = dict(existing or {})
    obj.update({
        "@context": "https://schema.org",
        "@type": "Physician",
        "@id": PHYSICIAN_ID,
        "name": obj.get("name") or "陳翊嘉",
        "alternateName": obj.get("alternateName") or ["Dr. Chen Yi-Jia", "Yi-Jia Chen, M.D."],
        "honorificPrefix": obj.get("honorificPrefix") or "Dr.",
        "jobTitle": obj.get("jobTitle") or "Dermatology Resident Physician",
        "medicalSpecialty": obj.get("medicalSpecialty") or "Dermatology",
        "url": f"{DOMAIN}/about",
        "sameAs": obj.get("sameAs") or [f"{DOMAIN}/about"],
        # SEO_AUDIT D3 — affiliation strengthens E-E-A-T (Google rewards
        # named institutional context for YMYL medical content).
        "affiliation": obj.get("affiliation") or {
            "@type": "Hospital",
            "name": "中國醫藥大學附設醫院 皮膚部",
            "alternateName": "China Medical University Hospital, Department of Dermatology",
            "url": "https://www.cmuh.cmu.edu.tw/",
            "address": {
                "@type": "PostalAddress",
                "addressCountry": "TW",
                "addressRegion": "臺中市",
            },
        },
    })
    return obj


def article_id(meta: dict[str, str]) -> str:
    return meta["canonical"] + "#article"


def webpage_id(meta: dict[str, str]) -> str:
    return meta["canonical"] + "#webpage"


def normalize_obj(obj: dict, path: Path, meta: dict[str, str],
                  metrics: dict[str, int] | None = None) -> dict:
    typ = obj.get("@type")
    if typ in {"Person", "Physician"} and path.name in {"index.html", "about.html"}:
        return physician_schema(obj)

    if typ == "MedicalOrganization":
        obj.setdefault("@id", f"{DOMAIN}/#organization")
        obj.setdefault("url", DOMAIN + "/")

    is_blog_article = (meta.get("canonical") and "/blog/" in meta["canonical"]
                       and path.name not in {"index.html", "topics.html"})

    if typ in {"Article", "BlogPosting", "MedicalScholarlyArticle"}:
        # Keep MedicalScholarlyArticle only for research-summary articles
        # (cat: 'research'); downgrade patient-education articles to
        # MedicalWebPage so Google doesn't treat them as peer-reviewed
        # publications and de-rank them.
        is_research_blog = (meta.get("canonical") and "/blog/" in meta["canonical"]
                            and _is_research_article(path))
        if meta.get("canonical"):
            obj["@id"] = article_id(meta)
            obj["mainEntityOfPage"] = meta["canonical"]
        obj["@type"] = "MedicalScholarlyArticle" if is_research_blog else "MedicalWebPage"
        obj["author"] = PHYSICIAN_REF
        obj["publisher"] = PHYSICIAN_REF
        obj["reviewedBy"] = PHYSICIAN_REF
        obj.setdefault("isAccessibleForFree", True)
        obj.setdefault("isFamilyFriendly", True)
        if meta.get("image"):
            obj.setdefault("image", meta["image"])
        if meta.get("title"):
            # MedicalWebPage uses `name`; Article uses `headline`.
            # Set both so the field is correct regardless of @type.
            short_title = meta["title"].split("|")[0].strip()
            obj["headline"] = short_title
            obj["name"] = short_title
        if meta.get("description"):
            obj["description"] = meta["description"]
        if metrics and is_blog_article:
            obj["wordCount"] = metrics["wordCount"]
            obj["timeRequired"] = f"PT{metrics['readingMinutes']}M"
            # Direct assignment (not setdefault) so SPEAKABLE_SPEC updates
            # propagate to existing blocks. CODE_REVIEW C4 fixed the
            # selector list to target real DOM (h1 + #proseZh > p +
            # .tldr) instead of the original nonexistent itemprop ref.
            obj["speakable"] = SPEAKABLE_SPEC
            # SEO_AUDIT D4 — accessibilityFeature for a11y signal
            obj["accessibilityFeature"] = ACCESSIBILITY_FEATURES
        if is_blog_article:
            section = _article_section_for_slug(path.stem)
            if section:
                obj["articleSection"] = section
            if meta.get("keywords"):
                obj["keywords"] = meta["keywords"]

    if typ == "MedicalWebPage":
        if meta.get("canonical"):
            obj["@id"] = webpage_id(meta)
            if "/blog/" in meta["canonical"]:
                obj["mainEntity"] = {"@id": article_id(meta)}
        obj["author"] = PHYSICIAN_REF
        obj["reviewedBy"] = PHYSICIAN_REF
        obj.setdefault("about", {"@type": "MedicalSpecialty", "name": "Dermatology"})
        if meta.get("title"):
            obj["name"] = meta["title"].split("|")[0].strip()
        if meta.get("description"):
            obj["description"] = meta["description"]
        if metrics and is_blog_article:
            obj["wordCount"] = metrics["wordCount"]
            obj["timeRequired"] = f"PT{metrics['readingMinutes']}M"
            # Direct assignment (not setdefault) so SPEAKABLE_SPEC updates
            # propagate to existing blocks. CODE_REVIEW C4 fixed the
            # selector list to target real DOM (h1 + #proseZh > p +
            # .tldr) instead of the original nonexistent itemprop ref.
            obj["speakable"] = SPEAKABLE_SPEC
            # SEO_AUDIT D4 — accessibilityFeature for a11y signal
            obj["accessibilityFeature"] = ACCESSIBILITY_FEATURES
        if is_blog_article:
            section = _article_section_for_slug(path.stem)
            if section:
                obj["articleSection"] = section
            if meta.get("keywords"):
                obj["keywords"] = meta["keywords"]

    return obj


def script_for(obj: dict) -> str:
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "</script>"


def iter_jsonld(src: str):
    for m in re.finditer(r'<script\s+type="application/ld\+json"[^>]*>([\s\S]*?)</script>', src, re.I):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError as exc:
            # CODE_REVIEW 2026-05-25 — was silent `except Exception: continue`
            # → masked real malformed-JSON-LD bugs. Now narrow to
            # JSONDecodeError + warn to stderr so problems surface in CI logs.
            preview = m.group(1)[:80].replace('\n', ' ')
            print(f"[normalize_schema] iter_jsonld: skipping malformed JSON-LD ({exc.msg}): {preview!r}",
                  file=sys.stderr)
            continue
        if isinstance(obj, dict):
            yield obj


def has_jsonld_type(src: str, typ: str) -> bool:
    return any(obj.get("@type") == typ for obj in iter_jsonld(src))


def has_article_schema(src: str) -> bool:
    return any(obj.get("@type") in {"MedicalScholarlyArticle", "Article", "BlogPosting"} for obj in iter_jsonld(src))


_LD_BLOCK_RE = re.compile(
    r'<script\s+type="application/ld\+json"[^>]*>([\s\S]*?)</script>',
    re.IGNORECASE,
)


def dedupe_jsonld_type(src: str, typ: str) -> tuple[str, int]:
    """Remove all but the first JSON-LD block of @type=typ.

    History (CODE_REVIEW C1): 46/48 articles ship 2 MedicalWebPage
    blocks because an earlier version of the schema normalizer inserted
    a fresh `build_medical_webpage()` block on every run, on top of
    whatever Article→MedicalWebPage conversion the same pass produced.
    The current pass has has_jsonld_type guard against re-insertion,
    but doesn't clean up the legacy duplicates left in the file.

    Strategy: scan the HTML, find every JSON-LD block of the given
    @type, keep ONLY the first one. The first block is typically the
    converted-from-Article version which carries the most editorial
    metadata (headline, isAccessibleForFree, image). The second was
    auto-built and only carries derived fields.

    Returns (new_src, count_removed).
    """
    matches: list[tuple[int, int]] = []  # (start, end) of MedicalWebPage blocks
    for m in _LD_BLOCK_RE.finditer(src):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError as exc:
            preview = m.group(1)[:80].replace('\n', ' ')
            print(f"[normalize_schema] dedupe_type({typ}): skipping malformed JSON-LD ({exc.msg}): {preview!r}",
                  file=sys.stderr)
            continue
        if isinstance(obj, dict) and obj.get("@type") == typ:
            matches.append((m.start(), m.end()))
    if len(matches) <= 1:
        return src, 0
    # Drop all but the first; iterate end→start so positions stay valid.
    keep_start, keep_end = matches[0]
    out = src
    for start, end in reversed(matches[1:]):
        out = out[:start] + out[end:]
    return out, len(matches) - 1


def build_medical_webpage(src: str, path: Path,
                          metrics: dict[str, int] | None = None) -> dict:
    meta = page_meta(src)
    article_about = None
    for obj in iter_jsonld(src):
        if obj.get("@type") in {"MedicalScholarlyArticle", "Article", "BlogPosting"}:
            article_about = obj.get("about")
            break

    out = {
        "@context": "https://schema.org",
        "@type": "MedicalWebPage",
        "url": meta["canonical"],
        "inLanguage": meta["lang"],
        "name": meta["title"],
        "description": meta["description"],
        "audience": {"@type": "MedicalAudience", "audienceType": "Patient"},
        "author": PHYSICIAN_REF,
        "reviewedBy": PHYSICIAN_REF,
        "isPartOf": {"@type": "WebSite", "name": "ChenDermatologist", "url": DOMAIN + "/"},
    }
    if meta.get("canonical"):
        out["@id"] = webpage_id(meta)
        out["mainEntity"] = {"@id": article_id(meta)}
    if article_about:
        out["about"] = article_about
    else:
        out["about"] = {"@type": "MedicalSpecialty", "name": "Dermatology"}
    if metrics and "/blog/" in (meta.get("canonical") or ""):
        out["wordCount"] = metrics["wordCount"]
        out["timeRequired"] = f"PT{metrics['readingMinutes']}M"
        out["speakable"] = SPEAKABLE_SPEC
        out["accessibilityFeature"] = ACCESSIBILITY_FEATURES
    return out


def normalize_file(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    src = src.replace(f"{DOMAIN}/#person", PHYSICIAN_ID)
    src = src.replace(f"{DOMAIN}/about#person", PHYSICIAN_ID)
    meta = page_meta(src)
    metrics = compute_metrics(src, lang=meta.get("lang") or "zh") if path.name not in {"index.html", "topics.html"} else None

    changed = False

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        attrs = match.group(1)
        raw = match.group(2)
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            # 2026-05-26 — narrowed from bare `except Exception` (matches the
            # iter_jsonld policy): surface malformed JSON-LD on stderr instead
            # of silently leaving it un-normalized, which later shows up as a
            # confusing missing-field error in _audit_jsonld far from the cause.
            print(f"[normalize_schema] WARN malformed JSON-LD skipped: {exc}: {raw[:80]}",
                  file=sys.stderr)
            return match.group(0)
        if not isinstance(obj, dict):
            return match.group(0)
        new_obj = normalize_obj(obj, path, meta, metrics)
        new = '<script type="application/ld+json"' + attrs + ">" + json.dumps(new_obj, ensure_ascii=False, separators=(",", ":")) + "</script>"
        if new != match.group(0):
            changed = True
        return new

    src2 = re.sub(r'<script\s+type="application/ld\+json"([^>]*)>([\s\S]*?)</script>', repl, src, flags=re.I)

    # CODE_REVIEW C1 — dedupe legacy duplicate MedicalWebPage blocks.
    # Must run BEFORE the build_medical_webpage insertion check so the
    # has_jsonld_type guard sees the cleaned state.
    src2, removed = dedupe_jsonld_type(src2, "MedicalWebPage")
    if removed:
        changed = True

    if has_article_schema(src2) and path.name not in {"index.html", "topics.html"} and not has_jsonld_type(src2, "MedicalWebPage"):
        block = script_for(build_medical_webpage(src2, path, metrics))
        src2 = src2.replace("</head>", block + "</head>", 1)
        changed = True

    if src2 != src:
        path.write_text(src2, encoding="utf-8")
        return True
    return changed


def main() -> None:
    include_en = "--include-en" in sys.argv
    targets = [
        path
        for path in sorted(ROOT.rglob("*.html"))
        if not any(part in {".git", "node_modules"} for part in path.relative_to(ROOT).parts)
        and (include_en or path.relative_to(ROOT).parts[0] != "en")
        and path.name not in {"404.html", "offline.html", "admin.html", "reset-sw.html"}
    ]
    n = 0
    for path in targets:
        if path.exists() and normalize_file(path):
            n += 1
            print("normalized", path.relative_to(ROOT).as_posix())
    print(f"Normalized schema in {n} files")


if __name__ == "__main__":
    main()
