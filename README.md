# DermNotes · 皮膚科筆記與衛教

A Taiwanese dermatology R2 resident's bilingual study-notes & patient-education site.
Static HTML + Tailwind CDN, no build step.

> Domain: **chendermatologist.vercel.app**
> GitHub repo: (set below)
> Auto-deploy: Vercel on every `git push`

---

## 1. 一次性環境準備（只做一次）

### 1-1 安裝 Git
https://git-scm.com/download/win → 下載 64-bit Standalone Installer → 全部 Next 預設即可。

### 1-2 註冊 GitHub 帳號
https://github.com/signup
- Username 建議：`chendermatologist`
- Email：用真實 email，後面 GitHub 會寄驗證信。

### 1-3 在 GitHub 建立 repo
1. https://github.com/new
2. **Repository name**：`dermnotes`（或 `chendermatologist.vercel.app`）
3. **Public**（公開，比較容易讓搜尋引擎抓到）
4. **不要勾選任何 README / .gitignore / license**（保持空白 repo）
5. 按 **Create repository**
6. 在新頁面複製 **HTTPS** 那條 URL，例如：
   `https://github.com/chendermatologist/dermnotes.git`

### 1-4 註冊網域 chendermatologist.vercel.app
推薦三家：

| 註冊商 | 年費 (.com) | 備註 |
|---|---|---|
| **Cloudflare Registrar** | ~ NT$ 320 | 最便宜、無加價、自動含 WHOIS 隱私 — 強烈推薦 |
| Namecheap | ~ NT$ 380 | 介面友善、英文 |
| GoDaddy | ~ NT$ 450 | 廣告多但中文介面完整 |

> Cloudflare 必須先有帳號（免費），先在 https://cloudflare.com 註冊，再去 Domain Registration 購買。

### 1-5 註冊 Vercel（用 GitHub 登入）
https://vercel.com/signup → 選 **Continue with GitHub** → 授權 → 完成。
你會直接看到剛才建立的 GitHub repo 列表。

---

## 2. 第一次上架（5 分鐘）

### 2-1 上傳檔案到 GitHub
**雙擊 `deploy.bat`**（在 DermNotes 資料夾裡）。腳本會：

1. 檢查 Git 安裝
2. 第一次會問你 GitHub 帳號名 + email（自動 `git config --global` 一次）
3. 第一次會問你 **GitHub repo URL**（貼上 1-3 複製的 URL）
4. 自動 `git init` → `git add` → 問你 commit message → `git push`

成功後會看到：
```
Pushed to GitHub.
If Vercel is connected, it will auto-deploy in ~30 seconds.
```

### 2-2 把 GitHub repo 連到 Vercel
1. 登入 https://vercel.com/dashboard
2. 點 **Add New → Project**
3. 從清單找到 `dermnotes` repo → 點 **Import**
4. **Framework Preset**：選 **Other**（純 HTML 不需要 build）
5. **Build & Output Settings**：保持空白 / 預設
6. **Environment Variables**：不需要
7. 按 **Deploy**

約 30 秒後 Vercel 會給你一個臨時網址（例如 `dermnotes-abc123.vercel.app`）— 此時網站已經活了，但還沒接你的網域。

---

## 3. 把 chendermatologist.vercel.app 接到 Vercel

### 3-1 在 Vercel 加網域
1. 進入剛才的 project → 上方 **Settings** → 左欄 **Domains**
2. 輸入 `chendermatologist.vercel.app` → **Add**
3. 再輸入 `www.chendermatologist.vercel.app` → **Add** → 設定 redirect 到根網域
4. Vercel 會給你 **DNS records 要怎麼填** 的指示（記下來）

通常顯示：
- **A record** for `@` → `76.76.21.21`
- **CNAME** for `www` → `cname.vercel-dns.com`

### 3-2 在註冊商設定 DNS
**如果是 Cloudflare：**
1. 登入 → 點 chendermatologist.vercel.app → **DNS** → **Records**
2. **Add record**：
   - Type `A`, Name `@`, IPv4 `76.76.21.21`, Proxy status **DNS only**（灰色雲）
   - Type `CNAME`, Name `www`, Target `cname.vercel-dns.com`, Proxy status **DNS only**
3. **重要**：Proxy 一定要灰色（DNS only），橘色雲會跟 Vercel 衝突。

**如果是 Namecheap / GoDaddy：**
1. Domain Dashboard → 找 DNS / Manage
2. 加上同樣兩筆 A + CNAME
3. 砍掉註冊商預設的轉址 / parking page

### 3-3 等 DNS 生效
通常 5–30 分鐘。可在 https://dnschecker.org 查 `chendermatologist.vercel.app` 看是否已指向 `76.76.21.21`。

DNS 生效後 Vercel 自動幫你**簽發免費 SSL 憑證（Let's Encrypt）**，網站從此跑在 `https://chendermatologist.vercel.app`。

---

## 4. 提交給搜尋引擎（讓流量開始進來）

### 4-1 Google Search Console
1. https://search.google.com/search-console → **Add property**
2. 選 **URL prefix** → 輸入 `https://chendermatologist.vercel.app`
3. 驗證方法選 **HTML tag**，複製 `content="..."` 那串
4. 打開 `index.html`，找到這行（接近 head 末尾）：
   ```html
   <!-- <meta name="google-site-verification" content="" /> -->
   ```
   取消註解、把 `content` 填進去：
   ```html
   <meta name="google-site-verification" content="你的驗證字串" />
   ```
5. 雙擊 `deploy.bat` → commit message 寫 `add GSC verification`
6. 等 1 分鐘 Vercel 重新部署 → 回 GSC 點 **Verify**
7. 驗證通過後，左欄 **Sitemaps** → 輸入 `sitemap.xml` → 提交

### 4-2 Bing Webmaster
1. https://www.bing.com/webmasters → 用 Microsoft / Google 帳號登入
2. **Import from Google Search Console**（最快）或自己加
3. 同樣提交 sitemap

### 4-3 加上 Microsoft Clarity（免費 heatmap，選用）
1. https://clarity.microsoft.com → 用 Microsoft / Google 帳號 → **Create new project**
2. 取得 tag id（10 位字串）
3. 在 `index.html` 找到 Clarity 區塊：
   ```html
   <!--
   <script type="text/javascript">
   ...XXXXXXXXXX...
   </script>
   -->
   ```
   取消註解、把 `XXXXXXXXXX` 換成你的 tag id
4. `deploy.bat` 推送

---

## 5. 申請 Google AdSense（**有流量再做**）

AdSense 對「全新且內容少」的站很挑剔。建議 **至少累積以下條件後才申請**：
- 文章 ≥ 15 篇
- 有原創、有實質內容
- 上線 ≥ 2 週
- 每天有自然搜尋流量（例如 Search Console 看到至少幾十次 impression）
- 有 About / Privacy Policy / Disclaimer 頁面（本站首頁已包含 disclaimer，但建議另開 `/privacy.html`）

申請流程：
1. https://www.google.com/adsense → **Get started** → 填網址 `https://chendermatologist.vercel.app`
2. AdSense 會給你一段程式碼（含 `ca-pub-XXXXXXXXXXXXXXXX`）
3. **打開全部 HTML**（首頁 + 所有文章），找到這段被註解的區塊：
   ```html
   <!--
   <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXX" crossorigin="anonymous"></script>
   <meta name="google-adsense-account" content="ca-pub-XXXXXXXXXXXXXXXX">
   -->
   ```
   取消註解、把 `ca-pub-XXXXXXXXXXXXXXXX` 換成你的真正 publisher ID（兩處）
4. 打開 `ads.txt`，把 `pub-XXXXXXXXXXXXXXXX` 換成你的 publisher ID
5. `deploy.bat` 推送
6. 回 AdSense 點 **Verify** → 等 1–4 週審核

審核通過後，`.ad-slot` 那些灰底虛線框可以替換成實際的 `<ins class="adsbygoogle">` tag（每個版位 AdSense 會給你 slot id）。

---

## 6. 之後新增文章 / 修改的工作流

每次更新內容（例如新增第三篇衛教文章）：

1. 在 `blog/` 加 .html 檔
2. **同步更新五個地方**：
   - `sitemap.xml`：加新 url
   - `sw.js`：加進 `PRECACHE` 陣列
   - `blog/feed.xml`：加新 `<item>`
   - `blog/index.html`：加新卡片
   - `blog/blog-shared.js`：行動版抽屜選單加新連結
3. 雙擊 `deploy.bat`，輸入 commit message → 自動推送
4. 30 秒後 Vercel 上線 → 文章已可在 `https://chendermatologist.vercel.app/blog/新檔名` 看到

---

## 7. 備援部署：GitHub Pages（不用 Vercel）

如果不想用 Vercel：
1. GitHub repo → **Settings** → **Pages**
2. Source 選 `Deploy from a branch` → Branch `main` / `(root)` → Save
3. 加 `CNAME` 檔內容寫 `chendermatologist.vercel.app`
4. 在 DNS 加 4 個 A record 指向 GitHub IP（185.199.108.153 / .109.153 / .110.153 / .111.153）+ CNAME `www → username.github.io`

⚠️ 用 GitHub Pages 會失去 `vercel.json` 的 `cleanUrls`（網址會變成 `/blog/xxx.html` 而非 `/blog/xxx`），結構化資料 / canonical 都需要改回 `.html`。**強烈建議用 Vercel**，免費額度對個人站綽綽有餘。

---

## 8. 檔案結構

```
DermNotes/
├── index.html                    首頁
├── icon.svg                      網站 icon
├── manifest.json                 PWA manifest
├── robots.txt                    搜尋引擎指示
├── sitemap.xml                   sitemap
├── ads.txt                       AdSense 占位（核准後填 pub ID）
├── vercel.json                   Vercel 部署設定（cleanUrls + headers）
├── package.json                  Node engine 標記
├── sw.js                         Service worker（PWA 離線）
├── deploy.bat                    一鍵上傳 GitHub
├── .gitignore
├── README.md                     本檔
└── blog/
    ├── index.html                文章索引（衛教 vs 學習筆記分頁）
    ├── blog-shared.js            10 語言 i18n runtime
    ├── feed.xml                  RSS
    ├── isotretinoin-patient.html      衛教 #1：口服 A 酸（民眾版）
    ├── isotretinoin-clinical.html     學習筆記 #1：Isotretinoin 學理
    ├── topical-acids-patient.html     衛教 #2：外用酸類（民眾版）
    └── topical-acids-clinical.html    學習筆記 #2：外用 retinoids/acids 學理
```

---

## 9. 常見問題

**Q：deploy.bat 跳「git is not installed」**
A：去 https://git-scm.com/download/win 安裝後**重開命令提示字元 / 重啟電腦**再試。

**Q：第一次 push 出現 "Authentication failed"**
A：GitHub 已不支援密碼登入。需要 Personal Access Token：
1. https://github.com/settings/tokens → **Generate new token (classic)**
2. 勾 `repo` 全部權限 → 設過期時間 90 天 → 產生
3. **複製 token**（只會顯示一次）
4. push 時帳號填 GitHub username，密碼貼 token

**Q：DNS 設定完還是看不到網站**
A：(1) 確認 Cloudflare proxy 是「DNS only」灰色雲，不是橘色雲；(2) https://dnschecker.org 看 A record 是否全球已生效；(3) 等到 Vercel Domains 頁面那個網域旁邊顯示綠色勾才算成功。

**Q：可以同時用兩個網域嗎？例如 chendermatologist.vercel.app 和 chendermatologist.tw**
A：可以。在 Vercel Domains 兩個都加，DNS 都指過來。Vercel 會自動 301 redirect 到主網域（你選 `chendermatologist.vercel.app` 為 primary）。

**Q：要把 vercel.app 那個臨時網址藏起來怎麼做？**
A：Vercel project Settings → Domains → 把 `xxx.vercel.app` 設為 redirect 到正式網域（或直接 disable，不建議刪）。

---

© DermNotes — 本站僅作教育參考，不構成醫療建議。
