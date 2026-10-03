# PIPELINE.md — 建置管線地圖(源頭 → 生成器 → 產物)

> 發佈入口：生成器順序不變；發佈改走 `REMOTE_CI_DELIVERY.md` 的 codex/* → 完整候選 CI／PR／Preview → 同 SHA main。`deploy.ps1` 只發布乾淨且候選驗證通過的 SHA，不自行 stage/rebase。排程工作只準備本機候選 bundle，保留遠端 queue 與來源草稿分支，不自行推送或上線。

候選驗證同時核對該來源 SHA 的 push 與適用 PR workflows、最新完整 attempt、jobs 與 steps。
PR 的來源分支、同庫 main 基線和完整差異檔案數必須一致，驗證後會再次核對 PR 身分。
Vale 沿用工作流原有文章／樣式路徑篩選；僅在完整 PR 檔案證據證明不適用且沒有實際
PR 執行紀錄時，才不要求該 PR workflow。已有失敗紀錄不能藉路徑篩選忽略。
PR Delivery 的 Preview browser／Production smoke 沿用原本 event 條件略過，候選 push
的 Preview 與正式 main 的 Production smoke 仍必須通過。Python pre-push 門檻與
Vercel 正式建置前後門檻共同執行這份 `_delivery_policy.json` 契約。

> 目的:讓任何 session 一眼分清「哪些檔案是**源頭**(可手改)、哪些是**生成物**(絕不手改)」,
> 以及「改了 X 之後要跑什麼」。順序的唯一權威是 `_run_quality.py` 的 `REGEN_STEPS`(~46 步)
> 與 `CHECK_STEPS`(當前 30 步,以該檔為準)—— **本檔不複製完整清單**(會漂移),只給結構與配方。

## 一張圖看懂資料流

本機第一次執行建置／檢查前，使用 Node 20.19.0 以上並執行
`npm ci --ignore-scripts --no-audit --no-fund`。文章草稿驗證依賴鎖定的 parse5；
品質生成與完整候選 CI 的乾淨 runner 也先安裝同一份 lockfile。
排程的源碼準備階段只使用 Python 與 Node 讀取可信目錄，不執行生成器或聲稱 CI 通過。

需要跨日重建同一份 CMS 候選結果時，生成步驟可使用
`python _run_quality.py build --content-date YYYY-MM-DD` 固定內容日期。
此日期只套用於日期紀錄中首次出現或文字已變更的文章；文字未變的文章保留原日期。
省略參數時沿用當天日期。`check` 不產生檔案，因此不接受此參數。
固定日期是可重現生成的前置功能，不能證明生成結果正確、醫師核可或已上線；
仍須保存完整來源／生成結果、核對實際作者意圖並走相同 SHA 的交付門檻。

CMS 內容包的離線準備分成兩層：`_cms_generated_package.py` 記錄完整不可變 Git
樹，`_cms_patient_package.py` 再將其原始檔案與整個忽略的 `pagefind/` 搜尋輸出
封存成可攜 ZIP。封存包含逐檔原始摘要、Git 身分與來源申請；驗證不會執行或解壓文章。
ZIP 的檔案排序與時間戳固定，同一份來源與搜尋輸出會得到相同封存摘要。
封存工具拒絕連結、檔案競態、超出大小限制及缺少搜尋入口的輸出；不修改 repository
中的檔案或 Git refs。CLI 的新封存必須寫到 repository 外，既有封存不會被覆寫。
`record` 與 `verify` 仍只核對內容快照，所有 generation／content／CI／published
旗標維持 false。要另做完整輸出重建，使用
`python _cms_patient_package.py rebuild <封存.zip> --pipeline-head <目前可信 HEAD 的完整 SHA> --content-date YYYY-MM-DD`。

`_prepare_patient_review.py` 將「原稿申請」接到完整生成審閱包。指定可信 main、
不可變申請 SHA 與固定內容日期，在乾淨的隔離 checkout 執行生成及第二次完整
重播；原工作區、遠端 refs 與原稿保持不動。輸出目錄必須是系統暫存區內尚未存在的
外部目錄，包含全部 Git／Pagefind 原始輸出、manifest、source／generated Git
bundle 與摘要報告。bundle 不夾帶原稿分支的其他檔案；使用前須另以唯讀傳輸取得
同一個、仍有效的原稿申請物件。此流程尚未接入雲端自動工作流。

執行入口：`python _prepare_patient_review.py --root <乾淨隔離 checkout> --output <新系統暫存目錄> --request-head <完整申請 SHA> --file blog/<slug>.html --expected-main <完整 main SHA> --content-date YYYY-MM-DD`。
入口腳本必須位於該 `--root` checkout，HEAD 與所有 helper 原始碼均須匹配指定 main。
先驗證乾淨 checkout 與 Git blob，再從已核對的原始碼載入 helper，忽略舊 `.pyc`
及其他 checkout 的已載入模組。輸出路徑可正常化，但父目錄不得是 symlink／junction。
Pagefind 1.5.2 的入口 JSON 以固定物件鍵順序生成；保留語言、雜湊、頁數與陣列順序。
這避免原生工具的 HashMap 序列化順序漂移；審閱包仍逐檔比較全部原始位元組。
`generationVerified` 只表示兩次完整生成結果一致；報告仍標示等待生成內容核可，
不核可英文或新增摘要、不通過 CI，也不發布。後續作者核可 UI／API、完整內容
核可紀錄、Python／Node 發布門檻及實際作者雲端試用仍須完成。
日期必須與原始生成時相同；pipeline SHA 由操作者明確指定，不從封存自動取信。
重建只在系統暫存目錄執行該 SHA 的可信程式：先獨立重建原草稿與目錄、核對完整源碼樹，
再以 `npm ci` 安裝 lockfile 中的相依（停用安裝腳本）並執行現有生成步驟。
首次安裝可能需連線取得套件；生成時直接使用 lockfile 鎖定的 Pagefind 平台執行檔，
並比對七個官方平台套件中已驗證的執行檔大小與 SHA256。套件版本升級須連同
lockfile、官方套件 SHA512 與執行檔雜湊一併更新，不能只改版本號。
不使用 npx 即時解析或重新下載。封存內容不解壓執行、不使用
使用者目前的 Pagefind 檔案或 session 密鑰，原專案及 Git refs 保持原狀。
全部 Git 檔案與完整 Pagefind 原始輸出相同，才回報本次 `generationVerified=true`。
結果另記錄固定日期、pipeline／source／generated SHA、lockfile 摘要及實際工具版本；
原封存不重寫，content／live author intent／CI／published 仍為 false。
作者對完整生成內容的核可、雲端介面與正式發布仍須接入。不得把封存或重建成功當作
醫療核可、候選 CI、正式部署輸出核對或任何交付門檻的替代證據。

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
- **候選與正式發布**：本機快速檢查／相關回歸後 push `codex/*`，取得完整遠端 CI、
  同庫 PR、同 SHA Preview 與瀏覽器證據，才正常快轉相同 SHA 到 main。
  main 的正式 CI／部署／smoke 都成功才交付。詳見 `REMOTE_CI_DELIVERY.md`。
  本機 `python _run_ci.py` 可驗證完整 build、HTML validator、Lighthouse；
  門檻由 `.lighthouserc.json` 共用，本機成功不代表遠端 CI 已通過。
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
- **排程候選源碼準備（工程已隨 6c6814d 發布）**：可信 main 的排程每 15 分鐘唯讀發現
  `drafts/<slug>` 上的 `.cms-requests/<slug>.json`，不再以舊 queue 代替作者核可。
  `_process_article_requests.py` 核對固定 repo、乾淨 checkout／即時 main、申請及到期時間；
  每篇使用同一 main 的獨立暫存 clone，只複製核可文章／manifest 圖片及必要 catalog。
  不執行草稿分支程式、不合併分支、不改本機或遠端 refs／queue。Git clean filter 改動
  核可 bytes 時拒絕；建立 bundle 前後及最終報告前重查 live main／作者申請。
  舊 queue 原樣保留，缺申請、未到期、改版或衝突不自動猜測授權。產物限 runner 暫存
  目錄內的 bundle 與 report，明示 source_prepared／reviewVerified=false／ciVerified=false／
  published=false。這一階段不執行生成器或完整 CI；後續仍須獨立審查、醫療核可、
  codex 候選完整 CI／PR／Preview、同 SHA main 及正式 CI／部署核對，不能直接發布。
- **版本綁定申請驗證（工程已發布，完整作者流程尚待完成）**：候選抽取器的 --request 模式先唯讀核對 origin
  當前 drafts/<slug> head、作者申請 schema、原草稿直接 parent、文章與 manifest SHA、
  main 原文章版本及排程到期時間，結束前再次查 origin，避免使用已取消／改版的申請。
  只產生待獨立審查的源碼與準備證據，不寫 Git refs；寫檔前也重新確認工作區未變更。
  下架採專用 catalog＋noindex 候選，只改目前 main 文章的索引政策，不複製未完成草稿。
  先前 robots 政策保存在目錄，以供另經核可的恢復操作；目前不自動重新公開隱藏文章。
  --request 準備時會附上 .cms-delivery.json 的版本證據；Delivery contract 查目前申請、
  唯一 parent／申請檔 diff、原草稿／manifest／圖片與候選源碼摘要，PR 查實際 head SHA。
  main 推送重新查作者申請（若 hook 執行模型審查，審查後再查一次），Vercel 在正式建置
  前後另查即時申請。取消或後續編輯使舊候選失效；API 錯誤、缺證據、未到期都不能通過。
  證據本身不代表已部署；工程門檻、申請發現及隔離源碼 bundle 已隨 6c6814d 正式發布。
  新版草稿重設與 exact-main CI／部署觀察已接入；已發布申請的證據退役仍待完成。
  此處記錄工程上線，不宣稱已實際完成作者申請到文章發布的完整操作。
  生成器若改動核可源碼，摘要門檻會拒絕，不能手改摘要或刪除證據以規避；須完成生成內容
  與核可源碼的正式驗證流程。不能把此模式當成直接發布许可或已核可新生成英文內容。
- **IndexNow**(indexnow.yml + `_submit_indexnow.py`):deploy 後 ping Bing/Yandex 等。
  Google 不吃 IndexNow — Google 收錄靠 GSC sitemap(已提交)。
- 其他 CI:a11y.yml(pa11y)、hyperlink.yml(斷鏈)、schema-validator.yml、vale.yml(文風)。

## 已知管線地雷
- **CMS 申請紀錄退役（2026-10-01 本機新實作，尚未发布）**：
  `python _retire_cms_receipts.py --expected-main <完整正式 SHA> --check` 唯讀準備並檢查；
  沒有 active receipts 時回報 noOp，不會宣稱正式發布或建立檔案。
  要保存待審 bundle，指定 `--output <系統暫存目錄內尚不存在的新資料夾>`。
  此工具只輸出兩份待審 source bytes，不 stage／commit／push，也不寫作者草稿或 refs。
  將 bundle 套用到以同一最新 main 建立的乾淨候選，再走獨立審查／完整候選 CI／同庫
  PR／Preview／正常 main／正式 CI／部署／smoke；退役不能混入任何其他來源修改。
  `.cms-retirements/` 原有紀錄不可移除、改名或改寫；Python Delivery contract 與
  Vercel 建置前後都核對 exact published receipt、最新正式 run attempt／job／step、
  trusted Production deployment／status 及即時 main。來源或正式狀態變動使舊 bundle 失效。
  本批工程修改必須先正常交付，再另做真正的 retirement-only 候選；不能合併兩個範圍。
- 一次性 `_build_ad_*.py`、`_fix_ad_articles.py`、`_extract_pdfs.py` 寫死**舊電腦路徑**,
  重跑會 crash — 它們是歷史工具,不在 REGEN_STEPS 裡,**不要跑也不必修**(除非要用)。
- `_check_balance.py`/`_check_min_balance.py` 已改為相對路徑(2026-06 修復),可正常跑。
- regen 全量約需數分鐘;只想驗單項時先跑對應 `_check_*.py`,但 push 前仍要完整 gate。
# Word 式編輯（工程已隨 6c6814d 正式發布）

在後台開啟文章後，按「Word 編輯」。也可以在原始碼模式確認完整文章後切入。
貼上圖文會整理段落、巢狀清單、文獻連結與表格；圖片留在本機草稿，按保存後才與同一份文章快照送入雲端草稿。
「圖片說明／排序」可補替代文字、調整位置；「復原／重做」處理文件模型內的編輯。
SVG、計算器及未支援格式顯示受保護標記，保存時保留原始區塊，不在後台執行文章腳本。

Word 模式目前提供粗體、斜體、底線、刪除線、標題、清單及圖文貼上。
尚未接入的後設資料、雙語並排、圖庫等按鈕會停用；回到原有編輯或原始碼模式後恢復。
原有預覽模式若已有修改，先切換原始碼確認內容，再進入 Word 模式，避免用經過清理的預覽覆蓋原始區塊。
貼上失敗時保留原稿與剪貼簿；圖片正在整理或中文輸入仍在選字時，保存會暫緩；完成後再保存。
草稿保存與送審仍遵守候選 CI／Preview／正式發布門檻；雲端草稿保存成功不代表正式上線。

字型與文章排序目前也先存成本機設定草稿，可在同一瀏覽器重新載入。
排序草稿只有在已載入的目錄 SHA 與文章集合一致時恢復；正式來源更新時保留舊草稿，不自動套用。
這兩項設定尚未接入雲端候選發布，介面會明示未發布，不再直接寫 main。

## 生成內容二次核可（本機實作，尚未發布）

原文章送審只核可來源，不代表新生成的英文、摘要與搜尋內容已核可。
受信任的 main 管線先在系統暫存目錄生成完整病人預覽，固定內容日期與全部檔案摘要，
以 `.cms-review/<slug>.json` 保存不可變版本。預覽候選的來源核可不足以通過正式 Delivery contract。
後台「確認生成預覽」只接受同庫、相同 SHA 的成功 Preview；作者逐項檢查中文、英文、摘要
及其他變更後，勾選核可，伺服器才在既有草稿分支保存第二份版本綁定申請。
取消、較新存檔、main 更新、預覽版本錯誤或生成內容變動皆須重新準備與核可。
初次預覽與最後候選重建都沿用紀錄中的內容日期；隔天重建不會自行換成當天日期。

準備初次預覽，在與即時 main 一致的乾淨、受信任 checkout 執行：
`python _prepare_patient_review.py --request-head <來源申請完整SHA> --file blog/<slug>.html --expected-main <main完整SHA> --content-date YYYY-MM-DD --output <系統暫存新資料夾>`。
保存包內的 `patient-package.zip`、`review-manifest.json`、`objects.bundle` 與報告；
原作者草稿歷史另以完整 SHA 唯讀取得，不作為執行程式的來源。

作者在後台核可生成預覽後，使用同一受信任 main checkout：
`python _prepare_patient_review.py --approval-head <最終核可完整SHA> --file blog/<slug>.html --expected-main <main完整SHA> --archive <原patient-package.zip> --output <系統暫存新資料夾>`。
此模式從可信 main 獨立重建來源與完整生成物，全部 raw bytes 與原核可包相符才建立候選；
相對於作者預覽只升級 `.cms-delivery.json`，不再修改任何已核可病人內容。
輸出的 Git bundle 不含原作者分支歷史，驗證時須另取得最終核可 SHA。
工具不推送、不寫 main、不執行草稿或封存包中的程式，也不自動宣稱模型審查或 CI 通過。
完整獨立審查後仍走 codex 候選、完整遠端 CI、同庫 PR／同 SHA Preview／瀏覽器、
正常快轉 main，再核對正式 CI／部署／smoke。候選包及雲端核可成功都不等於已上線。
