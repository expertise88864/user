#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Final pass: make every JSON-LD block on the /en mirror English.

WHY
===
_gen_en_pages.py copies each zh page's JSON-LD into its /en mirror and only
re-labels headline/name/description/breadcrumbs. Everything else stayed
Chinese on the English pages: citation and isBasedOn names (Chinese reference
titles, the 「來源」 source label), related-article ItemList titles, the author
/ publisher / reviewer name, Chinese keywords, glossary @id fragments, and the
site-identity blocks on /en and /en/about (measured 2026-10-18: 573 CJK strings
on 61 of 64 /en pages).

It was also not idempotent. isBasedOn is derived on the zh page by
_normalize_is_based_on.py, which runs AFTER _gen_en_pages.py; an /en mirror
without its own reference list kept whatever isBasedOn the zh page had when it
was copied. When a zh reference changes, the first regeneration wrote the old
value into /en and only the second one caught up (the 2026-10-18 CI failure on
en/blog/prurigo-nodularis.html, "Canonical generated file consistency").

WHAT THIS DOES (runs after every step that writes /en JSON-LD)
=============================================================
* isBasedOn on an /en page without its own reference list is rebuilt from the
  zh page's final #dn-citations graph (same selection as
  _normalize_is_based_on.build_is_based_on), so one run is enough.
* Citation names (any ScholarlyArticle in @graph / isBasedOn / citation) are
  translated through the zh page's own reference list: each <li> is parsed
  twice by _normalize_citations.parse_citation, once as Chinese and once as the
  /en mirror renders it from data-en. References with no English rendering
  fall back to CITATION_EN below. Nothing is dropped.
* ItemList entries take the article's English title from DN.ARTICLES (title_en).
* Fixed site-identity strings come from TEXT_EN; the Chinese original is kept
  in alternateName where the object can carry one.
* keywords: Chinese synonyms of the English terms already listed are dropped
  (皮膚科 / 衛教 become "dermatology" / "patient education").
* Left as they are, because they are identities, not text: alternateName (the
  schema.org slot for other-language names), IRIs (@id, url, item, sameAs, …,
  which must equal the zh pages' IRIs, e.g. /glossary#term-蕈狀肉芽腫 — see
  _check_bilingual_attrs.py), and the physician node's name parts (TD-72: one
  name, "陳翊嘉 醫師", under https://chendermatologist.com/about#physician).

_check_en_jsonld_cjk.py fails the build if any CJK is left outside those. The visible /en page text is not touched.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from _gen_en_pages import apply_data_en  # noqa: E402
from _json_html import script_json  # noqa: E402
from _normalize_citations import LI_RE, OL_RE, parse_citation  # noqa: E402
from _normalize_is_based_on import build_is_based_on, load_citations  # noqa: E402
from _sync_hub_catalog import load_catalog  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CJK = re.compile(r"[㐀-鿿豈-﫿]")
LD_RE = re.compile(r'(<script\b[^>]*type="application/ld\+json"[^>]*>)([\s\S]*?)</script>', re.I)
URL_KEYS = frozenset({"@id", "url", "item", "sameAs", "contentUrl", "embedUrl", "thumbnailUrl", "image", "logo",
                      "mainEntityOfPage", "target", "urlTemplate"})
PAGE_TYPES = frozenset({"MedicalWebPage", "MedicalScholarlyArticle"})
CITATION_TYPES = frozenset({"ScholarlyArticle", "CreativeWork", "Article"})
# CODE_REVIEW TD-72 (_audit_jsonld.PHYSICIAN_NAMES): the physician entity has ONE
# name, "陳翊嘉 醫師", on every page in both locales. That is a decided identity
# contract, so the physician node keeps its name parts; only text is localized.
PHYSICIAN_ID = "https://chendermatologist.com/about#physician"
PHYSICIAN_IDENTITY_KEYS = frozenset({"name", "givenName", "familyName"})

# Site identity and hub pages: exact zh string -> English.
TEXT_EN = {
    "陳翊嘉醫師": "Dr. Chen Yi-Jia",
    "醫師 (Licensed Physician, Taiwan)": "Licensed Physician (Taiwan)",
    "衛生福利部 Ministry of Health and Welfare (Taiwan)": "Ministry of Health and Welfare (Taiwan)",
    "關於 陳翊嘉醫師 — About Dr. Chen Yi-Jia": "About Dr. Chen Yi-Jia",
    "陳翊嘉醫師 · 皮膚科衛教筆記": "Dr. Chen Yi-Jia · Dermatology Notes",
    "ChenDermatologist · 陳翊嘉醫師 · 皮膚科衛教筆記": "ChenDermatologist · Dr. Chen Yi-Jia · Dermatology Notes",
    "陳翊嘉醫師 · 皮膚科 · ChenDermatologist": "Dr. Chen Yi-Jia · Dermatology · ChenDermatologist",
    "皮膚科主題地圖 | 陳翊嘉醫師": "Dermatology topic map | Dr. Chen Yi-Jia",
    "所有皮膚科衛教文章按主題整理 — 痘痘、防曬、異膚、肝斑、酸類、A 酸、落髮、香港腳。":
        "All dermatology patient-education articles by topic — acne, sunscreen, atopic dermatitis, melasma, "
        "topical acids, retinoids, hair loss, athlete's foot.",
    "。皮膚科。專長：一般皮膚病、痘痘、痘疤、玫瑰斑、異位性皮膚炎、乾癬、圓禿、生物製劑、雷射光電、皮膚外科。":
        "Dermatology. Interests: general dermatology, acne, acne scars, rosacea, atopic dermatitis, psoriasis, "
        "alopecia areata, biologics, lasers and energy-based devices, dermatologic surgery.",
    "首頁": "Home",
    "支持本站": "Support this site",
    "Prurigo nodularis (PN) is called 結節性癢疹 in Chinese. Read about its definition, itch and nodules, "
    "diagnostic assessment, treatment options and references.":
        "Prurigo nodularis (PN): read about its definition, itch and nodules, diagnostic assessment, "
        "treatment options and references.",
}
KEYWORD_EN = {"皮膚科": "dermatology", "衛教": "patient education"}

# References that the zh page lists without any English rendering.
# zh citation name (as _normalize_citations parses it) -> English name.
CITATION_EN = {
    "衛生福利部中央健康保險署．全民健康保險藥品給付規定（115/9/22 版）．第 13 節 皮膚科製劑．https://www.nhi.gov.tw/":
        "National Health Insurance Administration, Ministry of Health and Welfare (Taiwan). National Health "
        "Insurance Drug Reimbursement Regulations (2026-09-22 edition), Section 13: Dermatological "
        "preparations. https://www.nhi.gov.tw/",
}


def zh_source(en_path: Path) -> Path:
    return ROOT / en_path.relative_to(ROOT / "en")


def citation_map(zh_src: str) -> dict[str, str]:
    """zh citation name -> English citation name, from the zh reference list itself."""
    out: dict[str, str] = {}
    for ol in OL_RE.finditer(zh_src):
        for li in LI_RE.finditer(ol.group(1)):
            if "list-style:none" in (li.group("attrs") or ""):
                continue
            zh = parse_citation(li.group("body"))
            # render the whole <li>: the data-en may sit on the <li> itself
            rendered = apply_data_en(li.group(0))
            inner = re.sub(r"^<li\b(?:[^>\"]|\"[^\"]*\")*>|</li>$", "", rendered.strip())
            en = parse_citation(inner)
            if zh and en and zh.get("name") and en.get("name"):
                out[zh["name"]] = english_reference_tail(en["name"])
    return out


MONTHS = ("January February March April May June July August September October November December").split()


def english_reference_tail(name: str) -> str:
    """Bibliographic bits the zh page writes in Chinese around an English title."""
    name = re.sub(r"(\d{4})\s*年\s*(\d{1,2})\s*月", lambda m: f"{MONTHS[int(m.group(2)) - 1]} {m.group(1)}", name)
    name = name.replace("「來源」", "[Source]").replace("。", ".").replace("．", ". ")
    return re.sub(r"(?<!\.)\.\.(?!\.)", ".", name).strip()


def translate_citation_name(name: str, cmap: dict[str, str]) -> str:
    if not CJK.search(name):
        return name
    for table in (cmap, CITATION_EN):
        if name in table and not CJK.search(table[name]):
            return table[name]
        # isBasedOn truncates names to 300 characters
        for zh, en in table.items():
            if len(name) == 300 and zh.startswith(name) and not CJK.search(en):
                return en[:300]
    return name


def localize(obj, cmap: dict[str, str], titles: dict[str, str], key: str | None = None):
    if isinstance(obj, list):
        return [localize(v, cmap, titles, key) for v in obj]
    if isinstance(obj, str):
        if key in URL_KEYS:
            return obj  # identifiers must stay byte-identical to the zh pages' IRIs
        if key == "keywords" and CJK.search(obj):
            words = []
            for w in (x.strip() for x in obj.split(",")):
                w = KEYWORD_EN.get(w, w)
                if w and not CJK.search(w) and w not in words:
                    words.append(w)
            return ", ".join(words)
        return TEXT_EN.get(obj, obj)
    if not isinstance(obj, dict):
        return obj
    typ = obj.get("@type")
    out = {}
    keep_zh_name = None
    physician = obj.get("@id") == PHYSICIAN_ID
    for k, v in obj.items():
        if k == "alternateName" or (physician and k in PHYSICIAN_IDENTITY_KEYS):
            out[k] = v
        elif k == "name" and isinstance(v, str) and typ in CITATION_TYPES:
            out[k] = translate_citation_name(v, cmap)
        elif k == "name" and isinstance(v, str) and typ == "ListItem" and isinstance(obj.get("url"), str):
            slug = obj["url"].rstrip("/").rsplit("/", 1)[-1]
            out[k] = titles.get(slug) or TEXT_EN.get(v, v)
        elif k == "name" and isinstance(v, str) and v in TEXT_EN and typ in {"Person", "Physician", "Organization"}:
            out[k] = TEXT_EN[v]
            keep_zh_name = v
        else:
            out[k] = localize(v, cmap, titles, k)
    if keep_zh_name:
        # keep the Chinese name on the entity, in the slot meant for it
        alt = obj.get("alternateName")
        alts = alt if isinstance(alt, list) else ([alt] if alt else [])
        if keep_zh_name not in alts:
            out["alternateName"] = alts + [keep_zh_name] if alts else keep_zh_name
    return out


def process(en_path: Path, titles: dict[str, str]) -> bool:
    src = en_path.read_text(encoding="utf-8")
    zh_path = zh_source(en_path)
    zh_src = zh_path.read_text(encoding="utf-8") if zh_path.exists() else ""
    cmap = citation_map(zh_src) if zh_src else {}
    own_citations = bool(load_citations(src))
    zh_graph = load_citations(zh_src) if zh_src else []

    def patch(m: re.Match) -> str:
        try:
            obj = json.loads(m.group(2))
        except json.JSONDecodeError:
            return m.group(0)
        if isinstance(obj, dict) and obj.get("@type") in PAGE_TYPES and not own_citations and zh_graph:
            based_on = build_is_based_on(zh_graph)
            if based_on:
                obj["isBasedOn"] = based_on
            else:
                obj.pop("isBasedOn", None)
        new = localize(obj, cmap, titles)
        return m.group(1) + script_json(new) + "</script>"

    new_src = LD_RE.sub(patch, src)
    if new_src != src:
        en_path.write_text(new_src, encoding="utf-8")
        return True
    return False


def main() -> int:
    titles = {a["slug"]: a.get("title_en") or "" for a in load_catalog(ROOT) if a.get("title_en")}
    pages = sorted((ROOT / "en").rglob("*.html"))
    changed = sum(process(p, titles) for p in pages)
    print(f"[en-jsonld] localized JSON-LD on {len(pages)} /en pages (modified {changed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
