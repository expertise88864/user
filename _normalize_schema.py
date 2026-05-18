#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Normalize JSON-LD identity and medical page schema."""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path


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


def compute_metrics(src: str, lang: str = "zh") -> dict[str, int]:
    """Estimate wordCount + reading minutes from the main article body.

    For ZH pages: count CJK chars at 300/min + Latin words at 200/min.
    For EN pages: count Latin words from BOTH visible text AND the
    data-en attribute values that DN.applyTextOnly() swaps in at runtime.
    Without that, EN articles would report 2-3 min based on the few
    visible Latin tokens alone.
    """
    article_m = re.search(r"<article\b[^>]*>([\s\S]*?)</article>", src, re.I)
    main_m = re.search(r"<main\b[^>]*>([\s\S]*?)</main>", src, re.I)
    body_src = (article_m.group(1) if article_m
                else (main_m.group(1) if main_m else src))

    if lang.startswith("en"):
        data_en_text = " ".join(re.findall(r'data-en="([^"]*)"', body_src))
        visible_text = clean_text(re.sub(r'\sdata-en="[^"]*"', '', body_src))
        text = data_en_text + " " + visible_text
        latin_words = len(re.findall(r"\b[A-Za-z][A-Za-z'\-]{1,}\b", text))
        minutes = max(1, round(latin_words / 200))
        return {"wordCount": latin_words, "readingMinutes": minutes}

    text = clean_text(body_src)
    cjk_chars = len(re.findall(r"[一-鿿]", text))
    latin_words = len(re.findall(r"\b[A-Za-z][A-Za-z'\-]{1,}\b", text))
    minutes = max(1, round(cjk_chars / 300 + latin_words / 200))
    return {"wordCount": cjk_chars + latin_words, "readingMinutes": minutes}


SPEAKABLE_SPEC = {
    "@type": "SpeakableSpecification",
    "cssSelector": ["h1", "[itemprop='description']", ".dn-summary"],
}


def page_meta(src: str) -> dict[str, str]:
    title_m = re.search(r"<title>([\s\S]*?)</title>", src, re.I)
    desc_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', src, re.I)
    canon_m = re.search(r'<link\s+rel="canonical"\s+href="([^"]*)"', src, re.I)
    lang_m = re.search(r'<html\b[^>]*lang="([^"]*)"', src, re.I)
    image_m = re.search(r'<meta\s+property="og:image"\s+content="([^"]*)"', src, re.I)
    return {
        "title": clean_text(title_m.group(1)) if title_m else "",
        "description": html.unescape(desc_m.group(1)).strip() if desc_m else "",
        "canonical": canon_m.group(1) if canon_m else "",
        "lang": lang_m.group(1) if lang_m else "zh-Hant-TW",
        "image": image_m.group(1) if image_m else f"{DOMAIN}/logo-512.png",
    }


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
            obj.setdefault("speakable", SPEAKABLE_SPEC)

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
            obj.setdefault("speakable", SPEAKABLE_SPEC)

    return obj


def script_for(obj: dict) -> str:
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "</script>"


def iter_jsonld(src: str):
    for m in re.finditer(r'<script\s+type="application/ld\+json"[^>]*>([\s\S]*?)</script>', src, re.I):
        try:
            obj = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(obj, dict):
            yield obj


def has_jsonld_type(src: str, typ: str) -> bool:
    return any(obj.get("@type") == typ for obj in iter_jsonld(src))


def has_article_schema(src: str) -> bool:
    return any(obj.get("@type") in {"MedicalScholarlyArticle", "Article", "BlogPosting"} for obj in iter_jsonld(src))


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
        except Exception:
            return match.group(0)
        if not isinstance(obj, dict):
            return match.group(0)
        new_obj = normalize_obj(obj, path, meta, metrics)
        new = '<script type="application/ld+json"' + attrs + ">" + json.dumps(new_obj, ensure_ascii=False, separators=(",", ":")) + "</script>"
        if new != match.group(0):
            changed = True
        return new

    src2 = re.sub(r'<script\s+type="application/ld\+json"([^>]*)>([\s\S]*?)</script>', repl, src, flags=re.I)

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
