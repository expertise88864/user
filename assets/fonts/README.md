# Self-hosted fonts (P2-12 — partially complete)

## 目前狀況（2026-05-17）

`assets/fonts.css` 已寫好 7 個 `@font-face` rule（3 Inter + 2 Noto Sans TC + 2 Noto Serif TC）但**只下載了 Inter**：

```
Inter-Bold.woff2       (114 KB)
Inter-Regular.woff2    (111 KB)
Inter-SemiBold.woff2   (114 KB)
```

`fonts.css` 仍未被任何 HTML 引用 — 站台繼續走 `fonts.googleapis.com` CDN。

## 為何沒切換

切換的話需要先下載並 subset 5 個 TC woff2 才不會 404：

```
NotoSansTC-Regular.woff2     # 需從 Google Fonts API 抓
NotoSansTC-Medium.woff2
NotoSerifTC-SemiBold.woff2
NotoSerifTC-Bold.woff2
NotoSansTC-Bold.woff2        # 如果 H1 / H2 用粗體
```

TC 字型未 subset 原始檔每個 ~10-15 MB，subset 後可以到 ~200 KB 上下（zh-TW + 常用標點 + 半形 ASCII）。

## 切換步驟（之後再做）

1. 用 `fonttools` 或 google-webfonts-helper 從 Google 的 css2 API 抓 subset 過的 TC woff2（unicode-range U+4E00–9FFF + U+3000–303F + U+FF00–FFEF）
2. 放到 `assets/fonts/`
3. 在所有 HTML 的 `<head>` 把：
   ```html
   <link href="https://fonts.googleapis.com/css2?family=Inter..." rel="stylesheet">
   ```
   換成：
   ```html
   <link rel="stylesheet" href="/assets/fonts.css">
   ```
   （或加進 tw-mini.css `@import`）
4. 砍 `<link rel="preconnect" href="https://fonts.googleapis.com">` 和 `https://fonts.gstatic.com` — 不再需要
5. 砍 vercel.json / 任何 CSP allowlist 內的 fonts.googleapis.com / fonts.gstatic.com

## 預期收益

- LCP 冷網路約 -200 ms（少 1 DNS + 1 TLS + 1 RTT 抓 CSS）
- 不依賴 Google CDN（GDPR / 中國訪客體驗友善）
- 完全自主控制字型版本（避免 Google 換版面跑掉）

## 為何先暫緩

P0/P1 影響更大；TC 字型 self-host 是 medium-impact + medium-effort，可以單獨開一個 PR 處理。
