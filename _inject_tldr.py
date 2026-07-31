#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inject a TL;DR "一句話結論" direct-answer block under each article H1.

GEO/AEO lever: AI answer engines (AI Overviews, Perplexity, ChatGPT-search)
reward a short, extractable, plain-language answer near the top of the page,
and — unlike classic SERPs — do NOT gate on domain authority. The site's
speakable JSON-LD already lists `.dn-tldr` / `[data-speakable]` selectors, so
this block is picked up automatically once present.

Placement: immediately AFTER the first </h1>, BEFORE the disclaimer block.
Bilingual: <span data-en="..."> so the EN mirror swaps it at runtime.
Idempotent: replaces an existing .dn-tldr block, else inserts it.

⚠️ Medical content — the blurbs below are DRAFTS for physician review.
Usage:  python _inject_tldr.py            # dry-run (report only)
        python _inject_tldr.py --apply     # write changes (after review)
"""
import os, io, sys, re, html as _html

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.dirname(os.path.abspath(__file__))
APPLY = "--apply" in sys.argv

# slug -> {zh: 40-80 字 direct answer, en: concise English}
TLDR = {
    "acne-myths": {
        "zh": "痘痘的根因是毛孔角化、皮脂與痤瘡桿菌發炎,不是「沒洗乾淨」。擠痘、狂洗臉、戒巧克力都無法根治;真正有效的是外用 A 酸/酸類、必要時口服藥,並規律使用數週才見效。",
        "en": "Acne is driven by clogged pores, oil and C. acnes inflammation — not poor hygiene. Squeezing, over-washing or cutting chocolate won't cure it; topical retinoids/acids (plus oral meds when needed), used consistently for weeks, do.",
    },
    "isotretinoin-patient": {
        "zh": "口服 A 酸是目前對中重度痘痘最有效的治療,多數人完成療程後可長期緩解,部分仍可能復發。常見副作用是嘴唇與皮膚乾燥、可處理;重點是孕婦絕對禁用、需嚴格避孕並依醫囑定期追蹤。",
        "en": "Oral isotretinoin is the most effective treatment for moderate-to-severe acne, with lasting remission for most though some relapse. Dryness is the common, manageable side effect; it is absolutely contraindicated in pregnancy and needs strict contraception and monitoring.",
    },
    "topical-acids-patient": {
        "zh": "A 酸、A 醇、杜鵑花酸、果酸、水楊酸各有適應症與刺激性。新手從低濃度、隔天晚上開始,白天務必防曬;不必「越濃越好」,重點是建立耐受、持續使用。",
        "en": "Retinoids, retinol, azelaic, AHA and salicylic acid each have their use and irritancy. Start low-strength every other night and always use daytime sunscreen — 'stronger' isn't better; consistency is.",
    },
    "atopic-dermatitis-overview": {
        "zh": "異位性皮膚炎是慢性、會反覆的皮膚屏障與免疫問題,不會傳染,也不是「沒擦乳液」那麼簡單。治療核心是每天保濕+發作時外用類固醇/TCI;中重度可用生物製劑或 JAK,多能良好控制。",
        "en": "Atopic dermatitis is a chronic, relapsing skin-barrier + immune condition — not contagious and not just 'dry skin'. Daily moisturising plus topical steroids/TCI for flares controls most cases; biologics or JAK help moderate-to-severe disease.",
    },
    "sunscreen-myths": {
        "zh": "室內、陰天、冬天紫外線仍在,該防曬。SPF 不是越高越好,足量與補擦更重要;物理性與化學性防曬都有效,選一支你願意天天擦的才是好防曬。",
        "en": "UV reaches you indoors, on cloudy days and in winter, so wear sunscreen. Higher SPF isn't automatically better — applying enough and reapplying matters more. Both mineral and chemical filters work; the best is the one you'll use daily.",
    },
    "melasma-myths": {
        "zh": "肝斑是受荷爾蒙與紫外線影響的慢性色素問題,容易復發,無法「雷射一次根治」。治療靠嚴格防曬+外用美白藥(如三合一、傳明酸);雷射使用不當反而會反黑。",
        "en": "Melasma is a hormone- and UV-driven chronic pigment problem that recurs and can't be 'lasered away' in one go. Strict sun protection plus topical lighteners (triple-combination, tranexamic acid) are the mainstay; wrong laser settings can darken it.",
    },
    "hairloss-myths": {
        "zh": "戴帽子、洗頭、壓力通常不是雄性禿主因;雄性禿是基因加雄性荷爾蒙造成、會持續進展。有實證的是 minoxidil 與 finasteride,需持續使用,停藥會逐漸退回。",
        "en": "Hats, washing and stress aren't the main cause of male-pattern hair loss — it's genetic + hormonal and progressive. Minoxidil and finasteride are the evidence-based treatments and must be used continuously; stopping reverses gains.",
    },
    "psoriasis-myths": {
        "zh": "乾癬不是「癬」、不會傳染,是免疫造成的慢性發炎,可能合併關節炎與代謝疾病。雖不能根治,但外用藥、照光、口服與生物製劑能讓多數人皮膚接近清零。",
        "en": "Psoriasis is not 'ringworm' and not contagious — it's chronic immune-driven inflammation that can involve the joints and metabolic disease. It can't be cured, but topicals, phototherapy, oral and biologic drugs can clear most people's skin.",
    },
    "rosacea-myths": {
        "zh": "酒糟不是單純「過敏」或洗不乾淨,是以血管與發炎為主的慢性問題,會臉紅、長丘疹膿皰。治療要避開誘因(辣、酒、高溫)加上外用/口服藥;亂擦類固醇會惡化。",
        "en": "Rosacea isn't simple 'allergy' or poor washing — it's a chronic vascular + inflammatory condition causing flushing and bumps. Avoid triggers (spice, alcohol, heat) plus topical/oral therapy; misusing steroids makes it worse.",
    },
    "tinea-myths": {
        "zh": "香港腳、灰指甲是黴菌感染,不痛不癢也要治、且會傳染家人。擦藥常需數週至數月;灰指甲多需口服藥才會好,療程不足是最常見的復發原因。",
        "en": "Athlete's foot and nail fungus are fungal infections that need treatment even when painless, and they spread to family. Creams often take weeks-to-months; nail fungus usually needs oral medication, and under-treatment is the top cause of relapse.",
    },
    "alopecia-areata": {
        "zh": "圓禿是自體免疫攻擊毛囊造成的塊狀掉髮,不是壓力「嚇掉」的,多數會自行或在治療後重新長回。範圍大或反覆者,JAK 抑制劑是新的有效選擇。",
        "en": "Alopecia areata is autoimmune patchy hair loss — not 'scared off' by stress — and often regrows by itself or with treatment. For extensive or recurrent cases, JAK inhibitors are an effective new option.",
    },
    "vitiligo": {
        "zh": "白斑是自體免疫造成的色素脫失,不會傳染,可能合併甲狀腺等自體免疫疾病。早期治療(外用藥、照光、新藥 ruxolitinib)有機會復色,臉部與近期病灶效果較好。",
        "en": "Vitiligo is autoimmune loss of skin pigment, not contagious, and can accompany thyroid and other autoimmune disease. Early treatment (topicals, phototherapy, newer ruxolitinib) can repigment, working best on the face and recent lesions.",
    },

    # ── TD-01 batch, 2026-07-31 ────────────────────────────────────────
    # Every blurb below is written ONLY from what its own article already
    # says — no claim is introduced here that the page does not make. These
    # are still DRAFTS for physician review (D-01).
    #
    # perioral-dermatitis-guide and toenail-mechanical-disorders are
    # deliberately absent: both open with the physician's own
    # 「先講結論 / 30 秒重點」 section, so DOCTOR_SUMMARY_RE skips them and an
    # entry here could never apply.
    "acne-scar-treatment": {
        "zh": "痘疤要先分類再選療程:紅疤(PIE)平均 6-12 個月會自己淡,不必急著雷射;黑疤(PIH)最重要的是防曬。真正的凹疤才需要處置——冰鑿型用 TCA CROSS、廂車型用飛梭、滾動型用皮下分離,通常需要多次療程。",
        "en": "Acne scars need classifying before treating: red marks (PIE) usually fade on their own in 6-12 months, and brown marks (PIH) mainly need sun protection. Only true depressions call for procedures — TCA CROSS for ice-pick, fractional laser for boxcar, subcision for rolling — usually over several sessions.",
    },
    "actinic-keratosis-scc": {
        "zh": "日光性角化症是長期紫外線傷害造成的癌前病變,可能進展為鱗狀細胞癌。病灶多發時要做整片區域治療,而不是一顆一顆處理,因為整片日曬皮膚都已有亞臨床傷害;防曬是最實際的預防。",
        "en": "Actinic keratosis is a sun-damage precancer that can progress to squamous cell carcinoma. When lesions are multiple, treat the whole sun-damaged field rather than one spot at a time, because the surrounding skin already carries subclinical damage — and sun protection is the practical prevention.",
    },
    "atopic-dermatitis-special-populations": {
        "zh": "異位性皮膚炎不只是皮膚病,合併症要主動篩檢。嬰兒從出生起每天保濕可降低約 50% 發病率,在適當月齡引入花生與雞蛋有助預防食物過敏;懷孕、嬰幼兒與老年族群的用藥選擇各有不同。",
        "en": "Atopic dermatitis is more than a skin disease — its comorbidities should be screened for actively. Daily moisturising from birth cuts incidence by about half, and introducing peanut and egg at the right age helps prevent food allergy; treatment choices differ in pregnancy, infancy and old age.",
    },
    "atopic-dermatitis-systemic": {
        "zh": "外用治療控制不住時才升階到全身性治療。光療是合理的替代或橋接選項;生物製劑與 JAK 抑制劑在起效速度、給藥方式與監測需求上各有差異,台灣健保有給付條件,選藥要看病情與可近性。",
        "en": "Systemic therapy comes after topical treatment fails to control the disease. Phototherapy is a reasonable alternative or bridge; biologics and JAK inhibitors differ in onset, administration and monitoring, and with Taiwan's reimbursement criteria the choice depends on severity and access.",
    },
    "atopic-dermatitis-topical": {
        "zh": "外用治療的第一基石是每天保濕,量要夠(成人每週 250-500 g),劑型比品牌重要。急性期用適當強度的類固醇 7-14 天,穩定後改成每週兩次的主動維持;臉部與皺褶處可換成 TCI 等非類固醇藥。",
        "en": "Daily moisturising is the foundation — enough of it (250-500 g a week for an adult), with the base mattering more than the brand. Flares take an appropriately potent steroid for 7-14 days, then proactive twice-weekly maintenance, with non-steroidal options such as TCI for the face and folds.",
    },
    "biologics-overview": {
        "zh": "生物製劑與小分子標靶藥是精準阻斷特定發炎路徑,比傳統的廣泛免疫抑制更專一、副作用較輕,但價格高且多有健保給付條件。用藥前要完成共通篩檢,診斷不明時須先排除皮膚 T 細胞淋巴瘤。",
        "en": "Biologics and small-molecule targeted drugs block specific inflammatory pathways rather than suppressing immunity broadly — more selective and better tolerated, but costly and often subject to reimbursement criteria. Baseline screening comes first, and cutaneous T-cell lymphoma must be excluded when the diagnosis is unclear.",
    },
    "contact-dermatitis": {
        "zh": "接觸性皮膚炎分成過敏性(ACD)與刺激性(ICD),兩者處理方向不同。反覆發作或找不到原因時,貼膚試驗才能確認過敏原;治療核心是避開致病物質加上外用藥,職業暴露要一併評估。",
        "en": "Contact dermatitis is either allergic (ACD) or irritant (ICD), and the two are managed differently. When it keeps returning or the cause is unclear, patch testing is what identifies the allergen; treatment is avoidance plus topical therapy, with occupational exposure assessed alongside.",
    },
    "cutaneous-t-cell-lymphoma": {
        "zh": "蕈狀肉芽腫(MF)是最常見的皮膚 T 細胞淋巴瘤,早期病灶與濕疹、乾癬高度重疊,常需要反覆切片並依 ISCL 演算法評分才能確診。早期以皮膚導向治療為主,進展期才進入系統性治療。",
        "en": "Mycosis fungoides is the commonest cutaneous T-cell lymphoma, and early lesions overlap heavily with eczema and psoriasis, so diagnosis often takes repeat biopsies scored against the ISCL algorithm. Early stages are treated with skin-directed therapy; systemic treatment belongs to advanced disease.",
    },
    "dermatology-faq": {
        "zh": "收錄診間最常被問的 25 個問題:A 酸為什麼晚上擦、類固醇藥膏能連續擦多久、保養品順序、痘疤與雷射的期待值、孕期與哺乳期用藥等。多數問題的答案不在於挑哪個產品,而在用法、頻率與時間。",
        "en": "The 25 questions asked most often in clinic: why retinoids go on at night, how long a topical steroid can be used continuously, the order of skincare, what to expect from acne-scar and laser work, and medication in pregnancy and breastfeeding. Most answers turn on how and how long, not on which product.",
    },
    "epidermoid-cyst": {
        "zh": "粉瘤是皮下一個有完整囊袋的構造,把內容物擠出來囊袋還在,所以會再長、還可能發炎。輕度發炎可打稀釋類固醇消腫;要根本解決得在不發炎時把囊袋完整切除,健保有給付條件。",
        "en": "An epidermoid cyst is a sac beneath the skin, so squeezing the contents out leaves the sac behind — it refills and can become inflamed. Mild inflammation can be settled with a dilute steroid injection, but removing the sac intact once it is quiet is what stops it coming back.",
    },
    "hidradenitis-suppurativa": {
        "zh": "化膿性汗腺炎是毛囊阻塞加上免疫發炎的慢性病,不是衛生不好造成,也不會傳染。初次評估就應記錄 Hurley 分期並評估共病;中重度需要生物製劑,台灣健保目前給付 secukinumab。",
        "en": "Hidradenitis suppurativa is a chronic disease of follicular occlusion and immune inflammation — not poor hygiene, and not contagious. Hurley staging and comorbidity assessment belong at the first visit; moderate-to-severe disease needs a biologic, and Taiwan's NHI currently covers secukinumab.",
    },
    "isotretinoin-clinical": {
        "zh": "給臨床工作者的口服 A 酸整理:13-cis-RA 本身對 RAR 親和力低,療效大多來自體內轉為 ATRA 與其衍生物。內容涵蓋四大機轉、累積劑量與低劑量/間歇給藥的取捨、治療前後監測、副作用全光譜,以及致畸性與避孕規範細節。",
        "en": "A clinician's reference on oral isotretinoin: 13-cis-retinoic acid binds RAR weakly itself, and most of its effect follows isomerisation to ATRA and related metabolites. It covers the four mechanisms, cumulative versus low-dose and intermittent regimens, workup and monitoring, the full side-effect spectrum, and the specifics of teratogenicity and contraception.",
    },
    "laser-dermatology": {
        "zh": "雷射的原理是選擇性光熱解:不同波長被不同顯色團(黑色素、血紅素、水)吸收,把光能轉成熱能精準破壞目標。所以選雷射先問目標是色素、血管還是水、病灶在表皮或真皮、膚色分型為何,而不是比機器新舊。",
        "en": "Lasers work by selective photothermolysis: different wavelengths are absorbed by different chromophores — melanin, haemoglobin, water — turning light into heat at the target. Choosing one starts from whether the target is pigment, vessel or water, how deep the lesion sits and the patient's skin type, not from which machine is newest.",
    },
    "mpox-care": {
        "zh": "猴痘皮疹的特徵是界限清楚、常呈中央凹陷的病灶,依序經過五個階段,整個病程約 2-4 週。在所有病灶結痂脫落、新皮膚長好之前仍具傳染性;照護重點是避免搔抓摳破、溫和清潔,並預防續發細菌感染。",
        "en": "Mpox lesions are well-demarcated and often umbilicated, pass through five stages, and the illness runs about 2-4 weeks. It remains infectious until every lesion has crusted and new skin has formed; care centres on not scratching or picking, gentle cleansing, and preventing secondary bacterial infection.",
    },
    "nhi-derm-drugs": {
        "zh": "整理皮膚科常用藥的健保給付條件、劑量與療程,含乾癬生物製劑的 PASI 門檻與事前審查(PASS)、異膚全身性藥物、圓禿 JAK 抑制劑、慢性蕁麻疹 omalizumab 與化膿性汗腺炎用藥。規範會更新,實際以最新公告為準。",
        "en": "Reimbursement criteria, dosing and course length for the drugs used most in dermatology: PASI thresholds and prior authorisation for psoriasis biologics, systemic therapy for atopic dermatitis, JAK inhibitors for alopecia areata, omalizumab for chronic urticaria, and the hidradenitis suppurativa agents. Criteria change — the current announcement governs.",
    },
    "pediatric-eczema": {
        "zh": "嬰幼兒異位性皮膚炎靠臨床診斷,不需抽血或切片,但要先排除脂漏性皮膚炎、尿布疹、疥瘡等。照護核心是洗澡後保濕、依部位選類固醇強度,臉部可用 TCI;不建議常規做過敏原檢測,中重度自 6 個月起可考慮 dupilumab。",
        "en": "Eczema in infants is a clinical diagnosis — no blood test or biopsy — once seborrhoeic dermatitis, nappy rash, scabies and others are excluded. Care is moisturising after bathing and matching steroid potency to the site, with TCI an option on the face; routine allergy testing is not advised, and dupilumab can be considered from six months in moderate-to-severe disease.",
    },
    "prurigo-nodularis": {
        "zh": "結節性癢疹的核心是癢-抓循環:神經發炎與搔抓互相強化,形成頑固的結節。治療要同時止癢並打斷搔抓,並篩檢潛在共病;中重度已有 dupilumab、nemolizumab 等新選擇。",
        "en": "Prurigo nodularis is driven by the itch-scratch cycle, where neural inflammation and scratching reinforce each other into stubborn nodules. Treatment has to settle the itch and interrupt the scratching while screening for underlying comorbidity; dupilumab and nemolizumab are newer options in moderate-to-severe disease.",
    },
    "psoriasis-overview": {
        "zh": "乾癬是慢性、會復發的免疫介導發炎疾病,不只是皮膚問題,也不會傳染。主流機轉是 IL-23/Th17/IL-17 軸,現行生物製劑正是照這條路徑設計。分型與嚴重度決定治療強度,感染、壓力與某些藥物是常見誘發因子。",
        "en": "Psoriasis is a chronic, relapsing, immune-mediated inflammatory disease — not confined to the skin, and not contagious. The IL-23/Th17/IL-17 axis is the mainstream model and the one today's biologics were designed around; subtype and severity set treatment intensity, with infection, stress and certain drugs among the common triggers.",
    },
    "psoriasis-special-populations": {
        "zh": "乾癬要主動篩檢關節炎與心血管代謝等合併症,那是治療決策的一部分。懷孕期約半數病人會改善、產後六週內常見惡化;兒童乾癬、指甲乾癬與紅皮症型各有不同的評估與處置重點。",
        "en": "Psoriasis calls for active screening for arthritis and cardiometabolic comorbidity, which feeds directly into treatment choice. About half of patients improve during pregnancy and flares are common within six weeks of delivery; childhood, nail and erythrodermic psoriasis each need their own assessment.",
    },
    "psoriasis-systemic": {
        "zh": "中重度乾癬的全身性治療中,窄頻 UVB 是第一線光療,有效且可長期使用。口服藥與生物製劑各有適應症與監測需求;台灣健保對生物製劑有明確門檻與事前審查,治療目標與換藥時機建議事先講清楚。",
        "en": "For moderate-to-severe psoriasis, narrowband UVB is the first-line phototherapy — effective and usable long term. Oral agents and biologics each carry their own indications and monitoring; Taiwan's NHI sets explicit thresholds and prior authorisation for biologics, and treatment targets and switching points are worth agreeing in advance.",
    },
    "psoriasis-topical": {
        "zh": "輕度到中度乾癬以外用藥為主;即使已在用光療或生物製劑,外用藥仍是處理殘餘斑塊的輔助。外用類固醇是基石,常與維生素 D 衍生物合併或輪替;臉部、皺褶、頭皮與指甲等部位要另外選劑型與強度。",
        "en": "Mild-to-moderate psoriasis is managed topically, and topicals stay useful alongside phototherapy or a biologic for stubborn residual plaques. Topical steroids are the backbone, often combined or alternated with vitamin D analogues, while the face, folds, scalp and nails need their own vehicle and potency.",
    },
    "shingles-myths": {
        "zh": "帶狀皰疹是體內潛伏的水痘病毒再活化,得過水痘的人終生都可能發作,年輕人也會。繞一圈會死並不是事實,但錯過發疹後 72 小時的抗病毒黃金期,神經痛風險明顯上升;民俗療法沒有醫療效果,疫苗可降低發作與神經痛。",
        "en": "Shingles is reactivation of latent varicella virus, so anyone who has had chickenpox can develop it, young adults included. The belief that a rash encircling the body is fatal is untrue, but missing the 72-hour antiviral window clearly raises the risk of nerve pain; folk remedies do nothing, and vaccination lowers both episodes and neuralgia.",
    },
    "skin-biopsy-excision": {
        "zh": "切片是取組織送病理確診,切除是把病灶連同安全邊緣完整移除;實務上常用同一個梭形切口,差別在有沒有留足夠邊緣。所有切下來的組織都應送病理化驗,這是常規,也是避免漏診早期皮膚癌的關鍵。",
        "en": "A biopsy takes tissue for a pathological diagnosis; an excision removes the lesion together with a margin. In practice both use the same elliptical incision and differ only in whether an adequate margin is included — and everything removed goes to pathology, which is routine and is what keeps an early skin cancer from being missed.",
    },
    "skin-whitening-agents": {
        "zh": "美白成分各有機轉與適用情境:氫醌仍是黃金標準,三合一藥膏效果優於單用氫醌,傳明酸、杜鵑花酸、維他命 C、菸鹼醯胺與 A 酸各有角色。濃度不是越高越好,自行拉高濃度反而容易反黑,防曬是所有療程的前提。",
        "en": "Each brightening agent has its own mechanism and place: hydroquinone remains the gold standard, the triple-combination cream outperforms hydroquinone alone, and tranexamic acid, azelaic acid, vitamin C, niacinamide and retinoids each have a role. Higher strength is not better — pushing it invites rebound pigmentation — and sun protection underpins every regimen.",
    },
    "targeted-therapy-skin": {
        "zh": "標靶藥物(TKI)的皮膚副作用很常見:EGFR 抑制劑的痤瘡樣皮疹發生率達 50-90%,多在用藥 1-2 週出現、3-4 週達高峰。乾皮症、甲溝炎與手足皮膚反應也常見,臨床依 CTCAE 分級決定處置強度。",
        "en": "Skin toxicity from targeted therapy is common: acneiform rash affects 50-90% of patients on EGFR inhibitors, appearing within 1-2 weeks and peaking at 3-4. Xerosis, paronychia and hand-foot skin reaction are frequent too, and management is graded by CTCAE severity.",
    },
    "topical-acids-clinical": {
        "zh": "給臨床工作者的外用 retinoid 與酸類整理:前體需要幾個酵素轉換步驟決定其相對效力。內容逐一整理各代 retinoid、杜鵑花酸的雙重機轉,以及 AHA 與水楊酸(BHA)的差異與適用情境。",
        "en": "A clinician's reference on topical retinoids and acid actives: a precursor's relative potency follows how many enzymatic conversion steps it needs. It works through each retinoid generation in turn, azelaic acid's dual mechanism, and how AHAs differ from salicylic acid in use.",
    },
    "topical-steroids-guide": {
        "zh": "外用類固醇是皮膚科第一線藥,重點不在能不能用,而在強度、部位與用量是否正確。美國分 7 級,臉部與皺褶用弱效、厚皮部位用強效;用量以指尖單位(FTU)估算,穩定後可改週末療法,過度恐懼反而讓病情拖久。",
        "en": "Topical steroids are a first-line dermatology treatment, and the question is not whether to use one but at what potency, on which site, and in what quantity. The US system has seven classes — weaker on face and folds, stronger on thick skin — with the fingertip unit to gauge amount and weekend therapy once things settle; excessive fear of them tends to prolong the disease.",
    },
    "urticaria-myths": {
        "zh": "蕁麻疹不一定是吃到過敏原,除非每次發作都與同一種食物明確相關,否則忙著找凶手往往徒勞。慢性蕁麻疹是肥大細胞過度敏感,不代表免疫力差,也不會傳染;治療以抗組織胺為基礎,不夠時再往上加。",
        "en": "Hives are not necessarily a food allergy — unless every episode clearly follows the same food, hunting for a culprit is usually wasted effort. Chronic urticaria reflects oversensitive mast cells rather than a weak immune system, and it is not contagious; antihistamines are the base of treatment, stepped up when they are not enough.",
    },
    "warts-myths": {
        "zh": "病毒疣是 HPV 感染,放著不治會自體接種——抓癢、刮鬍、剪指甲會把病毒帶到旁邊皮膚,共用毛巾剃刀也會傳染家人。香蕉皮、大蒜、白醋沒有實證;含 17-40% 水楊酸的貼布或液劑依指示連用 8-12 週約有六到七成緩解率,冷凍與雷射通常都需要多次。",
        "en": "Warts are an HPV infection, and leaving them alone invites autoinoculation — scratching, shaving and nail-trimming spread them, and shared towels and razors pass them to family. Banana peel, garlic and vinegar have no evidence; 17-40% salicylic acid patches or solution used as directed for 8-12 weeks clear about 60-70%, and cryotherapy or laser usually needs several sessions.",
    },
}

DOCTOR_SUMMARY_RE = re.compile(r"(一句話結論|30 ?秒重點|重點摘要|快速結論)")


def box(zh: str, en: str) -> str:
    # Match the existing doctor-written TL;DR design (atopic-dermatitis-overview)
    # for visual consistency. The `.dn-tldr` class is already in the speakable
    # JSON-LD selector, so no data-speakable needed. data-zh/data-en feed the
    # bilingual runtime swap (inner text = zh source).
    style = ("background:#fefce8;border-left:4px solid #ca8a04;border-radius:0 10px 10px 0;"
             "padding:14px 18px;margin:18px 0;font-size:14px;line-height:1.85")
    # Escape so any future <, >, &, or quote in the text can't corrupt markup.
    zh_e = _html.escape(zh, quote=True)
    en_e = _html.escape(en, quote=True)
    return (f'<div class="dn-tldr" style="{style}">'
            f'<strong data-zh="一句話結論" data-en="TL;DR">一句話結論</strong>:'
            f'<span data-zh="{zh_e}" data-en="{en_e}">{zh_e}</span></div>')


def main():
    inserted, skipped, missing, authored = [], [], [], []
    for slug, t in TLDR.items():
        path = os.path.join(ROOT, "blog", f"{slug}.html")
        if not os.path.exists(path):
            missing.append(slug)
            continue
        src = open(path, encoding="utf-8").read()
        # NEVER overwrite an existing TL;DR (may be a richer doctor-written one).
        if 'class="dn-tldr"' in src:
            skipped.append(slug)
            continue
        # CODE_REVIEW TD-01 — 12 articles open with a conclusion the physician
        # wrote himself, as an H2 (「一句話結論」/「30 秒重點」/「重點摘要」).
        # Those are not .dn-tldr blocks, so the check above does not see them,
        # and adding a box would put a second summary directly above the first.
        # They are excluded from TLDR for that reason; this makes the exclusion
        # something the script enforces rather than something to remember.
        if DOCTOR_SUMMARY_RE.search(re.sub(r"<[^>]+>", " ", src)):
            authored.append(slug)
            continue
        m = re.search(r'</h1>', src)
        if not m:
            missing.append(slug + " (no </h1>)")
            continue
        new = src[:m.end()] + box(t["zh"], t["en"]) + src[m.end():]
        inserted.append(slug)
        if APPLY:
            open(path, "w", encoding="utf-8").write(new)

    print(("APPLIED" if APPLY else "DRY-RUN") + f" — TL;DR injection")
    print(f"  inserted: {len(inserted)}")
    for slug in inserted:
        print(f"     + blog/{slug}.html")
    if skipped:
        print(f"  skipped (already has TL;DR): {skipped}")
    if authored:
        print(f"  skipped (physician already wrote a summary section): {authored}")
    if missing:
        print(f"  MISSING: {missing}")


if __name__ == "__main__":
    main()
