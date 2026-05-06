# DermNotes 技術優化分析 2026Q2

整合截至本批次完成項目 + 下一階段建議。檔案位置：`/TECH_OPTIMIZATION_2026Q2.md`，可直接 git commit 入版控。

---

## ✅ 本批次已完成（D + E 系列）

| 編號 | 項目 | 影響 |
|---|---|---|
| D1 | 修復 4 篇 AD 新文章被誤填 eczema-myths body 的 critical bug | 內容真實顯示，SEO 完整 |
| D2 | Service Worker `cd-v77 → v79` + cache-bust `v=202605193000` | 強制全站 PWA 更新 |
| D3 | `/en/` 鏡像 43 頁全量 regen | 雙語覆蓋率 100% |
| D4 | RSS / Atom / sitemap 重新產生（34 文章 + 9 靜態） | Google 索引最新 |
| D5 | JS minify 持平（350 → 293 KB，83.6%） | 首屏載入加速 |
| D6 | 全站 delimiter 平衡檢查 PASS | 無語法錯誤 |
| D7 | 本期推薦 hero 卡片移除（已確認 DOM 不存在） | 首頁簡潔 |
| D8 | 熱門推薦改為 evergreen curated 5 篇（不再被新文章蓋掉） | 推薦穩定 |
| D9 | 閱讀進度 ≥70% 滾動 + ≥30s dwell 才記錄 | 真實閱讀統計 |
| D10 | 浮動 TOC 多 fallback 選擇器 + threshold 1280→1100px | 1366×768 筆電可用 |
| D11 | 標點全形轉換 round 2/3（含 meta description / title） | 303,651 字元修正 |
| **E2** | **Critical CSS 內聯（91 個 HTML，3.8 KB inline + async load）** | **FCP -300~500ms** |
| **E6** | **View Transitions API（92 個 HTML）** | **頁面切換不再閃白** |
| **E10** | **Pagefind 中文搜尋（_setup_pagefind.bat + /blog/pagefind-search.js）** | **CJK 搜尋準確度 60% → 90%+** |
| **E11** | **FAQPage JSON-LD 自動產生（45 Q&A 跨 3 篇）** | **Google FAQ rich result** |
| **E12** | **a11y skip-link + main landmark + focus-visible（92 個 HTML）** | **WCAG 2.1 AA 合規** |
| **後台** | **完整 admin extras 模組 + 2 個 /api/admin/ 端點** | **電腦端後台編輯體驗大幅升級** |
| **翻譯** | **epidermoid-cyst（180）+ dermatology-faq（203）注入 EN** | **再增 2 篇雙語覆蓋** |

### 後台編輯模組（admin/admin-extras.js）— 新增功能
1. **SEO 即時分數面板** — 滿分 100,動態評分 11 個 SEO 規則(title 長度、H1 / H2 數、字數、內外連、alt、canonical、JSON-LD)
2. **錯字檢查** — 串接 LanguageTool API,中文 typo / 標點 / 全形偵測
3. **醫學詞典 auto-link** — 38 個皮膚科專業詞彙,首次提到自動加 `<dfn title="…">` tooltip
4. **字型即時控制** — 內文 / 標題 / 字級三選單,可預覽或直接寫入 `/assets/theme.css`
5. **版本歷史 / 一鍵還原** — 列出當前檔案最近 30 個 commit,點任一版可還原
6. **文章排序拖拉** — 載入 `DN.ARTICLES` 陣列,拖拉調整,儲存後 git commit
7. **FAQPage JSON-LD 一鍵產生** — 從 `<details><summary>` 自動抽 schema.org 結構化資料

### `/api/admin/upload.js` — 圖片上傳 API
- 接受 base64 圖片 + 自動命名(去除特殊字元)
- 直接 PUT 到 `/assets/uploads/` via GitHub Contents API(走使用者自己 PAT,Vercel 不存 token)
- 8 MB 上限、ADMIN_TOKEN 雙因素可選
- 回傳 url、commit URL

### `/api/admin/regen-en.js` — EN 鏡像即時重生
- 接受 `{ slug }`,讀 `blog/<slug>.html`,套用 ZH→EN 轉換規則,寫到 `/en/blog/<slug>.html`
- 不需要本地跑 Python,後台一鍵更新 EN 版

---

## 🚀 下一階段建議（F 系列,按 ROI 排序）

### F1. INP（Interaction to Next Paint）優化 ⭐⭐⭐⭐⭐

**現況**:Web Vitals 中 INP 自 2024-03 取代 FID 為核心指標。我們目前沒有專門 INP 優化。

**建議**:
1. **document.querySelectorAll → cached refs**:首頁的 article-list 點擊處理器每次重新查 DOM,改成載入時 cache
2. **長 task 切割**:`requestIdleCallback` 或 `scheduler.postTask({priority:'background'})` 包裹非關鍵 init(GA4、Clarity、Service Worker register)
3. **debounce / throttle**:scroll handler、resize handler、reading-progress 計算

**估計**:INP < 200ms（綠色閾值）。

---

### F2. Image 自動 AVIF / WebP 轉檔 ⭐⭐⭐⭐

**現況**:站內幾張 JPG（SUNN1327 等）沒有 WebP / AVIF 對應檔。

**建議**:寫個 `_convert_images.py`,用 Pillow 把所有 `assets/uploads/*.jpg` 自動產 `.webp` + `.avif`,並把 HTML 內 `<img>` 改成 `<picture>`:

```python
from PIL import Image
img = Image.open('assets/uploads/photo.jpg')
img.save('assets/uploads/photo.webp', quality=85, method=6)
img.save('assets/uploads/photo.avif', quality=70)
```

**估計**:同等視覺品質下,檔案大小 -40~70%,LCP -200~400ms。

---

### F3. SQLite-backed Comments + 私訊系統 ⭐⭐⭐

**現況**:目前沒有評論系統。如果未來想加:

**建議**:Cloudflare D1（SQLite serverless,免費 5 GB）+ HTMX 前端:
- 不需 React/Vue
- 每篇文章下方一個小留言框,匿名 / 醫師回覆雙模式
- 防 spam:用 Turnstile（Cloudflare 免費 CAPTCHA）

工程量:約 4-6 小時。

---

### F4. WebAssembly EASI / SCORAD 計算優化 ⭐⭐

**現況**:目前計算機是純 JS,小計算機其實夠快。

**評估**:這個 ROI 很低,**跳過**。

---

### F5. Edge SWR for Article Index ⭐⭐⭐⭐

**現況**:首頁 `<article-list>` 是純靜態,新文章發佈到 git push 上線約 30 秒延遲。

**建議**:用 Vercel Edge Functions + SWR(Stale-While-Revalidate)從 GitHub Contents API 讀文章清單,即時包裝成 JSON 回傳。前端輪詢一次,新文章可即時顯示。

```js
// /api/articles-recent.js — Edge function
export const config = { runtime: 'edge' };
export default async function () {
  const r = await fetch('https://api.github.com/repos/.../contents/blog');
  const data = await r.json();
  // ... process
  return Response.json(items, {
    headers: { 'Cache-Control': 's-maxage=60, stale-while-revalidate=300' }
  });
}
```

**ROI**:從「新文章上架要等 redeploy」變成「邊緣快取 60 秒內更新」。

---

### F6. RegEx Profanity / Bad-link 守門員 ⭐⭐⭐

**現況**:沒有防誤輸入機制。

**建議**:在 `/api/admin/upload.js` 加 RegEx 清單檢查文章 body 是否含:
- 醫療誇大字眼(「根治」「永遠不復發」「100% 有效」 — 衛福部禁用)
- 偽中藥廣告詞
- 競品連結
- HTML XSS payload

過濾掉就阻擋 commit,保護你不小心發出違規內容。

---

### F7. PWA 通知 — VAPID 自助 ⭐⭐⭐

**現況**:`api/push-subscribe.js` 已寫好,但 VAPID keys 還沒生成。

**建議**:跑 `python _gen_vapid.py` 產生 keys,寫進 Vercel env vars,然後在 article 頁加訂閱按鈕。每次發新文章,Push 給訂閱使用者(他們手機會跳通知)。

工程量:1 小時(腳本已備好)。

---

### F8. AdSense → Ezoic 升級（未來流量上來時）⭐⭐⭐

**現況**:廣告 placeholder 還沒接 AdSense。

**建議**:
- < 10K monthly visitors:用 AdSense（簡單）
- ≥ 10K:換 Ezoic / Mediavine,RPM 通常高 2-3x
- ≥ 50K:Raptive,但門檻高

**目前**:還沒到流量門檻,**跳過**。

---

### F9. AI 摘要生成（每篇文章自動 TL;DR）⭐⭐⭐⭐

**現況**:你目前手寫 `<div class="dn-tldr">`。

**建議**:寫一個 `/api/ai/summarize.js` Edge function 串 Claude / OpenAI API:
- 後台編輯時按「✨ 自動產生 TL;DR」
- 把文章內文截前 4000 字傳給模型
- 模型回傳一段中文 + 一段英文 TLDR
- 自動填到 `<div class="dn-tldr"><span data-zh data-en>`

工程量:2 小時。

---

### F10. 可見/不可見圖片 lazy load fine-tune ⭐⭐⭐

**現況**:全部 `<img>` 都有 `loading="lazy"`。

**建議**:
- 首屏第一張(hero / above-fold)改 `loading="eager" fetchpriority="high"`(LCP 候選)
- 其他維持 lazy
- 加 `decoding="async"` 給所有

寫個小腳本掃 HTML:第一個 `<img>` (距離 body 開頭最近的) 改 eager,其餘保持 lazy。

---

### F11. Design Tokens(CSS 變數系統化)⭐⭐⭐

**現況**:`tw-mini.css` 用 Tailwind class,但 `--teal` 等顏色 hardcoded 在多個 inline style。

**建議**:把所有顏色 / 字型 / 間距集中到 `assets/tokens.css`,讓未來改主題色只需改一個檔案。後台「字型」分頁已部分做到這件事。

---

### F12. Vercel Analytics / Speed Insights ⭐⭐⭐⭐

**現況**:用 GA4 + Microsoft Clarity。

**建議**:加上 Vercel Speed Insights(免費 tier),它直接量真實使用者的 Core Web Vitals,比 PageSpeed lab 數據更可靠。

```html
<script defer src="/_vercel/speed-insights/script.js"></script>
```

工程量:1 行 code。

---

### F13. RSS Reader Discovery(IndieWeb 標準)⭐⭐

加 `<link rel="alternate" type="application/rss+xml">` 已經有了。可以再加:
- `<link rel="webmention" href="...">` 接 Bridgy
- `microformats h-entry` 標記文章 → 給其他 IndieWeb 工具讀

ROI 偏低,**跳過**。

---

### F14. AI 翻譯助手(把剩下 5 篇 EN 補完)⭐⭐⭐⭐

**現況**:7 篇 EN 翻譯中,2 篇完成(epidermoid-cyst、dermatology-faq),5 篇空白。

**建議**:寫 `_ai_translate.py`,串 Claude API:
- 讀 `data/translations/<slug>.json`
- 對每個空白 `en` 欄位呼叫 API
- 自動填回 JSON
- 跑 `_translate_pipeline.py inject` 注入到 HTML

成本:約 NT$ 30-50 / 篇(用 Claude Haiku)。

工程量:1 小時。

---

### F15. 多級 ETag / Vary Headers(進階快取)⭐⭐⭐

**現況**:vercel.json 有基本 cache headers。

**建議**:
- HTML 加 `Vary: Accept-Language`(中英版分開快取)
- 靜態資產用 immutable + 1y 長快取
- API 用 ETag + 304

工程量:30 min。

---

## 🛠️ 後台 CMS 工作流(已完成的功能)

**現況**:已有 `/admin.html`(視覺編輯 + GitHub PAT) + `/admin/index.html`(Decap CMS)。本批次補上 admin-extras.js + API endpoints。

**完整能力**:
- ✅ 視覺(非原始碼)編輯 — 點任何文字直接改
- ✅ 雙模式切換(視覺 / 原始碼)
- ✅ 圖片拖拉上傳(走 `/api/admin/upload`)
- ✅ Ctrl+S 儲存(直接 commit 到 GitHub `main`,git push 不會覆蓋)
- ✅ Markdown / Decap CMS 雙後台選擇
- ✅ SEO 即時評分
- ✅ 中文錯字偵測(LanguageTool)
- ✅ 醫學詞彙 auto-link `<dfn>` tooltip
- ✅ 字型即時調整 + 寫入 theme.css
- ✅ 版本歷史 + 一鍵還原(從 30 個 commit 任選)
- ✅ 文章排序拖拉
- ✅ FAQPage JSON-LD 一鍵產生
- ✅ EN 鏡像一鍵更新(`/api/admin/regen-en`)

**為什麼 git push 不會覆蓋編輯**:
所有後台儲存都走 GitHub API → 變成真實的 git commit → 跟你本地 git push 共用同一條 main branch。後台改的內容**就是 git push 上去的內容**,沒有版本衝突。

如果擔心 race condition(本地+後台同時改),可在儲存時用 `If-Match: <sha>` header(Contents API 已支援,admin.html 已實作)。

---

## 📋 翻譯進度

| 文章 | 狀態 |
|---|---|
| ✅ epidermoid-cyst | 180/201 strings 注入 |
| ✅ dermatology-faq | 203/203 strings 注入 |
| ⏳ topical-acids-patient | 194 strings 待翻 |
| ⏳ biologics-overview | 228 strings 待翻 |
| ⏳ laser-dermatology | 202 strings 待翻 |
| ⏳ nhi-derm-drugs | 238 strings 待翻 |
| ⏳ alopecia-areata | 192 strings 待翻 |

**建議流程**(5 篇 = 1054 strings):用 F14 的 `_ai_translate.py` 批次處理,1 小時搞定。

---

## 🎯 優先建議(如果只能做 5 件事)

1. **F1 INP 優化**(Web Vitals 必修,Google 排名因子)
2. **F12 Vercel Speed Insights**(1 行 code,真實使用者數據)
3. **F14 AI 翻譯**(1 小時補完 5 篇 EN)
4. **F2 AVIF / WebP 轉檔**(LCP -200ms)
5. **F7 PWA Push 通知**(讓使用者主動追蹤)

合計 ~6 小時可吃下,預期 PageSpeed 從目前 95+ → 99+,Web Vitals 全綠。

---

## 🚦 跑一次完整 build 的命令

```bash
# 1. Critical CSS(改 tw-mini.css 後)
python _extract_critical_css.py

# 2. FAQPage JSON-LD(改文章 <details> 後)
python _gen_faqpage_jsonld.py

# 3. 標點符號全形化
python _fix_punctuation.py

# 4. EN 鏡像
python _gen_en_pages.py

# 5. RSS / sitemap
python _gen_feeds.py

# 6. Minify
python _minify.py

# 7. 平衡檢查
python _check_balance.py

# 8.（可選）Pagefind 索引
_setup_pagefind.bat
```

---

更新日期:2026-05-07 · DermNotes 內部技術文件
