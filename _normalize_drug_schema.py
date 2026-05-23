#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inject `Drug` schema.org JSON-LD blocks for drug-focused articles.

Why: For articles that primarily describe a medication (isotretinoin,
dupilumab, biologics, topical retinoids/steroids/acids), Google rewards
explicit `Drug` schema with:
  • Eligibility for the "About this medication" rich-card on SERPs
  • Knowledge Graph linkage via `sameAs` Wikidata + DrugBank IDs
  • Bing / Apple intelligence drug-info card surfacing
  • LLM crawler (Perplexity, ChatGPT, Claude) entity disambiguation

The `Drug` block is a SEPARATE top-level JSON-LD block (not nested in
MedicalWebPage's `about`) — schema.org permits multiple top-level
@types per page, and Google's parser prefers this for drug rich-cards.

ATC codes verified against WHOCC (WHO Collaborating Centre for Drug
Statistics, 2025). Wikidata QIDs hand-verified.

Idempotent: replaces existing #dn-drug-schema block on every run.
Wired into REGEN_STEPS after _normalize_medical_codes.py.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent


def drug(name: str, name_zh: str,
         active_ingredient: str,
         atc: str | None = None,
         wikidata: str | None = None,
         drugbank: str | None = None,
         drug_class: str | None = None,
         mechanism: str | None = None,
         warning: str | None = None,
         prescribing: str | None = None) -> dict:
    """Build a schema.org Drug object."""
    d: dict = {
        "@context": "https://schema.org",
        "@type": "Drug",
        "name": name,
        "alternateName": [name_zh],
        "nonProprietaryName": name,
        "activeIngredient": active_ingredient,
    }
    codes = []
    if atc:
        codes.append({
            "@type": "MedicalCode",
            "code": atc,
            "codingSystem": "ATC",
        })
    if codes:
        d["code"] = codes if len(codes) > 1 else codes[0]
    same_as: list[str] = []
    if wikidata:
        same_as.append(f"https://www.wikidata.org/wiki/{wikidata}")
    if drugbank:
        same_as.append(f"https://go.drugbank.com/drugs/{drugbank}")
    if same_as:
        d["sameAs"] = same_as
    if drug_class:
        d["drugClass"] = {"@type": "DrugClass", "name": drug_class}
    if mechanism:
        d["mechanismOfAction"] = mechanism
    if warning:
        d["warning"] = warning
    if prescribing:
        d["prescribingInfo"] = prescribing
    return d


# slug -> list of Drug schema objects (multiple drugs per article OK)
SLUG_DRUGS: dict[str, list[dict]] = {
    "isotretinoin-patient": [
        drug(
            name="Isotretinoin",
            name_zh="口服 A 酸 (異維甲酸)",
            active_ingredient="Isotretinoin (13-cis-retinoic acid)",
            atc="D10BA01",
            wikidata="Q422587",
            drugbank="DB00982",
            drug_class="Systemic retinoid",
            mechanism="Vitamin A derivative; reduces sebaceous gland size and activity, normalizes follicular keratinization, and modulates immune-mediated inflammation.",
            warning="Highly teratogenic. Pregnancy must be excluded before treatment, monthly during therapy, and for one month after. Two reliable contraceptive methods are required.",
        ),
    ],
    "isotretinoin-clinical": [
        drug(
            name="Isotretinoin",
            name_zh="口服 A 酸 (異維甲酸)",
            active_ingredient="Isotretinoin (13-cis-retinoic acid)",
            atc="D10BA01",
            wikidata="Q422587",
            drugbank="DB00982",
            drug_class="Systemic retinoid",
            mechanism="Vitamin A derivative; reduces sebaceous gland size and activity, normalizes follicular keratinization, and modulates immune-mediated inflammation.",
            warning="Highly teratogenic. Pregnancy must be excluded before treatment, monthly during therapy, and for one month after. Two reliable contraceptive methods are required.",
        ),
    ],
    "dupilumab-long-term-maintenance": [
        drug(
            name="Dupilumab",
            name_zh="杜避炎 (Dupilumab)",
            active_ingredient="Dupilumab",
            atc="D11AH05",
            wikidata="Q21111977",
            drugbank="DB12159",
            drug_class="Interleukin-4 receptor alpha antagonist (monoclonal antibody)",
            mechanism="Fully human monoclonal antibody that binds the alpha subunit of the IL-4 receptor, blocking IL-4 and IL-13 signaling driving type-2 inflammation in atopic dermatitis.",
            warning="Conjunctivitis is the most common adverse event. Patients receiving live vaccines during therapy should consult their dermatologist.",
        ),
    ],
    "biologics-overview": [
        drug(
            name="Adalimumab",
            name_zh="復邁 (Adalimumab)",
            active_ingredient="Adalimumab",
            atc="L04AB04",
            wikidata="Q412806",
            drugbank="DB00051",
            drug_class="Tumor necrosis factor alpha (TNF-α) inhibitor",
            mechanism="Fully human monoclonal antibody binding soluble and membrane TNF-α, blocking its interaction with TNF receptors.",
        ),
        drug(
            name="Secukinumab",
            name_zh="可善挺 (Secukinumab)",
            active_ingredient="Secukinumab",
            atc="L04AC10",
            wikidata="Q7444008",
            drugbank="DB09302",
            drug_class="Interleukin-17A inhibitor",
            mechanism="Fully human monoclonal antibody selectively binding IL-17A, blocking its interaction with the IL-17 receptor.",
        ),
        drug(
            name="Ixekizumab",
            name_zh="達癬治 (Ixekizumab)",
            active_ingredient="Ixekizumab",
            atc="L04AC13",
            wikidata="Q16923585",
            drugbank="DB11569",
            drug_class="Interleukin-17A inhibitor",
            mechanism="Humanized monoclonal antibody binding IL-17A with high affinity, neutralizing its biological activity.",
        ),
        drug(
            name="Guselkumab",
            name_zh="特諾雅 (Guselkumab)",
            active_ingredient="Guselkumab",
            atc="L04AC16",
            wikidata="Q17126011",
            drugbank="DB11834",
            drug_class="Interleukin-23 (p19 subunit) inhibitor",
            mechanism="Human monoclonal antibody selectively binding the p19 subunit of IL-23, blocking IL-23 driven Th17 axis activation.",
        ),
        drug(
            name="Risankizumab",
            name_zh="喜開亞 (Risankizumab)",
            active_ingredient="Risankizumab",
            atc="L04AC18",
            wikidata="Q56308611",
            drugbank="DB14761",
            drug_class="Interleukin-23 (p19 subunit) inhibitor",
            mechanism="Humanized monoclonal antibody selectively binding the p19 subunit of IL-23, blocking the Th17-mediated inflammatory cascade in psoriasis.",
        ),
    ],
    "topical-acids-patient": [
        drug(
            name="Tretinoin",
            name_zh="外用 A 酸 (Tretinoin)",
            active_ingredient="Tretinoin (all-trans retinoic acid)",
            atc="D10AD01",
            wikidata="Q422087",
            drugbank="DB00755",
            drug_class="Topical retinoid",
            mechanism="Binds nuclear retinoic acid receptors; normalizes follicular keratinization, reduces comedone formation, and stimulates dermal collagen synthesis.",
        ),
        drug(
            name="Adapalene",
            name_zh="第三代外用 A 酸 (Adapalene)",
            active_ingredient="Adapalene",
            atc="D10AD03",
            wikidata="Q415411",
            drugbank="DB00210",
            drug_class="Topical retinoid (third-generation)",
            mechanism="Selective retinoic acid receptor agonist (RAR-β/γ); anti-inflammatory and comedolytic activity with better photostability than tretinoin.",
        ),
        drug(
            name="Salicylic acid",
            name_zh="水楊酸 (Salicylic acid)",
            active_ingredient="Salicylic acid",
            atc="D11AF",
            wikidata="Q161634",
            drugbank="DB00936",
            drug_class="Beta-hydroxy acid (BHA), keratolytic",
            mechanism="Lipophilic keratolytic; dissolves intercellular cement of the stratum corneum and penetrates sebum-filled follicles.",
        ),
    ],
    "topical-acids-clinical": [
        drug(
            name="Tretinoin",
            name_zh="外用 A 酸 (Tretinoin)",
            active_ingredient="Tretinoin (all-trans retinoic acid)",
            atc="D10AD01",
            wikidata="Q422087",
            drugbank="DB00755",
            drug_class="Topical retinoid",
            mechanism="Binds nuclear retinoic acid receptors; normalizes follicular keratinization, reduces comedone formation, and stimulates dermal collagen synthesis.",
        ),
        drug(
            name="Adapalene",
            name_zh="第三代外用 A 酸 (Adapalene)",
            active_ingredient="Adapalene",
            atc="D10AD03",
            wikidata="Q415411",
            drugbank="DB00210",
            drug_class="Topical retinoid (third-generation)",
            mechanism="Selective retinoic acid receptor agonist (RAR-β/γ); anti-inflammatory and comedolytic activity with better photostability than tretinoin.",
        ),
    ],
    "topical-steroids-guide": [
        drug(
            name="Hydrocortisone",
            name_zh="氫化可體松 (Hydrocortisone)",
            active_ingredient="Hydrocortisone",
            atc="D07AA02",
            wikidata="Q207610",
            drugbank="DB00741",
            drug_class="Topical corticosteroid (Class VII, lowest potency)",
            mechanism="Binds the cytosolic glucocorticoid receptor; suppresses pro-inflammatory cytokine transcription, vasoconstricts dermal vessels, and reduces immune cell infiltration.",
        ),
        drug(
            name="Triamcinolone acetonide",
            name_zh="三安西龍 (Triamcinolone acetonide)",
            active_ingredient="Triamcinolone acetonide",
            atc="D07AB09",
            wikidata="Q420840",
            drugbank="DB00620",
            drug_class="Topical corticosteroid (Class IV-V, mid potency)",
            mechanism="Synthetic glucocorticoid; binds glucocorticoid receptor with higher affinity than hydrocortisone for sustained anti-inflammatory effect.",
        ),
        drug(
            name="Clobetasol propionate",
            name_zh="氯倍他索 (Clobetasol propionate)",
            active_ingredient="Clobetasol propionate",
            atc="D07AD01",
            wikidata="Q412286",
            drugbank="DB01013",
            drug_class="Topical corticosteroid (Class I, super-high potency)",
            mechanism="Highest-potency topical glucocorticoid; binds glucocorticoid receptor at femtomolar affinity, producing maximal anti-inflammatory effect.",
            warning="Super-potent class. Limit continuous use to ≤2 weeks; avoid on face, intertriginous areas, and in children.",
        ),
    ],
}


MARKER_OPEN = '<script type="application/ld+json" id="dn-drug-schema">'
MARKER_CLOSE = '</script>'
EXISTING_RE = re.compile(
    r'<script type="application/ld\+json" id="dn-drug-schema">.*?</script>\s*',
    re.DOTALL,
)


def serialize_drugs(drugs: list[dict]) -> str:
    if len(drugs) == 1:
        body = json.dumps(drugs[0], ensure_ascii=False, separators=(",", ":"))
    else:
        # Schema.org permits multiple top-level @types via @graph
        graph = {
            "@context": "https://schema.org",
            "@graph": [{k: v for k, v in d.items() if k != "@context"} for d in drugs],
        }
        body = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
    return f"{MARKER_OPEN}{body}{MARKER_CLOSE}"


def inject(html: str, drugs: list[dict]) -> tuple[str, bool]:
    new_block = serialize_drugs(drugs) + "\n"
    if EXISTING_RE.search(html):
        new_html = EXISTING_RE.sub(new_block, html, count=1)
        return new_html, new_html != html
    # Insert right before </head>
    head_close = html.find("</head>")
    if head_close == -1:
        return html, False
    new_html = html[:head_close] + new_block + html[head_close:]
    return new_html, True


def main() -> int:
    """RETRACTED 2026-05-23: Drug schema injection disabled.

    Google Search Console started flagging our Drug @type blocks as
    "Product snippets" requiring offers / review / aggregateRating
    (WNC-10030322, affecting 11 items across biologics-overview /
    topical-steroids-guide / topical-acids-patient). Drug is technically
    a MedicalEntity not a Product, but Google's parser treats
    `nonProprietaryName` + `activeIngredient` as product-like markers.

    Adding fake offers / reviews would be misleading; Google has no
    Drug rich-card to lose either. Net better to strip the schema
    entirely and let MedicalCondition + Wikidata sameAs + the article
    body carry the entity disambiguation.

    This function now only REMOVES existing dn-drug-schema blocks
    (cleanup mode) — no re-injection. Kept in REGEN_STEPS so any
    drift gets cleaned on every build.
    """
    blog = ROOT / "blog"
    en_blog = ROOT / "en" / "blog"
    total_removed = 0
    for base in (blog, en_blog):
        if not base.exists():
            continue
        for fp in sorted(base.glob("*.html")):
            src = fp.read_text(encoding="utf-8")
            if EXISTING_RE.search(src):
                new_src = EXISTING_RE.sub("", src)
                if new_src != src:
                    fp.write_text(new_src, encoding="utf-8")
                    total_removed += 1

    print(f"[drug-schema] RETRACTED — stripped Drug JSON-LD from "
          f"{total_removed} article files (GSC WNC-10030322 fix)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
