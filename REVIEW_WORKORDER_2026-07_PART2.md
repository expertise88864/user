# REVIEW_WORKORDER_2026-07_PART2.md — 續審計劃書(Phase 7-9,V2)

> **撰稿**:Fable 5(2026-07-12,只規劃不動工);**V2**:整合 Codex gpt-5.6-sol 對 V1 的規劃複核
> (Codex 抓到 4 個實質規劃問題,已修正:①`_check_*` 數目 ~34→**27**;②Phase 8 太重,拆成 8A/8B;
> ③供應鏈必查點瞄錯檔——真正風險是**在 gate 內、跑 `npx pagefind@latest` 不釘版**的 `_run_pagefind.py`,
> 非 legacy 的 `_setup_pagefind`;④`_translate_pipeline`/`_ai_translate` 不是死歷史——後者帶
> `ANTHROPIC_API_KEY`+呼叫外部 API+寫醫療翻譯,誤排進非目標,已拉回審查)。
> **執行**:Opus 4.8,一 Phase = 一 session。
> **前情**:REVIEW_WORKORDER_2026-07.md 的 6 phase + P2/P3 backlog 已全數完成上線
> (2026-07-11,commit 到 `3f784505`)。那一輪是**價值排序、深讀高風險檔**——已 100%
> 逐行深讀:全部前端 JS(8 bundle + 5 inline + pagefind-search)、全部 admin/api/部署面、
> 19 個計算器、~10 支最高風險管線生成器、13 支關鍵安全/SEO 驗證器。
> **本續篇處理「長尾」**:那一輪只做了 Phase-3 bug-class regex 掃描 + 每次 build 跑綠、
> 但**沒逐行深讀**的 ~80 支活躍管線腳本(~10,300 行)。專打驗證器蓋不到的東西。
> **預算**:使用者 Claude Max 方案,5 小時一個 session 窗口。每個 Phase 設計為
> **一個 session 內可完整做完**(含收工儀式);做不完有中止協議,寫 `N/M` 進度,不硬撐。

---

## 0. 目標與非目標

**目標**(按價值排序,Phase 順序即價值順序):
1. **剩餘驗證器可信度**(**27** 支未深讀 `_check_*`;39 支 − 12 支已審 = 27):假綠燈比沒 checker 更危險。Phase 4 只審了
   security/SEO 那批;其餘只「跑綠」,沒查它們**是否真的在驗它宣稱要驗的**(死斷言、被
   try/except 吞掉的失敗、post-D17 vacuous 斷言、兩支 checker 窗口不一致)。這是本續篇的主戰場。
2. **schema/內容注入生成器**(~25 支 `_normalize_*`/`_gen_*`/`_inject_*`):生成器本身無單元測試
   (TD-15),邏輯錯 = 產物受害。獵殺 bug 類 1-8(同 Phase 3)+ schema @id/頁面實況漂移。
3. **版面正規化 + 建置基建 + 供應鏈**:低-中風險,但 `_setup_pagefind` 的下載/解壓值得看
   (見必查點)。

**非目標**(明確不做,別浪費預算):
- ❌ **一次性/歷史腳本**(`_build_ad_*`、`_fix_*`、`_mirror_*`、`_apply_*`、`_redraw_norwood`、
  `_consolidate_ad`、`_undo_nested`、`_svg_bilingual`、`_table_bilingual`、`_rest_bilingual`…)=
  TD-13/TD-14 已定調「不在管線、不會被跑到,重用時才修」。命中 bug 類只記錄不修。
  ⚠️ **但 `_translate_pipeline.py` 與 `_ai_translate.py` 不算歷史**(Codex V2 更正):前者是
  ONBOARDING.md/TECH_OPTIMIZATION 記載的**現行翻譯工作流**,後者帶 `ANTHROPIC_API_KEY`+呼叫
  外部 API+寫醫療翻譯 → **拉進 Phase 7 審**(見必查點 6)。**教訓:別只看檔名前綴就把腳本歸「歷史」,
  要照文件化/手動進入點盤點(見誠實條款)。**
- ❌ **文章內文**(55 篇 + 64 en 鏡像的 prose)= 醫療文字是醫師的事(D-01);產它們的生成器/
  schema 上一輪已審,inline `<script>` 已被 `_check_dangerous_sinks` 掃過。
- ❌ **已深讀的檔**(上一輪 23 支 `_*.py` + 全前端/admin/api)—— 見進度表「已審清單」,別重跑。
- ❌ 重議 DECISIONS.md;重跑八大領域向度稽核;TD-04(🔴 CSP nonce 重構)、TD-05(🟡 og/schema
  首圖,使用者已暫緩)、TD-02(🔴 字型自託管)等已記錄的大項。

---

## 1. 鐵則(每個 session 都適用;沿用上一輪)

1. **開工儀式**(~10 分鐘):讀 CLAUDE.md → 本檔「進度表」→ 該 Phase 工作包;
   `git fetch` + `git status`,只 fast-forward(遠端常有 CI 的 `auto-regen [skip actions]`,
   有分歧先停下來問,**不裸 `git pull`**);`python _run_quality.py check` 確認 30 步綠燈起步。
2. **發現 ≠ 修復**。所有發現先寫進 TECH_DEBT.md(沿用 🟢🟡🔴 標籤,下一個編號 **TD-37**)。
   只有 **🟢 且有驗證器兜底** 才可順手修;🟡 修完必過 codex+使用者過目;🔴 只記錄、先問使用者。
   **修驗證器本身 = 🟡**(改 checker 需 codex 覆核;假綠燈的反面是「修完反而漏驗」,見上一輪
   TD-31 血淚:我為修誤報把字串挖空,反把真 sink 藏掉=false negative,Codex 擋下)。
3. **push 前必過 Codex GPT-5.6-sol review**——走 repo 的 `tools/codex_review.sh`
   (上一輪已建,read-only、`--ignore-user-config`;背景跑要 `</dev/null` 否則卡 stdin)。
   docs-only commit 也一樣。只 parse 最後一則訊息的 APPROVE/REQUEST_CHANGES。
4. **生成物絕不手改**(PIPELINE.md;`.min.js` 改源檔後跑 `_minify.py`)。改源頭 →
   `python _run_quality.py build` → 兩次冪等 + gate。
5. **收工儀式**:更新本檔進度表(勾選/寫一行結果)→ commit(訊息帶 Phase 編號)→ codex → push。
   Session 快見底時**提前進入收工**,在進度表寫 `HANDOFF:` 一行(讀到哪、剩什麼、下一步)。
6. **預算紀律**:單線深讀為主,**不開平行 subagent 大隊**(Max 額度連坐)。Explore 子代理只限
   「找檔案位置」。**深讀上限約 4,000-5,000 行/session**,超過就是切錯了 → 拆 phase 或中止。
   **驗證器抽查比純讀快**(是「掃斷言 + 問死斷言/吞失敗/vacuous」,非逐行),一 session 可掃 ~20-30 支。
7. **⚠️ 本檔會公開部署**（repo `.md` 皆公開,`/CLAUDE.md` 回 200）。安全類發現寫入文件時
   維持 TECH_DEBT 既有抽象層級(講「哪類問題」,不寫利用步驟);利用細節只在對話向使用者報告。
8. Windows:`python`(非 python3);console 印 CJK 會 mojibake(檔案往返或 UTF-8 wrapper);
   寫檔一律 `encoding="utf-8"`。

---

## 2. 先驗(執行前就知道的事,別重新發現)

**上一輪已 100% 深讀(勿重審)**:
- 前端 JS 全部:`blog/blog-{shared,hub,calculators,diagrams,article-footer,article-reading,article-visuals}.js`、
  `blog/pagefind-search.js`、`assets/inline/*.js`(5 支)。
- Admin/API/部署面全部:`admin.html`、`admin/{admin-extras.js,edit.html}`、`dashboard.html`、
  `api/og.js`、`api/admin/*`(4 支)、`middleware.js`、`sw.js`、`vercel.json`、8 支 CI workflow。
- 管線 `_*.py`(23 支):`_gen_en_pages`、`_gen_feeds`、`_normalize_{schema,medical_codes,
  drug_schema,article_metadata,llms_counts,date_modified}`、`_minify`、`_run_quality`、
  `_check_{seo_signals,meta,sitemap,robots,api_security,frontend_security,internal_links,
  html_balance,deployment,performance_budget,min_sync,dangerous_sinks}`、`_audit_jsonld`。

**本輪範圍(未深讀的活躍腳本,~80 支/~10,300 行,三大類)**:
- **A 類 — 未深讀的 `_check_*` 驗證器(27 支,~2,900 行)+ 3 支安全熱點(pagefind/ai_translate)**:最高價值。
- **B 類 — schema/內容注入 + 次要生成器(~25 支,~4,600 行)**:中價值。
- **C 類 — 版面正規化 + 建置基建 + scaffold(~24 支,~2,800 行)**:低-中價值。

**必查點(Opus 執行時優先確認的具體疑點)**:
1. **`_run_pagefind.py`(供應鏈——真正的活躍風險,Codex V2 更正)**:它在 **`BUILD_GENERATED_STEPS`
   內**(每次 `build`/CI 跑),用 **`npx pagefind@latest`**(**不釘版**、download-on-demand)產搜尋
   索引,且**失敗被當非致命**(npx 不在就 skip)。風險:①`@latest` = 每次 build 拉未釘版程式碼
   (供應鏈:上游被投毒即進 build);②失敗靜默 → 可能上線沒有/舊搜尋索引而無人知。**移到 Phase 7
   早審**(緊鄰 `_check_supply_chain`)。判定:要不要釘一個已知 pagefind 版本 + 失敗要不要更明顯
   (至少 log warning 進 gate 輸出)。legacy 的 `_setup_pagefind.py`(手動 binary 下載、已因
   GitHub release 檔名漂移一直 404、非 gate)只需**快速確認它已不是活躍路徑**,不深究。
2. **`_check_secrets.py` / `_check_supply_chain.py`**(安全類驗證器,Phase 4 沒深讀):優先確認它們
   **真的在驗**(比照 TD-31 揭露的「字串契約 regression-lock、覆蓋比名稱窄」問題)。它們宣稱驗
   secret 外洩/供應鏈,實際斷言範圍多大?有沒有死斷言/被 try-except 吞?
3. **TD-09 已知**:`_check_meta.py`(字元)vs `_check_meta_descriptions.py`(寬度)兩支 desc 窗口
   不一致(常態 16 WARN、非 blocking)。順帶確認 WARN 是否遮蔽了真問題。
4. **`_normalize_citations` / `_normalize_glossary_schema` / `_normalize_mentions` /
   `_normalize_is_based_on`**:這幾支對 HTML/JSON-LD 做 regex 改寫並注入 `@id` 交叉引用——
   bug 類 1-8 的高風險區(regex 對屬性順序/引號/換行的脆弱假設、`@id` 漂移、冪等性)。
5. **`_gen_llms_full` / `_gen_search_index` / `_gen_site_graph`**:產大檔(截斷/編碼/路徑)。
   `_gen_llms_full` 已知 TD-17 單篇 6000 字截斷(刻意,勿修)。
6. **AI 翻譯/外部服務邊界(Codex V2 新增)**:`_ai_translate.py` 讀 `ANTHROPIC_API_KEY`(env)、
   `urllib` 呼叫 Anthropic API、把回傳的**醫療翻譯**寫入檔案;`_translate_pipeline.py` 是現行翻譯
   工作流。查:①API key 有沒有意外落檔/log/commit;②**AI 產出的醫療文字進站前有沒有過 gate/醫師審**,
   還是繞過管線直接寫入(YMYL:AI 幻覺的醫療翻譯直接上線 = 風險);③外部回應未消毒直接進 HTML
   (bug 類 #15)。這是**安全+內容完整性**面,非純風格。

**分級與處置**(沿用 TECH_DEBT):假綠燈驗證器 = P1 🟡(修 checker、codex 覆核);
生成器邏輯錯(產物已受害)= P1 🟢/🟡(有驗證器兜底才順手修);潛在地雷(未爆)= P2 🟢;
供應鏈/建置工具強化 = 🟡 記錄;風格/低價值 = P3 只記錄。

---

## 3. Phase 工作包(價值排序;一個 Phase = 一個 session)

### Phase 7 — 剩餘驗證器可信度 II + 供應鏈/外部服務熱點(最高價值)
- **先做(安全熱點,~3 支,Codex V2 前移)**:`_run_pagefind.py`(必查點 1:`pagefind@latest` 不釘版
  + 失敗靜默,且在 gate 內)、`_ai_translate.py` + `_translate_pipeline.py`(必查點 6:API key /
  AI 醫療翻譯進站是否過審 / 外部回應消毒)。這三支不是 `_check_*`,但風險最高、先清。
- **主體範圍**:上一輪沒深讀的 **27** 支 `_check_*`。**方法**:逐支問三題——
  (a) 它宣稱驗什麼(讀 docstring/檔名意圖)?(b) 斷言真的驗到了嗎(死斷言、被 try/except 吞掉、
  regex 永遠 match/永不 match、post-D17 vacuous「verified on 0 items」)?(c) 跑綠 = 真綠 or 假綠?
- **gate 內(18 支,優先——它們鬆了 push 閘就漏)**:`_check_secrets`、`_check_supply_chain`
  (必查點 2)、`_check_metadata_uniqueness`、`_check_index_boundaries`、`_check_static_a11y`、
  `_check_inline_events`、`_check_pwa`、`_check_nav_critical`、`_check_text_integrity`、
  `_check_en_internal_links`、`_check_third_party`(D-11 單一入口驗證器)、`_check_external_links`、
  `_check_button_types`、`_check_html_escape`、`_check_article_runtime`、`_check_js_syntax`、
  `_check_no_js_render_dependency`、`_check_runtime_smoke`。
- **非 gate(~9 支,次要)**:`_check_balance`、`_check_min_balance`、`_check_articles`、
  `_check_links`、`_check_inline_scripts`、`_check_syntax_residue`、`_check_meta_descriptions`
  (必查點 3)、`_check_internal_link_density`、`_check_readability`。
- **獵殺**:死斷言(`assert True` 類/永真條件)、`except: pass` 吞掉驗證失敗、regex 契約過窄
  (只 match 舊識別字,新寫法漏——TD-31 同類)、post-D17/post-重構的 vacuous 斷言、兩支同領域
  checker 判準不一致(TD-09)。
- **產出**:每支一行結論(✅真綠 / ⚠️假綠+證據 / 🟡覆蓋過窄)寫入 TECH_DEBT。假綠燈 = P1 🟡。
- **中止點**:先做 3 支安全熱點,再掃 27 支 `_check_*`,做到哪停到哪,進度表記「N/27」。優先序:
  安全熱點(pagefind/ai_translate)→ 安全驗證器(secrets/supply_chain/third_party)→ gate 內其餘 → 非 gate。
  **若 3 支安全熱點就吃掉半個 session,`_check_*` 可留到下個 session 補**(記 HANDOFF)。

### Phase 8 — schema/內容注入生成器(中價值;Codex V2 拆成 8A/8B,單 session 吃不下 4,600 行有狀態的 regex/HTML/JSON-LD 改寫)

**Phase 8A — schema/JSON-LD 正規化器(~7 支,最需推理)**:
- **讀**:`_normalize_{citations,glossary_schema,tools_schema,mentions,is_based_on,og_article_meta,
  robots_meta}`。
- **獵殺**:regex 對 JSON-LD/HTML 的脆弱假設(屬性順序/引號/換行)、**`@id` 交叉引用漂移**
  (citations↔is_based_on↔mentions 的 `@id` 對得上嗎)、schema 與 tools/glossary 頁實況漂移、冪等性。

**Phase 8B — 次要生成器 + 內容注入器(~14 支)**:
- **讀**:`_gen_{llms_full,search_index,site_graph,ai_faq,ai_service,faq_from_qa,faqpage_jsonld}`、
  `_inject_{related,tldr,cluster_nav,speculation_rules,404,reading_time,nav_critical}`、
  `_normalize_{articles_desc,ai_well_known,head_extras,robots}`。
- **獵殺**:bug 類 1-8(f-string 進 re.sub、`open` 無 encoding、bare except、`shell=True`、硬路徑、
  手拼日期、HTML escape 缺失、冪等性)、`DN.ARTICLES` 欄位缺失時的行為(KeyError vs 默默跳過)、
  大檔截斷/編碼(`_gen_llms_full` TD-17 刻意勿修)。

- **兩者共通驗證**:改動後 `build` 兩次冪等 + gate;schema 類另跑 `_audit_jsonld`。
- **產出**:TECH_DEBT 更新;生成器邏輯錯 = P1(有驗證器兜底才順手修)。
- **中止點**:8A 先(高推理密度),8B 後;各記 `N/M`。

### Phase 9 — 版面正規化 + 建置基建(低-中價值)+ 總結（供應鏈已移 Phase 7）
- **讀**(~24 支,~2,800 行):
  - 版面/樣式正規化(低風險,快掃):`_normalize_{bilingual_attrs,heading_structure,css_links,
    critical_css,social_urls,social_images,external_links,third_party,button_types,th_scope,
    breadcrumb_aria,ad_slots,analytics}`、`_extract_critical_css`、`_wrap_citations`。
  - **建置基建(中價值)**:`_setup_pagefind`(legacy,只快速確認非活躍路徑——供應鏈已在 Phase 7
    審活躍的 `_run_pagefind`)、`_submit_indexnow`(對外送 URL:注入/隱私)、
    `_self_host_fonts`(TD-02 已知暫緩,只確認)、
    `_convert_images`、`_scaffold_article`(模板 = `blog/semaglutide-hair-loss.html`,scaffold
    與現行決策脫節 = bug 類 #8,上一輪踩過)、`_dashboard`(產 `_dashboard.md`;**注意 .gitignore
    第 51 行已排除、非公開**,但確認它讀寫的路徑)、`_bump_v`、`_bump_svg_text`。
- **獵殺**:同 Phase 8 的 bug 類;對外送出(indexnow)的參數消毒;scaffold 種入被淘汰的標記。
- **總結**(本續篇交付物):
  1. TECH_DEBT.md 全面更新 + 把 TD-37~ 排序。
  2. 給使用者的總結報告(對話輸出):三 Phase 發現分級統計、P0/P1 逐條、需醫師/使用者決策項。
  3. 本檔進度表全勾 + 完成日期。
  4. 更新記憶 [[chendermatologist-institution]]:全庫深讀覆蓋率(續篇後還剩什麼)。

---

## 4. 進度表(Opus 執行時隨做隨更;HANDOFF 寫在該行下方)

- [ ] Phase 7 安全熱點(pagefind/ai_translate,3 支)+ 剩餘驗證器（掃過 ____/27；假綠燈 ____ 支）
- [ ] Phase 8A schema/JSON-LD 正規化器（深讀 ____/7；`@id` 漂移:____）
- [ ] Phase 8B 次要生成器 + 內容注入器（深讀 ____/14）
- [ ] Phase 9 版面正規化 + 建置基建 + 總結（深讀 ____/~21）

> 註:V2 後為 **4 個 session**(7 / 8A / 8B / 9)。若 Phase 7 的 3 支安全熱點 + 部分 `_check_*`
> 就滿一個 session,`_check_*` 剩餘留到額外 session 補——不硬塞。

## 5. 誠實條款(Fable 5 具名標註)
- 行數/支數是 2026-07-12 實測盤點(`wc -l` + 交叉比對上一輪深讀清單);**「一 Phase 一 session」
  是工程估算非保證**——中止協議(記 `N/M`、寫 HANDOFF)才是真正的安全網。
- 本續篇的**邊際效益遞減**:Phase 7(驗證器 + 安全熱點)最值得(假綠燈直接危及 push 閘、供應鏈/
  API key 是真風險);8A(schema `@id`)次之;**8B/9 多是次要生成器與版面正規化,低風險**——做完
  7、8A 若時間/額度緊,9 可只做 scaffold(bug 類 #8 熱區),其餘選做或只記錄。**別為湊完整而燒
  額度審低價值版面腳本**。
- 上一輪 6 phase + P2/P3 已證明:全站體質優良、無未修 P0/P1。本續篇預期**多為「✅真綠/低風險」
  結論 + 少數覆蓋過窄的驗證器**,不預期大缺陷——若某 Phase 掃完全綠,如實寫、別硬找問題。
- 供應鏈必查點(`_run_pagefind` 的 `pagefind@latest`)雖在 gate 內,但產物(搜尋索引)非醫療內容、
  上游是知名專案——寫發現時仍要標明風險等級(釘版建議 vs 實際被投毒),別誇大成 production 事件。
- **V1→V2 的教訓(Codex 規劃複核抓到,具名記錄)**:①別靠檔名前綴推斷腳本活不活躍——`_translate_*`/
  `_ai_translate` 被我誤歸「歷史」,實則是帶 API key 的現行外部服務;正確做法是照**文件化/手動進入點**
  (ONBOARDING.md、WRITING_NEW_ARTICLE.md、TECH_OPTIMIZATION、CLAUDE.md)+ gate 步驟兩邊盤點,
  不只看 `_run_quality.py`。②盤點數字要自我對帳(`_check_*` 我寫 ~34、實為 27)。
  ③單 session 行數上限對「有狀態的 regex/HTML 改寫」要打折(比純驗證器耗推理)——故 Phase 8 拆 8A/8B。
- **本續篇仍是邊際效益遞減的收尾**:主要價值在 Phase 7(驗證器可信度 + 3 支安全熱點);做完 7 若
  額度/時間緊,8A(schema `@id`)次之,8B/9 可選做或只記錄。別為湊完整而燒額度審低價值版面腳本。
