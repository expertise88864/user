# TECH_DEBT.md — 技術債登記簿

> 來源:2026-06 全站架構 review(10 向度稽核 + 對抗式覆核 + Codex 複審)。
> 安全標籤:🟢=弱模型可直接做(有驗證器兜底) 🟡=做完必過 codex+使用者過目 🔴=先問使用者才能動。
> 完成一項 → 改狀態為 DONE 並留一行結果;新發現 → 往下加,沿用格式。

## P0 — Phase 1 計算器逐檔 review(2026-07-08,`blog/blog-calculators.js`;YMYL 最高優先)
> 方法:19 個計算器逐一抽公式/係數/範圍/邊界對照。**19 個的計分公式本身全部正確**
> (SCORAD 103、PASI 72、EASI 72、MASI 48、GAGS 44、UAS7 42、DLQI 30、POEM 28、PHQ-9 27、
> SALT 100%、IHS4、NAPSI 8/指、VASI、VAS、IGA、Hurley 皆與原始文獻一致;bands 亦標準)。
> 以下是公式**以外**的缺陷。**皆未修**(計算器改動涉醫療輸出,一律 🟡:先醫師確認再動)。
| ID | 項目 | 證據/症狀 | 修法 | 驗證 | 安全 |
|----|------|-----------|------|------|------|
| TD-20 | 🔴 **分級錯誤** Ludwig(女性雄性禿)被標成 I–VII | `injectHairScale`(:362-405):性別選 F 時,stage 仍共用同一組 **I–VII** 選單(:373-381),輸出 `'Ludwig ' + roman[s-1]`(:402)→ 女性可得「Ludwig IV/V/VI/VII」,**但 Ludwig 量表只有 I–III**;且 7 個階段描述(:374-380)全是男性 M 型/馬蹄形,**不適用女性**(女性為瀰漫性中央稀疏)。Codex 已預先標出。 | 性別=F 時切換成 3 選項的 Ludwig I–III + 女性專屬描述(需醫師撰寫);男性維持 Norwood I–VII | 手測 F 各級輸出;醫師定稿描述 | 🟡(醫師定案) |
| TD-21 | Fitzpatrick 用非驗證的「取平均」計分 | `injectFitzpatrick`(:433-437):把膚色(1-6)+ 曬後反應(1-6)`Math.round((b+s)/2)` 當型別。**非標準**(標準為驗證問卷加總或臨床判型);矛盾輸入(最白膚色+從不曬傷)會算出中間 Type IV;sub/disclaimer **未標示為簡化版**。 | 二擇一:①明示為簡化啟發式;②改用驗證問卷計分。交醫師裁決 | 醫師定案 | 🟡 |
| TD-22 | 通用 `_buildCalc` 數字輸入**無 JS clamp**(bug 類 #11) | `_buildCalc.readVals`(:242)只 `parseFloat(el.value)||0`,**不夾 min/max**;只有手寫的 SCORAD/SALT/UAS7 的 calc() 有 `Math.max/min` 夾。受影響(number 輸入):PASI、MASI、IHS4、NAPSI、VAS、VASI、EASI — 超界打字(如 0-4 欄輸入 44)**靜默灌高分**。 | 在 readVals 依元素 `min`/`max` 夾值(集中一處修好全部);屬落實既宣告範圍、非改公式 | 手測超界輸入被夾;跑 `_minify.py`+check-js | 🟡(保守) |
| TD-23 | ASIS 自訂嚴重度分級無實證依據 | `injectASIS`(:749-753):ASIS 原為**變化量測 PRO**(無官方 severity cutoff),站上自訂極輕~極重五級 bands。已於 disclaimer 揭露為 12/17 精簡版,但分級切點非來自原量表。 | 改為「追蹤變化」框架,或由醫師定義/背書分級 | 醫師定案 | 🟡 |
| TD-24 | 5 個 in-article 計算器的「查看完整指南 →」連到不存在的 `/tools#` 錨點 | `/tools` hub 只有 10 區塊(scorad/pasi/dlqi/salt/uas7/gags/masi/hurley/norwood/fitzpatrick)。但 EASI/IHS4/VAS-pruritus/IGA/VASI 會實際 in-article 渲染並由 `_buildCalc`(:235)產生 `href="/tools#easi"` 等連結 → 該錨點不存在,點了落在 /tools 頂端。 | 二擇一:①在 tools.html 補這些工具區塊;②這些 calc 的 cfg 拿掉 `toolsAnchor`(不產生死連結) | 手點 5 連結;`_check_internal_links`/link-rot CI | 🟢 |
| TD-25 | 計算器死碼/不可達(維護性,非醫療錯誤) | (a) `injectPHQ9`(:608)**刻意未接線**(tools.html build note R20 2026-05-14:「PHQ-9 移除」)→ 函式+其 min 檔為死碼。(b) 因 `autoInjectCalculators` 硬上限 1/篇(`.slice(0,1)`,:911)只顯示 CALC_ORDER 第 1 個,**永遠排第 2 的 POEM/NAPSI/ASIS 從不 auto-render**,又不在 /tools hub → 實質不可達。 | 決定去留:移除死碼(injectPHQ9 + 相關),或把想保留的工具放進 /tools hub / 調整 CALC_ORDER。**PHQ-9 之去留涉心理健康顯示政策,需使用者/醫師決策** | 移除後 `_minify.py`+check-js+smoke;冪等 | 🟡 |

## P1(值得做,影響真實但不緊急)
| ID | 項目 | 證據/症狀 | 修法 | 驗證 | 安全 |
|----|------|-----------|------|------|------|
| TD-01 | TL;DR 只覆蓋 12/~53 篇 | `grep -rl 'class="dn-tldr"' blog/*.html \| wc -l` = 12 | 分批(每批~10 篇)補 `_inject_tldr.py` 的 map:從該篇 FAQ/首段濃縮 zh 40-80 字+EN;**逐句給醫師審**後 --apply | gate + codex;措辭不得含「根治/cure」 | 🟡 |
| TD-02 | ⏸️ **暫緩(需手動)** 字型未自託管:fonts.googleapis.com render-blocking | 2026-06-15 複驗:仍走 Google Fonts。但 `_self_host_fonts.py` **只自動處理 Inter**;Noto Sans/Serif **TC(CJK)需手動 subset**(全檔數 MB,盲抓有缺字風險)。現行 `display=optional` 已把 FOUT 降到最低,render-blocking 只剩 CSS fetch 一跳 | 若要做:先手動 subset CJK(只含站內用字)→ 改 `_self_host_fonts.py` 產 @font-face → 實機逐頁確認**無缺字**。非弱模型可獨立安全完成 | PSI 手查前後 LCP | 🔴 |
| TD-03 | admin/dashboard 無邊緣驗證(僅 noindex+PAT) | admin.html 公開可達;寫入靠 PAT 但介面裸奔 | Vercel 密碼保護或 middleware Basic-Auth;或搬離 public | 手測 401;`_check_api_security.py` | 🔴(部署層變更) |
| TD-04 | CSP `script-src 'unsafe-inline'` | vercel.json 全站 CSP;8 個 inline script + 128 頁 speculation rules 依賴 | 需 nonce 化或外移 inline script 的**專案級重構** — 勿零碎修 | 全站 smoke + 實機 console 無 CSP 錯誤 | 🔴 |
| TD-05 | ⚠️ **仍開啟(先前誤標 DONE,Codex 2026-07-06 更正)** og/schema 首圖 | 實測:og:image **28/55** 用 `/assets/og/<slug>.png`、**27/55** 仍用動態 `/api/og?...`;更關鍵——**JSON-LD `image` 54/55 仍是 `logo-512.png`**(通用 logo,非真實圖)。所以 og:image 只做一半、schema image 幾乎沒做 | (a) 讓 og:image 全部收斂到 `/assets/og`;(b) schema image 指向真實首圖而非 logo(改 `_normalize_schema` 的 image 來源) | `_check_seo_signals.py`、分享/rich-result 手查 | 🟡 |

## P2(小、便宜、可順手)
| ID | 項目 | 證據 | 修法 | 驗證 | 安全 |
|----|------|------|------|------|------|
| TD-06 | ⚠️ **仍開啟(先前誤標非缺陷,Codex 2026-07-06 更正)** sitemap 文章 lastmod 用 raw catalog date | 實測:文章項是 `emit_url(out, zh, a['date'], ...)`——直接把 DN.ARTICLES 的 `a['date']` 當 lastmod,**未走 `_parse_date_safe`**(該 guard 只用在 RSS/Atom pubDate)。靜態頁那條走 existing_sitemap/today 是安全的,但**文章這條不是**。畸形日期會產生壞 lastmod | 文章 lastmod 也走 `_parse_date_safe(a['date'], a['slug'])` | `_check_sitemap.py`、跑兩次冪等 | 🟢 |
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

## 內容債(需要醫師,不是純程式)
| ID | 項目 | 狀態 |
|----|------|------|
| CD-01 | 8 個 section-add 草稿待醫師審(`DRAFTS-section-adds.md`) | 審核通過後:轉雙語 HTML+FAQPage schema 注入對應文章 → gate → codex → push |
| CD-02 | 內容路線圖 18 個新文章題目(`CONTENT_ROADMAP.md`) | 依排序寫;每篇必經醫師定稿 |
| CD-03 | TL;DR 其餘 ~40 篇(=TD-01) | 同上 |
