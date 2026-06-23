#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Write a clean robots.txt with explicit crawler policy."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


# CODE_REVIEW — UTF-8 console on Windows (cp950 default crashes on CJK).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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
    # AI answer-engine citation crawlers (NOT model-training scrapers).
    # Allowed so Claude + Gemini / Google AI Overviews can fetch and CITE
    # the article tree — mirrors the OpenAI split (OAI-SearchBot allowed,
    # GPTBot blocked). The site's llms.txt / ai.txt investment exists to be
    # cited by these engines, so they must be able to reach the content.
    "Claude-User",       # Anthropic — user-initiated fetch during a Claude chat
    "Claude-SearchBot",  # Anthropic — powers Claude's web search citations
    "ClaudeBot",         # Anthropic — indexes content that Claude.ai cites
    "Claude-Web",        # Anthropic — legacy on-demand fetcher
    "Google-Extended",   # gates Gemini grounding + Google AI Overviews citation
    "Perplexity-User",   # Perplexity — user-initiated citation fetch
    "DuckAssistBot",     # DuckDuckGo DuckAssist AI answers
    "AI2Bot",            # Allen Institute / Semantic Scholar (academic citation)
    "Applebot",          # Apple — Siri / Spotlight search surfacing
]

BLOCK_UAS = [
    "GPTBot",
    "anthropic-ai",
    "CCBot",
    "Applebot-Extended",            # Apple Intelligence model training
    "cohere-ai",                    # Cohere model training
    "cohere-training-data-crawler", # Cohere data crawler
    "Diffbot",                      # bulk structured-data scraping
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
    """Block training/aggregation crawlers from the site EXCEPT for the
    AI-facing manifest + corpus files, which exist for them to read.

    Allow rules take precedence over Disallow when they're more specific,
    so the bots can fetch llms.txt + llms-full.txt + sitemap.xml but
    can't crawl the full article tree to backfill their training data.
    """
    lines = [f"User-agent: {ua}" for ua in BLOCK_UAS]
    lines.append("Disallow: /")
    lines.append("Allow: /llms.txt")
    lines.append("Allow: /llms-full.txt")
    lines.append("Allow: /sitemap.xml")
    lines.append("Allow: /robots.txt")
    return lines


def existing_last_update() -> str | None:
    path = ROOT / "robots.txt"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# Last update: "):
            return line.rsplit(" ", 1)[-1]
    return None


def main() -> None:
    today = existing_last_update() or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "# ChenDermatologist · 陳翊嘉醫師 皮膚科衛教",
        f"# Site: {DOMAIN}/",
        f"# Last update: {today}",
        "#",
        "# Strategy:",
        "#   1. Allow search, ads, user-requested browsing, and AI answer-engine",
        "#      CITATION crawlers (ChatGPT/Perplexity/Claude search + Google AI).",
        "#   2. Block model-TRAINING and aggressive SEO/scraping crawlers (they may",
        "#      still fetch llms.txt + llms-full.txt + sitemap for citation grounding).",
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
