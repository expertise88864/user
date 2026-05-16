# DermNotes — Onboarding 完整指南

> 開新 Claude Code 視窗（或新 session）時第一個讀的文件。  
> Repo 內已有的 `README.md`、`WRITING_NEW_ARTICLE.md`、`TECH_OPTIMIZATION_2026Q2.md`、`SEARCH_CONSOLE_TODO.md` 也都仍有效；本檔做整體 navigation + 最近做的事 + 易踩雷的點。

最後更新：2026-05-16（第 711c0842 session）

---

## 1. 站台與身份

- **網址**：[chendermatologist.com](https://chendermatologist.com)
- **作者**：陳翊嘉醫師（KMU medicine → KMUH PGY → CMUH 皮膚科 R2）
- **定位**：皮膚科醫師個人衛教 + 學習筆記網站（**不是**醫院制式衛教、**不是**診所廣告頁）
- **雙語**：繁體中文主、英文鏡像（zh-Hant-TW / en）
- **雙軌**：
  - **衛教文章**（民眾語言、診間 FAQ、避免醫療廣告）
  - **學習筆記**（住院醫師等級、guideline + RCT、累積劑量等臨床細節）
- **AdSense 狀態**：核准中（之前被退「low value content」，目前在累積審核期內容）

姊妹站（共用大架構但程式碼庫分離）：
- **HsiaoEye**（眼科，太太）：`個人網頁謙/`，hsiao.chendermatologist.com
- **finance-calculators**（台灣稅務計算器）：finance.chendermatologist.com
- **BrillianceLab**（鑽石 SEO，早期專案）：本架構的祖先模板

---

## 2. 技術棧速覽

- **靜態 HTML**（純手寫、無 SSG），部署在 **Vercel**（cleanUrls）
- **PWA**：`sw.js`（service worker），離線可讀，cache version `cd-v131`（commit `c328c29`）
- **CI**：GitHub Actions（`.github/workflows/quality.yml`）
- **建置工具**：Python 3.13 + 自製 scripts（`_check_*.py`、`_gen_*.py`、`_normalize_*.py`）
- **沒有**：React、Vue、Next.js、Tailwind 編譯、CMS、資料庫 — 一切都靜態 + 自製 Python

### npm scripts 速查
```bash
npm run build       # = python _run_quality.py build (regen + audit + minify + smoke)
npm run check       # = python _run_quality.py check (audit only, 不寫檔)
npm run serve       # = node _serve.mjs (本機開發 server)
npm run minify      # 重新 minify blog/*.js
```

### Python build 重點 scripts
| Script | 用途 |
|---|---|
| `_run_quality.py build` | one-stop：跑 normalize → gen → audit → minify → smoke |
| `_gen_en_pages.py` | 從繁中 HTML 產生 `/en/` 鏡像 |
| `_gen_feeds.py` | 重新生 RSS / Atom / sitemap |
| `_gen_search_index.py` | 產生 `/assets/search-index.json` |
| `_minify.py` | minify 七個 blog/*.js bundles |
| `_check_runtime_smoke.py` | 開 server 打 5 個 page + 6 個 lazy bundles |
| `_check_static_a11y.py` | a11y + 抓壞掉的 data-zh/data-en 巢狀引號 |
| `_check_internal_links.py` | 抓壞掉的 internal href |
| `_check_performance_budget.py` | blog-shared.min.js 必須 ≤ 72 KB |
| `_translate_pipeline.py extract / inject` | 翻譯流程（見第 6 節）|

---

## 3. Repo 結構

```
DermNotes/
├── index.html                   ← 首頁（手寫；含 .article-list-item 卡片 + chip 條）
├── blog/
│   ├── index.html               ← /blog/ 文章索引頁
│   ├── topics.html              ← /blog/topics 主題地圖
│   ├── *.html                   ← 46 篇文章（每篇獨立檔，無 template engine）
│   ├── blog-shared.js (.min.js) ← 全站共用 runtime（DN.ARTICLES catalog 在這）
│   ├── blog-hub.js              ← 首頁 / blog index 用的 hub bundle（lazy load）
│   ├── blog-article-reading.js  ← TOC / 進度條（article 頁 lazy load）
│   ├── blog-article-footer.js   ← related articles / share / disclaimer（article 頁 lazy load）
│   ├── blog-article-visuals.js  ← hero / lightbox（article 頁 lazy load）
│   ├── blog-diagrams.js         ← 醫學 SVG diagrams（article 頁 lazy load）
│   ├── blog-calculators.js      ← 計算器（SCORAD/EASI/PASI…，article 頁 lazy load）
│   ├── feed.xml / atom.xml      ← _gen_feeds.py 自動生
│   └── topics/*.html            ← 主題子頁
├── en/                          ← /en/ 鏡像（_gen_en_pages.py 自動生，請勿手改）
│   ├── index.html
│   └── blog/*.html              ← 46 篇對應英文鏡像
├── data/
│   ├── nhi/derm_2025-04-23.md   ← 健保條文 source of truth（170 KB markdown）
│   └── translations/            ← *.json 翻譯字串檔（_translate_pipeline 產生）
├── assets/
│   ├── tw-mini.css?v=19         ← Tailwind 子集（手寫小型 CSS，~7 KB）
│   ├── search-index.json        ← 全文搜尋 index（_gen_search_index.py 生）
│   ├── og/                      ← Open Graph 圖片
│   └── ...
├── admin/                       ← 後台編輯器（GitHub Contents API + PAT）
├── api/                         ← Vercel serverless functions (/api/og 動態生 OG)
├── sw.js                        ← Service Worker（cache version cd-v131）
├── robots.txt                   ← 自動生 by _normalize_robots.py
├── sitemap.xml                  ← 自動生 by _gen_feeds.py
├── _serve.mjs                   ← 本機 dev server
├── _check_*.py / _gen_*.py / _normalize_*.py / _run_quality.py
├── package.json / vercel.json
├── README.md                    ← 一般介紹
├── WRITING_NEW_ARTICLE.md       ← 寫新文章流程（仍有效）
├── TECH_OPTIMIZATION_2026Q2.md  ← 早期技術筆記
├── SEARCH_CONSOLE_TODO.md       ← GSC 待辦
└── ONBOARDING.md                ← 本檔
```

---

## 4. 文章撰寫 — 完整 SOP

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

### 4.2 兩種文章模式

DermNotes 有**兩種雙語架構**並存：

| | Pattern A（41 篇舊文章）| Pattern B（5 篇新文章）|
|---|---|---|
| 結構 | `<div id="proseZh">` + `<div id="proseEn">` 兩個獨立區塊 | `<div id="proseZh">` 內每個元素 `data-zh="..." data-en="..."` |
| 切換語言 | display:none / block 切 prose div | `DN.applyTextOnly` 逐元素 swap textContent |
| 缺點 | 改內容要改兩次 | 必須每個 `<p>` `<li>` `<th>` `<td>` SVG `<text>` 都掛 hook |
| **新文章一律用** | ❌ | ✅ **Pattern B** |

**Pattern B 範例文章**：`dupilumab-long-term-maintenance.html`、`psoriasis-biologic-monitoring.html`（最新一篇）

### 4.3 新文章 SOP（按順序）

```
1. 讀 user 給的 PDF
2. 整理可被引用的醫學重點 + 列出哪些有來源、哪些需確認
3. 用 AskUserQuestion 問 user：
   - 標題候選 5 個（醫學問句 / 中性學術 / 主張）
   - 標籤（最新研究 / 衛教 / 學習筆記）
   - 是否要 AdSense 審核期適用語氣
   ⚠️ 一律先討論，不要直接寫
4. user 確認後才開工
5. 寫 HTML（複製 dupilumab-long-term-maintenance.html 當 template）
6. 加入 DN.ARTICLES catalog（blog/blog-shared.js）
7. 加首頁卡片 + chip 條（index.html）
8. Bump SW version (sw.js cd-vXXX + _check_runtime_smoke.py)
9. python _run_quality.py build（必過所有 audit）
10. git add + commit + push
11. git pull --rebase 處理 auto-regen 衝突 → push
```

### 4.4 文章 HTML template 必檢項目（從以前慘痛經驗）

- [ ] `<link rel="stylesheet" href="/assets/tw-mini.css?v=19" />`（缺了會手機版渲染）
- [ ] **不要**寫 `<div class="toc">`（auto TOC 會雙 TOC，DN.addInlineTOC 自動產）
- [ ] 暖米色背景：`--bg:#faf7f2`、`--teal:#7a9285`（**不要**用冷色 mint，舊 scaffolder 是錯的）
- [ ] SVG `font-size` 最小 14、一般 15-16、標題 17-20（**不要** 11/12/13）
- [ ] 每個 `<img>` 有 alt
- [ ] h1 只有一個
- [ ] 完整 JSON-LD：MedicalScholarlyArticle、BreadcrumbList、MedicalWebPage、FAQPage（若有 Q&A 段）、HowTo（若為 procedural）
- [ ] proseEn 對於 Pattern B 是空 `<div id="proseEn" class="prose" style="display:none"></div>`
- [ ] Vancouver references 含 PMID / DOI 連結

### 4.5 加入首頁卡片 — 必做

`index.html` 內找到最新一張 `.article-list-item` 卡片，複製為新卡片，**順序在最前**：
- href = `/blog/<slug>`
- class = `article-list-item`
- `data-cat="research"`（或 myth / rx / note）
- `data-tag-en="<英文標籤>"`
- 圖示 SVG
- 內含 `<span class="chip cat-rx">最新研究</span><span class="chip tag">...</span>` + `<time>` + `<h2>` + `<p>`

並在 chip strip（位於 index.html 約 46000 字節處）插入新標籤 chip：
```html
<a href="/blog/<slug>" style="padding:5px 11px;border-radius:9999px;font-size:12px;font-weight:600;color:#334155;background:#fff;border:1px solid var(--border);text-decoration:none" data-zh="<標籤>" data-en="<en>">標籤</a>
```

### 4.6 DN.ARTICLES catalog（`blog/blog-shared.js`）

```js
{ slug:'<slug>', title:'<中文標題>', title_en:'<English title>',
  cat:'research', tag:'<中文標籤>', date:'2026-05-16',
  emoji:'', tag_en:'<English tag>' },
```

`cat:'research'` 會自動歸到「最新研究」chip 群組（透過 `_from_cat:'research'` 動態解析）。

---

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

## 6. 翻譯流程（繁中 → 英文）

### 6.1 Pattern B 文章翻譯（新文章必用）

```bash
# 1. extract — 抓出文章中所有 CJK 純文字到 JSON
python _translate_pipeline.py extract <slug>

# 2. 翻譯 — 兩個選擇：
#    (a) Claude 在對話內直接翻（高品質、不用 API key）
#    (b) python _ai_translate.py <slug>（用 ANTHROPIC_API_KEY + Haiku，~NT$ 35/篇）

# 3. inject — 把翻好的 data-en 寫回 HTML
python _translate_pipeline.py inject <slug>

# 4. 對於 nested HTML（例 <p> 含 <strong>），pipeline 抓不到，需手動編
#    補上 data-zh / data-en 屬性

# 5. 重生 EN 鏡像
python _gen_en_pages.py
```

### 6.2 已翻譯狀態
| Pattern B 文章 | 翻譯狀態 |
|---|---|
| dupilumab-long-term-maintenance | ✅ 294/294 pairs |
| atopic-dermatitis-overview | ✅ 317/317 pairs |
| severe-scabies-treatment | ✅ 257/257 pairs |
| dermatologic-oral-examination | ✅ 277/277 pairs |
| toenail-mechanical-disorders | ✅ 328/328 pairs |
| psoriasis-biologic-monitoring | ✅ 214/214 pairs（最新）|

Pattern A 41 篇都有 proseEn mirror，視為已翻譯。

### 6.3 翻譯品質注意
- 醫療術語用臨床英文（pharmacokinetic、selection bias 等正式詞）
- NHI 條文用全名（"National Health Insurance Administration, MOHW"）
- 民國日期 → 西元日期（114/4/23 → "23 April 2025"）
- 中文引號 「」『』 → "..."
- 數值單位完整保留

---

## 7. SEO / CTR 目前狀態

### 7.1 已做（commit `c328c29`，A+B+C 全部完成）

- **首頁 title**：「皮膚科衛教筆記 \| 痘痘、乾癬、異膚、A 酸、生物製劑、健保完整解析 — 陳翊嘉醫師」
- **19 篇 meta description** 改為 96–136 字（SERP 不截斷）
- **FAQPage schema**：35/47 篇
- **HowTo schema**：5/47 篇（biopsy / scabies / oral exam / toenail / acne-scar）
- **Orphan articles**：13 → **0**（全消除）
- 所有 articles：MedicalScholarlyArticle + BreadcrumbList + MedicalWebPage + Physician JSON-LD ✓
- 47/47 `<img>` 有 alt
- 全站 canonical / hreflang x-default / og:image / twitter:card ✓
- sitemap 56 URLs 全部含 lastmod / changefreq / priority

### 7.2 剩下可做的長期戰

1. **Domain age**（新站 sandbox，無解，等時間）
2. **Backlinks**（沒同行轉貼、媒體引用 — 比技術 SEO 影響大 10 倍）
3. **巨頭佔位**（「乾癬」「痘痘」前 10 名被康健、Hello 醫師、TDA 佔了）
4. **Submit URL Inspection 到 GSC** 讓更新 schema 更快被看到
5. 觀察 GSC「曝光高但 CTR 低」query → 那篇的標題可再優化

---

## 8. 易踩雷的點（每個都至少踩過一次）

### 8.1 屬性內 HTML 必須 escape
```html
<!-- 錯：data-zh 屬性值裡有原生 " 會破壞 HTML -->
<p data-zh="參考 <a href="/blog/x">x</a>" ...>

<!-- 對：用 &lt; &quot; &gt; -->
<p data-zh="參考 &lt;a href=&quot;/blog/x&quot;&gt;x&lt;/a&gt;" ...>
```

### 8.2 用 str.replace 編 article 時的雷
若 search pattern 同時出現在 data-zh 屬性值 AND 可見 body，`replace(..., count=1)` 會打到第一個 = 屬性值，後果同上節。**對策**：要加 inline link，開新 `<p>` 比較安全；不要 append 到既有 data-zh。

### 8.3 GH Actions auto-regen 衝突
GH workflow 會自動 commit `auto-regen /en/ mirror + feeds + runtime bundles [skip actions]`。本地 push 前要：
```bash
git pull --rebase origin main
# 若 atom.xml / feed.xml 衝突：
python _gen_feeds.py
git add blog/atom.xml blog/feed.xml sitemap.xml
git rebase --continue
git push origin main
```

### 8.4 [skip ci] vs [skip actions]
- workflow 自動 commit message 一定要寫 `[skip actions]`，**不要寫** `[skip ci]`（Vercel 也會吃 `[skip ci]` → 不部署）
- 自己寫的 commit message 不能含字串「[skip ci]」（會讓 Vercel 跳過）

### 8.5 SW cache 版本
新文章上線後，老用戶因為 service worker cache 看到舊頁/舊 JS。每次新文章/重大 JS 變動：
- bump `sw.js`: `cd-v131` → `cd-v132`
- 同步更新 `_check_runtime_smoke.py` 的 assert 字串

### 8.6 Pattern B vs A 的 `_gen_en_pages.py` 行為
- Pattern A（有 proseEn 內容）：strip proseZh，留 proseEn 給 /en/
- Pattern B（proseEn 空殼）：保留 proseZh，呼叫 apply_data_en 渲染英文
- 若 Pattern A 在 proseZh 加新內容，**不會**出現在 /en/（要同步改 proseEn）

### 8.7 Performance budget
`blog/blog-shared.min.js` 上限 **72 KB**（目前 ~62 KB，commit `56913aa` 瘦身過）。新增功能前可先試移到 lazy bundle（blog-hub / blog-article-footer 等）。

### 8.8 admin 編輯後台
- 路徑：/admin（robots.txt 已 Disallow）
- 透過 GitHub Contents API + Personal Access Token 直接 commit
- 已修：fetch cache:no-store + If-None-Match:'' 避免瀏覽器 HTTP cache 把 stale 編輯吃掉
- 「暫時下架」按鈕：把 article 的 `unpublished:true` flag toggle，DN.injectUnpublishedBanner 在頁頂顯示黃色 banner，並從首頁/索引隱藏（保留在後台）

---

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

## 10. 開新視窗第一件事做什麼？

1. **讀 memory** — Claude Code 啟動會自動讀 `~/.claude/projects/...memory/MEMORY.md` 與 index 連到的所有 .md，包括：
   - `project_dermnotes.md` — 站台基本資訊
   - `article_writing_spec.md` — 醫學原則 + 文章模板
   - `dermnotes_nhi_reference.md` — 健保速查
   - `project_dermnotes_nhi_audit.md` — 校對紀錄
   - `feedback_dermnotes_*.md` — 模板、首頁卡片、調色、SVG 字體、Vercel skip-ci 等 feedback

2. **讀本檔**（ONBOARDING.md）— 整合 view + 最新 session 做的事

3. **跑一次 `npm run check`** — 確認 local 環境 OK

4. **看當前 git log -10** — 知道最近 commits 的脈絡

5. **看 user 給的新任務**：
   - 寫文章？→ 先用 `AskUserQuestion` 問標題 / 角度 / 標籤
   - SEO？→ 先查當前 GSC 數據
   - 健保？→ 查 `data/nhi/derm_2025-04-23.md`
   - 翻譯？→ 用 `_translate_pipeline.py`

---

## 11. 待辦清單（下次 session 可接的事）

- [ ] **GSC submit URL 重新索引**：c328c29 後的更新 meta + schema 還沒 ping Google
- [ ] **觀察 GSC 1-2 週數據變化**：A+B+C 修復後的 CTR / 流量影響
- [ ] **長期：找 backlink 機會**（同行轉貼、媒體訪問、學會推薦）
- [ ] **AdSense 重審**（內容累積夠了再申請）
- [ ] **若新研究值得寫**：JAAD / JID / BJD / JAMA Derm 每月 review 一次新刊 abstracts
- [ ] **HsiaoEye 站**：可比照 DermNotes 做同樣的 SEO + NHI 校對
- [ ] 補 FAQPage schema 到剩下 11 篇有 FAQ section 的舊文章（產生 +20% rich-result CTR uplift potential）

---

## 12. 一句話總結

DermNotes 是個 **46 篇文章、雙語、靜態 HTML、Vercel + GH Actions 部署的個人皮膚科衛教站**。技術 SEO 已做到 90 分，剩下卡在 domain age + backlinks（時間問題）。寫新文章請用 Pattern B（data-zh/data-en attrs）+ 醫學原則 + NHI source of truth + 衛教/醫學雙軌。NHI 條文以 `data/nhi/derm_2025-04-23.md` 為準。
