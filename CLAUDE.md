# CLAUDE.md — chendermatologist.com 操作手冊(給每一個 AI session)

> 讀者:之後接手的 AI 模型(Sonnet/Haiku 等級也要能照做)。規則具體、可執行;
> 深入細節在四份姊妹檔:**PIPELINE.md**(建置管線)、**REVIEW_PLAYBOOKS.md**(review 手冊)、
> **TECH_DEBT.md**(技術債登記簿)、**DECISIONS.md**(已定案、不得重議)。

## 這是什麼專案
台灣皮膚科住院醫師(陳翊嘉)的靜態衛教網站,部署於 Vercel(push 到 main = 直接上 production)。
zh-Hant 為源頭、`/en/` 鏡像為生成物。~57 篇文章 + 128 支根目錄 Python 腳本組成的建置管線。
**這是 YMYL 醫療網站** — 內容錯誤會傷害真實病人,合規限制見下方鐵律。

## 每次開工(照順序做,不要跳)
1. `git fetch origin` → 看 `git status -sb`。使用者在**兩台電腦**工作 + CI 會自動推
   `auto-regen ... [skip actions]` commit,**遠端經常比本地新**。
2. 落後 → `git merge --ff-only origin/main`。本地有**不是你改的**未提交檔案 →
   幾乎都是換機殘留:`git stash push -m "stale pre-sync"`(可還原,不要直接 checkout 丟棄)。
3. 絕不把「不是你這個 session 改的」檔案 bundle 進 commit。只 `git add` 你明確改過的檔。

## 鐵律(違反 = 事故)
1. **醫療內容(文章文字、TL;DR、FAQ、藥物劑量)一律先給使用者(醫師)審核才可上線。**
   模型不得自行判斷臨床正確性。流程:草稿 → 使用者說「通過」→ 注入 → codex review → push。
2. **合規紅線**:作者是住院醫師 —— schema/內文**不得**掛醫院隸屬(worksFor/affiliation)、
   不得出現掛號/預約/價格/診所名(醫療法 §9)。`hasCredential` 只放「醫師」執照、不放號碼。
3. **push 前必過 Codex GPT-5.5 review**(全域規則,見 ~/.claude/CLAUDE.md)。流程:
   diff → `mcp__codex__codex`(或 CLI `codex exec -c model="gpt-5.5"`)→ 修 blocking → APPROVE 才 push。
   codex 不可用且使用者未明示跳過 → **不 push**。本專案 codex 已實際攔下多次真問題。
4. **生成物不手改**。哪些是生成物、改了源頭要跑什麼:見 PIPELINE.md。
   通則:`en/**`、`sitemap.xml`、feeds、`llms-full.txt`、`ai/*.json`、`.well-known/ai.txt`、
   `robots.txt`、`*.min.js`、pagefind/ 都是生成物 → 改對應的 `_normalize_*/_gen_*` 源頭再重跑。
5. **push 前必過品質閘**:`python _run_quality.py check` 必須 exit 0(31+ 驗證器)。
   只動 1-2 檔時可先跑對應單一 `_check_*.py` 快篩,但 push 前仍跑完整 gate。
6. **DECISIONS.md 裡的定案不得重議/回退**(例:mainEntity→#article 是刻意契約、
   severe-scabies noindex 是刻意草稿、robots 引用/訓練分流)。想推翻 → 先問使用者。

## 常用命令
```
python _run_quality.py check     # 31+ 驗證器(push 前必跑, exit 0 才行)
python _run_quality.py all       # 全量 regen + check(改了源頭腳本後用)
python _check_robots.py          # 單項快篩範例(所有 _check_*.py 都可單跑)
node _serve.mjs                  # 本地預覽
```
Python 3.13(命令是 `python`,**沒有 `python3`**)。腳本只用 stdlib。Node 有裝。

## 環境陷阱(每一條都真實踩過)
- **Windows 主控台 CJK 會 mojibake**(cp950/GBK)。讀寫中文一律 UTF-8 檔案往返,
  別信 console 輸出;inline Python 開頭加 `sys.stdout` UTF-8 wrapper 或寫暫存檔再 Read。
- **WebSearch 是美國節點且不支援 `site:`** — 台灣排名/收錄請以 GSC 為準,別用搜尋工具下結論。
- push 後 CI 會再推 auto-regen commit → 下次 push 前必 `fetch + rebase`(rebase 前工作區要乾淨)。
- Bash heredoc 可用;PowerShell 5.1 沒有 `&&`。路徑含中文(`程式`)— 引號包好。
- `llms.txt` 是**手維護**檔(不是生成物),但文章數等計數由 `_normalize_llms_counts.py` 校正。

## 發佈機制(內容怎麼上線)
- 直接改 main + push = 立即部署(Vercel)。
- 排程發佈:開 `drafts/<slug>` 分支 + 登記 `.github/scheduled-publish/queue.json`,
  CI 每 15 分鐘檢查、時間到自動 merge(見 `.github/workflows/scheduled-publish.yml`)。
- 新文章 SOP:`WRITING_NEW_ARTICLE.md` + `new-article.ps1` / `_scaffold_article.py`。

## 什麼時候必須升級 / 求援(誠實條款)
弱模型**可以安全做**:跑 gate、修 checker 抓到的具體錯、照 playbook 執行、機械性重構、
照既有 map 加 TL;DR/FAQ(內容仍需醫師審)。
弱模型**不得自行決定**,要問使用者或升級(強模型/codex 第二意見):
- 臨床措辭與正確性(永遠是醫師定案)
- 品牌/標題/內容策略的改向;robots·AI 爬蟲政策變更;刪除/更改 redirect
- 「品味題」(視覺、文案語氣):最多給 2-3 案讓使用者選,不要自行拍板
- 任何「查不到依據」的事:明說查不到,**不要編造**(尤其健保給付條件、藥物數字)。

## 目前戰略脈絡(2026-06,幫你抓輕重)
站內技術已到頂(gate 全綠);流量瓶頸是**新網域零權重 + 站外分發**,不是程式。
別再花時間磨站內效能/SEO 細節(邊際效益≈0);高價值待辦見 TECH_DEBT.md 與 CONTENT_ROADMAP.md。
TL;DR 區塊已覆蓋 12/57 篇(`_inject_tldr.py`,冪等、絕不覆寫既有)— 其餘 45 篇是
現成高價值任務:補 map → 醫師審 → apply → codex → push。
