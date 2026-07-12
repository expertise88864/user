# TECH_DEBT.md — 技術債登記簿

> 來源:2026-06 全站架構 review(10 向度稽核 + 對抗式覆核 + Codex 複審)。
> 安全標籤:🟢=弱模型可直接做(有驗證器兜底) 🟡=做完必過 codex+使用者過目 🔴=先問使用者才能動。
> 完成一項 → 改狀態為 DONE 並留一行結果;新發現 → 往下加,沿用格式。

## P0 — Phase 1 計算器逐檔 review(2026-07-08,`blog/blog-calculators.js`;YMYL 最高優先)
> 方法:19 個計算器逐一抽公式/係數/範圍/邊界對照。**19 個的計分公式本身全部正確**
> (SCORAD 103、PASI 72、EASI 72、MASI 48、GAGS 44、UAS7 42、DLQI 30、POEM 28、PHQ-9 27、
> SALT 100%、IHS4、NAPSI 8/指、VASI、VAS、IGA、Hurley 皆與原始文獻一致;bands 亦標準)。
> 以下是公式**以外**的缺陷。**TD-20~25 已於 2026-07-08 修復並上線**(醫師提供 Ludwig 描述、node 驗證、Codex APPROVE;TD-25 = 醫師選擇「刪除」PHQ-9 死碼)。
| ID | 項目 | 證據/症狀 | 修法 | 驗證 | 安全 |
|----|------|-----------|------|------|------|
| ~~TD-20~~ ✅ | 🔴 **分級錯誤(已修 2026-07-08)** Ludwig(女性雄性禿)被標成 I–VII | `injectHairScale`(:362-405):性別選 F 時,stage 仍共用同一組 **I–VII** 選單(:373-381),輸出 `'Ludwig ' + roman[s-1]`(:402)→ 女性可得「Ludwig IV/V/VI/VII」,**但 Ludwig 量表只有 I–III**;且 7 個階段描述(:374-380)全是男性 M 型/馬蹄形,**不適用女性**(女性為瀰漫性中央稀疏)。Codex 已預先標出。 | 性別=F 時切換成 3 選項的 Ludwig I–III + 女性專屬描述(需醫師撰寫);男性維持 Norwood I–VII。**✅ 已修:`injectHairScale` 重寫為 hand-written、性別切換 stage 清單(F=Ludwig I–III、M=Norwood I–VII),採醫師提供之 Ludwig 描述,stage 依性別 clamp。node 驗:F 選/誤填 7 → 夾成 Ludwig III(非 VII)** | node 驗證 + gate 綠 | ✅ DONE |
| ~~TD-21~~ ✅ | Fitzpatrick 用非驗證的「取平均」計分 | `injectFitzpatrick`(:433-437):把膚色(1-6)+ 曬後反應(1-6)`Math.round((b+s)/2)` 當型別。**非標準**(標準為驗證問卷加總或臨床判型);矛盾輸入(最白膚色+從不曬傷)會算出中間 Type IV;sub/disclaimer **未標示為簡化版**。 | 二擇一:①明示為簡化啟發式;②改用驗證問卷計分。**✅ 已修(揭露):disclaimer 加註「本工具為簡易自評、非正式分型、確切分型與雷射參數請由皮膚科醫師判定」;演算法暫留,若要改標準問卷再議** | 醫師過目 | ✅ DONE(揭露) |
| ~~TD-22~~ ✅ | 通用 `_buildCalc` 數字輸入**無 JS clamp**(bug 類 #11)(已修 2026-07-08) | `_buildCalc.readVals`(:242)只 `parseFloat(el.value)||0`,**不夾 min/max**;只有手寫的 SCORAD/SALT/UAS7 的 calc() 有 `Math.max/min` 夾。受影響(number 輸入):PASI、MASI、IHS4、NAPSI、VAS、VASI、EASI — 超界打字(如 0-4 欄輸入 44)**靜默灌高分**。 | 在 readVals 依元素 `min`/`max` 夾值(集中一處修好全部);屬落實既宣告範圍、非改公式。**✅ 已修:`readVals` 依元素 min/max 夾值,一處修好 7 個 calc。node 驗:44→4、-5→0、3→3** | node 驗 + gate 綠 | ✅ DONE |
| ~~TD-23~~ ✅ | ASIS 自訂嚴重度分級無實證依據 | `injectASIS`(:749-753):ASIS 原為**變化量測 PRO**(無官方 severity cutoff),站上自訂極輕~極重五級 bands。已於 disclaimer 揭露為 12/17 精簡版,但分級切點非來自原量表。 | 改為「追蹤變化」框架,或由醫師定義/背書分級。**✅ 已修(揭露):disclaimer 加註「分級為相對嚴重度參考、主要用於追蹤治療前後變化,非原量表之正式分級」** | 醫師過目 | ✅ DONE(揭露) |
| ~~TD-24~~ ✅ | 5 個 in-article 計算器的「查看完整指南 →」連到不存在的 `/tools#` 錨點(已修 2026-07-08) | `/tools` hub 只有 10 區塊(scorad/pasi/dlqi/salt/uas7/gags/masi/hurley/norwood/fitzpatrick)。但 EASI/IHS4/VAS-pruritus/IGA/VASI 會實際 in-article 渲染並由 `_buildCalc`(:235)產生 `href="/tools#easi"` 等連結 → 該錨點不存在,點了落在 /tools 頂端。 | 二擇一:①在 tools.html 補這些工具區塊;②這些 calc 的 cfg 拿掉 `toolsAnchor`(不產生死連結)。**✅ 已修:8 個非-hub calc(easi/poem/ihs4/napsi/vas-pruritus/iga/asis/vasi)移除 toolsAnchor;6 個 hub calc 保留** | gate 綠 | ✅ DONE |
| ~~TD-25~~ ✅ | 計算器死碼/不可達(維護性,非醫療錯誤) | (a) `injectPHQ9` **刻意未接線**(tools.html build note R20 2026-05-14:「PHQ-9 移除」)→ 函式+其 min 檔為死碼;另 dashboard.html 有 `/glossary#dn-phq9` 死連結。(b) 因 `autoInjectCalculators` 硬上限 1/篇(`.slice(0,1)`)只顯示 CALC_ORDER 第 1 個,**永遠排第 2 的 POEM/NAPSI/ASIS 從不 auto-render**,又不在 /tools hub → 實質不可達。 | **✅ (a) 已修(2026-07-08,醫師選「刪除」):移除 `injectPHQ9`(−2317 字元)+ 重生 min;修好 dashboard.html 死連結(改「PHQ-9 量表」純文字)。** (b) POEM/NAPSI/ASIS 非死碼、係 hard-cap-1 設計後果,**降 P3**:未來若要讓其可達,再放進 /tools hub 或調 CALC_ORDER。 | gate 綠 | ✅ PHQ-9 DONE;(b)→P3 |

## Phase 2 — Admin 攻擊面複審(2026-07-08)結論
> 讀了 `api/admin/*`(session/login/logout/popular-picks)、`api/og.js`、`admin/admin-extras.js`、
> `admin/edit.html`、`admin.html` inline JS、8 支 CI workflow、`/admin*` CSP。
> **總結:寫入層安全設計良好,未發現 P0/P1 漏洞**(上一輪「修資安」成果紮實)。
> 詳細評估只在對話回報,不落公開 .md(本 repo .md 會被公開部署)。
> **已於 2026-07-08 加固三項**:(2) `/api/admin/login` 加 KV per-IP rate-limit(10 次/15 分、fail-open);
> (3) `api/og.js` eyebrow 先 uppercase 再 escape(修 entity mangling);
> (5) 新增 `middleware.js` 對 `/admin*` 加可選邊緣 Basic-Auth(**inert:未設 `ADMIN_BASIC_USER`/`ADMIN_BASIC_PASS` 前完全不動作**,不碰 /api 與公開頁)。以下只記非敏感的流程備註:
| ID | 項目 | 說明 | 安全 |
|----|------|------|------|
| TD-26 | 編輯器直寫 GitHub 繞過**本地** gate(#13) | WYSIWYG 用瀏覽器端 PAT 直接 commit 到 GitHub(8 個 `api.github.com` 呼叫)→ 觸發 Vercel 部署;Vercel 不等 CI(`quality.yml`)。內容由可信站長寫入,但**編輯器寫的內容未過本地 `_run_quality.py` 即可能上線**。非漏洞、屬流程取捨。建議:編輯器送出前至少跑輕量前端驗證,或讓 Vercel 部署 gate 在 CI 綠燈後。 | 🟢 流程 P3 |

## Phase 3 — 全庫掃描 + 核心生成器(2026-07-09)結論
> 步驟 0:對 132 支 `_*.py` 跑 bug-class regex(f-string→re.sub、`open()` 無 encoding、bare `except:`、`shell=True`、`C:\Users` 硬路徑、手拼日期)。
> 深讀(按風險序):`_gen_en_pages.py`(1130)、`_gen_feeds.py`、`_normalize_schema.py`、`_normalize_medical_codes.py`、`_normalize_drug_schema.py`、`_normalize_article_metadata.py`、`_minify.py`、`_run_quality.py`、`_normalize_llms_counts.py`、`_normalize_date_modified.py`。
> **整體體質優良**:① `open/read_text/write_text` 全庫 **100% 帶 `encoding=`**(唯二無 encoding 是 `_setup_pagefind`/`_self_host_fonts` 的 `'wb'` binary,正確)→ bug 類 #6 全清;② **無 bare `except:`、無 `shell=True`**(subprocess 全走 list args + timeout + 窄化例外);③ 硬路徑僅在 TD-13 一次性腳本;④ JSON-LD 解析全 `try/except JSONDecodeError` + stderr 警告(歷史上刻意從 bare except 收窄);⑤ 生成器冪等(`build` 兩次 sitemap/生成物零內容 diff 已驗)。
> re.sub f-string(bug 類 #1)複查:管線內 `_normalize_llms_counts` 皆 int/嚴格日期插值(不可觸發)、`_normalize_date_modified` 用 callable replacement(安全);唯一未防護的 `_gen_en_pages.py:987` canonical 已順手修(TD-27)。

| ID | 項目 | 證據/症狀 | 修法 | 驗證 | 安全 |
|----|------|-----------|------|------|------|
| ~~TD-27~~ ✅ | **DONE(Phase 3)** `_gen_en_pages.py:987` canonical 用 f-string 當 re.sub replacement(bug 類 #1) | 正下方 :993 og:url 已改 lambda(guarded),canonical 這條漏改;與本檔 :620 自述「f-string 是最後一個未防護的」不一致。`new_canonical` 來自檔名 stem(無反斜線)→ 當前不可觸發,屬同類潛在缺陷 | **✅ 已修**:改 lambda replacement(callable 回傳值 re.sub 不做反斜線處理),比照 :621/:993 既有守衛。輸出 byte-identical(EN 生成物零內容 diff) | `_check_seo_signals.py` + `build` 兩次冪等 | 🟢 順手修 |
| ~~TD-28~~ ✅ | **DONE(2026-07-10)** `check` 模式漏驗 source/min 同步(bug 類 #14) | `_minify.py` 只在 `POST_BUILD_STEPS`(僅 `build` 跑),不在 `CHECK_STEPS`;但 CLAUDE.md rule 5 的 push 閘只要求 `check`。改了 `blog/*.js` 源檔卻忘跑 `_minify`/`build`、只跑 `check` 就 push → `check` 內 `_check_js_syntax` 只驗語法(舊 min 仍合法)、抓不到 stale min。 | **✅ 已修**:① 新增 `_check_min_sync.py`,對 7 支 bundle 斷言 `js_minify(source)==min`(LF-normalized,見 TD-34);**源檔或 min 缺一即 fail**(否則刪掉源檔會讓 stale min 繼續出貨、audit 卻只比對剩下 6 支而過關);**真正的防空掃**是「`JS_BUNDLES` 不得為空」+ **反向對帳**:每支已提交的 `blog/*.min.js` 都必須在 `JS_BUNDLES` 內(`checked==len(JS_BUNDLES)` 不算守衛 —— 空清單時 0==0 照樣過);② `_minify.py` 抽出 `JS_BUNDLES` 常數當單一真相來源,checker import 它以防清單漂移;③ **`_minify.py` 從 POST_BUILD 移到 `BUILD_GENERATED_STEPS`**——它是生成器,本就該在 checks 之前跑(順帶讓 perf-budget/js-syntax 稽核到本次 build 產生的 min 而非上一次的)。 | 正/負向都驗過:改源不重 minify → exit 1;移走源檔 → exit 1(不再靜默跳過);`build`(改源)→ minify 先跑故通過;全 gate 綠 | 🟢 DONE |
| ~~TD-29~~ ✅ | **(b)(c) DONE(2026-07-10);(a) 刻意保留** 生成器內死碼 | (a) `_normalize_drug_schema.py`:RETRACTED 後 `drug()`/`SLUG_DRUGS`/`serialize_drugs`/`inject` 約 260 行未被 `main()` 呼叫;(b) `_normalize_medical_codes.py`:內層 `replace_about` 定義後**從未被呼叫**(重構改用手動 splice 後殘留);(c) `_normalize_article_metadata.py`:`import sys` 重複兩次 | **✅ (b) 已刪 `replace_about`;(c) 已去重 `import sys`,並順手移除兩檔未使用的 `import io`。(a) 維持保留**(docstring 明載為 GSC WNC-10030322 撤回後的參考實作,要恢復 Drug schema 時需要)。另:全庫尚有 15 支腳本有未使用的 `import io`,純美觀、未掃(避免污染此次 diff)。 | 兩支生成器重跑皆 0 檔異動(冪等未變)+ py_compile + 全 gate 綠 | 🟢 DONE |

## Phase 4 — 驗證器可信度 + 部署基建(2026-07-10)結論
> A. 抽查 7 支驗證器問「它宣稱驗的真的驗到了嗎」:`_check_seo_signals`(747)、`_check_meta`、`_check_sitemap`、`_check_robots`、`_check_api_security`、`_check_frontend_security`、`_audit_jsonld`。
> B. 部署基建:`sw.js`(325)、`vercel.json`、8 支 CI workflows(868)。
> **整體結論:驗證器與基建體質良好,無假綠燈(false-green)、無 P0/P1**。
> - **`_check_robots.py` = 黃金標準**:`REQUIRED_BLOCKED` 刻意寫成獨立硬編碼清單(不從 `_normalize_robots.BLOCK_UAS` import),註解明言避免「同源 shadowing 讓 checker 與生成器連坐縮小」——checker-trust 的正確示範。
> - `_audit_jsonld.py` 真結構驗證、fail-safe;`_check_sitemap.py` canonical/noindex/hreflang 皆真行為驗證。
> - **基建**:CI **無 `pull_request_target`**、actions 全 SHA-pin、per-job scoped permissions、`GITHUB_TOKEN` + `persist-credentials:false`(除需 push 者);`quality.yml` auto-regen 用 `[skip actions]` 防迴圈 + 有界 retry;`scheduled-publish.yml` 輸入驗證紮實(slug regex + branch/file 精確比對 + subprocess list args);`indexnow.yml` 的 `mode` 是 `type:choice` 白名單(注入面中和);`sw.js` cache-poisoning 已由 same-origin+路徑白名單防護。

| ID | 項目 | 證據/症狀 | 修法 | 驗證 | 安全 |
|----|------|-----------|------|------|------|
| ~~TD-30~~ ✅ | **DONE(Phase 4)** `_check_sitemap.py` 從不驗 `<lastmod>`(TD-06 溜進去的缺口) | 該 checker 驗 loc/canonical/noindex/hreflang,但**完全無 lastmod 格式斷言**;`ET.parse` 只對結構壞的 XML 報錯,`<lastmod>garbage</lastmod>` 仍是合法 XML → 壞 lastmod 這支看不到。TD-06 的真正防線是生成器,不是它。 | **✅ 已修**:新增 `valid_w3c_lastmod()`(W3C date/datetime regex + `date.fromisoformat` 拒不可能日期)+ 每個 `<url>` 驗 lastmod 存在且格式有效。單元驗:接受 date/datetime、拒 garbage/2026-13-45/空值;現行 sitemap 63 URL 全過。 | 單元測 + `_check_sitemap.py` 綠 + 全 gate | 🟢 強化 checker |
| ~~TD-31~~ ✅ | **DONE(2026-07-10)** 安全驗證器是「字串契約 regression-lock」,非掃描器(覆蓋比名稱窄) | `_check_api_security.py`/`_check_frontend_security.py` 對**固定檔案清單**斷言特定字串在/不在。缺口:①新增的 `api/admin/*.js` 或前端檔完全不被稽核;②只 forbid 特定舊變數名的 `innerHTML`,新 sink 不擋。**非假綠燈**,屬覆蓋限制。 | **✅ 已補 `_check_dangerous_sinks.py`(廣掃 companion,已入 gate)**:以 glob 掃整個安全面(api/**、admin、前端 JS/**HTML(含 root/blog/en 各頁,inline `<script>`)**、sw、middleware;排除 .min.js)。斷言:(A) `eval()`/`Function()` 建構子/`document.write(ln)`/`.outerHTML=`(**含 `['bracket']` 記法與 `+=`**)**全面禁止**(基線 0);(B) `innerHTML`/`insertAdjacentHTML` **只能出現在已審白名單檔**——新檔用了就 fail,逼人審;(C) `Authorization` 不得內嵌字面憑證(Bearer/token/**Basic**)。(D) **反空掃哨兵**:`REQUIRED_SCANNED` 斷言代表性檔案確實被掃到,glob 壞掉會 fail(單看「掃了幾檔」抓不到漏掉整個類別)。**關鍵:比對前先剝註解**(重用 `_minify.js_minify()`,對字串/regex literal 有感知)——否則 `api/admin/login.js` 註解提到 localStorage、`edit.html`/`blog-shared.js` 的 `javascript:` **防禦性**檢查都會誤報,且 `'https://…'` 會被當成 `//` 註解。**已知極限(誠實標註)**:純詞法掃描,擋不了刻意混淆(`el['inner'+'HTML']`、`Reflect.set`);目標是擋意外回歸與未審新檔,不是擋有 push 權限的惡意提交者。 | 正/負向全測:新檔 innerHTML(含 `['innerHTML']=`、**backtick 記法** ``[`innerHTML`]``)→fail;`eval`/`Function()`/`outerHTML+=`/`document.write`/`writeln`/`document['write']`→fail;字面憑證(含 **backtick 模板 `Basic`**)→fail;註解裡的 eval()+URL 內 `//`、`Bearer ${var}`、**`innerHTML === x` 比較式**→pass;藏掉 `api/og.js`→哨兵 fail;把某 glob 改成不存在路徑→**per-glob 守衛** fail。全 gate 綠(155 檔/89 sites)。**多個自己的 bug 是被負向測試/Codex 抓出來的**:①`writeln?` 實為 `writel`+`n?`,**比不到 `document.write(`**(改 `write(?:ln)?`);②`_Q` 漏 backtick → 模板字串憑證與 ``[`innerHTML`]`` 全漏(補上);③`\s*\+?=` 會把 `innerHTML === x` **當成賦值**誤報(改 `\+?=(?!=)`);④(Codex deep review 追加)`AUTH_LITERAL_RE` 的 `[^\n]{0,40}` **跨不了換行** → 憑證換行寫就漏掃(改 `[\s\S]{0,40}?`);⑤(round-1 我試修 sink-in-string 誤報時)加 `blank_simple_strings` 挖空字串 —— **Codex round-2 抓到這是嚴重回歸**:`el['innerHTML']=x` 的 `'innerHTML'` 是字串,挖空後變 `el['']=x`,bracket-notation sink **反而漏掃(false negative,資安 checker 最不能有的)**。**已還原**:sink 掃描一律跑「字串保留」的原始碼(bracket sink 一定抓得到),把「字串內出現 sink 字樣」列為**文件化的 false positive(fail-safe,寧可誤報不可漏報)**。教訓:安全掃描器的挖空/淨化很容易把真 sink 藏掉,寧可保守誤報。 | 🟢 DONE(2 輪 Codex review)|
| TD-32 | 部署基建 P3 觀察 —— **(a) DONE(2026-07-10);(b)(c) 記錄不修** | (a) ~~global CSP `connect-src` 含 admin 專用 host~~ → **已收斂**;(b) `scheduled-publish.yml` merge→push→Vercel 部署發生在 quality gate 驗證合併結果**之前**(Vercel 不等 CI)= TD-26 同族,draft 為站長可信內容故風險低;(c) `_check_seo_signals` 的 hreflang 互惠檢查 post-D-17 完全 vacuous(「verified on 0 pairs」),屬刻意休眠的 forward-compat 守衛。 | **✅ (a) 已修(使用者授權)**:公開頁只用 `<a href>` 連 pubmed(**connect-src 不管 href**);admin 瀏覽器端實際 fetch 的**只有** `api.github.com`(存檔/上傳走 contents API)、`api.languagetool.org`(拼字)、`eutils.ncbi.nlm.nih.gov`(PMID 引用)。→ **global `connect-src` 縮到 `'self'`+analytics**;3 條 `/admin*` CSP 保留上述三個 host。`uploads.github.com`/`raw.githubusercontent.com` 全庫零引用 → 一併移除。`_check_deployment.py` 同步更新(bug 類 #4):global **forbid** 這些 host、admin **require** 那三個 host(防未來收斂誤殺編輯器);admin 那條是**解析 CSP 後檢查 `connect-src` directive 本身**,不是對整條 CSP 做子字串比對(否則把 host 搬到 `img-src` 也會過關,fetch 仍被擋)。**依賴 Vercel「後匹配 header 覆蓋前者」——Codex 已確認此為 Vercel 實際行為(規則不合併),admin 硬化 CSP 本就建立在此前提。** ⚠️ **本條的第一版差點出事**:我用 `fetch(` 相鄰 regex 判定「沒人 fetch eutils」,漏掉 `admin.html:1090` 是先組 `const url` 再 `fetch(url)` → 會打爛編輯器的 PubMed 引用鈕。**Codex gpt-5.6-sol 擋下**;教訓:查 host 用途要用**裸主機名**掃描 + 逐一分類 href/程式碼,別假設呼叫形狀。 | 雙向負驗:`api.github.com` 塞回 global → fail;admin CSP 拿掉 eutils → fail;還原→綠。全 gate 綠 | 🟡 已上線,**請開一次 admin 編輯器確認「儲存並推送 / 拼字 / 文獻」三鈕正常**;有異狀一個 commit 回退 |

## Phase 5 — 前端核心 runtime(2026-07-10)結論
> 深讀 `blog/blog-shared.js`(2004)、`assets/inline/*.js`、`blog/blog-hub.js`、`blog/pagefind-search.js`;獵殺 `?q=` XSS(#9)、search async 競態(#12)、事件重複掛載、雙語切換殘留、localStorage 守衛、D-11 單一入口、source/min 同步(#14)。
> **整體體質良好、無 P0/P1**:① **`?q=` handler 安全**——query 進 `input.value`(property,非 innerHTML)、render 全程 `escapeHtml`(印證 TD-10);② 雙語 `applyTextOnly` 的 innerHTML(:78)來源是 build 注入的 data-en/zh(author-trusted);③ **無 pageshow/popstate handler → 無 bfcache 重掛**;④ reading-progress / nav-burger 的 localStorage **全包 try/catch**;⑤ **D-11 單一入口未被繞過**——`analytics-loader.js` 是唯一注入 GA/Clarity/AdSense 處,由 `isBot`(完整 BOT_RE)+ internal-page + localhost 三重 gate(且 `_check_third_party` 兜底);⑥ `blog-hub.js` 一致 `escapeHtml`/`safeSlug`;⑦ `pagefind-search.js` 是黃金標準(search+data() 雙階段 requestId re-check + `sanitizeExcerpt` allowlist);⑧ **#14 source/min 全同步**(對乾淨源重跑 `_minify.py`,7 支 `.min.js` 零 diff——無 stale min)。

| ID | 項目 | 證據/症狀 | 修法 | 驗證 | 安全 |
|----|------|-----------|------|------|------|
| ~~TD-33~~ ✅ | **DONE(Phase 5)** `blog-shared.js` runtime 三處硬化 | (a) `detectLang`(:41)`localStorage.getItem` **未包 try/catch**(全站唯一)——storage 完全封鎖(SecurityError)時,因 detectLang 是 `initBlog` 第一步 → 整個互動層(選單/語言/搜尋)全掛;(b) `renderPagefind` 只在 `PAGEFIND.search()` 後 re-check freshness、**`r.data()` 批次後沒有** → 慢查詢的 data() 可覆寫新查詢(#12;對照 `pagefind-search.js` 兩階段都檢查);(c) cmdk `renderPagefind` 的 pagefind excerpt **原樣插入 innerHTML**(`pagefind-search.js` 對等處有 `sanitizeExcerpt`)。 | **✅ 已修**:(a) getItem 包 try/catch;(b) 內層 `.then` 加 freshness re-check;(c) excerpt 改 `escapeHtml(String(m.meta||'').replace(/<\/?mark>/gi,''))`——**先剝 `<mark>` 再 escape**(Codex 指出純 escape 會顯示字面 `<mark>…</mark>`;剝標後 escape 既安全又不露標記,放棄 highlight 守 TD-12,dedicated /search modal 仍 highlight);(d) **順帶修既有 bug**:兩處 freshness check 原比對 raw `input.value` vs 已 lowercase 的 `q` → 大寫英文查詢永遠被丟棄,改 `input.value.toLowerCase().trim()`。 | `_minify.py` + `check-js`(37 檔綠)+ `_check_frontend_security` 綠 + smoke + 全 gate + Codex gpt-5.6-sol APPROVE | 🟢 小修 |
| ~~TD-34~~ ✅ | **DONE(Phase 5)** `_check_performance_budget.py` 量到本機 CRLF、非部署的 LF size | 該 checker(:78)用 `stat().st_size` 量 `blog-shared.min.js` 原始位元組。本機 Windows 上 min 是 CRLF(1443 個 `\r`,+1.4KB),量到 75.0KB(過線 fail);但 git 存 LF、CI/Vercel 服務 LF = **73.6KB(實際在預算內)**。checker 量錯對象(本機 CRLF vs 部署 LF)= checker-trust 缺口。**根因**:`_minify.py`(:168)用 text-mode `open('w')`(無 `newline=''`)在 Windows 寫 CRLF。 | **✅ 已修 checker**:改量 `read_bytes().replace(b'\r\n',b'\n')` 的 LF-normalized size(反映部署產物,CI 上本就 LF 故行為不變)。**根因 `_minify` CRLF 寫入 → P3 記錄**(git autocrlf 已遮蔽 churn;checker 修正後量測已正確,`_minify` 加 `newline=''` 為可選清理)。 | `_check_performance_budget` 綠(73.6KB)+ 全 gate | 🟢 修 checker |

## Phase 6 — 次要 bundles + 總結(2026-07-10)結論
> 深讀 `blog-diagrams.js`(1189)、`blog-article-visuals.js`(664)、`blog-article-reading.js`(604)、`blog-article-footer.js`(596);獵殺同 Phase 5。
> **整體體質良好、無 P0/P1**:① `blog-diagrams.js` **零危險 sink**(純 SVG 生成器,由呼叫端當可信 author 圖插入);② `blog-article-visuals.js` `heroSvg` 是 build/author SVG、lightbox 從點擊的文章 `<img>.src`(property assignment、author 內容)→ 安全;③ `blog-article-footer.js` A/B + newsletter 的 localStorage **全包 try/catch**、innerHTML 皆 author/static、mailto 走 `encodeURIComponent`;④ `blog-article-reading.js` 捲動位置 localStorage 全守衛。

| ID | 項目 | 證據/症狀 | 修法 | 驗證 | 安全 |
|----|------|-----------|------|------|------|
| ~~TD-35~~ ✅ | **DONE(Phase 6)** `blog-article-reading.js` 兩處 | (a) `addFontSizer` 的 `localStorage.getItem`(:523)+ `setItem`(:543)**未包 try/catch**(同 TD-33a 類,storage 封鎖時炸掉字型調整器;此 bundle 其他 localStorage 都有守衛);(b) TOC 用 H2 `textContent`/`id` 拼 innerHTML,`title` 只 escape 引號,但**元素內容 `shown` 與 `href`/`data-toc` 的 `h.id` 未 escape** → 標題含醫學比較運算子(如「PASI < 10」)會讓 TOC 誤渲染(author 內容 → 顯示正確性、非 XSS)。 | **✅ 已修**:(a) 兩處 localStorage 包 try/catch;(b) 加 `esc()` helper,對 `h.id`/`txt`/`shown` 全 escape(對不含 `&<>"` 的標題輸出 byte-identical)。此為 lazy bundle(非 shared,無 TD-12 預算問題)。 | `_minify.py` + `check-js`(37)+ `_check_min_balance` + smoke + 全 gate + Codex gpt-5.6-sol | 🟢 小修 |

---

## 📊 REVIEW_WORKORDER_2026-07 全案總結(6 phases,2026-07-08~10)
> 逐檔讀 code review(非向度稽核),專打驗證器蓋不到的東西。**結論:全站體質優良**——19 計算器公式全對、寫入層安全無 P0/P1、生成器冪等且 encoding/例外處理紀律良好、驗證器無假綠燈、部署基建硬化、前端無 XSS。
>
> **修復統計(全數上線,皆過 Codex review)**:P0 醫療 5 項(Phase 1:TD-20~25 Ludwig/clamp/死錨/揭露/PHQ-9)、生成器 2(TD-06 sitemap lastmod、TD-27 canonical lambda)、驗證器 2(TD-30 sitemap lastmod 斷言、TD-34 perf-budget LF)、前端 runtime 2 組(TD-33 blog-shared ×4、TD-35 reading ×2)。
>
> **待決策(需醫師/使用者)**:
> - **TD-05**(🟡):schema image 全站指向 logo 非真實首圖;根因與工單已備妥,涉 55 篇、需醫師+codex+rich-result 手驗。**使用者已表示暫緩**。
> - **TD-25(b)**:PHQ-9 已刪死碼,POEM/NAPSI/ASIS 因 hard-cap-1 不可達 → 降 P3(未來放進 /tools hub 再解)。
>
> **P2/P3 備忘 → 已於 2026-07-10 執行完畢**(見各 TD 條目):✅ TD-28(`_check_min_sync.py` + `_minify` 移到 build-generated)、✅ TD-31(`_check_dangerous_sinks.py` 廣掃 companion)、✅ TD-29(b)(c)(死碼清理;(a) 刻意保留)、✅ TD-32(a)(global CSP `connect-src` 收斂到 `'self'`+analytics)。**gate 由 28 → 30 步。**
> 仍未動工:TD-34 根因(`_minify` 改寫 LF;checker 已 LF-normalize 故非必要)、TD-32(b)(c)、TD-04(🔴 CSP `script-src 'unsafe-inline'`,需專案級 nonce 重構)、TD-02(🔴 CJK 字型自託管)。
>
> **未發現任何 P0/P1 未修項**;#14 source/min 全同步(無 stale);D-11 單一入口未繞過;CI 無 `pull_request_target`。

## Phase 7(PART2 續審)— 剩餘驗證器 + 供應鏈/外部服務熱點(2026-07-12)結論
> 依 `REVIEW_WORKORDER_2026-07_PART2.md`(V2,Codex 複核過)審上一輪只掃過沒逐行讀的長尾。
> **3 支安全熱點 + 27 支剩餘 `_check_*` 驗證器**。**結論:體質良好,修 3 項供應鏈/覆蓋缺口,無 gate 內假綠燈。**
> 驗證器 sweep:18 支 gate 驗證器結構健康(真 fail path、無吞失敗、抽讀 secrets/supply_chain/third_party/html_escape/inline_events 皆真檢查器);5 支「無 fail path」的**都不在 gate**(readability/link-density/meta_descriptions/links/inline_scripts = 診斷工具,exit-0 是設計、非 vacuous)。
> 外部服務:`_ai_translate.py` API key 只走 env(不落檔/log)、AI 醫療翻譯餵 `/en/` 鏡像 = D-17 的 noindex courtesy MT(制度一致);`_translate_pipeline inject` data-en 有跳脫引號、進 innerHTML 屬全站既有 author-trust 模型。

| ID | 項目 | 證據/症狀 | 修法 | 驗證 | 安全 |
|----|------|-----------|------|------|------|
| ~~TD-37~~ ✅ | **DONE(Phase 7)** `_run_pagefind` 供應鏈:`pagefind@latest` 不釘版 | 該腳本在 `BUILD_GENERATED_STEPS`(每次 `build`/Vercel deploy 跑),`npx --yes pagefind@latest` **不釘版、download-on-demand**,產物 `/pagefind/*.js` **送到訪客瀏覽器**(gitignore 註解:每次 Vercel build 重建)。→ 每次部署拉未審 npm 最新版並上線(供應鏈)。且所有失敗路徑 `return 0`(非致命),`check=True` 抓不到→搜尋索引壞掉也 gate 綠。 | **✅ 已修**:釘 `pagefind@1.5.2`(= pin 時 `@latest` 解析值,凍結現行行為);未來升版要人工審。silent-failure 是**文件化的 graceful degradation**(壞了退回內建搜尋)→ 維持,降 P3。**⚠️ 需你上 Vercel 確認 build 是否真的跑此步**(本機驗不了)。 | py_compile + gate 綠 + `_check_supply_chain` 新鎖負向驗過 | 🟡 供應鏈(釘現版、低風險) |
| ~~TD-38~~ ✅ | **DONE(Phase 7)** `_check_secrets` 覆蓋缺口:不掃 shell/PowerShell/batch | `TEXT_SUFFIXES` 少了 `.sh/.ps1/.cmd/.bat` → 8 支 tracked 腳本(`deploy.*`、`set-domain.*`、`new-article.ps1`、`tools/codex_review.*`、`_setup_pagefind.bat`)**完全不掃 secret**——這些正是硬編碼 token 常見處(TD-31 同類的覆蓋過窄)。 | **✅ 已修**:補 `.sh/.ps1/.cmd/.bat`;實測現有腳本 **0 誤報**。**+Codex round-2**:光補副檔名不夠——`.ps1`/`.bat` 常是 **UTF-16**(PowerShell 預設),原 `read_text(utf-8)` 會 `UnicodeDecodeError` 靜默跳過(覆蓋是假的)。改 `decode_text()` **BOM-aware**(utf-8-sig/utf-16 + NUL 啟發式),且**無法解碼的合格檔改「回報」不「跳過」**(fail closed)。負驗:UTF-16 `.ps1` 藏假 ghp_ token → **抓到**。 | `_check_secrets` 綠 + UTF-16 負驗 + gate 綠 | 🟡 安全覆蓋 |
| ~~TD-39~~ ✅ | **DONE(Phase 7)** `_check_supply_chain` 看不到 npx `@latest` | package.json 釘版檢查**結構上看不到 `npx <pkg>@latest`** 這種 Python 腳本內的調用(TD-37 的缺口即源於此)。 | **✅ 已修**:新增掃描禁 tracked pipeline 腳本內的 `<pkg>@latest`。**+Codex round-2**:原只抓引號式 `"<pkg>@latest"`(Python argv),漏掉 shell/PowerShell 的**未引號** `npx pagefind@latest`(而我現在有掃 .sh/.ps1)。改**先剝行註解**(`#`/`//`,保留換行故行號準)再廣抓 `[\w@./-]*@latest`(涵蓋引號/未引號/npx 各形)+ 排除 checker 自身;`_run_pagefind` docstring 也改寫掉字面 `@latest`(否則 prose 誤判)。負驗:Python `"x@latest"`、shell `npx x@latest`、PS `x@latest` 皆 fail;`# ...@latest` 註解不誤判。 | 三形態負驗 + gate 綠 | 🟢 regression lock |

## P1(值得做,影響真實但不緊急)
| ID | 項目 | 證據/症狀 | 修法 | 驗證 | 安全 |
|----|------|-----------|------|------|------|
| TD-01 | TL;DR 只覆蓋 12/~53 篇 | `grep -rl 'class="dn-tldr"' blog/*.html \| wc -l` = 12 | 分批(每批~10 篇)補 `_inject_tldr.py` 的 map:從該篇 FAQ/首段濃縮 zh 40-80 字+EN;**逐句給醫師審**後 --apply | gate + codex;措辭不得含「根治/cure」 | 🟡 |
| TD-02 | ⏸️ **暫緩(需手動)** 字型未自託管:fonts.googleapis.com render-blocking | 2026-06-15 複驗:仍走 Google Fonts。但 `_self_host_fonts.py` **只自動處理 Inter**;Noto Sans/Serif **TC(CJK)需手動 subset**(全檔數 MB,盲抓有缺字風險)。現行 `display=optional` 已把 FOUT 降到最低,render-blocking 只剩 CSS fetch 一跳 | 若要做:先手動 subset CJK(只含站內用字)→ 改 `_self_host_fonts.py` 產 @font-face → 實機逐頁確認**無缺字**。非弱模型可獨立安全完成 | PSI 手查前後 LCP | 🔴 |
| TD-03 | ✅ **大幅緩解(Phase 2 複審 2026-07-08)** admin 寫入層安全 | 寫入 API 全走 HttpOnly+Secure+SameSite=Strict session cookie(`api/admin/_session.js`:KV+24h+owner allowlist)、PAT shape 驗證、slug 白名單;`/admin*` 有**專屬硬化 CSP**(無第三方 script、connect-src 鎖 GitHub/languagetool/ncbi、frame-ancestors none);DOM 動態值走 `textContent`;CI action 全 SHA-pin、無 pull_request_target。**殘留僅「admin HTML 殼公開可載入」= 標準 SPA、非漏洞**(無 PAT 即無作用)。 | 可選 defense-in-depth:對 admin HTML 殼加 Vercel 邊緣密碼(細節見對話) | Phase 2 複審 | 🟢 可選 |
| TD-04 | CSP `script-src 'unsafe-inline'` | vercel.json 全站 CSP;8 個 inline script + 128 頁 speculation rules 依賴 | 需 nonce 化或外移 inline script 的**專案級重構** — 勿零碎修 | 全站 smoke + 實機 console 無 CSP 錯誤 | 🔴 |
| TD-05 | ⚠️ **仍開啟** og/schema 首圖(Phase 3 已看清根因,寫成工單,未動工) | 實測:og:image **28/55** 用 `/assets/og/<slug>.png`、**27/55** 仍用動態 `/api/og?...`;**JSON-LD `image` 54/55 仍是 `logo-512.png`**。**根因(Phase 3 深讀 `_normalize_schema.py` 找到)**:`normalize_obj`(:278-279)用 `obj.setdefault("image", meta["image"])`——既有 JSON-LD 區塊已內建 `image: logo-512.png`,`setdefault` 永不覆寫 → 停在 logo;且 `page_meta`(:174)image 來源只是 og:image、fallback 也是 logo。 | **可執行工單**:(i) 加 `resolve_article_image(path)` helper,鏡像 `_gen_feeds.resolve_og`——優先 `assets/og/<slug>.png`(磁碟存在)、次 og:image、末 logo;(ii) `normalize_obj` 對 blog 文章改用**直接賦值** `obj["image"]=resolved`(非 setdefault,比照 :291-297 speakable/a11y 的直接賦值註解「so updates propagate to existing blocks」)以覆寫舊 logo;(iii) og:image 這半的收斂另案。 | `_check_seo_signals.py`(現行斷言不辨 logo-vs-真圖,Phase 4 可補配套斷言)+ 分享/rich-result 手查 + `build` 兩次冪等 | 🟡(改 55 檔 schema image;需 codex + 使用者 + rich-result 手驗)|

## P2(小、便宜、可順手)
| ID | 項目 | 證據 | 修法 | 驗證 | 安全 |
|----|------|------|------|------|------|
| ~~TD-06~~ ✅ | **DONE(Phase 3,2026-07-09)** sitemap 文章 lastmod 用 raw catalog date | 實測確認:文章項 `emit_url(out, zh, a['date'], ...)` 直接把 DN.ARTICLES 的 `a['date']` 當 lastmod,**未走 `_parse_date_safe`**(該 guard 原只用在 RSS/Atom pubDate)。畸形日期會產生無效 W3C `<lastmod>`。**✅ 已修:`_gen_feeds.build_sitemap` 兩個文章迴圈(ZH + 保留的 EN 路徑)改走 `_parse_date_safe(a['date'], a.get('slug',''))` .strftime('%Y-%m-%d')。有效日期輸出 byte-identical(sitemap.xml 零 diff),畸形才 fallback today** | `_check_sitemap.py` 綠 + `build` 兩次冪等(sitemap 未變)+ Codex APPROVE | ✅ DONE（Codex 附註:`discover_articles` 仍以 raw `a['date']` 字串排序,畸形日期理論上可影響 feed 排序——非本次範圍、非 regression,若要根治可在排序前也套 `_parse_date_safe`）|
| ~~TD-07~~ | ✅ **DONE**(2026-06-15) title 替換改 lambda | `_gen_en_pages.set_meta` 第 613 行原用 f-string 作 re.sub replacement(description 已修、title 漏改);標題含 `\`+數字會炸。已改 lambda,單元測試:正常標題輸出不變、backslash 標題不再 crash | 當前 en 輸出 byte-identical(無現有標題含反斜線),不需 regen | 🟢 |
| ~~TD-08~~ | ❎ **刻意設計**(2026-06-15 複驗) | sw.js `maybeTrim` 1/5 機率跑 `trimCache` 是**文件化的取捨**(軟 FIFO 上限不必每次寫都做 O(n) 掃描);程式註解已說明。不是 bug | — | — | — |
| TD-09 | desc 檢查:①兩支 checker 窗口不一致(常態 16 WARN,非 blocking)②`en/tools.html` desc 過短(w=112<120) | `_check_meta.py`(字元) vs `_check_meta_descriptions.py`(寬度) | ①以寬度版為準,`_check_meta.py` desc 降 info ②en/tools desc 在 en 生成源加長(反覆 regression,低價值 en 頁) | 兩支跑;Problems→0 | 🟢 低優先 |
| ~~TD-10~~ | ❎ **非缺陷**(2026-07-06 複驗) SearchAction 非 phantom | `blog-shared.js:1728`(2026-05-17 加)已有 `?q=` handler:讀 URLSearchParams `q` → 開 Cmd+K → 預填查詢 → 觸發搜尋。SearchAction 契約已兌現,無需修改。 |
| ~~TD-18~~ | ✅ **DONE**(2026-07-06)about.html ProfilePage `dateModified` 由 date-only 改 full ISO datetime | GSC「dateModified datetime 值無效」警告(/about,ProfilePage rich result 要 datetime)。`_normalize_date_modified` 只跑 blog/*.html(寫 `T00:00:00+08:00`),about.html 在範圍外故停在 date-only。已直接改 about.html;新文章的 breadcrumb 尾斜線 scaffold(new-article.ps1)也一併修。 |
| ~~TD-19~~ | ✅ **DONE**(2026-07-06)breadcrumb JSON-LD `item` 尾斜線 `/blog/`→`/blog` | 每篇 breadcrumb position-2「衛教文章」item 指 `/blog/`(308 轉址)。112 檔 + scaffold 修正,與 D-08 導覽無尾斜線一致。 |
| ~~TD-11~~ | ❎ **非缺陷**(2026-06-15 複驗) | 那 2 個 `Person` publisher 是 `blog/index.html` + `blog/topics.html`(Blog/CollectionPage,本就非文章型);55 篇文章 publisher 一致為 `Physician`。無不一致 | — | — | — |
| TD-12 | blog-shared.min.js 72KB/75KB 逼近 budget 上限 | `_check_performance_budget.py` 基線 | 新功能改放 lazy bundle(blog-hub/diagrams 模式),不進 shared | budget checker | 🟢(規則)|

## P3(知道就好 / 刻意不修)
| ID | 項目 | 說明 |
|----|------|------|
| TD-13 | 一次性腳本寫死舊電腦路徑(`_build_ad_*`, `_fix_ad_articles`, `_extract_pdfs`) | 不在管線內、不會被跑到。要重用時才修(相對路徑化,參考 `_check_balance.py` 的修法)。 |
| TD-14 | 根目錄 ~130 支腳本無資料夾分層 | 大重構風險>收益;命名前綴(_check/_normalize/_gen/_inject)已是實質分層。🔴 除非使用者主動要求。 |
| TD-15 | 生成器無單元測試 | 以「產物驗證器(gate 28 步 CHECK_STEPS)+ 冪等檢查」代償,見 REVIEW_PLAYBOOKS §8。補測試優先級低。 |
| ~~TD-16~~ | ✅ **DONE**(2026-07-01)導覽連結改無尾斜線 canonical。改 `_gen_en_pages`(`en_mirror_exists`+`to_en_path` 支援無斜線目錄)+ zh 導覽 replace + `build` 重生。三支 link checker 全綠、live 200。見 DECISIONS D-08(已推翻原「不修」判斷)。 |
| TD-17 | llms-full.txt 單篇 6000 字截斷 | 刻意取捨(檔案<1MB),截斷處附 canonical URL。勿「修」。 |
| TD-36 | `en/reset-sw.html` 把 `${e.message}` 直接塞進 `innerHTML` | 新的 `_check_dangerous_sinks.py` 掃出來的。該頁是 noindex + robots-disallow 的 SW 重置工具頁,`_check_index_boundaries.py` 明確**要求它存在**(不是孤兒檔,勿刪 —— 我試刪過,gate 當場擋下)。插值只有註冊數(數字)與瀏覽器 Error 訊息,非使用者輸入 → 非 XSS。改 `textContent` 即可,低優先。註:其 zh 版 `reset-sw.html` 已無此 sink(兩版已分歧)。 |

## 內容債(需要醫師,不是純程式)
| ID | 項目 | 狀態 |
|----|------|------|
| CD-01 | 8 個 section-add 草稿待醫師審(`DRAFTS-section-adds.md`) | 審核通過後:轉雙語 HTML+FAQPage schema 注入對應文章 → gate → codex → push |
| CD-02 | 內容路線圖 18 個新文章題目(`CONTENT_ROADMAP.md`) | 依排序寫;每篇必經醫師定稿 |
| CD-03 | TL;DR 其餘 ~40 篇(=TD-01) | 同上 |
