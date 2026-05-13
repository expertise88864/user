#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Write a clean robots.txt with explicit crawler policy."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"

ALLOW_UAS = [
    "*",
    "Googlebot",
    "Googlebot-Image",
    "Googlebot-News",
    "Bingbot",
    "DuckDuckBot",
    "Slurp",
    "Yandex",
    "Naverbot",
    "Yeti",
    "Mediapartners-Google",
    "AdsBot-Google",
    "AdsBot-Google-Mobile",
    "ChatGPT-User",
    "OAI-SearchBot",
    "PerplexityBot",
]

BLOCK_UAS = [
    "GPTBot",
    "ClaudeBot",
    "Claude-Web",
    "anthropic-ai",
    "CCBot",
    "Google-Extended",
    "FacebookBot",
    "Amazonbot",
    "Bytespider",
    "omgilibot",
    "omgili",
    "AhrefsBot",
    "SemrushBot",
    "MJ12bot",
    "DotBot",
    "BLEXBot",
    "PetalBot",
]

INTERNAL_DISALLOWS = [
    "/admin",
    "/admin/",
    "/admin.html",
    "/reset-sw",
    "/reset-sw.html",
    "/en/reset-sw",
    "/en/reset-sw.html",
    "/_tmp_*",
    "/_pso_*",
    "/_ad_*",
    "/_surgery_*",
]


def allow_group() -> list[str]:
    lines = [f"User-agent: {ua}" for ua in ALLOW_UAS]
    lines.append("Allow: /")
    lines.extend(f"Disallow: {rule}" for rule in INTERNAL_DISALLOWS)
    return lines


def block_group() -> list[str]:
    lines = [f"User-agent: {ua}" for ua in BLOCK_UAS]
    lines.append("Disallow: /")
    return lines


def main() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "# ChenDermatologist · 陳翊嘉醫師 皮膚科衛教",
        f"# Site: {DOMAIN}/",
        f"# Last update: {today}",
        "#",
        "# Strategy:",
        "#   1. Allow search, ads, and user-requested browsing crawlers.",
        "#   2. Block known AI-training and aggressive SEO/scraping crawlers.",
        "#   3. Block admin/reset/internal generated working files.",
        "",
        "# Public/search crawlers",
    ]

    groups: list[list[str]] = [allow_group(), block_group()]
    lines.extend("\n\n".join("\n".join(group) for group in groups).splitlines())
    lines.extend(["", f"Sitemap: {DOMAIN}/sitemap.xml", ""])

    (ROOT / "robots.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote robots.txt ({len(ALLOW_UAS)} allow user-agents, {len(BLOCK_UAS)} block user-agents)")


if __name__ == "__main__":
    main()
