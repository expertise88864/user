# 新增一篇衛教文章 SOP

> 適用於 ChenDermatologist。醫療文字與英文翻譯取得醫師核可後，完成來源與生成物、本機相關檢查、候選 CI／Preview、正常快轉 main，以及同 SHA 正式 CI／部署／smoke，才算正式交付。存檔、生成英文版或單次 CI 成功各代表不同階段。

---

## 0. 寫之前先想清楚

| 項目 | 決定 |
|---|---|
| 主題 | 例：口周皮膚炎 |
| slug（URL）| 例：`perioral-dermatitis-guide`（英文小寫、hyphen） |
| category | `myth` / `product` / `rx` |
| 主要參考來源 | guideline / systematic review / RCT / major journal review — **不可捏造** |
| 是否討論台灣健保 | 台灣商品名與健保狀態要單獨查證並標來源 |

---

## 1. 兩個語言版本是「必須」，不是 nice-to-have

**規則**：所有新文章都必須同時生成英文版。EN 不可以只是 stub。

技術原因：`_gen_en_pages.py` 會用兩種方式產出 `/en/blog/<slug>.html`：
1. 從元素的 `data-en` 屬性取代 inner HTML
2. 或者整段以 `<div id="proseEn">` 並排區塊取代 `<div id="proseZh">`

**推薦做法（也是 POD 文章用的方式）：proseEn 並排區塊**，保留完整對照內容，方便生成英文鏡像；英文索引策略維持 D-17：

```html
<article ...>
  <div id="proseZh" class="prose">
    ... 中文完整內容 ...
  </div>
  <div id="proseEn" class="prose" style="display:none">
    ... English full content ...
  </div>
</article>
```

`_gen_en_pages.py` 中的 `prefer_static_english_blocks()` 會在生成 EN mirror 時把 `proseZh` 整段拿掉，留 `proseEn`，並把 `display:none` 拿掉。

---

## 2. SOP — 從零到上線

### Step 1：scaffold

```powershell
powershell -ExecutionPolicy Bypass -File new-article.ps1
```

輸入 slug 後，PS 腳本呼叫 `_scaffold_article.py`，從維護中的既有文章複製結構至 `blog/<slug>.html`。
這是本機草稿：必須更換模板的標題、內文、圖表、引用與 metadata，取得醫師核可，
另行登錄 `DN.ARTICLES` 並生成該頁的 PNG 分享卡。腳本不直接修改 sitemap、feeds 或 SW precache；
這些由正式生成管線負責。發布流程與完整 CI 工具設定見 [PIPELINE.md](PIPELINE.md)。

### Step 2：補完 ZH 內容（proseZh）

把 scaffold 出來的 `<div id="proseZh">` 內補上：
- TL;DR card
- TOC
- 30 秒重點結論
- 民眾常見問題 Q&A（建議 6–10 題，能寫成 `<details><summary>` 也行 — 後者可由 `_gen_faqpage_jsonld.py` 自動抽 FAQ schema）
- 正文章節
- SVG 圖（inline，不要 base64 img）
- 迷思澄清卡片（`.myth-card`）
- 進階補充區塊（`.advanced`）
- 延伸閱讀（`<a href="/blog/...">`）
- 參考資料（Vancouver style，每篇要有 PMID 或 DOI）

### Step 3：寫 EN 並排區塊（proseEn）

複製 ZH 的結構，全部翻成英文，包到：

```html
<div id="proseEn" class="prose" style="display:none">
  ...英文版整篇...
</div>
```

放在 `<div id="proseZh">...</div>` **後面**、`</article>` **前面**。

**EN 內部錨點請加 `en-` 前綴**（例：`<h2 id="en-intro">`、`<a href="#en-intro">`），避免和 ZH 的 id 衝突。

**EN 的延伸閱讀連結要指向 `/en/blog/...`**，不是 `/blog/...`：

```html
<a href="/en/blog/rosacea-myths">Rosacea: complete patient guide</a>
```

### Step 4：在 `_gen_en_pages.py` 加 `EN_OG_OVERRIDES`

打開 [`_gen_en_pages.py`](_gen_en_pages.py)，找到 `EN_OG_OVERRIDES` dict，加上新文章：

```python
'blog/<slug>.html': {
    'title': 'English Title | Suffix',
    'desc': 'English meta description, 50-160 chars.',
},
```

不加的話 EN 鏡像的 `<title>` 和 `<meta description>` 會 fallback 成「Dermatology Patient Education」的通用 stub — SEO 很糟。

### Step 5：跑生成腳本

```bash
python _run_quality.py build
```

這會依正式順序生成英文鏡像、schema、feeds、搜尋索引及 runtime bundles，並執行完整品質檢查。英文 canonical 依 D-17 維持指向中文版本。GitHub Actions 只核對生成物是否一致，不會自動提交缺少的生成物；所有此次需要交付的來源與生成檔都必須先在本機完成。

### Step 6：核對本機檢查與獨立審查

```bash
python _run_quality.py check
```

依實際變更執行本機快速檢查、相關回歸及必要生成，並完成專案要求的獨立模型審查。完整本機 CI 可作額外診斷；候選 push 依 2026-09-06 定案，不要求先跑完整本機 CI。環境需求與日誌位置見 [PIPELINE.md](PIPELINE.md)。新的修改、生成或整合會使舊版本證據失效。

### Step 7：候選、Preview 與正式發布

先以 `git status --short` 和 `git diff` 核對此次來源與生成檔，逐項加入本次提交，不要混入其他工作。醫療文字須取得醫師核可；完成專案要求的獨立模型審查後，再建立此次提交。

將本次來源與生成物提交至 `codex/*` 候選分支，正常 push，沿用或建立同庫 PR。完整遠端 CI、同 SHA Vercel Preview 與瀏覽器驗收全部通過後，才可正常快轉 main。候選驗證命令：

```text
python _delivery.py verify <候選完整SHA> --phase candidate --wait 1800
```

main 更新後，另核對同 SHA 正式 CI、Production 部署與 smoke 成功，再確認公開頁面。完整步驟依 [REMOTE_CI_DELIVERY.md](REMOTE_CI_DELIVERY.md)；後台作者操作見 [AUTHOR_WORKFLOW.md](AUTHOR_WORKFLOW.md)。遠端 CI 不會替作者自動補檔或提交；若失敗，在本機修正並以新版本重新走完整交付流程，不沿用舊綠燈。

---

## 3. 看不到新文章？先確認正式發布，再檢查快取

**這個 repo 使用 PWA Service Worker (`sw.js`) 保存網站外殼與 `/blog` 索引。** 先核對目前版本的正式 CI、部署及公開頁 smoke；舊快取只是可能原因，不能先假設文章已上線。

### 三種解法

| 方式 | 怎麼做 |
|---|---|
| **快取恢復** | 開啟 [`清除網站快取`](https://chendermatologist.com/reset-sw)，再按「清除網站快取」。開啟頁面不會自動清除；工具保留作者草稿、登入與圖片資料庫。 |
| Hard refresh | Ctrl + Shift + R（Windows）或 Cmd + Shift + R（Mac） |
| DevTools | F12 → Application → Service Workers → Unregister。不要使用 Clear site data 清掉未保存的本機草稿與圖片。 |

### 怎麼確認 Vercel 真的部署完了

1. 去 [Vercel Dashboard](https://vercel.com/dashboard) → chendermatologist → Deployments。
2. 核對正式部署的完整 commit SHA，不能用較早的 Ready 部署代表目前版本。
3. 核對同 SHA 的完整正式 GitHub CI、Production smoke 與公開頁資源驗證，並檢查 Build Logs。

候選 CI 未通過不可正式發布；Vercel Ready 也不代表正式 CI 已成功。交付依 [REMOTE_CI_DELIVERY.md](REMOTE_CI_DELIVERY.md) 的候選、Preview、正常快轉 main 與正式驗證流程。

---

## 4. 醫學內容硬規矩（必讀）

從 root [`README.md`](README.md) 與你寫衛教文時的系統提示繼承的原則：

1. 只能根據實際 PDF 文獻、guideline、systematic review、RCT、major journal review 撰寫
2. **不得捏造文獻、guideline 建議、統計數據、副作用頻率**
3. 如果來源沒有提到，要標「**需要確認來源**」
4. 所有醫學主張要能回推到某一篇 reference
5. 台灣健保 / 商品名要單獨查證（食藥署藥品仿單、健保署藥品給付規定、各醫院 e-pharm）
6. 不寫成醫療廣告、不保證療效、不誇大
7. 不用簡體中文詞彙
8. 不直接複製版權圖（PDF 內的 Fig 1 / Fig 2 等），要自己畫 SVG 或標註「概念改編」

---

## 5. 本機檢查與交付 checklist

本機相關檢查與內容準備：

- [ ] `python _audit_jsonld.py` 顯示 `Errors: 0`
- [ ] `python _check_sitemap.py` 顯示 `[OK]`
- [ ] `python _check_meta.py` 顯示 `[OK]`
- [ ] `python _check_internal_links.py` 顯示 `[OK]`
- [ ] `python _check_static_a11y.py` 顯示 `[OK]`
- [ ] `python _check_balance.py` 顯示 `OK — all delimiters balanced`
- [ ] 文章內所有 `<` 用於不等號的地方都跳脫成 `&lt;`（驗證器會誤判）
- [ ] EN proseEn 區塊存在且不是空的
- [ ] `_gen_en_pages.py` 的 `EN_OG_OVERRIDES` 有對應條目
- [ ] 醫療文字及英文翻譯已取得醫師核可
- [ ] 完整交付差異已依專案規則獨立審查；額度 pending 依既有規則明示
- [ ] 候選完整 SHA 的遠端 CI、同庫 PR、Preview 與瀏覽器驗收成功
- [ ] 同 SHA 正常快轉 main 後，正式 CI、部署與 smoke 成功

---

## 6. 常用模板片段速查

### proseEn 並排區塊起手式

```html
<div id="proseEn" class="prose" style="display:none">
  <div class="toc"><div class="toc-title">In this article</div><ol>
    <li><a href="#en-intro">...</a></li>
  </ol></div>
  <h2 id="en-intro">...</h2>
  ...
</div>
```

### TL;DR 卡

```html
<div class="tldr"><strong>TL;DR：</strong>一句話總結。</div>
```

### 重點條列卡

```html
<div class="key-points">
  <div class="lbl">30 秒重點</div>
  <ul>
    <li>...<sup><a href="#ref1">1</a></sup></li>
  </ul>
</div>
```

### Q&A 卡

```html
<div class="qa"><h3>Q1：問題？</h3>
<p>回答<sup><a href="#ref1">1</a></sup>。</p></div>
```

### 迷思卡

```html
<div class="myth-card">
  <div class="myth">「錯誤說法」</div>
  <div class="truth">正確說法<sup><a href="#ref1">1</a></sup>。</div>
</div>
```

### 進階補充

```html
<div class="advanced">
  <div class="lbl">本段醫學深度較高，民眾可選擇略過</div>
  <h3>...</h3>
  <p>...</p>
</div>
```

### Vancouver references

```html
<h2 id="refs">參考資料</h2>
<ol class="references">
  <li id="ref1">Author A, et al. Title. <em>Journal</em>. 2026;94(5):1483-1492. doi:10.xxxx/x. PMID: 12345678. <a href="https://pubmed.ncbi.nlm.nih.gov/12345678/" target="_blank" rel="noopener noreferrer">[PubMed]</a></li>
</ol>
```

### inline SVG（不要用 img + data: URI）

```html
<figure class="fig" id="fig1">
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 400" role="img" aria-label="圖片描述">
    <title>SVG 標題</title>
    <desc>長描述</desc>
    ...
  </svg>
  <figcaption>圖一　說明<sup><a href="#ref1">1</a></sup>。</figcaption>
</figure>
```

---

## 7. 為什麼這個流程要這樣設計

| 設計 | 原因 |
|---|---|
| ZH + EN 並排 | 一個檔案兩份內容，沒有同步漂移；JS 切換語言 = 同檔切換 `display`；EN mirror = 機械式拆出來給 `/en/...` |
| `_normalize_schema.py --include-en` | EN mirror 從 ZH 複製過來時 JSON-LD `@id` 與 `mainEntityOfPage` 還指向 `/blog/X`；要重寫成 `/en/blog/X` 否則 Google 認為兩頁 schema 衝突 |
| `<` 跳脫成 `&lt;` | html5validator 把 `BMI < 25` 這類不等式當成壞的 HTML tag，CI 會 fail |
| 不用 `img + data:` 放 SVG | inline SVG 才能被 `_gen_en_pages.py` 保留、被 screen reader 讀、被 CSS 修改色彩 |
| Vancouver references with PMID/DOI | 醫學文章可信度 SEO 與 E-E-A-T 都需要；PMID/DOI 讓讀者能驗證 |

---

更新時間：2026-10-03。
維護：陳翊嘉醫師（[`expertise88864@gmail.com`](mailto:expertise88864@gmail.com)）。
