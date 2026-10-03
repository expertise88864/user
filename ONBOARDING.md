# ChenDermatologist 接手指南

本檔說明現行工程入口，並保留下方明確標示的歷史醫療摘錄。最新狀態以 Git、執行中的流程、完整 SHA 的 CI／部署及版本綁定紀錄為準。

## 接手順序

1. 讀取 `AGENTS.md`、`CLAUDE.md`、`REMOTE_CI_DELIVERY.md`、`DECISIONS.md` 與 `_delivery_policy.json`。較新的使用者定案優先於舊流程文字。
2. `git fetch origin`，核對 main、工作區與遠端。保留使用者及 CMS 修改；整合前確認範圍與衝突，不自行 stash、丟棄或包入提交。
3. 讀取 `.codex-review/patient-growth/` 的最新 checkpoint、handoff、覆蓋及交付證據。核對來源摘要，辨認歷史結果與當前版本。
4. 從實際 commit trailers 核對 pending；只有後續 passed/high 記錄中的完整 `Reviewed-Commit` 能解析相應 SHA。
5. 確認有無正在執行的生成、審查或交付。不要競態開第二個流程。

## 現行網站與來源

靜態 HTML 由 Python／Node 管線產生英文鏡像、搜尋、schema、feeds、runtime 與其他生成物。後台含 Word 式編輯、雲端文章與設定草稿、版本綁定作者申請及發布狀態觀察，相關 API 位於 `api/admin/`。

中文是權威來源，英文索引政策保留 DECISIONS D-17。文章與檔案數、SW 版本和效能門檻應讀取目前來源，不沿用舊 session 的計數。改生成物須修改相應來源並依管線重建。

作者操作見 [AUTHOR_WORKFLOW.md](AUTHOR_WORKFLOW.md)，管線見 [PIPELINE.md](PIPELINE.md)。特殊 SVG／互動區塊保留原稿，Word 系統剪貼簿與手機實機試作須與自動化證據分列。

## 程式、內容與交付

本機快速檢查與相關回歸後，完成指定獨立模型審查，再進 `codex/*` 候選、同 SHA 完整遠端 CI、同庫 PR／Preview／瀏覽器。正常快轉 main 後仍須同 SHA 正式 CI／部署／smoke。

Claude 固定 `claude-opus-5-5`、high、唯讀並核對實際 modelUsage；Codex 依目前專案指定模型及 effort。補審覆蓋完整原始範圍及後續 task-owned 差異。來源改變需重建 packet；額度不足依既有 pending／排程規則處理。

所有醫療文字及英文修改依醫師逐項核可。未核可草稿與確認缺陷保持可追蹤；schema 類型、作者資訊、robots、URL 與英文鏡像政策依 DECISIONS 執行。

Vercel 建置前後須驗證候選及即時作者意圖，定時草稿流程準備候選 artefacts，保存不直接發布 main。不要以取消、逾時、缺失、應跑而跳過或部署成功冒充 CI 通過；保留歷次失敗。

## 量測與閱讀驗收

先固定 GSC／GA4 日期、時區、hostname、品牌分類及資料覆蓋。搜尋點擊與 GA 使用者不是相同指標；圖表與頁面／查詢明細的差距須保留限制。

逐模組記錄程式閱讀、測試、瀏覽器與實機範圍。主要瀏覽器與三寬度的測試、Word 真實貼上、手機 PWA、lab 與 field 各自記錄；完整 diff review 不等於全模組驗收。

網站成效以既有查詢及讀者行為驗證，沒有本站證據時不宣稱固定 SEO 分數、網域等待期、schema CTR 增幅或連結影響倍數。[八週計畫](WEBSITE_EXPERIMENTS.md) 準備素材與量測；工程結案不等待特定流量目標。

## 歷史醫療原則與給付摘錄

以下兩段保留原始歷史文字以便追溯，日期與公告版本均屬當時資料。後續文章需依具體來源與醫師核可重新確認，不能將本段視為目前給付規則或新的醫療核可。

### 4.1 一律遵守的醫學原則（不可違反）

詳見 `~/.claude/projects/...memory/article_writing_spec.md`。重點：

1. 只能根據 user 給的 PDF / guideline / RCT / major journal review 寫
2. 不得使用模型內建知識新增醫學事實
3. 不得捏造數據、副作用頻率、療效
4. 不得把相關性寫成因果
5. 不得把小型回溯性研究寫成「確立治療標準」
6. 來源未提到的 → 標示「需要確認來源」
7. 所有醫學主張要能回推到具體 reference
8. **台灣健保 / 商品名**：獨立查證（食藥署仿單、健保署藥品給付規定、醫院 e-pharm），不可猜 → 用 `data/nhi/derm_2025-04-23.md` + memory 的 `dermnotes_nhi_reference.md` 查
9. Vancouver style references + PMID / DOI
10. 不簡體中文詞彙
11. 不寫成醫療廣告 / 不保證療效 / 不誇大 / 不恐嚇式標題

## 5. NHI 健保條文 — Source of Truth

### 5.1 來源檔

- **完整**：衛福部中央健康保險署「全民健康保險藥品給付規定」114/4/23（2025-04-23）公告版本
- **完整 docx**（6 MB）：`C:\Users\User\Downloads\完整給付規定1150423.docx`，**不放進 repo**
- **皮膚科萃取**：`data/nhi/derm_2025-04-23.md`（170 KB，§6.2.6 + §8.2.4.x + §13.x）
- **memory 速查**：`~/.claude/projects/.../memory/dermnotes_nhi_reference.md`

### 5.2 6 個最常被寫錯的健保事實（一定要知道）

1. **Dupilumab/Upa/Abro AD**：須 **MTX/AZA/CsA 二種**免疫抑制劑 ≥ 12 週失敗（不是「至少一種」）+ 照光每週 ≥ 2 次達 12 週
2. **Upa 與 Abro 擇一**：兩者不能併用、不能換來換去，僅於無法耐受時可互換
3. **AD vs 乾癬暫緩**：AD 生物製劑 1 年、乾癬生物製劑 **2 年**；AD JAK 從 114/6/1 起改為 2 年
4. **HS 健保藥**：目前是 **Secukinumab §8.2.4.14**（2025/7/1 起），**不是 Adalimumab**（已不在 NHI HS 清單）
5. **Baricitinib NHI 範圍**：僅 §8.2.4.13 COVID-19 + §8.2.4.2 RA，**圓禿全自費**
6. **乾癬「PASI 10/10/10 三 10 標準」**：DLQI ≥ 10 是 BAD/AAD 臨床口訣、**非健保條文**。健保 §8.2.4.6.1 只要求 PASI ≥ 10

### 5.3 NHI 章節速查
| 章節 | 藥品 | 適應症 |
|---|---|---|
| §6.2.6 | Omalizumab | **重度持續性氣喘**（不含 CSU！）|
| §8.2.4.6.1 | TNFi/IL-12/23/IL-17/IL-23/JAK | 中重度乾癬 |
| §8.2.4.6.2 | Spesolimab | 急性膿疱性乾癬（113/7/1）|
| §8.2.4.11 | Guselkumab | 掌蹠膿皰症 |
| §8.2.4.13 | Baricitinib | COVID-19 only |
| §8.2.4.14 | Secukinumab | HS（114/7/1 起）|
| §9.55 | Ruxolitinib 口服 | 骨髓纖維化（**不含**白斑、AD）|
| §13.4 | Isotretinoin 口服 | 嚴重痤瘡 |
| §13.10 | Tacrolimus 0.03/0.1% | 中重度 AD 第二線 |
| §13.11 | Pimecrolimus 1% | 中重度 AD 第二線 |
| §13.15 | Permethrin 5% | 疥瘡 |
| §13.16 | Ivermectin 口服 | 鏡檢確診疥瘡（長照住民免鏡檢）|
| §13.17.1 | Dupilumab/Upa/Abro | ≥ 12 歲中重度 AD |
| §13.17.2 | Dupilumab | 6–12 歲 AD（條件較寬）|

### 5.4 已校對 19 篇文章的紀錄

完整紀錄見 `~/.claude/projects/.../memory/project_dermnotes_nhi_audit.md`：包含 4 輪校對的所有具體修正（commits `3e86cc4` → `10c3d75` → `ea11917` → `78406d4`）。

---

## 歷史工程與文章校對紀錄

以下為原 2026-05 session 紀錄，保留原文；不是本輪進度或目前正式交付證據。

## 9. 最近 3 個 session 做的事（context for new window）

### Session `711c0842`（本次，~50 turns）

| 區塊 | 完成內容 | Commit |
|---|---|---|
| 翻譯 | 5 篇 Pattern B 文章全翻譯（dupilumab、AD overview、scabies、oral exam、toenail）+ 修 `_translate_pipeline.py` segmenter | b925b63 |
| NHI 校對（4 輪） | 19 篇文章對 114/4/23 公告版本校對；HS 改 Secukinumab；Baricitinib AA 改自費；CSU Omalizumab 加 caveat；乾癬「10/10/10」迷思澄清 | 3e86cc4 → 78406d4 |
| 新文章 | psoriasis-biologic-monitoring（JAAD 2026 證據評級重新看常規抽血篩檢） | e6162a2 |
| Bundle 瘦身 | blog-shared.min.js 70.3 KB → 61.3 KB（刪 dead code + 搬 CALC_ORDER 到 blog-calculators / markNewArticles 到 blog-hub）| 56913aa |
| SEO 修復 | A+B+C：首頁 title、FAQ + HowTo schema、19 條 meta description、13 orphan link 全修齊 | c328c29 |
| HTML 修復 | 修 orphan-link script 副作用造成的 attribute corruption | 9a6ef64 |

### Session `c388ab63`（前一個）
- 寫了 5 篇新文章（oral exam、scabies、dupilumab、perioral、toenail）
- AdSense 審核期清單
- admin 編輯後台 cache 修復、暫時下架功能

---
