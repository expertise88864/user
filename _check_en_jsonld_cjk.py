#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The /en mirror's structured data must be English.

Every JSON-LD block on en/**/*.html is parsed and every string value is
scanned for CJK characters. Exempt, because they are identities rather than
text, and must stay identical to the zh pages:
  * alternateName — schema.org's slot for an entity's other-language names;
  * IRIs (@id, url, item, sameAs, …) — e.g. /glossary#term-蕈狀肉芽腫, which
    _check_bilingual_attrs.py requires to equal the zh glossary identities;
  * the physician node's name parts — CODE_REVIEW TD-72 fixes ONE name,
    "陳翊嘉 醫師", under https://chendermatologist.com/about#physician on every
    page in both locales (_audit_jsonld.PHYSICIAN_NAMES); a Person/Physician
    node without the @id that carries exactly that name is the same person.

Background: before 2026-10-18 the /en pages carried 573 Chinese strings in
JSON-LD (citation / isBasedOn names, related-article titles, author name,
keywords, glossary @id fragments). _localize_en_jsonld.py now localizes them as
the last regeneration step; this check keeps it that way. Unlike the visible-
text en-leak scan, it reads the head too, which is where the leak was.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CJK = re.compile(r"[㐀-鿿豈-﫿]")
LD_RE = re.compile(r'<script\b[^>]*type="application/ld\+json"[^>]*>([\s\S]*?)</script>', re.I)
EXEMPT_KEYS = frozenset({"alternateName"})
IRI_KEYS = frozenset({"@id", "url", "item", "sameAs", "contentUrl", "embedUrl", "thumbnailUrl", "image", "logo",
                      "mainEntityOfPage", "target", "urlTemplate"})
PHYSICIAN_ID = "https://chendermatologist.com/about#physician"
PHYSICIAN_IDENTITY_KEYS = frozenset({"name", "givenName", "familyName"})
PHYSICIAN_NAMES = frozenset({"陳翊嘉 醫師"})  # same set as _audit_jsonld.PHYSICIAN_NAMES
MIN_FILES = 55  # anti-vacuity: the /en mirror has 64 pages (2026-10)


def leaks(obj, path="$"):
    if isinstance(obj, dict):
        physician = obj.get("@id") == PHYSICIAN_ID or (
            obj.get("@type") in ("Person", "Physician") and obj.get("name") in PHYSICIAN_NAMES)
        for k, v in obj.items():
            if k in EXEMPT_KEYS or (physician and k in PHYSICIAN_IDENTITY_KEYS):
                continue
            if k in IRI_KEYS and isinstance(v, (str, list)) and all(
                    isinstance(x, str) and x.startswith("http") for x in (v if isinstance(v, list) else [v])):
                continue
            yield from leaks(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from leaks(v, f"{path}[{i}]")
    elif isinstance(obj, str) and CJK.search(obj):
        yield path, obj


def scan(src: str) -> list[tuple[str, str]]:
    out = []
    for n, m in enumerate(LD_RE.finditer(src)):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            out.append((f"block {n}", "unparseable JSON-LD"))
            continue
        out.extend((f"block {n} {p}", v) for p, v in leaks(obj))
    return out


def main(root: Path = ROOT) -> int:
    pages = sorted((root / "en").rglob("*.html"))
    errors = []
    for p in pages:
        rel = p.relative_to(root).as_posix()
        for where, value in scan(p.read_text(encoding="utf-8", errors="replace")):
            errors.append(f"{rel}: {where}: {value[:120]}")
    if len(pages) < MIN_FILES:
        errors.append(f"only {len(pages)} /en page(s) found (expected >= {MIN_FILES}) — discovery is broken")
    if errors:
        print(f"[FAIL] {len(errors)} Chinese string(s) in /en JSON-LD "
              "(run _localize_en_jsonld.py; add a translation there, never delete the data):")
        for e in errors[:30]:
            print(f"  - {e}")
        if len(errors) > 30:
            print(f"  … and {len(errors) - 30} more")
        return 1
    print(f"[OK] no CJK in JSON-LD of {len(pages)} /en pages (alternateName, IRIs, physician name exempt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
