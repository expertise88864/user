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
- 快取修正後 analytics/runtime 32 項、目錄 12 項、資源發布 9 項、導航生成 8 項、admin skeleton 17 項及本機 runtime smoke 通過。新上下文的獨立 Codex `gpt-5.5`／high 已核對 `13ae58b75f4f05472bf9ba43769c13d1cfea4a0e` 的完整 153 檔範圍並 APPROVE；後續日期排序修改仍須重新審查。
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

## 第一批正式驗證與效能修正

- 第一批 SHA：`13ae58b75f4f05472bf9ba43769c13d1cfea4a0e`；[PR #39](https://github.com/expertise88864/user/pull/39)。六個候選 push workflows 全部成功，PR Quality 同內容首次失敗、一次完整重跑成功；保留首次失敗報告。
- [候選 Quality](https://github.com/expertise88864/user/actions/runs/36653078266) 與 [Delivery／Preview](https://github.com/expertise88864/user/actions/runs/36653078214) 成功，完成同 SHA Preview 桌面／手機瀏覽器檢查後正常快轉 main。
- [正式 Delivery／部署與 smoke](https://github.com/expertise88864/user/actions/runs/36654109134) 成功，但 [正式 Quality](https://github.com/expertise88864/user/actions/runs/36654109136) 的首頁 Lighthouse performance 為 61，未達既有 70 門檻。因此第一批交付尚未完成，部署成功不等於 CI 全綠。
- 正式報告首頁 TBT 約 1743 ms、LCP 約 3751 ms，沒有 CPU 校準警告。trace 顯示首屏 layout／paint 與 shared runtime 初始化耗時；不以重跑取代修正。
- 移除 ISO 日期排序的語系 collation 初始化；文章編號維持原排序及同日期次序，首頁／文章推薦使用同一比較契約。新增回歸先重現初始化呼叫，再確認修正後全部編號一致。
- Windows 本機 Chrome 148 對照僅供診斷；Ubuntu CI 使用不同 Chrome／平台，不能把本機分數當成正式 CI 結果。保留插圖及文字排版，未採用改字體或移除插圖的試驗版本。

## GSC 基線重新核對

2026-09-30 在 Search Console UI 重新選取 `https://chendermatologist.com/`，
比較 2026-08-29～09-25 與 2026-08-01～08-28、台灣、網頁搜尋。
UI 同樣顯示總計 233／154 clicks、9383／4887 impressions，頁面表共 95 列；
原 ZIP 的頁面加總 38／23 clicks 仍與總計不一致。已排除重複 CSV 欄名解析、
選錯 property／日期及 1000 列匯出上限的解釋，但尚未證明實際差距原因。
匿名查詢只足以解釋查詢表缺項，不能擅自套用來解釋頁面表。
本次 GA 網頁遇到 DNS 解析失敗，Enhanced Measurement／Clarity 設定仍待核對。

## 日期排序候選結果與生成來源修正

`47cba8b3fc428d141190b4c8d8597913a7586a01`／[PR #40](https://github.com/expertise88864/user/pull/40)：
[push Quality](https://github.com/expertise88864/user/actions/runs/36656624668) 的首頁 performance 80、TBT 489 ms；
[PR Quality](https://github.com/expertise88864/user/actions/runs/36656666505) 的首頁 performance 93、TBT 68 ms。
五個代表頁的 Lighthouse 都通過，兩份報告都沒有 CPU 校準警告。這是 lab 結果，不是搜尋排名或實際 CWV 成效。

兩個 Quality workflow 仍失敗：Canonical consistency 重建 `vercel.json` 時移除了
本機 Lighthouse 報告帶入的兩個額外 CSP 雜湊。已確認是生成器把 Git 忽略的
診斷 HTML 誤當網站來源；並非網站缺少必需腳本雜湊。
修正僅排除四個精確的根目錄診斷資料夾，保留 root／blog／admin／en 的完整來源檢查、
原有腳本數量下限與 CSP 門檻。加入三個先失敗後通過的測試，涵蓋診斷報告不影響輸出、
相似名稱及巢狀公共路徑仍接受檢查、真正文章缺少雜湊仍失敗。
後續新 SHA 須重新跑完整候選 CI／Preview；不沿用此版本的 Lighthouse 成功作為交付證據。

## 首頁初始 DOM 與互動完整性

`c08b9d5b95efa7e0c1a20ddc5902347ac404f3e0` 的生成一致性與 Preview 已成功。
但 [push Quality](https://github.com/expertise88864/user/actions/runs/36657702916)
首頁 performance 65／TBT 1053 ms，仍未達 70；
[PR Quality](https://github.com/expertise88864/user/actions/runs/36657706716)
首頁 performance 83／TBT 228 ms。兩份報告沒有 CPU 校準警告，不能以 PR 綠燈代替候選 push 全綠，也沒有推進 main。

再讀原始 CSS 確認首頁原本已隱藏第 7 張之後的卡片；並非 52 張都在首屏顯示。
舊 CSS 的 6 張與 hub 設定的 5 張不一致，所有卡片仍是 live DOM。
本次改由設定生成初始篇數，其餘卡片保留於原始 HTML 的 inert template，首次搜尋／選主題時一次移入清單。
完整文章索引保持 52 張原生卡片，停用 JavaScript 的首頁仍能從原生「全部文章」連結前往索引。
搜尋、清除搜尋後的日期順序、全部主題與分類篩選保留；作者卡片及 SVG 插圖逐張比較沒有改寫。

本機隔離瀏覽器通過 390／800／1440、ZH／EN、JS／no-JS。
新增 Preview 檢查先搜尋模板內的杜避炎文章，再驗證清除後的原日期順序，避免先展開全部文章掩蓋載入缺陷。
目錄回歸 15 項、analytics/runtime 33 項通過；新增卡片、改變初始篇數、移除模板模式與插圖完整性皆有回歸。
資源版本 `202609301040`，兩個 SW cache generation 同時更新。

Windows Chrome 148 的隔離對照：首次互動前 live DOM 元素 1281 → 551、live 文章卡片 52 → 5；
所有 52 張原始卡片內容仍相同。這個對照沒有證明首屏速度改善：兩次 first paint 約 912／928 ms，處於相近範圍。
首頁仍有初始排版工作，Lighthouse 的實際改善與發布完成條件須由新 SHA 的完整遠端 CI 判定。
未更動字體、文字換行策略、插圖或評分門檻，未採用診斷試驗的視覺版本。

## 閱讀資訊的字數與載入競態

`3cc5b1a0653bca607098a347a46eb4fbcc851cd0` 的六個候選 push workflows 全綠，
[Quality](https://github.com/expertise88864/user/actions/runs/36661328607) 首頁 79／TBT 522 ms、痘痘 78／TBT 415 ms；
[Delivery／Preview](https://github.com/expertise88864/user/actions/runs/36661328744) 成功。
但 [PR Quality](https://github.com/expertise88864/user/actions/runs/36661331560) 首頁與痘痘均為 66，尚未進 main。
首頁 benchmarkIndex 為 1180（候選 2205），其他 PR 頁面約 2467，報告沒有 CPU 校準警告；
這是實際執行差異的證據，不能直接免除失敗或把未查證原因一律稱為 runner 問題。

痘痘失敗報告中 footer bundle 的 script evaluation 約 1012 ms。
程式核對發現字數徽章不必要地初始化 locale formatter，而且先移除所有空白，
會把英文段落的單字合併並低估閱讀時間。徽章另由 footer 加入，footer 較早到達時會因 reading bar 尚未存在而永久漏掉。
本次讓字數與閱讀時間共用保留空白的文本計算，區分中文字數與英文單字；以固定的 ZH／EN 整數分組代替 locale formatter。
字數徽章與 reading bar 一次建立，取消 footer 的第二次掛載及文字重算。
沒有改變前景可見 30 秒＋文章 70% 的有效閱讀門檻。

新增回歸先重現 800 個英文單字被合併成 1 個造成的錯誤；analytics/runtime 共 34 項通過。
隔離瀏覽器在停用 Number locale formatter、阻擋 footer bundle 的條件下驗證 ZH／EN 痘痘與 EN 杜避炎：
閱讀資訊與唯一字數徽章仍出現，重複初始化不重複；新增檢查也接到 Preview。
生成、min sync、部署設定、JS 語法與 runtime smoke 通過；這批採相關本機驗證，完整 CI 仍以新 SHA 的遠端結果為準。
新的資源版本 `202609301115`，兩個 SW cache generation 同時更新，不沿用舊候選的成功證據。
