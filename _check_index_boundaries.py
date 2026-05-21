#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit indexable/public page boundaries for sitemap, robots, and noindex pages."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[\s\S]*?</\1>", re.I)
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

PRIVATE_PAGES = {
    "admin.html": {"route": "/admin", "robots": "noindex,nofollow", "blocked": True},
    "admin/index.html": {"route": "/admin/", "robots": "noindex,nofollow", "blocked": True},
    "reset-sw.html": {"route": "/reset-sw", "robots": "noindex,nofollow", "blocked": True},
    "en/reset-sw.html": {"route": "/en/reset-sw", "robots": "noindex,nofollow", "blocked": True},
    "offline.html": {"route": "/offline", "robots": "noindex,nofollow", "blocked": False},
    "404.html": {"route": "/404", "robots": "noindex,follow", "blocked": False},
}

PUBLIC_STATIC_ROUTES = {
    "/",
    "/about",
    "/blog",
    "/blog/topics",
    "/dashboard",
    "/glossary",
    # /notes intentionally omitted — page is noindex while content is
    # being drafted (SEO_AUDIT A1). Re-add when content ships and the
    # robots meta flips back to index,follow.
    "/privacy",
    "/support",
    "/tools",
}


def headish(path: Path) -> str:
    return SCRIPT_STYLE_RE.sub("", path.read_text(encoding="utf-8"))


def robots_meta(src: str) -> str:
    match = re.search(r'<meta\s+name="robots"\s+content="([^"]*)"', src, re.I)
    return (match.group(1) if match else "").lower().replace(" ", "")


def sitemap_routes() -> set[str]:
    tree = ET.parse(ROOT / "sitemap.xml")
    routes: set[str] = set()
    for loc in tree.getroot().findall("sm:url/sm:loc", NS):
        url = (loc.text or "").strip()
        if not url.startswith(DOMAIN):
            continue
        route = url[len(DOMAIN) :] or "/"
        routes.add(route)
    return routes


def robots_disallows() -> set[str]:
    rules: set[str] = set()
    for line in (ROOT / "robots.txt").read_text(encoding="utf-8").splitlines():
        if line.lower().startswith("disallow:"):
            rules.add(line.split(":", 1)[1].strip())
    return rules


def parse_robots(src: str) -> list[tuple[list[str], list[tuple[str, str]]]]:
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    for raw in src.split("\n\n"):
        uas: list[str] = []
        rules: list[tuple[str, str]] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key == "user-agent":
                uas.append(value.lower())
            elif key in {"allow", "disallow"}:
                rules.append((key, value))
        if uas:
            groups.append((uas, rules))
    return groups


def rules_for(user_agent: str, groups: list[tuple[list[str], list[tuple[str, str]]]]) -> list[tuple[str, str]]:
    ua = user_agent.lower()
    for uas, rules in groups:
        if ua in uas:
            return rules
    for uas, rules in groups:
        if "*" in uas:
            return rules
    return []


def disallowed(path: str, rules: list[tuple[str, str]]) -> bool:
    best: tuple[str, str] | None = None
    for kind, pattern in rules:
        if not pattern:
            continue
        prefix = pattern.rstrip("*")
        if path.startswith(prefix) and (best is None or len(prefix) > len(best[1].rstrip("*"))):
            best = (kind, pattern)
    return bool(best and best[0] == "disallow")


def main() -> int:
    errors: list[str] = []
    routes = sitemap_routes()
    robots_src = (ROOT / "robots.txt").read_text(encoding="utf-8")
    disallows = robots_disallows()
    googlebot_rules = rules_for("Googlebot", parse_robots(robots_src))

    for rel, expected in PRIVATE_PAGES.items():
        path = ROOT / rel
        if not path.exists():
            errors.append(f"{rel}: expected private/noindex page is missing")
            continue
        meta = robots_meta(headish(path))
        if meta != expected["robots"]:
            errors.append(f"{rel}: robots meta should be {expected['robots']}, got {meta or 'missing'}")
        route = str(expected["route"])
        if route in routes:
            errors.append(f"{rel}: private/noindex route is included in sitemap ({route})")
        if expected["blocked"] and route not in disallows:
            errors.append(f"{rel}: private route should be disallowed in robots.txt ({route})")

    for route in sorted(PUBLIC_STATIC_ROUTES):
        if route not in routes:
            errors.append(f"{route}: public static route missing from sitemap")
        if disallowed(route, googlebot_rules):
            errors.append(f"{route}: public static route is blocked by robots.txt")

    if errors:
        print("[FAIL] Index boundary audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1

    print("[OK] Index boundary audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
