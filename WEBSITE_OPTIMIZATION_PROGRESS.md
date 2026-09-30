# 網站深度優化覆蓋紀錄

更新：2026-09-30。實作基準：`8abf91f23d14204ffb3e1518f55194699844bf4f`。
讀者優先順序：一般民眾／病人，保留專業入口。
編輯優先情境：像 Word 一樣貼上，整理格式與圖片。

這是進行中紀錄。程式閱讀、回歸測試、瀏覽器檢查與正式交付分別記錄；
單次 diff review 不代表整個專案已逐模組完成。

| 模組 | 已有證據與目前實作 | 尚待完成 |
| --- | --- | --- |
| Analytics | 確認延後 GA 導致初始化漏綁；同步事件入口、有限佇列、重複初始化防護；移除搜尋原文，清除 GA 自訂 URL query/hash | GA Enhanced Measurement 設定核對、正式 collector smoke、返回頁面量測 |
| 有效閱讀 | 既有前景可見 30 秒＋文章 70% 門檻；隔離測試保留此契約 | 代表頁及返回情境瀏覽器核對 |
| 首頁／全部文章 | 52 篇公開文章；修正卡片分類缺失／誤分類、切片標籤及中文卡片英文殘留；策展文字移至明確覆寫資料，保留插圖 | responsive、篩選及下一篇旅程瀏覽器驗證 |
| 六篇病人旅程 | 杜避炎、口周皮膚炎、酸類、結節性癢疹、香港腳／灰指甲、皮膚切片；既有 URL／anchor 已盤點 | 第一屏及推薦入口逐頁核對；新增醫療內容逐句核可 |
| 全文章內容 | 公開目錄 52 篇、未發布草稿另計 | 逐篇 metadata／anchor／搜尋索引一致性與閱讀抽查 |
| 搜尋／主題 | 既有空白、多詞、全形查詢與草稿排除回歸測試 | 搜尋成功事件、零結果、鍵盤／手機實測 |
| 雙語 | 保留 EN canonical 指向 ZH 的 D-17 決策；卡片雙語 metadata 檢查 | 完整生成管線、主要瀏覽器實測 |
| 詞彙／工具／圖表 | 現有程式及延後載入邊界已盤點 | 圖表／計算器／詞彙逐模組檢阅及適用回歸 |
| SEO／生成 | 目錄同步增強分類與語言契約；作者覆寫保留於 `_hub_card_overrides.json` | schema、sitemap、描述、日期、索引全量檢查；過期效益宣稱修正 |
| CMS／認證 | 確認普通存檔仍寫 main；已有 immutable snapshot、SHA 衝突及切換保護 | 雲端草稿／候選工作流、伺服端發布門檻、可信發布狀態 |
| Word 式編輯 | 確定先做貼上試點，不預設付費雲端 DOCX | 成熟文件模型評估；長文、表格／引用、SVG／計算器三篇試點及資料保全驗證 |
| 媒體／草稿 | 既有圖片上傳、草稿與配額失敗程式已盤點 | 混貼多圖、順序／alt、IME、undo、斷網、配額失敗實測 |
| PWA／導覽 | 確認修改程式仍沿用舊 immutable URL；改用中央資源版本、更新 SW 快取，新增內容 fingerprint／版本遞移檢查；基準已有 redirect cache 修復 | 舊 SW 升級瀏覽器實測、離線／恢復、正式版本 smoke |
| 效能／可及性 | Lab 及 field 分開；GSC 沒有足夠 CWV field 資料 | 390／800／1440、主要瀏覽器、鍵盤 focus、表格與固定列驗證 |
| GSC／GA4 | 已保存 2026-09-29 分析基線；台灣 28 天 GSC 233 clicks，GA4 日期不同 | 頁面 CSV 38 與國家／裝置 233 clicks 的差距；同日期／條件重新匯出 |
| CI／正式交付 | 採 codex 候選→完整遠端 CI→同 SHA Preview→main→正式 CI／部署／smoke | 獨立 Codex／Opus 5.5 high 唯讀 review 及每批 exact-SHA 證據 |

## 本機驗證

- 2026-09-30：analytics/runtime 原有 31 項通過；Opus 5.5 發現外站 URL 被誤算成站內路徑，新增外站點擊回歸先重現失敗，再修正為保留 absolute origin。
- 2026-09-30：目錄回歸原有 11 項通過；獨立 Codex 發現三張異膚卡片的舊乾癬標籤，新增回歸先重現失敗，再修正覆寫資料，12 項通過。
- 2026-09-30：analytics loader／shared runtime 語法及第三方載入守衛檢查通過。
- 2026-09-30：快取發布檢查新增版本回滾拒絕、雙 SW generation 更新、Windows／Ubuntu 換行一致性、舊量測 loader 遷移與未版本化載入拒絕；導航生成與驗證共用中央版本，保留原有導航功能檢查。
- 2026-09-30：修正本機 Python PATH 後完整 `python _run_quality.py build` exit 0；後續 review 找到的標籤修正使該版本證據失效，最終版本需重新取得對應檢查與遠端 CI。
- 基準 main 的歷史 pending review trailers 已逐 SHA 核對，未解決數量為 0。Opus 5.5 的前兩次實際審查找出外站 URL 與 immutable 快取版本問題，已修正並補回歸；完整最終範圍尚未通過。最新 provider 429 的重置時間為今日台灣時間 13:10，`modelUsage` 空，不能視為通過；補審安排每日 13:15，無待審範圍時停止。
- 快取修正後 analytics/runtime 32 項、目錄 12 項、資源發布 9 項、導航生成 8 項、admin skeleton 17 項及本機 runtime smoke 通過。完整 diff 的 Codex 審查曾因上下文容量不足中斷，需以新上下文重審完整範圍；不沿用較早版本的 APPROVE。
- 上述是本機回歸，不是 GitHub CI、Preview 或正式交付證據。

## 發布與資料保護

- 不納入使用者現有的 AGENTS.md、CLAUDE.md、REMOTE_CI_DELIVERY.md 未提交修改。
- 不更動現有醫療核可、CI 門檻、通知降噪或單一 user-main 資料夾規則。
- 普通編輯存檔不應直接成為正式上線；此項尚待實作，不能宣稱已完成。
- 未新增醫療建議。卡片修正使用既有目錄、既有中文標題與明確策展覆寫。

## 量測設定核對

自訂事件停止收集搜尋原文並清除 URL query／hash。這並不能證明 GA4
Enhanced Measurement 的自動搜尋與 history page_view 已停用；必須另外核對
資料串流設定。[Google 官方說明](https://developers.google.com/analytics/devguides/collection/ga4/views)
明確指出 `send_page_view: false` 不會停用 Enhanced Measurement 的 history page_view。
在完成設定核對前，量測隱私里程碑保持未完成。
Clarity 的 URL 收集也尚未驗證，不能把 GA 自訂事件的修正說成全站所有
collector 都已完成隱私檢查。延後載入期間的事件只存在記憶體；讀者提早離開
仍可能遺失，不能宣稱已消除所有量測漏失。
