# Project agreements

## 最新使用者定案：每個 PR review 一次（2026-10-15）

本節優先於下方及舊文件中所有「逐 commit review」「push 前 review」「review trailer」「audit commit」規則；模型、CI、Preview、資料保護與醫療內容核可要求不變。
- 不再逐 commit review，也不用 pre-commit／commit-msg hook 審查；commit 不需要 review trailer。
- 分支推上 `codex/*` 後執行 `python tools/pr_review.py`：開（或找到）指向 main 的同庫 PR（本網站 `require_pr` 的 PR CI 與 Preview 也用同一個 PR），以 `gpt-6.1-sol`／`xhigh` 唯讀審查 `merge-base(main, head)..head` 整段 diff，結論與 findings 寫成 PR comment，並在 exact head SHA 設 `codex-review/gpt-6.1-sol` commit status。
- findings 逐條驗證（CONFIRMED／REJECTED／UNCERTAIN），只修 CONFIRMED；修正後 push，再跑 `python tools/pr_review.py --resume`（同一 session）直到 APPROVE。head 一變，舊 APPROVE 即作廢。
- 推 main 時 pre-push hook（`_delivery.py`）除候選 CI、PR 與作者意圖檢查外，還要求 exact head 有本人建立的 APPROVE status，且審查範圍涵蓋所有要進 main 的 commit。額度不足時 status 為 quota-pending：可照常發佈但不是通過；額度恢復後用 `python tools/pr_review.py --pending` 找出並補審，結果寫在同一 PR。
- 不再產生 audit commit；「空 audit commit 也走候選流程」已刪除。純文件變更仍走候選分支、CI、Preview 與 PR review。
- 切換前帶 `Claude-Opus-5-Review: pending` 的舊 commit 仍以 `claude-opus-5-5`／high 補審，結果記在 PR comment 或 issue，不再寫 audit commit。

## 最新使用者定案：遠端 CI 候選驗證與正式發佈（2026-09-06）
本節取代下方／舊任務／舊排程中「每次候選 push 前完整本機 CI」及「直接推 main 再修」的規則；不變更醫療內容核可、獨立 Codex/Claude review 或資料保護要求。
- 四個專案採本機快速檢查與相關回歸測試 → codex/* 候選分支 → 完整遠端 CI → 已驗證同一 SHA 才正常快轉進 main；候選 push 不要求先有完整本機 CI。
- 使用 _delivery.py 與 _delivery_policy.json；正式 push 的 pre-push hook 必須驗證 exact SHA 的候選 push workflows/jobs/steps 成功，並確認最新 main 是候選祖先。新的修改、生成、整合或 rebase 使旧證據失效。
- 網站還須 same-repository PR、exact-SHA Vercel Preview 與瀏覽器檢查；Vercel 正式建置前另驗證候選 CI，未驗證版本不可上線。部署成功不等於 CI 通過。
- HsiaoEye 視覺基準只能由 Ubuntu 產生並人工確認，不自動接受差異；保留 CMS 新修改，衝突停止，不 force-push。CMS 存檔不等於正式發佈完成。
- 晨報候選 CI 不得寄信、寫回正式 state 或觸發正式排程；變更產報/LLM/外部資料關鍵路徑時另做不寄信 dry-run。既有正式寄信排程不得因候選驗證中斷。
- CI 失敗持續診斷並修正可確認缺陷，修正後重跑完整遠端驗證；取消、逾時、缺失、讀不到及應跑卻跳過皆不通過。禁止 skip-ci、降門檻或繞 hook 製造全綠。
- 審查方式見上方 2026-10-15 定案（每個 PR 一次，gpt-6.1-sol／xhigh／read-only）；quota pending 只延後模型審查，不豁免正式發佈的遠端 CI。
- main 發佈後還要驗證 exact-SHA 正式 CI／部署及適用 smoke checks，才可宣告交付；純文件變更也走候選流程。
- 詳細入口、範圍與限制見 REMOTE_CI_DELIVERY.md。不得把本機快速檢查說成完整 CI，也不得把候選 CI 綠燈當作正式部署成功。
