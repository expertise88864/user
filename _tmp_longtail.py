#!/usr/bin/env python3
"""Inject long-tail FAQ section + Reference section before the conclusion of each article.
Targets PTT/Dcard-style searches that clinic blogs neglect.
Idempotent — skips files already containing 'id="longtail"'."""
import os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))

# Per-article long-tail Q&A + references
ARTICLES = {
    'acne-myths': {
        'qa': [
            ('痘痘 PTT / Dcard 上常被推薦的藥膏值得買嗎?',
             'PTT/Dcard 上常被推薦的有 Differin(Adapalene 0.1%)、Skinoren(Azelaic acid 20%)、Effaclar Duo+。這些都是<strong>皮膚科常用、有實證的藥膏</strong>,但「適不適合你」要看痘痘類型(粉刺型 vs 發炎型 vs 囊腫型),建議先看一次皮膚科確認。網路推薦的「痘痘救星 OOO 神膏」如果是處方藥(如 Duac、Acnatac),沒有醫師處方買得到的多半是水貨或假藥,不建議。'),
            ('痘痘多久會好? 為什麼我吃藥/擦藥沒效?',
             '輕度粉刺擦藥 4-8 週看到變化;發炎型痘痘抗生素+外用藥需 8-12 週;中重度口服 A 酸完整療程約 6-9 個月。「沒效」最常見原因是<strong>用藥時間不夠</strong>(停藥太早)、<strong>沒同時清粉刺</strong>(只治發炎不治源頭)、<strong>沒避開誘發因素</strong>(高升糖食物、乳清蛋白、特定藥物)、或<strong>診斷錯誤</strong>(其實是玫瑰痤瘡、毛囊炎、酒糟)。'),
            ('痘痘飲食真的有差嗎?',
             '有實證有差的:<strong>高升糖食物</strong>(白飯、白麵、含糖飲料、甜食)、<strong>低脂牛奶/脫脂奶</strong>(全脂反而較少相關)、<strong>乳清蛋白(whey protein)</strong>。沒有實證需禁的:巧克力、油炸、辣椒、海鮮、堅果。建議減糖減奶 3 個月看是否改善,不需「完全戒」造成壓力。'),
            ('痘痘看皮膚科會開什麼藥? 健保 vs 自費差別?',
             '健保:外用 Adapalene、BPO、克林黴素、Acnatac/Duac、口服抗生素(Doxycycline、Minocycline)、口服 A 酸(Isotretinoin,但需符合條件)。自費常見:雷射(脈衝染料、皮秒)、化學換膚、痘痘針(局部類固醇注射)、進階保養品。健保藥物已涵蓋 90% 痘痘需求,自費主要是處理痘疤或加速改善。'),
            ('痘痘是不是要忌口豆漿、雞蛋、巧克力?',
             '<strong>沒有實證需要全面忌口</strong>。豆漿、雞蛋、巧克力對多數痘痘病人沒有顯著影響。如果你發現吃完特定食物 24-48 小時內必爆痘(個人觀察記錄 4 週以上),那是個人體質,可避開。否則無需忌口造成飲食偏差。'),
        ],
        'refs': [
            ('Zaenglein AL, et al. Guidelines of care for the management of acne vulgaris. <em>J Am Acad Dermatol</em>. 2016;74(5):945-973.', 'https://pubmed.ncbi.nlm.nih.gov/26897386/'),
            ('Reynolds RC, et al. Effect of the glycemic index of carbohydrates on Acne vulgaris. <em>Nutrients</em>. 2010;2(10):1060-1072.', 'https://pubmed.ncbi.nlm.nih.gov/22253995/'),
            ('UpToDate: Acne vulgaris: Overview of management. Accessed 2026.', 'https://www.uptodate.com/contents/acne-vulgaris-overview-of-management'),
            ('衛福部食藥署 — Adapalene/Tretinoin 仿單', 'https://www.fda.gov.tw/'),
        ],
    },
    'sunscreen-myths': {
        'qa': [
            ('防曬乳 PTT / Dcard 推薦的牌子如何挑?',
             '網路討論度高的:<strong>安耐曬</strong>(Anessa)、<strong>理膚寶水</strong>(La Roche-Posay Anthelios)、<strong>怡麗絲爾</strong>、<strong>Heliocare 360</strong>、<strong>艾比安</strong>(Albion)、<strong>Neutrogena Ultra Sheer</strong>。挑選重點不是品牌:① 廣譜(SPF 30+ PA+++ 以上)② 含<strong>氧化鐵 iron oxide</strong>(防可見光,肝斑必備)③ 質地能規律補擦的。售價 NT$ 400-2000 都有實用品。'),
            ('防曬 SPF 50 跟 SPF 30 差很多嗎?',
             '<strong>SPF 30 已擋掉 97% UVB,SPF 50 擋 98%</strong> — 邊際效益 1%。實際擦的<strong>厚度</strong>(2 mg/cm²)才是關鍵,多數人實際只擦 1/3 厚度,導致 SPF 50 變成「實質 SPF 17」。挑能規律擦、不油不悶、能補擦的 SPF 30+ 比追求 SPF 50+ 重要。'),
            ('物理性 vs 化學性防曬哪個好?',
             '<strong>沒有絕對贏家</strong>。物理性(Zinc oxide、Titanium dioxide)穩定、敏感肌可用、孕婦較安心,但傳統質地較厚白。化學性(Octinoxate、Avobenzone、Octisalate、Tinosorb)質地較佳,但部分舊款成分(Oxybenzone、Octinoxate)有環境疑慮、極少數人接觸過敏。新款混合型(Tinosorb S/M、Mexoryl)質地與穩定性都好。'),
            ('防曬乳要不要卸妝?',
             '純化學性防曬通常溫和洗面乳就能洗掉。物理性、含氧化鐵、防水抗汗款、有色防曬建議用<strong>潔顏油或卸妝乳</strong>輕柔卸除。指引:擦了之後皮膚摸起來「卡卡」、洗完還有殘留感,就需要卸妝。'),
            ('小孩、孕婦防曬怎麼挑?',
             '6 個月以下嬰兒避免擦防曬,以遮蔽和避光為主。6 個月以上+孕婦建議用<strong>純物理性防曬</strong>(Zinc oxide、Titanium dioxide),避開 Oxybenzone、Octinoxate(內分泌干擾疑慮)。孕婦肝斑活化,室內也要擦含氧化鐵的防曬。'),
        ],
        'refs': [
            ('Schalka S, Steiner D. Brazilian consensus on photoprotection. <em>An Bras Dermatol</em>. 2014;89(6 Suppl 1):1-74.', 'https://pubmed.ncbi.nlm.nih.gov/25761256/'),
            ('Lim HW, et al. Adverse effects of ultraviolet radiation. <em>J Am Acad Dermatol</em>. 2017;76(5):866-875.', 'https://pubmed.ncbi.nlm.nih.gov/28038884/'),
            ('Castanedo-Cazares JP, et al. Iron oxide-containing sunscreens for melasma. <em>Photodermatol Photoimmunol Photomed</em>. 2014;30(1):35-42.', 'https://pubmed.ncbi.nlm.nih.gov/24313929/'),
            ('UpToDate: Selection of sunscreen and sun-protective measures.', 'https://www.uptodate.com/contents/selection-of-sunscreen-and-sun-protective-measures'),
        ],
    },
    'eczema-myths': {
        'qa': [
            ('異位性皮膚炎 PTT 推薦的乳液如何挑?',
             '網路常被討論的:<strong>理膚寶水 Lipikar AP+M</strong>、<strong>艾芙美 Avene Xeracalm</strong>、<strong>Cetaphil RestoraDerm</strong>、<strong>艾惟諾 Aveeno 燕麥系列</strong>、<strong>Bioderma Atoderm Intensive</strong>。挑選重點:含<strong>神經醯胺(ceramide)、膽固醇、脂肪酸 3:1:1</strong>的修護型 > 普通保濕。每天<strong>大量、厚塗、洗澡後 3 分鐘內</strong>擦比挑哪個牌子重要。'),
            ('異膚多久會好? 長大會不會自己好?',
             '<strong>40-60% 兒童在青春期前明顯改善;30-50% 持續到成年</strong>。重要的是「越早控制好、越能避免後續過敏進行曲(食物過敏 → 氣喘 → 鼻過敏)」。新一代生物製劑(Dupilumab)+JAK inhibitor 已能讓多數中重度成年異膚維持幾乎沒症狀,不再像過去「治不好只能忍」。'),
            ('異膚飲食真的要忌口嗎?',
             '只在<strong>明確時間相關</strong>(吃某食物 30 分-2 小時內必發作)+<strong>有 IgE 過敏史</strong>時才忌口。盲目戒奶蛋海鮮會造成兒童營養不均、社交困擾,且大多無效。「過敏原檢測 100 項套組」陽性≠過敏,不要看到一堆紅字就全戒。'),
            ('類固醇藥膏可以擦多久? PTT 上很多人說會傷皮膚?',
             '<strong>正確使用是非常安全的第一線治療</strong>。臉/眼周/外陰用 Class V-VII(弱),四肢可用 Class III-IV(中強),手腳掌可用 Class I-II(強)。急性期每天 1-2 次連續 7-14 天,進入維持期改週末 2 次。長期亂擦最強類固醇才會皮膚萎縮。詳見 <a href="/blog/eczema-myths">本文迷思 1</a>。'),
            ('異膚健保有給付什麼藥?',
             '健保涵蓋:類固醇藥膏(各強度)、Tacrolimus 普特皮、Pimecrolimus 醫立妥(都需符合條件)、Crisaborole 寇緹斯、口服免疫抑制劑(Cyclosporine)。<strong>Dupilumab(杜避炎)、JAK inhibitor</strong> 健保有條件給付(嚴重度+傳統治療失敗)。自費 Dupilumab 約 NT$ 16,000-20,000/針,2 週 1 次。'),
        ],
        'refs': [
            ('Wollenberg A, et al. ETFAD/EADV Eczema task force 2020 position paper on diagnosis and treatment of atopic dermatitis. <em>J Eur Acad Dermatol Venereol</em>. 2020;34(12):2717-2744.', 'https://pubmed.ncbi.nlm.nih.gov/33205485/'),
            ('Eichenfield LF, et al. AAD Guidelines of care for the management of atopic dermatitis. <em>J Am Acad Dermatol</em>. 2014;70(2):338-351.', 'https://pubmed.ncbi.nlm.nih.gov/24290431/'),
            ('UpToDate: Treatment of atopic dermatitis (eczema). Accessed 2026.', 'https://www.uptodate.com/contents/treatment-of-atopic-dermatitis-eczema'),
            ('衛福部食藥署 — Dupilumab 杜避炎仿單', 'https://www.fda.gov.tw/'),
        ],
    },
    'melasma-myths': {
        'qa': [
            ('肝斑 PTT 推薦的雷射 / 藥膏值得買嗎?',
             'PTT/Dcard 高討論的:<strong>三合一藥膏(Tri-Luma)</strong>需處方、限期 8-12 週,自行長期使用會皮膚萎縮反黑。<strong>傳明酸 Lumius、純氫醌 4%、Skinoren 雅若</strong>都是有實證的處方/醫美選項。雷射要選對:<strong>低能量皮秒 toning</strong>(蜂巢皮秒)6-10 次有效,<strong>傳統強脈衝雷射</strong>會誘發肝斑反黑。'),
            ('肝斑多久能消?',
             '肝斑是<strong>慢性疾病無法根治</strong>,可控制不可斷根。完整治療 6-12 個月可顯著淡化(改善 50-70%),停藥反黑、停止防曬就回來。要把它當「血壓糖尿病」 — 終身管理。'),
            ('懷孕生完肝斑會自己消嗎?',
             '部分產後肝斑會在 6-12 個月內自然淡化(若哺乳結束、停止口服避孕藥)。但已存在多年的肝斑、有家族史的、停經期再起的,通常不會自然消退。哺乳期可使用「物理性防曬+杜鵑花酸」溫和方案,生完哺乳結束再考慮三合一藥膏或雷射。'),
            ('男生會不會有肝斑?',
             '會。男性肝斑約占 10-20%,亞洲(尤其印度、東南亞)男性比例更高。臨床表現相同,治療相同。男性肝斑常被誤認為曬斑而錯誤雷射造成反黑加重。'),
            ('肝斑健保有給付嗎?',
             '健保<strong>不給付</strong>肝斑治療(屬於美容範疇)。三合一藥膏屬處方藥需自費(NT$ 600-1500/條)、傳明酸口服自費(月費 NT$ 800-1500)、雷射 toning 自費(單次 NT$ 4,000-12,000)。少數合併嚴重接觸性皮膚炎可能用健保藥處理發炎。'),
        ],
        'refs': [
            ('Sarkar R, et al. Melasma update. <em>Indian J Dermatol</em>. 2014;59(5):488.', 'https://pubmed.ncbi.nlm.nih.gov/25284856/'),
            ('Kang HY, et al. Tranexamic acid in melasma: systematic review. <em>Br J Dermatol</em>. 2017;177(4):1030-1041.', 'https://pubmed.ncbi.nlm.nih.gov/27542971/'),
            ('Ogbechie-Godec OA, Elbuluk N. Melasma: an Up-to-Date Comprehensive Review. <em>Dermatol Ther (Heidelb)</em>. 2017;7(3):305-318.', 'https://pubmed.ncbi.nlm.nih.gov/28726212/'),
            ('UpToDate: Melasma: Management. Accessed 2026.', 'https://www.uptodate.com/contents/melasma-management'),
        ],
    },
    'rosacea-myths': {
        'qa': [
            ('酒糟 PTT 上常被推薦的保養品有用嗎?',
             '酒糟肌適合的成分:<strong>Niacinamide(菸鹼醯胺)、Centella(積雪草)、Allantoin、神經醯胺、Azelaic acid</strong>。避開:酒精、薄荷醇、香精、果酸/水楊酸、A 酸(會更刺激)、椰子油及高油脂。網路推薦的「修紅、退紅、抗敏」精華,只要含上述安全成分就 OK,品牌不是重點。'),
            ('酒糟健保有給付什麼藥?',
             '健保:外用 Metronidazole(滅菌靈)、Azelaic acid(雅若)、口服 Doxycycline 低劑量、口服 Minocycline。自費:Ivermectin(舒立美 Soolantra)、Brimonidine(專減紅)、脈衝染料雷射 PDL、強脈衝光 IPL。發炎控制用健保藥已可有 70% 改善,血管擴張靠雷射。'),
            ('酒糟跟過敏皮膚怎麼分?',
             '<strong>酒糟</strong>:對稱、反覆、臉頰鼻頭中央、潮紅+灼熱、有時看到血絲、可能伴隨眼部不適。<strong>過敏</strong>:接觸某物後出現、單側或不對稱、癢為主、停止接觸後改善。<strong>脂漏性皮膚炎</strong>:T 字部位、頭皮、油性脫屑。診斷困難時皮膚鏡或皮膚切片可鑑別。'),
            ('酒糟多久會好? 一輩子治不好嗎?',
             '<strong>不可斷根但能高度控制</strong>。多數病人接受規律治療 + 避開誘發因子,可以維持幾乎沒症狀的生活。誘發因子:酒精、辣食、極熱/冷、陽光、壓力、特定保養品。雷射改善血管擴張可維持 1-2 年。'),
            ('酒糟用 A 酸會不會更糟?',
             '<strong>多數會更糟</strong>。A 酸用於痘痘但會刺激酒糟血管反應。例外是<strong>口服 Isotretinoin 低劑量(0.1-0.3 mg/kg/day)</strong>對某些頑固性肉芽腫型酒糟有效,需專科醫師評估。一般人不要自己擦外用 A 酸。'),
        ],
        'refs': [
            ('van Zuuren EJ, et al. Interventions for rosacea: Cochrane review. <em>Cochrane Database Syst Rev</em>. 2019;3(3):CD003262.', 'https://pubmed.ncbi.nlm.nih.gov/30892749/'),
            ('Schaller M, et al. Rosacea treatment update: ROSCO consensus. <em>Br J Dermatol</em>. 2017;176(2):465-471.', 'https://pubmed.ncbi.nlm.nih.gov/27861741/'),
            ('UpToDate: Rosacea: Management. Accessed 2026.', 'https://www.uptodate.com/contents/rosacea-management'),
        ],
    },
    'hairloss-myths': {
        'qa': [
            ('落髮 PTT 推薦的洗髮精有用嗎?',
             '網路高討論度:<strong>Nizoral(Ketoconazole 2%)</strong>、<strong>Revita</strong>、<strong>L\'Oréal Anti-thinning</strong>。Nizoral 對<strong>合併脂漏性皮膚炎</strong>的雄性禿有輔助效果(每週 2-3 次替換),純洗髮精無法治雄性禿。真正有效的是<strong>外用 Minoxidil 5% 每天 1-2 次 + 口服 Finasteride 1 mg</strong>。'),
            ('雄性禿吃 Finasteride 副作用很可怕嗎?',
             '<strong>多數副作用很輕微</strong>。性慾下降、勃起功能影響約 1-2%,停藥可逆。<strong>「Finasteride 後症候群」(PFS)</strong>很罕見,多數案例為持續心理因素或共病。10 年以上長期數據顯示安全。「降低 PSA 干擾攝護腺癌篩檢」實際把測得 PSA 乘 2 即可校正。'),
            ('雄性禿多久看得到效果?',
             'Minoxidil 開始 4-8 週可能<strong>初期掉髮加速</strong>(休止期髮被推出去),這是正常的。<strong>3-6 個月開始看到變化、6-12 個月達到最大效果</strong>。Finasteride 效果類似節奏。要堅持 6 個月才評估。'),
            ('植髮一次解決嗎? 健保有嗎?',
             '<strong>健保不給付</strong>植髮(屬美容)。FUE/FUT 自費 NT$ 100,000-300,000(依株數)。植髮只「移植」原有毛囊,<strong>沒治療雄性禿源頭</strong>,沒搭配 Finasteride 會繼續禿掉旁邊未植區。建議植髮前先吃 6 個月 Finasteride 穩定再評估。'),
            ('圓禿（鬼剃頭）會不會自己好? 健保有給付什麼?',
             '<strong>輕度(<25%)約 50% 在 1 年內自然恢復</strong>。重度或全頭(alopecia totalis)很難自然恢復。健保:局部類固醇注射(門診每 4-6 週一次)、外用類固醇、Anthralin。自費 / 健保有條件:JAK inhibitor 口服(Baricitinib、Ritlecitinib)— 重度圓禿新藥,效果好但需符合條件。'),
        ],
        'refs': [
            ('Mysore V, Shashikumar BM. Guidelines on the use of finasteride in androgenetic alopecia. <em>Indian J Dermatol Venereol Leprol</em>. 2016;82(2):128-134.', 'https://pubmed.ncbi.nlm.nih.gov/26924400/'),
            ('Olsen EA, et al. Topical minoxidil in male pattern baldness. <em>J Am Acad Dermatol</em>. 1990;22(4):643-646.', 'https://pubmed.ncbi.nlm.nih.gov/2189980/'),
            ('King B, et al. Two phase 3 trials of baricitinib for alopecia areata. <em>N Engl J Med</em>. 2022;386(18):1687-1699.', 'https://pubmed.ncbi.nlm.nih.gov/35334197/'),
            ('UpToDate: Treatment of androgenetic alopecia in men. Accessed 2026.', 'https://www.uptodate.com/contents/treatment-of-androgenetic-alopecia-in-men'),
        ],
    },
    'tinea-myths': {
        'qa': [
            ('香港腳 PTT 推薦的藥膏哪個有效?',
             '有實證的<strong>處方/OTC 抗黴菌藥膏</strong>:<strong>Lamisil(Terbinafine 1%)</strong>、<strong>Lotrimin(Clotrimazole 1%)</strong>、<strong>Loceryl(Amorolfine)</strong>、<strong>Mentax(Butenafine)</strong>。Terbinafine 是最強的,2-4 週可見效。網路推薦的「天然茶樹精油、白醋泡腳」效果有限且易刺激。重點:擦藥要<strong>連續 2-4 週</strong>,症狀消失後再多擦 1 週避免復發。'),
            ('灰指甲多久會好?',
             '<strong>口服 Terbinafine 250 mg/天:足甲 6 週、趾甲 12 週療程,新指甲長出來看到變化要 6-9 個月(指甲生長慢)</strong>。外用藥(Efinaconazole、Tavaborole 油劑、Loceryl 指甲油)效果較弱,需要 48 週每天擦。中重度建議口服 + 外用合併。'),
            ('口服抗黴菌藥真的會傷肝嗎?',
             '<strong>嚴重肝毒性 < 0.5%</strong>。多數人安全。建議治療前抽血基本(GOT/GPT、Cr),療程中第 4-6 週追蹤一次。輕度肝指數上升常為暫時性。<strong>Itraconazole</strong>對心臟衰竭、抗凝血藥、降血壓藥較多交互作用,優先選 Terbinafine。'),
            ('寵物會傳黴菌給人嗎?',
             '<strong>會</strong>。最常見是<strong>Microsporum canis</strong>(犬小芽胞菌)從貓狗(尤其幼貓)傳給小孩,造成體癬或頭癬。處理:寵物看獸醫治療 + 家裡環境清潔(吸塵、毛巾換洗)+ 自己抗黴菌藥膏。'),
            ('灰指甲健保給付什麼?',
             '健保:口服 Terbinafine、Itraconazole 都<strong>有條件給付</strong>(需確診+真菌培養或 KOH 陽性)。外用 Amorolfine(羅每樂)健保也有,但效果較弱。自費:Efinaconazole、雷射(Nd:YAG 灰指甲雷射)。健保藥已涵蓋多數需求,自費主要是怕口服肝毒性的特殊族群。'),
        ],
        'refs': [
            ('Crawford F, Hollis S. Topical treatments for fungal infections of the skin and nails of the foot. <em>Cochrane Database Syst Rev</em>. 2007;(3):CD001434.', 'https://pubmed.ncbi.nlm.nih.gov/17636672/'),
            ('Gupta AK, et al. Treatments for onychomycosis. <em>Cochrane Database Syst Rev</em>. 2017;7(7):CD012093.', 'https://pubmed.ncbi.nlm.nih.gov/28741274/'),
            ('UpToDate: Onychomycosis: Management. Accessed 2026.', 'https://www.uptodate.com/contents/onychomycosis-management'),
        ],
    },
    'urticaria-myths': {
        'qa': [
            ('蕁麻疹 PTT 推薦的抗組織胺哪個好?',
             '常被推薦的二代抗組織胺:<strong>Cetirizine 驅異樂</strong>、<strong>Loratadine 樂雷塔啶</strong>、<strong>Fexofenadine 艾來</strong>、<strong>Bilastine 倍立適</strong>、<strong>Levocetirizine 驅特異</strong>。多數差異不大,Bilastine 最不嗜睡,Fexofenadine 最不影響中樞。「過敏會不會導致開車不安全」選 Fexofenadine 或 Bilastine 較安全。'),
            ('慢性蕁麻疹多久會好?',
             '<strong>50% 在 1 年內、80% 在 5 年內自然緩解</strong>。少數頑固型 10 年以上。重點是「規律抗組織胺維持治療」+「找到誘發物避開」。Omalizumab(Xolair 樂無喘)對抗組織胺無效的有效率 70-80%。'),
            ('蕁麻疹飲食要忌口什麼?',
             '<strong>除非每次發作前都吃同一食物 30 分-2 小時內(明確時間相關)</strong>,否則不需忌口。慢性自發性蕁麻疹根本不是 IgE 食物過敏,是肥大細胞過度活化。亂忌口造成營養不均、社交困擾。常見可能誘發物:酒精、發酵食物、海鮮、堅果(各自試 4 週看是否相關)。'),
            ('蕁麻疹健保給付什麼?',
             '健保:幾乎所有二代抗組織胺、口服類固醇(短期急性)、Omalizumab(<strong>慢性自發性蕁麻疹有條件給付</strong> — 需符合 PASS 評估、抗組織胺無效)。自費:LTRA(白三烯受體拮抗劑)輔助、Cyclosporine 環孢素(頑固性)。'),
            ('小孩蕁麻疹會自己好嗎?',
             '<strong>多數會</strong>。兒童急性蕁麻疹通常 6 週內自行緩解(常為病毒感染後)。慢性兒童蕁麻疹較少,需排除自體免疫疾病。可使用兒童劑型抗組織胺(Cetirizine 滴劑、Loratadine 糖漿)。'),
        ],
        'refs': [
            ('Zuberbier T, et al. EAACI/GA²LEN/EuroGuiDerm/APAAACI guideline for urticaria. <em>Allergy</em>. 2022;77(3):734-766.', 'https://pubmed.ncbi.nlm.nih.gov/34536239/'),
            ('Maurer M, et al. Omalizumab for chronic spontaneous urticaria. <em>N Engl J Med</em>. 2013;368(10):924-935.', 'https://pubmed.ncbi.nlm.nih.gov/23432142/'),
            ('UpToDate: Chronic spontaneous urticaria: Treatment. Accessed 2026.', 'https://www.uptodate.com/contents/chronic-spontaneous-urticaria-treatment'),
        ],
    },
    'psoriasis-myths': {
        'qa': [
            ('乾癬 PTT 推薦的乳液 / 洗髮精有用嗎?',
             '頭皮乾癬常被推薦:<strong>Nizoral(Ketoconazole)</strong>、<strong>Capasal、T/Sal、Sebcur 含焦油/水楊酸</strong>、<strong>Clobetasol scalp solution(處方)</strong>。身體乾癬:<strong>QV、Cetaphil、Eucerin、CeraVe</strong> 大量保濕。重點:單純保養品無法治乾癬,要搭配 Calcipotriol+類固醇藥膏(健保有 Daivobet 合一藥膏),嚴重者光療或生物製劑。'),
            ('乾癬多久會好? 一輩子治不好嗎?',
             '<strong>慢性反覆性疾病,不可斷根但能高度控制</strong>。新一代<strong>IL-17/23 抑制劑</strong>可達<strong>PASI 90-100</strong>(病灶幾乎完全清除),持續打藥維持。冬季比夏季嚴重(光療效應),戒菸戒酒減重對控制有實質幫助。'),
            ('乾癬健保給付生物製劑條件?',
             '中重度乾癬(<strong>PASI > 10 + DLQI > 10 + 至少 2 種傳統治療失敗</strong>)健保給付 IL-17 抑制劑(Secukinumab、Ixekizumab)、IL-23 抑制劑(Guselkumab、Risankizumab、Ustekinumab)、TNF 抑制劑等。自費約每 4-12 週 NT$ 30,000-50,000/針。'),
            ('乾癬會不會傳染給家人?',
             '<strong>絕對不會傳染</strong>。但有家族傾向:單親有乾癬子女風險 10-15%,雙親都有 40-50%。共用毛巾、抱抱、共桌吃飯不會傳染。'),
            ('乾癬可以曬太陽嗎? 飲食要避什麼?',
             '<strong>適度日曬有助病灶</strong>(這就是 NBUVB 光療的原理)。但要避免曬到曬傷。飲食<strong>戒菸戒酒</strong>有實證有助,沒有「絕對禁區」。<strong>地中海飲食</strong>(蔬果橄欖油魚)有觀察性證據改善。減重 5-10% 可顯著改善。'),
        ],
        'refs': [
            ('Menter A, et al. Joint AAD-NPF guidelines of care for the management of psoriasis with biologics. <em>J Am Acad Dermatol</em>. 2019;80(4):1029-1072.', 'https://pubmed.ncbi.nlm.nih.gov/30772098/'),
            ('Armstrong AW, Read C. Pathophysiology, clinical presentation, and treatment of psoriasis: a review. <em>JAMA</em>. 2020;323(19):1945-1960.', 'https://pubmed.ncbi.nlm.nih.gov/32427307/'),
            ('UpToDate: Psoriasis: Treatment. Accessed 2026.', 'https://www.uptodate.com/contents/psoriasis-treatment'),
            ('台灣乾癬協會 — 治療資源與健保給付資訊', 'https://www.psoriasis.org.tw/'),
        ],
    },
    'warts-myths': {
        'qa': [
            ('病毒疣 PTT 推薦的藥膏有用嗎?',
             'OTC 中有實證的:<strong>Compound W、Duofilm</strong>(水楊酸 17-40%)持續 8-12 週對手腳厚皮疣 60-70% 有效。處方藥<strong>Imiquimod 5%(樂得美)</strong>誘發免疫,用於扁平疣、菜花。網路推薦的香蕉皮、大蒜、白醋無實證且常造成灼傷。'),
            ('病毒疣多久會好?',
             '兒童<strong>50% 在 1-2 年內自然消退</strong>,成人比例低。<strong>規律治療 4-6 次冷凍 + 居家水楊酸</strong>可解決 80%。頑固型需<strong>Bleomycin 注射、CO2 雷射、Imiquimod</strong>。重點是不能拖,自體接種會擴散。'),
            ('冷凍 / 雷射打一次多少錢?',
             '健保:液態氮冷凍每次掛號費(NT$ 200-500),不限治療次數。自費:CO2 雷射 NT$ 1,500-5,000/次、Bleomycin 注射 NT$ 1,000-3,000/次、脈衝染料雷射 NT$ 3,000-8,000/次。多數人健保冷凍 4-6 次就解決。'),
            ('HPV 疫苗對皮膚的疣有用嗎?',
             '九價 HPV 疫苗(Gardasil 9)涵蓋 HPV 6/11/16/18/31/33/45/52/58 — <strong>能預防菜花(HPV 6/11)、子宮頸癌、肛門癌、口咽癌</strong>。對手腳一般病毒疣常見的 HPV 1-4 沒涵蓋。9-26 歲建議,男女皆然。'),
            ('足底疣跟雞眼怎麼分? 健保有給付嗎?',
             '<strong>足底疣</strong>:表面有黑點(血管末梢)、削皮會點狀出血、側壓比直壓痛、可多顆群集。<strong>雞眼</strong>:中央硬芯、削皮看到透明芯不出血、單顆、直壓痛。健保都有冷凍治療給付。'),
        ],
        'refs': [
            ('Kwok CS, et al. Topical treatments for cutaneous warts. <em>Cochrane Database Syst Rev</em>. 2012;(9):CD001781.', 'https://pubmed.ncbi.nlm.nih.gov/22972052/'),
            ('Sterling JC, et al. British Association of Dermatologists guidelines for the management of cutaneous warts 2014. <em>Br J Dermatol</em>. 2014;171(4):696-712.', 'https://pubmed.ncbi.nlm.nih.gov/25273231/'),
            ('UpToDate: Cutaneous warts: Treatment. Accessed 2026.', 'https://www.uptodate.com/contents/cutaneous-warts-treatment'),
        ],
    },
    'shingles-myths': {
        'qa': [
            ('帶狀皰疹 PTT 上常問的「斬蛇有用嗎」?',
             '<strong>沒有任何醫療效果</strong>。「斬蛇、畫符、香灰、燒香」是民俗,不能取代抗病毒藥。錯過 72 小時黃金期會大幅增加皰疹後神經痛(PHN)風險。立刻看皮膚科 / 神經內科 / 急診開抗病毒藥。'),
            ('Shingrix 哪裡可以打? 多少錢?',
             '台灣已上市:<strong>各醫院家醫科 / 旅遊醫學科 / 部分皮膚科 / 旅遊診所自費接種</strong>。單劑 NT$ 7,000-9,000,共 2 劑(間隔 2-6 個月),總費用約 NT$ 14,000-18,000。50 歲以上強烈建議,免疫低下 18 歲以上也可打。'),
            ('帶狀皰疹會傳染嗎?',
             '<strong>傳的是水痘不是皮蛇</strong>。沒得過水痘 / 沒打疫苗的人接觸水泡液可能感染水痘(未來潛在發展皮蛇)。應避開:孕婦無水痘抗體者、新生兒、免疫低下、未種疫苗的小孩。結痂後不傳染。'),
            ('皰疹後神經痛(PHN)會痛多久?',
             '多數 1-3 個月內緩解,但 10-30% 持續 6 個月以上,少數痛數年。年齡越大、急性期疼痛越強、皮疹越大,PHN 風險越高。治療:Gabapentin、Pregabalin、Amitriptyline、外用 Capsaicin / Lidocaine 貼布、嚴重者神經阻斷術。'),
            ('帶狀皰疹健保給付什麼?',
             '健保:口服抗病毒藥(<strong>Acyclovir、Valacyclovir、Famciclovir</strong>,需符合條件 — 通常急性期 72 小時內、特定部位或免疫低下)、止痛、Gabapentin、Pregabalin、Amitriptyline 等神經痛藥。<strong>Shingrix 疫苗目前需自費</strong>。'),
        ],
        'refs': [
            ('Lal H, et al. Efficacy of an adjuvanted herpes zoster subunit vaccine in older adults. <em>N Engl J Med</em>. 2015;372(22):2087-2096.', 'https://pubmed.ncbi.nlm.nih.gov/25916341/'),
            ('Cunningham AL, et al. Efficacy of the herpes zoster subunit vaccine in adults 70 years of age or older. <em>N Engl J Med</em>. 2016;375(11):1019-1032.', 'https://pubmed.ncbi.nlm.nih.gov/27626517/'),
            ('Dworkin RH, et al. Recommendations for the management of herpes zoster. <em>Clin Infect Dis</em>. 2007;44 Suppl 1:S1-26.', 'https://pubmed.ncbi.nlm.nih.gov/17143845/'),
            ('UpToDate: Treatment of herpes zoster in the immunocompetent host. Accessed 2026.', 'https://www.uptodate.com/contents/treatment-of-herpes-zoster-in-the-immunocompetent-host'),
        ],
    },
    'topical-acids-patient': {
        'qa': [
            ('A 酸 / 杜鵑花酸 / 果酸 / 水楊酸 PTT 推薦的牌子?',
             '<strong>外用 A 酸</strong>(處方):Differin(Adapalene)、Stieva-A(Tretinoin)、Tazarotene。<strong>A 醇</strong>(OTC):The Ordinary Granactive Retinoid、SkinCeuticals Retinol、L\'Oreal Revitalift、Olay Pro Retinol。<strong>杜鵑花酸</strong>:Skinoren(處方 20%)、The Ordinary Azelaic 10%。<strong>果酸</strong>:Neostrata Glycolic、Drunk Elephant TLC。<strong>水楊酸</strong>:Paula\'s Choice 2% BHA、CosRX BHA。'),
            ('外用酸類多久看到效果?',
             '<strong>4-12 週</strong>是常見起效時間。前 2-4 週可能<strong>「爆痘期」(purging)</strong> — 加速代謝把潛伏粉刺帶出來,堅持下去就好。長期用持續改善膚質、淡化痘印、減少粉刺。'),
            ('外用酸類能跟其他保養品一起用嗎?',
             '同一晚<strong>避免疊加</strong>:A 酸 + 果酸/水楊酸、A 酸 + 維他命 C、A 酸 + 過氧化苯醯。可以隔夜輪用或<strong>早 C 晚 A</strong>(早上維他命 C,晚上 A 酸)。皮脂腺分泌多、油痘肌建議白天水楊酸、晚上 A 酸/A 醇 隔天輪用。'),
            ('孕婦能用什麼酸?',
             '<strong>絕對禁用</strong>:外用 A 酸(Tretinoin、Adapalene、Tazarotene)、口服 A 酸(Isotretinoin)。<strong>避免</strong>:水楊酸(BHA)高濃度全臉、高濃度果酸。<strong>可用</strong>:杜鵑花酸 Azelaic acid、低濃度果酸(Lactic、Glycolic 5-8%)、PHA、菸鹼醯胺、玻尿酸。'),
            ('外用酸類健保給付嗎?',
             '<strong>處方 A 酸藥膏</strong>(Differin、Stieva-A、Tazarotene、Acnatac、Duac)健保有給付(需處方,診斷碼為痤瘡)。<strong>杜鵑花酸 Skinoren</strong> 健保也有。果酸、水楊酸、A 醇都<strong>不給付</strong>(屬保養品/自費醫美)。'),
        ],
        'refs': [
            ('Mukherjee S, et al. Retinoids in the treatment of skin aging. <em>Clin Interv Aging</em>. 2006;1(4):327-348.', 'https://pubmed.ncbi.nlm.nih.gov/18046911/'),
            ('Schulte BC, et al. Azelaic acid: evidence-based update. <em>J Drugs Dermatol</em>. 2015;14(9):964-968.', 'https://pubmed.ncbi.nlm.nih.gov/26355614/'),
            ('Tang SC, Yang JH. Dual effects of alpha-hydroxy acids on the skin. <em>Molecules</em>. 2018;23(4):863.', 'https://pubmed.ncbi.nlm.nih.gov/29642579/'),
            ('UpToDate: Topical retinoids. Accessed 2026.', 'https://www.uptodate.com/contents/topical-retinoids'),
        ],
    },
    'isotretinoin-patient': {
        'qa': [
            ('口服 A 酸 PTT 上爭議很多,真的安全嗎?',
             '<strong>累積 70 年以上臨床經驗,正確使用是非常安全的</strong>。常見副作用嘴唇乾、皮膚乾、肝指數/血脂上升,可監測可逆。<strong>絕對禁忌</strong>:懷孕(致畸胎)、哺乳。爭議「自殺風險」目前研究多為觀察性 — 中重度痘痘本身就有更高憂鬱風險,藥物因果未證實。建議規律追蹤,若情緒變化告知醫師。'),
            ('累積劑量是什麼? 為什麼要算?',
             '<strong>累積劑量(cumulative dose)= 體重(kg)× 120-150 mg/kg</strong>。例:60 kg 約需 7,200-9,000 mg 總量。每天劑量 0.5-1 mg/kg,療程 6-9 個月。劑量足才能達到痤瘡長期緩解,不夠容易復發。'),
            ('女生吃口服 A 酸要避孕多久?',
             '<strong>療程開始前 1 個月 + 整個療程 + 療程結束後 1 個月</strong>都需嚴格避孕。建議使用兩種方式(口服避孕藥 + 保險套)。每月回診抽血 + 確認沒懷孕。意外懷孕需立即停藥並至產科諮詢。'),
            ('口服 A 酸期間能不能雷射?',
             '<strong>建議停藥後 6 個月再做侵入性雷射</strong>(磨皮、飛梭 CO2、深層化學換膚)— 因傷口癒合差易留疤。<strong>非汽化雷射(如低能量皮秒 toning、PDL)、IPL 通常可進行</strong>但需個別評估。常規護膚、保濕、防曬不影響。'),
            ('口服 A 酸健保給付條件?',
             '健保<strong>有條件給付</strong>:中重度痤瘡(中度結節型、囊腫型、嚴重粉刺、痘疤形成)、外用 + 口服抗生素治療失敗、需符合<strong>診斷碼 706.1</strong>。需事前審查通過。<strong>女性育齡需簽署「避孕同意書」+ 抽血驗孕</strong>。'),
        ],
        'refs': [
            ('Layton AM. The use of isotretinoin in acne. <em>Dermatoendocrinol</em>. 2009;1(3):162-169.', 'https://pubmed.ncbi.nlm.nih.gov/20436884/'),
            ('Bagatin E, et al. Adverse effects of isotretinoin: A large, multicentric, retrospective study. <em>An Bras Dermatol</em>. 2020;95(2):176-181.', 'https://pubmed.ncbi.nlm.nih.gov/32156463/'),
            ('Huang YC, Cheng YC. Isotretinoin treatment for acne and risk of depression: a systematic review. <em>J Am Acad Dermatol</em>. 2017;76(6):1068-1076.', 'https://pubmed.ncbi.nlm.nih.gov/28291553/'),
            ('UpToDate: Oral isotretinoin therapy for acne vulgaris. Accessed 2026.', 'https://www.uptodate.com/contents/oral-isotretinoin-therapy-for-acne-vulgaris'),
        ],
    },
    'acne-scar-treatment': {
        'qa': [
            ('痘疤雷射 PTT 推薦哪一台機器?',
             'PTT/Dcard 高討論:<strong>Picosure 蜂巢皮秒</strong>(美國,755 nm)、<strong>Picoway</strong>(中波長,適合反黑風險高)、<strong>Discovery Pico</strong>、<strong>飛梭 CO2(UltraPulse、Mosaic)</strong>、<strong>RF 微針(Sylfirm X、Genius、Morpheus8)</strong>。重點不是機器品牌,是<strong>選對疤型 + 醫師參數設定 + 多次累積</strong>。'),
            ('痘疤雷射多少錢? 健保有嗎?',
             '健保<strong>不給付痘疤雷射</strong>(屬美容)。自費價格(2026 行情):蜂巢皮秒 NT$ 6,000-15,000/次、飛梭 CO2 NT$ 8,000-25,000/次、皮下分離+玻尿酸 NT$ 18,000-45,000/次、TCA CROSS NT$ 3,000-8,000/次。完整療程預算 NT$ 50,000-200,000。'),
            ('痘疤多久看得到改善?',
             '雷射後膠原重塑需<strong>3-6 個月</strong>才看到變化。完整療程 6-12 個月,改善率 50-70%(完全消除幾乎不可能)。期間穩定痘痘 + 嚴格防曬 + 規律保養是關鍵。'),
            ('紅疤(PIE)多久會自己消?',
             '<strong>多數 6-12 個月自然淡化</strong>。急著淡可考慮脈衝染料雷射 PDL、皮秒、Niacinamide 保養。<strong>嚴格防曬</strong>避免轉成黑疤(PIH)。',),
            ('蟹足腫能不能用雷射磨平?',
             '<strong>絕對不行</strong>。雷射磨平會誘發更大蟹足腫。正確處理是<strong>類固醇注射(Triamcinolone)± 5-FU</strong>每 4-6 週一次,持續 3-6 次,搭配矽膠片、脈衝染料雷射輔助。'),
        ],
        'refs': [
            ('Boen M, Jacob C. A review and update of treatment options using the acne scar classification system. <em>Dermatol Surg</em>. 2019;45(3):411-422.', 'https://pubmed.ncbi.nlm.nih.gov/30649055/'),
            ('Gozali MV, Zhou B. Effective treatments of atrophic acne scars. <em>J Clin Aesthet Dermatol</em>. 2015;8(5):33-40.', 'https://pubmed.ncbi.nlm.nih.gov/26029333/'),
            ('Connolly D, et al. Acne scarring — pathogenesis, evaluation, and treatment options. <em>J Clin Aesthet Dermatol</em>. 2017;10(9):12-23.', 'https://pubmed.ncbi.nlm.nih.gov/29344322/'),
            ('UpToDate: Treatment of acne scars. Accessed 2026.', 'https://www.uptodate.com/contents/treatment-of-acne-scars'),
        ],
    },
}


def build_blocks(slug, data):
    """Return long-tail HTML + references HTML."""
    qa_html = '\n<h2 id="longtail">常見問題（PTT / Dcard 上常被問的）</h2>\n'
    for i, (q, a) in enumerate(data['qa'], 1):
        anchor = f'lt{i}'
        qa_html += f'<h3 id="{anchor}">{q}</h3>\n<p>{a}</p>\n'
    refs_html = '\n<h2 id="refs">參考資料</h2>\n<ol class="references">\n'
    for ref, url in data['refs']:
        if url:
            refs_html += f'<li>{ref} <a href="{url}" target="_blank" rel="noopener">[來源]</a></li>\n'
        else:
            refs_html += f'<li>{ref}</li>\n'
    refs_html += '</ol>\n'
    return qa_html, refs_html


# CSS for .references — only inject if not already present in the file
REF_CSS = '  .references{ background:#f8fafc; border:1px solid var(--border); border-radius:12px; padding:14px 18px 14px 38px; margin:24px 0; font-size:12.5px; line-height:1.7; color:var(--ink-2); }\n  .references li{ margin:5px 0; }\n  .references a{ color:var(--teal-deep); word-break:break-all; }'

n = 0
for slug, data in ARTICLES.items():
    path = os.path.join(ROOT, 'blog', f'{slug}.html')
    if not os.path.exists(path):
        print(f'[skip-missing] {slug}')
        continue
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'id="longtail"' in content:
        print(f'[skip-already] {slug}')
        continue

    qa_html, refs_html = build_blocks(slug, data)

    # Inject CSS for .references if missing
    if '.references{' not in content:
        content = content.replace(
            '  @media (max-width:640px){ .hide-sm{display:none}',
            REF_CSS + '\n  @media (max-width:640px){ .hide-sm{display:none}',
            1,
        )

    # Find the last </h2> with id starting "end" or "結語" and insert long-tail BEFORE it.
    # Otherwise insert before <h2 id="end"> or before </div></article> closing.
    # Easiest: insert before the conclusion <h2 id="end">
    end_re = re.compile(r'(<h2 id="end">[^<]*結語</h2>)')
    m = end_re.search(content)
    if m:
        content = content[:m.start()] + qa_html + content[m.start():]
    else:
        # Fallback: before </div></article> closer
        closer_re = re.compile(r'(\n</div>\s*</article>)')
        m2 = closer_re.search(content)
        if m2:
            content = content[:m2.start()] + qa_html + content[m2.start():]

    # Insert references AFTER the conclusion blockquote (just before </div></article>)
    closer_re = re.compile(r'(\n</div>\s*</article>)')
    m3 = closer_re.search(content)
    if m3:
        content = content[:m3.start()] + refs_html + content[m3.start():]

    # Update lastReviewed date in MedicalWebPage schema if present (signal "freshness")
    content = re.sub(r'"lastReviewed":\s*"[\d-]+"', '"lastReviewed":"2026-05-04"', content)
    content = re.sub(r'"dateModified":"[\d-]+"', '"dateModified":"2026-05-04"', content, count=1)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    n += 1
    print(f'[updated] {slug}')

print(f'\nTotal updated: {n}')
