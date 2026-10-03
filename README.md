# ChenDermatologist · 皮膚科筆記與衛教

陳翊嘉醫師的衛教與學習筆記網站，以一般民眾／病人為優先，保留專業閱讀入口。作者身分為皮膚科住院醫師 R3。

- 正式網址：[chendermatologist.com](https://chendermatologist.com)
- 程式庫：[expertise88864/user](https://github.com/expertise88864/user)
- 網站為靜態 HTML，使用 Python／Node 建置生成物，並由 Vercel 提供頁面與後台 API。
- 中文為權威來源；`en/` 是生成的英文鏡像，索引政策依 [DECISIONS.md](DECISIONS.md)。

## 編輯文章

使用 [作者操作指南](AUTHOR_WORKFLOW.md) 完成 Word 貼上、圖片整理、保存雲端草稿、送審、確認生成預覽及查看上線狀態。

普通保存寫入雲端草稿。原稿送審後，由受信任管線準備完整生成 Preview；作者再核可生成內容，維護者完成所有正式交付門檻。

醫療文字、圖片、英文與劑量變更依 [DECISIONS.md](DECISIONS.md) 取得具體醫師核可。新文章來源與模板流程見 [WRITING_NEW_ARTICLE.md](WRITING_NEW_ARTICLE.md)，發布以 [REMOTE_CI_DELIVERY.md](REMOTE_CI_DELIVERY.md) 的現行規則為準。

## 在單一 user-main 工作目錄開發

使用目前的 `user-main` checkout，保留使用者未提交內容。交付驗證基準為 Python 3.12（與 CI 及 [PIPELINE.md](PIPELINE.md) 一致）；Node 須符合 `package.json` 的 `>=20.19.0`。本機現有 `python` 若為 3.13，須記錄版本差異，本機結果不能代替同 SHA 的 Python 3.12 遠端 CI。

```powershell
npm ci --ignore-scripts
npm run serve
```

預覽伺服器預設為 `http://127.0.0.1:8080`，以啟動時顯示的網址為準。它提供本機頁面預覽；雲端後台操作須使用具有實際 API 的已核對版本網址。

```powershell
npm run check
npm run build
```

`check` 執行本機品質與回歸檢查；`build` 另重新生成英文、索引、feeds、runtime 與其他建置產物。建置後檢查來源與生成差異並重新審查。工具需求與詳細順序見 [PIPELINE.md](PIPELINE.md)。

## 候選與正式發布

每批先做相關本機檢查與獨立模型審查，再正常推送 `codex/*` 候選，通過同 SHA 完整遠端 CI、同庫 PR、Preview 與瀏覽器檢查後才可正常快轉 main。

```powershell
python _delivery.py verify <完整候選SHA> --phase candidate --wait 1800
```

`deploy.bat`／`deploy.ps1` 使用乾淨、已驗證的候選 checkout 執行正式晉升。它不替作者提交、整合或覆寫修改。main 發布後還須同 SHA 正式 CI、正式部署與 hosted smoke 成功，才會輸出 `Delivered <SHA>`。

Vercel 的 `vercel.json` 已定義建置前後閘門及生成命令，並設定 clean URLs 與安全標頭。新專案／設定變更須依現有設定與權限核可流程處理；不能用空白建置設定取代閘門。

正式 build 如因 GitHub HTTP 403／額度失敗，保留失敗證據並修復受核可的存取設定。參照 [REMOTE_CI_DELIVERY.md](REMOTE_CI_DELIVERY.md)，候選成功、main 更新與部署成功須分別核對。

## 常見操作問題

| 情況 | 處理 |
|---|---|
| 雲端保存結果不確定 | 重讀草稿核對，保留本機編輯 |
| 原稿或生成預覽版本改變 | 重新準備 Preview 與作者核可 |
| CI／部署失敗或尚未完成 | 查完整 SHA 的失敗紀錄並處理原因 |
| 正式文章看起來仍是舊版 | 先查「查看上線狀態」與實際部署 SHA，再排查快取／SW |
| Git 登入失敗 | 使用現有 Git 認證機制處理；必要的新增權限另取得核可 |

## 維護入口

| 文件／來源 | 用途 |
|---|---|
| [ONBOARDING.md](ONBOARDING.md) | 接手時的核對順序與歷史資料界線 |
| [AGENTS.md](AGENTS.md)、[CLAUDE.md](CLAUDE.md) | 專案工作規則，依最新使用者定案執行 |
| [PIPELINE.md](PIPELINE.md) | 建置、生成內容核可與候選包 |
| [REMOTE_CI_DELIVERY.md](REMOTE_CI_DELIVERY.md) | 完整交付門檻與證據 |
| [DECISIONS.md](DECISIONS.md) | 已定案的來源、索引及醫療核可政策 |
| [WEBSITE_EXPERIMENTS.md](WEBSITE_EXPERIMENTS.md) | 八週內容與量測素材 |
| `admin/`、`api/admin/` | 編輯器、草稿、作者申請及發布觀察 |
| `_delivery_policy.json`、`.github/workflows/` | 必要 jobs／steps 與 CI 執行定義 |

工程交付與搜尋成效分別記錄。每批保留 SHA、審查、CI、Preview、正式部署及未決項目；八週計畫準備完成後再依核對過的正式版本開始觀測。
