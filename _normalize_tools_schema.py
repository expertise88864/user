#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inject a WebApplication @graph into /tools.html for the 10 calculators.

Why: /tools.html is the calculator hub linking to 10 embedded
calculators (SCORAD, PASI, DLQI, SALT, UAS7, GAGS, MASI, Hurley,
Norwood-Hamilton/Ludwig, Fitzpatrick). Each one is interactive but
currently has no schema.org SoftwareApplication signal — so Google
treats them as plain page content instead of "free tools."

Adding a WebApplication @graph unlocks:
  • Google's "free interactive tool" rich-card in SERPs (high CTR for
    queries like "PASI calculator", "SCORAD score online")
  • Deep-linking via the #anchor URL inside the article that hosts it
  • applicationCategory=MedicalApplication routes to medical app
    cluster in app-store-style results

Each tool is parsed from <article class="tool-block"> in tools.html.
We extract: id (anchor), name (H2 text), deep-link URL (first /blog/
href inside the block), and one-line description (the .tool-sub p
or first <p> body).

Mirrored to /en/tools.html with same structure but EN naming.
Idempotent: replaces #dn-tools-schema block on each run.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
TOOLS_ZH = ROOT / "tools.html"
TOOLS_EN = ROOT / "en" / "tools.html"
CANONICAL_HOST = "https://chendermatologist.com"


# --- Parsing helpers --------------------------------------------------------

TAG_RE = re.compile(r'<[^>]+>')


def strip_html(s: str) -> str:
    s = TAG_RE.sub('', s)
    s = (s.replace('&amp;', '&')
          .replace('&lt;', '<')
          .replace('&gt;', '>')
          .replace('&quot;', '"')
          .replace('&#39;', "'")
          .replace('&nbsp;', ' '))
    return re.sub(r'\s+', ' ', s).strip()


TOOL_BLOCK_RE = re.compile(
    r'<article class="tool-block" id="(?P<id>[^"]+)">(?P<body>[\s\S]*?)</article>',
    re.IGNORECASE,
)
H2_RE = re.compile(r'<h2[^>]*>([\s\S]*?)</h2>', re.IGNORECASE)
DEEP_LINK_RE = re.compile(
    r'<a[^>]+href="(/blog/[^"]+#[^"]+)"',
    re.IGNORECASE,
)
SUB_PARA_RE = re.compile(
    r'<p[^>]*class="[^"]*tool-sub[^"]*"[^>]*>([\s\S]*?)</p>',
    re.IGNORECASE,
)
ANY_PARA_RE = re.compile(r'<p[^>]*>([\s\S]{0,400})</p>', re.IGNORECASE)


def parse_tools(src: str) -> list[dict]:
    out: list[dict] = []
    for m in TOOL_BLOCK_RE.finditer(src):
        tool_id = m.group("id")
        body = m.group("body")
        h2 = H2_RE.search(body)
        name = strip_html(h2.group(1)) if h2 else tool_id.upper()
        # Strip the leading "01" / "02" ordinal that the page uses for layout.
        # The H2 has <span class="tool-num">01</span>SCORAD with no space —
        # strip_html collapses them to "01SCORAD", so we allow zero spaces.
        name = re.sub(r'^\d{1,2}\s*', '', name)
        link = DEEP_LINK_RE.search(body)
        link_url = link.group(1) if link else f"/tools#{tool_id}"
        # Description: prefer .tool-sub paragraph, else first <p>
        sub = SUB_PARA_RE.search(body)
        if not sub:
            sub = ANY_PARA_RE.search(body)
        description = strip_html(sub.group(1)) if sub else ""
        # Cap at 250 chars (rich-card description budget)
        description = description[:250]
        out.append({
            "id": tool_id,
            "name": name,
            "url": link_url,
            "description": description,
        })
    return out


# --- Build SoftwareApplication objects --------------------------------------

# Map tool_id → ICD-10 / target condition for the relatedDisease field.
# Helps Google route the calculator to disease-specific search clusters.
TOOL_TO_DISEASE = {
    "scorad": {"name": "Atopic dermatitis", "icd10": "L20.9"},
    "pasi": {"name": "Psoriasis vulgaris", "icd10": "L40.0"},
    "dlqi": {"name": "Dermatology (generic quality-of-life)", "icd10": None},
    "salt": {"name": "Alopecia areata", "icd10": "L63.9"},
    "uas7": {"name": "Chronic urticaria", "icd10": "L50.1"},
    "gags": {"name": "Acne vulgaris", "icd10": "L70.0"},
    "masi": {"name": "Melasma", "icd10": "L81.1"},
    "hurley": {"name": "Hidradenitis suppurativa", "icd10": "L73.2"},
    "norwood": {"name": "Androgenetic alopecia", "icd10": "L64.9"},
    "fitzpatrick": {"name": "Skin phototyping", "icd10": None},
}


def build_app(tool: dict, lang: str) -> dict:
    inLang = "en" if lang == "en" else "zh-Hant-TW"
    abs_url = CANONICAL_HOST + ("/en" if lang == "en" else "") + tool["url"]
    app: dict = {
        "@type": "WebApplication",
        "@id": CANONICAL_HOST + ("/en/tools" if lang == "en" else "/tools")
               + "#tool-" + tool["id"],
        "name": tool["name"] if lang == "en" else (
            tool["name"] + "（線上計算器）"
        ),
        "applicationCategory": "MedicalApplication",
        "applicationSubCategory": "HealthApplication",
        "operatingSystem": "Any (Web browser)",
        "browserRequirements": "Requires JavaScript. Requires HTML5.",
        "isAccessibleForFree": True,
        "url": abs_url,
        "inLanguage": inLang,
        "audience": {
            "@type": "MedicalAudience",
            "audienceType": ["Patient", "Clinician"],
        },
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "TWD",
        },
    }
    if tool["description"]:
        app["description"] = tool["description"]
    target = TOOL_TO_DISEASE.get(tool["id"])
    if target and target.get("name"):
        cond: dict = {
            "@type": "MedicalCondition",
            "name": target["name"],
        }
        if target.get("icd10"):
            cond["code"] = {
                "@type": "MedicalCode",
                "code": target["icd10"],
                "codingSystem": "ICD-10-CM",
            }
        app["featureList"] = f"Scoring scale for {target['name']}"
        app["about"] = cond
    return app


def build_graph(tools: list[dict], lang: str) -> dict:
    apps = [build_app(t, lang) for t in tools]
    return {
        "@context": "https://schema.org",
        "@graph": apps,
    }


# --- Injection --------------------------------------------------------------

EXISTING_RE = re.compile(
    r'<script type="application/ld\+json" id="dn-tools-schema">.*?</script>\s*',
    re.DOTALL,
)


def inject(html: str, graph: dict) -> tuple[str, bool]:
    body = json.dumps(graph, ensure_ascii=False, separators=(',', ':'))
    new_block = (
        '<script type="application/ld+json" id="dn-tools-schema">'
        f'{body}'
        '</script>\n'
    )
    if EXISTING_RE.search(html):
        new_html = EXISTING_RE.sub(new_block, html, count=1)
        return new_html, new_html != html
    head_close = html.find("</head>")
    if head_close == -1:
        return html, False
    new_html = html[:head_close] + new_block + html[head_close:]
    return new_html, True


# --- Main -------------------------------------------------------------------

def process(fp: Path, lang: str) -> tuple[bool, int]:
    if not fp.exists():
        return False, 0
    src = fp.read_text(encoding="utf-8")
    tools = parse_tools(src)
    if not tools:
        return False, 0
    graph = build_graph(tools, lang)
    new_src, changed = inject(src, graph)
    if changed:
        fp.write_text(new_src, encoding="utf-8")
    return changed, len(tools)


def main() -> int:
    changed_zh, n_zh = process(TOOLS_ZH, "zh")
    changed_en, n_en = process(TOOLS_EN, "en")
    n_total_changes = (1 if changed_zh else 0) + (1 if changed_en else 0)
    print(f"[tools-schema] emitted WebApplication @graph with {n_zh} "
          f"calculator entries to {n_total_changes} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
