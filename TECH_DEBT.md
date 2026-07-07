# TECH_DEBT.md — 技術債登記簿

> 來源:2026-06 全站架構 review(10 向度稽核 + 對抗式覆核 + Codex 複審)。
> 安全標籤:🟢=弱模型可直接做(有驗證器兜底) 🟡=做完必過 codex+使用者過目 🔴=先問使用者才能動。
> 完成一項 → 改狀態為 DONE 並留一行結果;新發現 → 往下加,沿用格式。

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
