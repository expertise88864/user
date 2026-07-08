# REVIEW_WORKORDER_2026-07.md — 完整 Code Review 施工指令書(V2,經 Codex 複核整合)

> **撰稿**:Fable 5(2026-07-07,只規劃不動工);**V2**:整合 Codex GPT-5.5 對 V1 的複核意見
> (Codex 已預先抓到兩個疑似真缺陷,見 Phase 1「必查點」)。**執行**:Opus 4.8,分 session 進行。
> **預算約束**:使用者為 Claude Max $100 方案(5 小時一個 session 窗口)。每個 Phase 設計為
> **一個 session 內可完整做完**(含收工儀式);做不完有中止協議,不硬撐。
> **與 6 月 review 的差異**:6 月是「向度稽核」——跑驗證器、看產物(產出 TECH_DEBT.md)。
> 本次是**逐檔讀 code**——專打驗證器蓋不到的東西:生成器邏輯錯誤、安全面、前端 runtime、
> **醫療計算器公式正確性**(全站沒有任何 checker 驗這個)。

---

## 0. 目標與非目標

**目標**(按價值排序,Phase 順序即價值順序):
1. **全部 19 個**醫療計算器/量表的計分正確性(YMYL:算錯分數 = 直接醫療風險)。
2. 安全面實況(admin 全家桶/api/sw/CI)——含確認 TD-03 是否已過時(`api/admin/_session.js` 已存在)。
3. 管線生成器的邏輯正確性(驗證器只驗產物,生成器本身無測試 = TD-15)。
4. 驗證器本身的可信度(checker 有 bug = 假綠燈,比沒有 checker 更危險)。
5. 前端 runtime JS 的正確性(XSS、雙語切換、事件掛載、search)。

**非目標**(明確不做,別浪費預算):
- ❌ 流量問題(制度已定調:站外權重問題,非程式;見 CLAUDE.md)。
- ❌ 醫療內容文字品質(D-01:醫師的事)。
- ❌ 重跑八大領域向度稽核(REVIEW_PLAYBOOKS.md 已覆蓋,基線 2026-07-07 新鮮)。
- ❌ 重議 DECISIONS.md 任何一條。
- ❌ 大重構(TD-14 資料夾分層等 🔴 項)。

---

## 1. 鐵則(每個 session 都適用)

1. **開工儀式**(~10 分鐘):讀 CLAUDE.md → 本檔「進度表」→ 該 Phase 工作包;
   同步遠端**依 CLAUDE.md 的紀律**(`git fetch` + `git status`,只 fast-forward;有分歧先停下來問,
   **不要**裸 `git pull`);`python _run_quality.py check` 確認綠燈起步。
2. **發現 ≠ 修復**。所有發現先寫進 TECH_DEBT.md(沿用格式與 🟢🟡🔴 標籤)。
   只有 **🟢 且有驗證器兜底** 才可順手修;🟡 修完必過 codex+使用者過目;🔴 只記錄、先問使用者。
3. **生成物絕不手改**(PIPELINE.md 清單;`.min.js` 是生成物——**改源檔後必跑 `_minify.py`**,
   源檔與 min 檔不同步本身就是一個 bug 類)。改源頭 → `python _run_quality.py build` → 兩次冪等。
4. **push 前必過 Codex GPT-5.5 review**(全域規則;D-03)。docs-only commit 也一樣。
5. **收工儀式**:更新本檔進度表(勾選/寫一行結果)→ commit(訊息帶 Phase 編號)→ codex → push。
   Session 快見底時**提前進入收工儀式**,在進度表寫 `HANDOFF:` 一行(讀到哪、剩什麼、下一步)。
6. **預算紀律**:單線深讀為主;**不要開平行 subagent 大隊**(Max 方案額度連坐,平行燒更快)。
   Explore 子代理僅限「找檔案位置」這種小事。深讀上限約 4,000-5,000 行/session,超過就是切錯了。
7. Windows 環境:`python`(非 python3);console 印 CJK 會 mojibake(檔案往返或 UTF-8 wrapper);
   寫檔一律 `encoding="utf-8"`。

---

## 2. 先驗(執行前就知道的事,別重新發現)

**已知開著的 TECH_DEBT(歸屬 Phase)**:TD-05 og/schema 首圖(P3 順手驗)、TD-06 sitemap lastmod
raw date(P3 直接修,🟢)、TD-09 desc 檢查窗口(P4)、TD-12 bundle 逼近上限(P5 順手看)、
TD-03 admin 邊緣驗證(P2 **驗證是否已過時**)。

**bug 類獵殺清單**(#1-8 為本 repo 實證發生過;#9-15 為 Codex 複核補充的高風險類):
| # | Bug 類 | 實例/說明 |
|---|--------|-----------|
| 1 | `re.sub` replacement 用 f-string(backslash 會炸) | TD-07,`_gen_en_pages.set_meta` |
| 2 | 日期解析不設防(畸形日期直接進產物) | TD-06,`_gen_feeds` 文章 lastmod |
| 3 | HTML escape 缺失(內容注入 HTML 時) | TL;DR 注入,codex 退件 |
| 4 | 多檔一致性漂移(政策/計數散在多處) | robots 三檔,codex 兩度退件 |
| 5 | 冪等性破壞(每次 build 產生 diff) | `_inject_related.py` `/blog/` 回寫 |
| 6 | `open()` 無 encoding(Windows cp950 地雷) | 通用風險,逐檔看 |
| 7 | hardcoded 舊電腦絕對路徑 | TD-13,`_build_ad_*` 等 |
| 8 | scaffold 與現行決策脫節(種入被淘汰的標記) | hreflang="en" 殘留 scaffold,2026-07-07 修 |
| 9 | 前端 `innerHTML` 拼接未跳脫、事件重複掛載 | P2/P5/P6 獵殺 |
| 10 | 計算器係數/邊界/四捨五入錯 | 從未被任何機制驗過,P1 主戰場 |
| 11 | HTML `min/max` 屬性沒有對應的 JS clamp(手改 DOM/鍵入超界值照算) | P1 |
| 12 | async 競態:晚到的舊回應覆蓋新狀態(search/admin fetch) | P2/P5 |
| 13 | 瀏覽器端直寫 GitHub(admin)**繞過本地 build/gate** 的路徑 | P2 必查 |
| 14 | 源 JS 與 `.min.js` 不同步(改了源沒重 minify,或反之) | P5/P6 抽查 diff |
| 15 | 外部/API 錯誤字串未消毒直接進 HTML | P2 |

**repo 盤點**(2026-07-07 實測,Opus 不必重新盤):
- 前端:blog-shared.js 2004 行、blog-calculators.js 917(**含 19 個計算器**,不只 tools.html 列的 10 個)、
  blog-diagrams.js 1189、blog-hub.js 692、blog-article-footer.js 596、blog-article-reading.js 604、
  blog-article-visuals.js 664、assets/inline/*.js 共 132、sw.js 325。`.min.js` 全是生成物(勿讀勿改)。
- Admin/後端:api/og.js 158、api/admin/{_session.js 218, login.js 53, logout.js 22, popular-picks.js 111}、
  admin.html 2301(含大量 inline JS)、**admin/edit.html + admin/admin-extras.js 共 1,394(edit.html 393 + admin-extras.js 1,001)**
  (PAT/sessionStorage、GitHub 寫入、rollback、sanitizer——V1 漏列,Codex 補)、dashboard.html 209、
  vercel.json、8 支 CI workflows 共 868 行。
- 管線:`_check_*` 37 支/5,515 行、`_normalize_*` 30 支/5,763 行、`_gen_*` 9 支/2,616 行、
  `_inject_*` 7 支/1,030 行、其他 49 支(含一次性腳本)。合計 132 支/22,705 行。
- ⚠️ 本 repo 的 `.md` 會公開部署(`/CLAUDE.md` 回 200)——安全類發現寫入文件時維持
  TECH_DEBT 既有抽象層級(講「哪類問題」,不寫利用步驟)。

---

## 3. Phase 工作包(價值排序;一個 Phase = 一個 session)

### Phase 1 — 醫療計算器正確性(最高價值,獨立性最高)
- **範圍**:`blog/blog-calculators.js`(917 行)內**全部 19 個**計算器/量表 + 各自所在文章的 UI 區塊:
  tools.html 的 10 個(SCORAD/PASI/DLQI/SALT/UAS7/GAGS/MASI/Hurley/Norwood-Ludwig/Fitzpatrick)
  **加** runtime 另有的 9 個(POEM/IHS4/NAPSI/PHQ-9/VAS-癢/IGA/ASIS/VASI/EASI;Codex 盤出)。
- **方法**:逐計算器三步:(a) 讀 JS 實作抽出公式/係數/範圍;(b) 與下表對照;(c) 邊界值手算驗證
  (最小/最大/中間各一組,含四捨五入與顯示格式)。另驗 #11(JS clamp)與輸入驗證(NaN/空值)。
- **Codex 已預先標出的必查點**(execution 時優先確認,疑似真缺陷):
  1. **Norwood/Ludwig**:`blog-calculators.js:373-402` 男女共用同一個 I-VII 選單,女性結果標
     「Ludwig I-VII」——但 Ludwig 應為 **I-III**。若屬實 = P0 分級錯誤。
  2. **Fitzpatrick**:`blog-calculators.js:433-437` 用兩個序數欄位**取平均**,非標準問卷計分。
     判定:站內文章有無明示這是簡化版?沒有 → 記缺陷交醫師裁決。
  3. **MASI**:程式寫 0-48(`:484,:502`)——**程式是對的**;本表 V1 曾誤寫 0-24(mMASI 才是 24),
     V2 已改正。此條留作「規劃者也會錯,一切以三方對照為準」的示範。
- **公式對照表**(⚠️ 誠實條款:憑訓練知識寫出+Codex 抽核過 SCORAD/PASI/MASI;**執行時仍須與
  站內文章敘述與原始文獻三方對照**;不一致 → 升級醫師裁決,絕不逕改係數):
  | 工具 | 公式/結構 | 範圍 |
  |------|----------|------|
  | SCORAD | A/5 + 7B/2 + C(A=面積0-100;B=6項強度各0-3;C=癢+睡眠 VAS 各0-10) | 0-103 |
  | PASI | Σ 部位係數×(E+I+D)×面積分(頭0.1、上肢0.2、軀幹0.3、下肢0.4;E/I/D 0-4) | 0-72 |
  | DLQI | 10 題各 0-3 直加;「不相關」計 0;**Q7 是兩段式題,計分處理要特別驗** | 0-30 |
  | SALT | 四區掉髮%加權:vertex 40%、posterior 24%、左右側各 18% | 0-100% |
  | UAS7 | 每日(膨疹 0-3 + 癢 0-3)×7 天加總 | 0-42 |
  | GAGS | Σ 部位係數×病灶等級(額2、左右頰各2、鼻1、下巴1、胸上背3;等級 0-4) | 0-44 |
  | MASI | 0.3·A額(D+H) + 0.3·A右頰(D+H) + 0.3·A左頰(D+H) + 0.1·A下巴(D+H)(A 0-6;D/H 各 0-4) | **0-48** |
  | Hurley | I/II/III 定性分期(判準文字對照) | — |
  | Norwood/Ludwig | 男 I-VII;**女 Ludwig I-III**(見必查點 1) | — |
  | Fitzpatrick | 標準為問卷加總後分段 I-VI(見必查點 2) | — |
  | EASI | Σ 部位係數×(E+I+Ex+L 各0-3)×面積分 0-6(成人:頭0.1、上肢0.2、軀幹0.3、下肢0.4) | 0-72 |
  | POEM | 7 題頻率各 0-4 直加 | 0-28 |
  | IHS4 | 結節×1 + 膿瘍×2 + 引流廔管×4(≤3 輕、4-10 中、≥11 重) | 開放 |
  | PHQ-9 | 9 題各 0-3;切點 5/10/15/20;**第 9 題(自殺意念)>0 時必須顯示就醫/求助資源——沒有就是 P0** | 0-27 |
  | NAPSI | 每指甲:甲母質 0-4 + 甲床 0-4(站內是單指甲版或 20 指版?先確認再對) | 0-8/指 |
  | VAS 癢 | 0-10 視覺類比 | 0-10 |
  | IGA | 0-4 定性等級 | — |
  | VASI | Σ 手掌單位面積 × 去色素比例 | 0-100 |
  | ASIS | **規劃者不識此工具**——執行時從站內文章+文獻求證,查不到權威來源就標註並問醫師 | ? |
  - 面積分共用切點(PASI/EASI):0=0%、1=1-9%、2=10-29%、3=30-49%、4=50-69%、5=70-89%、6=90-100%。
- **另驗**:雙語標籤、結果文案是否含療效過度承諾(D-01/D-02 紅線)。
- **產出**:每計算器一行結論(✅正確/❌偏差+證據)寫入 TECH_DEBT;公式錯誤 = **P0、🟡**
  (修復方案先給醫師確認再動)。
- **中止點**:19 個計算器逐一獨立,做到哪停到哪,進度表記「N/19」。優先順序:必查點 1-2 →
  PHQ-9(自殺題警語)→ 有公式的(PASI/SCORAD/EASI/MASI/…)→ 定性分級的。

### Phase 2 — Admin 攻擊面(Codex 補足後,security 拆成 P2+P4 兩塊)
- **讀**:api/admin/ 全部(404 行)→ `admin/admin-extras.js` + `admin/edit.html`(1,394 行;
  PAT/sessionStorage、GitHub 寫入、rollback、文章排序、popular picks、sanitizer、本地草稿)→
  admin.html 的 inline JS(2301 行中的 script 區)→ dashboard.html(209)→ api/og.js(158)。
- **獵殺**:session/token 處理(_session.js:簽章?過期?httpOnly?)、login 暴力破解面、
  PAT 在 sessionStorage 的暴露面、**#13 瀏覽器端直寫 GitHub 是否繞過本地 build/gate**(寫進去的
  內容有沒有過 sanitizer?會不會產生驗證器從沒看過的 HTML?)、og.js 參數注入、
  admin 頁 XSS(#9/#15)、async 競態(#12)。
- **必答題**:TD-03「admin 無邊緣驗證」在 api/admin/_session.js 存在後**還成立嗎**?
  答案寫回 TECH_DEBT(過時就改狀態,附證據行號)。
- **產出**:安全發現一律 🔴 或 🟡(不順手修,涉部署層);TECH_DEBT 更新。

### Phase 3 — 全庫掃描 + 管線核心生成器
- **步驟 0(便宜,先做,結果決定深讀名單)**:對 132 支 `_*.py` 跑 bug-class regex 掃描
  (f-string 進 re.sub、`open(` 無 encoding、bare `except:`、`shell=True`、`C:\\Users` 硬路徑、
  手拼日期字串);命中者進深讀名單。一次性腳本(TD-13 名單)命中只記錄不修。
- **深讀**(按風險序):`_gen_en_pages.py`(1129;歷史 bug 熱區)→ `_gen_feeds.py`(387;
  TD-06 在此**直接修,🟢**)→ `_normalize_schema.py`(515)→ `_normalize_medical_codes.py`(518)
  → `_normalize_drug_schema.py`(337)→ `_normalize_article_metadata.py`(315)→ `_minify.py`(195)
  → `_run_quality.py`(283)→ 掃描命中的其他檔(時間允許)。
- **獵殺**:bug 類 1-8 全套;regex 對 HTML 的脆弱假設(屬性順序/引號/換行)、slug/路徑拼接、
  DN.ARTICLES 欄位缺失時的行為(KeyError vs 默默跳過)、生成 schema 與 tools/glossary 頁實況的漂移。
- **驗證**:改動後 `build` 兩次冪等 + gate;TD-06 修好後 `_check_sitemap.py` 綠。
- **產出**:TECH_DEBT 更新;TD-06 關單;TD-05 若在讀 schema 生成器時看清了修法,寫成可執行工單(不動工)。

### Phase 4 — 驗證器可信度 + 部署基建
- **A. 驗證器抽查**(深讀,問「它聲稱驗的真的驗到了嗎」:死斷言、被 try/except 吞掉的失敗、
  與 D-17 後世界脫節的斷言):`_check_seo_signals.py`(747)、`_check_meta.py`(614)、
  `_check_sitemap.py`、`_check_robots.py`、**`_check_api_security.py`、`_check_frontend_security.py`**
  (Codex 點名:它們是字串契約式安全驗證器、蓋 admin 家族——**它們鬆了,P2 的面就漏了**)、
  `_audit_jsonld.py`。時間剩再加 `_check_internal_links.py`、`_check_html_balance.py`。
- **B. 部署基建**:sw.js(325;cache poisoning、更新機制)→ vercel.json(headers/CSP/redirects;
  TD-04 已知不重報)→ 8 支 workflows(868;secrets 用法、`pull_request_target`、自動 push 迴圈風險)。
- **產出**:假綠燈 = 🟡 修 checker 本身;基建發現多為 🔴 記錄。

### Phase 5 — 前端核心 runtime
- **讀**:`blog/blog-shared.js`(2004;搜尋/Cmd+K/`?q=` handler/雙語切換/主題/目錄)→
  `assets/inline/*.js`(132;analytics-loader 的 bot 過濾與單一入口 = D-11 契約)→
  `blog/blog-hub.js`(692)→ sw 註冊/更新與前端的整合(sw 本體 P4 已讀)。
- **獵殺**:#9(`?q=` 進搜尋框有沒有跳脫?)、#12(search 競態)、#14(抽 2-3 支源檔重跑
  `_minify.py` 比對 min 檔是否同步)、事件重複掛載(pageshow/popstate)、雙語 data-en 切換殘留、
  localStorage try/catch(Safari 隱私模式)、D-11 單一入口有沒有被繞過。
- **產出**:TECH_DEBT 更新;🟢 小修可動(改後 `_minify.py` + `check-js` + smoke)。

### Phase 6 — 次要 bundles + 總結報告
- **讀**:`blog-diagrams.js`(1189)、`blog-article-visuals.js`(664)、`blog-article-reading.js`(604)、
  `blog-article-footer.js`(596)。獵殺同 Phase 5。
- **總結**(本次 review 的交付物):
  1. TECH_DEBT.md 全面更新+重排序(P0→P3)。
  2. REVIEW_PLAYBOOKS.md 若有基線變動就刷新(隨做隨寫)。
  3. 給使用者的**總結報告**(對話輸出即可):發現分級統計、P0/P1 逐條、建議下一步、
     哪些需要醫師/使用者決策。
  4. 本檔進度表全勾 + 標註完成日期。

---

## 4. 分級與處置(沿用 TECH_DEBT 標籤)

| 情況 | 等級 | 處置 |
|------|------|------|
| 計算器公式/係數/分級錯;PHQ-9 無自殺警語 | **P0 🟡** | 立即報告使用者;修復方案經醫師確認才動 |
| 安全漏洞(可遠端利用) | **P0 🔴** | 只記錄+立即報告;不自行改部署層 |
| 假綠燈驗證器 | P1 🟡 | 修 checker 本身,codex 覆核 |
| 生成器邏輯錯(產物已受害) | P1 🟢/🟡 | 有驗證器兜底才順手修 |
| 潛在地雷(未爆) | P2 🟢 | 記錄;便宜就修 |
| 風格/低價值 | P3 | 只記錄,不修 |

## 5. 進度表(Opus 執行時隨做隨更;HANDOFF 寫在該行下方)

- [ ] Phase 1 醫療計算器(N/19:____;必查點 1 Norwood/Ludwig:____;2 Fitzpatrick:____;PHQ-9 警語:____)
- [ ] Phase 2 Admin 攻擊面(TD-03 真相:____;#13 繞過管線:____)
- [ ] Phase 3 全庫掃描 + 核心生成器(掃描命中:____ 支;TD-06 關單:____)
- [ ] Phase 4 驗證器可信度 + 部署基建(假綠燈:____ 支)
- [ ] Phase 5 前端核心 runtime
- [ ] Phase 6 次要 bundles + 總結報告

## 6. 誠實條款(Fable 5 具名標註)

- 計算器公式表憑訓練知識寫出;Codex 抽核了 SCORAD/PASI/MASI 三條並抓到 V1 的 MASI 範圍錯誤
  (0-24→0-48)——**規劃者也會錯**,執行時一律以「程式 vs 本表 vs 文獻」三方對照,衝突歸醫師。
  ASIS 一欄規劃者與 Codex 都未能確認,執行時必須自行查證。
- 「一個 Phase 一個 session」是**工程估算非保證**(Anthropic 未公開精確 token 配額;
  4,000-5,000 行深讀/session 的假設偏保守)。中止協議才是真正的安全網,估算不是。
- 本檔會公開部署(repo .md 皆公開)——安全發現的**細節**寫 TECH_DEBT 抽象層級即可,
  利用細節只在對話中向使用者報告,不落檔。
- Phase 4 的 CI workflows 審查在本機只能讀 YAML 靜態內容,無法驗證 GitHub 端 secrets/權限實況;
  涉及 repo settings 的判斷要標註「需使用者上 GitHub 確認」。
