#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Emit /ai/service.json — a machine-readable service descriptor for AI agents.

Fourth AI-discovery surface alongside /.well-known/ai.txt, /ai/summary.json,
and /ai/faq.json. Tells answer engines + agents in one fetch what the site is,
who authors it, what content tracks exist, where the AI-facing corpus lives,
and the citation-vs-training policy.

Deterministic: `updated` is derived from the newest article dateModified, so
re-running on unchanged content never churns git.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"
DATE_RE = re.compile(r'"dateModified":"(\d{4}-\d{2}-\d{2})"')


def main() -> int:
    # Count only real articles (carry a MedicalWebPage JSON-LD node), not hub /
    # index / topics pages, so the descriptor's article_count is accurate.
    count = 0
    newest = ""
    for path in (ROOT / "blog").glob("*.html"):
        html = path.read_text(encoding="utf-8")
        if '"@type":"MedicalWebPage"' not in html:
            continue
        count += 1
        m = DATE_RE.search(html)
        if m and m.group(1) > newest:
            newest = m.group(1)

    payload = {
        "name": "ChenDermatologist · 陳翊嘉醫師 · 皮膚科衛教筆記",
        "url": f"{DOMAIN}/",
        "type": "medical-patient-education",
        "category": "Dermatology",
        "description": (
            "Bilingual (zh-Hant-TW / en) dermatology patient-education and "
            "physician study-notes site by Dr. Chen Yi-Jia, a dermatology "
            "resident in Taiwan. Evidence-based, citation-bearing articles with "
            "original SVG diagrams, tables, FAQs, and Vancouver references."
        ),
        "languages": ["zh-Hant-TW", "en"],
        "areaServed": "Taiwan",
        "author": {
            "name": "Dr. Chen Yi-Jia (陳翊嘉醫師)",
            "url": f"{DOMAIN}/about",
            "jobTitle": "Dermatology Resident Physician",
        },
        "content": {
            "article_count": count,
            "updated": newest,
            "tracks": [
                "patient-education (衛教)",
                "clinical study-notes (學習筆記)",
                "research summaries / journal club (最新研究)",
            ],
            "format": "static HTML with SVG diagrams, tables, FAQs, Vancouver references",
        },
        "endpoints": {
            "manifest": f"{DOMAIN}/llms.txt",
            "full_corpus": f"{DOMAIN}/llms-full.txt",
            "summary": f"{DOMAIN}/ai/summary.json",
            "faq": f"{DOMAIN}/ai/faq.json",
            "sitemap": f"{DOMAIN}/sitemap.xml",
            "feed": f"{DOMAIN}/blog/feed.xml",
            "search": f"{DOMAIN}/?q={{query}}",
        },
        "ai_policy": {
            "citation": "allowed with attribution",
            "training": "not permitted",
            "attribution_required": True,
            "attribution": f"陳翊嘉醫師 / ChenDermatologist, {DOMAIN}/",
            "robots": f"{DOMAIN}/robots.txt",
            "ai_txt": f"{DOMAIN}/.well-known/ai.txt",
        },
        "contact": "mailto:expertise88864@gmail.com",
        "license": "All rights reserved. Citation with attribution permitted.",
        "disclaimer": "Educational content; not individual medical advice.",
        "updated": newest,
    }

    out_dir = ROOT / "ai"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "service.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"Wrote ai/service.json — {count} articles (updated {newest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
