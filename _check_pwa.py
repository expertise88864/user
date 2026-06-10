#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit PWA manifest, offline page, and service-worker precache targets."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BAD_MOJIBAKE_RE = re.compile("(?:\\u00c3.|\\u00c2.|\\u00e2\\u20ac|\\ufffd)")


def has_bad_text(value: object) -> bool:
    if isinstance(value, str):
        return bool(BAD_MOJIBAKE_RE.search(value))
    if isinstance(value, list):
        return any(has_bad_text(item) for item in value)
    if isinstance(value, dict):
        return any(has_bad_text(item) for item in value.values())
    return False


def local_url_exists(url: str) -> bool:
    clean = url.split("?", 1)[0].split("#", 1)[0]
    if clean == "/":
        return (ROOT / "index.html").exists()
    if clean.endswith("/"):
        return (ROOT / clean.strip("/") / "index.html").exists()
    rel = clean.lstrip("/")
    return (
        (ROOT / rel).exists()
        or (ROOT / f"{rel}.html").exists()
        or (ROOT / rel / "index.html").exists()
    )


def audit_manifest(errors: list[str]) -> None:
    path = ROOT / "manifest.json"
    if not path.exists():
        errors.append("manifest.json is missing")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"manifest.json is invalid JSON: {exc}")
        return

    for field in ("name", "short_name", "description", "start_url", "display", "icons"):
        if field not in data:
            errors.append(f"manifest.json missing {field}")
    if has_bad_text(data):
        errors.append("manifest.json appears to contain mojibake text")
    if data.get("start_url") and not local_url_exists(data["start_url"]):
        errors.append(f"manifest start_url does not resolve locally: {data['start_url']}")

    icons = data.get("icons", [])
    if not isinstance(icons, list) or not icons:
        errors.append("manifest icons must be a non-empty list")
        return
    purposes = " ".join(str(icon.get("purpose", "")) for icon in icons if isinstance(icon, dict))
    if "maskable" not in purposes:
        errors.append("manifest icons should include a maskable icon")
    for icon in icons:
        if not isinstance(icon, dict):
            errors.append("manifest icon entry must be an object")
            continue
        src = icon.get("src")
        if not src or not local_url_exists(str(src)):
            errors.append(f"manifest icon missing locally: {src}")


def audit_offline(errors: list[str]) -> None:
    path = ROOT / "offline.html"
    if not path.exists():
        errors.append("offline.html is missing")
        return
    src = path.read_text(encoding="utf-8")
    if BAD_MOJIBAKE_RE.search(src):
        errors.append("offline.html appears to contain mojibake text")
    if '<meta name="robots" content="noindex,nofollow"' not in src:
        errors.append("offline.html should be noindex,nofollow")
    if 'id="retryConnection"' not in src:
        errors.append("offline.html missing retry button")
    if "addEventListener('online'" not in src and 'addEventListener("online"' not in src:
        errors.append("offline.html should reload when the browser comes back online")


def audit_service_worker(errors: list[str]) -> None:
    path = ROOT / "sw.js"
    if not path.exists():
        errors.append("sw.js is missing")
        return
    src = path.read_text(encoding="utf-8")
    if BAD_MOJIBAKE_RE.search(src):
        errors.append("sw.js appears to contain mojibake text")
    if "Promise.allSettled(PRECACHE.map" not in src:
        errors.append("sw.js should tolerate partial precache failures with Promise.allSettled")
    if "skipWaiting" not in src or "clients.claim" not in src:
        errors.append("sw.js should call skipWaiting and clients.claim for update reliability")
    # 2026-05-25 — switched from network-first to cache-first for ?v=
    # versioned assets. The version string IS the freshness signal, so
    # an exact cached URL is by definition fresh; old keys naturally
    # fall out via trimCache. This is the biggest remaining Edge
    # Request reduction (network-first defeated cache-bust entirely).
    if "/[?&]v=/" not in src:
        errors.append("sw.js should match ?v= via /[?&]v=/ regex (cache-first strategy)")
    if "url.pathname === '/assets/search-index.json'" not in src:
        errors.append("sw.js should handle generated search-index.json network-first")
    if "url.pathname.startsWith('/admin')" not in src:
        errors.append("sw.js should bypass /admin so the editor is always fresh")
    if "url.pathname.startsWith('/api/')" not in src:
        errors.append("sw.js should bypass /api so OAuth and dynamic API responses are never cached")
    if "url.pathname === '/reset-sw'" not in src:
        errors.append("sw.js should bypass reset-sw pages")

    match = re.search(r"const\s+PRECACHE\s*=\s*\[([\s\S]*?)\];", src)
    if not match:
        errors.append("sw.js PRECACHE list not found")
        return
    precache = re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))
    if not precache:
        errors.append("sw.js PRECACHE list is empty")
    for url in precache:
        if url.startswith("/") and not local_url_exists(url):
            errors.append(f"sw.js PRECACHE target missing locally: {url}")
        if re.search(r"\.js(?:$|\?)", url):
            errors.append(f"sw.js PRECACHE should not include JavaScript bundles; keep them network/runtime cached: {url}")


def main() -> int:
    errors: list[str] = []
    audit_manifest(errors)
    audit_offline(errors)
    audit_service_worker(errors)

    if errors:
        print("[FAIL] PWA audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1

    print("[OK] PWA audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
