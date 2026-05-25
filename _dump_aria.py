#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dump aria-label strings from a source file as a Python dict initializer
suitable for pasting into _gen_en_pages.py ARIA_LABEL_TRANSLATIONS.
Provide EN translations manually in this script.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def extract_zh_arias(rel: str) -> list[str]:
    """Extract CJK aria-labels from FIGURE / SVG elements only.

    Earlier versions returned ALL CJK aria-labels in document order, which
    erroneously included nav-button labels ("主導覽", "搜尋", "贊助本站",
    "切換暗色模式", "開啟選單") at the front of the list. Mapping per-page
    figure translations onto those keys silently overrode the same labels
    site-wide via the shared ARIA_LABEL_TRANSLATIONS dict.

    Now we only pick aria-labels on <svg> tags.
    """
    text = (ROOT / rel).read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r'<svg\b[^>]*aria-label="([^"]+)"', text):
        if re.search(r"[一-鿿]", m.group(1)):
            out.append(m.group(1))
    return out


def dump(rel: str, en_translations: list[str], out_lines: list[str]) -> None:
    zhs = extract_zh_arias(rel)
    out_lines.append(f"# from {rel}")
    for zh, en in zip(zhs, en_translations):
        bs = chr(92)
        zh_esc = zh.replace(bs, bs + bs).replace('"', bs + '"')
        en_esc = en.replace(bs, bs + bs).replace('"', bs + '"')
        out_lines.append(f'    "{zh_esc}":')
        out_lines.append(f'        "{en_esc}",')


if __name__ == "__main__":
    out_lines: list[str] = []
    dump("blog/photodynamic-therapy-overview.html", [
        "PDT three essential elements and molecular mechanism: photosensitizer + light + oxygen → ROS → apoptosis / vascular damage / immune activation",
        "Schematic: ALA and MAL metabolism via the heme biosynthesis pathway to PpIX",
        "Comparison of penetration depth in skin: blue light, green light, red light, and near-infrared",
        "PDT 12 indications ranked by evidence level on a tiered ladder",
        "PDT pain-management strategy ladder",
    ], out_lines)
    dump("blog/severe-scabies-treatment.html", [
        "Scabies mite life cycle and burrow diagram: female mite tunnels in stratum corneum and lays eggs; eggs hatch in 3-4 days; adult in 2-3 weeks; full cycle 2-3 weeks",
        "Comparison of two severe scabies subtypes: profuse scabies (mites spread to atypical sites like head and back with erythematous scaling) versus crusted scabies (hyperkeratotic crusted plaques with thousands of mites)",
        "Severe scabies standard treatment schedule: Day 0 ivermectin 200 μg/kg + permethrin head-to-toe; Day 7 repeat; Day 14 ivermectin; daily emollient",
    ], out_lines)
    dump("blog/dupilumab-long-term-maintenance.html", [
        "Three side-by-side bar charts (EASI / SCORAD / pruritus NRS) at three time points T0 / T1 / T2: the long-term q2w arm shows the greatest decrease by week 52; the short-term arm maintains effect after stopping but does not improve further.",
        "Kaplan-Meier-style curve: cumulative relapse-free rate at 52 weeks is markedly higher in the long-term q2w arm than in the short-term or tapering arms; some long-term patients remain relapse-free beyond 300 days.",
        "Five atopic dermatitis phenotypes: classic symmetric flexural, generalized lichenified, generalized inflammatory, nummular eczema-like, and prurigo nodular-like.",
    ], out_lines)
    dump("blog/semaglutide-hair-loss.html", [
        "Herrera 2026 JAAD: forest plot of relative risks for various new-onset hair-loss types in semaglutide / tirzepatide users",
        "Hill 2026 JAAD: forest plot of treatment-utilization rates for scarring alopecia patients on GLP-1 / GIP",
        "2x2 concept matrix of the two studies: population × outcome",
        "GLP-1RA dual-pathway hypothesis on hair follicle",
        "New-onset hair-loss RR accumulating over time after GLP-1RA initiation",
    ], out_lines)
    dump("blog/dermatologic-oral-examination.html", [
        "Oral mucosa zones (3 types): keratinized masticatory mucosa over hard palate and gingiva (pink); non-keratinized lining mucosa over buccal, ventral tongue, floor of mouth, and soft palate (cream); specialized mucosa over dorsal tongue and lip vermilion (orange-red).",
        "6 oral mucosal diseases at a glance: oral lichen planus (white lacy reticulations), recurrent aphthous stomatitis (round ulcer), oral leukoplakia (uniform white patch), mucous membrane pemphigoid (desquamative gingivitis with blood blisters), actinic cheilitis (rough lower lip), and oral melanotic macule.",
        "Oral symptom triage decision flow: by symptom type, route to dentistry, dermatology, or oral & maxillofacial surgery / ENT.",
        "Oral biopsy instruments and two techniques: punch trephine (circular biopsy) and #15 blade (strip biopsy).",
    ], out_lines)
    dump("blog/psoriasis-biologic-monitoring.html", [
        "USPSTF evidence-grade summary: 13 routine pre-biologic labs across 5 biologic classes. Green B = recommended; uncolored C = case-by-case; red D = not recommended; gray I = insufficient evidence. TNF-α has the most stringent annual TB + HBV recommendations; IL-17 highlights mucocutaneous fungal infection and IBD considerations; IL-12/23 and IL-23 p19 are mostly D; HIV is I.",
        "Bar chart of biologic-associated HBV reactivation risk in psoriasis patients with chronic HBV carriage: 26% without antiviral prophylaxis; 7.7% with antiviral prophylaxis (entecavir or tenofovir); secukinumab + prophylaxis and ustekinumab + prophylaxis show no reactivation cases in current data; TNF-α inhibitors have the most reactivation events.",
        "Biologic class decision tree: required screening and mechanism-of-action questions before initiating any biologic. TNF-α → strict annual TB + HBV screening; IL-12/23 and IL-23 → individual-risk based; IL-17 → mucocutaneous fungal infection prophylaxis + IBD considerations.",
    ], out_lines)
    Path('_aria_lines.txt').write_text('\n'.join(out_lines), encoding='utf-8')
    print(f"Wrote {len(out_lines)} lines to _aria_lines.txt")
