#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Wrap dangling ZH text segments after bilingual <strong> tags inside
proseEn blocks. The DataEnRenderer in _gen_en_pages.py handles the
<strong data-en="..."> replacement, but plain text nodes between tags
remain ZH. This script finds every such span and wraps it in
<span data-en="<translation>"> so it gets translated too.

Translations are looked up by ZH text hash so we don't have to type
the exact string in the source file (which can have wrong-encoding gotchas).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


# ZH -> EN translation map. Keys are full ZH text segments that appear
# as text nodes immediately after a bilingual <strong> or anywhere else
# in proseEn that we want to translate.
TRANSLATIONS: dict[str, str] = {
    # topical-acids-patient.html — list items
    "（處方）:Differin(Adapalene)、Stieva-A(Tretinoin)、Tazarotene。":
        " (prescription): Differin (adapalene), Stieva-A (tretinoin), Tazarotene.",
    "(OTC):The Ordinary Granactive Retinoid、SkinCeuticals Retinol、L'Oreal Revitalift、Olay Pro Retinol。":
        " (OTC): The Ordinary Granactive Retinoid, SkinCeuticals Retinol, L'Oreal Revitalift, Olay Pro Retinol.",
    ":Skinoren（處方 20%）、The Ordinary Azelaic 10%。":
        ": Skinoren (prescription 20%), The Ordinary Azelaic 10%.",
    ":Neostrata Glycolic、Drunk Elephant TLC。":
        ": Neostrata Glycolic, Drunk Elephant TLC.",
    ":Paula's Choice 2% BHA、CosRX BHA。":
        ": Paula's Choice 2% BHA, CosRX BHA.",
    "是常見起效時間。前 2-4 週可能":
        " is the typical time to effect. During the first 2–4 weeks you may experience a",
    " — 加速代謝把潛伏粉刺帶出來，堅持下去就好。長期用持續改善膚質、淡化痘印、減少粉刺。":
        " — accelerated turnover brings latent comedones to the surface; persist through this phase. Long-term use continues to improve skin quality, fade post-acne marks, and reduce comedones.",
    ":A 酸 + 果酸/水楊酸、A 酸 + 維他命 C、A 酸 + 過氧化苯醯。可以隔夜輪用或":
        ": retinoid + AHA/BHA, retinoid + vitamin C, retinoid + benzoyl peroxide. Use them on alternate nights or",
    "（早上維他命 C，晚上 A 酸）。皮脂腺分泌多、油痘肌建議白天水楊酸、晚上 A 酸/A 醇 隔天輪用。":
        " (vitamin C in the morning, retinoid at night). For oily / acne-prone skin, salicylic acid in the morning and retinoid (or retinol) at night on alternate days is a common pattern.",
    "：外用 A 酸(Tretinoin、Adapalene、Tazarotene)、口服 A 酸(Isotretinoin)。":
        ": topical retinoids (tretinoin, adapalene, tazarotene), oral isotretinoin.",
    "：水楊酸(BHA)高濃度全臉、高濃度果酸。":
        ": high-concentration salicylic acid (BHA) on the full face, high-concentration AHAs.",
    "：杜鵑花酸 Azelaic acid、低濃度果酸(Lactic、Glycolic 5-8%)、PHA、菸鹼醯胺、玻尿酸。":
        ": azelaic acid, low-concentration AHAs (lactic, glycolic 5–8%), PHA, niacinamide, hyaluronic acid.",
    "(Differin, Stieva-A, Tazarotene, Acnatac, Duac) are covered by Taiwan NHI (prescription only, ICD-10 acne diagnosis required)。":
        " (Differin, Stieva-A, Tazarotene, Acnatac, Duac) are covered by Taiwan NHI (prescription only, ICD-10 acne diagnosis required).",
    " 健保也有。果酸、水楊酸、A 醇都":
        " is also covered by Taiwan NHI. AHAs, salicylic acid, and retinol are all",
    "（屬保養品/自費醫美）。":
        " (classified as cosmeceuticals / out-of-pocket aesthetic medicine).",
    "。傳統 A 酸主要研究在臉，背痘有需要時可考慮。":
        ". Traditional retinoids were studied mainly on facial acne; consider Aklief when the back/chest is involved.",
    "，2020 年 FDA 核准。直接在毛囊皮脂腺局部抑制雄激素訊號 — ":
        ", FDA-approved in 2020. Locally suppresses androgen signaling at the pilosebaceous unit — ",
    "，每天兩次，臉部全臉塗。對男性以前沒有外用抗雄選項的族群很重要。台灣目前尚未上市，可能需自費或透過代購。AAD 2024 列為 conditional recommendation（高品質證據，但成本是限制）。":
        ", applied twice daily to the full face. Important for male patients who previously had no topical anti-androgen option. Not yet available in Taiwan; may require self-pay or overseas purchase. AAD 2024 classifies as a conditional recommendation (high-quality evidence, but cost is a limitation).",
    " NICE 第一線治療一致採「retinoid+BPO」、「retinoid+topical antibiotic」固定複方，呼應 AAD 2024。":
        " NICE first-line therapy uses fixed-combination &quot;retinoid + BPO&quot; or &quot;retinoid + topical antibiotic&quot;, consistent with AAD 2024.",
    "同一晚":
        "Same evening — ",
    # Bogus data-en attribute values (ZH instead of EN)
    "data-en=\"美白成分完整解析\"":
        'data-en="Brightening ingredients — full breakdown"',
    "data-en=\"痘疤完整治療指引\"":
        'data-en="Acne scar treatment — full guide"',
    ">美白成分完整解析":
        ">Brightening ingredients — full breakdown",
    ">痘疤完整治療指引":
        ">Acne scar treatment — full guide",
}


# Per-file substitutions for articles where translations are too specific
# to share with other files (e.g., long Q&A card answers, related-article
# card titles with bogus data-en values).
PER_FILE: dict[str, dict[str, str]] = {
    "blog/isotretinoin-patient.html": {
        # Long-tail Q&A card answers (5 Q&As)
        "<strong>累積 70 年以上臨床經驗，正確使用是非常安全的</strong>。常見副作用嘴唇乾、皮膚乾、肝指數/血脂上升，可監測可逆。<strong>絕對禁忌</strong>：懷孕（致畸胎）、哺乳。爭議「自殺風險」目前研究多為觀察性 — 中重度痘痘本身就有更高憂鬱風險，藥物因果未證實。建議規律追蹤，若情緒變化告知醫師。":
            "<strong>With 70+ years of clinical experience, properly monitored use is very safe.</strong> Common side effects (dry lips, dry skin, lab elevations in LFTs/lipids) are monitorable and reversible. <strong>Absolute contraindications:</strong> pregnancy (teratogenic) and breastfeeding. The &quot;suicide risk&quot; controversy is mostly based on observational data — moderate-to-severe acne itself carries higher depression risk, and a causal link with isotretinoin is not established. Recommend regular follow-up; report any mood changes to your clinician.",
        "<strong>累積劑量(cumulative dose)= 體重(kg)× 120-150 mg/kg</strong>。例：60 kg 約需 7,200-9,000 mg 總量。每天劑量 0.5-1 mg/kg，療程 6-9 個月。劑量足才能達到痤瘡長期緩解，不夠容易復發。":
            "<strong>Cumulative dose = body weight (kg) × 120–150 mg/kg.</strong> Example: a 60 kg patient targets 7,200–9,000 mg total. Daily dose 0.5–1 mg/kg, course 6–9 months. Reaching the cumulative target is what produces long-term remission; under-dosing means easier relapse.",
        "<strong>療程開始前 1 個月 + 整個療程 + 療程結束後 1 個月</strong>都需嚴格避孕。建議使用兩種方式（口服避孕藥 + 保險套）。每月回診抽血 + 確認沒懷孕。意外懷孕需立即停藥並至產科諮詢。":
            "<strong>Strict contraception is required for 1 month before, throughout, and for 1 month after the course.</strong> Two methods are recommended (e.g., OCP + condom). Monthly visits with blood tests and pregnancy confirmation. If accidental pregnancy occurs, stop immediately and consult OB/GYN.",
        "<strong>建議停藥後 6 個月再做侵入性雷射</strong>（磨皮、飛梭 CO2、深層化學換膚）— 因傷口癒合差易留疤。<strong>非汽化雷射（如低能量皮秒 toning、PDL）、IPL 通常可進行</strong>但需個別評估。常規護膚、保濕、防曬不影響。":
            "<strong>Wait 6 months after stopping isotretinoin before invasive lasers</strong> (resurfacing, fractional CO2, deep chemical peels) — wound healing is impaired and scarring risk is higher. <strong>Non-ablative lasers (e.g., low-energy picosecond toning, PDL) and IPL are usually fine</strong>, but require individual assessment. Routine skincare, moisturizing, and sunscreen are unaffected.",
        "健保<strong>有條件給付</strong>：中重度痤瘡（中度結節型、囊腫型、嚴重粉刺、痘疤形成）、外用 + 口服抗生素治療失敗、需符合<strong>診斷碼 706.1</strong>。需事前審查通過。<strong>女性育齡需簽署「避孕同意書」+ 抽血驗孕</strong>。":
            "Taiwan NHI provides <strong>conditional coverage</strong>: moderate-to-severe acne (moderate nodulocystic, cystic, severe comedonal, scarring), failure of topical + oral antibiotic therapy, and matching <strong>ICD-10 706.1</strong>. Prior authorization required. <strong>Women of reproductive age must sign a contraception consent and have a baseline pregnancy test.</strong>",
        # Bogus data-en attribute values on related-article cards
        'data-en="外用酸類完整衛教"': 'data-en="Topical acids — complete patient guide"',
        'data-en="痘疤完整治療指引"': 'data-en="Acne scar treatment — complete guide"',
        'data-en="皮膚科常用藥物的健保規範整理"': 'data-en="Taiwan NHI rules for common dermatology drugs"',
        'data-en="皮膚科生物製劑與小分子標靶藥物常見"': 'data-en="Dermatology biologics and small-molecule targeted drugs — common questions"',
        # And the inner text of those spans
        ">外用酸類完整衛教": ">Topical acids — complete patient guide",
        ">痘疤完整治療指引": ">Acne scar treatment — complete guide",
        ">皮膚科常用藥物的健保規範整理": ">Taiwan NHI rules for common dermatology drugs",
        ">皮膚科生物製劑與小分子標靶藥物常見": ">Dermatology biologics and small-molecule targeted drugs — common",
    },
}


def apply_to_file(path: Path, rel: str) -> int:
    text = path.read_text(encoding='utf-8')
    n = 0
    # Global substitutions (TRANSLATIONS)
    for zh, en in TRANSLATIONS.items():
        if zh in text:
            cnt = text.count(zh)
            text = text.replace(zh, en)
            n += cnt
    # Per-file substitutions
    for zh, en in PER_FILE.get(rel, {}).items():
        if zh in text:
            cnt = text.count(zh)
            text = text.replace(zh, en)
            n += cnt
    path.write_text(text, encoding='utf-8')
    return n


def main() -> int:
    targets = sorted(set(["blog/topical-acids-patient.html"]) | set(PER_FILE.keys()))
    total = 0
    for rel in targets:
        p = ROOT / rel
        if not p.exists():
            print(f"  [MISS]  {p}")
            continue
        n = apply_to_file(p, rel)
        print(f"  [{n:3d}]  {rel}")
        total += n
    print(f"\nTotal: {total} text substitutions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
