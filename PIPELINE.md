# PIPELINE.md — 建置管線地圖(源頭 → 生成器 → 產物)

> 目的:讓任何 session 一眼分清「哪些檔案是**源頭**(可手改)、哪些是**生成物**(絕不手改)」,
> 以及「改了 X 之後要跑什麼」。順序的唯一權威是 `_run_quality.py` 的 `REGEN_STEPS`(~46 步)
> 與 `CHECK_STEPS`(當前 30 步,以該檔為準)—— **本檔不複製完整清單**(會漂移),只給結構與配方。

## 一張圖看懂資料流

```
源頭(手改這些)                     生成器                        產物(絕不手改)
─────────────────────           ──────────────────            ─────────────────────
blog/*.html(zh 文章本體)  ──►  _normalize_*(就地正規化)  ──►  同檔就地更新(schema/meta/…)
blog/blog-shared.js 裡的        _gen_en_pages.py          ──►  en/**(整棵英文鏡像)
  DN.ARTICLES(文章目錄=       _gen_feeds.py             ──►  sitemap.xml, blog/feed.xml, blog/atom.xml
  catalog 唯一源頭)            _gen_llms_full.py         ──►  llms-full.txt
根頁 *.html(index/about/…)    _normalize_ai_well_known  ──►  .well-known/ai.txt, ai/summary.json
llms.txt(手維護*)             _gen_ai_faq / _gen_ai_service ► ai/faq.json, ai/service.json
_normalize_robots.py 的         _normalize_robots.py      ──►  robots.txt
  ALLOW_UAS/BLOCK_UAS           _gen_search_index/_run_pagefind ► search index + pagefind/
vercel.json(手改,要審)       _minify.py                ──►  blog/*.min.js(由同名 .js 生成)
assets/inline/*.js(手改)      _gen_site_graph.py        ──►  站內連結圖 SVG
```
\* `llms.txt` 手維護,但其中的文章數/大小由 `_normalize_llms_counts.py` 自動校正。

**判斷法(記這個就夠)**:一個檔案若被某個 `_gen_*`/`_normalize_*` 寫出,它就是生成物。
不確定時:`grep -l "<檔名>" _*.py` — 有生成器寫它 → 改生成器,不改檔案本身。

## 就地正規化(_normalize_*)的心智模型
zh 文章 HTML 同時是「源頭」也是「被管線就地改寫的對象」:你手寫內文,
管線把 schema/meta/robots-meta/OG/citations/breadcrumb… 正規化寫回同一檔。
所以:**內文段落手改 OK;`<head>` 裡的 meta/JSON-LD 區塊改生成器**,否則下次 regen 被蓋掉。
所有 `_normalize_*` 都設計為**冪等**(重跑不再變)。驗證冪等:跑兩次,第二次 diff 應為空。

## 配方:「我改了 X,要跑什麼?」
| 你改了什麼 | 跑什麼 | 再驗什麼 |
|---|---|---|
| zh 文章內文(段落/表格/FAQ 文字) | `python _run_quality.py build`(會重生 en/feeds/llms) | gate exit 0 |
| DN.ARTICLES(新文章/改標題/日期) | `python _run_quality.py build` | `_check_articles.py`, gate |
| 某個 `_normalize_*`/`_gen_*` 腳本 | `python _run_quality.py build`(跑兩次確認冪等) | 第二次 git diff 為空 |
| `_normalize_robots.py` 的 UA 清單 | `python _normalize_robots.py` + **同步三檔**(見下) | `_check_robots.py` |
| `vercel.json`(redirect/header) | 不用 regen | `_check_deployment.py` + codex review |
| `assets/inline/*.js` | 不用 regen(非 min 化對象);跑 `_check_js_syntax.py` | `_check_runtime_smoke.py` |
| `blog/blog-shared.js` 或 `blog-hub.js` | `python _minify.py`(重生 .min.js) | `_check_min_balance.py`, smoke;忘了重生也沒關係 —— `_check_min_sync.py` 已在 gate 裡擋(TD-28) |
| 新增 TL;DR(`_inject_tldr.py` 的 map) | 醫師審核後 `python _inject_tldr.py --apply` → `python _run_quality.py build` | gate;絕不覆寫既有 dn-tldr |

## ⚠️ 三檔同步鐵則:AI 爬蟲政策
`robots.txt`、`.well-known/ai.txt`、`llms.txt` 三處都描述爬蟲政策,**政策方向必須一致(不得互相矛盾)**。
`robots.txt` 是權威且列得最全(當前列 30 支 AI 爬蟲);`.well-known/ai.txt`/`llms.txt` 可為**精選子集**(未必逐一列同一份名單),
但**絕不能**放行 robots.txt 所封鎖者、或封鎖其所放行者(Codex 曾兩度因此退件)。政策現況(詳見 DECISIONS.md D-06):
- **引用型爬蟲允許全站**:ChatGPT-User, OAI-SearchBot, PerplexityBot, Claude-User,
  Claude-SearchBot, ClaudeBot, Claude-Web, Google-Extended, Perplexity-User, DuckAssistBot, AI2Bot, Applebot
- **訓練型/掃站型封鎖**(但可抓 llms*.txt + sitemap):GPTBot, anthropic-ai, CCBot,
  Applebot-Extended, cohere-*, Diffbot, FacebookBot, Amazonbot, Bytespider, omgili*, SEO 掃描器
改政策的唯一入口:`_normalize_robots.py`(robots.txt)+ `_normalize_ai_well_known.py`(ai.txt)
+ 手改 `llms.txt` 的 Robots policy 段 → 三處一起改 → `_check_robots.py`(含 REQUIRED_BLOCKED 防護)。

## 發佈與 CI
- **push main = 立即部署**(Vercel)。每次 push 前先跑 `python _run_ci.py`：完整 build、
  HTML validator、Lighthouse collect 與 assertion；門檻由 `.lighthouserc.json` 共用。
  檢查失敗或缺少工具即停止。紀錄寫到系統暫存目錄，保留各項退出碼與日誌。
- 環境：Python 3.12、Node 20、Java 21、OpenSSL；
  `pip install html5validator==0.4.2 lxml==6.1.3`；
  `npm install -g @lhci/cli@0.13.0 puppeteer@24.43.1`。
  將全域 npm 模組目錄 (`npm root -g`) 設為 `NODE_PATH`，必要時以 `CHROME_PATH` 指定測試 Chrome。
  Windows 的 Git 附帶 OpenSSL 可加入 PATH。本機 HTTPS 使用暫時憑證；只信任該次
  憑證的公鑰，不更動系統信任或網路防護設定。
- `deploy.ps1` 只發布已準備好的 main commit，不自動 stage、stash、rebase 或處理衝突。
  須先完成 review／醫療內容核可，且工作目錄乾淨；build 產生差異時，先審查、提交生成物再重跑。
  推送後執行 `python _verify_remote_ci.py <完整 SHA>`（需已登入的 GitHub CLI），
  同一 SHA 的所有適用 GitHub 檢查全綠才能宣告交付。
- CI 只驗證生成物一致性，不自行回推或使用 skip token。後台直接編輯造成生成物過期時，
  必須先同步、重生與驗證，CI 不會替未驗證的版本另建發布 commit。
- **排程發佈**:`drafts/<slug>` 分支 + `.github/scheduled-publish/queue.json`,
  scheduled-publish.yml 每 15 分鐘 merge 到期項目。
- **IndexNow**(indexnow.yml + `_submit_indexnow.py`):deploy 後 ping Bing/Yandex 等。
  Google 不吃 IndexNow — Google 收錄靠 GSC sitemap(已提交)。
- 其他 CI:a11y.yml(pa11y)、hyperlink.yml(斷鏈)、schema-validator.yml、vale.yml(文風)。

## 已知管線地雷
- 一次性 `_build_ad_*.py`、`_fix_ad_articles.py`、`_extract_pdfs.py` 寫死**舊電腦路徑**,
  重跑會 crash — 它們是歷史工具,不在 REGEN_STEPS 裡,**不要跑也不必修**(除非要用)。
- `_check_balance.py`/`_check_min_balance.py` 已改為相對路徑(2026-06 修復),可正常跑。
- regen 全量約需數分鐘;只想驗單項時先跑對應 `_check_*.py`,但 push 前仍要完整 gate。
