# TECH_DEBT.md — 技術債登記簿

> 來源:2026-06 全站架構 review(10 向度稽核 + 對抗式覆核 + Codex 複審)。
> 安全標籤:🟢=弱模型可直接做(有驗證器兜底) 🟡=做完必過 codex+使用者過目 🔴=先問使用者才能動。
> 完成一項 → 改狀態為 DONE 並留一行結果;新發現 → 往下加,沿用格式。

## P1(值得做,影響真實但不緊急)
| ID | 項目 | 證據/症狀 | 修法 | 驗證 | 安全 |
|----|------|-----------|------|------|------|
| TD-01 | TL;DR 只覆蓋 12/57 篇 | `grep -rl 'class="dn-tldr"' blog/*.html \| wc -l` = 12 | 分批(每批~10 篇)補 `_inject_tldr.py` 的 map:從該篇 FAQ/首段濃縮 zh 40-80 字+EN;**逐句給醫師審**後 --apply | gate + codex;措辭不得含「根治/cure」 | 🟡 |
| TD-02 | 字型未自託管:fonts.googleapis.com render-blocking | index.html `<link href="https://fonts.googleapis...">`;`_self_host_fonts.py` 寫好從未套用 | 跑 `_self_host_fonts.py`(先讀腳本確認行為)→ regen → 實機預覽確認字型無 FOUT 惡化 | `_check_third_party.py`、smoke、PSI 手查 | 🟡 |
| TD-03 | admin/dashboard 無邊緣驗證(僅 noindex+PAT) | admin.html 公開可達;寫入靠 PAT 但介面裸奔 | Vercel 密碼保護或 middleware Basic-Auth;或搬離 public | 手測 401;`_check_api_security.py` | 🔴(部署層變更) |
| TD-04 | CSP `script-src 'unsafe-inline'` | vercel.json 全站 CSP;8 個 inline script + 128 頁 speculation rules 依賴 | 需 nonce 化或外移 inline script 的**專案級重構** — 勿零碎修 | 全站 smoke + 實機 console 無 CSP 錯誤 | 🔴 |
| TD-05 | 47/55 篇文章 og/schema image = 站 logo(通用圖) | schema audit 發現;Discover/分享卡吸引力低 | 逐篇產真實首圖(或 `_apply_dynamic_og.py` 動態 OG 已有?先查其覆蓋範圍再決定) | `_check_seo_signals.py`、分享預覽手查 | 🟡 |

## P2(小、便宜、可順手)
| ID | 項目 | 證據 | 修法 | 驗證 | 安全 |
|----|------|------|------|------|------|
| TD-06 | sitemap `<lastmod>` 未用 `_parse_date_safe` 防護(feeds 有) | `_gen_feeds.py` 內兩套日期處理不一致 | 統一走 `_parse_date_safe` | `_check_sitemap.py` | 🟢 |
| TD-07 | `_gen_en_pages.py` title 替換用 f-string 作 re.sub replacement(其他 meta 用 lambda 防護) | 若標題含 `\1` 等序列會炸 | 改成 lambda 形式與其他欄位一致 | regen 後 en/ diff 應僅預期變化 | 🟢 |
| TD-08 | sw.js HTML_CACHE_MAX_ENTRIES=150 只機率性執行 | code review 發現 | trim 改為每次 put 後確定執行 | `_check_runtime_smoke.py`(有 SW 斷言) | 🟢 |
| TD-09 | 兩支 meta checker 的 desc 窗口不一致(字元 vs 寬度) | `_check_meta.py` vs `_check_meta_descriptions.py` 常態 WARN | 統一以寬度版為準,把 `_check_meta.py` 的 desc 檢查對齊或降級為 info | 兩支都跑,WARN 歸零或僅 title 類 | 🟢 |
| TD-10 | WebSite SearchAction 指向無處理器的 `/?q=` | schema audit | 指向 pagefind 實際入口或移除 SearchAction | `_audit_jsonld.py` | 🟢 |
| TD-11 | publisher 實體表述不一致(Physician vs Person 混用) | schema audit(96/110 篇) | `_normalize_schema.py` 統一 publisher=同一 @id | `_audit_jsonld.py` 0 errors + 冪等 | 🟡 |
| TD-12 | blog-shared.min.js 72KB/75KB 逼近 budget 上限 | `_check_performance_budget.py` 基線 | 新功能改放 lazy bundle(blog-hub/diagrams 模式),不進 shared | budget checker | 🟢(規則)|

## P3(知道就好 / 刻意不修)
| ID | 項目 | 說明 |
|----|------|------|
| TD-13 | 一次性腳本寫死舊電腦路徑(`_build_ad_*`, `_fix_ad_articles`, `_extract_pdfs`) | 不在管線內、不會被跑到。要重用時才修(相對路徑化,參考 `_check_balance.py` 的修法)。 |
| TD-14 | 根目錄 128 支腳本無資料夾分層 | 大重構風險>收益;命名前綴(_check/_normalize/_gen/_inject)已是實質分層。🔴 除非使用者主動要求。 |
| TD-15 | 生成器無單元測試 | 以「產物驗證器 31 支 + 冪等檢查」代償,見 REVIEW_PLAYBOOKS §8。補測試優先級低。 |
| TD-16 | `/blog/`、`/en/` 導覽連結帶尾斜線 → 308 一跳 | Google 正常跟隨,純美觀。修它要動 EN 鏡像 link rewriter,風險>收益。刻意不修(DECISIONS D-08)。 |
| TD-17 | llms-full.txt 單篇 6000 字截斷 | 刻意取捨(檔案<1MB),截斷處附 canonical URL。勿「修」。 |

## 內容債(需要醫師,不是純程式)
| ID | 項目 | 狀態 |
|----|------|------|
| CD-01 | 8 個 section-add 草稿待醫師審(`DRAFTS-section-adds.md`) | 審核通過後:轉雙語 HTML+FAQPage schema 注入對應文章 → gate → codex → push |
| CD-02 | 內容路線圖 18 個新文章題目(`CONTENT_ROADMAP.md`) | 依排序寫;每篇必經醫師定稿 |
| CD-03 | TL;DR 其餘 45 篇(=TD-01) | 同上 |
