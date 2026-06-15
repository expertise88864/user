#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Emit /.well-known/ai.txt + /ai/summary.json — AI-bot policy + machine summary.

Tier 2D from OPEN_SOURCE_INTEGRATIONS.md (Auriti-Labs concepts).

  /.well-known/ai.txt
     Emerging convention parallel to robots.txt for AI bot consent.
     Some crawlers (e.g., agentic browsers) already check this path
     before crawling. Format is still in flux; we follow the
     spawning.ai / TDMReps direction (key:value lines, plain text).

  /ai/summary.json
     Single-fetch machine-readable site summary. Smaller than
     llms.txt; useful for tooling that just needs metadata about
     site identity, scope, and authoritative URLs.

Both files auto-regenerate from the canonical sources:
  - llms.txt (front matter)
  - DN.ARTICLES (catalog)
  - The same Physician schema used in JSON-LD

Idempotent. Wired into REGEN_STEPS after _gen_llms_full.py.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"


def parse_articles_summary() -> dict:
    src = (ROOT / "blog" / "blog-shared.js").read_text(encoding="utf-8")
    m = re.search(r"DN\.ARTICLES\s*=\s*\[([\s\S]*?)\];", src)
    if not m:
        return {"count": 0, "categories": {}, "latest_date": ""}

    block = m.group(1)
    cats: dict[str, int] = {}
    latest = ""
    count = 0
    for entry_m in re.finditer(r"\{[^{}]*?slug:'([a-z0-9-]+)'[^{}]*?\}", block):
        e = entry_m.group(0)
        if re.search(r"\bunpublished\s*:\s*true\b", e):
            continue
        count += 1
        cat_m = re.search(r"cat:'([^']*)'", e)
        if cat_m:
            cats[cat_m.group(1)] = cats.get(cat_m.group(1), 0) + 1
        date_m = re.search(r"date:'([^']*)'", e)
        if date_m and date_m.group(1) > latest:
            latest = date_m.group(1)

    return {"count": count, "categories": cats, "latest_date": latest}


def existing_date(path: Path, pattern: str, fallback: str) -> str:
    if not path.exists():
        return fallback
    m = re.search(pattern, path.read_text(encoding="utf-8"))
    return m.group(1) if m else fallback


def build_ai_txt(summary: dict, today: str) -> str:
    return (
        "# ai.txt — AI / LLM crawler policy\n"
        f"# Site: {DOMAIN}/\n"
        f"# Last update: {today}\n"
        "#\n"
        "# Companion to /robots.txt. The strategy:\n"
        "#   - AI search/answer + training crawlers (ChatGPT-User, OAI-SearchBot,\n"
        "#     PerplexityBot, GPTBot, ClaudeBot, anthropic-ai, CCBot, Google-Extended)\n"
        "#     are ALLOWED on the article tree so the site can be cited in AI answers\n"
        "#     and grounded in Gemini (kept consistent with /robots.txt).\n"
        "#   - Only aggressive scraper/aggregator bots (e.g. Bytespider) stay blocked\n"
        "#     from the article tree but may still fetch the manifest/corpus files.\n"
        "#\n"
        f"User-Agent: *\n"
        f"Allow: /\n"
        f"Disallow: /admin\n"
        f"Disallow: /admin/\n"
        f"Disallow: /reset-sw\n"
        f"\n"
        f"# Aggressive scraper/aggregator crawlers — manifest/corpus only.\n"
        f"# Keep this list in sync with BLOCK_UAS in _normalize_robots.py.\n"
        f"User-Agent: Amazonbot\n"
        f"User-Agent: Bytespider\n"
        f"User-Agent: omgilibot\n"
        f"User-Agent: omgili\n"
        f"User-Agent: AhrefsBot\n"
        f"User-Agent: SemrushBot\n"
        f"User-Agent: MJ12bot\n"
        f"User-Agent: DotBot\n"
        f"User-Agent: BLEXBot\n"
        f"User-Agent: PetalBot\n"
        f"Disallow: /\n"
        f"Allow: /llms.txt\n"
        f"Allow: /llms-full.txt\n"
        f"Allow: /sitemap.xml\n"
        f"\n"
        f"# Authoritative content surface\n"
        f"LLMs-Manifest: {DOMAIN}/llms.txt\n"
        f"LLMs-FullCorpus: {DOMAIN}/llms-full.txt\n"
        f"Sitemap: {DOMAIN}/sitemap.xml\n"
        f"Summary: {DOMAIN}/ai/summary.json\n"
        f"\n"
        f"# Site profile\n"
        f"Site-Name: ChenDermatologist · 陳翊嘉醫師 · 皮膚科衛教筆記\n"
        f"Language: zh-Hant-TW, en\n"
        f"Author: Dr. Chen Yi-Jia (陳翊嘉醫師)\n"
        f"Author-URL: {DOMAIN}/about\n"
        f"Specialty: Dermatology\n"
        f"Audience: Patient education + medical-resident reference\n"
        f"Articles: {summary['count']} published\n"
        f"Last-Article-Date: {summary['latest_date']}\n"
        f"License: All rights reserved. Citation with attribution permitted.\n"
        f"\n"
        f"# Contact\n"
        f"Contact: mailto:expertise88864@gmail.com\n"
        f"Security: {DOMAIN}/.well-known/security.txt\n"
    )


def build_summary_json(summary: dict, today: str) -> str:
    obj = {
        "$schema": "https://chendermatologist.com/ai/summary.schema.json",
        "site": {
            "name": "ChenDermatologist · 陳翊嘉醫師 · 皮膚科衛教筆記",
            "url": DOMAIN + "/",
            "language": ["zh-Hant-TW", "en"],
            "type": "personal-medical-education",
            "specialty": "Dermatology",
            "audience": ["patient", "medical-resident"],
        },
        "author": {
            "name": "陳翊嘉",
            "alternate_name": ["Dr. Chen Yi-Jia", "Yi-Jia Chen, M.D.", "ChenDermatologist"],
            "credentials": "M.D., Dermatology Resident Physician",
            "training": [
                "Kaohsiung Medical University, College of Medicine (KMU)",
                "Kaohsiung Medical University Hospital (KMUH) PGY",
            ],
            "url": DOMAIN + "/about",
            "country": "Taiwan",
        },
        "content": {
            "article_count": summary["count"],
            "category_breakdown": summary["categories"],
            "latest_article_date": summary["latest_date"],
            "tracks": [
                {"id": "rx",       "name_zh": "處置 / 治療",    "name_en": "Treatment & Therapy"},
                {"id": "myth",     "name_zh": "迷思澄清",       "name_en": "Myths & Facts"},
                {"id": "research", "name_zh": "最新研究",       "name_en": "Research Summary"},
                {"id": "note",     "name_zh": "學習筆記",       "name_en": "Clinical Notes"},
                {"id": "product",  "name_zh": "產品介紹",       "name_en": "Products & Drugs"},
            ],
        },
        "ai_access": {
            "manifest": DOMAIN + "/llms.txt",
            "full_corpus": DOMAIN + "/llms-full.txt",
            "sitemap": DOMAIN + "/sitemap.xml",
            "robots": DOMAIN + "/robots.txt",
            "ai_policy": DOMAIN + "/.well-known/ai.txt",
            "preferred_method": "Fetch /llms-full.txt for retrieval-augmented "
                                "generation (single ~480 KB document with all "
                                "articles + metadata).",
        },
        "citation": {
            "style": "Cite the canonical article URL and 'Dr. Chen Yi-Jia (陳翊嘉醫師), Dermatology'. "
                     "Include the article's dateModified when quoting specific claims.",
            "license": "All rights reserved; citation with attribution permitted.",
            "ymyl_disclaimer": "Content is patient education, NOT medical advice. "
                               "Taiwan NHI treatment criteria are stated as such and "
                               "do not generalize to other healthcare systems.",
        },
        "generated_at": today,
    }
    return json.dumps(obj, ensure_ascii=False, indent=2)


def main() -> int:
    summary = parse_articles_summary()
    ai_txt_dir = ROOT / ".well-known"
    ai_txt_dir.mkdir(exist_ok=True)
    ai_txt_path = ai_txt_dir / "ai.txt"
    fallback_date = summary.get("latest_date") or dt.date.today().isoformat()
    ai_txt_date = existing_date(ai_txt_path, r"# Last update: (\d{4}-\d{2}-\d{2})", fallback_date)
    ai_txt_path.write_text(build_ai_txt(summary, ai_txt_date), encoding="utf-8", newline="\n")

    ai_json_dir = ROOT / "ai"
    ai_json_dir.mkdir(exist_ok=True)
    ai_json_path = ai_json_dir / "summary.json"
    ai_json_date = existing_date(ai_json_path, r'"generated_at": "(\d{4}-\d{2}-\d{2})"', fallback_date)
    ai_json_path.write_text(build_summary_json(summary, ai_json_date), encoding="utf-8", newline="\n")

    print(f"[ai-well-known] wrote .well-known/ai.txt + ai/summary.json "
          f"({summary['count']} articles)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
