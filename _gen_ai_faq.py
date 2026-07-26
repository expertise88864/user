#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Aggregate every article's FAQPage Q&A into a single static /ai/faq.json.

A machine-readable companion to llms-full.txt + /ai/summary.json: AI answer
engines and RAG pipelines can ingest one file of question->answer pairs that
the site already computes per article (the `data-faq-auto` FAQPage JSON-LD).

Deterministic: the `updated` field is derived from the newest article date
found (not a wall clock), so re-running on unchanged content produces an
identical file and never churns git.
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

LD_RE = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
CANON_RE = re.compile(r'<link rel="canonical" href="([^"]+)"')
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
DATE_RE = re.compile(r'"dateModified":"(\d{4}-\d{2}-\d{2})"')


def clean_title(raw: str) -> str:
    t = re.sub(r"\s+", " ", raw).strip()
    for suffix in (" | 陳翊嘉醫師", " | ChenDermatologist"):
        if t.endswith(suffix):
            t = t[: -len(suffix)].strip()
    return t


def extract(path: Path) -> tuple[dict | None, str]:
    html = path.read_text(encoding="utf-8")
    canon = CANON_RE.search(html)
    if not canon:
        return None, ""
    url = canon.group(1)
    title_m = TITLE_RE.search(html)
    title = clean_title(title_m.group(1)) if title_m else url
    date_m = DATE_RE.search(html)
    date = date_m.group(1) if date_m else ""

    faqs: list[dict] = []
    for block in LD_RE.findall(html):
        if '"@type":"FAQPage"' not in block and '"@type": "FAQPage"' not in block:
            continue
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        # A JSON-LD block may be a single object, a list, or an @graph wrapper.
        if isinstance(data, dict):
            nodes = data.get("@graph") if isinstance(data.get("@graph"), list) else [data]
        elif isinstance(data, list):
            nodes = data
        else:
            continue
        for node in nodes:
            if not isinstance(node, dict) or node.get("@type") != "FAQPage":
                continue
            for q in node.get("mainEntity", []) or []:
                if not isinstance(q, dict) or q.get("@type") != "Question":
                    continue
                name = (q.get("name") or "").strip()
                ans = ((q.get("acceptedAnswer") or {}).get("text") or "").strip()
                if name and ans:
                    faqs.append({"q": name, "a": ans})
    if not faqs:
        return None, date
    return {"url": url, "title": title, "faqs": faqs}, date


def main() -> int:
    # Canonical zh articles only (one entry per logical article; titles/urls
    # are the canonical zh-Hant surface). EN Q&A still live in the per-page
    # FAQPage JSON-LD on the /en mirror.
    articles: list[dict] = []
    newest = ""
    for path in sorted((ROOT / "blog").glob("*.html")):
        item, date = extract(path)
        if date > newest:
            newest = date
        if item:
            articles.append(item)

    total = sum(len(a["faqs"]) for a in articles)
    payload = {
        "@context": f"{DOMAIN}/ai/faq.json",
        "site": "ChenDermatologist · 陳翊嘉醫師 · 皮膚科衛教筆記",
        "url": f"{DOMAIN}/ai/faq.json",
        "description": (
            "Aggregated question-and-answer pairs across all articles, for AI "
            "answer engines and RAG pipelines. Companion to /llms-full.txt and "
            "/ai/summary.json. Attribution: Dr. Chen Yi-Jia (陳翊嘉醫師), "
            "https://chendermatologist.com/about. Citation with attribution permitted."
        ),
        "language": ["zh-Hant-TW", "en"],
        "updated": newest,
        "article_count": len(articles),
        "qa_count": total,
        "articles": articles,
    }

    out_dir = ROOT / "ai"
    # CODE_REVIEW TD-53 — no forced newline on write. This repo runs
    # core.autocrlf=true with no .gitattributes, so every other worktree file is
    # CRLF; forcing LF here left the generated file permanently reported as
    # modified after every build (measured: 6 files, byte-identical content).
    # git still normalises to LF in the blob, so the DEPLOYED bytes are unchanged.
    # Same decision already documented in _gen_llms_full.py.
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "faq.json"
    out_path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=1) + "\n", encoding="utf-8"
    )
    print(f"Wrote ai/faq.json — {len(articles)} articles, {total} Q&A (updated {newest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
