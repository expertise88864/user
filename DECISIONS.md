# DECISIONS.md — 已定案事項(不得重議;想推翻先問使用者)

> 格式:決策 | 為什麼 | 什麼情況才重開。
> 弱模型注意:外部工具/audit 報告若與本檔衝突,**以本檔為準**,不要「順手修正」。

**D-01 醫療內容必經醫師審核才上線**(2026-06)
所有面向病人的醫療文字(內文、TL;DR、FAQ、藥物資訊)先草稿→使用者(醫師)逐句核可→才注入。
為何:YMYL;模型無法為臨床正確性負責。重開條件:無。永久有效。

**D-18 專科考試區（/exam/**）的詳解直接上線，由醫師上線後審閱**(2026-10-14,使用者定案)
/exam/** 是給皮膚科住院醫師的專科考試讀書筆記（歷屆題＋ Fitzpatrick 重點／詳解），不是病人衛教。
使用者明示：詳解與重點整理「不用審核、直接做上線」，使用者上線後逐選項自行閱讀，有錯再要求修改。
這是 D-01 的範圍例外：只限 /exam/**；面向病人的內容仍完全適用 D-01。詳解依課本原文並附頁碼：病理／組織學／
免疫染色引 McKee's Pathology of the Skin 5e（第 6 版到手前），臨床／流行病學／治療引 Fitzpatrick 9e，兩本都講就都引；
兩本都找不到就寫明「Fitzpatrick 9e／McKee 5e 未提及」，不得用模型知識補。兩本都不支持官方答案才算疑義題：
「考試答案」依出題本意維持原答案並說明疑義；只有指引或證據已更新才寫「現行觀念」，附 1–3 篇經 NCBI 核對的文獻
（舊版觀念／未提及／說法矛盾可查文獻；模稜兩可／誤植／缺圖不上網）。(2026-10-15 使用者定案)
Codex review、遠端 CI 與正式交付流程（D-03 等）照常適用。源頭：data/exam/**；生成器 _gen_exam.py。
重開：使用者撤回此授權。

**D-20 每月期刊新知（JAAD 月報＋衛教新文＋舊文更新）先上線、醫師上線後審閱**(2026-11-17,使用者定案)
使用者明示：每月依期刊（目前只用 JAAD，日後可能加 BJD、JEADV）出一篇給皮膚科醫師的深入月報、3–5 篇「上半衛教、下半給非皮膚科醫療人員」的新文章，並更新相關舊文；「文章可以先上線，我後續再做審核」，臨床解讀由模型直接評估撰寫；標題上方「醫師審閱」照常顯示上線日期（使用者 2026-11-17 指定）。
這是 D-01 的範圍例外，只限這個系列。前提：每個數字回原文核對、每篇引用以 DOI／PubMed 確認存在、台灣核准與健保狀態只寫查得到的，查不到就不寫；草稿經獨立事實查核後才上線。不得翻譯摘要或原文、不轉貼原圖表（著作權）。2026-11 期月報先上線，5 篇新文章隨後一次全部上線（使用者同日改為一次上線）。
2026-11-18 更新：使用者認為月報效果不佳，決定先隱藏 `blog/jaad-monthly-2026-11`（DN.ARTICLES `unpublished:true`＋noindex，網址仍可開但不列出、不進 sitemap）；各文章指向月報的「詳見」連結一併移除。衛教新文與舊文更新照常保留。
Codex review、遠端 CI 與正式交付流程照常適用。重開：使用者撤回此授權。

**D-21「疾病總覽」系列（由淺到深的完整疾病介紹）先上線、醫師上線後審閱**(2026-11-18,使用者定案)
使用者提供每個疾病的資料（指引、UpToDate、近期綜論的 PDF，放在 repo 外的本機資料夾），文章以這些資料為主軸，Fitzpatrick 筆記只作延伸連結；上半給民眾，下半給非皮膚科醫療人員；參考資料列出 UpToDate 篇名；首頁「快速查找」加「疾病總覽」標籤。使用者明示「直接先上線再審」，並確認 UpToDate 授權允許交給 AI 閱讀。
與 D-20 同樣是 D-01 的範圍例外，只限這個系列，前提相同：數字與劑量逐項回原文核對並經獨立查核、外部文獻以 DOI／PubMed 確認、台灣仿單與健保只寫查得到的（健保以 115/9/22 版給付規定為準）；不翻譯 UpToDate 段落或病人衛教、不轉貼原圖表。第一篇：類天疱瘡（bullous-pemphigoid）。
標題上方「醫師審閱」照常顯示上線日期（`_review_dates.json` source "published"），與 D-20 相同；使用者 2026-11-18 針對本系列明示「照 JAAD 系列顯示」，不使用「待審」狀態。
Codex review、遠端 CI 與正式交付流程照常適用。重開：使用者撤回此授權。

**D-23 文章上方只留封面；封面文字依文章類型**(2026-11-20,使用者定案)
文章標題下方不再顯示「封面與閱讀資訊」那一排（文章編號 №、閱讀時間、作者連結、字數），只保留封面圖；已讀記錄（捲動 70%＋停留 30 秒）照舊在背景運作。封面上的「皮膚科衛教」依文章類型改寫：疾病總覽「皮膚科疾病完整介紹」、研究「皮膚科最新研究」、迷思「皮膚科迷思破解」、治療「皮膚科治療解析」，其他維持「皮膚科衛教筆記」；痘痘封面的大標題非總覽時寫「痘痘 / 痤瘡」。頁首與頁尾的網站名稱「皮膚科衛教筆記」不變。重開：使用者要求恢復閱讀資訊。

**D-22 一個疾病一篇總覽：同疾病的舊衛教文章併入總覽、舊網址 301 到段落**(2026-11-18,使用者定案)
使用者希望每個疾病只有一篇完整的長文總覽（大綱導覽、圖文並茂、只用自繪圖解不放照片），讓讀者不必開多個網頁；研究類文章（最新研究）保持獨立並從總覽連過去。舊文章從 DN.ARTICLES 與首頁標籤移除、刪除頁面，zh／en 舊網址（含 .html）在 vercel.json 永久轉址到總覽對應段落，站內連結改指新段落。第一批：異位性皮膚炎（atopic-dermatitis-overview 沿用網址；併入 atopic-dermatitis-topical→#topical、atopic-dermatitis-systemic→#systemic、atopic-dermatitis-special-populations→#comorbidities、pediatric-eczema→#children）。第二批：乾癬（psoriasis-overview 沿用網址；併入 psoriasis-topical→#topical、psoriasis-systemic→#treatment（原文涵蓋照光、口服、生物製劑，故轉到治療階梯）、psoriasis-special-populations→#comorbidities、psoriasis-myths→#myths；PASI／NAPSI 計算器移到總覽，站內連結依原段落對到 #biologics、#dn-pasi 等）。第三批：痤瘡（新網址 acne-overview；只併入 acne-myths→#myths、isotretinoin-patient→#isotretinoin；acne-scar-treatment、isotretinoin-clinical、topical-acids 兩篇、spironolactone 研究保留獨立；GAGS／ASIS 計算器移到總覽；原本以 acne-myths 為範例頁的檢查與測試改用 acne-overview）。改寫的既有總覽保留首次發布日，另以 revised 欄位排序。第四批：口周皮膚炎（沿用 perioral-dermatitis-guide 網址改寫為總覽，無退役頁；首次發布日 2026-05-13 不變，revised 2026-11-20；中英頁改用相同段落錨點，原 en-* 錨點不再存在）。第五批：蕁麻疹（新網址 urticaria-overview；只併入 urticaria-myths→#myths；UAS7 計算器移到總覽，站內連結 #dn-uas7 保留、#uct 對到 #activity；舊頁的肥大細胞示意圖不搬，總覽用自繪圖；原本以 urticaria-myths 為範例頁的計算器測試改用 urticaria-overview）。轉址一律 statusCode 301。內容規則同 D-21。重開：使用者改回多篇架構。

**D-19 Codex 續審只審上一輪之後的差異**(2026-10-15,使用者定案)
`tools/codex_review.sh resume`:同一 session 上一輪可信審查的 HEAD(`.codex-review/last_reviewed_head`)
若仍是目前 HEAD 的祖先，只審「該 HEAD..HEAD + 未提交變更」並複核先前 finding；否則照舊完整重審。
可由追蹤中的源頭重新生成、且有 `--check` 步驟驗證的生成物（如 exam/** ← _gen_exam.py），
首輪與續審都改審生成器與源頭資料，生成頁只抽查。模型／effort（當時 gpt-6.1-sol / xhigh；2026-11-18 起改為 gpt-6.2-astra / medium）與「APPROVE 才能 push」不變。
為何：完整重讀 386 檔（含 228 個生成頁）讓每次續審要 4–5 小時，即使只修幾行。
`tools/codex_review.ps1` 仍是完整重審（較嚴格），本 repo 一律用 .sh。重開：使用者要求恢復完整重審。
PR 流程（2026-10-21 實作）：`tools/pr_review.py --resume` 只審上次裁決 head..目前 head；舊 head 因 rebase
不在歷史中、或該 session 由舊版工具開始（binding 無 base），同一 session 整段重審。status 記 `base=`、`prev=`、`s=`，`_delivery.py` 的 pre-push gate 沿 `prev=`
回溯（每一環須為同 session、同 base、祖先 commit 的完成裁決），直到一個沒有 `prev=` 的整段審查，base 仍須是 main 的祖先。
生成物清單與抽樣在 `tools/review_scope.py`（不在清單上的檔案一律全讀；分類失敗也全讀）。

**D-02 合規紅線:不掛醫院、不招攬**(2026-06)
作者為住院醫師:schema 與內文不得有 worksFor/affiliation(曾誤掛中國醫藥大學,已全面移除,
生成器已加防護 `obj.pop("affiliation")`)。全站不得出現掛號/預約/價格/診所名(醫療法 §9)。
hasCredential 僅「醫師」執照、不放號碼。重開:使用者升主治/受聘且明確指示。

**D-03 push 前必過 Codex GPT-5.5 review**(2026-06)
實績:已攔 robots 三檔不一致 ×2、TL;DR 跳脫缺失、isotretinoin「根治」措辭、redirect 檢查等。
重開:使用者明示。codex 掛掉時:CLI fallback;再不行就不 push。

**D-04 `MedicalWebPage.mainEntity → {@id: …#article}` 是刻意契約**(2026-05)
`_audit_jsonld.py` 強制要求;外部工具會報 dangling reference — **不是 bug**。
曾試「修正」→ 自家 auditor 立刻紅燈,已回退。重開:使用者要改 auditor 契約時一起改。

**D-05 severe-scabies-treatment 雙語 noindex = 刻意未發布草稿**(2026-05)
`_check_meta.py:542` 白名單背書。不是錯誤,不要「順手 index」。發布時走正常發佈流程。

**D-06 AI 爬蟲政策:引用型允許、訓練型封鎖**(2026-06-23 現行版)
允許(可爬全站):ChatGPT-User, OAI-SearchBot, PerplexityBot, Claude-User, Claude-SearchBot,
ClaudeBot, Claude-Web, Google-Extended, Perplexity-User, DuckAssistBot, AI2Bot, Applebot。
封鎖(僅可抓 llms*.txt+sitemap):GPTBot, anthropic-ai, CCBot, Applebot-Extended, cohere-*,
Diffbot, FacebookBot, Amazonbot, Bytespider, omgili*, AhrefsBot, SemrushBot, MJ12bot, DotBot,
BLEXBot, PetalBot。歷史:曾短暫全放(2026-06-15),隨後收斂為此分流並加 REQUIRED_BLOCKED 測試防回歸。
改動必同步三檔(robots.txt / .well-known/ai.txt / llms.txt,見 PIPELINE.md)。重開:使用者指示。

**D-07 URL 形式:trailingSlash:false,一律無尾斜線**(2026-06;EN 部分已被 D-17 取代)
所有內部 URL(sitemap/canonical/og/hreflang/內部連結)一律用無尾斜線形式(`/blog` 非 `/blog/`、`/en` 非 `/en/`)。曾因 `/en/`、`/blog/` 造成 GSC「頁面會重新導向」,已修。
**註**:本則原說「EN 首頁 canonical=/en」——**D-17 之後 EN 全站 canonical 改指向 zh**(見 D-17);無尾斜線原則本身仍有效(適用於 zh)。

**D-08 導覽列 URL 一律無尾斜線(`/blog`、`/en`);~~刻意不修~~ → 已於 2026-07-01 修正**
原判斷「純美觀、風險>收益」。**推翻理由**:使用者連續多次在 GSC 見「頁面會重新導向」含 `/en/`、
`/blog/`,且 Google 持續沿內部連結重爬會 308 的網址。實作:改 `_gen_en_pages` 的 `en_mirror_exists`
+ `to_en_path` 支援無斜線目錄形式 → zh 導覽 `/blog/`→`/blog`、`/en/`→`/en` → `build` 重生 EN 鏡像。
低風險已驗證(`_check_internal_links`/`_check_en_internal_links`/`_check_links` 全綠、live 皆 200)。
**新規則**:內部連結一律用無尾斜線的 canonical 形式(與 D-07 一致)。舊 slug 301(D-09)仍會在
GSC redirect 報告中、仍不要按驗證。

**D-09 舊 slug 301(demodex-rosacea / eczema-myths / atopic-dermatitis-comorbidity)永久保留**(2026-05)
改名遺留,vercel.json 刻意設 permanent。GSC 顯示「頁面會重新導向」是預期行為,驗證永遠會失敗,別再送。

**D-10 zh 文章 title 品牌後綴統一 `| 陳翊嘉醫師`**(2026-06)
取代四種混用(含 37 寬度的英文長品牌)。新文章沿用;副標題型 `｜`(全形)不是品牌後綴、勿動。

**D-11 數據量測單一入口:`/assets/inline/analytics-loader.js`**(2026-06)
GA4(G-XFF3L5QD10)+Clarity 只經這支載入(bot 過濾+idle);全站 129 內容頁一致;
admin/reset-sw/offline 不裝。**絕不**另加 gtag-bootstrap / 直掛 gtag.js / inline config(曾造成 34 頁重複計數)。

**D-12 衛教文用 MedicalWebPage、研究文才用 MedicalScholarlyArticle**(2026-05)
刻意降級,防 Google 把衛教文誤判為 peer-reviewed 出版品而降權。

**D-13 zh 為權威源;EN 鏡像=courtesy translation**(2026-05)
EN 不進 llms-full 語料;llms.txt 明示 EN 非醫療決策依據。內容一律先改 zh、由管線鏡像。

**D-14 FTU 用量表唯一正規位置 = topical-steroids-guide**(2026-06 路線圖定案)
異膚等其他文章只放連結指過來,不重複表格(防 duplicate content 與版本漂移)。

**D-17 /en 鏡像收斂指向 zh(不獨立索引)**(2026-07-04,使用者定案)
GSC 證據:Google 一直爬 /en 但**不收錄**(thin machine-translation);且 en 頁 JSON-LD 早就指
zh /blog、與其 canonical=/en 不一致(Codex 抓到)。決策:把 /en 當純翻譯,權重全部收斂到 zh。
實作(改源頭):`_gen_en_pages` en 頁 canonical+og:url→zh、hreflang_cluster **不再發 hreflang="en"**(2026-07-07 併移除 scaffold `new-article.ps1`/`admin.html` 的 hreflang="en",杜絕新文章重新引入);
`_gen_feeds` `en_route_for` 一律回 None → **sitemap 變 zh-only**(無 /en URL、無 en 替代);
`_check_metadata_uniqueness` 放行 en 與 zh 共用 canonical(刻意,非重複錯誤);dashboard.html 移除殘留 hreflang=en。
**誠實註記**:跨語言 canonical 是 Google 可能忽略的**軟訊號**;真正硬去索引可再對 en 加 noindex。
**⚠ 更正(2026-07-26 code review 實測)**:本則原寫「目前 en 內容頁**多數本就靠 CJK>500 規則
noindex**」——**這句話在寫下當時就不成立**。實測 `en/**/*.html` 共 64 頁,`noindex` 只有 **2 頁**
(2026-07-04 定案當天的 commit 量測結果同為 2/64,不是後來漂移的);其餘 **62 頁都是
`index,follow`**。原因是 `_gen_en_pages` 的 CJK>500 門檻在翻譯品質提升後幾乎不再觸發。
也就是說目前收斂**只靠** canonical→zh(軟訊號)+ 退出 sitemap + 不發 hreflang="en",
**沒有任何硬去索引**。這是事實更正,不是政策變更;要不要對 en 全面加 noindex 仍是使用者決定
(代價:GSC 會把 62 頁列為「已被 noindex 排除」,且日後想開 en 獨立索引要整批回退)。
**要重開 en 獨立索引**:改回 `en_route_for` 與 canonical、恢復 hreflang="en" — 一併回退本則。
內部連結仍指 `/en/...`(D-08,使用者仍可瀏覽英文;只是不餵 Google 獨立索引)。

**D-15 GSC 判讀準則**(2026-06)
「已找到/已檢索-尚未索引」= 新站常態,等權重;feed.xml/atom.xml 未索引=正常;robots 擋 /admin=正確。
真正要動手的訊號:sitemap 內頁面 404、canonical 指向轉址、或收錄數長期下降。
