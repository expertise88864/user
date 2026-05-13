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


def clean_text(src: str) -> str:
    src = re.sub(r"<script\b[\s\S]*?</script>", " ", src, flags=re.I)
    src = re.sub(r"<style\b[\s\S]*?</style>", " ", src, flags=re.I)
    src = re.sub(r"<[^>]+>", " ", src)
    return re.sub(r"\s+", " ", html.unescape(src)).strip()


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


def normalize_obj(obj: dict, path: Path, meta: dict[str, str]) -> dict:
    typ = obj.get("@type")
    if typ in {"Person", "Physician"} and path.name in {"index.html", "about.html"}:
        return physician_schema(obj)

    if typ == "MedicalOrganization":
        obj.setdefault("@id", f"{DOMAIN}/#organization")
        obj.setdefault("url", DOMAIN + "/")

    if typ in {"Article", "BlogPosting", "MedicalScholarlyArticle"}:
        if meta.get("canonical"):
            obj["@id"] = article_id(meta)
            obj["mainEntityOfPage"] = meta["canonical"]
        obj["@type"] = "MedicalScholarlyArticle"
        obj["author"] = PHYSICIAN_REF
        obj["publisher"] = PHYSICIAN_REF
        obj["reviewedBy"] = PHYSICIAN_REF
        obj.setdefault("isAccessibleForFree", True)
        obj.setdefault("isFamilyFriendly", True)
        if meta.get("image"):
            obj.setdefault("image", meta["image"])
        if meta.get("title"):
            obj["headline"] = meta["title"].split("|")[0].strip()
        if meta.get("description"):
            obj["description"] = meta["description"]

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


def build_medical_webpage(src: str, path: Path) -> dict:
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
    return out


def normalize_file(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    src = src.replace(f"{DOMAIN}/#person", PHYSICIAN_ID)
    src = src.replace(f"{DOMAIN}/about#person", PHYSICIAN_ID)
    meta = page_meta(src)

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
        new_obj = normalize_obj(obj, path, meta)
        new = '<script type="application/ld+json"' + attrs + ">" + json.dumps(new_obj, ensure_ascii=False, separators=(",", ":")) + "</script>"
        if new != match.group(0):
            changed = True
        return new

    src2 = re.sub(r'<script\s+type="application/ld\+json"([^>]*)>([\s\S]*?)</script>', repl, src, flags=re.I)

    if has_article_schema(src2) and path.name not in {"index.html", "topics.html"} and not has_jsonld_type(src2, "MedicalWebPage"):
        block = script_for(build_medical_webpage(src2, path))
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
