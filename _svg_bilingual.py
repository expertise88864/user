"""Add data-zh + data-en to every <text>...</text> SVG element containing CJK
in the four bilingual articles.

After this, DN.applyTextOnly() can swap SVG text in place when lang toggles.
"""
import re
import pathlib

FILES = [
    'blog/severe-scabies-treatment.html',
    'blog/dermatologic-oral-examination.html',
    'blog/perioral-dermatitis-guide.html',
    'blog/toenail-mechanical-disorders.html',
]

# Hand-written translations for every unique CJK SVG <text> across the 4 articles.
TR = {
    # severe-scabies SVGs
    "疥蟲生命週期與皮膚隧道": "Scabies life cycle & skin burrow",
    "皮膚剖面 · 隧道在角質層": "Skin cross-section · burrow in stratum corneum",
    "角質層": "Stratum corneum",
    "表皮": "Epidermis",
    "真皮": "Dermis",
    "卵": "Eggs",
    "雌蟲": "Adult female",
    "生命週期（總共 2-3 週）": "Life cycle (2–3 weeks total)",
    "雌蟲鑽入皮膚、開始挖隧道": "Female burrows into skin, starts tunneling",
    "每天產 2-3 顆卵": "Lays 2–3 eggs per day",
    "卵孵化成幼蟲": "Eggs hatch into larvae",
    "幼蟲 → 若蟲 → 成蟲": "Larva → nymph → adult",
    "交配 → 新雌蟲產卵": "Mating → new females lay eggs",
    "好發部位": "Predilection sites",
    "指縫、手腕屈側、腋窩、": "Finger webs, flexor wrists, axillae,",
    "腰、肚臍、生殖器、": "waist, umbilicus, genitals,",
    "腳踝、足底 · 嬰兒可": "ankles, soles · in infants also",
    "上頭皮與臉": "scalp and face",
    "💡 治療為何要 day 0、7、14？": "💡 Why dose on days 0, 7, 14?",
    "藥物殺成蟲，但殺不光蟲卵。": "The drug kills adults but not all eggs.",
    "7-14 天後新孵化的成蟲還要再殺一次。": "Adults that hatch 7–14 days later must be killed again.",
    "兩種嚴重疥瘡型態（衛教示意圖，非真實病例）": "Two types of severe scabies (educational schematic, not real patients)",
    "廣泛型疥瘡 Profuse": "Profuse scabies",
    "疥蟲擴散到不典型部位": "Mites spread to atypical sites",
    "特徵：": "Features:",
    "• 紅斑、脫屑、廣泛分佈": "• Erythematous, scaly, widespread",
    "• 連頭、頸、背、四肢都有": "• Involves scalp, neck, back, limbs",
    "• 嚴重時可發展成紅皮症": "• May progress to erythroderma",
    "結痂型疥瘡 Crusted": "Crusted scabies",
    "舊稱「挪威型」· 蟲數數百到數千": "Formerly &quot;Norwegian&quot; · hundreds to thousands of mites",
    "• 厚黃白色痂、像乾癬": "• Thick yellow-white crusts, psoriasiform",
    "• 痂內含數千隻疥蟲": "• Each crust harbors thousands of mites",
    "• 極度傳染 · 多見免疫低下": "• Highly contagious · immunocompromised",
    "嚴重疥瘡標準治療時程": "Severe scabies standard treatment timeline",
    "ivermectin 口服": "Oral ivermectin",
    "全身塗抹": "Head-to-toe apply",
    "第二次塗抹": "Second application",
    "最後一次口服": "Final oral dose",
    "皮膚刮片": "Skin scraping",
    "或皮膚鏡": "or dermoscopy",
    "複查疥蟲": "Re-check for mites",
    "臨床判定": "Clinical assessment",
    "治癒": "Cure",
    "與否": "or not",
    "每日：保濕乳膏全身塗抹": "Daily: full-body emollient",
    "• ivermectin 隨餐服用（200 μg/kg 體重 × 體重 kg）": "• Ivermectin with food (200 μg/kg × body weight in kg)",
    "• permethrin 5% 從脖子到腳趾全身塗，過夜 ≥ 8 小時，早上洗掉": "• 5% permethrin from neck to toes, leave on ≥ 8 hours overnight, wash off in morning",
    "• 老人、嬰兒、結痂型：含頭皮、臉、耳後也要塗": "• Elderly / infants / crusted: include scalp, face, behind ears",
    "• 結痂型：可加 5% 水楊酸軟膏軟化痂皮、提高 permethrin 滲透": "• Crusted: add 5% salicylic acid ointment to soften crusts and improve permethrin penetration",

    # dermatologic-oral-examination SVGs
    "口腔黏膜三大分型 — 為什麼疾病有它的好發位置": "Three types of oral mucosa — why diseases have their preferred locations",
    "硬顎 + 上下牙齦": "Hard palate + upper / lower gingiva",
    "咀嚼性黏膜（角化）": "Masticatory mucosa (keratinized)",
    "承受咀嚼力 · 像手掌厚皮": "Bears chewing force · like thick palm skin",
    "頰黏膜": "Buccal mucosa",
    "鬆軟（非角化）": "Soft / loose (non-keratinized)",
    "軟顎 · 舌腹 · 口底": "Soft palate · ventral tongue · floor of mouth",
    "鬆軟（非角化）· 靈活伸縮": "Soft / loose (non-keratinized) · flexible",
    "舌背 + 唇紅": "Dorsal tongue + vermilion lip",
    "特化黏膜 · 部分角化": "Specialized mucosa · partially keratinized",
    "● 復發性口瘡好發：鬆軟黏膜（頰、唇內、舌腹）": "● Recurrent aphthous ulcers favor soft mucosa (cheek, labial, ventral tongue)",
    "● 口腔扁平苔癬好發：頰黏膜雙側對稱、舌側、牙齦": "● Oral lichen planus favors bilateral buccal mucosa, lateral tongue, gingiva",
    "● 白斑、扁平苔癬萎縮型：可能跨多區，需切片": "● Leukoplakia & atrophic lichen planus may span regions — biopsy required",
    "● 光線性唇炎、唇癌：下唇唇紅（特化）": "● Actinic cheilitis & lip cancer: lower vermilion (specialized)",
    "6 大屬於皮膚科的口腔病變（示意圖，非真實病例）": "6 oral lesions in dermatology's scope (schematic, not real patients)",
    "① 口腔扁平苔癬": "① Oral lichen planus",
    "白色蕾絲狀紋路": "White lacy lines",
    "② 復發性口瘡（嘴破）": "② Recurrent aphthous ulcer",
    "圓形邊緣紅 + 黃白底": "Round red border + yellow-white base",
    "③ 口腔白斑（癌前病變）": "③ Oral leukoplakia (precancer)",
    "均勻白斑 · 不可擦掉": "Uniform white patch · doesn't wipe off",
    "④ 類天疱瘡 / 天疱瘡": "④ Mucous membrane pemphigoid / pemphigus",
    "牙齦剝離 · 血皰 · 易破": "Desquamative gingivitis · blisters · fragile",
    "⑤ 光線性唇炎": "⑤ Actinic cheilitis",
    "下唇粗糙 · 邊緣模糊": "Rough lower lip · blurred vermilion border",
    "⑥ 口腔色素斑": "⑥ Oral pigmented lesion",
    "需區分良性 vs 黑色素瘤": "Differentiate benign vs melanoma",
    "① OLP：自體免疫，常合併皮膚扁平苔癬（紫色丘疹）、頭皮、指甲。": "① OLP: autoimmune; often coexists with cutaneous LP (purple papules), scalp, nails.",
    "② 復發性口瘡：常規 1–2 週癒合；反覆與 B12 / 葉酸缺乏、缺鐵、壓力相關。": "② RAS: heals in 1–2 weeks; recurrence linked to B12 / folate / iron deficiency, stress.",
    "③ 白斑：與檳榔、抽菸、喝酒高度相關，是癌前病變，需切片。": "③ Leukoplakia: strongly linked to betel / tobacco / alcohol; precancerous; biopsy needed.",
    "④ 類天疱瘡：『desquamative gingivitis』剝離性牙齦炎，皮膚也可能有水皰。": "④ Pemphigoid: presents as desquamative gingivitis; skin may also blister.",
    "⑤ 光線性唇炎：下唇被太陽曝曬導致，是唇癌的癌前病變。": "⑤ Actinic cheilitis: chronic UV on lower lip; precursor to lip cancer.",
    "⑥ 色素斑：多為良性 melanotic macule，但需排除黏膜黑色素瘤。": "⑥ Pigmented lesion: usually benign melanotic macule, but rule out mucosal melanoma.",
    "口腔症狀分流：誰看你的嘴巴？": "Oral symptom triage: which specialty?",
    "我嘴巴有狀況": "I have an oral problem",
    "是哪一類問題？": "Which type?",
    "蛀牙 · 牙齒痛": "Caries · tooth pain",
    "牙周病 · 補牙": "Periodontal disease · fillings",
    "植牙 · 矯正": "Implants · orthodontics",
    "→ 牙科": "→ Dentistry",
    "嘴破 &gt; 2 週": "Ulcer &gt; 2 weeks",
    "黏膜白斑 · 蕾絲紋": "Mucosal leukoplakia · lacy lines",
    "水皰 · 牙齦剝離": "Blisters · gum desquamation",
    "唇粗糙 · 黑斑": "Rough lips · pigmented patch",
    "→ 皮膚科": "→ Dermatology",
    "舌頭硬塊 · 口底硬塊": "Tongue mass · floor-of-mouth mass",
    "下顎 / 唾腺腫脹": "Jaw / salivary swelling",
    "張口困難 · 吞嚥困難": "Trismus · dysphagia",
    "頸部淋巴結腫": "Cervical lymphadenopathy",
    "→ 口腔外科 / 耳鼻喉科": "→ Oral surgery / ENT",
    "⚠️ 立即就醫（不分科別都先去急診或最近的口腔／皮膚科）": "⚠️ Seek prompt care (ED or nearest dermatology / oral specialist)",
    "• 嘴破超過 3 週不癒、變硬、邊緣捲起、出血": "• Ulcer not healing in 3 weeks, hardening, rolled edges, bleeding",
    "• 口腔內任何快速變大的黑斑或黑色結節": "• Any rapidly enlarging dark patch or pigmented nodule",
    "• 大面積水皰、牙齦剝離流血、無法進食": "• Extensive blisters, bleeding desquamative gingivitis, inability to eat",
    "• 張口受限 + 體重下降 + 頸部硬塊 + 同側耳痛": "• Trismus + weight loss + neck mass + ipsilateral ear pain",
    "• 嚼檳榔者：發現任何白斑、紅斑、混合斑 → 立即切片": "• Betel chewers: any white / red / mixed lesion → biopsy immediately",
    "口腔切片的兩種常用方法": "Two common oral biopsy techniques",
    "A. Punch（環形切片）": "A. Punch biopsy",
    "3–4 mm · 適合『典型病灶取代表區域』": "3–4 mm · ideal for representative sampling of typical lesions",
    "• 適合：扁平苔癬白色蕾絲取樣、白斑代表區": "• Use for: lichen planus white striae sampling, leukoplakia representative area",
    "• 不需縫線、癒合 1–2 週、不留疤": "• No sutures needed · heals in 1–2 weeks · no scarring",
    "• 限制：太小不足以判斷深部侵犯": "• Limitation: too small to assess deep invasion",
    "B. 15 號刀片（切除式切片）": "B. 15-blade excisional",
    "橢圓形切除 · 適合小病灶或唇部": "Elliptical excision · suits small lesions or lip",
    "• 適合：唇部小病灶、可疑黑色素瘤完整切除": "• Use for: small lip lesions, suspected melanoma complete excision",
    "• 沿解剖線切，唇紅切片用 4-0 可吸收線縫合": "• Follow anatomic lines · close vermilion with 4-0 absorbable suture",

    # perioral-dermatitis-guide SVGs
    "嘴唇紅緣": "Vermilion border",
    "明顯空白一圈": "Sparing of perioral skin",
    "口周（perioral）": "Perioral",
    "最常見區域": "Most common region",
    "鼻周（perinasal）": "Perinasal",
    "鼻翼兩側": "Alar grooves",
    "眼周（periorbital）": "Periorbital",
    "較少見": "Less common",
    "口周皮膚炎典型分布": "Typical distribution of perioral dermatitis",
    "紅色陰影 = 好發區；紅點 = 典型小丘疹/膿皰": "Red shading = favored areas; red dots = typical small papules/pustules",
    "口周皮膚炎四大致病機轉": "Four pathogenic mechanisms of perioral dermatitis",
    "四角共同作用，彼此放大循環": "Four corners interact and amplify each other",
    "口周": "Perioral",
    "皮膚炎": "Dermatitis",
    "① 皮膚屏障下降": "① Impaired skin barrier",
    "• 經皮水分流失↑（TEWL）": "• Increased TEWL",
    "• 角質層脂質失衡": "• Stratum corneum lipid imbalance",
    "• 外來物質容易滲入": "• Easier penetration of irritants",
    "② 發炎反應失調": "② Dysregulated inflammation",
    "• T 細胞免疫被活化": "• T-cell activation",
    "• 持續低度發炎": "• Sustained low-grade inflammation",
    "• NF-κB 訊號活化": "• NF-κB pathway activation",
    "③ 微生物失衡": "③ Microbial dysbiosis",
    "• 毛囊蟎蟲 (Demodex)": "• Demodex follicular mites",
    "• Fusobacterium 增加": "• Fusobacterium overgrowth",
    "• 正常菌叢多樣性↓": "• Reduced microbiome diversity",
    "④ 外來誘發因子": "④ External triggers",
    "• 類固醇（外用/吸入/口服）": "• Steroids (topical / inhaled / oral)",
    "• 封閉性保養品、化妝品": "• Occlusive skincare, cosmetics",
    "• 氟化牙膏": "• Fluoridated toothpaste",
    "• 紫外線、熱、唾液": "• UV, heat, saliva",
    "資料來源概念改編：Acevedo-Fontanez et al., J Am Acad Dermatol 2026;94:1483-92（Fig 1）": "Concept adapted from: Acevedo-Fontanez et al., J Am Acad Dermatol 2026;94:1483-92 (Fig 1)",
    "四種臉部紅疹的鑑別": "Differentiating four facial eruptions",
    "口周皮膚炎": "Perioral dermatitis",
    "好發：": "Sites:",
    "嘴、鼻、眼周": "Perioral, perinasal, periorbital",
    "病灶：": "Lesion:",
    "小紅疹、膿皰": "Small papules, pustules",
    "關鍵辨識：": "Key clue:",
    "嘴唇紅緣空白": "Vermilion sparing",
    "無粉刺": "No comedones",
    "族群：": "Population:",
    "20-45 歲女性": "Women 20–45",
    "誘發：": "Trigger:",
    "類固醇、油膏": "Steroids, occlusives",
    "痤瘡（痘痘）": "Acne",
    "全臉、胸背": "Whole face, chest, back",
    "粉刺、丘疹、囊腫": "Comedones, papules, cysts",
    "有黑/白頭粉刺": "Black/whiteheads present",
    "皮脂分泌旺": "Increased sebum",
    "青春期為主": "Adolescents mostly",
    "荷爾蒙、油性": "Hormonal, oily skin",
    "玫瑰斑（酒糟）": "Rosacea",
    "兩頰、鼻、額": "Cheeks, nose, forehead",
    "潮紅、微血管": "Flushing, telangiectasia",
    "持續性發紅": "Persistent erythema",
    "微血管擴張": "Telangiectasia",
    "30 歲以上": "Age 30+",
    "熱、酒、辣食": "Heat, alcohol, spicy",
    "異位性皮膚炎": "Atopic dermatitis",
    "嬰兒臉頰、屈側": "Infant cheeks, flexures",
    "乾燥、脫屑、苔癬化": "Dry, scaly, lichenified",
    "非常癢": "Severely itchy",
    "過敏家族史": "Atopy family history",
    "幼兒、有過敏體質": "Children, atopic background",
    "乾燥、過敏原": "Dryness, allergens",
    "本表為簡化辨識用，實際診斷請由皮膚專科醫師評估": "Simplified clue table — formal diagnosis by a dermatologist",
    "口周皮膚炎治療階梯": "Perioral dermatitis treatment ladder",
    "由下而上，依嚴重度逐步加上去": "Build from base up based on severity",
    "第 1 層 ‧ 所有人都要做": "Tier 1 · for everyone",
    "停（漸減）類固醇 · 停油膩保養 · 換無氟牙膏試 · 溫和洗臉 + 清爽保濕": "Taper / stop steroids · stop occlusive products · trial fluoride-free toothpaste · gentle cleansing + light moisturizer",
    "第 2 層 ‧ 輕中度（4-8 週）": "Tier 2 · mild–moderate (4–8 weeks)",
    "外用：metronidazole、tacrolimus / pimecrolimus、": "Topical: metronidazole, tacrolimus / pimecrolimus,",
    "第 3 層 ‧ 嚴重 / 反覆（4-8 週）": "Tier 3 · severe / recurrent (4–8 weeks)",
    "外用 + 口服 doxycycline / minocycline": "Topical + oral doxycycline / minocycline",
    "孕婦/&lt;8 歲：改用口服 erythromycin / azithromycin": "Pregnancy / age &lt; 8: oral erythromycin / azithromycin",
    "頑固型：ivermectin / isotretinoin": "Refractory: ivermectin / isotretinoin",
    "數據限於個案報告": "Evidence limited to case reports",
    "資料來源：Acevedo-Fontanez et al., J Am Acad Dermatol 2026;94:1483-92（Fig 2 概念改編）": "Adapted from Acevedo-Fontanez et al., J Am Acad Dermatol 2026;94:1483-92 (Fig 2)",

    # toenail-mechanical-disorders SVGs
    "趾甲構造（俯視 + 側面剖視）": "Toenail anatomy (top view + side cross-section)",
    "A. 俯視": "A. Top view",
    "近側甲褶": "Proximal nail fold",
    "半月（lunula）": "Lunula",
    "甲基質的可見部分": "Visible part of nail matrix",
    "甲板（nail plate, NP）": "Nail plate (NP)",
    "角蛋白構造，肉眼可見": "Keratin structure, visible",
    "側甲褶（lateral fold）": "Lateral nail fold",
    "嵌甲常從這裡開始": "Where ingrown nails often start",
    "游離邊緣": "Free edge",
    "B. 側面剖視": "B. Side cross-section",
    "遠端趾骨": "Distal phalanx",
    "甲基質": "Nail matrix",
    "甲板（NP）": "Nail plate (NP)",
    "手 ~3 mm/月、足 ~1 mm/月": "Finger ~3 mm/mo, toe ~1 mm/mo",
    "甲床（NB）": "Nail bed (NB)",
    "佔 75-85%；剝離後若太久": "Makes up 75–85%; if onycholysis persists",
    "會「消失」（DNB）": "becomes &quot;disappearing&quot; (DNB)",
    "關節炎可影響甲基質": "Arthritis can affect the matrix",
    "資料來源概念改編：Ricardo et al., J Am Acad Dermatol 2026;94:1493-503": "Concept adapted from Ricardo et al., J Am Acad Dermatol 2026;94:1493-503",
    "鞋子三方向擠壓 → 對應的趾甲變化": "Three directions of shoe compression → corresponding nail changes",
    "① 橫向擠壓（窄、尖頭鞋）": "① Lateral squeeze (narrow, pointed shoes)",
    "造成的腳變化": "Resulting foot changes",
    "• 拇指外翻、小趾內翻": "• Hallux valgus, fifth-toe inversion",
    "• 第二趾被擠到蓋到拇趾": "• Second toe overrides hallux",
    "• 大拇趾繭（bunion）": "• Bunion on hallux",
    "造成的趾甲問題": "Resulting nail problems",
    "• 內側拇趾甲繭、嵌甲": "• Medial hallux corn, ingrown nail",
    "• 外側拇趾甲剝離、夾擊甲": "• Lateral onycholysis, pincer nail",
    "• 拇趾內側 / 小趾外側黑線": "• Frictional melanonychia (medial hallux / lateral 5th)",
    "② 前後擠壓（鞋太小、沒綁鞋帶、高跟）": "② Front-back compression (tight shoes, no laces, heels)",
    "• 槌狀趾、爪狀趾": "• Hammer toes, claw toes",
    "• 鞋跟 &gt; 35 mm 重心前移": "• Heel &gt; 35 mm shifts weight forward",
    "• 趾尖反覆撞鞋頭": "• Toes repeatedly strike toe-box",
    "• 遠端裂甲、分層": "• Distal splitting, lamination",
    "• Beau's line、甲脫離": "• Beau's lines, onychomadesis",
    "• 白色橫紋、甲下血腫": "• Leukonychia, subungual hematoma",
    "③ 上下擠壓（鋼頭鞋、低頂鞋、騎車鞋）": "③ Vertical compression (steel-toe, low-top, cycling shoes)",
    "• 趾背骨突過度角化": "• Hyperkeratosis over dorsal toe prominence",
    "• 趾甲上方反覆摩擦": "• Repeated friction on nail dorsum",
    "• 騎車鞋族特別常見": "• Common in cyclists",
    "• 甲下繭（heloma）": "• Subungual heloma",
    "• 甲下角化、剝離": "• Subungual hyperkeratosis, onycholysis",
    "• 大拇趾甲變「磨亮」": "• Hallux nail becomes &quot;polished&quot;",
    "資料來源概念改編：Ricardo et al., JAAD 2026; Richert B. Trauma from footwear and pedal deformities, 2019": "Adapted from Ricardo et al., JAAD 2026; Richert B. Trauma from footwear and pedal deformities, 2019",
    "12 種趾甲機械性變形圖鑑": "Atlas of 12 mechanical toenail disorders",
    "1. 甲剝離 Onycholysis": "1. Onycholysis",
    "甲板從甲床浮起": "Nail plate lifts off bed",
    "遠端發白、空腔感": "Distal whitening, hollow feel",
    "2. 甲下角化 Subungual hyperkeratosis": "2. Subungual hyperkeratosis",
    "甲床下角質堆積": "Keratin buildup under bed",
    "趾甲看起來厚 + 黃": "Nail looks thick + yellow",
    "3. 甲下繭 Subungual heloma": "3. Subungual heloma",
    "圓形痛點 + 血絲": "Round painful spot + blood streak",
    "老年女性大拇趾居多": "Mostly elderly women, hallux",
    "4. Beau's 橫紋": "4. Beau's lines",
    "橫向凹溝": "Transverse grooves",
    "創傷讓甲基質暫停": "Trauma halts matrix briefly",
    "5. 甲脫落 Onychomadesis": "5. Onychomadesis",
    "甲板完全與甲床分離": "Full separation of plate from bed",
    "創傷暫停 → 完全停產": "Trauma halt → complete production stop",
    "6. Retronychia 倒嵌": "6. Retronychia",
    "甲板向近端嵌入": "Nail plate embedded proximally",
    "慢性甲溝炎、不長": "Chronic paronychia, no growth",
    "7. 夾擊甲 Pincer nail": "7. Pincer nail",
    "甲板兩側向內捲": "Nail plate curls inward bilaterally",
    "夾肉、疼痛、嵌甲": "Pinches flesh, painful, ingrown",
    "8. 嵌甲 Onychocryptosis": "8. Onychocryptosis (ingrown nail)",
    "甲緣戳進肉裡 + 發炎": "Nail edge pierces flesh + inflammation",
    "剪太圓、鞋太窄": "Rounded cutting, narrow shoes",
    "9. 甲下血腫 Hematoma": "9. Subungual hematoma",
    "瘀血累積": "Blood pooling",
    "壓砸傷、跑步": "Crush injury, running",
    "10. 摩擦性黑線": "10. Frictional melanonychia",
    "摩擦活化黑色素": "Friction activates melanocytes",
    "11. 白色橫紋": "11. Transverse leukonychia",
    "壓不出血色的白": "White lines that don't blanch",
    "12. 消失甲床 DNB": "12. Disappearing nail bed (DNB)",
    "長期剝離 → 軟組織頂上來": "Chronic onycholysis → soft tissue rises up",
    "資料來源：Ricardo et al., J Am Acad Dermatol 2026;94:1493-503（12 種變形 + 解釋）": "Source: Ricardo et al., J Am Acad Dermatol 2026;94:1493-503 (12 types + explanations)",
    "4 種常見腳型異常": "4 common foot deformities",
    "Morton's toe（希臘腳）": "Morton's toe (Greek foot)",
    "第二趾比大拇趾長": "Second toe longer than hallux",
    "盛行率 2.95-35.3%": "Prevalence 2.95–35.3%",
    "第二趾受擠壓 → 甲下角化、剝離、Beau's": "Second toe compressed → subungual hyperkeratosis, onycholysis, Beau's lines",
    "拇指外翻 Hallux valgus": "Hallux valgus",
    "大拇趾向外側偏；繭、第二趾重疊": "Hallux deviates laterally; corns, second-toe overlap",
    "盛行率 23-36%（女性多）": "Prevalence 23–36% (mostly women)",
    "大拇趾甲增厚、外側剝離；像灰指甲": "Hallux nail thickens, lateral onycholysis; mimics onychomycosis",
    "扁平足 Flat foot": "Flat foot",
    "足弓塌陷；糖尿病人 71.2% 合併": "Arch collapse; 71.2% of diabetics affected",
    "弓垮、整足貼地": "Arch drops, whole sole touches ground",
    "甲下角化、剝離；糖尿病潰瘍風險↑": "Subungual hyperkeratosis, onycholysis; increases diabetic ulcer risk",
    "開張足 Splayfoot": "Splayfoot",
    "蹠骨頭向兩側分開、變寬": "Metatarsal heads splay apart, foot widens",
    "大拇趾向內、小趾向外；甲側面磨痛": "Hallux medial, fifth toe lateral; painful nail-edge friction",
    "資料來源：Ricardo et al., JAAD 2026 Table II": "Source: Ricardo et al., JAAD 2026 Table II",
}


# Regex: <text ...>CONTENT</text> — capture attrs and content separately.
# We only modify if content contains CJK and we have a translation.
TEXT_RE = re.compile(r'<text\b([^>]*)>([^<]*)</text>')
CJK_RE = re.compile(r'[一-鿿]')


def has_data_zh(attrs: str) -> bool:
    return 'data-zh=' in attrs


def patch(html: str) -> tuple[str, int, list[str]]:
    missing = []
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        attrs, content = m.group(1), m.group(2)
        stripped = content.strip()
        if not CJK_RE.search(content):
            return m.group(0)
        if has_data_zh(attrs):
            return m.group(0)
        en = TR.get(stripped)
        if not en:
            if stripped not in missing:
                missing.append(stripped)
            return m.group(0)
        # Build the augmented opening tag.
        zh_esc = stripped.replace('"', '&quot;')
        en_esc = en.replace('"', '&quot;') if '&quot;' not in en else en
        new_open = f'<text{attrs} data-zh="{zh_esc}" data-en="{en_esc}">'
        count += 1
        return new_open + content + '</text>'

    new_html = TEXT_RE.sub(repl, html)
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
            print(f'{rel}: patched {n} <text> elements')
        else:
            print(f'{rel}: no changes')
        for s in missing:
            if s not in grand_missing:
                grand_missing.append(s)
    if grand_missing:
        print('\nUntranslated strings (add to TR dict and re-run):')
        for s in grand_missing:
            print(f'  {s!r}')
    else:
        print('\nAll SVG CJK text successfully bilingualized.')


if __name__ == '__main__':
    main()
