#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit JSON-LD structured data across all HTML pages."""

from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"
SKIP_DIRS = {".git", "__pycache__", "node_modules", "astro-rewrite"}

# 2026-05-17 — schema type policy: research-summary articles use
# MedicalScholarlyArticle as the primary @type (they ARE journal-club
# write-ups). Patient-education articles (cat in {rx, myth, product})
# use MedicalWebPage to avoid Google de-ranking them as misrepresented
# academic publications. Single source of truth mirrored in
# _normalize_schema.py.
RESEARCH_SLUGS = {
    'dupilumab-long-term-maintenance',
    'psoriasis-biologic-monitoring',
    'ai-dermatology-roles',
    'spironolactone-dermatology-safety',
    'jaki-switching-alopecia-areata',
    'nail-psoriasis-topical-intralesional',
    'bimekizumab-hidradenitis-suppurativa',
}

REQUIRED_FIELDS = {
    "MedicalScholarlyArticle": [
        "@id",
        "headline",
        "description",
        "datePublished",
        "dateModified",
        "author",
        "reviewedBy",
        "publisher",
        "mainEntityOfPage",
        "image",
    ],
    "MedicalWebPage": ["@id", "name", "description", "about", "author", "reviewedBy"],
    "BreadcrumbList": ["itemListElement"],
    "FAQPage": ["mainEntity"],
    "ItemList": ["itemListElement"],
    "Person": ["name"],
    "Physician": ["@id", "name", "medicalSpecialty", "url"],
}


def iter_html_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.html"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        files.append(path)
    return files


def canonical_of(src: str) -> str:
    m = re.search(r'<link\s+rel="canonical"\s+href="([^"]*)"', src, re.I)
    return m.group(1) if m else ""


def is_noindex(src: str) -> bool:
    m = re.search(r'<meta\s+name="robots"\s+content="([^"]*)"', src, re.I)
    return bool(m and "noindex" in m.group(1).lower())


def type_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)] if value else []


def jsonld_blocks(src: str):
    for i, m in enumerate(re.finditer(r'<script type="application/ld\+json">([\s\S]*?)</script>', src, re.I)):
        yield i, m.group(1).strip()


def require_ref_object(rel: str, typ: str, field: str, value, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{rel}: {typ}.{field} should be an object reference")
        return
    if not (value.get("@id") or value.get("name")):
        errors.append(f"{rel}: {typ}.{field} missing @id or name")


def audit_object(rel: str, canonical: str, obj: dict, errors: list[str], type_counts: dict[str, int]) -> None:
    types = type_list(obj.get("@type"))
    if not types:
        errors.append(f"{rel}: block missing @type")
        return

    for typ in types:
        type_counts[typ] = type_counts.get(typ, 0) + 1
        for field in REQUIRED_FIELDS.get(typ, []):
            if field not in obj:
                errors.append(f'{rel}: {typ} missing required field "{field}"')

    if "MedicalScholarlyArticle" in types:
        expected_id = canonical + "#article" if canonical else ""
        if expected_id and obj.get("@id") != expected_id:
            errors.append(f"{rel}: MedicalScholarlyArticle @id should be {expected_id}")
        if canonical and obj.get("mainEntityOfPage") != canonical:
            errors.append(f"{rel}: MedicalScholarlyArticle mainEntityOfPage does not match canonical")
        if obj.get("image") and not isinstance(obj.get("image"), str):
            errors.append(f"{rel}: MedicalScholarlyArticle image should be a URL string")
        for field in ("author", "reviewedBy", "publisher"):
            require_ref_object(rel, "MedicalScholarlyArticle", field, obj.get(field), errors)

    if "MedicalWebPage" in types:
        expected_id = canonical + "#webpage" if canonical else ""
        if expected_id and obj.get("@id") != expected_id:
            errors.append(f"{rel}: MedicalWebPage @id should be {expected_id}")
        if "/blog/" in canonical:
            main = obj.get("mainEntity")
            if not isinstance(main, dict) or main.get("@id") != canonical + "#article":
                errors.append(f"{rel}: MedicalWebPage mainEntity should point to article @id")
        for field in ("author", "reviewedBy"):
            require_ref_object(rel, "MedicalWebPage", field, obj.get(field), errors)

    if "FAQPage" in types:
        entities = obj.get("mainEntity")
        if not isinstance(entities, list) or not entities:
            errors.append(f"{rel}: FAQPage mainEntity should be a non-empty list")


def main() -> int:
    n_files = 0
    n_blocks = 0
    errors: list[str] = []
    type_counts: dict[str, int] = {}

    for path in iter_html_files():
        rel = path.relative_to(ROOT).as_posix()
        src = path.read_text(encoding="utf-8")
        canonical = canonical_of(src)
        n_files += 1
        page_types: list[str] = []

        for index, raw in jsonld_blocks(src):
            n_blocks += 1
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f"{rel}: invalid JSON-LD block {index}: {exc.msg} at pos {exc.pos}")
                continue
            objects = data if isinstance(data, list) else [data]
            for obj in objects:
                if not isinstance(obj, dict):
                    errors.append(f"{rel}: JSON-LD block {index} is not an object")
                    continue
                page_types.extend(type_list(obj.get("@type")))
                audit_object(rel, canonical, obj, errors, type_counts)

        if rel.startswith("blog/") and rel not in {"blog/index.html", "blog/topics.html"} and not is_noindex(src):
            # Schema type expectation depends on article category:
            #   - research articles (cat:'research'): require MedicalScholarlyArticle
            #   - patient-ed articles (cat in {rx, myth, product}): require MedicalWebPage
            #     as the PRIMARY article type (MedicalWebPage may still appear
            #     in addition as the webpage wrapper schema)
            slug = Path(rel).stem
            is_research = slug in RESEARCH_SLUGS
            if is_research:
                if "MedicalScholarlyArticle" not in page_types:
                    errors.append(f"{rel}: research article missing MedicalScholarlyArticle")
            else:
                if "MedicalScholarlyArticle" in page_types:
                    errors.append(f"{rel}: patient-ed article should NOT use MedicalScholarlyArticle (Google reserves that for peer-reviewed publications); use MedicalWebPage as primary @type")
            if "MedicalWebPage" not in page_types:
                errors.append(f"{rel}: public blog article missing MedicalWebPage")

    print(f"Files scanned: {n_files}")
    print(f"JSON-LD blocks found: {n_blocks}")
    print("\nType distribution:")
    for typ, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {count:>4}× {typ}")
    print(f"\nErrors: {len(errors)}")
    for error in errors[:80]:
        print(f"  - {error}")
    if len(errors) > 80:
        print(f"  ... ({len(errors) - 80} more)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
