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

    # === psoriasis-biologic-monitoring "Further reading" anchor wraps ===
    "乾癬全身治療請看 ":
        "for psoriasis systemic treatment, see ",
    "；生物製劑機轉與藥物選擇請看 ":
        "; for biologic mechanism of action and drug selection, see ",
    "；台灣健保完整給付條件請看 ":
        "; for full Taiwan NHI coverage conditions, see ",
    # Footer references in Chinese (Taiwan NHI documents)
    "衛生福利部中央健康保險署. 全民健康保險藥品給付規定（生物製劑用於乾癬治療部分；114/6/1 修正版本）. 公告日期 114/4/23. ":
        "Taiwan NHI Administration. National Health Insurance Drug Coverage Regulations (Biologics for Psoriasis section; revised effective 2025/6/1). Published 2025/4/23. ",
    "衛生福利部食品藥物管理署. 各生物製劑藥品仿單（adalimumab、infliximab、etanercept、certolizumab、ustekinumab、secukinumab、ixekizumab、brodalumab、bimekizumab":
        "Taiwan FDA. Drug package inserts for each biologic (adalimumab, infliximab, etanercept, certolizumab, ustekinumab, secukinumab, ixekizumab, brodalumab, bimekizumab",
    # semaglutide-hair-loss SVG <title> elements (visible in many SR tools)
    "圖 1：GLP-1RA 使用者 vs metformin 的新發掉髮風險 (RR 95% CI)":
        "Figure 1: GLP-1RA users vs metformin — new-onset hair-loss risk (RR 95% CI)",
    "圖 2：GLP-1 / GIP agonist 使用者 vs 對照 — 疤痕性禿髮治療 HRU RR":
        "Figure 2: GLP-1 / GIP agonist users vs controls — scarring alopecia treatment HRU RR",
    "圖 3：Herrera 與 Hill 兩篇研究的族群與結果 2×2 矩陣":
        "Figure 3: Herrera and Hill — population × outcome 2×2 matrix",
    "圖 4：GLP-1RA 對毛囊的雙路徑機轉假說":
        "Figure 4: GLP-1RA dual-pathway hypothesis on hair follicle",
    "圖 5：新發掉髮 RR 隨用藥時間累積上升":
        "Figure 5: New-onset hair-loss RR accumulating over time",
    # semaglutide-hair-loss list items (PSM cohort characteristics)
    "：女性 85.65% vs 87.27%(SMD 0.0474)— 反映疤痕性禿髮(尤其 CCCA、FFA)的女性盛行特性。":
        ": 85.65% vs 87.27% female (SMD 0.0474) — reflecting the female predominance of scarring alopecia (especially CCCA, FFA).",
    "：35.9 vs 35.2 kg/m²(SMD 0.0916)— 屬肥胖等級、解釋為何這群人會被處方 GLP-1 / GIP。":
        ": 35.9 vs 35.2 kg/m² (SMD 0.0916) — obese range, explaining why this population was prescribed GLP-1 / GIP.",
    "：白人 66.01% vs 62.93%、黑人 24.85% vs 29.80%(SMD 0.1113)":
        ": White 66.01% vs 62.93%, Black 24.85% vs 29.80% (SMD 0.1113)",
    "：21.52% vs 22.11%(SMD 0.0145、平衡良好)。":
        ": 21.52% vs 22.11% (SMD 0.0145, well balanced).",

    # === laser-dermatology hero + legend ===
    "本文為衛教整理。實際雷射選擇需專科醫師依個別膚色 (Fitzpatrick I-VI)、病灶深度、過往治療反應評估。「同一波長」不同廠牌 / 不同脈寬 / 不同能量結果差異很大，本文僅整理波長層級的適應症。":
        "This article is a patient-education summary. Actual laser selection must be done by a specialist based on individual skin type (Fitzpatrick I–VI), lesion depth, and prior treatment response. Even at the \"same wavelength\", outcomes differ significantly across manufacturers, pulse widths, and energy settings. This guide covers only wavelength-level indications.",
    " 多數知情者會選擇此療法，效果與安全有充分證據":
        " Most informed patients would choose this treatment; efficacy and safety are well supported",
    " 多數會選擇，但仍需個別評估":
        " Most would choose it, but individual evaluation is still needed",
    " 證據有限或風險效益不明確，個案考量":
        " Evidence is limited or risk-benefit is unclear; consider case-by-case",
    " 多數不會選擇此療法，效果差或風險高":
        " Most would not choose this treatment; efficacy is poor or risk is high",
    # laser-dermatology H1
    '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n皮膚科雷射完整對照':
        '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n<span data-zh="皮膚科雷射完整對照" data-en="Dermatologic laser comparison">皮膚科雷射完整對照</span>',

    # === skin-biopsy-excision TLDR ===
    "、約 1-2% 因感染等併發症需要追蹤、整體安全性高。":
        "; about 1–2% require follow-up for complications such as infection; overall safety is high.",
    "「切片會讓癌細胞擴散」是常見迷思":
        "\"Biopsy spreads cancer\" is a common myth",
    " — 實證上不存在這個風險、反而":
        " — evidence does not support this risk; on the contrary,",
    "沒切片才會延誤診斷":
        "skipping biopsy delays diagnosis",
    "。皮膚腫瘤切除手術中、":
        ". In skin tumor excision surgery, ",
    "正確設計梭形（fusiform）的長寬比 3：1、頂角 ≤ 30°、長軸平行 Langer 皮膚張力線":
        "correct fusiform design with a 3:1 length-to-width ratio, apex angle ≤30°, and long axis parallel to Langer's tension lines",
    "是疤痕美觀的關鍵（":
        " is the key to cosmetically acceptable scars (",
    "）。傷口感染率約 1-3%（":
        "). Wound infection rate is about 1–3% (",
    "）、抗生素並非常規預防、僅高風險病人或部位（植入瓣、糖尿病、免疫抑制、人工關節等）或免疫抑制者使用。":
        "). Routine antibiotic prophylaxis is not recommended; reserve antibiotics for high-risk patients or sites (skin flap, diabetes, immunosuppression, prosthetic joint, etc.).",

    # === epidermoid-cyst TLDR ===
    "長在": "Lumps located on the ",
    "的腫塊有時是其他疾病（如皮樣囊腫、淋巴管瘤、脂肪瘤），需皮膚科醫師面對面評估，本文不能取代看診。":
        " can sometimes be other diseases (dermoid cyst, lymphangioma, lipoma); evaluation must be in person by a dermatologist. This article does not replace consultation.",
    "是表皮細胞陷入皮下後形成的":
        " forms when epidermal cells become trapped below the skin surface, creating a ",
    "，袋子裡裝滿角質與皮脂混合物（臭豆腐味）。":
        " — the sac is filled with a mixture of keratin and sebum (often with a stinky-tofu smell).",
    "。只擠掉內容物、不切除囊袋，囊袋會繼續產生新角質 → 反覆腫起來 → 反覆發炎 → 越來越大、越來越疤。「粉瘤 = 痘痘」是錯誤的概念。":
        ". Squeezing out the contents without removing the capsule leaves the sac in place; it keeps producing new keratin → repeated swelling → repeated inflammation → larger and more scarred over time. The notion that \"epidermoid cyst = acne pimple\" is incorrect.",
    # epidermoid-cyst H1
    '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n粉瘤完整衛教':
        '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n<span data-zh="粉瘤完整衛教" data-en="Epidermoid cyst — complete patient guide">粉瘤完整衛教</span>',

    # === shingles-myths TLDR ===
    "）是潛伏的":
        ") is reactivation of dormant ",
    "在年紀大、免疫低下時重新活化。台灣 50 歲以上每 3 個人就有 1 個會發作。「繞一圈會死」是民間誤解，但":
        " when age or immunosuppression weakens immunity. In Taiwan, 1 in 3 people over 50 will experience an episode. The folk belief that \"it kills if it circles your body\" is wrong, but ",
    "確實會大幅增加皰疹後神經痛（PHN）風險。本文整理 6 個最常見的錯誤觀念，以及該不該打":
        " genuinely increases the risk of post-herpetic neuralgia (PHN). This article covers 6 of the most common misconceptions and whether to get the ",
    " 疫苗。":
        " vaccine.",
    "可能是「眼部帶狀皰疹」需立即眼科；Lumps located on the ":
        " may be \"herpes zoster ophthalmicus\" — immediate ophthalmology referral required. ",
    "可能是 Ramsay Hunt 症候群，需立即就醫。":
        " may be Ramsay Hunt syndrome — immediate medical attention required.",
    "帶狀皰疹（俗稱":
        "Herpes zoster (commonly called ",
    # shingles H1
    '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n帶狀皰疹（皮蛇）6 大迷思':
        '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n<span data-zh="帶狀皰疹（皮蛇）6 大迷思" data-en="6 Shingles (Herpes Zoster) Myths">帶狀皰疹（皮蛇）6 大迷思</span>',

    # === melasma-myths TLDR ===
    "肝斑(melasma)是亞洲女性最常見的色素困擾，門診講最多次的就是 —「我這個是不是肝斑？」、「雷射打一次就會消嗎？」、「我聽說氫醌會":
        "Melasma is the most common pigmentary concern in Asian women. The questions most often heard in clinic are — \"Is this melasma?\", \"Will one laser session clear it?\", \"I've heard hydroquinone ",
    "：肝斑同時跟「":
        ": melasma is driven by BOTH \"",
    "」與「":
        "\" AND \"",
    "」有關，所以單靠雷射不夠；單靠防曬也不夠，要 ":
        "\" — so laser alone is not enough, and sunscreen alone is not enough; ",
    " 才會穩定。":
        " is required for sustained control.",

    # === skin-whitening-agents TLDR + mechanism ===
    "美白藥膏（含氫醌、A 酸、Tri-Luma）為處方用藥，需皮膚科醫師評估。網路購買「神膏」常含":
        "Brightening creams containing hydroquinone, retinoid, or Tri-Luma are prescription only and require dermatologist evaluation. \"Miracle creams\" sold online often contain ",
    "，使用前請查證。":
        " — verify ingredients before use.",
    "受 UV、發炎、荷爾蒙刺激，經 ":
        " are stimulated by UV, inflammation, and hormones; via ",
    "催化合成":
        " they synthesize ",
    "，然後傳遞給角質細胞。美白成分作用點分四大類：":
        " and transfer it to keratinocytes. Brightening agents act on four targets:",
    "（氫醌、麴酸、熊果素、Resorcinol 衍生物）":
        " (hydroquinone, kojic acid, arbutin, resorcinol derivatives)",
    "（A 酸、果酸、水楊酸）":
        " (retinoids, AHAs, salicylic acid)",
    "（維他命 C、菸鹼醯胺）":
        " (vitamin C, niacinamide)",
    "（菸鹼醯胺、傳明酸）":
        " (niacinamide, tranexamic acid)",
    "先理解黑色素機轉":
        "First, understand melanin biology",
    # skin-whitening H1
    '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n美白成分完整解析':
        '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n<span data-zh="美白成分完整解析" data-en="Brightening ingredients — full breakdown">美白成分完整解析</span>',

    # === pediatric-eczema TLDR + key facts ===
    "嬰幼兒個別差異大，本文為衛教整理。實際藥物選擇與劑量請由皮膚科或兒科專科醫師評估。":
        "Infants vary widely; this article is a general education summary. Actual drug selection and dosing must be evaluated by a dermatologist or pediatrician.",
    "：兒童 13%、成人 2-3% （德國 / 台灣相近）":
        ": 13% in children, 2–3% in adults (similar in Germany and Taiwan)",
    ":60% 在 1 歲前發病、85% 在 5 歲前發病":
        ": 60% before age 1, 85% before age 5",
    "：異膚 → 食物過敏 → 氣喘 → 過敏性鼻炎（約 30-50% 順序進展）":
        ": AD → food allergy → asthma → allergic rhinitis (about 30–50% progress in this sequence)",
    ":40-60% 在青春期前明顯改善；30-50% 持續到成年":
        ": 40–60% improve markedly before puberty; 30–50% persist into adulthood",
    ":2023 年起核准 ":
        ": FDA-approved since 2023 for ",
    "（改變治療版圖）":
        " (a paradigm shift)",
    "關鍵數字":
        "Key numbers",
    # pediatric-eczema H1
    '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n嬰幼兒 / 兒童異位性皮膚炎完整照護指南':
        '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n<span data-zh="嬰幼兒 / 兒童異位性皮膚炎完整照護指南" data-en="Infant &amp; pediatric atopic dermatitis — complete care guide">嬰幼兒 / 兒童異位性皮膚炎完整照護指南</span>',

    # === atopic-dermatitis-overview proseEn leakage ===
    ":NB-UVB 是":
        ": NB-UVB is the ",
    "(優於寬波 UVB、UVA1)":
        " (superior to broadband UVB and UVA1)",
    ":光療期間":
        ": during phototherapy, ",
    "、視需要併用":
        ", combine as needed with ",
    "控制亞急性發炎":
        " to control subacute inflammation",
    "(避免照光誘發 Koebner / 加重)":
        " (avoid phototherapy-induced Koebner / flare)",
    ":頑固型可考慮":
        ": for refractory cases consider ",
    "(避免與 azathioprine 長期併用、提升皮膚癌風險)":
        " (avoid long-term combination with azathioprine due to increased skin-cancer risk)",
    ":正式 ":
        ": formal ",
    "較精準、亦可改採膚色分型(Fitzpatrick)起始":
        " is more accurate; Fitzpatrick skin-type-based starting dose is an alternative",
    "民眾最常問的皮膚科問題 25 題見〈":
        "see \"",
    "Baricitinib in adults with moderate to severe atopic dermatitis (BREEZE-異位性皮膚炎). ":
        "Baricitinib in adults with moderate to severe atopic dermatitis (BREEZE-AD). ",

    # === targeted-therapy-skin TLDR ===
    "。請與您的腫瘤科 / 胸腔科醫師、皮膚科醫師討論，共同擬定處置計畫。":
        ". Discuss with your oncologist / pulmonologist and dermatologist to develop a joint management plan.",
    "幾乎所有病人都會出現皮膚反應，主要因為 EGFR 受體也存在於皮膚毛囊與表皮細胞中。":
        " — almost all patients develop cutaneous reactions because the EGFR receptor is also expressed on skin follicles and epidermal cells.",
    " — 這往往是好的訊號，但需要正確的皮膚科處置才不會被迫減藥或停藥。":
        " — this is often a good prognostic sign, but proper dermatologic management is essential to avoid forced dose reduction or discontinuation.",
    "使用標靶藥物期間出現皮膚問題":
        "When skin problems develop during targeted-therapy use, ",
    # targeted-therapy H1
    '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n標靶藥物（TKI）皮膚副作用完整衛教':
        '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n<span data-zh="標靶藥物（TKI）皮膚副作用完整衛教" data-en="Targeted-therapy (TKI) cutaneous side effects — complete patient guide">標靶藥物（TKI）皮膚副作用完整衛教</span>',

    # === PDT SVG <title> elements + table headers ===
    "圖 1：PDT 分子機轉":
        "Figure 1: PDT molecular mechanism",
    "圖 2：ALA / MAL → PpIX 代謝":
        "Figure 2: ALA / MAL → PpIX metabolism",
    "圖 3：光源穿透深度":
        "Figure 3: Penetration depth by light source",
    "圖 4：12 適應症證據階梯":
        "Figure 4: 12 indications by evidence ladder",
    "圖 5：疼痛管理階梯":
        "Figure 5: Pain-management ladder",
    "<th>項目": "<th>Item",

    # === psoriasis-myths TLDR ===
    "乾癬（psoriasis）是一種":
        "Psoriasis is a chronic inflammatory skin disease caused by ",
    "造成的慢性發炎性皮膚疾病，全球盛行率約 2-3%，台灣約有 10-20 萬人。但很多病人長期抗拒治療 — 因為誤以為是「癬」、「皮膚不乾淨」、「會傳染」、「擦藥就好」，結果延誤治療。本文整理 7 個民眾最常見的誤解。":
        "; global prevalence is about 2–3%, and Taiwan has roughly 100,000–200,000 affected patients. But many resist treatment long-term, mistakenly believing it is a fungal infection (\"癬\" / tinea), a hygiene problem, contagious, or solvable with topicals alone — delaying care. This article covers the 7 most common misconceptions.",
    "乾癬不只是皮膚病，可能合併":
        "Psoriasis is not just a skin disease; it may be associated with ",
    "。請至皮膚科或風濕免疫科完整評估。":
        ". Comprehensive evaluation by dermatology or rheumatology / immunology is recommended.",
    # psoriasis-myths H1
    '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n乾癬 7 大迷思':
        '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n<span data-zh="乾癬 7 大迷思" data-en="7 Psoriasis Myths">乾癬 7 大迷思</span>',

    # === alopecia-areata + nhi-derm-drugs TLDR ===
    "本文為衛教整理，實際藥物選擇、劑量、健保給付條件需由專科醫師依個別狀況評估。":
        "This article is a patient-education summary. Actual drug selection, dosing, and Taiwan NHI coverage criteria must be evaluated by a specialist based on your individual situation.",
    "（出現任一項提高一級）：影響心理社交功能、眉毛/睫毛掉落、≥6 個月治療無反應、快速進展且拉髮試陽性。":
        " (any one promotes the severity by one tier): psychosocial impact, eyebrow / eyelash loss, ≥ 6 months treatment non-response, rapid progression with positive hair-pull test.",
    "健保條件每年由健保署修訂，本文整理至 2026 年 5 月為止。實際給付以":
        "Taiwan NHI coverage rules are revised annually by the NHIA; this article reflects rules through May 2026. Actual coverage follows ",
    "為準。處方需專科醫師依個別狀況評估。":
        ". Prescription must be evaluated by a specialist based on your individual situation.",
    # alopecia-areata H1
    '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n圓禿（鬼剃頭）完整衛教':
        '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n<span data-zh="圓禿（鬼剃頭）完整衛教" data-en="Alopecia areata — complete patient guide">圓禿（鬼剃頭）完整衛教</span>',
    # nhi-derm-drugs H1
    '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n皮膚科常用藥物健保規範完整整理':
        '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n<span data-zh="皮膚科常用藥物健保規範完整整理" data-en="Taiwan NHI rules for common dermatology drugs — complete reference">皮膚科常用藥物健保規範完整整理</span>',

    # === contact-dermatitis TLDR ===
    "本文內容僅作為一般教育參考。若您懷疑自己有接觸性皮膚炎、特別是反覆發作或職業相關紅疹、請至皮膚科門診評估；Patch Test 須由訓練有素的皮膚科醫師判讀。":
        "This article is for general education only. If you suspect contact dermatitis — especially recurrent or occupation-related rashes — please see a dermatologist; patch testing must be interpreted by a trained dermatologist.",
    " — 美髮業、醫療、餐飲、清潔、機械業最常見。":
        " — hairdressing, healthcare, food service, cleaning, and mechanical industries are the most affected.",
    "。一旦對某過敏原致敏、終生都會反應、必須長期避開。":
        ". Once sensitized to an allergen, the reaction is lifelong and the allergen must be avoided permanently.",
    # contact-dermatitis H1
    '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">接觸性皮膚炎完整衛教':
        '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]"><span data-zh="接觸性皮膚炎完整衛教" data-en="Contact dermatitis — complete patient guide">接觸性皮膚炎完整衛教</span>',

    # === vitiligo TLDR ===
    "本文為衛教整理。實際治療方案、劑量、療程請與您的皮膚科醫師討論。":
        "This article is a patient-education summary. Actual treatment, dose, and course must be discussed with your dermatologist.",
    "白斑為慢性疾病，治療需數月至數年才有色素再生。建議至皮膚科專科醫師評估個人化治療計畫。":
        "Vitiligo is a chronic disease; repigmentation typically takes months to years. Evaluation by a dermatologist is recommended to design a personalized treatment plan.",
    " — 表皮黑色素細胞功能喪失，造成邊界清晰的色素脫失斑塊。":
        " — loss of epidermal melanocyte function results in sharply demarcated depigmented patches.",
    "（約 20-30% 病人有家族史）。常合併甲狀腺異常等其他自體免疫疾病，需主動篩檢。":
        " (about 20–30% of patients have a family history). Often co-occurs with thyroid disease and other autoimmune conditions; active screening is recommended.",
    # vitiligo H1
    '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n白斑（Vitiligo）完整衛教':
        '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">\n<span data-zh="白斑（Vitiligo）完整衛教" data-en="Vitiligo — complete patient guide">白斑（Vitiligo）完整衛教</span>',

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
