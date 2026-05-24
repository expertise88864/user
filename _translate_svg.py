#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Batch translation of SVG <text> labels across all blog articles.

Loads a comprehensive Chinese→English dictionary and applies it to every
`<text>` element WITHOUT `data-en`. Adds `data-zh="..." data-en="..."`
attributes so _gen_en_pages.py picks them up on next build.

Run: python _translate_svg.py
"""
from __future__ import annotations
import io, os, re, sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent

# Comprehensive medical/dermatology Chinese→English dictionary.
# Add to this dict as new terms come up. Keys must match EXACTLY (whitespace +
# punctuation included).
TRANS = {
    # ─── Skin layers (anatomy) ───
    "表皮": "Epidermis",
    "真皮": "Dermis",
    "皮下": "Hypodermis",
    "皮下脂肪": "Subcutaneous fat",
    "表皮 · Epidermis": "Epidermis",
    "真皮 · Dermis": "Dermis",
    "皮下 · Hypodermis": "Hypodermis",
    "角質層": "Stratum corneum",
    "基底層": "Basal layer",
    "毛囊": "Hair follicle",
    "皮脂腺": "Sebaceous gland",
    "汗腺": "Sweat gland",
    "黑色素細胞": "Melanocyte",

    # ─── Severity levels ───
    "輕度": "Mild",
    "中度": "Moderate",
    "重度": "Severe",
    "極重度": "Very severe",
    "輕微": "Mild",
    "嚴重": "Severe",
    "高": "High",
    "中": "Medium",
    "低": "Low",
    "高風險": "High risk",
    "中風險": "Moderate risk",
    "低風險": "Low risk",
    "（最低風險）": "(lowest risk)",
    "（最高風險）": "(highest risk)",

    # ─── Yes/No / Reference / Group ───
    "有": "Yes",
    "無": "None",
    "是": "Yes",
    "否": "No",
    "有 / 沒有": "Yes / No",
    "參考組": "Reference group",
    "參考組：兩者皆無": "Reference: neither",
    "對照組": "Control group",
    "治療組": "Treatment group",
    "實驗組": "Experimental group",
    "兩者皆有": "Both",
    "兩者皆無": "Neither",
    "僅一個": "One only",

    # ─── Time / frequency ───
    "每日": "Daily",
    "每週": "Weekly",
    "每月": "Monthly",
    "每年": "Yearly",
    "一次": "Once",
    "兩次": "Twice",
    "三次": "Three times",
    "1 年": "1 year",
    "2 年": "2 years",
    "5 年": "5 years",
    "6 個月": "6 months",
    "12 個月": "12 months",
    "3-6 個月": "3-6 months",

    # ─── Common dermatology disease names ───
    "痘痘": "Acne",
    "粉刺": "Comedones",
    "膿皰": "Pustule",
    "丘疹": "Papule",
    "蕁麻疹": "Urticaria",
    "乾癬": "Psoriasis",
    "痤瘡": "Acne vulgaris",
    "苔癬": "Lichen",
    "玫瑰斑": "Rosacea",
    "酒糟": "Rosacea",
    "環肉": "Granuloma annulare",
    "脂漏": "Seborrheic dermatitis",
    "紅斑性狼瘡": "Lupus erythematosus",
    "多形紅斑": "Erythema multiforme",
    "白斑": "Vitiligo",
    "圓禿": "Alopecia areata",
    "雄性禿": "Androgenetic alopecia (AGA)",
    "休止期掉髮": "Telogen effluvium",
    "皮膚癌": "Skin cancer",
    "黑色素瘤": "Melanoma",
    "基底細胞癌": "Basal cell carcinoma",
    "鱗狀細胞癌": "Squamous cell carcinoma",
    "光化性角化症": "Actinic keratosis",
    "肝斑": "Melasma",
    "雀斑": "Freckle",
    "曬斑": "Sun spot",
    "汗管瘤": "Syringoma",
    "脂肪瘤": "Lipoma",

    # ─── Acne scar types ───
    "冰鑿型": "Ice-pick",
    "廂車型": "Boxcar",
    "滾動型": "Rolling",
    "肥厚型": "Hypertrophic",
    "萎縮型": "Atrophic",
    "窄、深、垂直": "Narrow, deep, vertical",
    "寬、淺至中、垂直壁": "Wide, shallow-to-moderate, vertical walls",
    "寬、波浪、底有牽絆": "Wide, undulating, with tethering at base",
    "→ 飛梭雷射 / 微針": "→ Fractional laser / microneedling",
    "→ 皮下分離 + 飛梭": "→ Subcision + fractional laser",

    # ─── Treatments ───
    "雷射": "Laser",
    "冷凍": "Cryotherapy",
    "手術": "Surgery",
    "切片": "Biopsy",
    "切除": "Excision",
    "電燒": "Electrocautery",
    "光療": "Phototherapy",
    "光動力": "PDT",
    "口服藥": "Oral medication",
    "外用藥": "Topical medication",
    "注射": "Injection",
    "類固醇": "Steroid",
    "外用類固醇": "Topical steroid",
    "口服類固醇": "Oral steroid",
    "抗組織胺": "Antihistamine",
    "抗生素": "Antibiotic",
    "免疫抑制劑": "Immunosuppressant",
    "生物製劑": "Biologic",
    "皮下分離": "Subcision",
    "飛梭雷射": "Fractional laser",
    "皮秒雷射": "Picosecond laser",
    "微針": "Microneedling",
    "酸類換膚": "Chemical peel",

    # ─── Symptoms / signs ───
    "癢": "Itch",
    "痛": "Pain",
    "紅腫": "Redness + swelling",
    "脫皮": "Desquamation",
    "起疹": "Rash",
    "起水泡": "Blistering",
    "化膿": "Pus",
    "結痂": "Crust",
    "色素沉澱": "Pigmentation",
    "色素脫失": "Depigmentation",

    # ─── Mechanism / processes ───
    "皮脂分泌過多": "Excess sebum",
    "毛孔角化異常": "Abnormal follicular keratinization",
    "阻塞 → 粉刺": "Obstruction → comedo",
    "痤瘡桿菌增生": "C. acnes proliferation",
    "免疫發炎反應": "Immune-inflammatory response",
    "紅腫 / 化膿": "Inflammation / pus",
    "青春期 / 油性肌": "Puberty / oily skin",
    "發炎": "Inflammation",
    "免疫": "Immunity",
    "代謝": "Metabolism",
    "氧化": "Oxidation",
    "纖維化": "Fibrosis",

    # ─── Diagnosis / common abbreviations ───
    "病史": "History",
    "症狀": "Symptom",
    "診斷": "Diagnosis",
    "治療": "Treatment",
    "預後": "Prognosis",
    "復發": "Recurrence",
    "緩解": "Remission",
    "停藥": "Treatment discontinuation",
    "減量": "Tapering",

    # ─── Hair loss specific ───
    "手腳病灶": "Acral involvement",
    "甲狀腺疾病": "Thyroid disease",
    "手腳病灶 × 甲狀腺疾病 — 調整後風險比值 (Hazard ratio)":
        "Acral lesions × thyroid disease — adjusted hazard ratio",
    "僅手腳": "Acral only",
    "僅甲狀腺": "Thyroid only",
    "髮根": "Hair root",
    "毛幹": "Hair shaft",

    # ─── Misc common labels ───
    "建議：": "Recommendation:",
    "每 appointment：": "Per appointment:",
    "每日 note/EMR：": "Daily note/EMR:",
    "下班後 EMR：": "After-hours EMR:",
    "看影像": "Image review",
    "資料來源：": "Source:",
    "百分點": "percentage points",
    "淺膚色": "Light skin",
    "中等": "Medium",
    "深膚色": "Dark skin",
    "膚色 bias：mLLM 對深膚色準確率系統性下降":
        "Skin-tone bias: mLLM accuracy systematically lower on dark skin",
    "GPT-5：差 13 個": "GPT-5: 13 points worse",
    "三個多模態 LLM 在 12 種發炎性皮膚病的辨識準確率":
        "Three multimodal LLMs' accuracy on 12 inflammatory skin diseases",
    "資料來源：Mahajan et al. JAAD 2026, Table I (n = 1,758 影像)":
        "Source: Mahajan et al. JAAD 2026, Table I (n = 1,758 images)",
    "資料來源：Mahajan et al. JAAD 2026, Table II":
        "Source: Mahajan et al. JAAD 2026, Table II",
    "淺膚色 (n=345)": "Light skin (n=345)",
    "中等 (n=346)": "Medium (n=346)",
    "深膚色 (n=157)": "Dark skin (n=157)",
    "ALA → PBG → 中間物質 →": "ALA → PBG → intermediates →",

    # ─── Acne scar comparison ───
    "紅疤（PIE）= 表面紅色尚未消退；黑疤（PIH）= 色素沉著":
        "PIE (post-inflammatory erythema) = persistent red marks; PIH (post-inflammatory hyperpigmentation) = pigmentation",
    "兩者皆會自行淡化，先防曬即可，不需立即雷射":
        "Both fade spontaneously — sunscreen first, no immediate laser needed",

    # ─── semaglutide-hair-loss SVGs (Herrera + Hill forest plots, 2×2 matrix, mechanism) ───
    "GLP-1RA 使用者 vs metformin — 新發掉髮風險 (TriNetX US)":
        "GLP-1RA users vs metformin — new-onset hair-loss risk (TriNetX US)",
    "資料來源：Herrera et al. JAAD 2026, Table I (n = 576,250 對、PSM 後)":
        "Source: Herrera et al. JAAD 2026, Table I (n = 576,250 pairs, after PSM)",
    "RR = 1.0 (無差異)": "RR = 1.0 (no difference)",
    "休止期 + 生長期掉髮": "Telogen + anagen effluvium",
    "其他非疤痕性掉髮": "Other non-scarring alopecia",
    "(L65 統括分類)": "(L65 umbrella category)",
    "圓禿 (AA)": "Alopecia areata (AA)",
    "圓禿 AA": "Alopecia areata (AA)",
    "雄性禿 AGA": "Androgenetic alopecia (AGA)",
    "其他非疤痕性": "Other non-scarring",
    "6 月 (NS)": "6 mo (NS)",
    "6 月": "6 months",
    "1 年 (顯著)": "1 yr (significant)",
    "anytime (顯著)": "anytime (significant)",
    "線段 = 95% CI、點 = point estimate": "Bar = 95% CI, dot = point estimate",
    "無差異": "No difference",
    "新發掉髮 RR 隨用藥時間累積": "New-onset hair-loss RR accumulates over treatment time",
    "資料：Herrera 2026 JAAD Table I (TriNetX US n = 576,250 對)":
        "Data: Herrera 2026 JAAD Table I (TriNetX US, n = 576,250 pairs)",
    "越上升 = 風險越高、實線 = 95% CI 顯著、點顯示 point estimate。雄性禿 AGA 是 4 種掉髮中累積風險最高的型態(anytime 2.41×)。":
        "Higher = greater risk; solid bar = 95% CI significant, dot = point estimate. AGA carries the highest cumulative risk of the 4 types (anytime 2.41×).",
    "GLP-1 / GIP 使用者對疤痕性禿髮治療使用率的影響":
        "GLP-1 / GIP users — impact on scarring-alopecia treatment utilization",
    "資料來源：Hill et al. JAAD 2026, Figure 1 (n = 1,171 對、PSM 後)":
        "Source: Hill et al. JAAD 2026, Figure 1 (n = 1,171 pairs, after PSM)",
    "(doxycycline、minocycline 等)": "(doxycycline, minocycline, etc.)",
    "(clobetasol、betamethasone 等)": "(clobetasol, betamethasone, etc.)",
    "病灶內 Triamcinolone": "Intralesional triamcinolone",
    "注射(IL-Triamcinolone)": "Injection (IL-triamcinolone)",
    "TNF-α 抑制劑": "TNF-α inhibitor",
    "(adalimumab 等)": "(adalimumab, etc.)",
    "← 顯著下降": "← Significant decrease",
    "顯著上升 →": "Significant increase →",
    "顯著下降 (95% CI 整段在 1 左)": "Significant decrease (95% CI entirely left of 1)",
    "未達顯著 (CI 跨 1)": "Non-significant (CI crosses 1)",
    "兩篇研究的族群 × 結果 2×2 矩陣":
        "2×2 matrix — populations × outcomes from the two studies",
    "用同一個藥、不同人群、不同 outcome、看似衝突實則互補":
        "Same drug, different populations, different outcomes — apparent conflict but actually complementary",
    "已罹患「疤痕性禿髮」": "Already has scarring alopecia",
    "一般人(沒有疤痕性禿髮)": "General population (no scarring alopecia)",
    "糖尿病 / 肥胖患者": "Diabetic / obese patients",
    "病情變化": "Disease course",
    "新發掉髮": "New-onset hair loss",
    "n = 1,171 對 PSM": "n = 1,171 PSM pairs",
    "治療使用率 ↓": "Treatment use ↓",
    "類固醇、HCQ、TCI、抗生素": "Steroids, HCQ, TCI, antibiotics",
    "(此格不適用)": "(N/A here)",
    "一般人本來就沒有": "General population never had it",
    "「疤痕性禿髮」可以惡化": "Can worsen scarring alopecia",
    "(資料不足)": "(insufficient data)",
    "已有疤痕性禿髮族群": "Already-diagnosed scarring-alopecia group",
    "會不會再「合併新發」": "Whether it triggers new-onset?",
    "非疤痕性掉髮、未報告": "Non-scarring hair loss — not reported",
    "新發掉髮 ↑": "New-onset hair loss ↑",
    "兩篇研究分別占據不同象限、彼此互補。同一個 GLP-1 / GIP 對「已發炎的疤痕性禿髮族群」是輔助、對「沒有禿髮的一般人」是風險。":
        "The two studies occupy different quadrants and complement each other. The same GLP-1 / GIP is therapeutic for inflamed scarring-alopecia patients but a risk for the otherwise hair-healthy general population.",
    "GLP-1RA → 毛囊 — 雙路徑機轉假說":
        "GLP-1RA → hair follicle — dual-pathway mechanism hypothesis",
    "兩條路徑同時運作、但對不同人群造成方向相反的淨結果":
        "Both pathways run in parallel but produce opposite net outcomes in different populations",
    "路徑 A：抗發炎": "Pathway A: anti-inflammatory",
    "(對「已發炎」族群有益)": "(beneficial for inflamed cohorts)",
    "• GLP-1R 結合 macrophage / T cell": "• GLP-1R binds macrophages / T cells",
    "• Th17 軸調節 → IL-17 ↓": "• Th17-axis modulation → IL-17 ↓",
    "• 全身性 metabolic syndrome ↓": "• Systemic metabolic syndrome ↓",
    "• 周圍毛囊 perifollicular 發炎 ↓": "• Perifollicular inflammation ↓",
    "→ 疤痕性禿髮病情改善": "→ Scarring-alopecia disease improvement",
    "路徑 B：代謝 / 內分泌重設": "Pathway B: metabolic / endocrine reset",
    "(對「易感體質」族群誘發)": "(triggers susceptible cohorts)",
    "• 熱量赤字 → 毛囊集體休止期化": "• Caloric deficit → mass follicle telogen entry",
    "• 蛋白質攝取不足 → AA / 角蛋白 ↓": "• Inadequate protein → amino acids / keratin ↓",
    "• IGF-1 軸下降 → 毛囊生長期縮短": "• IGF-1 axis ↓ → shorter anagen phase",
    "• SHBG ↑ → 游離 androgen 改變": "• SHBG ↑ → free androgen shift",
    "• 加速 AGA 顯化": "• Accelerates AGA expression",
    "→ 新發 TE / AE / AGA / AA": "→ New-onset TE / AE / AGA / AA",
    "兩條路徑同時運作、淨結果取決於患者體質":
        "Both pathways run in parallel; net outcome depends on patient constitution",
    "已有發炎性疤痕禿髮": "Has inflammatory scarring alopecia",
    "路徑 A 主導": "Pathway A dominant",
    "(治療需求 ↓ 30-47%)": "(treatment need ↓ 30-47%)",
    "兩者平衡": "Pathways balanced",
    "無禿髮體質、體重穩": "No hair-loss predisposition, stable weight",
    "(對頭髮影響不明顯)": "(minimal hair impact)",
    "易感體質 (家族禿髮 / PCOS)": "Susceptible (family alopecia / PCOS)",
    "路徑 B 主導": "Pathway B dominant",
    "(新發掉髮 ↑ 1.5-2.4 倍)": "(new-onset hair loss ↑ 1.5-2.4×)",

    # ─── photodynamic-therapy-overview SVGs ───
    "PDT 三要素 → ROS → 三大下游效應":
        "PDT triad → ROS → three downstream effects",
    "光敏劑": "Photosensitizer",
    "光源": "Light source",
    "分子氧": "Molecular oxygen",
    "細胞凋亡": "Apoptosis",
    "apoptosis / 粒線體": "apoptosis / mitochondria",
    "血管損傷": "Vascular damage",
    "內皮凋亡 / 微栓": "Endothelial apoptosis / microthrombi",
    "免疫活化": "Immune activation",
    "DAMPs / 細胞激素": "DAMPs / cytokines",
    "ALA / MAL → PpIX 代謝路徑與選擇性原理":
        "ALA / MAL → PpIX metabolism and selectivity principle",
    "正常細胞": "Normal cell",
    "ferrochelatase 正常活性": "Normal ferrochelatase activity",
    "PpIX 快速代謝 → heme": "PpIX rapidly metabolized → heme",
    "PpIX 累積 ≈ 低": "PpIX accumulation ≈ low",
    "光照下傷害輕微": "Mild damage under light",
    "癌 / 異常細胞": "Cancer / abnormal cell",
    "ferrochelatase 活性 ↓": "Ferrochelatase activity ↓",
    "PpIX 累積、代謝瓶頸": "PpIX accumulates — metabolic bottleneck",
    "PpIX 累積 ≈ 高": "PpIX accumulation ≈ high",
    "光照下選擇性破壞": "Selective phototoxicity under light",
    "PDT 光源穿透深度比較（皮膚層次）":
        "PDT light source — penetration depth comparison (skin layers)",
    "角質層 stratum corneum ~ 0.1 mm": "Stratum corneum ~ 0.1 mm",
    "藍光 BL": "Blue light (BL)",
    "綠光 GL": "Green light (GL)",
    "紅光 RL": "Red light (RL)",
    "近紅外": "Near-infrared",
    "近紅外 IR": "Near-infrared (IR)",
    "BL: 表淺 AK / 痘痘表層": "BL: superficial AK / surface acne",
    "GL: 中間深度": "GL: intermediate depth",
    "RL: BCC、深層 AK、痘痘": "RL: BCC, deep AK, acne",
    "IR: 深層或 ICG 配對": "IR: deep lesions or ICG combo",
    "表皮 epidermis ~ 0.5 mm": "Epidermis ~ 0.5 mm",
    "真皮 dermis ~ 2-4 mm": "Dermis ~ 2-4 mm",
    "皮下組織 subcutis": "Subcutis",
    "PDT 12 個適應症的證據等級階梯（LoE）":
        "LoE ladder for the 12 PDT indications",
    "LoE IA — 最強證據（多 RCT + meta-analysis）":
        "LoE IA — strongest evidence (multiple RCTs + meta-analyses)",
    "1. 光化性角化症 AK（FDA 唯一正式適應症、77-89%）":
        "1. Actinic keratosis (AK) — sole FDA-approved indication, 77-89%",
    "2. 淺層 / 低風險 BCC（92-97%）　3. Bowen disease（77-82%）　4. 中重度痘痘":
        "2. Superficial/low-risk BCC (92-97%) | 3. Bowen disease (77-82%) | 4. Moderate-severe acne",
    "LoE IB-II — 中等證據（單一 RCT 或多 cohort）":
        "LoE IB-II — moderate evidence (single RCT or multiple cohorts)",
    "5. 酒紅斑 PWS（Hemoporfin + KTP、中國上市）":
        "5. Port-wine stain (Hemoporfin + KTP, China-approved)",
    "6. 光老化 photoaging　　7. 光化性唇炎 actinic cheilitis":
        "6. Photoaging | 7. Actinic cheilitis",
    "8. 皮膚感染（HPV warts、MRSA、HSV、leishmaniasis）":
        "8. Skin infections (HPV warts, MRSA, HSV, leishmaniasis)",
    "LoE III-IV — 早期證據（case series、小型 trial）":
        "LoE III-IV — early evidence (case series, small trials)",
    "9. 蕈狀肉芽腫 mycosis fungoides（CTCL）":
        "9. Mycosis fungoides (CTCL)",
    "10. 玫瑰斑 rosacea　　11. 圓禿 alopecia areata":
        "10. Rosacea | 11. Alopecia areata",
    "12. 乳房外 Paget disease EMPD（紓緩性、無法取代手術）":
        "12. Extramammary Paget disease (palliative, not a surgery substitute)",
    "不適合 PDT": "Not suitable for PDT",
    "侵犯性 / 高風險 BCC、侵犯性 SCC、黑色素瘤、紫質症、孕婦":
        "Infiltrative / high-risk BCC, invasive SCC, melanoma, porphyria, pregnancy",
    "PDT 疼痛管理策略階梯（依 RCT 證據）":
        "PDT pain-management ladder (by RCT evidence)",
    "第一線（最強證據）": "First-line (strongest evidence)",
    "頭皮神經阻斷 nerve block（RCT 證實優於 cold-air 與 IV 鎮痛）":
        "Scalp nerve block (RCT-proven superior to cold-air + IV analgesia)",
    "第二線（簡單、便宜、中等效果）": "Second-line (simple, cheap, moderate)",
    "冷空氣鎮痛 cold-air analgesia（吹風機式冷風機）":
        "Cold-air analgesia (blower-style cooler)",
    "輔助：外用麻醉 + 心理支持": "Adjunct: topical anesthesia + psychological support",
    "外用 lidocaine / prilocaine 治療前 30 min；talk therapy（談話分心）有 RCT 證據":
        "Topical lidocaine/prilocaine 30 min pre-treatment; talk therapy (distraction) is RCT-supported",
    "改變方案": "Change protocol",
    "改用日光 PDT（顯著降低痛感、僅限淺層病灶）；改用 RL（比 BL 略輕）":
        "Switch to daylight PDT (significantly less painful, superficial only); switch to RL (slightly less painful than BL)",
    "註：靜脈鎮痛 / 全身麻醉非標準作法、僅在特殊情境（兒童、極大面積）考慮。":
        "Note: IV sedation / general anesthesia are non-standard, reserved for special cases (children, very large fields).",

    # ─── vitiligo-maintenance-clinical extras ───
    "❶ 手腳病灶 (acral involvement) — aHR 1.56":
        "① Acral involvement — aHR 1.56",
    "❷ 甲狀腺疾病 (Hashimoto / Graves) — aHR 1.42":
        "② Thyroid disease (Hashimoto / Graves) — aHR 1.42",
    "❸ 其他自體免疫共病 — aHR 1.73":
        "③ Other autoimmune comorbidities — aHR 1.73",
    "aHR 1.00": "aHR 1.00",
    "(最低風險)": "(lowest risk)",
}


def transform_text_element(html: str) -> tuple[str, int]:
    """Add data-zh + data-en to <text> elements with translatable content."""
    n_added = 0

    def repl(m):
        nonlocal n_added
        attrs = m.group("attrs")
        inner = m.group("inner")
        if "data-en=" in attrs:
            return m.group(0)
        en = TRANS.get(inner.strip())
        if not en:
            return m.group(0)
        n_added += 1
        new_attrs = attrs.rstrip() + f' data-zh="{inner.strip()}" data-en="{en}"'
        return f"<text{new_attrs}>{inner}</text>"

    pattern = re.compile(r"<text(?P<attrs>[^>]*)>(?P<inner>[^<]+)</text>")
    new_html = pattern.sub(repl, html)
    return new_html, n_added


def main() -> int:
    total = 0
    files_changed = 0
    for fn in sorted((ROOT / "blog").glob("*.html")):
        text = fn.read_text(encoding="utf-8")
        new_text, n = transform_text_element(text)
        if n > 0:
            fn.write_text(new_text, encoding="utf-8")
            files_changed += 1
            total += n
            print(f"  {fn.name}: +{n} SVG <text> translations")
    print(f"\n[translate-svg] {total} translations across {files_changed} files")
    print(f"  dictionary size: {len(TRANS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
