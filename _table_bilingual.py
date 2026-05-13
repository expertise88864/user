"""Add data-zh + data-en to <td> / <th> cells with CJK in 4 bilingual articles."""
import re
import pathlib

FILES = [
    'blog/severe-scabies-treatment.html',
    'blog/dermatologic-oral-examination.html',
    'blog/perioral-dermatitis-guide.html',
    'blog/toenail-mechanical-disorders.html',
]

TR = {
    # severe-scabies
    "Day 0、7、14 各服用 1 次（與食物併服）": "One dose on Days 0, 7, 14 (with food)",
    "Day 0 與 Day 7 全身塗抹（頭到腳）": "Head-to-toe on Days 0 and 7",
    "每日使用": "Daily",
    "66 人": "66 patients",
    "0.64（0.25–1.67）—— 跨越 1，無統計顯著差異": "0.64 (0.25–1.67) — crosses 1, not statistically significant",
    "Amoxicillin 2 g 口服": "Amoxicillin 2 g oral",
    "Ampicillin 2 g 或 Cefazolin/Ceftriaxone 1 g 肌注/靜注": "Ampicillin 2 g or Cefazolin/Ceftriaxone 1 g IM/IV",
    "Cephalexin 2 g（曾過敏性休克、血管性水腫或蕁麻疹者禁用）；或 Azithromycin / Clarithromycin 500 mg；或 Doxycycline 100 mg": "Cephalexin 2 g (avoid if anaphylaxis / angioedema / urticaria history); or Azithromycin / Clarithromycin 500 mg; or Doxycycline 100 mg",
    "Cefazolin / Ceftriaxone 1 g（如非嚴重過敏）": "Cefazolin / Ceftriaxone 1 g (if no severe allergy)",

    # perioral-dermatitis
    "證據最強烈的誘發因子；包括異位性皮膚炎在用的藥膏、氣喘吸入劑、鼻噴劑、自行使用家人剩下的類固醇藥膏": "Strongest evidence trigger; includes atopic dermatitis topicals, asthma inhalers, nasal sprays, self-applied family steroid creams",
    "凡士林、油性封閉產品": "Petrolatum, oily occlusive products",
    "含礦油、petrolatum、paraffin 的厚重保養品": "Mineral oil, petrolatum, paraffin-containing heavy creams",
    "化妝品、保養品": "Cosmetics, skincare",
    "某些 cosmeceutical 成分可能誘發": "Certain cosmeceutical ingredients may trigger",
    "文獻有明確記載": "Documented in literature",
    "物理性刺激": "Physical irritants",
    "紫外線、熱、風、唾液（舔唇炎 lip-licking cheilitis）": "UV, heat, wind, saliva (lip-licking cheilitis)",
    "荷爾蒙因素": "Hormonal factors",
    "口服避孕藥、懷孕、經前": "Oral contraceptives, pregnancy, premenstrual",
    "物理性防曬（兒童）": "Physical sunscreen (in children)",
    "含氧化鋅、二氧化鈦的高 SPF 防曬乳曾在兒童被報告為誘發因子": "High-SPF zinc oxide / titanium dioxide sunscreens reported as triggers in children",
    "病灶外觀": "Lesion appearance",
    "群聚的紅色小丘疹、小膿皰（1-2 mm）；有時細小脫屑": "Clustered small red papules and pustules (1–2 mm); occasional fine scale",
    "分布": "Distribution",
    "自覺症狀": "Symptoms",
    "灼熱感、刺刺感、輕微癢；「不太癢但很煩、很醜」是典型描述": "Burning, stinging, mild itch; classically described as &quot;not very itchy but annoying and unsightly&quot;",
    "病程": "Course",
    "反覆，可能持續數月到數年；停掉誘發因子後多能改善": "Relapsing; can last months to years; usually improves after triggers are removed",
    "沒有粉刺（區分痘痘）；沒有顯著潮紅、毛細血管擴張（區分玫瑰斑）；通常沒有明顯苔癬化、廣泛乾燥（區分異位性皮膚炎）": "No comedones (vs acne); no prominent flushing or telangiectasia (vs rosacea); no marked lichenification or widespread dryness (vs atopic dermatitis)",
    "益膚康、膚麗、柔潔、潔諾": "Various Taiwan brands (e.g., Yi-Fu-Kang, Fu-Li, Rou-Jie, Jie-Nuo)",
    "第一線；POD 屬 off-label": "First line; off-label for POD",
    "醫立妥（Elidel）": "Elidel (pimecrolimus)",
    "健保限中重度 AD + 傳統治療失敗；多需自費": "NHI covers moderate–severe AD after standard therapy fails; usually out-of-pocket for POD",
    "第一線（實證最佳）；POD 屬 off-label": "First line (strongest evidence); off-label for POD",
    "普特皮（Protopic）": "Protopic (tacrolimus)",
    "同上": "Same as above",
    "舒利達（Soolantra）": "Soolantra (ivermectin cream)",
    "第二線；POD 屬 off-label": "Second line; off-label for POD",
    "處方調配 / 部分院內製劑": "Compounded prescription / some hospital formulations",
    "視院所": "Varies by facility",
    "兒童 / 孕婦首選之一": "Preferred option for children / pregnancy",
    "思麗安（Skinoren，僅 20% cream）": "Skinoren (azelaic acid 20% cream)",
    "處方自費為主": "Mostly out-of-pocket prescription",
    "第二線；對色素沉著有幫助": "Second line; helpful for pigmentation",
    "多種學名藥": "Multiple generics",
    "部分品項健保給付（適應症為痤瘡）": "Some products NHI-covered (acne indication)",
    "Sarecycline / 外用 roflumilast / 外用 ruxolitinib": "Sarecycline / topical roflumilast / topical ruxolitinib",
    "新興選項；目前無法在台灣取得": "Emerging options; currently unavailable in Taiwan",
    "50-100 mg 一天 1-2 次": "50–100 mg once or twice daily",
    "成人、非孕、&gt;8 歲；最常用": "Adults, non-pregnant, &gt; 8 years; most commonly used",
    "光敏感（注意防曬）、可能腸胃不適；服藥後 30 分鐘內不要躺": "Photosensitivity (use sunscreen), possible GI upset; don't lie down within 30 min of dosing",
    "不能用 doxycycline 者": "When doxycycline isn't suitable",
    "較少光敏感，但有罕見但嚴重副作用（藥物性肝炎、DRESS、假性腦瘤、色素沉著），謹慎使用": "Less photosensitivity, but rare serious effects (drug-induced hepatitis, DRESS, pseudotumor cerebri, pigmentation) — use cautiously",
    "500 mg 一天 2 次": "500 mg twice daily",
    "孕婦、哺乳、8 歲以下兒童": "Pregnancy, lactation, children &lt; 8 years",
    "腸胃不適；與多種藥物有交互作用": "GI upset; multiple drug interactions",
    "500 mg 一週 3 次（文獻劑量）": "500 mg three times weekly (literature dose)",
    "替代選項": "Alternative option",
    "個案資料為主": "Mostly case-report evidence",
    "Tetracycline（舊式）": "Tetracycline (older)",
    "250-500 mg 一天 2 次": "250–500 mg twice daily",
    "已較少使用": "Less commonly used now",
    "飯前 1 小時或飯後 2 小時，避免與牛奶、鈣鎂鋁同服": "1 hour before meals or 2 hours after; avoid with milk / calcium / magnesium / aluminum",
    "體重調整劑量": "Weight-adjusted dosing",
    "美國上市，新興選項": "Available in US; emerging option",
    "誘發因子": "Trigger",
    "說明": "Notes",
    "特徵": "Feature",
    "描述": "Description",
    "外用藥": "Topical drug",
    "台灣商品名（部分）": "Taiwan brand names (partial)",
    "健保 / 自費": "NHI / out-of-pocket",
    "對 POD 的角色": "Role in POD",
    "口服藥": "Oral drug",
    "劑量（成人）": "Dose (adult)",
    "適合對象": "Suitable population",
    "注意事項": "Cautions",

    # toenail-mechanical
    "甲板與甲床分離，遠端泛白": "Plate separates from bed, distal whitening",
    "反覆微創傷、鞋擠壓、不對稱步態（AGNUS）": "Repeated microtrauma, shoe pressure, asymmetric gait (AGNUS)",
    "甲下角質堆積，趾甲看起來黃厚": "Keratin buildup under bed; nail appears yellow and thick",
    "慢性摩擦、灰指甲合併": "Chronic friction, often with onychomycosis",
    "圓形痛點 + 血絲": "Round painful spot + blood streak",
    "上下擠壓 + 腳型異常（HV/HE/HR、槌狀趾）": "Vertical compression + foot deformity (HV/HE/HR, hammer toes)",
    "橫向凹溝（不深）": "Shallow transverse grooves",
    "創傷讓甲基質暫停產甲；推甲皮也會": "Trauma briefly halts matrix; aggressive cuticle pushing can also cause",
    "整片甲板與甲床分離脫離": "Entire plate separates from bed",
    "創傷完全停止甲基質產甲": "Trauma completely halts matrix",
    "甲板向近端嵌入甲褶；慢性甲溝炎、不長": "Plate embedded proximally into fold; chronic paronychia, no growth",
    "反覆微創傷、突然大力撞擊；超音波可確診": "Repeated microtrauma, sudden impact; confirmed by ultrasound",
    "甲板兩側向內捲，越遠端越彎": "Plate curls inward bilaterally, more so distally",
    "遠端趾骨變寬 ± 骨刺 ± 尖頭鞋": "Widened distal phalanx ± osteophyte ± pointed shoes",
    "甲緣戳進周圍肉，紅腫疼痛": "Nail edge pierces surrounding flesh, red and painful",
    "剪太圓、鞋太窄、糖尿病": "Rounded cutting, narrow shoes, diabetes",
    "趾甲下黑色 / 紅紫色": "Black or red-purple under nail",
    "壓砸傷、跑步、運動鞋不合腳": "Crush injury, running, ill-fitting athletic shoes",
    "縱向黑線，常在大拇趾內側或小趾外側": "Longitudinal dark line, often medial hallux or lateral fifth toe",
    "橫向擠壓刺激黑色素細胞": "Lateral squeeze stimulates melanocytes",
    "橫向白紋，壓不出血色": "Transverse white lines that don't blanch",
    "鞋頭反覆撞擊未剪短的趾甲": "Toe-box repeatedly strikes untrimmed nail",
    "甲床縮短，趾肉「鼓起來」": "Nail bed shortens, soft tissue rises up",
    "長期剝離未處理；甲剝離 = 預防 DNB 的關鍵": "Chronic untreated onycholysis; treating onycholysis is key to preventing DNB",
    "1 顆/天": "1 tablet daily",
    "肝功能監測；療程後 12個月內不得重複申請": "Monitor LFTs; no repeat NHI claim within 12 months of treatment",
    "2 顆/天（連續）或 pulse 4 顆/天 × 1 週、停 3 週 × 3-4 cycle": "2 tabs/day continuous, or pulse 4 tabs/day × 1 week / off 3 weeks × 3–4 cycles",
    "多種藥物交互作用（statin、抗心律不整等）；療程後限制同上": "Many drug interactions (statins, antiarrhythmics, etc.); same post-treatment NHI restriction",
    "每週 1-2 次": "1–2 times weekly",
    "自費；醫師藥師指示藥": "Out-of-pocket; pharmacist-directed product",
    "單獨使用治癒率較低（mild &lt; 50% 甲面積適用），常用作合併治療": "Lower cure as monotherapy (best for mild, &lt; 50% nail involvement); usually combined",
    "每天塗": "Apply daily",
    "自費": "Out-of-pocket",
    "Efinaconazole（更新型外用）": "Efinaconazole (newer topical)",
    "需確認來源（台灣可能尚未上市或全自費）": "Status to confirm (may not be marketed in Taiwan or fully out-of-pocket)",
    "對 &lt; 50% 甲面積適用": "Suitable for &lt; 50% nail involvement",
    "把整片或部分甲板拔掉": "Remove entire or part of the nail plate",
    "高（甲長回後常再嵌）": "High (often recurs after regrowth)",
    "有給付但點數低（295 點）": "NHI covered but low reimbursement (295 points)",
    "切除嵌入側 + 縫合": "Excise ingrown side + suture",
    "約 15%": "About 15%",
    "用酚把該側甲基質破壞": "Phenolize the affected matrix",
    "健保點數低，多數需自費": "Low NHI reimbursement; mostly out-of-pocket",
    "正甲器（Orthonyx braces）": "Orthonyx braces",
    "用鋼絲 / 塑膠夾矯正甲板捲曲": "Wire or plastic clip to correct curl",
    "適合輕度夾擊甲": "For mild pincer nail",
    "76% 有非特異性甲變化": "76% non-specific nail changes",
    "白甲、紅甲、縱向溝紋、囊腫性指甲變化（myxoid cyst 74.5% 合併甲變形）": "Leukonychia, red nail, longitudinal grooves, cystic nail changes (myxoid cyst with 74.5% nail deformity)",
    "62.3% 有甲變形（122 人 cohort）": "62.3% with nail deformity (122-patient cohort)",
    "縱向溝紋、甲板增厚變色、splinter hemorrhage、紅色 lunula；侵蝕性 RA OR 2.26": "Longitudinal grooves, plate thickening / discoloration, splinter hemorrhages, red lunula; erosive RA OR 2.26",
    "80% 有甲乾癬": "80% with nail psoriasis",
    "甲坑、油滴、splinter hemorrhage、甲板崩解；甲乾癬是 PsA 預測因子": "Pitting, oil drops, splinter hemorrhages, plate disintegration; nail psoriasis predicts PsA",
    "20-30% 有甲變化": "20–30% nail changes",
    "甲剝離、甲坑、甲下角化、甲溝膿皰": "Onycholysis, pitting, subungual hyperkeratosis, paronychial pustules",
    "變形類型": "Deformity type",
    "長相": "Appearance",
    "常見原因": "Common cause",
    "藥物": "Drug",
    "劑量": "Dose",
    "健保限制": "NHI restriction",
    "手術方式": "Surgical method",
    "原理": "Mechanism",
    "復發率": "Recurrence rate",
    "台灣健保": "Taiwan NHI",
    "關節疾病": "Joint disease",
    "盛行率": "Prevalence",
    "典型指甲變化": "Typical nail changes",
}


TD_TH_RE = re.compile(r'<(td|th)\b([^>]*)>([^<]*[一-鿿][^<]*)</\1>')


def patch(html: str) -> tuple[str, int, list[str]]:
    missing: list[str] = []
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        tag, attrs, content = m.group(1), m.group(2), m.group(3)
        stripped = content.strip()
        if 'data-en=' in attrs:
            return m.group(0)
        en = TR.get(stripped)
        if not en:
            if stripped not in missing:
                missing.append(stripped)
            return m.group(0)
        zh_esc = stripped.replace('"', '&quot;')
        new = f'<{tag}{attrs} data-zh="{zh_esc}" data-en="{en}">{content}</{tag}>'
        count += 1
        return new

    new_html = TD_TH_RE.sub(repl, html)
    return new_html, count, missing


def main() -> None:
    root = pathlib.Path(__file__).parent
    grand_missing: list[str] = []
    for rel in FILES:
        p = root / rel
        before = p.read_text(encoding='utf-8')
        after, n, missing = patch(before)
        if n:
            p.write_text(after, encoding='utf-8')
            print(f'{rel}: patched {n} cells')
        else:
            print(f'{rel}: no changes')
        for s in missing:
            if s not in grand_missing:
                grand_missing.append(s)
    if grand_missing:
        print('\nUntranslated:')
        for s in grand_missing:
            print(f'  {s!r}')
    else:
        print('\nAll table cells successfully bilingualized.')


if __name__ == '__main__':
    main()
