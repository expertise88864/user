#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inject ICD-10 + SNOMED-CT codes into each article's MedicalCondition
schema `about` field.

Why: Google's Medical Q&A rich-result eligibility requires structured
medical entity codes (ICD-10 / SNOMED) on YMYL content. Currently our
`about` field carries only `name` + `alternateName`. Adding `code:`
with `codingSystem` lets:
  • Google's MedLM classifier recognize entities for Q&A snippets
  • Medical professionals find articles via diagnosis-code search
  • Knowledge Graph link the article to the disease entity

Each article's slug maps to one or more conditions. We use ICD-10-CM
(WHO 2024) as primary; SNOMED-CT as secondary where ICD-10 is too
coarse. Mappings are hand-curated against WHO ICD-10 browser +
NHS UK Read codes for dermatology.

Idempotent: replaces existing about field with the enriched version
on every run. Wired into REGEN_STEPS after schema normalization.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent


def medical_condition(name_en: str, name_zh: str,
                      icd10: str | None = None,
                      snomed: str | None = None,
                      mesh: str | None = None,
                      wikidata: str | None = None) -> dict:
    """Build a fully-coded MedicalCondition schema object.

    `wikidata`: a Q-identifier (e.g. "Q83320" for psoriasis). Emitted as
    `sameAs: ["https://www.wikidata.org/wiki/Q..."]` which Google uses to
    link the article to its Knowledge Graph entity. Critical for AI-snippet
    eligibility — Google's MedLM + Bing's BioBERT match on Wikidata QIDs
    when no schema.org @id exists. Verified against Wikidata 2025-05.
    """
    cond: dict = {
        "@type": "MedicalCondition",
        "name": name_en,
        "alternateName": [name_zh],
    }
    codes = []
    if icd10:
        codes.append({
            "@type": "MedicalCode",
            "code": icd10,
            "codingSystem": "ICD-10-CM",
        })
    if snomed:
        codes.append({
            "@type": "MedicalCode",
            "code": snomed,
            "codingSystem": "SNOMED-CT",
        })
    if mesh:
        codes.append({
            "@type": "MedicalCode",
            "code": mesh,
            "codingSystem": "MeSH",
        })
    if codes:
        cond["code"] = codes if len(codes) > 1 else codes[0]
    if wikidata:
        cond["sameAs"] = [f"https://www.wikidata.org/wiki/{wikidata}"]
    return cond


# Hand-curated slug → condition mapping. ICD-10-CM 2024 codes.
SLUG_CONDITIONS: dict[str, list[dict]] = {
    # ─── Atopic dermatitis cluster ───
    "atopic-dermatitis-overview": [
        medical_condition("Atopic dermatitis", "異位性皮膚炎",
                          icd10="L20.9", snomed="24079001",
                          mesh="D003876", wikidata="Q864350"),
    ],
    "atopic-dermatitis-topical": [
        medical_condition("Atopic dermatitis", "異位性皮膚炎",
                          icd10="L20.9", snomed="24079001",
                          wikidata="Q864350"),
    ],
    "atopic-dermatitis-systemic": [
        medical_condition("Atopic dermatitis", "異位性皮膚炎",
                          icd10="L20.9", snomed="24079001",
                          wikidata="Q864350"),
    ],
    "atopic-dermatitis-special-populations": [
        medical_condition("Atopic dermatitis", "異位性皮膚炎",
                          icd10="L20.9", snomed="24079001",
                          wikidata="Q864350"),
    ],
    "pediatric-eczema": [
        medical_condition("Pediatric atopic dermatitis", "兒童異位性皮膚炎",
                          icd10="L20.83", snomed="24079001",
                          wikidata="Q864350"),
    ],

    # ─── Psoriasis cluster ───
    "psoriasis-overview": [
        medical_condition("Psoriasis vulgaris", "乾癬",
                          icd10="L40.0", snomed="9014002",
                          mesh="D011565", wikidata="Q83320"),
    ],
    "psoriasis-topical": [
        medical_condition("Psoriasis vulgaris", "乾癬",
                          icd10="L40.0", snomed="9014002",
                          wikidata="Q83320"),
    ],
    "psoriasis-systemic": [
        medical_condition("Psoriasis vulgaris", "乾癬",
                          icd10="L40.0", snomed="9014002",
                          wikidata="Q83320"),
    ],
    "psoriasis-special-populations": [
        medical_condition("Psoriatic arthritis", "乾癬性關節炎",
                          icd10="L40.5", snomed="33339001",
                          wikidata="Q1138898"),
    ],
    "psoriasis-myths": [
        medical_condition("Psoriasis", "乾癬", icd10="L40",
                          snomed="9014002", wikidata="Q83320"),
    ],
    "psoriasis-biologic-monitoring": [
        medical_condition("Psoriasis", "乾癬", icd10="L40",
                          snomed="9014002", wikidata="Q83320"),
    ],

    # ─── Acne + isotretinoin ───
    "acne-myths": [
        medical_condition("Acne vulgaris", "尋常性痤瘡",
                          icd10="L70.0", snomed="11381005",
                          mesh="D000152", wikidata="Q188601"),
    ],
    "acne-scar-treatment": [
        medical_condition("Acne scarring", "痘疤",
                          icd10="L90.5", snomed="402411006"),
    ],
    "isotretinoin-patient": [
        medical_condition("Severe acne vulgaris", "嚴重尋常性痤瘡",
                          icd10="L70.0", snomed="11381005",
                          wikidata="Q188601"),
    ],
    "isotretinoin-clinical": [
        medical_condition("Severe acne vulgaris", "嚴重尋常性痤瘡",
                          icd10="L70.0", snomed="11381005",
                          wikidata="Q188601"),
    ],

    # ─── Topical acids + steroids ───
    "topical-acids-patient": [
        medical_condition("Acne vulgaris", "痤瘡", icd10="L70.0",
                          wikidata="Q188601"),
        medical_condition("Photoaging", "光老化", icd10="L57.9"),
    ],
    "topical-steroids-guide": [
        medical_condition("Eczema and dermatitis", "濕疹與皮膚炎",
                          icd10="L30.9", snomed="43116000",
                          wikidata="Q188661"),
    ],

    # ─── Hair / scalp ───
    "hairloss-myths": [
        medical_condition("Androgenetic alopecia", "雄性禿",
                          icd10="L64.9", snomed="87224000",
                          mesh="D000505", wikidata="Q1378019"),
    ],
    "alopecia-areata": [
        medical_condition("Alopecia areata", "圓禿",
                          icd10="L63.9", snomed="278951000",
                          mesh="D000506", wikidata="Q717619"),
    ],

    # ─── Vitiligo / pigmentation ───
    "vitiligo": [
        medical_condition("Vitiligo", "白斑",
                          icd10="L80", snomed="56727007",
                          mesh="D014820", wikidata="Q170082"),
    ],
    "vitiligo-maintenance-clinical": [
        medical_condition("Non-segmental vitiligo", "非分節型白斑",
                          icd10="L80", snomed="56727007",
                          mesh="D014820", wikidata="Q170082"),
    ],
    "melasma-myths": [
        medical_condition("Melasma", "肝斑",
                          icd10="L81.1", snomed="2884008",
                          mesh="D008548", wikidata="Q1922336"),
    ],
    "skin-whitening-agents": [
        medical_condition("Post-inflammatory hyperpigmentation",
                          "炎症後色素沉澱",
                          icd10="L81.0", snomed="402710002"),
    ],

    # ─── Rosacea / perioral ───
    "rosacea-myths": [
        medical_condition("Rosacea", "玫瑰斑",
                          icd10="L71.9", snomed="33438005",
                          mesh="D012393", wikidata="Q333418"),
    ],
    "perioral-dermatitis-guide": [
        medical_condition("Perioral dermatitis", "口周皮膚炎",
                          icd10="L71.0", snomed="403163004",
                          wikidata="Q1062618"),
    ],

    # ─── Tinea / fungal ───
    "tinea-myths": [
        medical_condition("Tinea pedis", "足癬 (香港腳)",
                          icd10="B35.3", snomed="6531000146109",
                          wikidata="Q186979"),
        medical_condition("Onychomycosis", "甲癬 (灰指甲)",
                          icd10="B35.1", snomed="414941008",
                          wikidata="Q2271826"),
    ],
    "toenail-mechanical-disorders": [
        medical_condition("Nail disorder", "趾甲疾患",
                          icd10="L60.9", snomed="56961003"),
    ],

    # ─── Urticaria / inflammatory ───
    "urticaria-myths": [
        medical_condition("Chronic spontaneous urticaria", "慢性自發性蕁麻疹",
                          icd10="L50.1", snomed="48740009",
                          mesh="D014581", wikidata="Q207314"),
    ],
    "prurigo-nodularis": [
        medical_condition("Prurigo nodularis", "結節性癢疹",
                          icd10="L28.1", snomed="36821000119103",
                          wikidata="Q1463059"),
    ],
    "contact-dermatitis": [
        medical_condition("Allergic contact dermatitis", "過敏性接觸性皮膚炎",
                          icd10="L23.9", snomed="40275004",
                          wikidata="Q380933"),
        medical_condition("Irritant contact dermatitis", "刺激性接觸性皮膚炎",
                          icd10="L24.9", snomed="238575004"),
    ],
    "hidradenitis-suppurativa": [
        medical_condition("Hidradenitis suppurativa", "化膿性汗腺炎",
                          icd10="L73.2", snomed="59393003",
                          mesh="D017497", wikidata="Q581149"),
    ],

    # ─── Viral skin ───
    "warts-myths": [
        medical_condition("Viral wart", "病毒疣",
                          icd10="B07.9", snomed="240542004",
                          wikidata="Q201405"),
    ],
    "shingles-myths": [
        medical_condition("Herpes zoster", "帶狀皰疹",
                          icd10="B02.9", snomed="4740000",
                          mesh="D006562", wikidata="Q132621"),
    ],
    "mpox-care": [
        medical_condition("Mpox", "猴痘",
                          icd10="B04", snomed="414015000",
                          mesh="D008844", wikidata="Q839582"),
    ],

    # ─── Skin cancer ───
    "actinic-keratosis-scc": [
        medical_condition("Actinic keratosis", "光化性角化症",
                          icd10="L57.0", snomed="201101007",
                          wikidata="Q576550"),
        medical_condition("Cutaneous squamous cell carcinoma",
                          "皮膚鱗狀細胞癌",
                          icd10="C44.92", snomed="402815007"),
    ],
    "cutaneous-t-cell-lymphoma": [
        medical_condition("Cutaneous T-cell lymphoma", "皮膚 T 細胞淋巴瘤",
                          icd10="C84.A0", snomed="404138006",
                          mesh="D016410"),
    ],
    "targeted-therapy-skin": [
        medical_condition("Cutaneous adverse effect of antineoplastic agents",
                          "標靶藥物皮膚副作用",
                          icd10="L27.0"),
    ],

    # ─── Procedures + general ───
    "epidermoid-cyst": [
        medical_condition("Epidermoid cyst", "表皮囊腫 (粉瘤)",
                          icd10="L72.0", snomed="35147009",
                          wikidata="Q1342300"),
    ],
    "skin-biopsy-excision": [
        # No condition — procedure article; about a procedure, not a disease.
        # Will be supplemented by MedicalProcedure schema below.
    ],
    "laser-dermatology": [
        # Procedure article; supplemented by MedicalProcedure schema.
    ],
    "dermatologic-oral-examination": [
        medical_condition("Oral lichen planus", "口腔扁平苔癬",
                          icd10="L43.9", snomed="78028004"),
    ],

    # ─── Drug / therapy specific ───
    "biologics-overview": [
        # Drug class overview — no single condition mapping
    ],
    "dupilumab-long-term-maintenance": [
        medical_condition("Atopic dermatitis", "異位性皮膚炎",
                          icd10="L20.9", snomed="24079001"),
    ],
    "ai-dermatology-roles": [
        # Research review on AI in dermatology — point to Wikidata
        # entity "Dermatology" (Q3893099) as the most appropriate broad
        # entity tag. Schema.org MedicalCondition is a structural
        # mismatch for an AI / specialty review, so we use a minimal
        # condition stub solely as a Knowledge Graph anchor.
        {
            "@type": "MedicalCondition",
            "name": "Dermatology (general)",
            "alternateName": ["皮膚科 (一般)"],
            "sameAs": ["https://www.wikidata.org/wiki/Q3893099"],
        },
    ],

    # ─── NHI / FAQ ───
    "nhi-derm-drugs": [],  # policy article, no condition
    "dermatology-faq": [],  # general FAQ
}

# Procedure schemas for articles that describe interventions
SLUG_PROCEDURES: dict[str, list[dict]] = {
    "skin-biopsy-excision": [
        {
            "@type": "MedicalProcedure",
            "name": "Skin biopsy",
            "alternateName": ["皮膚切片", "punch biopsy", "shave biopsy"],
            "procedureType": {
                "@type": "MedicalProcedureType",
                "name": "DiagnosticProcedure",
            },
            "bodyLocation": "Skin",
            "code": {
                "@type": "MedicalCode",
                "code": "86.11",
                "codingSystem": "ICD-9-PCS",
            },
        },
        {
            "@type": "MedicalProcedure",
            "name": "Surgical excision",
            "alternateName": ["切除手術"],
            "procedureType": {
                "@type": "MedicalProcedureType",
                "name": "TherapeuticProcedure",
            },
        },
    ],
    "laser-dermatology": [
        {
            "@type": "MedicalProcedure",
            "name": "Laser dermatology",
            "alternateName": ["雷射皮膚治療"],
            "procedureType": {
                "@type": "MedicalProcedureType",
                "name": "TherapeuticProcedure",
            },
        },
    ],
}


def update_article_about(html: str, conditions: list[dict],
                         procedures: list[dict]) -> tuple[str, bool]:
    """Replace MedicalWebPage.about with conditions (+procedures).
    Returns (new_html, changed)."""
    if not conditions and not procedures:
        return html, False

    # Combine conditions + procedures into one `about` array
    about_value = conditions + procedures
    new_about = json.dumps(about_value, ensure_ascii=False, separators=(",", ":"))
    # Strip surrounding [ ] if single item — schema.org accepts both
    if len(about_value) == 1:
        new_about_str = json.dumps(about_value[0], ensure_ascii=False, separators=(",", ":"))
    else:
        new_about_str = new_about

    # Match `"about":` followed by either an object or array, then update
    # Use balanced-brace/bracket scanning to find the end.
    pattern = re.compile(r'"about":(\[|\{)', re.DOTALL)
    changed = False

    def replace_about(m: re.Match) -> str:
        nonlocal changed
        start = m.end() - 1  # position of opening bracket/brace
        open_ch = m.group(1)
        close_ch = ']' if open_ch == '[' else '}'
        depth = 1
        pos = start + 1
        while depth > 0 and pos < len(html):
            ch = html[pos]
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    break
            pos += 1
        if depth != 0:
            return m.group(0)  # unbalanced, leave alone
        # Replace from m.start() through pos (inclusive)
        full_old = html[m.start():pos + 1]
        full_new = f'"about":{new_about_str}'
        if full_old != full_new:
            changed = True
        # Return marker — actual splice happens manually
        return f'\x00ABOUT_REPLACE\x00{full_new}\x00END\x00'

    # Find ALL `"about":` and replace each one (typically 1-3 per article
    # for MedicalWebPage + MedicalScholarlyArticle blocks)
    matches = []
    for m in pattern.finditer(html):
        start = m.end() - 1
        open_ch = m.group(1)
        close_ch = ']' if open_ch == '[' else '}'
        depth = 1
        pos = start + 1
        while depth > 0 and pos < len(html):
            ch = html[pos]
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    break
            pos += 1
        if depth == 0:
            matches.append((m.start(), pos + 1))

    if not matches:
        return html, False

    # Splice from end to start so positions stay valid
    new_html = html
    for start, end in reversed(matches):
        old = new_html[start:end]
        full_new = f'"about":{new_about_str}'
        if old != full_new:
            new_html = new_html[:start] + full_new + new_html[end:]
            changed = True

    return new_html, changed


def main() -> int:
    blog = ROOT / "blog"
    en_blog = ROOT / "en" / "blog"
    total_changed = 0

    for slug, conditions in SLUG_CONDITIONS.items():
        procedures = SLUG_PROCEDURES.get(slug, [])
        if not conditions and not procedures:
            continue
        # ZH
        zh_fp = blog / f"{slug}.html"
        if zh_fp.exists():
            src = zh_fp.read_text(encoding="utf-8")
            new_src, changed = update_article_about(src, conditions, procedures)
            if changed:
                zh_fp.write_text(new_src, encoding="utf-8")
                total_changed += 1
        # EN
        en_fp = en_blog / f"{slug}.html"
        if en_fp.exists():
            src = en_fp.read_text(encoding="utf-8")
            new_src, changed = update_article_about(src, conditions, procedures)
            if changed:
                en_fp.write_text(new_src, encoding="utf-8")
                total_changed += 1

    print(f"[medical-codes] enriched `about` with ICD-10/SNOMED/MeSH "
          f"codes in {total_changed} article files "
          f"({len(SLUG_CONDITIONS)} slug mappings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
