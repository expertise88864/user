#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""One-shot translator for blog/topics.html + blog/index.html hub pages.

These hub pages are mostly static <h2> cluster headings + <a> link texts
with no bilingual data-en attributes — so the EN mirror at
/en/blog/topics.html and /en/blog/index.html shows untranslated ZH to
GoogleBot. This script adds data-en="..." inline to every static element
that needs translation, in a translation dictionary maintained below.

Run after editing the dictionary; then re-run _gen_en_pages.py to refresh
the EN mirror.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Translation dictionary: ZH text → EN text.
# Add an entry here whenever you write a new topic-card link, a new
# cluster heading, or any other hub-page string. Order doesn't matter.
TRANSLATIONS: dict[str, str] = {
    # Cluster H2 headings (topics.html)
    "痘痘 · 痤瘡": "Acne",
    "防曬 · 紫外線": "Sunscreen · UV",
    "異位性皮膚炎 · 濕疹": "Atopic Dermatitis · Eczema",
    "色素沉澱 · 美白": "Pigmentation · Brightening",
    "玫瑰痤瘡 · 酒糟肌": "Rosacea",
    "落髮 · 頭皮": "Hair Loss · Scalp",
    "感染 · 黴菌 · 病毒": "Infections · Fungi · Viruses",
    "免疫 · 自體免疫疾病": "Immune · Autoimmune",
    "外用藥膏 · 處方用藥": "Topical & Prescription Drugs",
    "處置 / 手術": "Procedures / Surgery",
    # Anchor link text (topics.html article links)
    "痘痘 8 大迷思 — 民眾最常誤會的觀念":
        "8 Acne Myths — patient misconceptions clarified",
    "外用酸類完整衛教 — A 酸、A 醇、杜鵑花酸、果酸、水楊酸":
        "Topical acids — full patient guide (retinoids, AHA, BHA, azelaic, PHA)",
    "口服 A 酸完整衛教 — 適合誰、副作用、復發率":
        "Oral isotretinoin — who, side effects, relapse rate",
    "痘疤完整治療指引 — 4 種凹疤、紅疤、黑疤、肥厚疤怎麼選":
        "Acne scar treatment — atrophic, red, dark, hypertrophic",
    "口服抗生素治痘 — Doxycycline / Minocycline — 規劃中":
        "Oral antibiotics for acne — doxycycline / minocycline (coming)",
    "防曬 8 大迷思 — 室內、陰天、SPF、物理化學一次釐清":
        "8 Sunscreen Myths — indoor, cloudy day, SPF, mineral vs chemical",
    "含氧化鐵(iron oxide)防曬完整指南 — 規劃中":
        "Iron-oxide sunscreens — full guide (coming)",
    "嬰幼兒 / 孕婦 / 敏感肌防曬挑選 — 規劃中":
        "Sunscreen choice for infants / pregnancy / sensitive skin (coming)",
    "異位性皮膚炎概論 — 病態生理、診斷、嚴重度評分":
        "Atopic dermatitis overview — pathophysiology, diagnosis, severity",
    "異位性皮膚炎外用治療 — 保濕、類固醇、TCI、PDE4、JAK 軟膏":
        "AD topical treatment — moisturizer, steroid, TCI, PDE4, topical JAK",
    "異位性皮膚炎全身性治療 — 生物製劑、JAK 抑制劑、光療":
        "AD systemic treatment — biologics, JAK inhibitors, phototherapy",
    "異位性皮膚炎合併症與特殊族群 — 過敏進行曲、心理、懷孕、感染":
        "AD comorbidities & special populations — atopic march, mental health, pregnancy, infection",
    "兒童異膚 — Dupilumab 嬰幼兒時代":
        "Pediatric eczema — the dupilumab-infant era",
    "肝斑 7 大迷思 — 雷射、藥膏、停藥反黑、孕婦":
        "7 Melasma Myths — laser, topicals, rebound, pregnancy",
    "曬斑 / 雀斑雷射選擇指南 — 規劃中":
        "Sun spots / freckles laser selection guide (coming)",
    "美白成分大整理（氫醌 / 傳明酸 / 杜鵑花酸 / 維他命 C) — 規劃中":
        "Brightening ingredients — hydroquinone / tranexamic acid / azelaic / vitamin C (coming)",
    "玫瑰痤瘡 6 大迷思 — 不是過敏、不是螨蟲、能治好嗎？":
        "6 Rosacea Myths — not allergy, not Demodex, can it be cured?",
    "血管雷射 / 脈衝光治酒糟 — 規劃中":
        "Vascular laser / IPL for rosacea (coming)",
    "酒糟肌專用保養品挑選 — 規劃中":
        "Rosacea-friendly skincare selection (coming)",
    "落髮 / 雄性禿 7 大迷思 — Minoxidil、Finasteride、植髮真相":
        "7 Hair-loss / AGA Myths — minoxidil, finasteride, hair-transplant truths",
    "圓禿（鬼剃頭）完整衛教 — JAK 抑制劑時代，TDA 2024 共識":
        "Alopecia areata complete guide — JAK era, TDA 2024 consensus",
    "植髮 FUE / FUT 完整指南 — 規劃中":
        "Hair transplant FUE / FUT complete guide (coming)",
    "產後落髮怎麼辦 — 規劃中":
        "Postpartum hair loss management (coming)",
    "香港腳 / 灰指甲 7 大迷思 — 含 Terbinafine、Itraconazole 對照":
        "7 Athlete's Foot / Nail Fungus Myths — terbinafine vs itraconazole",
    "病毒疣 6 大迷思 — 香蕉皮、雷射打一次就好？HPV 疫苗？":
        "6 Wart Myths — banana peel, one-laser cure, HPV vaccine?",
    "帶狀皰疹（皮蛇）6 大迷思 — 72 小時黃金期、Shingrix":
        "6 Shingles Myths — 72-hour window, Shingrix",
    "蜂窩性組織炎完整衛教 — 規劃中":
        "Cellulitis complete patient guide (coming)",
    "乾癬完整衛教 — 分型、嚴重度評估、誘發因子與診斷":
        "Psoriasis complete guide — subtypes, severity, triggers, diagnosis",
    "乾癬外用藥治療 — 類固醇、維生素 D、特殊部位用法":
        "Psoriasis topical treatment — steroids, vitamin D, special sites",
    "乾癬全身性治療 — 光療、口服、生物製劑、健保給付":
        "Psoriasis systemic treatment — phototherapy, oral, biologics, Taiwan NHI",
    "乾癬合併症與特殊族群 — PsA、心血管、懷孕、兒童、指甲、紅皮症":
        "Psoriasis comorbidities & special populations — PsA, CV, pregnancy, pediatric, nail, erythroderma",
    "乾癬 7 大迷思 — 不是癬、不會傳染、生物製劑安全嗎？":
        "7 Psoriasis Myths — not tinea, not contagious, are biologics safe?",
    "A 酸、A 醇、杜鵑花酸、果酸、水楊酸、PHA、口服 A 酸、抗生素、生物製劑 — 處方藥完整解析":
        "Retinoids, retinol, azelaic acid, AHA, BHA, PHA, oral isotretinoin, antibiotics, biologics — full prescription drug review",
    "外用酸類完整衛教 — 五大酸一次搞懂":
        "Topical acids — all five acids in one guide",
    "口服 A 酸完整衛教":
        "Oral isotretinoin — complete patient guide",
    "類固醇藥膏完整使用指南 — 規劃中":
        "Topical steroid full-use guide (coming)",
    "外用免疫調節劑 Tacrolimus / Pimecrolimus — 規劃中":
        "Topical immunomodulators — tacrolimus / pimecrolimus (coming)",
    "皮膚切片與腫瘤切除手術完整衛教 — 為什麼要切？怎麼切？術後怎麼照顧？":
        "Skin biopsy & excision — why, how, post-op care",
    "表皮囊腫（粉瘤）— 為什麼會復發？要切除嗎？":
        "Epidermoid cyst — why does it recur? should it be excised?",
    "日光性角化症 + 鱗狀細胞癌 + 波文氏症 完整衛教":
        "Actinic keratosis + SCC + Bowen disease — complete guide",
    # Standalone strings (crumbs, headings, notices)
    "首頁": "Home",
    "衛教文章": "Articles",
    "主題地圖": "Topic Map",
    "主題地圖 · TOPICS": "Topic Map · TOPICS",
    "中文": "Chinese",
    "重要提醒": "Important notice",
    "本網站文章僅作衛教資訊、個別評估、處方、雷射或手術仍需就近至皮膚科專科醫師門診評估。本站不從事醫療廣告、亦不推薦特定診所或療程。":
        "All articles are for general education only. Individual evaluation, prescription, laser, or surgery must be assessed by a dermatologist in person. This site does not engage in medical advertising and does not recommend specific clinics or procedures.",
    # index.html — article card H2 titles + descriptions
    "皮膚科雷射完整對照 — 波長 × 適應症 × 證據強度":
        "Dermatologic laser comparison — wavelength × indication × evidence",
    "嬰幼兒 / 兒童異位性皮膚炎完整照護指南":
        "Infant & pediatric atopic dermatitis — complete care guide",
    "標靶藥物（TKI）皮膚副作用完整衛教 — TLCS + TDA 共識":
        "Targeted-therapy (TKI) cutaneous side effects — TLCS + TDA consensus",
    "猴痘（Mpox）皮膚照護完整指南 — TDA 官方建議":
        "Monkeypox (Mpox) skin care — full guide per TDA recommendations",
    "化膿性汗腺炎（HS）完整衛教 — TDA 共識":
        "Hidradenitis suppurativa (HS) — patient guide per TDA consensus",
    "帶狀皰疹（皮蛇）6 大迷思 — 繞一圈會死？疫苗值得嗎？神經痛多久？":
        "6 Shingles Myths — does it kill if it circles? is the vaccine worth it? how long does neuralgia last?",
    "病毒疣 6 大迷思 — 香蕉皮、雷射打一次就好？HPV 疫苗值得？":
        "6 Wart Myths — banana peel, one-laser cure? Is the HPV vaccine worth it?",
    "乾癬 7 大迷思 — 不是癬、不會傳染、生物製劑很安全嗎？":
        "7 Psoriasis Myths — not tinea, not contagious, are biologics safe?",
    "蕁麻疹 6 大迷思 — 一定是過敏？抗組織胺嗜睡？慢性能治好？":
        "6 Urticaria Myths — is it always allergy? do antihistamines cause drowsiness? can chronic urticaria be cured?",
    # Article descriptions
    "2022 德國 S2k 雷射指引整理。532-10600 nm 全波長，30+ 適應症「該用 / 可考慮 / 不建議」清單。":
        "2022 German S2k laser guideline summarized. 532-10600 nm full spectrum, 30+ indications classified as 'recommended / consider / not recommended'.",
    "0-5 歲嬰幼兒異膚：洗澡保濕、外用類固醇 / TCI、過敏原檢測時機、Dupilumab 6 個月以上適應症、過敏進行曲。依 2024 德國 S3 指引整理。":
        "Infant/child (0-5 y) atopic dermatitis: bathing & moisturizing, topical steroid / TCI, allergy-test timing, dupilumab indication (≥6 months), atopic march. Per 2024 German S3 guideline.",
    "EGFR 抑制劑痤瘡樣皮疹、乾皮症、甲溝炎、手足症 — 預防、評估與處置完整流程。":
        "EGFR-inhibitor acneiform eruption, xerosis, paronychia, hand-foot syndrome — prevention, evaluation and management workflow.",
    "病灶 5 階段、避免搔抓、溫和清潔、傷口照護、預防疤痕。":
        "Lesion staging (5 phases), avoiding scratching, gentle cleansing, wound care, scar prevention.",
    "反常性痤瘡、Hurley 分期、Adalimumab 健保 2024 給付、外科治療。":
        "Acne inversa, Hurley staging, adalimumab Taiwan NHI 2024 coverage, surgical treatment.",
    "72 小時黃金期、Shingrix vs Zostavax、皰疹後神經痛 PHN、年輕人為何也會得。附 dermatome 分布圖。":
        "72-hour golden window, Shingrix vs Zostavax, postherpetic neuralgia (PHN), why young adults get it. Includes dermatome distribution diagram.",
    "會自己好嗎？冷凍要打幾次？足底疣與雞眼怎麼分？HPV 疫苗對皮膚疣有幫助嗎？附 HPV 型別 × 部位對照圖。":
        "Does it resolve on its own? How many cryotherapy sessions? Plantar wart vs corn? Does the HPV vaccine help cutaneous warts? Includes HPV type × location chart.",
    "IL-17/23 抑制劑健保條件、乾癬性關節炎、心血管合併症、Methotrexate / Apremilast / Deucravacitinib 完整階梯。":
        "Taiwan NHI criteria for IL-17/23 inhibitors, psoriatic arthritis, cardiovascular comorbidity, methotrexate / apremilast / deucravacitinib treatment ladder.",
    "一定是吃到過敏的東西？反覆發作是免疫力差？抗組織胺會嗜睡上癮？會傳染家人？食物過敏原檢測有用？":
        "Is it always food allergy? Are recurrent episodes a sign of weak immunity? Are antihistamines addictive or sedating? Is it contagious? Are food allergy tests useful?",
    # Chip labels (categories / tags — many repeats)
    "皮膚科": "Dermatology",
    "處方 / 雷射": "Prescription / Laser",
    "痘疤治療": "Acne scar treatment",
    "處方用藥": "Prescription drugs",
    "圓禿 / 鬼剃頭": "Alopecia areata",
    "玫瑰斑 / 蠕形蟎蟲": "Rosacea / Demodex",
    "白斑 / Vitiligo": "Vitiligo",
    "外用類固醇": "Topical steroids",
    "生物製劑": "Biologics",
    "產品介紹": "Product guide",
    "美白成分": "Brightening ingredients",
    "常見問題": "FAQ",
    "處方 / 手術": "Prescription / Surgery",
    "粉瘤": "Epidermoid cyst",
    "健保規範": "Taiwan NHI rules",
    "處方治療": "Prescription treatment",
    "雷射 / 光電": "Laser / Light",
    "兒童異膚": "Pediatric eczema",
    "標靶藥物副作用": "Targeted-therapy side effects",
    "感染照護": "Infection care",
    "猴痘 Mpox": "Monkeypox / Mpox",
    "化膿性汗腺炎 HS": "Hidradenitis suppurativa (HS)",
    "迷思澄清": "Myth busting",
    "帶狀皰疹 / 皮蛇": "Shingles / Herpes zoster",
    "病毒疣 / HPV": "Warts / HPV",
    "完整衛教": "Full patient guide",
    "乾癬": "Psoriasis",
    "蕁麻疹": "Urticaria",
    # Common chip-label pairs (compound categories)
    "衛教 · 產品介紹": "Patient guide · Product overview",
    "衛教 · 痘痘": "Patient guide · Acne",
    "衛教 · 痘疤": "Patient guide · Acne scars",
    "衛教 · 防曬": "Patient guide · Sunscreen",
    "衛教 · 處方藥": "Patient guide · Prescription",
    "衛教 · 處方治療": "Patient guide · Prescription treatment",
    "衛教 · 雷射": "Patient guide · Laser",
    "衛教 · 圓禿": "Patient guide · Alopecia areata",
    "衛教 · 玫瑰斑": "Patient guide · Rosacea",
    "衛教 · 白斑": "Patient guide · Vitiligo",
    "衛教 · 兒童異膚": "Patient guide · Pediatric eczema",
    "衛教 · 標靶副作用": "Patient guide · Targeted-therapy SE",
    "衛教 · 帶狀皰疹": "Patient guide · Shingles",
    "衛教 · 病毒疣": "Patient guide · Warts",
    "衛教 · 乾癬": "Patient guide · Psoriasis",
    "衛教 · 蕁麻疹": "Patient guide · Urticaria",
    "衛教 · 異膚": "Patient guide · Atopic dermatitis",
    "衛教 · 香港腳": "Patient guide · Athlete's foot",
    "衛教 · 黴菌感染": "Patient guide · Fungal infections",
    "衛教 · 健保規範": "Patient guide · Taiwan NHI rules",
    "衛教 · 完整衛教": "Patient guide · Complete",
    "衛教 · 處方手術": "Patient guide · Prescription & surgery",
    "衛教 · 美白成分": "Patient guide · Brightening ingredients",
    "衛教 · 常見問題": "Patient guide · FAQ",
    "處方 · 外用類固醇": "Prescription · Topical steroid",
    "處方 · 生物製劑": "Prescription · Biologics",
    "處方 · 處方用藥": "Prescription drugs",
    "處方 · 化膿性汗腺炎": "Prescription · Hidradenitis suppurativa",
    "處方 · 標靶藥物副作用": "Prescription · TKI cutaneous SE",
    "處方 · 猴痘": "Prescription · Monkeypox",
    "處方 · 兒童異膚": "Prescription · Pediatric eczema",
    "處方 · 雷射": "Prescription · Laser",
    # Reference link text
    "來源": "Source",
    "「來源」": "[Source]",
    "[來源]": "[Source]",
    # Date / category prefix patterns (from card chips like "2026-05-07")
    "口服 A 酸 · 2026-05-07": "Oral isotretinoin · 2026-05-07",
    "美白 · 2026-05-04": "Brightening · 2026-05-04",
    "痘痘 · 2026-05-07": "Acne · 2026-05-07",
    "痘疤 · 2026-05-07": "Acne scar · 2026-05-07",
    # Hero / lead sentence (topical-acids-patient)
    "塗抹酸類完整衛教 — A 酸、A 醇、杜鵑花酸、果酸、水楊酸、PHA":
        "Complete patient guide to topical acids — retinoids, retinol, azelaic, AHA, BHA, PHA",
    "開架專櫃藥局滿滿的「酸」，有的拿來祛痘、有的拿來美白、有的拿來抗老。但成分標籤上 Retinol、Retinaldehyde、Tretinoin、Adapalene、Azelaic、Glycolic、Salicylic… 看到頭暈。本篇用一張表把":
        "Pharmacies and beauty counters are full of &quot;acids&quot; — some for acne, some for brightening, some for anti-aging. But the ingredient list (Retinol, Retinaldehyde, Tretinoin, Adapalene, Azelaic, Glycolic, Salicylic…) is dizzying. This article uses a single table to lay out",
    "整理清楚，告訴你它們各自做什麼、適合誰、不能跟誰一起用、孕婦能不能用、用了會不會反黑爆痘。":
        "clearly: what each does, who it suits, what not to combine with, pregnancy safety, and whether it causes purging or rebound pigmentation.",
    # Disclaimer / Notice strings
    "提醒 · ": "Reminder · ",
    "本文僅供衛教參考。是否用酸、用什麼濃度、合併用藥、停藥時機，請依您的皮膚科醫師個別判斷。皮膚屏障受損、嚴重發炎、剛做完雷射 / 換膚術後請暫停使用。":
        "This article is for general education only. Whether to use acids, what concentration, combined use, and timing of discontinuation should be individually assessed by your dermatologist. Pause use if your skin barrier is compromised, severely inflamed, or recently treated with laser / peel.",
    # Card descriptions on related articles
    "Topical Retinoids &amp; Acid Actives 完整整理":
        "Topical Retinoids &amp; Acid Actives — full clinical write-up",
    "同主題醫師版 — receptor selectivity、AHA pH/penetration、孕期安全表、retinoid dermatitis 處置。":
        "Same topic, clinician version — receptor selectivity, AHA pH/penetration, pregnancy safety table, retinoid dermatitis management.",
    "中重度痘痘可能需要進階到口服 A 酸 — 全衛教在這篇。":
        "Moderate-to-severe acne may need to step up to oral isotretinoin — full guide here.",
    # Author byline — shared across all 53 articles in the sticky header
    "陳翊嘉醫師 · 皮膚科衛教筆記":
        "Dr. Yi-Jia Chen · Dermatology Patient Education Notes",
    "陳翊嘉醫師": "Dr. Yi-Jia Chen",
    "皮膚科衛教筆記": "Dermatology Patient Education Notes",
    # Common card-chip date prefix patterns ("成分 · YYYY-MM-DD")
    "處方 · 2026-05-07": "Prescription · 2026-05-07",
    "處方 · 2026-05-09": "Prescription · 2026-05-09",
    "規範 · 2026-05-07": "NHI rules · 2026-05-07",
    "生物製劑 · 2026-05-04": "Biologics · 2026-05-04",
    "AI 與皮膚科 · 2026-05-23": "AI & Dermatology · 2026-05-23",
    "玫瑰斑 · 2026-05-04": "Rosacea · 2026-05-04",
    "白斑 · 2026-05-15": "Vitiligo · 2026-05-15",
    "白斑 · 2026-05-22": "Vitiligo · 2026-05-22",
    "光動力治療 · 2026-05-23": "Photodynamic therapy · 2026-05-23",
    "GLP-1 · 2026-05-23": "GLP-1 · 2026-05-23",
    # Related-article card titles (bogus data-en values across many files)
    "皮膚科生物製劑與小分子標靶藥物常見":
        "Dermatology biologics and small-molecule targeted drugs — overview",
    "皮膚科常用藥物的健保規範整理":
        "Taiwan NHI rules for common dermatology drugs",
    "牛皮癬全身性治療完整衛教":
        "Psoriasis systemic treatment — complete guide",
    "塗抹酸類完整衛教":
        "Topical acids — complete patient guide",
    "口服 A 酸完整衛教":
        "Oral isotretinoin — complete patient guide",
    "痘疤完整治療指引":
        "Acne scar treatment — complete guide",
    "美白成分完整解析":
        "Brightening ingredients — full breakdown",
    "外用酸類完整衛教":
        "Topical acids — complete patient guide",
    # Further-reading section common in clinical articles
    "Further reading:": "Further reading:",  # already EN
    "詳細給付條件請見 ":
        "For detailed coverage criteria, see ",
    "；生物製劑分類與藥效請見 ":
        "; for biologics drug-class overview and pharmacology, see ",
    "；台灣健保完整給付請見 ":
        "; for Taiwan NHI full coverage rules, see ",
    "牛皮癬全身性治療完整衛教 ":
        "Psoriasis systemic treatment — complete guide ",
    # Article-archive nav button (in sticky header)
    "← 文章索引": "← Articles",
    # perioral-dermatitis-guide hero
    "口周皮膚炎完整衛教": "Perioral dermatitis — complete patient guide",
    "衛教 · 鑑別與治療 ": "Patient guide · Diagnosis & treatment ",
    "衛教 · 鑑別與治療": "Patient guide · Diagnosis & treatment",
    "嘴角紅疹是痘痘還是濕疹？": "Is that rash around the mouth acne or eczema?",
    "口周皮膚炎的成因、症狀與治療":
        "Perioral dermatitis — causes, symptoms, and treatment",
    "一句話結論：": "Bottom line:",
    "嘴唇紅色邊緣那一圈會明顯「跳過」不發炎":
        "the lip vermilion border is conspicuously spared",
    "提醒：": "Reminder:",
    # Common related-card date prefixes ("接觸性皮膚炎 · 2026-05-08" etc.)
    "接觸性皮膚炎 · 2026-05-08": "Contact dermatitis · 2026-05-08",
    "異位性皮膚炎 · 2026-05-05": "Atopic dermatitis · 2026-05-05",
    "趾甲與足部 · 2026-05-13": "Toenail / foot · 2026-05-13",
    "口腔黏膜 · 2026-05-13": "Oral mucosa · 2026-05-13",
    # Footer / nav shared across all articles
    "皮膚科常見衛教及學習筆記網站":
        "Plain-language dermatology articles and clinical study notes",
    "皮膚科醫師": "Dermatologist",
    "網站": "Site",
    "關於我": "About",
    "隱私權政策": "Privacy",
    # actinic-keratosis-scc kicker + chips
    "衛教 · 皮膚癌 / 癌前病變": "Patient guide · Skin cancer / Precancer",
    "衛教 · 皮膚癌": "Patient guide · Skin cancer",
    "皮膚 T 細胞淋巴瘤(CTCL/MF)完整衛教":
        "Cutaneous T-cell lymphoma (CTCL / MF) — complete patient guide",
    "粉瘤完整衛教": "Epidermoid cyst — complete patient guide",
    "標靶藥物（TKI）皮膚副作用":
        "Targeted-therapy (TKI) cutaneous side effects",
    # More date chips
    "處置 / 手術 · 2026-05-09": "Procedures / Surgery · 2026-05-09",
    "皮膚淋巴瘤 · 2026-05-07": "Cutaneous lymphoma · 2026-05-07",
    "粉瘤 · 2026-05-05": "Epidermoid cyst · 2026-05-05",
    "標靶藥物 · 2026-05-04": "Targeted therapy · 2026-05-04",
    "Note:": "Note:",  # already EN; here for the disclaimer label translation pairing
    "突然變大、變硬、潰瘍出血":
        "rapid enlargement, hardening, ulceration, or bleeding",
    # rosacea-myths hero kicker + H1 + trigger labels
    "衛教 · 完整指引": "Patient guide · Complete guidelines",
    "玫瑰痤瘡（酒糟肌）完整衛教":
        "Rosacea (commonly called 酒糟肌) — complete patient guide",
    "陽光 / UV": "Sun / UV",
    "溫差 / 熱風": "Temperature change / heat",
    "酒精": "Alcohol",
    "辣的食物": "Spicy food",
    "熱飲 / 咖啡": "Hot drinks / coffee",
    "壓力": "Stress",
    "劇烈運動": "Intense exercise",
    "刺激性保養": "Irritating skincare",
    "皮膚科雷射完整對照": "Dermatologic laser comparison",
    "蕁麻疹 6 大迷思": "6 Urticaria Myths",
    "雷射 / 光電 · 2026-05-05": "Laser / Light · 2026-05-05",
    "蕁麻疹 · 2026-05-07": "Urticaria · 2026-05-07",
    # Disclaimer label variants
    "提醒 ·": "Reminder ·",
    # toenail-mechanical-disorders
    "衛教 · 趾甲與足部": "Patient guide · Toenail / foot",
    "腳趾甲變形 12 種型態完整圖鑑":
        "Toenail deformity — visual atlas of 12 patterns",
    "從鞋子、腳型、關節到糖尿病":
        "From shoes, foot shape, joints, to diabetes",
    "香港腳 / 灰指甲 7 大迷思":
        "7 Athlete's Foot / Nail Fungus Myths",
    "足癬 · 2026-05-03": "Tinea pedis · 2026-05-03",
    "口周皮膚炎 · 2026-05-13": "Perioral dermatitis · 2026-05-13",
    # Byline variant with space ("陳翊嘉 醫師")
    "陳翊嘉 醫師 · 整合 Ricardo 2026 JAAD review、Haneke 2024 Skin Appendage Disord、Watjer 2024 BMJ":
        "Dr. Yi-Jia Chen · Synthesis of Ricardo 2026 JAAD review, Haneke 2024 Skin Appendage Disord, Watjer 2024 BMJ",
    "陳翊嘉 醫師": "Dr. Yi-Jia Chen",
    "ChenDermatologist · 陳翊嘉 醫師":
        "ChenDermatologist · Dr. Yi-Jia Chen",
    # dermatologic-oral-examination related-card + chips
    "白斑（Vitiligo）完整衛教":
        "Vitiligo — complete patient guide",
    "白斑 · 2026-05-07": "Vitiligo · 2026-05-07",
    # dupilumab / semaglutide / PBM related-card titles
    "結節性癢疹完整衛教":
        "Prurigo nodularis — complete patient guide",
    "皮膚科生物製劑與小分子標靶藥物總覽":
        "Dermatology biologics and small-molecule targeted drugs — overview",
    "乾癬全身性治療完整衛教":
        "Psoriasis systemic treatment — complete patient guide",
    "皮膚科常用藥物健保規範完整整理":
        "Taiwan NHI rules for common dermatology drugs — complete reference",
    # Date chips
    "生物製劑安全 · 2026-05-16": "Biologics safety · 2026-05-16",
    "異位性皮膚炎 · 2026-05-09": "Atopic dermatitis · 2026-05-09",
    "結節性癢疹 · 2026-05-07": "Prurigo nodularis · 2026-05-07",
    "白斑復發 · 2026-05-23": "Vitiligo relapse · 2026-05-23",
    "乾癬 · 2026-05-09": "Psoriasis · 2026-05-09",
    # semaglutide-hair-loss hero stat cards
    "1.77 倍 / 2.41 倍": "1.77× / 2.41×",
    "不只是「瘦太快」": "Not just &quot;weight loss too fast&quot;",
    # PBM "Further reading" anchor texts (used inside <a> in proseEn)
    "乾癬全身性治療完整衛教 ":
        "Psoriasis systemic treatment — complete guide ",
    # laser-dermatology
    "衛教 · 醫療雷射": "Patient guide · Medical lasers",
    "皮膚科雷射完整對照": "Dermatologic laser comparison",
    "證據強度標示": "Evidence-strength legend",
    "玫瑰痤瘡 6 大迷思": "6 Rosacea Myths",
    "酒糟肌 · 2026-05-03": "Rosacea · 2026-05-03",
    # skin-biopsy-excision + epidermoid-cyst shared related-card
    "日光性角化症 AK + 鱗狀細胞癌 SCC 完整衛教":
        "Actinic keratosis (AK) + cutaneous SCC — complete patient guide",
    "皮膚癌 · 2026-05-08": "Skin cancer · 2026-05-08",
    # epidermoid-cyst
    "衛教 · 處方用藥 / 手術": "Patient guide · Prescription / Surgery",
    "粉瘤完整衛教": "Epidermoid cyst — complete patient guide",
    # === Myth-style article batch ===
    "衛教 · 迷思澄清": "Patient guide · Myth busting",
    "衛教 · 產品 / 處方介紹": "Patient guide · Product / Prescription",
    "衛教 · 兒童皮膚": "Patient guide · Pediatric skin",
    "衛教 · 處方用藥": "Patient guide · Prescription drugs",
    "帶狀皰疹（皮蛇）6 大迷思": "6 Shingles (Herpes Zoster) Myths",
    "肝斑 7 大迷思": "7 Melasma Myths",
    "美白成分完整解析": "Brightening ingredients — full breakdown",
    "嬰幼兒 / 兒童異位性皮膚炎完整照護指南":
        "Infant & pediatric atopic dermatitis — complete care guide",
    "標靶藥物（TKI）皮膚副作用完整衛教":
        "Targeted-therapy (TKI) cutaneous side effects — complete patient guide",
    "病毒疣 6 大迷思": "6 Wart Myths",
    "猴痘（Mpox）皮膚照護": "Monkeypox (Mpox) skin care",
    "乾癬 7 大迷思": "7 Psoriasis Myths",
    "病毒疣 · 2026-05-04": "Warts · 2026-05-04",
    "猴痘 · 2026-05-04": "Monkeypox · 2026-05-04",
    "乾癬 · 2026-05-07": "Psoriasis · 2026-05-07",
    "肝斑 · 2026-05-03": "Melasma · 2026-05-03",
    "酸類 · 2026-05-07": "Acids · 2026-05-07",
    "異位性皮膚炎 · 2026-05-03": "Atopic dermatitis · 2026-05-03",
    "外用類固醇 · 2026-05-04": "Topical steroids · 2026-05-04",
    "兩劑保護力 > 90%": "2-dose protection > 90%",
    "兩劑保護力 &gt; 90%": "2-dose protection > 90%",
    # AD-overview related-card titles
    "AD 外用治療完整衛教": "AD topical treatment — complete patient guide",
    "AD 合併症與特殊族群": "AD comorbidities & special populations",
    "接觸性皮膚炎（鑑別診斷）":
        "Contact dermatitis (differential diagnosis)",
    "嬰幼兒 AD 完整照護": "Infant & pediatric AD — complete care",
    "皮膚科 25 個最常見問題":
        "25 most-asked dermatology questions",
    "AD 外用治療完整衛教、": "AD topical treatment — complete patient guide、",
    # Batch 51 — hero kickers + H1 + chips
    "衛教 · 處方用藥 / 健保規範": "Patient guide · Prescription / NHI rules",
    "衛教 · 環境 / 職業": "Patient guide · Environment / Occupation",
    "圓禿（鬼剃頭）完整衛教":
        "Alopecia areata — complete patient guide",
    "皮膚科常用藥物健保規範完整整理":
        "Taiwan NHI rules for common dermatology drugs — complete reference",
    "接觸性皮膚炎完整衛教":
        "Contact dermatitis — complete patient guide",
    "白斑（Vitiligo）完整衛教":
        "Vitiligo — complete patient guide",
    "深入閱讀 · 給醫療同仁":
        "In-depth reading · For clinicians",
    # Severity card labels (alopecia-areata)
    "輕度 Mild": "Mild",
    "中度 Moderate": "Moderate",
    "重度 Severe": "Severe",
    "頭髮脫落 ≤ 20% 頭皮面積":
        "Hair loss ≤ 20% of scalp surface",
    "頭髮脫落 20-50%": "Hair loss 20–50% of scalp",
    "頭髮脫落 > 50%，含全頭禿、全身禿":
        "Hair loss > 50%, including alopecia totalis and universalis",
    "頭髮脫落 &gt; 50%，含全頭禿、全身禿":
        "Hair loss > 50%, including alopecia totalis and universalis",
    # NHI legend (nhi-derm-drugs)
    "健保標誌定義": "NHI badge legend",
    " 一般情況即可使用": " Usable in routine cases",
    " 需符合特定診斷 / 嚴重度 / 過去治療歷程，部分需事前審查 (PASS)":
        " Requires specific diagnosis / severity / prior-treatment history; some need prior authorization (PASS)",
    " 健保不給付，或核准適應症外使用":
        " Not covered by NHI, or off-label use",
    # PBM-related related-card chip dates
    "GLP-1 與落髮 · 2026-05-23": "GLP-1 & hair loss · 2026-05-23",
    "落髮 · 2026-05-03": "Hair loss · 2026-05-03",
    # topical-acids-clinical
    "把外用 retinoid 四代差別、Azelaic acid 雙重機轉、AHA pH ":
        "Topical retinoids by generation, azelaic acid's dual mechanism, AHA pH — ",
    "同主題的口語衛教版，可直接傳給門診病人。":
        "Patient-facing version of the same topic — share directly with clinic patients.",
    "系統性 retinoid：藥理、機轉、累積劑量、副作用、爭議、AAD 2024。":
        "Systemic retinoids: pharmacology, mechanism, cumulative dose, adverse effects, controversies, AAD 2024.",
    # topical-acids-clinical hero kicker
    "深入閱讀 · 給醫療同仁 ":
        "In-depth reading · For clinicians ",
    # Batch 53
    "衛教 · 感染照護": "Patient guide · Infection care",
    "衛教 · 罕見皮膚癌": "Patient guide · Rare skin cancer",
    # Batch 54
    "結節性癢疹（Prurigo Nodularis）完整衛教":
        "Prurigo nodularis — complete patient guide",
    "皮膚科生物製劑與小分子標靶藥物總覽":
        "Dermatology biologics and small-molecule targeted drugs — overview",
    "圓禿 · 2026-05-04": "Alopecia areata · 2026-05-04",
    "皮膚科衛教 ":
        "Dermatology patient education ",
    # SVG text labels (sunscreen-myths penetration diagram)
    "膠原蛋白 / 彈性纖維 — UVA 在這裡造成老化":
        "Collagen / elastic fibers — UVA causes aging here",
    "~ 數 mm": "~ a few mm",
    "主要造成曬傷": "Primarily causes sunburn",
    "主要造成曬黑、老化、肝斑": "Primarily causes tanning, aging, melasma",
    "加重肝斑、深膚色色素": "Worsens melasma and pigmentation in darker skin",
    # SVG <title> elements (hairloss-myths)
    "男性雄性禿 Hamilton-Norwood 分級（頭頂俯視）":
        "Male androgenetic alopecia — Hamilton-Norwood classification (top-down view)",
    # vitiligo-maintenance SVG titles
    "2×2 風險矩陣：手腳病灶與甲狀腺疾病合併時的調整後 hazard ratio":
        "2×2 risk matrix: adjusted hazard ratio when hand/foot lesions co-occur with thyroid disease",
    "長庚研究資料庫患者篩選流程：從 5365 人到最終 809 人世代":
        "Chang Gung database patient screening flow: from 5,365 to final 809-patient cohort",
    "Forest plot: 3 個獨立預測因子的調整後 hazard ratio":
        "Forest plot: adjusted hazard ratios for 3 independent predictors",
    "3-tier risk-stratified maintenance 建議":
        "3-tier risk-stratified maintenance recommendation",
    # sunscreen-myths SVG <text> labels
    "可見光 / 藍光": "Visible / blue light",
    "皮下 · Hypodermis": "Hypodermis",
    "真皮 · Dermis": "Dermis",
    "表皮 · Epidermis": "Epidermis",
    "膠原蛋白 / 彈性纖維 — UVA 在這裡造成老化":
        "Collagen / elastic fibers — UVA causes aging here",
    "膠原蛋白／彈性纖維 — UVA 在這裡造成老化":
        "Collagen / elastic fibers — UVA causes aging here",
    # melasma-myths SVG text labels
    "UVA · 可見光 · 藍光": "UVA · Visible · Blue light",
    "荷爾蒙": "Hormones",
    "過度活躍 → 製造大量 melanin":
        "Overactive → produces excess melanin",
    # topical-steroids-guide
    "外用類固醇完整指南": "Topical steroids — complete guide",
    # Common Note disclaimer text
    "類固醇藥膏屬處方藥（部分指示用藥例外），不應自行購買強效類固醇長期使用。請依醫師處方使用。":
        "Topical steroids are prescription medications (some indications are OTC exceptions). Do not self-purchase potent topical steroids for long-term use. Follow physician prescription.",
    "化膿性汗腺炎（HS）完整衛教":
        "Hidradenitis suppurativa (HS) — complete patient guide",
    "猴痘（Mpox）皮膚照護完整指南":
        "Monkeypox (Mpox) skin-care complete guide",
    "皮膚 T 細胞淋巴瘤(CTCL / MF)":
        "Cutaneous T-cell lymphoma (CTCL / MF)",
    "帶狀皰疹 6 大迷思": "6 Shingles Myths",
    "皮蛇 · 2026-05-04": "Shingles · 2026-05-04",
    "Key Facts（TDA 共識）": "Key Facts (TDA consensus)",
    # Final batch — short isolated strongs
    "每天": "Daily",
    "或": "or",
    "懷孕": "Pregnancy",
    "按主題整理": "Organized by topic",
    "9 篇": "9 articles",
    "8 大類別": "8 categories",
    "「Soak and seal」原則": "&quot;Soak and seal&quot; principle",
    "每年問關節症狀": "Ask about joint symptoms annually",
    "乾癬性關節炎（PsA）若未即時診斷":
        "Psoriatic arthritis (PsA), if undiagnosed in time,",
}


# Tags to which we will add data-en. We only target tag patterns where
# the ZH content has no bilingual attribute yet.
INTERESTING_TAGS = ("a", "h2", "h3", "span", "li", "p", "div", "summary", "option", "td", "th", "strong", "em", "figcaption", "text", "title", "h4", "blockquote")


_ATTR_VALUE_RANGES_CACHE: list[tuple[int, int]] | None = None


def _attribute_value_ranges(html: str) -> list[tuple[int, int]]:
    """Return (start, end) char ranges of every double-quoted attribute
    value in `html`. Used to skip tag-pattern matches that would land
    INSIDE an attribute value (which is malformed HTML — we'd be adding
    `data-en="..."` to a `<span>` that lives inside a `data-zh="..."`
    attribute, breaking the parent's quoting).
    """
    ranges: list[tuple[int, int]] = []
    # All attribute=val patterns: attr="value"
    for m in re.finditer(r'\s\w[\w-]*="([^"]*)"', html):
        # m.group(1) is the value content (no quotes)
        ranges.append((m.start(1), m.end(1)))
    return ranges


def _inside_attribute(pos: int, ranges: list[tuple[int, int]]) -> bool:
    for start, end in ranges:
        if start <= pos < end:
            return True
        if start > pos:
            return False
    return False


def _attr_safe(en: str) -> str:
    """Escape any `"` in an EN translation so it's safe to put inside an
    HTML attribute value. Replaces literal `"` with `&quot;`. Does NOT
    touch existing `&quot;` (idempotent because `&quot;` has no `"`).
    """
    return en.replace('"', '&quot;')


def add_data_en(html: str) -> tuple[str, int]:
    """For each interesting tag with inner CJK that matches a TRANSLATIONS
    key (after stripping leading <span> sibling tags), add `data-en="..."`
    to that tag's open. Skip tags that already carry data-en.

    Also fixes existing `data-en="<CJK>"` values where the data-en attribute
    was authored as ZH placeholder text — replace its value with the EN
    translation if the key is in TRANSLATIONS.

    2026-05-25 — guard against matches that fall inside ANOTHER attribute
    value (e.g., the literal `<span class='teal-text'>皮膚科</span>` that
    appears inside `data-zh="<span class='teal-text'>皮膚科</span>常見..."`).
    Adding data-en there would inject a `"` inside the parent attribute and
    break HTML5 parsing.

    2026-05-25 — also escape any `"` in EN translation values to `&quot;`
    before injection so EN text like `Not just "weight loss too fast"`
    doesn't break attribute quoting.

    Returns (new_html, replacement_count).
    """
    count = 0

    # Pre-pass: fix bogus data-en="<ZH>" values
    for zh, en in TRANSLATIONS.items():
        bogus_attr = f'data-en="{zh}"'
        good_attr = f'data-en="{_attr_safe(en)}"'
        if bogus_attr in html:
            occ = html.count(bogus_attr)
            html = html.replace(bogus_attr, good_attr)
            count += occ

    for zh, en in TRANSLATIONS.items():
        if zh not in html:
            continue
        en_attr = f' data-en="{_attr_safe(en)}"'

        # Case A: tag with inner-only text matching ZH exactly
        # <tagX attrs>ZH</tagX>
        pat_simple = re.compile(
            r'<(' + '|'.join(INTERESTING_TAGS) + r')\b([^>]*?)>'
            + re.escape(zh)
            + r'</\1>',
            re.IGNORECASE,
        )

        def repl_simple(m: re.Match) -> str:
            nonlocal count
            attrs = m.group(2)
            if 'data-en=' in attrs:
                return m.group(0)
            # Skip if this match starts inside another attribute value
            ranges = _attribute_value_ranges(html)
            if _inside_attribute(m.start(), ranges):
                return m.group(0)
            count += 1
            return f'<{m.group(1)}{attrs}{en_attr}>{zh}</{m.group(1)}>'

        html = pat_simple.sub(repl_simple, html)

        # Case B: tag with a leading <span...>...</span> sibling followed
        # by ZH text (the topic-card <h2><span>N</span>ZH</h2> pattern)
        pat_with_span = re.compile(
            r'<(h2|h3)\b([^>]*?)>(<span[^>]*>[^<]*</span>)'
            + re.escape(zh)
            + r'</\1>',
            re.IGNORECASE,
        )

        def repl_with_span(m: re.Match) -> str:
            nonlocal count
            attrs = m.group(2)
            if 'data-en=' in attrs:
                return m.group(0)
            ranges = _attribute_value_ranges(html)
            if _inside_attribute(m.start(), ranges):
                return m.group(0)
            count += 1
            return f'<{m.group(1)}{attrs}{en_attr}>{m.group(3)}{zh}</{m.group(1)}>'

        html = pat_with_span.sub(repl_with_span, html)

    return html, count


def process(path: Path) -> int:
    text = path.read_text(encoding='utf-8')
    new_text, n = add_data_en(text)
    if new_text != text:
        path.write_text(new_text, encoding='utf-8')
        print(f"  [WRITE] {path}: +{n} data-en attributes")
    else:
        print(f"  [SKIP]  {path}: no changes")
    return n


def main() -> int:
    total = 0
    # Hub pages first
    hub_files = ["blog/topics.html", "blog/index.html"]
    for rel in hub_files:
        p = ROOT / rel
        if not p.exists():
            continue
        total += process(p)
    # Then all blog articles for common UI strings (lang option, chips, etc.)
    blog_dir = ROOT / "blog"
    if blog_dir.exists():
        for p in sorted(blog_dir.glob("*.html")):
            if p.name in {"topics.html", "index.html"}:
                continue
            total += process(p)
    print(f"\nTotal: +{total} data-en attributes added.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
