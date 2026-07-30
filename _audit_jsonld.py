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


PHYSICIAN_ID = f"{DOMAIN}/about#physician"
# CODE_REVIEW TD-72 — this used to accept two spellings, because the site was
# publishing two and choosing between them was the physician's call. It now
# publishes one: "陳翊嘉 醫師", the form every page visibly displays in both
# locales, sourced from a single constant in _normalize_schema. An @id exists
# to say "this is the same person"; two names under it says the opposite.
PHYSICIAN_NAMES = {"陳翊嘉 醫師"}


def require_ref_object(rel: str, typ: str, field: str, value, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{rel}: {typ}.{field} should be an object reference")
        return
    if not (value.get("@id") or value.get("name")):
        errors.append(f"{rel}: {typ}.{field} missing @id or name")


def check_physician_identity(rel: str, nodes: list[dict]) -> list[str]:
    """Anything claiming to BE the physician must spell his name correctly.

    CODE_REVIEW TD-66 — a measurement probe of mine appended a sentinel to
    PHYSICIAN_REF's name, ran the normalizer, and restored only blog/. The
    normalizer writes the whole site, so dashboard.html and tools.html shipped
    the physician's name with `TD66-PROPAGATION-PROBE` glued to it — on two
    public YMYL pages, through a gate that was entirely green. Nothing checked
    the NAME: require_ref_object() accepts any reference carrying an @id, and
    the article-field check reads blog/ only and compares the @id.

    On a medical site the author's identity is the E-E-A-T signal, so it is
    worth asserting exactly rather than structurally.
    """
    problems: list[str] = []

    def walk(value) -> None:
        if isinstance(value, dict):
            if value.get("@id") == PHYSICIAN_ID:
                name = value.get("name")
                if name is not None and name not in PHYSICIAN_NAMES:
                    problems.append(
                        f"{rel}: a node claiming to be the physician spells the "
                        f"name {name!r}, which is neither of the accepted forms "
                        f"{sorted(PHYSICIAN_NAMES)}")
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(nodes)
    return problems


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
        # CODE_REVIEW SEO-2 — this used to demand a bare URL string. schema.org
        # types `image` as URL *or* ImageObject, and Google's Article guidance
        # asks for the dimensions an ImageObject carries, so the old rule
        # rejected the better shape. Now either form is accepted and the
        # ImageObject form is checked properly: a dict with no url is a node
        # that resolves to no picture at all, which the string rule could
        # never have caught.
        image = obj.get("image")
        if image is not None and not isinstance(image, str):
            if not isinstance(image, dict):
                errors.append(
                    f"{rel}: MedicalScholarlyArticle image should be a URL string "
                    f"or an ImageObject, got {type(image).__name__}")
            elif image.get("@type") != "ImageObject" or not image.get("url"):
                errors.append(
                    f"{rel}: MedicalScholarlyArticle image object needs "
                    f'@type "ImageObject" and a url')
        for field in ("author", "reviewedBy", "publisher"):
            require_ref_object(rel, "MedicalScholarlyArticle", field, obj.get(field), errors)

    if "MedicalWebPage" in types:
        expected_id = canonical + "#webpage" if canonical else ""
        if expected_id and obj.get("@id") != expected_id:
            errors.append(f"{rel}: MedicalWebPage @id should be {expected_id}")
        # CODE_REVIEW TD-66 — this used to REQUIRE
        # `mainEntity -> <canonical>#article` on every blog MedicalWebPage,
        # without ever asking whether such a node exists. On the 48
        # non-research articles it does not: that block IS the article, and
        # _normalize_schema had renamed it to `#webpage`. So the checker and
        # the generator agreed on a shape that pointed at nothing, which is the
        # most durable kind of wrong. The rule is now conditional, and
        # dangling_same_page_refs() enforces that whatever it points at
        # resolves.
        main = obj.get("mainEntity")
        if isinstance(main, dict) and main.get("@id") == obj.get("@id"):
            errors.append(f"{rel}: MedicalWebPage mainEntity points at itself")
        for field in ("author", "reviewedBy"):
            require_ref_object(rel, "MedicalWebPage", field, obj.get(field), errors)

    if "FAQPage" in types:
        entities = obj.get("mainEntity")
        if not isinstance(entities, list) or not entities:
            errors.append(f"{rel}: FAQPage mainEntity should be a non-empty list")


def dangling_same_page_refs(rel: str, canonical: str,
                            nodes: list[dict]) -> list[str]:
    """A `{"@id": …}` pointing at THIS page must resolve to a node on it.

    CODE_REVIEW TD-66 — _normalize_schema wrote
    `mainEntity: {"@id": <canonical>#article}` onto every blog MedicalWebPage,
    but on the 48 non-research articles no `#article` node exists: that block
    WAS the article, and the same branch had renamed it to `#webpage`. So 48
    pages pointed at themselves through an identifier that resolves to
    nothing, and nothing noticed.

    Scoped to same-page fragments on purpose. Cross-page identifiers are
    normal here and must not be flagged: PHYSICIAN_REF points at
    /about#physician, and `mentions` points at glossary entries.
    """
    if not canonical:
        return []
    # An @id is DEFINED by any object that also carries other keys, at any
    # depth: index.html defines #logo inside the Organization node's `logo`,
    # not as a sibling. Collecting only top-level @ids reported that as
    # dangling — a false positive found while writing this check.
    present: set[str] = set()

    def collect(value) -> None:
        if isinstance(value, dict):
            ref = value.get("@id")
            if isinstance(ref, str) and len(value) > 1:
                present.add(ref)
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(nodes)
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()

    def walk(value, field: str) -> None:
        if isinstance(value, dict):
            ref = value.get("@id")
            # A bare reference: an @id and nothing that defines a node.
            if ref and len(value) == 1 and isinstance(ref, str):
                if ref.startswith(canonical + "#") and ref not in present:
                    key = (field, ref)
                    if key not in seen:
                        seen.add(key)
                        problems.append(
                            f"{rel}: {field} points at {ref}, which is not a node "
                            f"on this page")
                return
            for key, item in value.items():
                if key != "@id":
                    walk(item, key)
        elif isinstance(value, list):
            for item in value:
                walk(item, field)

    for node in nodes:
        walk(node, "@graph")
    return problems


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
        page_nodes: list[dict] = []

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
                page_nodes.append(obj)

        errors.extend(dangling_same_page_refs(rel, canonical, page_nodes))
        errors.extend(check_physician_identity(rel, page_nodes))

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
