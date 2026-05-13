#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit sitemap URLs against local HTML canonical/noindex state."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"
NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "xhtml": "http://www.w3.org/1999/xhtml",
    "image": "http://www.google.com/schemas/sitemap-image/1.1",
}


def local_html_for_url(url: str) -> Path | None:
    if not url.startswith(DOMAIN):
        return None
    slug = url[len(DOMAIN):].strip("/")
    candidates: list[Path]
    if not slug:
        candidates = [ROOT / "index.html"]
    else:
        candidates = [
            ROOT / f"{slug}.html",
            ROOT / slug / "index.html",
        ]
    return next((path for path in candidates if path.exists()), None)


def canonical_of(src: str) -> str:
    match = re.search(r'<link\s+rel="canonical"\s+href="([^"]*)"', src, re.I)
    return match.group(1) if match else ""


def is_noindex(src: str) -> bool:
    match = re.search(r'<meta\s+name="robots"\s+content="([^"]*)"', src, re.I)
    return bool(match and "noindex" in match.group(1).lower())


def main() -> int:
    sitemap = ROOT / "sitemap.xml"
    if not sitemap.exists():
        print("[FAIL] sitemap.xml is missing")
        return 1

    errors: list[str] = []
    tree = ET.parse(sitemap)
    root = tree.getroot()
    page_locs: list[str] = []

    for url_el in root.findall("sm:url", NS):
        loc_el = url_el.find("sm:loc", NS)
        if loc_el is None or not (loc_el.text or "").strip():
            errors.append("sitemap <url> missing <loc>")
            continue
        loc = loc_el.text.strip()
        page_locs.append(loc)

        if not loc.startswith(DOMAIN + "/") and loc != DOMAIN:
            errors.append(f"{loc}: sitemap URL must use {DOMAIN}")

        html_path = local_html_for_url(loc)
        if html_path is None:
            errors.append(f"{loc}: no matching local HTML file")
            continue

        src = html_path.read_text(encoding="utf-8")
        canonical = canonical_of(src)
        if canonical != loc:
            rel = html_path.relative_to(ROOT).as_posix()
            errors.append(f"{loc}: sitemap loc does not match {rel} canonical ({canonical or 'missing'})")
        if is_noindex(src):
            rel = html_path.relative_to(ROOT).as_posix()
            errors.append(f"{loc}: noindex page included in sitemap ({rel})")

        alt_hrefs = [
            (alt.get("hreflang") or "", alt.get("href") or "")
            for alt in url_el.findall("xhtml:link", NS)
            if (alt.get("rel") or "").lower() == "alternate"
        ]
        if alt_hrefs:
            langs = [lang for lang, _ in alt_hrefs]
            if "x-default" not in langs:
                errors.append(f"{loc}: sitemap alternate set missing x-default")
            if len(set(langs)) != len(langs):
                errors.append(f"{loc}: sitemap alternate set has duplicate hreflang values")
            for lang, href in alt_hrefs:
                target = local_html_for_url(href)
                if target is None:
                    errors.append(f"{loc}: hreflang {lang} target missing local HTML ({href})")
                    continue
                target_src = target.read_text(encoding="utf-8")
                if canonical_of(target_src) != href:
                    rel = target.relative_to(ROOT).as_posix()
                    errors.append(f"{loc}: hreflang {lang} target canonical mismatch in {rel}")
                if is_noindex(target_src):
                    rel = target.relative_to(ROOT).as_posix()
                    errors.append(f"{loc}: hreflang {lang} target is noindex ({rel})")

    duplicates = sorted({url for url in page_locs if page_locs.count(url) > 1})
    for url in duplicates:
        errors.append(f"{url}: duplicate sitemap <loc>")

    if errors:
        print("[FAIL] sitemap audit found issues:")
        for error in errors[:120]:
            print(" - " + error)
        if len(errors) > 120:
            print(f" ... {len(errors) - 120} more")
        return 1

    print(f"[OK] sitemap audit passed ({len(page_locs)} page URLs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
