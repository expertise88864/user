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
    # === Cross-file: text segments OUTSIDE wrapping tags that need to
    # become EN regardless of which article they're in.

    # Footer copyright + email-contact line (53 articles share this)
    "網站內容更正 / 學術引用詢問 / 媒體合作請寄:":
        "Site corrections / citation queries / media inquiries:",
    "本站僅作教育參考,不構成醫療建議。":
        "This site is for general education only; it does not constitute medical advice.",
    "本站僅作教育參考、不構成醫療建議。":
        "This site is for general education only; it does not constitute medical advice.",
    " ChenDermatologist · 陳翊嘉醫師":
        " ChenDermatologist · Dr. Yi-Jia Chen",
    # Kicker / chip with trailing space (the div-with-child-span pattern
    # add_data_en can't auto-translate because the div has mixed content)
    ">衛教 · 鑑別與治療 <":
        ">Patient guide · Diagnosis & treatment <",
    ">衛教 · 鑑別與治療<":
        ">Patient guide · Diagnosis & treatment<",
    # === Per-article: long-text segments that only appear in one article ===

    # perioral-dermatitis-guide
    "嘴角紅疹是痘痘還是濕疹？\n":
        "Is that rash around the mouth acne or eczema?\n",
    "口周皮膚炎是嘴巴、鼻子、眼睛周圍反覆長紅色小丘疹和膿皰的發炎性皮膚病，":
        "Perioral dermatitis is a recurring inflammatory skin disease around the mouth, nose, and eyes, with small red papules and pustules; ",
    "是辨識關鍵；最常見的誘發因子是外用、吸入或口服類固醇。治療重點是「停掉誘發因子 + 溫和保養 ± 外用 / 口服藥 4-8 週」，並避免突然停類固醇造成反彈。":
        " is the key recognition clue. The most common trigger is topical, inhaled, or oral corticosteroid use. Management hinges on \"stopping the trigger + gentle skincare ± topical / oral medication for 4–8 weeks\" while avoiding abrupt corticosteroid withdrawal (rebound).",
    "本文僅作衛教參考，不可取代面對面看診。個別藥物選擇、劑量與療程請由皮膚專科醫師依您的狀況評估。":
        "This article is for general education only and does not replace in-person consultation. Individual drug selection, dose, and duration must be assessed by a dermatologist based on your specific situation.",
    "陳翊嘉醫師 · 整合 Acevedo-Fontanez 2026 JAAD review、Tempark 2014 Am J Clin Dermatol、Schwarz 2008 / Veien 1991 / Ollech 2020 JAAD 等實證":
        "Dr. Yi-Jia Chen · Synthesis of Acevedo-Fontanez 2026 JAAD review, Tempark 2014 Am J Clin Dermatol, Schwarz 2008 / Veien 1991 / Ollech 2020 JAAD evidence",
    # bogus data-en value
    'data-en="接觸性皮膚炎(過敏 vs 刺激)完整衛教"':
        'data-en="Contact dermatitis (allergic vs irritant) — complete patient guide"',
    ">接觸性皮膚炎(過敏 vs 刺激)完整衛教":
        ">Contact dermatitis (allergic vs irritant) — complete patient guide",
    # H1 with mixed text + span (replace whole pattern)
    '<h1 class="font-display font-bold leading-[1.18] text-[30px] sm:text-[40px]">\n嘴角紅疹是痘痘還是濕疹？<br/><span class="teal-text">口周皮膚炎的成因、症狀與治療</span></h1>':
        '<h1 class="font-display font-bold leading-[1.18] text-[30px] sm:text-[40px]">\n<span data-zh="嘴角紅疹是痘痘還是濕疹？" data-en="Is that rash around the mouth acne or eczema?">嘴角紅疹是痘痘還是濕疹？</span><br/><span class="teal-text" data-zh="口周皮膚炎的成因、症狀與治療" data-en="Perioral dermatitis — causes, symptoms, and treatment">口周皮膚炎的成因、症狀與治療</span></h1>',

    # === actinic-keratosis-scc TLDR text segments ===
    "是長期紫外線傷害造成的":
        " is caused by long-term UV damage; ",
    "則是":
        " is ",
    "是已經穿過基底膜、可能轉移的真正皮膚癌。三者是":
        " is a true skin cancer that has invaded through the basement membrane and may metastasize. The three lie along ",
    "的不同階段。本文整合英國皮膚科醫學會（BAD）":
        " at different stages. This article synthesizes the British Association of Dermatologists (BAD) guidelines ",
    "（日光性角化症）、": " (actinic keratosis), ",
    "（波文氏症）、": " (Bowen disease), ",
    "（鱗狀細胞癌）、以及美國皮膚科醫學會（AAD）":
        " (cutaneous squamous cell carcinoma), and the American Academy of Dermatology (AAD) ",
    "等五大指引、整理出一篇病人友善又有實證根據的完整衛教。":
        " — five major guidelines — into a single patient-friendly, evidence-based guide.",
    "本文僅作為一般教育參考。任何疑似日光性角化症、波文氏症或鱗狀細胞癌的皮膚變化、特別是":
        "This article is for general education only. Any skin change suspicious for actinic keratosis, Bowen disease, or squamous cell carcinoma — especially ",
    "、都應盡快至皮膚科門診評估、必要時接受切片(skin biopsy)確認。":
        " — should be evaluated by a dermatologist promptly, with a skin biopsy when indicated.",
    "、與長期紫外線(UVA + UVB)累積暴露密切相關。":
        ", strongly associated with cumulative UVA + UVB exposure.",
    "、但日光性角化症多發、累積終生風險不可忽視。":
        ", but actinic keratoses are often multiple, so the cumulative lifetime risk is significant.",
    "、必須長期追蹤。":
        ", requiring long-term surveillance.",
    # actinic-keratosis-scc H1 hero
    '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">日光性角化症 + 皮膚鱗狀細胞癌':
        '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]"><span data-zh="日光性角化症 + 皮膚鱗狀細胞癌" data-en="Actinic keratosis + cutaneous squamous cell carcinoma">日光性角化症 + 皮膚鱗狀細胞癌</span>',

    # === rosacea-myths TLDR + trigger footnote ===
    "臉常常潮紅、灼熱、長像痘痘的紅疹，皮膚科醫師會想到的常見診斷之一是":
        "If you have a face that frequently flushes, burns, and breaks out with acne-like red papules, one common diagnosis a dermatologist will consider is ",
    "。這個病很常被搞錯 —「我這是過敏吧」、「聽說酒糟是螨蟲造成的、洗乾淨就好」、「擦 A 酸應該也行」⋯⋯ 本文依英國 BAD 2021 指引、德國 2022 S2k 指引、ROSCO 共識與 TDA 2022 共識，從表現型分類、致病機轉與蠕形蟎蟲(Demodex)角色、誘因清單、治":
        ". This condition is often misunderstood — \"It must be an allergy,\" \"I heard rosacea is caused by mites, so just wash thoroughly,\" \"Topical retinoid should work too\" ... This article integrates the UK BAD 2021 guideline, German 2022 S2k guideline, ROSCO consensus, and TDA 2022 consensus to cover phenotype classification, pathogenesis and the role of Demodex mites, trigger lists, and treatment.",
    "本文僅供衛教。臉部紅疹也可能是脂漏性皮膚炎、紅斑性狼瘡、皮肌炎等不同疾病，個別判斷請至皮膚科。":
        "This article is for general education only. Facial redness can also be seborrheic dermatitis, lupus, dermatomyositis, or other conditions — individual evaluation must be done by a dermatologist in person.",
    "不是「碰到就一定爆」，而是":
        "It's not \"one exposure equals immediate flare\" — rather, triggers ",
    "才發作。每個人的點不同，記下你的觸發物。":
        " before a flare occurs. Everyone's threshold is different — track your personal triggers.",
    # rosacea-myths H1
    '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n玫瑰痤瘡（酒糟肌）完整衛教':
        '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n<span data-zh="玫瑰痤瘡（酒糟肌）完整衛教" data-en="Rosacea (commonly called 酒糟肌) — complete patient guide">玫瑰痤瘡（酒糟肌）完整衛教</span>',

    # === toenail-mechanical-disorders TLDR ===
    "研究顯示":
        "Studies show that ",
    "，而是鞋子擠壓 + 腳型問題造成的。最常被誤認為灰指甲，但如果腳型沒處理，再怎麼治療都會反覆。從鞋子、腳型、關節、神經、血管到糖尿病都會影響趾甲，這篇把 12 種變形型態跟對應原因一次講清楚。":
        " — they are caused by shoe pressure and foot shape. The most common misdiagnosis is onychomycosis (nail fungus), but if foot shape is not addressed, no amount of antifungal treatment cures it. From shoes, foot shape, joints, nerves, vessels, to diabetes — all affect toenails. This guide walks through 12 deformity patterns and their causes in one place.",
    "本文僅作衛教參考，不可取代面對面看診。個別治療請由皮膚專科或足踝專科醫師依您的狀況評估。":
        "This article is for general education only and does not replace in-person consultation. Individual treatment must be assessed by a dermatologist or foot-and-ankle specialist based on your specific situation.",
    # toenail H1
    '<h1 class="font-display font-bold leading-[1.18] text-[30px] sm:text-[40px]">\n腳趾甲變形 12 種型態完整圖鑑<br/><span class="teal-text">從鞋子、腳型、關節到糖尿病</span></h1>':
        '<h1 class="font-display font-bold leading-[1.18] text-[30px] sm:text-[40px]">\n<span data-zh="腳趾甲變形 12 種型態完整圖鑑" data-en="Toenail deformity — visual atlas of 12 patterns">腳趾甲變形 12 種型態完整圖鑑</span><br/><span class="teal-text" data-zh="從鞋子、腳型、關節到糖尿病" data-en="From shoes, foot shape, joints, to diabetes">從鞋子、腳型、關節到糖尿病</span></h1>',

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
    # Apply TRANSLATIONS to every blog article (cross-file segments like
    # footer copyright, kicker chips, byline tokens). Apply PER_FILE
    # substitutions only to their listed file.
    import glob
    files = sorted(glob.glob('blog/*.html'))
    total = 0
    for rel in files:
        p = ROOT / rel
        n = apply_to_file(p, rel)
        if n:
            print(f"  [{n:3d}]  {rel}")
        total += n
    print(f"\nTotal: {total} text substitutions across {len(files)} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
