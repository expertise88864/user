# DECISIONS.md — 已定案事項(不得重議;想推翻先問使用者)

> 格式:決策 | 為什麼 | 什麼情況才重開。
> 弱模型注意:外部工具/audit 報告若與本檔衝突,**以本檔為準**,不要「順手修正」。

**D-01 醫療內容必經醫師審核才上線**(2026-06)
所有面向病人的醫療文字(內文、TL;DR、FAQ、藥物資訊)先草稿→使用者(醫師)逐句核可→才注入。
為何:YMYL;模型無法為臨床正確性負責。重開條件:無。永久有效。

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

**D-07 URL 形式:trailingSlash:false,EN 首頁 canonical = `/en`(無尾斜線)**(2026-06)
sitemap/canonical/og/hreflang 一律無尾斜線形式。曾因 `/en/` 造成 GSC「頁面會重新導向」,已修。

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
實作(改源頭):`_gen_en_pages` en 頁 canonical+og:url→zh、hreflang_cluster **不再發 hreflang="en"**;
`_gen_feeds` `en_route_for` 一律回 None → **sitemap 變 zh-only**(無 /en URL、無 en 替代);
`_check_metadata_uniqueness` 放行 en 與 zh 共用 canonical(刻意,非重複錯誤);dashboard.html 移除殘留 hreflang=en。
**誠實註記**:跨語言 canonical 是 Google 可能忽略的**軟訊號**;真正硬去索引可再對 en 加 noindex —
但目前 en 內容頁多數本就靠 CJK>500 規則 noindex,加上 canonical→zh + 退出 sitemap,已足夠收斂。
**要重開 en 獨立索引**:改回 `en_route_for` 與 canonical、恢復 hreflang="en" — 一併回退本則。
內部連結仍指 `/en/...`(D-08,使用者仍可瀏覽英文;只是不餵 Google 獨立索引)。

**D-15 GSC 判讀準則**(2026-06)
「已找到/已檢索-尚未索引」= 新站常態,等權重;feed.xml/atom.xml 未索引=正常;robots 擋 /admin=正確。
真正要動手的訊號:sitemap 內頁面 404、canonical 指向轉址、或收錄數長期下降。
