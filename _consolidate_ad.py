#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Consolidate 4 AD articles → 2:

Final structure:
  1. atopic-dermatitis-overview     (BIG comprehensive guide:
                                     pathophysiology + diagnosis + severity
                                     + topical Tx + systemic Tx)
  2. atopic-dermatitis-comorbidity  (kept as-is, separate focus)

What this script does:
  1. Replaces overview's article body with a BIG merged version covering
     pathogenesis / diagnosis / severity / topical / systemic.
  2. Adds 308 redirects in vercel.json:
       /blog/atopic-dermatitis-topical  → /blog/atopic-dermatitis-overview
       /blog/atopic-dermatitis-systemic → /blog/atopic-dermatitis-overview
  3. Removes topical + systemic entries from DN.ARTICLES
  4. Removes them from DN.TAG_GROUPS

The 2 HTML files (topical, systemic) stay on disk so direct URL hits 308
to the overview.
"""
import os, re, sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))


def replace_article_body(html, new_inner):
    m = re.search(r'<article\s+class="max-w-3xl[^"]*"[^>]*>', html)
    if not m:
        return None
    open_start = m.start()
    open_end = m.end()
    depth = 1
    i = open_end
    while i < len(html) and depth > 0:
        no = html.find('<article', i)
        nc = html.find('</article>', i)
        if nc < 0: break
        if no >= 0 and no < nc:
            depth += 1; i = no + 8
        else:
            depth -= 1; i = nc + 10
    end = i
    return html[:open_start] + new_inner + html[end:]


# ────────────── BIG MERGED OVERVIEW ARTICLE ──────────────
MERGED_OVERVIEW = '''<article class="max-w-3xl mx-auto px-5 sm:px-8 my-8 prose prose-lg" data-slug="atopic-dermatitis-overview">
<nav class="text-[12.5px] text-ink-500 mb-3" aria-label="breadcrumb"><a href="/" class="hover:text-teal-700">首頁</a> · <a href="/blog/" class="hover:text-teal-700">衛教文章</a> · <span class="text-ink-700" data-zh="異位性皮膚炎完整指引" data-en="AD Complete Guide">異位性皮膚炎完整指引</span></nav>
<div class="text-[11px] uppercase tracking-[.22em] text-teal-700 font-semibold mb-2" data-zh="異膚 · 完整指引" data-en="Atopic Dermatitis · Complete Guide">異膚 · 完整指引</div>
<h1 class="font-display font-bold text-[28px] sm:text-[36px] leading-tight text-ink-900 mb-3" data-zh="異位性皮膚炎完整治療指引 — 從病態生理到 4 個生物製劑 + 7 級類固醇" data-en="Atopic Dermatitis Complete Treatment Guide — From Pathophysiology to 4 Biologics and 7-class Topical Steroids">異位性皮膚炎完整治療指引 — 從病態生理到 4 個生物製劑 + 7 級類固醇</h1>
<div class="text-[13.5px] text-ink-500 mb-6" data-zh="陳翊嘉 醫師 · 整合 Hanifin & Rajka 1980 + UK Working Party + Sidbury 2023 JAAD + Davis 2024/2025 JAAD · 更新 2026-05-14" data-en="Dr. Yi-Jia Chen · Integrating Hanifin & Rajka 1980 + UK Working Party + Sidbury 2023 JAAD + Davis 2024/2025 JAAD · Updated 2026-05-14">陳翊嘉 醫師 · 整合 Hanifin & Rajka 1980 + UK Working Party + Sidbury 2023 JAAD + Davis 2024/2025 JAAD · 更新 2026-05-14</div>
<div class="dn-tldr" style="background:#fefce8;border-left:4px solid #ca8a04;border-radius:0 10px 10px 0;padding:14px 18px;margin:18px 0;font-size:14px;line-height:1.85"><strong data-zh="一句話結論" data-en="TL;DR">一句話結論</strong>:<span data-zh="異位性皮膚炎是「皮膚屏障 + Th2 免疫 + 微生物失衡」三角缺陷的慢性發炎疾病。診斷靠臨床(Hanifin & Rajka 或 UK Working Party 標準),嚴重度用 EASI / SCORAD / IGA / POEM / DLQI 評估。治療三層次:每天保濕為基礎、急性期外用類固醇 / TCI / PDE-4 / JAK / Tapinarof,中重度搭配 4 個生物製劑(Dupilumab/Tralokinumab/Lebrikizumab/Nemolizumab)、3 個口服 JAK 或光療。" data-en="AD is a chronic inflammatory disease arising from a triad of barrier dysfunction, Th2-skewed immunity, and microbiome dysbiosis. Diagnosis is clinical (Hanifin & Rajka or UK Working Party criteria); severity is graded with EASI / SCORAD / IGA / POEM / DLQI. Three-tier treatment: daily moisturizer foundation; flare with topical TCS / TCI / PDE-4 / JAK / tapinarof; moderate-severe with 4 biologics (dupilumab / tralokinumab / lebrikizumab / nemolizumab), 3 oral JAKs, or phototherapy.">異位性皮膚炎是「皮膚屏障 + Th2 免疫 + 微生物失衡」三角缺陷的慢性發炎疾病。診斷靠臨床(Hanifin & Rajka 或 UK Working Party 標準),嚴重度用 EASI / SCORAD / IGA / POEM / DLQI 評估。治療三層次:每天保濕為基礎、急性期外用類固醇 / TCI / PDE-4 / JAK / Tapinarof,中重度搭配 4 個生物製劑(Dupilumab/Tralokinumab/Lebrikizumab/Nemolizumab)、3 個口服 JAK 或光療。</span></div>

<h2 id="epidemiology" data-zh="一、流行病學" data-en="1. Epidemiology">一、流行病學</h2>
<ul>
<li data-zh="<strong>全球盛行率</strong>:兒童 15-30%、成人 2-10%。台灣兒童約 8-10%" data-en="<strong>Global prevalence</strong>: 15–30% children, 2–10% adults. Taiwan pediatric ~8–10%"><strong>全球盛行率</strong>:兒童 15-30%、成人 2-10%。台灣兒童約 8-10%</li>
<li data-zh="<strong>發病高峰</strong>:60% 在 1 歲前、85% 在 5 歲前。第二高峰是青少年 / 成年期(占成人 AD 約 25%)" data-en="<strong>Onset peaks</strong>: 60% before age 1, 85% before age 5; second peak in adolescence/adulthood (~25% of adults)"><strong>發病高峰</strong>:60% 在 1 歲前、85% 在 5 歲前。第二高峰是青少年 / 成年期(占成人 AD 約 25%)</li>
<li data-zh="<strong>自然病程</strong>:40-60% 兒童在青春期前明顯改善、30-50% 持續到成年" data-en="<strong>Natural history</strong>: 40–60% improve before puberty; 30–50% persist into adulthood"><strong>自然病程</strong>:40-60% 兒童在青春期前明顯改善、30-50% 持續到成年</li>
</ul>

<h2 id="pathogenesis" data-zh="二、病態生理 — 三角缺陷" data-en="2. Pathophysiology — the triad">二、病態生理 — 三角缺陷</h2>
<h3 data-zh="① 皮膚屏障缺陷" data-en="① Barrier dysfunction">① 皮膚屏障缺陷</h3>
<ul>
<li data-zh="<strong>Filaggrin 突變</strong>:歐美 AD 患者 20-50% 有 FLG loss-of-function;亞洲常見突變不同" data-en="<strong>Filaggrin mutations</strong>: 20–50% of European/American AD; Asian populations have distinct mutations"><strong>Filaggrin 突變</strong>:歐美 AD 患者 20-50% 有 FLG loss-of-function;亞洲常見突變不同</li>
<li data-zh="<strong>脂質失衡</strong>:神經醯胺(尤其 ceramide-3、ceramide-NS)減少、膽固醇/脂肪酸/神經醯胺比例失調(理想 1:1:3)" data-en="<strong>Lipid imbalance</strong>: decreased ceramides; ideal cholesterol:fatty-acid:ceramide ratio 1:1:3"><strong>脂質失衡</strong>:神經醯胺減少、膽固醇/脂肪酸/神經醯胺比例失調(理想 1:1:3)</li>
</ul>
<h3 data-zh="② Th2 主導的免疫失調" data-en="② Th2-skewed immune dysregulation">② Th2 主導的免疫失調</h3>
<ul>
<li data-zh="<strong>急性期</strong>:Th2 + Th22。IL-4、IL-13 抑制屏障 + 促進 IgE class switching;IL-31 為癢 cytokine" data-en="<strong>Acute</strong>: Th2 + Th22. IL-4 and IL-13 suppress barrier and promote IgE; IL-31 is the itch cytokine"><strong>急性期</strong>:Th2 + Th22。IL-4、IL-13 抑制屏障 + 促進 IgE class switching;IL-31 為癢 cytokine</li>
<li data-zh="<strong>慢性期</strong>:Th1 + Th17 加入(亞洲族群、苔癬化病灶)" data-en="<strong>Chronic</strong>: Th1 + Th17 join (Asian populations and lichenified lesions)"><strong>慢性期</strong>:Th1 + Th17 加入(亞洲族群、苔癬化病灶)</li>
<li data-zh="<strong>新藥標靶</strong>:Dupilumab(IL-4Rα)、Tralokinumab/Lebrikizumab(IL-13)、Nemolizumab(IL-31RA)、JAK 抑制劑" data-en="<strong>Therapeutic targets</strong>: dupilumab (IL-4Rα), tralokinumab/lebrikizumab (IL-13), nemolizumab (IL-31RA), JAK inhibitors"><strong>新藥標靶</strong>:Dupilumab(IL-4Rα)、Tralokinumab/Lebrikizumab(IL-13)、Nemolizumab(IL-31RA)、JAK 抑制劑</li>
</ul>
<h3 data-zh="③ 皮膚微生物失衡" data-en="③ Skin microbiome dysbiosis">③ 皮膚微生物失衡</h3>
<ul>
<li data-zh="<strong>金黃色葡萄球菌</strong>:90%+ 病灶帶菌;Staphylococcal enterotoxin 為 superantigen 觸發因子" data-en="<strong>S aureus colonization</strong>: 90%+ lesions colonized; staphylococcal enterotoxin is a superantigen trigger"><strong>金黃色葡萄球菌</strong>:90%+ 病灶帶菌;Staphylococcal enterotoxin 為 superantigen 觸發因子</li>
<li data-zh="<strong>實務</strong>:稀釋漂白水泡澡(0.005% NaClO,每週 2 次)降低 S. aureus 負擔" data-en="<strong>Practical</strong>: dilute bleach baths (0.005% NaClO, twice weekly) reduce S aureus burden"><strong>實務</strong>:稀釋漂白水泡澡(0.005% NaClO,每週 2 次)降低 S. aureus 負擔</li>
</ul>

<h2 id="diagnosis" data-zh="三、診斷標準" data-en="3. Diagnostic criteria">三、診斷標準</h2>
<p data-zh="AD 是<strong>臨床診斷</strong>。最常用兩套:" data-en="AD is a <strong>clinical diagnosis</strong>. Two main criteria sets:">AD 是<strong>臨床診斷</strong>。最常用兩套:</p>
<h3>Hanifin & Rajka 1980</h3>
<ul>
<li data-zh="<strong>Major</strong>(≥ 3):瘙癢、典型分布、慢性反覆、個人或家族 atopy 史" data-en="<strong>Major</strong> (≥ 3): pruritus, typical morphology/distribution, chronic relapsing, personal/family atopy"><strong>Major</strong>(≥ 3):瘙癢、典型分布、慢性反覆、個人或家族 atopy 史</li>
<li data-zh="<strong>Minor</strong>(≥ 3,共 23 項):乾皮、毛囊角化、Dennie-Morgan 摺、白色皮膚劃痕、IgE 上升等" data-en="<strong>Minor</strong> (≥ 3 of 23): xerosis, keratosis pilaris, Dennie-Morgan fold, white dermographism, elevated IgE, etc."><strong>Minor</strong>(≥ 3,共 23 項):乾皮、毛囊角化、Dennie-Morgan 摺、白色皮膚劃痕、IgE 上升等</li>
</ul>
<h3 data-zh="UK Working Party(門診實用)" data-en="UK Working Party (clinic-friendly)">UK Working Party(門診實用)</h3>
<ul>
<li data-zh="必要:過去 12 個月內皮膚搔癢病史 + 任 3 項(屈側病史、個人 atopy 史、近 1 年皮膚普遍乾燥史、可見屈側濕疹、2 歲前發病)" data-en="Mandatory: itchy skin in past 12 months PLUS ≥ 3 of (flexural involvement, personal atopy, generalized dry skin, visible flexural eczema, onset before age 2)">必要:過去 12 個月內皮膚搔癢病史 + 任 3 項(屈側病史、個人 atopy 史、近 1 年皮膚普遍乾燥史、可見屈側濕疹、2 歲前發病)</li>
</ul>

<h2 id="severity" data-zh="四、嚴重度評分系統" data-en="4. Severity scoring">四、嚴重度評分系統</h2>
<ul>
<li data-zh="<strong>EASI</strong>(臨床試驗金標準):4 區域 × 4 個臨床特徵,0-72 分。EASI-75 是主要 endpoint" data-en="<strong>EASI</strong> (trial gold standard): 4 regions × 4 signs; 0–72. EASI-75 is the primary endpoint"><strong>EASI</strong>(臨床試驗金標準):4 區域 × 4 個臨床特徵,0-72 分。EASI-75 是主要 endpoint</li>
<li data-zh="<strong>SCORAD</strong>:A 面積 + B 強度 + C 主觀(癢 + 失眠);A/5 + 7B/2 + C(0-103)" data-en="<strong>SCORAD</strong>: A area + B intensity + C subjective (itch + sleep); A/5 + 7B/2 + C (0–103)"><strong>SCORAD</strong>:A 面積 + B 強度 + C 主觀(癢 + 失眠);A/5 + 7B/2 + C(0-103)</li>
<li data-zh="<strong>IGA-AD</strong>:5 級;治療目標 IGA 0/1 + 下降 ≥ 2(健保生物製劑門檻)" data-en="<strong>IGA-AD</strong>: 5 levels; goal IGA 0/1 + drop ≥ 2 (NHI biologic threshold)"><strong>IGA-AD</strong>:5 級;治療目標 IGA 0/1 + 下降 ≥ 2(健保生物製劑門檻)</li>
<li data-zh="<strong>POEM</strong>:7 題病人自評 5 分鐘可完成。<strong>DLQI</strong>:&gt; 10 顯著影響(健保生物製劑門檻)" data-en="<strong>POEM</strong>: 7-item patient-reported, 5 min. <strong>DLQI</strong>: > 10 = significant impact (NHI biologic threshold)"><strong>POEM</strong>:7 題病人自評 5 分鐘可完成。<strong>DLQI</strong>:&gt; 10 顯著影響(健保生物製劑門檻)</li>
<li data-zh="本網站線上計算器:<a href='/tools#dn-easi' style='color:#0c5159;text-decoration:underline'>EASI</a> · <a href='/tools#dn-scorad' style='color:#0c5159;text-decoration:underline'>SCORAD</a> · <a href='/tools#dn-dlqi' style='color:#0c5159;text-decoration:underline'>DLQI</a>" data-en="On-site calculators: <a href='/tools#dn-easi' style='color:#0c5159;text-decoration:underline'>EASI</a> · <a href='/tools#dn-scorad' style='color:#0c5159;text-decoration:underline'>SCORAD</a> · <a href='/tools#dn-dlqi' style='color:#0c5159;text-decoration:underline'>DLQI</a>">本網站線上計算器:<a href='/tools#dn-easi' style='color:#0c5159;text-decoration:underline'>EASI</a> · <a href='/tools#dn-scorad' style='color:#0c5159;text-decoration:underline'>SCORAD</a> · <a href='/tools#dn-dlqi' style='color:#0c5159;text-decoration:underline'>DLQI</a></li>
</ul>

<h2 id="topical" data-zh="五、外用治療" data-en="5. Topical therapy">五、外用治療</h2>
<h3 data-zh="保濕劑(強建議,基礎)" data-en="Moisturizers (strong rec, foundation)">保濕劑(強建議,基礎)</h3>
<ul>
<li data-zh="Sidbury 2023 強建議:每日 ≥ 1 次,每週至少 250 g(成人)、洗澡後 3 分鐘內塗(soak-and-seal)" data-en="Sidbury 2023 strong rec: daily ≥ 1×, ≥ 250 g/week (adult); apply within 3 min of bathing (soak-and-seal)">Sidbury 2023 強建議:每日 ≥ 1 次,每週至少 250 g(成人)、洗澡後 3 分鐘內塗(soak-and-seal)</li>
<li data-zh="優先含神經醯胺、甘油、凡士林;避香精 / 酒精 / 精油" data-en="Prefer ceramide / glycerin / petrolatum; avoid fragrance / alcohol / essential oils">優先含神經醯胺、甘油、凡士林;避香精 / 酒精 / 精油</li>
</ul>
<h3 data-zh="外用類固醇(TCS)— 7 級分類" data-en="Topical corticosteroids (TCS) — 7-class system">外用類固醇(TCS)— 7 級分類</h3>
<ul>
<li data-zh="<strong>I 超強</strong>:Clobetasol 0.05%、Halobetasol — 短期、肥厚部位" data-en="<strong>Class I (super-potent)</strong>: clobetasol 0.05%, halobetasol — short-term, thick areas"><strong>I 超強</strong>:Clobetasol 0.05%、Halobetasol — 短期、肥厚部位</li>
<li data-zh="<strong>II-III 強</strong>:Mometasone 0.1%、Betamethasone — 軀幹四肢急性期" data-en="<strong>Class II-III (high-potent)</strong>: mometasone 0.1%, betamethasone — body/limbs flare"><strong>II-III 強</strong>:Mometasone 0.1%、Betamethasone — 軀幹四肢急性期</li>
<li data-zh="<strong>IV-V 中</strong>:Triamcinolone 0.1%、Fluocinolone 0.025% — 多數中度病灶" data-en="<strong>Class IV-V (mid-potent)</strong>: triamcinolone 0.1%, fluocinolone 0.025% — most moderate lesions"><strong>IV-V 中</strong>:Triamcinolone 0.1%、Fluocinolone 0.025% — 多數中度病灶</li>
<li data-zh="<strong>VI-VII 弱</strong>:Hydrocortisone 1%、Desonide 0.05% — 臉、皺褶、嬰幼兒" data-en="<strong>Class VI-VII (low-potent)</strong>: hydrocortisone 1%, desonide 0.05% — face, folds, infants"><strong>VI-VII 弱</strong>:Hydrocortisone 1%、Desonide 0.05% — 臉、皺褶、嬰幼兒</li>
<li data-zh="<strong>用量 FTU</strong>:1 FTU(指尖單位 ≈ 0.5 g)= 2 個手掌面積" data-en="<strong>FTU dosing</strong>: 1 FTU (~0.5 g) covers 2 palms"><strong>用量 FTU</strong>:1 FTU(指尖單位 ≈ 0.5 g)= 2 個手掌面積</li>
<li data-zh="<strong>Proactive(強建議)</strong>:緩解後在「易復發處」每週 2 次,可降低復發 30-60%" data-en="<strong>Proactive (strong rec)</strong>: twice-weekly at relapse-prone sites reduces recurrence 30–60%"><strong>Proactive(強建議)</strong>:緩解後在「易復發處」每週 2 次,可降低復發 30-60%</li>
</ul>
<h3 data-zh="外用 calcineurin 抑制劑(TCI)" data-en="Topical calcineurin inhibitors (TCI)">外用 calcineurin 抑制劑(TCI)</h3>
<ul>
<li data-zh="<strong>Tacrolimus 0.03% / 0.1%、Pimecrolimus 1%</strong>:臉、皺褶、眼周特別有用。<strong>Black-box 風險被高估</strong>,2024 AAD 立場確認" data-en="<strong>Tacrolimus 0.03% / 0.1%, Pimecrolimus 1%</strong>: ideal for face, folds, periocular. <strong>Black-box risk overstated</strong> per 2024 AAD position"><strong>Tacrolimus 0.03% / 0.1%、Pimecrolimus 1%</strong>:臉、皺褶、眼周特別有用。<strong>Black-box 風險被高估</strong>,2024 AAD 立場確認</li>
<li data-zh="Proactive twice-weekly 是最強證據降低復發藥物;塗抹初期會刺痛(1-2 週後改善)" data-en="Proactive twice-weekly has the strongest relapse-reduction evidence; stinging in first 1–2 weeks">Proactive twice-weekly 是最強證據降低復發藥物;塗抹初期會刺痛(1-2 週後改善)</li>
</ul>
<h3 data-zh="PDE-4 / JAK / Tapinarof(2025 新藥)" data-en="PDE-4 / JAK / Tapinarof (2025 new agents)">PDE-4 / JAK / Tapinarof(2025 新藥)</h3>
<ul>
<li data-zh="<strong>Crisaborole 2%(Eucrisa)</strong>:≥ 2 歲輕中度;非類固醇" data-en="<strong>Crisaborole 2% (Eucrisa)</strong>: ≥ 2 yr mild-moderate; non-steroidal"><strong>Crisaborole 2%(Eucrisa)</strong>:≥ 2 歲輕中度;非類固醇</li>
<li data-zh="<strong>Roflumilast cream 0.15%(Zoryve)</strong>:Davis 2025 強建議;每日 1 次;鎮癢 24 小時內" data-en="<strong>Roflumilast cream 0.15% (Zoryve)</strong>: Davis 2025 strong rec; QD; itch relief within 24 h"><strong>Roflumilast cream 0.15%(Zoryve)</strong>:Davis 2025 強建議;每日 1 次;鎮癢 24 小時內</li>
<li data-zh="<strong>Ruxolitinib 1.5%(Opzelura)</strong>:JAK1/2;≥ 12 歲;鎮癢速度最快(12 小時內);Black-box 屬於 class label,外用全身吸收極低" data-en="<strong>Ruxolitinib 1.5% (Opzelura)</strong>: JAK1/2; ≥ 12 yr; fastest itch onset (within 12 h); black-box is class label, minimal systemic absorption"><strong>Ruxolitinib 1.5%(Opzelura)</strong>:JAK1/2;≥ 12 歲;鎮癢速度最快(12 小時內);Black-box 屬於 class label,外用全身吸收極低</li>
<li data-zh="<strong>Tapinarof cream 1%(Vtama)</strong>:Davis 2025 強建議;AhR 激動劑;每日 1 次;主要副作用為毛囊炎(10-20%)" data-en="<strong>Tapinarof cream 1% (Vtama)</strong>: Davis 2025 strong rec; AhR agonist; QD; main AE folliculitis (10–20%)"><strong>Tapinarof cream 1%(Vtama)</strong>:Davis 2025 強建議;AhR 激動劑;每日 1 次;主要副作用為毛囊炎(10-20%)</li>
</ul>

<h2 id="systemic" data-zh="六、全身治療" data-en="6. Systemic therapy">六、全身治療</h2>
<h3 data-zh="生物製劑(4 個)" data-en="Biologics (4 agents)">生物製劑(4 個)</h3>
<ul>
<li data-zh="<strong>Dupilumab(Dupixent)</strong>:阻 IL-4Rα;成人 600 mg loading → 300 mg q2w(6 個月 +);EASI-75 第 16 週 60-70%。台灣健保:成人 EASI ≥ 20 + DLQI &gt; 10 + 對外用 / 環孢靈 ≥ 8 週反應不足" data-en="<strong>Dupilumab (Dupixent)</strong>: anti–IL-4Rα; adult 600 mg load → 300 mg q2w (≥ 6 mo); EASI-75 ~60–70% at week 16. Taiwan NHI: adult EASI ≥ 20 + DLQI > 10 + inadequate response to topicals/cyclosporine ≥ 8 weeks"><strong>Dupilumab(Dupixent)</strong>:阻 IL-4Rα;成人 600 mg loading → 300 mg q2w(6 個月 +);EASI-75 第 16 週 60-70%。台灣健保:成人 EASI ≥ 20 + DLQI &gt; 10 + 對外用 / 環孢靈 ≥ 8 週反應不足</li>
<li data-zh="<strong>Tralokinumab(Adbry)</strong>:特異 IL-13;EASI-75 ~50%(略低於 dupi);結膜炎較少" data-en="<strong>Tralokinumab (Adbry)</strong>: IL-13 specific; EASI-75 ~50% (slightly lower than dupi); less conjunctivitis"><strong>Tralokinumab(Adbry)</strong>:特異 IL-13;EASI-75 ~50%(略低於 dupi);結膜炎較少</li>
<li data-zh="<strong>Lebrikizumab(Ebglyss)</strong>:IL-13 高親和;FDA 2024-09;Davis 2025 強建議" data-en="<strong>Lebrikizumab (Ebglyss)</strong>: high-affinity IL-13; FDA Sep 2024; Davis 2025 strong rec"><strong>Lebrikizumab(Ebglyss)</strong>:IL-13 高親和;FDA 2024-09;Davis 2025 強建議</li>
<li data-zh="<strong>Nemolizumab(Nemluvio)</strong>:阻 IL-31RA(癢專屬);第 1 週即顯著鎮癢;Davis 2025 強建議" data-en="<strong>Nemolizumab (Nemluvio)</strong>: anti–IL-31RA (itch-specific); significant itch relief by week 1; Davis 2025 strong rec"><strong>Nemolizumab(Nemluvio)</strong>:阻 IL-31RA(癢專屬);第 1 週即顯著鎮癢;Davis 2025 強建議</li>
</ul>
<h3 data-zh="口服 JAK 抑制劑(3 個)" data-en="Oral JAK inhibitors (3 agents)">口服 JAK 抑制劑(3 個)</h3>
<ul>
<li data-zh="<strong>Upadacitinib(Rinvoq)</strong>:JAK1;15 / 30 mg QD;EASI-75 第 16 週 70-80%(起效最快)" data-en="<strong>Upadacitinib (Rinvoq)</strong>: JAK1; 15 / 30 mg QD; EASI-75 ~70–80% (fastest onset)"><strong>Upadacitinib(Rinvoq)</strong>:JAK1;15 / 30 mg QD;EASI-75 第 16 週 70-80%(起效最快)</li>
<li data-zh="<strong>Abrocitinib(Cibinqo)</strong>:JAK1;100 / 200 mg QD;EASI-75 ~60-70%" data-en="<strong>Abrocitinib (Cibinqo)</strong>: JAK1; 100 / 200 mg QD; EASI-75 ~60–70%"><strong>Abrocitinib(Cibinqo)</strong>:JAK1;100 / 200 mg QD;EASI-75 ~60-70%</li>
<li data-zh="<strong>Baricitinib(Olumiant)</strong>:JAK1/2;歐洲核准但 FDA 未核准 AD" data-en="<strong>Baricitinib (Olumiant)</strong>: JAK1/2; EU approved, not FDA approved for AD"><strong>Baricitinib(Olumiant)</strong>:JAK1/2;歐洲核准但 FDA 未核准 AD</li>
<li data-zh="<strong>Black-box(class label)</strong>:MACE / 血栓 / 惡性腫瘤 / 嚴重感染。&gt; 50 歲且有 ≥ 1 心血管風險建議改 dupilumab。<strong>使用前篩檢</strong>:CBC / LFT / RFT / 脂質 / B/C 肝 / TB / HIV / 帶狀疱疹疫苗" data-en="<strong>Black-box (class label)</strong>: MACE / thrombosis / malignancy / serious infection. Prefer dupilumab if > 50 yr with ≥ 1 CV risk factor. <strong>Pre-Tx screening</strong>: CBC / LFT / RFT / lipids / HBV/HCV / TB / HIV / shingles vaccine"><strong>Black-box(class label)</strong>:MACE / 血栓 / 惡性腫瘤 / 嚴重感染。&gt; 50 歲且有 ≥ 1 心血管風險建議改 dupilumab。<strong>使用前篩檢</strong>:CBC / LFT / RFT / 脂質 / B/C 肝 / TB / HIV / 帶狀疱疹疫苗</li>
</ul>
<h3 data-zh="光療 + 傳統免疫調節劑" data-en="Phototherapy + conventional immunomodulators">光療 + 傳統免疫調節劑</h3>
<ul>
<li data-zh="<strong>NB-UVB(311 nm)</strong>:每週 2-3 次,平均 24 次達 EASI-75;懷孕、哺乳安全;主要限制是時間負擔" data-en="<strong>NB-UVB (311 nm)</strong>: 2–3×/wk; EASI-75 reached after avg 24 sessions; safe in pregnancy/lactation; main barrier is time burden"><strong>NB-UVB(311 nm)</strong>:每週 2-3 次,平均 24 次達 EASI-75;懷孕、哺乳安全;主要限制是時間負擔</li>
<li data-zh="<strong>Cyclosporine</strong>:3-5 mg/kg/d;短期(≤ 1 年)橋接到生物製劑首選;台灣健保事前審查門檻" data-en="<strong>Cyclosporine</strong>: 3–5 mg/kg/d; short-term (≤ 1 yr) bridge to biologic; Taiwan NHI prior-auth"><strong>Cyclosporine</strong>:3-5 mg/kg/d;短期(≤ 1 年)橋接到生物製劑首選;台灣健保事前審查門檻</li>
<li data-zh="<strong>MTX、Azathioprine、Mycophenolate</strong>:Davis 2024 conditional;在無法用生物製劑時考慮" data-en="<strong>MTX, azathioprine, mycophenolate</strong>: Davis 2024 conditional; consider when biologics unavailable"><strong>MTX、Azathioprine、Mycophenolate</strong>:Davis 2024 conditional;在無法用生物製劑時考慮</li>
<li data-zh="<strong>系統性類固醇</strong>:不建議長期;短期 bridge(&lt; 2 週)且必須有後續治療接力" data-en="<strong>Systemic corticosteroids</strong>: NOT recommended long-term; short bridges (< 2 wk) only with planned follow-on therapy"><strong>系統性類固醇</strong>:不建議長期;短期 bridge(&lt; 2 週)且必須有後續治療接力</li>
</ul>

<h2 id="related" data-zh="七、延伸閱讀" data-en="7. Related">七、延伸閱讀</h2>
<ul>
<li><a href='/blog/atopic-dermatitis-comorbidity' style='color:#0c5159;text-decoration:underline' data-zh="共病完整評估 — 過敏進展、心理、骨骼、心血管、感染" data-en="AD Comorbidity Evaluation">共病完整評估 — 過敏進展、心理、骨骼、心血管、感染</a></li>
<li><a href='/blog/eczema-myths' style='color:#0c5159;text-decoration:underline' data-zh="異膚 6 大迷思 — 含類固醇恐懼症完整澄清" data-en="6 AD Myths — including steroid phobia">異膚 6 大迷思 — 含類固醇恐懼症完整澄清</a></li>
<li><a href='/blog/pediatric-eczema' style='color:#0c5159;text-decoration:underline' data-zh="嬰幼兒 / 兒童異膚" data-en="Pediatric AD">嬰幼兒 / 兒童異膚</a></li>
</ul>

<h2 id="references" data-zh="參考資料" data-en="References">參考資料</h2>
<ol style="font-size:13px;line-height:1.8">
<li>Hanifin JM, Rajka G. <em>Diagnostic features of atopic dermatitis.</em> Acta Derm Venereol Suppl. 1980;92:44-47.</li>
<li>Williams HC, et al. <em>U.K. Working Party diagnostic criteria.</em> Br J Dermatol. 1994;131:383-396.</li>
<li>Sidbury R, et al. <em>AAD guidelines: topical therapies.</em> J Am Acad Dermatol. 2023;89(1):e1-e20.</li>
<li>Davis DMR, et al. <em>AAD guidelines: phototherapy and systemic therapies.</em> J Am Acad Dermatol. 2024;90(2):e43-e56.</li>
<li>Davis DMR, et al. <em>2025 AAD focused update on AD topical and systemic therapies.</em> J Am Acad Dermatol. 2025;93(3):745.e1-e7.</li>
<li>Simpson EL, et al. <em>Two phase 3 trials of dupilumab (SOLO 1, SOLO 2).</em> N Engl J Med. 2016;375:2335-2348.</li>
<li>Kabashima K, et al. <em>Nemolizumab for severe pruritus in AD (ARCADIA).</em> Lancet. 2024;404:1571-1582.</li>
<li>Hanifin JM, et al. <em>The Eczema Area and Severity Index.</em> Exp Dermatol. 2001;10:11-18.</li>
</ol>
</article>'''


def main():
    # 1. Replace overview body with merged content
    overview_path = os.path.join(ROOT, 'blog', 'atopic-dermatitis-overview.html')
    with open(overview_path, 'r', encoding='utf-8') as f:
        src = f.read()
    new = replace_article_body(src, MERGED_OVERVIEW)
    if new:
        with open(overview_path, 'w', encoding='utf-8') as f:
            f.write(new)
        print(f'  ✓ Merged overview: {len(src)} -> {len(new)} bytes')
    else:
        print('  ✗ Failed to replace overview body')

    # 2. Update vercel.json with redirects
    vp = os.path.join(ROOT, 'vercel.json')
    with open(vp, 'r', encoding='utf-8') as f:
        vj = json.load(f)
    redirects = vj.get('redirects', [])
    new_redirects = [
        {'source': '/blog/atopic-dermatitis-topical', 'destination': '/blog/atopic-dermatitis-overview', 'permanent': True},
        {'source': '/blog/atopic-dermatitis-systemic', 'destination': '/blog/atopic-dermatitis-overview', 'permanent': True},
        {'source': '/en/blog/atopic-dermatitis-topical', 'destination': '/en/blog/atopic-dermatitis-overview', 'permanent': True},
        {'source': '/en/blog/atopic-dermatitis-systemic', 'destination': '/en/blog/atopic-dermatitis-overview', 'permanent': True},
    ]
    existing_sources = {r.get('source') for r in redirects}
    for r in new_redirects:
        if r['source'] not in existing_sources:
            redirects.append(r)
    vj['redirects'] = redirects
    with open(vp, 'w', encoding='utf-8') as f:
        json.dump(vj, f, ensure_ascii=False, indent=2)
    print(f'  ✓ Added {len(new_redirects)} redirects to vercel.json')

    # 3. Update DN.ARTICLES + TAG_GROUPS in blog-shared.js
    bsp = os.path.join(ROOT, 'blog', 'blog-shared.js')
    with open(bsp, 'r', encoding='utf-8') as f:
        bs = f.read()
    # Remove topical + systemic entries from DN.ARTICLES
    bs0 = bs
    bs = re.sub(r"\s*\{\s*slug:'atopic-dermatitis-systemic'[^}]*\},?\n?", '', bs)
    bs = re.sub(r"\s*\{\s*slug:'atopic-dermatitis-topical'[^}]*\},?\n?", '', bs)
    # Update overview entry title to reflect merged content
    bs = re.sub(
        r"slug:'atopic-dermatitis-overview',\s*title:'[^']+',",
        "slug:'atopic-dermatitis-overview', title:'異位性皮膚炎完整治療指引 — 從病態生理到 4 個生物製劑 + 7 級類固醇',",
        bs
    )
    # Update TAG_GROUPS — remove the 2 slugs from any list
    bs = re.sub(r",\s*'atopic-dermatitis-topical'", '', bs)
    bs = re.sub(r"'atopic-dermatitis-topical'\s*,?", '', bs)
    bs = re.sub(r",\s*'atopic-dermatitis-systemic'", '', bs)
    bs = re.sub(r"'atopic-dermatitis-systemic'\s*,?", '', bs)
    if bs != bs0:
        with open(bsp, 'w', encoding='utf-8') as f:
            f.write(bs)
        print(f'  ✓ Removed topical + systemic from DN.ARTICLES + TAG_GROUPS')

    print('\nDone. Run regen + minify next.')


if __name__ == '__main__':
    main()
