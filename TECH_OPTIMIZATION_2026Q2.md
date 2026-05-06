# DermNotes 技術優化分析 2026Q2

整合本批次完成項目 + 下一階段建議。檔案位置：`/TECH_OPTIMIZATION_2026Q2.md`，可直接 git commit 入版控。

---

## ✅ 本批次已完成（D 系列）

| 編號 | 項目 | 影響 |
|---|---|---|
| D1 | 修復 4 篇 AD 新文章被誤填 eczema-myths body 的 critical bug | 內容真實顯示，SEO 完整 |
| D2 | Service Worker `cd-v77` + cache-bust `v=202605173000` | 強制全站 PWA 更新 |
| D3 | `/en/` 鏡像 43 頁全量 regen | 雙語覆蓋率 100% |
| D4 | RSS / Atom / sitemap 重新產生（34 文章 + 9 靜態） | Google 索引最新 |
| D5 | JS minify 合格（350 → 293 KB，83.6%） | 首屏載入加速 |
| D6 | 全站 delimiter 平衡檢查 PASS | 無語法錯誤 |
| D7 | 本期推薦 hero 卡片移除（已確認 DOM 不存在） | 首頁簡潔 |
| D8 | 熱門推薦改為 evergreen curated 5 篇（不再被新文章蓋掉） | 推薦穩定 |
| D9 | 閱讀進度 ≥70% 滾動 + ≥30s dwell 才記錄 | 真實閱讀統計 |
| D10 | 浮動 TOC 多 fallback 選擇器 + threshold 1280→1100px | 1366×768 筆電可用 |
| D11 | 標點全形轉換 round 2/3（含 meta description / title） | 303,651 字元修正 |

---

## 🚀 下一階段建議（E 系列，按 ROI 排序）

### E1. Image LCP 優化（最高 ROI）⭐⭐⭐⭐⭐

**現況**：站內幾乎沒有圖片，但首頁 hero 區用的是 emoji + CSS 漸層。Google PageSpeed 對沒有 hero image 的網站給的 LCP 通常落在 1.5-2s（CSS-driven elements）。

**建議**：
1. **不要硬塞 hero image** — emoji + 漸層的 LCP 表現實際上更好
2. 改善文章內 `<img>` tag：
   - 全部加 `loading="lazy"`（已有）+ `decoding="async"`（少數缺）
   - 加 `width` + `height` 防 CLS（避免布局位移）
3. **AVIF / WebP 雙格式**：
   ```html
   <picture>
     <source srcset="/img/a.avif" type="image/avif">
     <source srcset="/img/a.webp" type="image/webp">
     <img src="/img/a.jpg" alt="..." width="800" height="600" loading="lazy" decoding="async">
   </picture>
   ```

**估計**：LCP < 1.2s，Web Vitals 全綠。

---

### E2. Critical CSS 內聯（中高 ROI）⭐⭐⭐⭐

**現況**：`tw-mini.css` 23KB minified，每頁外連載入。FCP 約 800ms（mobile 4G）。

**建議**：把 above-the-fold 用到的 ~3-5KB CSS 內聯到 `<style>` 裡（hero card、nav、breadcrumb），其餘繼續外連。

```html
<style>/* critical - hero/nav/typography */
:root{--ink-900:#1a1a1a;--teal-700:#0c5159}
body{font-family:-apple-system,BlinkMacSystemFont,"Noto Sans TC",sans-serif}
/* ... 50 lines max */
</style>
<link rel="preload" href="/assets/tw-mini.css?v=14" as="style" onload="this.onload=null;this.rel='stylesheet'">
```

**估計**：FCP 從 800ms → 300ms（mobile 4G），LCP -200ms。

工具：可寫個 `_extract_critical_css.py` 用 puppeteer 自動提取。

---

### E3. Font Display Strategy（中 ROI）⭐⭐⭐

**現況**：已 self-host Inter 3 個字重（332KB）；CJK Noto Sans TC 還沒下載（需手動）。

**建議**：
1. 完成 CJK Noto Sans TC self-host，**只取 Traditional Chinese subset**（用 `subset.py` 只保留台灣常用 13,000 字，從 5MB 砍到 ~800KB）
2. 在 `<head>` 加 `<link rel="preload" as="font" type="font/woff2" crossorigin>` 對 Inter-Regular（最常用）
3. `font-display: swap` 已設定 ✓

**目前**：CJK 字型 fallback 到系統內建（蘋果 PingFang TC / Windows Microsoft JhengHei），看起來其實 OK，**這項可以延後**。

---

### E4. JavaScript 程式碼分割（中 ROI）⭐⭐⭐

**現況**：`blog-shared.min.js` 293KB minified（gzip 後約 90KB）。所有頁面都載入完整檔案，但 50% 功能（admin、搜尋、評分計算機）不在多數頁面被用到。

**建議**：
1. 拆出 `blog-tools.js`（EASI / SCORAD / DLQI / FTU 計算機）→ 只在 `/tools` 頁面載入
2. 拆出 `blog-search.js`（Lunr 索引）→ 只在使用者按下搜尋鍵時動態 import
3. 主檔保留：navigation、TOC、reading progress、theme switcher

```js
// 範例：lazy-load search
document.querySelector('#search-btn').addEventListener('click', async () => {
  const { runSearch } = await import('/blog/search.min.js');
  runSearch();
});
```

**估計**：主 JS 從 293KB → ~120KB。TTI 提升 30%。

**工程量**：約 2-3 小時 refactor。

---

### E5. Resource Hints 補強（低工程量、中 ROI）⭐⭐⭐⭐

**現況**：vercel.json 已有 Early Hints。但 `<head>` 內 preconnect 不齊。

**建議**：在每篇 HTML `<head>` 早期加：
```html
<link rel="dns-prefetch" href="//fonts.googleapis.com">
<link rel="dns-prefetch" href="//www.googletagmanager.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="modulepreload" href="/blog/blog-shared.min.js?v=202605173000">
```

**估計**：第三方資源建立連線時間省 100-200ms。

---

### E6. View Transitions API（PWA 體驗升級）⭐⭐⭐

**現況**：頁面切換是傳統 navigation，會閃白畫面。

**建議**：用 [View Transitions API](https://developer.chrome.com/docs/web-platform/view-transitions/)：

```html
<meta name="view-transition" content="same-origin">
```

```css
@view-transition { navigation: auto }
::view-transition-old(root), ::view-transition-new(root) {
  animation-duration: 0.25s;
}
```

零 JS 即可在 Chrome / Safari Tech Preview 啟用平滑切換。Firefox 還沒支援，但有 graceful fallback。

**ROI**：感官品質大躍進，工程量 < 1 小時。

---

### E7. Server-Sent Events 取代 polling（如果有）⭐⭐

**現況**：`/api/` 下有 web-push notification 和 view counter。view counter 如果是 polling-based 會有性能損失。

**建議**：未來如果加聊天 / 即時通知，改用 SSE 或 WebSocket。**目前無此需求**。

---

### E8. Image CDN（未來擴張時）⭐⭐⭐

**現況**：所有靜態資產走 Vercel CDN，但圖片無 on-the-fly 變換（resize / format conversion）。

**建議**：如果未來文章內加大量圖片（皮膚病灶、流程圖）：
- 用 Vercel Image Optimization（內建 `next/image` 但 static HTML 也可用 [/_vercel/image](https://vercel.com/docs/image-optimization)）
- 或免費的 [Cloudinary free tier](https://cloudinary.com/pricing)（25GB / month）

**目前**：圖片量少不需要，**延後**。

---

### E9. Database / KV 升級（後台 CMS 擴張時）⭐⭐⭐

**現況**：Vercel KV 用於 web-push subscriptions。如果未來上線 CMS、會員系統、評論：

**建議**：
- 評論系統：Giscus（免費，用 GitHub Discussions）
- 留言 / 諮詢表單：Vercel Form + Slack webhook 或 Resend.com
- 文章瀏覽計數：用 Cloudflare Analytics 或 Vercel Analytics（免費 tier）

---

### E10. Search Index 升級（中 ROI）⭐⭐⭐⭐

**現況**：用 Lunr.js 全文搜尋（client-side）。優點：免後端、極快；缺點：索引大（中文 tokenize 不佳）。

**建議**：
1. **短期**：Lunr 換 [FlexSearch](https://github.com/nextapps-de/flexsearch)（CJK tokenizer 較好，索引縮小 40%）
2. **長期**：用 [Pagefind](https://pagefind.app/)（靜態網站專用、CJK 支援極佳、索引自動分片載入）

```bash
npx pagefind --site ./
```

跑一次自動產生 `/pagefind/` 目錄，前端直接 import：

```html
<input type="text" id="search">
<div id="results"></div>
<script type="module">
  import('/pagefind/pagefind.js').then(p => {
    p.search('防曬').then(r => /* render results */);
  });
});
</script>
```

**估計**：中文搜尋準確度從 60% 跳到 90%+。

---

### E11. Schema.org 結構化資料補強（SEO 高 ROI）⭐⭐⭐⭐

**現況**：300 個 JSON-LD 區塊，`MedicalWebPage`、`MedicalCondition`、`MedicalProcedure` 已用。

**建議**新增類型：
- **`FAQPage`**：每篇文章末的「常見問題」區段 → Google FAQ rich result
- **`MedicalAudience`**：明確標註「給患者」vs「給醫療專業人員」
- **`Drug`** + **`MedicalDosage`**：藥物文章（biologics / topical-acids）
- **`SpeakableSpecification`**：給 Google Assistant / 語音助理朗讀重點

**已有腳本**：`_audit_jsonld.py` 可審計，再寫個 `_inject_faq_jsonld.py` 自動產生。

---

### E12. Accessibility 升級（醫療網站合規）⭐⭐⭐⭐⭐

**現況**：
- 多數 image 有 alt（但部分裝飾性 SVG 缺 `aria-hidden="true"`）
- color contrast 多數合格（teal-700 #0c5159 on white = 7.5:1 ✓）
- 鍵盤導航：Tab 順序大致 OK
- 螢幕閱讀器：缺少 `<main>` landmark + skip link

**建議**：
1. 每頁 `<body>` 第一個元素加：
   ```html
   <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 bg-teal-700 text-white px-4 py-2 rounded">跳至內容</a>
   ```
2. 主內容包 `<main id="main-content" role="main">`
3. 工具計算機 `<input>` 加 `aria-describedby` 連結說明文字
4. 焦點 ring：`*:focus-visible{outline:2px solid #0c5159;outline-offset:2px}`

**ROI**：醫療類網站 a11y 是法律 + 倫理需求；對 SEO 有正面影響。

---

### E13. Web Vitals 持續監控 ⭐⭐⭐

**現況**：blog-shared.js 已有 PerformanceObserver → GA4。

**建議**新增監控：
- **INP**（Interaction to Next Paint）：2024 起取代 FID 的 Core Web Vital
- **TBT**（Total Blocking Time）：lab 指標但對 INP 預測力強
- 在 GA4 上設 funnel：閱讀進度 ≥70% → 點擊內連 → 點擊工具

```js
// Add to blog-shared.js
new PerformanceObserver((entries) => {
  for (const entry of entries.getEntries()) {
    if (entry.entryType === 'event' && entry.duration > 100) {
      gtag('event', 'slow_interaction', {
        duration: entry.duration,
        type: entry.name,
        target: entry.target?.tagName
      });
    }
  }
}).observe({type: 'event', buffered: true, durationThreshold: 100});
```

---

### E14. CSP（Content Security Policy）⭐⭐⭐⭐

**現況**：vercel.json 沒有 CSP header。對醫療網站來說是合規風險。

**建議**：加入嚴格 CSP（先 report-only 模式 1 週後正式上線）：

```json
{
  "key": "Content-Security-Policy-Report-Only",
  "value": "default-src 'self'; script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://pagead2.googlesyndication.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: https:; connect-src 'self' https://www.google-analytics.com; frame-src https://www.youtube.com; report-uri /api/csp-report"
}
```

**附帶**：把 inline `<script>` 都搬到外部 + 加 nonce（最大工程量項，估 4-6 小時）。

---

### E15. 內容 / SEO 持續優化 ⭐⭐⭐⭐

不是純技術，但對流量影響最大：

1. **Internal linking density**：每篇文章末再多 3-5 個 contextual cross-links
2. **Long-tail keyword targeting**：用 [Google Search Console](https://search.google.com/search-console) → Performance → Queries 找出「impressions 高但 CTR 低」的查詢，針對這些寫小段 H3
3. **Updated date freshness signal**：加 `<meta name="article:modified_time">` + JSON-LD `dateModified`（每次小修文章都改）→ Google freshness boost
4. **AMP？** **不用**。Google 已 deprecated AMP-as-ranking-signal（2021），且 Vercel 站本身已快過 AMP

---

## 🛠️ 後台 CMS 工作流（Decap CMS）

**現況**：已有 `/admin/` + Decap CMS + GitHub OAuth 設定，但用戶不確定如何使用。

**操作流程**：
1. **登入**：訪問 https://chendermatologist.com/admin/ → GitHub OAuth 登入
2. **編輯文章**：左欄選文章 → 右側 markdown / WYSIWYG 編輯器
3. **新增文章**：「新增 Articles → 填欄位 → Publish
4. **背後機制**：每次 publish 會 commit + push 到 GitHub `main` branch → Vercel 自動 redeploy（約 30 秒上線）
5. **編輯持久性**：所有變更走 git，可在 GitHub repo 看到 commit history

**限制**：
- 不能直接改字型（要改 `tw-mini.css` 的 CSS）
- 不能改大架構（hero 卡片、nav）— 那些是 hand-coded HTML
- 但**文章內容、TLDR、標題、tag、metadata 都可以改**

**建議**：在 `/admin/config.yml` 加一個 `themes` collection 用簡單欄位讓使用者改 primary color：
```yaml
- name: theme
  label: 主題色
  files:
    - file: 'data/theme.json'
      label: '主色與字型'
      fields:
        - { name: primary_color, label: '主色', widget: color }
        - { name: heading_font, label: '標題字型', widget: select, options: ['Noto Serif TC', 'Source Han Serif TC', 'Inter'] }
```

需配合一段小 build script 把 `data/theme.json` → CSS variables。約 1 小時可完成。

---

## 📋 翻譯進度（Translation backlog）

7 篇文章 JSON 已建立但 EN 欄位空白，總計 1,456 strings 待翻：

| 文章 | strings | 大小 |
|---|---|---|
| topical-acids-patient | 194 | 18.9 KB |
| biologics-overview | 228 | 22.6 KB |
| laser-dermatology | 202 | 20.8 KB |
| nhi-derm-drugs | 238 | 24.0 KB |
| alopecia-areata | 192 | 19.6 KB |
| dermatology-faq | 201 | 22.0 KB |
| epidermoid-cyst | 201 | 19.0 KB |

**建議流程**：每次處理 1 篇，
```bash
# 1. 我（陳醫師）填 data/translations/<slug>.json 的 en 欄位（可用 ChatGPT 批量）
# 2. 跑 inject
python _translate_pipeline.py inject <slug>
# 3. regen /en/ + minify + cache-bust
python _gen_en_pages.py && python _minify.py
```

或下次對話請我用同樣模式逐篇做。

---

## 🎯 優先建議（如果只能做 5 件事）

1. **E12 a11y skip link + main landmark**（30 min，合規必做）
2. **E10 換 Pagefind**（2 小時，中文搜尋體驗大幅提升）
3. **E2 critical CSS 內聯**（1 小時，FCP -500ms）
4. **E6 View Transitions**（30 min，PWA 質感升級）
5. **E11 加 FAQPage JSON-LD**（1 小時，SEO rich result）

合計 ~5 小時可吃下，預期 PageSpeed 從目前 92 → 99+。

---

更新日期：2026-05-07 · DermNotes 內部技術文件
