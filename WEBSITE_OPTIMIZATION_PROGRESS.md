# 網站深度優化覆蓋紀錄

更新：2026-10-01。實作基準：`8abf91f23d14204ffb3e1518f55194699844bf4f`。
讀者優先順序：一般民眾／病人，保留專業入口。
編輯優先情境：像 Word 一樣貼上，整理格式與圖片。

這是進行中紀錄。程式閱讀、回歸測試、瀏覽器檢查與正式交付分別記錄；
單次 diff review 不代表整個專案已逐模組完成。

最新狀態：全 Goal 尚未完成。正式 main 為 `6c6814d607c7ecd07d84430b95a3e3390eff6982`。
這批已完成同 SHA 的六個候選 push workflows、六個 PR workflows、Preview／瀏覽器與正常
快轉 main；正式六個 workflows、部署及 Production smoke 都成功。
正式 [Quality 36795557873](https://github.com/expertise88864/user/actions/runs/36795557873)、
[Delivery 36795557919](https://github.com/expertise88864/user/actions/runs/36795557919) 可核對。
新增版本草稿、Word 編輯及發布狀態觀察的工程程式已上線；這不代表已替作者實際發布文章，
也不代表真實 Word 剪貼簿、全部醫療內容或全專案已驗證完。
八個精確 pending commit 的 Opus 完整補審仍待額度；最新 provider 重置為
2026-10-01 台灣時間 09:10，既有本機排程 09:15 重試，須開機並登入。
計算器輸入與標籤修正目前為本機工作，尚未取得新 SHA 的交付證據。
以下表格記錄目前覆蓋，後面各節保留歷次檢查與失敗；舊候選失敗屬歷史紀錄，
不能沿用舊版本證據核可新差異。

| 模組 | 已有證據與目前實作 | 尚待完成 |
| --- | --- | --- |
| Analytics | 確認延後 GA 導致初始化漏綁；同步事件入口、有限佇列、重複初始化防護；移除搜尋原文，清除 GA 自訂 URL query/hash | GA Enhanced Measurement 設定核對、正式 collector smoke、返回頁面量測 |
| 有效閱讀 | 既有前景可見 30 秒＋文章 70% 門檻；隔離測試保留此契約 | 代表頁及返回情境瀏覽器核對 |
| 首頁／全部文章 | 52 篇公開文章；修正卡片分類缺失／誤分類、切片標籤及中文卡片英文殘留；策展文字移至明確覆寫資料，保留插圖 | responsive、篩選及下一篇旅程瀏覽器驗證 |
| 六篇病人旅程 | 杜避炎、口周皮膚炎、酸類、結節性癢疹、香港腳／灰指甲、皮膚切片；既有 URL／anchor 已盤點 | 第一屏及推薦入口逐頁核對；新增醫療內容逐句核可 |
| 全文章內容 | 52 篇逐篇分類／metadata／URL／搜尋／sitemap 結構核對；134 HTML 內鏈及 413 JSON-LD 檢查通過，anchor 數量留存 | 逐篇內容閱讀與關鍵旅程 anchor 的語意／瀏覽器驗證；醫療文字與三項長度提醒核可 |
| 搜尋／主題 | 既有空白、多詞、全形查詢回歸；共同目錄解析器及 noindex／下架／隱藏文字保護新增十項回歸；主要 Pagefind 搜尋套用相同可見性規則，保留兩篇專業入口 | 搜尋成功事件、零結果、鍵盤／手機實測；完整生成後的同 SHA 候選驗證 |
| 雙語 | 保留 EN canonical 指向 ZH 的 D-17 決策；卡片雙語 metadata 檢查 | 完整生成管線、主要瀏覽器實測 |
| 詞彙／工具／圖表 | 計算器完整 924 行及 18 個元件檢閱；修正空白／範圍／step 驗證、HairScale 標籤與 DLQI registry 入口；三引擎各三寬度、960 個無效輸入案例及有效結果契約通過 | 本批新版本獨立 review／完整交付；完整文章／工具頁與詞彙／圖表覆蓋、實機與輔助科技驗證 |
| SEO／生成 | 全量 schema／sitemap／描述／索引檢查；九個模組效益宣稱校正；52 篇、104 份中英文頁面日期與作者帳冊一致，全部為發表日基準 | 醫師實際重新審閱日期的核可來源；完整生成與正式 CI；不把發表日當近期審閱 |
| CMS／認證 | 本機文章雲端草稿、immutable snapshot／blob bytes、SHA 衝突及切換保護；版本綁定作者申請、獨立源碼 bundle 準備及伺服端交付門檻；exact-main 正式 CI／部署觀察入口；新版草稿／可還原本機快照在隔離環境實作驗證並隨 6c6814d 正式交付 | 生成內容核可一致性、已發布證據退役、雲端設定與其餘衝突 UI；正式認證作者 API 操作驗證 |
| Word 式編輯 | 成熟文件模型已接入實際後台；三引擎各 52 篇內容往返、特殊區塊保護及 390／800／1440 後台流程通過 | 真實 Windows Word 剪貼簿、實機 iOS／Android、其他格式操作；Opus 完整補審（工程已隨 6c6814d 正式發布） |
| 媒體／草稿 | 批次圖片來源準備、魔術位元組／尺寸／摘要驗證、rollback；圖文混貼、多圖、alt／順序、undo／redo 與草稿恢復；Chromium 原生 IME 回歸 | 真實外部剪貼簿與實機長文操作；正式 API／候選流程中的斷網、配額與衝突回復 |
| PWA／導覽 | 中央資源版本及 SW 快取／fingerprint 遷移；13ae → 452 的双分頁原生升級、清除舊快取、文章導覽、實際伺服器斷線／恢復在三引擎通過；Chromium／Firefox 離線旗標通過；52 卡片及查詢／篩選／零結果／清除已測 | WebKit 離線旗標模擬仍有内部導覽錯誤，不能代表實機 Safari；安裝 PWA／實機離線、其他工具模組及正式 smoke |
| 效能／可及性 | Lab 及 field 分開；GSC 沒有足夠 CWV field 資料 | 390／800／1440、主要瀏覽器、鍵盤 focus、表格與固定列驗證 |
| GSC／GA4 | 已保存分析基線；台灣 28 天 GSC 233 clicks，GA4 日期不同；同條件 reload 前後六份 CSV 位元組相同 | 頁面 CSV 38 與國家／裝置 233 clicks 的差距仍未釐清；GA 設定及日期口徑核對 |
| CI／正式交付 | 採 codex 候選→完整遠端 CI→同 SHA Preview→main→正式 CI／部署／smoke | 獨立 Codex／Opus 5.5 high 唯讀 review 及每批 exact-SHA 證據 |

## 本機驗證

### 2026-10-01 計算器輸入及工具入口（本機驗證，尚未發布）

- 以正式 6c6814d 的原始碼，在 Chromium／Firefox／WebKit 重現十個數值元件接受空白或超範圍後仍显示結果；HairScale 兩個選單欠缺關聯標籤。新增共用輸入驗證，保留輸入值供修正，不再以零值或邊界值悄悄代替；有效輸入才計算。錯誤標示、可讀提示及動態結果狀態已接入，未改既有公式、臨床解讀、預設值或限制。
- 原先工具頁的 DLQI 入口指向 `/blog/dermatology-faq#dn-dlqi`，registry 指定載入但元件自身白名單忽略 registry 的 force 旗標。使用實際 dispatcher 重現舊版零個元件；修正後出現十個問題的 DLQI 元件，force 旗標正常釋放。
- 三種原生瀏覽器各在 390／800／1440 驗證 18 個元件，960 個空白／上下界／step 無效案例、修正後恢復、鍵盤操作、標籤、隔離事件及 DLQI dispatcher 通過。有效預設／最小／最大／中間值與固定舊版輸出摘要一致；這是維持既有行為，不是醫療公式正確性核可。未使用正式 collector，也未把隔離 DOM 當成全部文章、實機或輔助科技驗證。
- 新回歸已加入 Preview 瀏覽器入口；資源版本及 SW 快取同步遞增，由原管線生成。完整新版本 review、候選遠端 CI／同庫 PR／Preview、main 正式 CI／部署／smoke 仍須逐版取得證據，舊 6c 的全綠不能替本批核可。


### 2026-10-01 新候選與 Preview 建置修正（進行中）

- 81 個工程檔完成獨立 `gpt-5.5`／high 唯讀審查的完整增量組合，保留原 `REQUEST_CHANGES` 與修正證據。隔離的完整 `build`／check／postbuild smoke exit 0（181 Python、274 Node）；原本機目錄的私人診斷 HTML 未混入候選。
- 正常推送 `9aa4277` 到既有候選分支及 [PR #40](https://github.com/expertise88864/user/pull/40)，未推 main。[push Quality](https://github.com/expertise88864/user/actions/runs/36783551824) 的四個其他 jobs 成功，首頁 Lighthouse 63 未達 70；[Delivery](https://github.com/expertise88864/user/actions/runs/36783551866) 因 Preview 失敗無法取得成功瀏覽器證據。其他適用 push workflows 成功，不代表候選全部通過。
- [Vercel Preview](https://vercel.com/expertise88864s-projects/chendermatologist/31MAFS4xSghaNo6QuhqotwkAwRHc) 在 Pagefind 建置退出碼 2。現有輸出篩選隱藏了小寫 `error:`；本機以實際 npx／Bash 重現 brace 清單展開後的 `unexpected argument 'dashboard.html'`，相同來源用原 Windows shell 成功 125 頁。
- 修改 `_run_pagefind.py`，把相同、已驗證的可見頁清單經官方支援的 `PAGEFIND_GLOB` 子程序環境傳入；覆寫繼承值但不更動父程序設定。Bash 診斷成功索引相同 125 頁；新增真實 npx／Bash 公開與排除頁回歸、父環境不變及失敗診斷測試，共 8 項通過。[Pagefind 官方設定](https://pagefind.app/docs/config-options/)
- 這項新修正尚未取得新 SHA 的遠端 CI／Preview，不能把本機重現等同於 Vercel 已修復。既有 Node／依賴版本、noindex／未發布可見性、超時與失敗退出門檻都保留。
- 首頁卡片 layer／transition／標誌動畫的七次成對本機診斷沒有明顯改善，未採用為效能修正；Lighthouse 問題仍待可驗證的根因處理。

### 2026-10-01 Word 編輯器安全邊界修正（候選驗證）

- 實際瀏覽器重現文章 CSS、`srcset` 與舊式表格 `background` 載入外部資源；原始來源改為受保護區塊，保留原始位元組，避免在登入後的編輯區啟用。
- 移除自寫 Word／草稿視窗的 `innerHTML` 指派。ProseMirror 剪貼簿解析剩餘一處在無 browsing context 的文件內；完整掃描保留，生成檔另以一處 sink 數量與確切 SHA-256 綁定，任何變動須重新審查。
- 首次可讀的獨立 Codex 審查為 `REQUEST_CHANGES`：新增 `image-set()` 與實際 drop 路徑測試，前者已重現外部請求，後者重現舊版會先解析貼上 HTML。修正 CSS 函數保護及 `handleDOMEvents.drop` 解析前攔截；最終獨立審查 `WORD_SECURITY_INCREMENT_APPROVE`，實際 model／effort／唯讀 metadata 已核對。
- 最終三引擎各 20 組來源、20 組貼上事件、實際 drop、52 篇文章往返與 390／800／1440 後台流程通過；以上 81 檔候選完整本機建置亦通過。生成 license 尾端空行及本機 AdGuard 的 close-response smoke 問題另有最小修正、回歸與獨立審查；沒有停用 AdGuard 或降低檢查門檻。
- 貼上事件使用隔離合成剪貼簿，Firefox 測試明確提供 event data；尚非 Windows Word OS 剪貼簿測試。所有外部目的地攔截，未寫正式內容或遙測。
- 全 Goal、Claude Opus 補審、exact-SHA 遠端 CI／Preview／main／正式部署仍未完成。

- 2026-10-01：完整 build 的生成階段完成，實際搜尋 Pagefind、Word bundle、minify、資源 fingerprint／CSP 都已執行；既有 75 個工作來源摘要完全未變。檢查階段因三項發布測試仍解析已移除的舊排程 heredoc 而失敗，不能稱完整 build 通過。
- 改為執行目前工作流程的真正 Python CLI，使用隔離 Git fixture 驗證 source bundle、文章／圖片位元組、準備失敗及未追蹤生成物拒絕。12 項發布回歸通過；保留原失敗日誌，未移除測試、降低門檻或執行 hosted 寫入。
- 修正後的完整 check 再次執行，停在 metadata uniqueness：兩份本機首頁對照 HTML 位於忽略的審查證據資料夾，被全目錄掃描當成重複網站頁面。保留證據及失敗；後續以不含私人診斷檔、但包含全部實際候選來源的隔離 checkout 驗證，不能把目前本機目錄檢查說成全綠。
- 2026-10-01 04:35 完整 Opus 補審實際執行 39 turns；`modelUsage` 確認 `claude-opus-5-5`，唯讀工具沒有 permission denial，但中途 session limit、exit 1／`is_error=true`，未取得完整核可。不能用結果中的 `subtype=success` 或部分讀取當作 APPROVE。
- Search Console 重新下載同日期／台灣／網頁搜尋報表，reload 前後六份 CSV member 位元組相同；頁面 95 列合計 38／23，國家及三種裝置仍為 233／154。差距尚未釐清；不把頁面明細和全站總計混為同一口徑，也不把搜尋點擊當成所有訪客。GA4 錯誤頁受到瀏覽器 URL 協定安全政策拒絕，量測設定仍未核對，未繞過限制。

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
- 本機 CMS 的普通文章存檔已改為雲端草稿；正式站仍需通過候選與正式交付流程。雲端設定、生成核可及部署中的實際 API 尚未完成驗證，不能宣稱 CMS 改版已正式完成。
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

## 最新候選與草稿工作進度

`89d58e23a8d37eb014efd1c44e54d70ae9892fc8` 的 [候選 Quality](https://github.com/expertise88864/user/actions/runs/36663666458)
及 [PR Quality](https://github.com/expertise88864/user/actions/runs/36663669635) 都只有首頁 Lighthouse 未達門檻，
分別 63／64；痘痘文章 87／88，其餘代表頁通過。生成一致性及其他適用 workflows、
[同 SHA Preview](https://github.com/expertise88864/user/actions/runs/36663666446) 成功。
尚未推 main，不以這些局部成功宣稱完整交付。

首頁對照試驗移除字型網路、template 解析或 content-visibility，都未證明 first paint 明顯改善；
沒有套用這些試验版，也沒有降低 Lighthouse 門檻或重跑來挑綠燈。
trace 有長任務的 wall duration 遠高於 thread CPU duration 的現象，實際等待原因仍需查明，
不能把全部成本歸因網站 JavaScript 或直接當作 runner 問題免除。

2026-09-30 13:11 的完整 Opus 補審範圍是基準 8ab → 89 的 164 檔逐字差異。
`modelUsage` 證明實際 `claude-opus-5-5`，但審查途中 session quota 耗盡，沒有 APPROVE。
provider 回報台灣時間 18:10 重置；專案补審改到 18:15，電腦需開機並保持登入。
新加入的草稿模組不在那份舊 snapshot 中，後續完整交付審查必須包含它們。

草稿工作已新增 `api/admin/article-draft.js` 與 `admin/article-drafts.js`：
固定 repository／article path、HttpOnly session、同源寫入、讀取時的 expected-head、
main blob 衝突保護、非 force ref 更新、完整 HTML／圖片／manifest 同一提交，
以及 accepted immutable content 驗證。舊草稿未被自動覆寫；網路結果不明不重複寫入。
圖片先留本機，草稿讀取可顯示尚未正式上線的圖片；圖片大小以整個保存後 bundle 計算，
避免增量存檔成功但下一次重讀超過限制。異版本本機草稿保留內容且禁止自動覆寫雲端。
隔離 server／client 回歸共 25 項通過，已接入既有 quality 檢查。
新增回歸另確認保存後的 immutable manifest 與所有圖片，再回報 verified；
不只驗證文章文字。既有相鄰 Node 回歸 148 項通過，之後新增的兩項只重跑受影響草稿測試；
上述是本機結果，不是完整遠端 CI。

獨立 `gpt-5.5`／high／read-only 的草稿 component review 找出非 JSON 閘道回應缺乏清楚錯誤處理；
已修正、增加成功／失敗 HTTP 非 JSON 回應測試，保留版本並顯示保存結果未確認，不重複寫入。
圖片 polyglot 疑慮在核對現有 MIME／nosniff 邊界與隔離瀏覽器後撤回：
有效 GIF 附帶 script 內容仍可正常作圖片，直接開啟或當 script 請求時都不執行。
僅本機 Chrome fixture 已驗證，不能代表全部瀏覽器或正式新 API 可用；檢查已接入 Preview。
這是 component review，完整發布範圍仍須重新審查，不能套用來宣告全專案完成。

後續重審另找到大於 1 MB 圖片的 GitHub Contents 相容性問題：保存可能已接受，
但讀取只期待 base64，造成驗證失敗及草稿無法重讀。
已保留原尺寸支援，改用 Contents `object` media type 並核對 immutable path SHA／size，
缺 base64 時讀取 exact Git blob；加入 1.1 MB 有效 GIF 的保存／重讀及 post-ref 讀取失敗測試。
ref 已接受後的文章／manifest／圖片驗證失敗一律回報保存結果未確認，不把它當成未寫入的普通衝突。
依據：[GitHub Contents API 大小限制](https://docs.github.com/en/rest/repos/contents#get-repository-content)。

最終五個草稿 source／test 檔的獨立 `gpt-5.5`／high／read-only component 重審通過，
實際模型／sandbox 已核對；涵蓋上列大圖片及錯誤處理修正。
這份核對不包含未來的後台整合，也不替代整批發布範圍的 Codex／Opus 審查。
程式盤點另确认 `admin/admin-extras.js` 的全站字型保存、版本回退與目錄排序也直接寫 main；
這三條路徑必須一併改為草稿／候選，不能只改普通儲存按鈕就宣稱 CMS 發布安全完成。

## 後台普通存檔的草稿整合（尚未發布）

已在 `admin.html` 接入草稿 client 與 `admin/draft-editor.js`：一般文章由實際雲端草稿／正式來源載入，
普通保存與「存草稿」都使用同源 cookie API，不再寫 main；共用 `gh` 函式只允許 GET，
即使 bridge 腳本缺失，也不回退為直接寫入。介面明示雲端草稿不等於正式上線。
圖片先留本機；保存時與 HTML 同批。暫存帶入所載入 revision 及圖片資料，重讀後可恢復，
遠端版本觀測採只讀 status，不偷偷改變編輯器的 CAS revision。

隔離的實際後台瀏覽器確認：載入正式來源、先插入圖片而沒有 repository write、
保存中繼續輸入保留 dirty／暫存、下一次保存使用已接受的草稿 head、
衝突保留編輯／blob SHA、重讀與暫存還原仍顯示尚未發布的圖片，以及共用直接寫入阻擋。
檢查已接到 Preview。此處只代表本機 Chrome fixture，不代表新 API 已正式部署或完整瀏覽器覆蓋。
JS 語法／frontend security 通過，新的 inline admin script CSP 已由生成器同步。

建立文章、排程 queue、下架、全站字型與目錄排序尚須目的明確的草稿操作；
部分舊路徑因共用直接寫入守衛而暫時無法保存，另有 extras 的直接寫入仍需改造。
目前新整合不能發布。衝突整合 UI、可信送審／候選／正式狀態与 Word 文件模型也尚未完成。
整合後的完整差異需要重新取得独立 review，先前五檔 component approval 不足以覆蓋這些新變更。

普通文章存檔與圖片已接入本機尚未發布的整合；建立文章及其他後台寫入路徑仍待改造。
正式網站尚未取得這批修改，CMS 里程碑保持未完成。
衝突比對／整合 UI、送審與候選建立、可信發布狀態及 Word 三篇試點仍須實作。

### 整合重審與資料保護修正

完整未發布增量的獨立 Codex 審查找到切換文章前未立即暫存、缺少文章被誤標已發布，
以及進度文字過期；均已修正。載入採延後啟用 context，避免先覆寫舊文章圖片映射；
等待載入期間的新輸入也在切換前暫存。實際 Chrome fixture 刻意延遲 GET、繼續輸入，
確認暫存含最新文字與圖片、恢復後可見；不存在的文章回傳 not_created／published=false。
實際 review session metadata 證明 gpt-5.5／high／read-only，不能只依 reviewer 自述猜測模型。

後續重審另找到原始碼存檔可保留 data URI 或缺少的圖片引用。新增鎖定版本 parse5，
依實際 HTML attributes（含 entity／無引號／srcset）核對圖片，拒絕本機 URL、
內嵌 data URI 與沒有既有 manifest／本次上傳／immutable main 來源的 managed 圖片。
已發布的 managed 圖片在重新編輯時可納入 manifest；增量存檔保留既有圖片。
重審再要求既有 main 圖片也核對實際 SHA-256／raster magic，已共用 immutable 讀取與
相同圖片驗證，保留新舊來源；補錯誤雜湊、格式與引用数量上限測試。
套件要求 Node 20.19.0，root engine 與 lockfile 同步標明最低版本。
目前 server／client 34 項通過；前次相鄰 Node 全批 159 項通過，API／supply-chain 檢查通過，
npm audit 回報 0 個已知漏洞。更新後完整 Node 批次仍須重跑。
這些是本機結果，仍須新完整差異審查、遠端 CI、Preview 及正式發布。

### Word 文件模型的隔離試點

在 Git 忽略的診斷目錄評估固定版本 ProseMirror，尚未接入正式後台。
先測痤瘡長文、杜避炎表格／文獻、外用類固醇表格，逐項比較文字、anchor、連結、
表格／清單數及 undo／redo；第一版已重現把保護 div 放入 table／list 造成內容移位，
修正保護節點的 HTML 結構後上述有限檢查通過。不能把它當成完整保真或 Word 驗收。
表格屬性／表頭結構、雙語標記、實際互動計算器、多圖混貼、IME 和斷網仍需另驗。
不加入付費 Word PasteHandler 或雲端 DOCX 轉換；現有醫療來源與插圖未改動。

### 新文章與歷史還原（尚未發布）

新文章精靈改走固定 article-draft API，連同中英文標題／分類資料保存為經驗證草稿，
不直接修改正式目錄或 EN 生成物。既有網址／草稿拒絕覆寫；輸入保留。
以 authenticated／immutable／分頁有界的草稿清單補入左側檔案清單，重新登入或載入新版仍可找到。
空白文章使用空白正文範本，避免把整篇痤瘡文字／舊 canonical 複製到新主題。
中文 title 沿用 D-10 品牌後綴；新建 h1 英文標題使用作者輸入。

extras 歷史按鈕已移除直接 PUT main，改開啟有文章／載入／登入識別保護的版本比較；
作者選擇後才載入編輯器，保留目前草稿 CAS revision，需再保存為草稿。
actual Chrome fixture 已驗證比較不寫入、還原不寫入、明確保存才寫草稿，
並測新文章精靈、清單與重複網址拒絕。

另確認 CI 以前沒有安裝 root npm dependencies；quality 生成與 scheduled 候選工作增加
鎖定 `npm ci --ignore-scripts`，避免本機安裝成功但乾淨 runner 缺解析器。
完整 20 檔未發布增量的獨立 Codex 重審要求移除仍留在頁面的舊 main 建文程式，
已刪除，精靈入口現在只委派已就緒的草稿控制器；未載入時保留輸入並明示未寫入。
原本依賴舊 main 建文函式的測試改為驗證這個入口，provider blob／tree／commit／ref
失敗保護改由實際草稿 API 回歸覆蓋。讀取草稿服務失敗也有可操作且不洩漏 provider 細節的提示。
圖片上限明確區分 raw bytes 與 base64：1,900,000 個 base64 字元最多容納 1,425,000 bytes，
manifest 每張及整批都先驗證此預算；既有超過 1 MB 的 immutable Git blob 讀取仍通過。
目前 server／client 42 項在 Node 20.19.0 通過，相鄰 Node 全批 164 項通過；
實際 Chrome 精靈／版本比較／草稿恢復整合也通過。CSP 已按移除後程式重新生成。
這輪修正後仍須完整獨立重審，前次 14 檔 INCREMENT_APPROVE 不能涵蓋它們。
排程、下架、全站字型、排序與可信候選／正式狀態仍待改造，整批不具備發布條件。

### 只抽取文章 bundle 的候選準備（尚未發布）

已新增 immutable 文章候選抽取器，核對 queue head／article blob、manifest、main 原文章
blob、普通檔案模式、圖片 SHA-256／Git SHA／raster magic 與整批大小；驗證完成前不寫檔案。
只準備文章與列出的圖片，新文章另建立安全的 catalog entry；不合併整條草稿分支，
不導入 draft 內的其他程式、manifest 或 EN 生成物，也不變更 Git refs／遠端。
最新 main 的其他文章或程式改動保留；文章本身改動時停止並保留原草稿供整合。

實際暫存 Git history 測試 9 項通過；另執行工作流的 Python 原文，使用隔離本機 bare
remote 檢查版本精確、舊 queue、排程後再編輯與 main 衝突共 4 項通過。
測試先發現拒絕項目仍因 queue 格式重寫而生成候選，已改為只有確實準備的項目才移除，
保留其他項目的次序；全拒絕時保留原始 bytes，沒有 artifact／CI 重跑。
這些 workflow 測試使用 orchestration CI stub，不能冒充真實完整 CI 或正式部署。

作者的送審／排程意圖寫入、醫療核可與 revision 綁定、候選建立／可信正式狀態仍待完成；
目前後台排程按鈕仍被禁止直接寫 main。這一批抽取器修改尚須獨立完整增量重審。

### 作者確認與版本綁定申請（尚未發布）

article-draft API 新增送審／排程／下架／取消操作，固定 cookie 身分、same-origin、
文章與 expected head／blob／base SHA；只寫草稿分支的 .cms-requests/<slug>.json。
作者送審／排程須明確確認醫療文字、圖片與出處；伺服端把作者、時間、文章 blob、
完整 manifest SHA 及原草稿 head 一併保存。申請 commit 必須緊接確認的草稿，
其他 successor commit、main 文章變動或 manifest 不一致都使申請失效。
保存新版本會在同一個 commit 移除舊申請；取消只移除申請、保留原文章與圖片。
這是記錄作者確認，不能當成模型判定臨床正確或完整交付已通過。

後台實際按鈕改走上述 API；已刪除舊排程寫 main queue 及下架寫正式 catalog 的程式。
模態視窗綁定原文章／登入／載入識別／內容與已保存版本；確認期間有修改則不送出，
I/O 期間新輸入仍暫存，接受後採新 CAS head。對話框有鍵盤 focus 圈與關閉後焦點還原。
顯示待審核／排程申請／下架申請／取消事實，不把它們當成 CI 成功或正式已發布。
API 另區分 sourceOnMain 與 deploymentVerified，不因 main 有檔案就宣稱正式部署。

瀏覽器先重現重讀草稿後編輯器格式空白被誤判為新編輯，現改以未修改的掛載視圖
建立獨立比較投影，不改雲端原始 bytes 或 blob SHA；真實新文字仍被拒絕送審。
server／client 現有 63 項在 Node 20.19.0 通過，相鄰 Node 全批 184 項通過；
actual Chrome fixture 已驗證未勾選不寫入、確認後
內容變更不寫入、申請等待期間輸入暫存、保存後申請失效、排程／取消／下架、
重讀狀態及舊視窗失效。這批新增差異尚須完整獨立重審及適用相關檢查。

移除舊 modal 後，安全檢查仍尋找已不存在的 slugLabel；已改為核對新標題使用
textContent 而非 innerHTML，並在 actual Chrome 以帶 onerror 標籤的作者標題確認
文字不產生圖片節點／程式執行。API／frontend／deployment／supply-chain／49 檔 JS
語法檢查通過，CSP 按新 inline 入口重新生成；保留其他安全與 CI 門檻。

仍須接上申請→候選準備，並在候選與正式交付前再次核對申請未被撤回／改版。
精確 CI／Preview／正式部署狀態、下架 catalog 候選、字型／排序與衝突整合 UI
尚未完成；所有改動維持未發布，不能用前次 23 檔增量 APPROVE 涵蓋本節新修改。

### 申請版本驗證與新文章目錄相容性（尚未發布）

新增唯讀申請驗證／準備模式：核對 origin 當前草稿 head、固定作者與明確核可、
完整 request schema、文章／manifest／base SHA 及 request 的唯一直接 parent。
申請 commit 只能改申請 sidecar；後續 commit、取消、改版、main 文章衝突都拒絕。
排程須到期且在申請後一年內；驗證結束再查 origin。準備證據包含源碼摘要，但不等於
release permit；後續取消仍須在 CI／promotion／正式建置階段重新檢查。
重新公開刻意隱藏的文章仍會拒絕，須另經明確核可的 visibility 候選。
寫候選檔案前新增工作區／revision 再檢查，保護驗證期間的新本機輸入。

新文章 catalog 原本使用 JSON keys，部分生成器無法辨識；改為保持現有
unquoted keys／單引號 slug 契約。feed 目錄讀取改用共同 JS-literal reader，避免
作者標題含 apostrophe 被截斷；匯入 feed 模組不再執行生成或改寫檔案。
沒有新增或修改公開醫療文字。申請自動發現／候選連接、正式撤回門檻及可信發布狀態
仍未完成，這批新差異另需獨立重審；尚無新 commit／push／遠端 CI 或正式發布。

### 下架候選的文字與索引政策保護（尚未發布）

下架申請準備專用候選：驗證原文章版本與申請後，只取目前 main 的文章，增加 noindex
並在 catalog 標示 unpublished。未完成的草稿與圖片不會跟著下架操作進入公開源碼。
保留 URL、段落、SVG、anchor、其他 metadata 與其他文章的原始 catalog bytes。
下架前的 robots 政策存入該文章 metadata，原本 noindex／nofollow 政策保持；
之後恢復可見性也不能把既有 noindex 擅自解除。重複下架／缺條目／不明舊政策拒絕。
catalog 定位忽略字串及註解內的大括號，robots 缺失、重複或位於 head 外都停止。
尚未串接自動申請發現與正式 gate，不代表按下申請就已下架／正式發布。

### Word 編輯接入與既有文章相容性（2026-09-30，本機未發布）

成熟文件模型試點已移入後台，按「Word 編輯」才載入文件模型 JS；公開讀者頁沒有新增編輯器載入。
以 parse5 來源位置只替換唯一中文區塊，舊版 overview 明確限定 article.prose[data-slug]，不擴大成 main／body。
完整文章外框、英文區塊及腳本保持原始 bytes；SVG、計算器及未知區塊保護並禁止執行。
修正 section 被轉成 div、表格 style 被 cssText 正規化、預覽轉入模型會遺漏受保護原稿，以及失敗載入後無法保存原編輯等問題。

新增實際草稿用的整批圖片準備／一次 commit／逐項 rollback，包含 raster magic、解碼、尺寸、摘要與總量驗證。
圖文貼上、多張圖片、替代文字、排序、復原／重做、存檔中繼續輸入與原始碼往返已接入。
保留單一文章快照；普通保存仍只送入雲端草稿。未接入的舊工具在 Word 模式明確停用，切回後恢復。
建置產生鎖定依賴的 JS、必要原生編輯器 CSS 與套件授權，逐 byte 檢查生成物一致性。
視覺核對找出原生圖片 separator 缺樣式造成空白高度，已加入上游樣式與跨引擎尺寸回歸檢查。

本機 Chromium／Firefox／WebKit 各對 52 篇公開文章檢查開啟原碼、文字、IDs、連結、表格、section、保護區塊及 undo／redo。
三引擎各在 390／800／1440 執行實際後台流程，含模型載入失敗、草稿保存、圖片去重、替代文字、存檔期間輸入、載入失敗保留編輯及 source 往返。
Chromium 另用 native CDP 驗證中文 composition／取消／快照等待與 undo／redo（12 項）。
這些不代表真實 Windows Word 剪貼簿、iOS Safari、Android 或全部編輯操作已驗證。
未新增公開醫療文字；仍需完整新差異独立審查、CMS 發布門檻整合、首頁 CI 效能修正及正式候選／Preview／main 交付。

獨立審查後修正模型文字插入 API，使其使用目前選取位置；另增加非首段插入與四種 comment 的原始碼保護測試。
parse5 8.0.1 在 sourceCodeLocationInfo 模式會為 comment token 設定位置；實測正常、空白、巢狀及未終止 comment 保持原始 bytes，未移除位置不明時的安全停止。
移除字型與文章排序直接 PUT main 的路徑，改保存可恢復的本機設定草稿並明示未發布；排序草稿绑定載入目錄的 SHA，來源更新不自動套用舊排序。
這是關閉 CI 繞過路徑，不代表設定草稿的雲端候選發布已完成。
Word 模式停用會修改隱藏 iframe 的編輯助手；SEO 快照檢查在圖片處理／中文選字期間暫緩。
圖片 separator 樣式與固定編輯區的長文捲動皆已增加三引擎／三寬度尺寸回歸。

### 作者申請與候選內容的發布門檻（2026-09-30，本機未發布）

申請候選附上版本證據，Delivery contract 核對即時 drafts head、申請 blob、直接 parent、
申請 commit 只含該申請檔、manifest、核可文章與完整圖片集合。候選源碼須符合準備摘要；
修改文章、遺漏圖片、改摘要冒充新文字、撤回申請或提交新版都不能繼續用舊證據發布。
下架另核對目前 main 文字只被調整 robots 索引設定，避免帶入未完成醫療草稿。
精簡 request JSON 與縮排 receipt JSON 分開驗證，保持實際後台 API 格式，拒絕重複屬性。

main 推送門檻在模型 hook 成功後再次核對作者申請；Vercel 的既有 exact-SHA CI／PR
门檻後增加即時申請核對，正式 build 前後都執行。GitHub API 不跟隨轉址、要求重新驗證
快取且限制回應 bytes；無法讀取證據時不放行。這是增加發布核對，不宣稱跨 Git ref 與
Vercel 部署具有原子鎖定能力，也不把準備／通過檢查標示成正式上線。

本機新增撤回、驗證中改版、內容與圖片變更、錯誤 immutable blob、錯誤 parent／diff、
排程未到期與下架文字保護測試；Python／Node 實際 API bytes 的一致性另作交叉檢查。
當時尚需完成申請自動發現、候選生成與核可內容一致性、已發布證據退役／新版草稿、可信
部署狀態與使用者衝突處理。首頁原候選 CI 效能仍未過；沒有新 push、Preview 或正式發布。

### 作者申請的獨立源碼準備（2026-09-30，本機未發布）

排程改為由可信 main 唯讀發現 drafts 分支上的版本綁定申請，舊 queue 不再充當核可。
每篇從同一最新 main 建立獨立暫存 clone；只複製核可文章、圖片、必要 catalog 與 receipt，
不合併草稿分支程式。多篇新文章各自使用原 main 目錄，避免共用 catalog 使摘要失效。
建立 bundle 前後及最終 report 前重查即時版本；Git 寫入後的 bytes 也須符合準備計畫。
正式及本機 refs、queue 與使用者 checkout 保持原樣；產物明示未 review、未 CI、未發布。

源碼準備與候選驗證分為不同階段；這個排程不執行會修改源碼的生成器，也不產生 CI
成功證據。既有 Quality／Delivery 的完整候選、PR／Preview 與正式發布門檻維持。
待完成項目仍包括生成內容的核可一致性、receipt 退役／新版草稿、可信部署狀態、
雲端設定與衝突處理；Word 與全專案 Goal 不能因此宣告完成。

相關 Python 回歸 89 項、Node 發布門檻 51 項通過；這些是隔離 Git／模擬 API 本機測試，
不是完整遠端 CI 或部署證據。獨立審查指出 Actions checkout 的 HTTPS URL 可省略 .git、
以及草稿祖先驗證 exit 1 不應中斷其他有效申請；兩項已在舊行為重現並修正，加上回歸。
Opus 212 檔完整重試被 provider 額度限制拒絕，未取得核可；下次重置後補審維持 pending。
本批仍未提交、推送或上線；首頁 Lighthouse 未過及其他里程碑仍須完成。


## 2026-10-01：草稿重新載入的位元組驗證

- 修正文章、草稿摘要及圖片讀取：除 GitHub 的 SHA／size 欄位外，核對實際解碼長度與 Git blob SHA-1（含 `blob <size>\0` 標頭）。大於 1 MB 的 Contents fallback 必須回傳相同 blob SHA 與大小；無效摘要、長度、編碼或內容一律拒絕，不把不一致的資料送入編輯器。
- 原先測試重現同大小改動仍被接受；9 個新增案例中 8 個失敗、1 個既有編碼防護已通過。修正後文章 API 53 個案例全數通過，另有 client／CMS／Vercel 74 個相關案例與 API／前端安全檢查通過。這是局部回歸，尚未代表完整 CI、獨立補審或正式交付。
- 首頁效能仍待修正。隔離本機 HTTP 額外改寫後，提早 CSS preload 沒有穩定改善；延後必要 CSS 的實驗增加排版位移，均未採用。沒有修改公開首頁、字型、插圖或醫療文字，也沒有降低 Lighthouse 門檻。
- 整體 Goal、正式 CI／Preview／發布、可信部署狀態、生成內容核可一致性、證據退役／新版草稿與雲端設定仍未完成。Opus 依最新額度重置時間補審；不因等待額度停止其他工程。

## 2026-10-01：校正 SEO 效益說明

- 已校正生成流程與九個 SEO 模組的註解／docstring，移除「醫療 Q&A、藥品、詞彙定義或免費工具標記會自動取得特殊搜尋卡片」、「預先載入必然提升排名／節省行動流量」及固定 CTR 成效等無證據承諾。比對去除 docstring 後的 Python AST，確認可執行邏輯與既有醫療代碼沒有改動；公開 HTML、生成 schema 與 CI 門檻也未變更。
- Google 官方更新記錄指出 FAQ rich result 已於 2026-05-07 停止顯示；保留對讀者有用的 FAQ 與正確語意，不再把這個搜尋展示當作成長目標。來源：[Google Search 更新記錄](https://developers.google.com/search/updates)。
- `DefinedTermSet` 與醫療代碼等語意，不等同 Google 支援的專屬 rich result；即使符合支援類型，Google 仍不保證顯示。來源：[支援類型](https://developers.google.com/search/docs/appearance/structured-data/search-gallery)、[一般規範](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)。
- `max-snippet:-1` 是讓 Google 選擇摘要長度，`max-image-preview:large` 是允許較大圖片預覽，均不能保證點擊率。來源：[robots 指令](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag)。預先呈現頁面可能改善實際導航體驗，也會消耗頻寬、記憶體與 CPU；應量測效益與浪費。來源：[Chrome 預先呈現文件](https://developer.chrome.com/docs/web-platform/prerender-pages)。
- 核對實際程式後確認，`lastReviewed` 已使用作者的 `_review_dates.json` 帳冊，缺少可用項目時保留頁面既有日期，並不使用 Git 修改日期。帳冊的 `published` 保守基準與 `reviewed` 重新審閱記錄須區分；全站日期來源的逐篇核對仍待完成。此輪校正過期註解，沒有自行變更公開醫療日期。

## 2026-10-01：編輯器 bundle 的文字完整性門檻

- 確認 parse5 的合法替代字元常數在編輯器 JS bundle 內直接輸出 `U+FFFD`，會觸發既有文字完整性檢查。改為 esbuild 的 ASCII 字元輸出，保留解析器字串值，沒有降低檢查門檻。CSS 與授權文件維持原本設定。
- 已重新產生 bundle，固定來源／相依套件的位元組檢查與四項 source-offset 測試通過。舊／新 bundle 經相同、未縮小、移除註解的 esbuild 轉換後，可執行 JS 一致。原先含註解的比較未通過，原因與後續轉換證據另存，沒有把首次比較說成通過。
- 根目錄直接執行文字完整性檢查仍有本機限制：它也讀取被 Git 忽略的診斷文件；其中兩份 PowerShell 重導向日誌是 UTF-16，舊測試生成物亦有替代字元，之後主控台編碼無法列印部分錯誤。這次失敗有保留，不是完整 CI 通過；候選仍須乾淨 runner 上的完整遠端驗證。

## 2026-10-01：全文章結構核對與搜尋下架保護

- 已逐篇核對 52 篇公開文章的分類、標題、摘要、canonical／OG URL、搜尋入口與 sitemap，並保存各篇來源 SHA-256、欄位及 anchor 數量。中英文首頁與索引卡片的中央目錄一致性檢查通過；另有兩篇保留的專業閱讀文章在搜尋中，共 54 個搜尋入口。這是完整文章集合的結構檢查，不代表臨床內容或全專案程式已全部審完。
- 134 份 HTML 的內部連結與 413 個 JSON-LD 區塊檢查通過，sitemap 與索引邊界檢查亦通過。另有三個標題／摘要長度提醒：文章索引標題較短、結節性癢疹摘要較短、螺內酯標題較長。這些提醒不是排名或點擊率證據；醫療文字仍須按核可流程修改。
- 修正搜尋產生器只認單引號／單行 catalog 的缺陷，改用首頁、CMS 與 feed 已使用的共同目錄解析入口。雙引號與多行的下架標記現在同樣排除；缺少或無效目錄會停止產生，保留上次索引。另排除 noindex／Googlebot none 與 template、textarea 等非顯示內容，保留可索引的專業文章。
- 新增十項搜尋可見性回歸，包含實際下架計畫的往返、較晚的 noindex、隱藏範例文字及無效目錄；修正前重現失敗，修正後通過。獨立審查另外指出重複 meta 屬性會造成瀏覽器與字典解析差異；已重現並改為保守排除不明 robots 政策。搜尋／目錄／下架 Python 共 32 項及搜尋完整性 Node 四項通過，相關安全與部署檢查亦通過。重新產生後備援搜尋 JSON 的位元組與 SHA-256 完全一致；沒有變更既有公開文章或插圖。
- 主要搜尋 Pagefind 1.5.2 的實際隔離測試證實，它不會自動排除 robots noindex／Googlebot none 或讀取下架目錄。生成流程現在先驗證目錄、選出兩種語言的可索引來源，再清除並重建舊索引；不再把管理頁、隱藏筆記、下架文章及 noindex 頁面交給爬取器。六項 Pagefind 回歸通過；直接以目前文章來源產生暫存索引，125 個允許頁面全被索引、八個排除頁面未出現，輸出位於獨立暫存位置。本機既有正式索引沒有改寫，正式生成／CI 仍待完成。
- 另核對 52 篇、104 份中英文頁面：帳冊日期、公開 `lastReviewed` 與發表日一致，全部帳冊項目為 `source: published`；沒有記錄實際重新審閱，不能宣稱文章在近期經過醫療補審。七篇的發表／修改日期位於獨立 `MedicalScholarlyArticle`，其餘位於 `MedicalWebPage`；檢查同時涵蓋兩種結構，未擅自移動日期。
- 目前候選與 PR 的 Quality 仍因首頁 Lighthouse 63／64 未達 70 而失敗。這批本機改動尚未提交、推送或上線，不能沿用既有候選 CI；Opus 依額度重置後補審，其他工程持續進行。CMS 生成內容核可一致性、已發布證據退役、新版草稿、可信部署狀態、雲端設定與其餘全站里程碑仍待完成。

## 2026-10-01：編輯中的上線狀態與保存保護

- 後台新增「查看上線狀態」，由 cookie 認證的固定儲存庫 API 唯讀查詢。先核对 exact main SHA 的正式 push workflows、實際 attempt、必要 jobs／steps 與正式 smoke，再核對同 SHA 的最新 Vercel 部署／狀態。候選、PR、手動 workflow 或舊綠燈不能冒充正式通過；main、run attempt 或部署在查詢途中改變時，回覆無法確認。
- 區分 CI 缺失／進行中／失敗、部署進行中／失敗、已部署但 noindex，以及網站原版本已上線、目前草稿尚未上線。查詢只接受可信 Vercel bot 與固定專案的 HTTPS 部署 URL；不取回該 URL、不回傳憑證。GitHub 部署中這個專案實際使用 `environment: Production`，但 `production_environment: false`，因此不能只靠該布林欄位辨識正式環境；仍須完整正式 CI、部署身分及 smoke 證據。
- 查詢不修改來源、草稿 CAS 或作者申請。回覆抵達時如文章、已保存版本或認證已切換，就捨棄舊回覆；查詢期間的編輯與明確草稿存檔保留。WebKit 隔離回歸曾重現正文已變動但未標成未保存，現增加內容變動偵測並與載入版本比較，避免遺漏保存提示，也避免把純顯示排版誤認為作者修改。
- 新 API 案例先重現失敗，再接入觀察流程；server／client／CMS／Vercel 相關案例通過。三引擎各 390／800／1440 的實際後台狀態與競態回歸通過，Word 編輯九個畫面流程與各引擎既有草稿回歸通過。這些使用隔離 API／collector；不代表正式 Edge API、真實 Word 剪貼簿、手機實機或完整 CI 已驗證。
- 唯讀讀取 GitHub 的 main `13ae58b75f4f05472bf9ba43769c13d1cfea4a0e` 實際 workflow 資料，觀察器正確判為 `ci_failed`，對應正式 Quality `36654109136`，沒有誤報已完成上線。此批新增實作尚未提交／推送，獨立審查、完整遠端候選及正式交付仍須逐版取得新證據。
- 獨立 Codex 審查找到「main 不變但正式部署已回滾至另一個 SHA」的誤報；新增回滾與查詢中換版案例先重現兩項失敗，再移除部署查詢的 SHA 篩選，先選最新可信正式部署、要求其 SHA 相同，再重新讀取確認。修正後相關 Node 案例共 149 項通過。首次 REQUEST_CHANGES 與 red log 保留；這個修正版本須重新獨立審查。

## 2026-10-01：首頁首屏渲染改善

- 延續實際 Linux CI 報告的首屏 layout／render delay 診斷，使用相同來源位元組、獨立新 Chromium 148、CPU 4 倍及相同資源延遲做本機對照。所有 collector 封鎖，不產生正式 GA 點擊。這個隔離環境不等於 Linux Lighthouse、真實網路或 field CWV。
- 首頁原本已有下方區塊的 `content-visibility:auto` 與 600 px 預留高度。試驗將首頁下方區塊的預留高度調為 1000 px，`auto` 保留實際渲染後的高度；確認只排除 `.mag-hero`，因為 main 的第一個 child 是 inline style，不能用 `:first-child` 當首屏邊界。第一次選擇器與平滑捲動尚未停止的診斷數值保留；後續分別修正，不把它們當定位驗證。
- 修正選擇器後的配對結果：原版首次顯示 1940–1964 ms，新版 1724–1732 ms，約縮短 208–240 ms；首屏前最長工作約由 677–696 ms 變為 444–449 ms。整體 layout 工作沒有減少，因此不宣稱所有互動阻塞或 CI 分數都已解決。單獨調整 hub、移除重複 CSS 或停用腳本沒有相同的首次顯示改善，沒有採用這些變體。
- 三引擎各 390／800／1440 的原版與實驗首屏 PNG 逐檔完全相同。搜尋、52 篇入口、anchor 的最終定位及 wheel 捲動已在隔離場景核對；即時捲動用於比較最終幾何，不代表已驗證所有原生平滑動畫或手機實機。公開字型、插圖與文章文字沒有改動。
- 已將規則加入首頁目錄生成入口，由中英文首頁共同使用；完整 `regen` exit 0。單跑英文生成器的中間結果曾有多篇 EN metadata／reading badge 差異，完整管線完成後這些差異消失，只剩兩份首頁的 CSS 規則。新回歸先重現缺少規則，修正後首頁／可見性／搜尋相關 Python 共 33 項通過；既有精確樣式字串測試同步驗證新的完整規則，沒有刪除檢查。
- 本機實作仍需新版本獨立 review、遠端候選 CI／Preview 及正式交付。最新遠端 main／候選仍為 13ae／89d58，Quality 仍失敗；不沿用本機量測宣稱 CI 通過，也沒有為找綠燈重跑未改動版本。
