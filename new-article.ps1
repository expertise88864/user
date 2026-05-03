# ============================================================
#  DermNotes — new article scaffolder
#  Prompts for slug + title, copies template, registers in
#  sitemap.xml, sw.js, blog/blog-shared.js (catalog), feed.xml,
#  atom.xml, blog/index.html (article-list), index.html (homepage).
#  Run: powershell -ExecutionPolicy Bypass -File new-article.ps1
# ============================================================
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "=== DermNotes 新文章 scaffolder ==="
Write-Host ""

# ---- Inputs ----
$slug = Read-Host "URL slug (e.g. molluscum-myths)"
if (-not $slug -or $slug -notmatch '^[a-z0-9-]+$') {
    Write-Host "[ERR] slug 必須是 lowercase + 數字 + 連字號" -ForegroundColor Red; exit 1
}
$path = Join-Path $PSScriptRoot "blog\$slug.html"
if (Test-Path $path) {
    Write-Host "[ERR] 檔案已存在: $path" -ForegroundColor Red; exit 1
}

$title    = Read-Host "中文標題 (e.g. 傳染性軟疣 5 大迷思)"
$subtitle = Read-Host "副標 (e.g. 會自己好嗎? 要不要打疫苗?)"
$desc     = Read-Host "Meta description (50-160 字)"
$tag      = Read-Host "tag 短名 (e.g. 傳染性軟疣)"
$emoji    = Read-Host "emoji icon (e.g. 🦠)"
$catRaw   = Read-Host "category [myth/product/rx]  (default: myth)"
$cat = if ($catRaw) { $catRaw } else { 'myth' }
$today = Get-Date -Format 'yyyy-MM-dd'

$catLabel = switch ($cat) {
    'myth'    { '迷思澄清' }
    'product' { '產品介紹' }
    'rx'      { '處方用藥' }
    default   { '迷思澄清' }
}

# ---- Template ----
$template = @"
<!doctype html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
<title>$title — $subtitle | ChenDermatologist · 陳翊嘉醫師</title>
<meta name="description" content="$desc" />
<meta name="theme-color" content="#0e7c86" />
<meta name="keywords" content="$tag,皮膚科衛教,陳翊嘉醫師,中國醫藥大學附設醫院 皮膚科,ChenDermatologist" />
<meta name="author" content="陳翊嘉 醫師 · ChenDermatologist" />
<link rel="canonical" href="https://chendermatologist.com/blog/$slug" />
<link rel="author" href="https://chendermatologist.com/about" />
<link rel="publisher" href="https://chendermatologist.com/" />
<link rel="alternate" hreflang="x-default" href="https://chendermatologist.com/blog/$slug" />
<link rel="alternate" hreflang="zh-TW" href="https://chendermatologist.com/blog/$slug" />
<link rel="alternate" hreflang="en" href="https://chendermatologist.com/blog/$slug" />
<link rel="icon" type="image/svg+xml" href="/icon.svg" />
<link rel="manifest" href="/manifest.json" />
<link rel="me" href="mailto:expertise88864@gmail.com" />
<link rel="me" href="https://www.cmuh.cmu.edu.tw/Department/Team?detail=77&amp;current=0&amp;source=dep" />
<link rel="alternate" type="application/rss+xml" title="ChenDermatologist RSS" href="/blog/feed.xml" />
<link rel="alternate" type="application/atom+xml" title="ChenDermatologist Atom" href="/blog/atom.xml" />

<meta property="og:type" content="article" />
<meta property="og:title" content="$title — $subtitle | ChenDermatologist" />
<meta property="og:description" content="$desc" />
<meta property="og:image" content="https://chendermatologist.com/icon.svg" />

<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8223268344248663" crossorigin="anonymous"></script>
<meta name="google-adsense-account" content="ca-pub-8223268344248663">
<script type="text/javascript">
(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);})(window,document,"clarity","script","wkvhe0mf7y");
</script>

<!-- Google Analytics 4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XFF3L5QD10"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XFF3L5QD10', { 'anonymize_ip': true });
</script>

<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Serif+TC:wght@500;600;700&display=swap" rel="stylesheet" />
<script src="https://cdn.tailwindcss.com"></script>

<style>
  :root{ --bg:#f5fbfa; --ink:#0f172a; --ink-2:#334155; --muted:#64748b; --teal:#0e7c86; --teal-deep:#0c5159; --teal-bright:#14b8a6; --mint-soft:#d4f1ee; --border:#d4eae6; --line:#e5f3ef; }
  html,body{ background:var(--bg); color:var(--ink); }
  body{ padding-bottom:env(safe-area-inset-bottom); }
  body::before{ content:''; position:fixed; inset:0; pointer-events:none; z-index:-1; background: radial-gradient(800px 500px at 12% -8%, rgba(20,184,166,.16), transparent 60%), linear-gradient(180deg,#f5fbfa 0%, #fbffff 40%, #f5fbfa 100%); }
  .teal-text{ background:linear-gradient(180deg,#14b8a6 0%, #0c5159 100%); -webkit-background-clip:text; background-clip:text; color:transparent; }
  .lang-select{ appearance:none; -webkit-appearance:none; -moz-appearance:none; padding:6px 26px 6px 12px; font-size:12px; font-weight:600; color:var(--ink); border:1px solid var(--border); border-radius:9999px; background:#fff url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 8'><path fill='%230c5159' d='M6 8 0 0h12z'/></svg>") no-repeat right 10px center; background-size:8px 6px; cursor:pointer; line-height:1.2; }
  .ad-slot{ border:1px dashed var(--border); border-radius:14px; background:#fff; color:var(--muted); font-size:11px; letter-spacing:.18em; text-transform:uppercase; display:flex; align-items:center; justify-content:center; }
  .prose{ line-height:1.9; font-size:16px; font-family:'Noto Serif TC','Microsoft JhengHei',Georgia,serif; color:var(--ink-2); }
  .prose h2{ font-family:'Noto Serif TC',Georgia,serif; font-weight:700; font-size:24px; margin:48px 0 14px; color:var(--ink); border-left:3px solid var(--teal); padding-left:14px; scroll-margin-top:80px; }
  .prose h3{ font-weight:700; font-size:17px; margin:24px 0 8px; color:var(--ink); }
  .prose p{ margin:14px 0; } .prose ul,.prose ol{ margin:14px 0 14px 22px; }
  .prose ul{ list-style:disc; } .prose ol{ list-style:decimal; }
  .prose li{ margin:6px 0; }
  .prose strong{ color:var(--ink); font-weight:700; }
  .prose a{ color:var(--teal-deep); font-weight:600; text-decoration:underline; text-underline-offset:3px; }
  .myth-card{ background:#fff; border:1px solid var(--border); border-radius:14px; padding:18px 22px; margin:18px 0; box-shadow:0 8px 18px -10px rgba(12,81,89,.18); transition:transform .15s, box-shadow .2s; }
  .myth-card .myth{ color:#991b1b; font-weight:700; font-size:15.5px; padding-left:28px; position:relative; line-height:1.6; }
  .myth-card .myth::before{ content:'❌'; position:absolute; left:0; top:0; }
  .myth-card .truth{ color:#065f46; font-weight:700; font-size:15.5px; padding-left:28px; position:relative; line-height:1.6; margin-top:10px; padding-top:10px; border-top:1px dashed var(--line); }
  .myth-card .truth::before{ content:'✅'; position:absolute; left:0; top:10px; }
  table.dn{ width:100%; border-collapse:collapse; margin:18px 0; font-size:14px; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 1px 2px rgba(15,23,42,.04), 0 8px 18px -10px rgba(12,81,89,.18); }
  table.dn th, table.dn td{ padding:10px 12px; text-align:left; border-bottom:1px solid var(--line); vertical-align:top; }
  table.dn th{ background:#ecfeff; color:var(--teal-deep); font-weight:700; font-size:13px; }
  table.dn tr:last-child td{ border-bottom:0; }
  .toc{ background:#fff; border:1px solid var(--border); border-radius:14px; padding:14px 18px; margin:14px 0 24px; }
  .toc h4{ font-size:13px; color:var(--teal-deep); letter-spacing:.1em; margin:0 0 8px; font-weight:700; text-transform:uppercase; }
  .toc ol{ margin:0; padding:0 0 0 18px; font-size:13.5px; color:var(--ink-2); }
  .toc ol li{ margin:4px 0; }
  .toc ol li a{ color:var(--teal-deep); text-decoration:none; }
  .disclaimer{ background:#fff7ed; border:1px solid #fed7aa; border-radius:14px; padding:14px 16px; color:#9a3412; font-size:13px; line-height:1.7; margin:18px 0; }
  .references{ background:#f8fafc; border:1px solid var(--border); border-radius:12px; padding:14px 18px 14px 38px; margin:24px 0; font-size:12.5px; line-height:1.7; color:var(--ink-2); }
  .references li{ margin:5px 0; }
  .references a{ color:var(--teal-deep); word-break:break-all; }
  .card{ background:#fff; border:1px solid var(--border); border-radius:18px; box-shadow:0 1px 2px rgba(15,23,42,.04), 0 14px 30px -18px rgba(12,81,89,.18); }
  @media (max-width:640px){ .hide-sm{display:none} .prose{font-size:15.5px} .prose h2{font-size:20px} table.dn{font-size:13px} table.dn th,table.dn td{padding:8px 10px} }
</style>

<script type="application/ld+json">
{ "@context":"https://schema.org","@type":"Article","headline":"$title — $subtitle","description":"$desc","datePublished":"$today","dateModified":"$today","author":{"@type":"Person","name":"陳翊嘉 醫師","affiliation":{"@type":"Hospital","name":"中國醫藥大學附設醫院 皮膚科"}},"publisher":{"@type":"Person","name":"陳翊嘉 醫師","url":"https://chendermatologist.com/"},"image":"https://chendermatologist.com/icon.svg","mainEntityOfPage":"https://chendermatologist.com/blog/$slug" }
</script>
<script type="application/ld+json">
{ "@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"首頁","item":"https://chendermatologist.com/"},{"@type":"ListItem","position":2,"name":"衛教文章","item":"https://chendermatologist.com/blog/"},{"@type":"ListItem","position":3,"name":"$title","item":"https://chendermatologist.com/blog/$slug"}]}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"MedicalWebPage","url":"https://chendermatologist.com/blog/$slug","inLanguage":["zh-TW","en"],"name":"$title 衛教","audience":{"@type":"MedicalAudience","audienceType":"Patient"},"lastReviewed":"$today","reviewedBy":{"@type":"Person","name":"陳翊嘉 醫師","honorificSuffix":"M.D.","affiliation":{"@type":"Hospital","name":"中國醫藥大學附設醫院 皮膚科"}},"speakable":{"@type":"SpeakableSpecification","cssSelector":["h1","h2",".tldr"]},"keywords":"$tag","articleSection":"Dermatology Patient Education","isPartOf":{"@type":"WebSite","name":"ChenDermatologist","url":"https://chendermatologist.com/"}}
</script>
</head>
<body class="font-sans antialiased text-ink-900">

<header class="sticky top-0 z-40 backdrop-blur border-b" style="background:rgba(245,251,250,.92); border-color:var(--border)">
  <div class="max-w-6xl mx-auto px-5 sm:px-8">
    <div class="h-16 flex items-center justify-between gap-4">
      <a href="/" class="flex items-center gap-3 min-w-0">
        <img src="/icon.svg" alt="ChenDermatologist" class="w-9 h-9 rounded-lg flex-shrink-0" />
        <div class="min-w-0 leading-tight">
          <div class="font-display font-semibold text-[16px] sm:text-[18px] teal-text">ChenDermatologist</div>
          <div class="text-[10.5px] sm:text-[11.5px] text-ink-500 mt-0.5 truncate">陳翊嘉醫師 · 中國醫藥大學附設醫院 皮膚科</div>
        </div>
      </a>
      <div class="flex items-center gap-2 sm:gap-3 flex-shrink-0">
        <a href="https://www.cmuh.cmu.edu.tw/Department/Team?detail=77&amp;current=0&amp;source=dep" target="_blank" rel="noopener" class="hidden sm:inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-teal-600 text-white text-[12px] font-semibold hover:bg-teal-700">預約掛號 →</a>
        <a href="/blog/" class="hidden sm:inline-flex text-[12px] uppercase tracking-[.18em] text-ink-700 font-semibold">← 文章索引</a>
        <a href="/about" class="hidden sm:inline-flex text-[12px] uppercase tracking-[.18em] text-ink-700 font-semibold" data-zh="關於我" data-en="About">關於我</a>
        <select id="langToggle" class="lang-select" aria-label="Language">
          <option value="zh">中文</option>
          <option value="en">EN</option>
        </select>
      </div>
    </div>
  </div>
</header>

<main>

<section class="pt-12 sm:pt-14 pb-6">
  <div class="max-w-3xl mx-auto px-5 sm:px-8">
    <nav style="font-size:12.5px; color:var(--muted); margin-bottom:18px;">
      <a href="/" style="color:var(--teal-deep); text-decoration:none; font-weight:600;">首頁</a><span style="margin:0 6px; opacity:.5;">/</span>
      <a href="/blog/" style="color:var(--teal-deep); text-decoration:none; font-weight:600;">衛教文章</a><span style="margin:0 6px; opacity:.5;">/</span>
      <span>$title</span>
    </nav>
    <div class="text-[11px] uppercase tracking-[.24em] text-teal-700 font-semibold mb-3">衛教 · $catLabel <span class="ml-3 inline-block px-2 py-0.5 rounded-full bg-mint-100 text-teal-700 text-[10.5px] font-semibold normal-case tracking-normal">更新日期 · $today</span></div>
    <h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">
      $title<br/>
      <span class="teal-text">$subtitle</span>
    </h1>
    <p class="mt-6 text-[15.5px] text-ink-700 leading-[1.95] tldr">
      <!-- TODO: write 1-2 sentence lede summarising what this article covers -->
    </p>
    <div class="disclaimer">
      <strong>提醒：</strong>本文僅作教育參考,不可取代面對面看診。
    </div>
  </div>
</section>

<section class="max-w-3xl mx-auto px-5 sm:px-8 my-2"><div class="ad-slot h-20 sm:h-24">廣告位</div></section>

<article class="max-w-3xl mx-auto px-5 sm:px-8 mt-2 mb-16">

<div class="toc">
  <h4>本篇大綱</h4>
  <ol>
    <li><a href="#m1">迷思 1: ...</a></li>
    <li><a href="#m2">迷思 2: ...</a></li>
    <li><a href="#tx">治療階梯</a></li>
    <li><a href="#longtail">常見問題（飲食、ptt、多久會好）</a></li>
    <li><a href="#refs">參考資料</a></li>
  </ol>
</div>

<div id="proseZh" class="prose">

<h2 id="m1">迷思 1: ___</h2>
<div class="myth-card">
  <div class="myth">「___」</div>
  <div class="truth">___</div>
</div>
<p>說明文字...</p>

<h2 id="m2">迷思 2: ___</h2>
<div class="myth-card">
  <div class="myth">「___」</div>
  <div class="truth">___</div>
</div>

<h2 id="tx">治療階梯</h2>
<table class="dn">
<thead><tr><th>步驟</th><th>處置</th><th>備註</th></tr></thead>
<tbody>
<tr><td>第 1 線</td><td>___</td><td>___</td></tr>
</tbody>
</table>

<!-- ===== Long-tail keyword section: PTT / 飲食 / 多久 / 推薦 / 健保 ===== -->
<h2 id="longtail">常見問題</h2>
<h3>$tag PTT / Dcard 上常見的問題?</h3>
<p>...</p>
<h3>$tag 多久會好?</h3>
<p>...</p>
<h3>$tag 飲食 / 食物要忌口嗎?</h3>
<p>...</p>
<h3>$tag 健保有給付嗎?</h3>
<p>...</p>

<h2 id="end">結語</h2>
<p>...</p>

<blockquote style="margin:22px 0; padding:16px 20px; background:var(--mint-soft); border-left:3px solid var(--teal); border-radius:0 12px 12px 0; color:var(--ink); font-family:inherit;"><p style="margin:0"><strong>延伸閱讀:</strong>...</p></blockquote>

<!-- ===== References ===== -->
<h2 id="refs">參考資料</h2>
<ol class="references">
  <li>UpToDate. _Topic_. Accessed $today.</li>
  <li>衛福部食藥署. _藥品仿單_. <a href="https://www.fda.gov.tw/" target="_blank" rel="noopener">https://www.fda.gov.tw/</a></li>
  <li>Author A, et al. <em>Title</em>. <em>Journal</em>. Year;Vol(Issue):Pages. <a href="https://pubmed.ncbi.nlm.nih.gov/" target="_blank" rel="noopener">PubMed</a></li>
</ol>

</div>
</article>

<section class="max-w-3xl mx-auto px-5 sm:px-8 my-6"><div class="ad-slot h-20 sm:h-24">廣告位</div></section>

<section class="max-w-3xl mx-auto px-5 sm:px-8 mb-12">
  <div class="card p-6 text-center" style="background:linear-gradient(135deg,#ecfeff,#f5fbfa)">
    <div class="text-[11px] uppercase tracking-[.24em] text-teal-700 font-semibold mb-2">想當面諮詢</div>
    <div class="font-display font-bold text-[20px]">中國醫皮膚科 · 立即掛號</div>
    <a href="https://www.cmuh.cmu.edu.tw/Department/Team?detail=77&amp;current=0&amp;source=dep" target="_blank" rel="noopener" class="inline-flex items-center gap-1 mt-4 px-5 py-2.5 rounded-lg bg-teal-600 text-white text-[13px] font-semibold hover:bg-teal-700">📅 中國醫皮膚科 預約掛號 →</a>
  </div>
</section>

</main>

<footer class="border-t border-[var(--border)] bg-mint-50/60">
  <div class="max-w-6xl mx-auto px-5 sm:px-8 py-10">
    <div class="grid sm:grid-cols-3 gap-8">
      <div>
        <div class="font-display font-bold text-[18px] teal-text">ChenDermatologist</div>
        <div class="text-[12.5px] text-ink-700 mt-1">皮膚科常見衛教及學習筆記網站</div>
        <div class="text-[13px] mt-3 leading-[1.8]"><strong>陳翊嘉 醫師</strong><br/><span class="text-ink-500">中國醫藥大學附設醫院 · 皮膚科</span></div>
      </div>
      <div>
        <div class="text-[11px] uppercase tracking-[.22em] text-teal-700 font-semibold mb-2">預約 / 掛號</div>
        <a href="https://www.cmuh.cmu.edu.tw/Department/Team?detail=77&amp;current=0&amp;source=dep" target="_blank" rel="noopener" class="inline-flex items-center gap-1 px-3 py-2 rounded-lg bg-teal-600 text-white text-[12.5px] font-semibold hover:bg-teal-700">中國醫皮膚科 預約掛號 →</a>
      </div>
      <div>
        <div class="text-[11px] uppercase tracking-[.22em] text-teal-700 font-semibold mb-2">網站</div>
        <ul class="space-y-1 text-[13px]">
          <li><a class="hover:text-teal-700" href="/">首頁</a></li>
          <li><a class="hover:text-teal-700" href="/blog/">衛教文章</a></li>
          <li><a class="hover:text-teal-700" href="/about">關於我</a></li>
          <li><a class="hover:text-teal-700" href="/privacy">隱私權政策</a></li>
          <li><a class="hover:text-teal-700" href="/blog/feed.xml">RSS</a></li>
        </ul>
      </div>
    </div>
    <div class="mt-8 pt-6 border-t border-[var(--line)] text-center text-[12.5px] text-ink-500">
      <span>網站內容更正 / 學術引用詢問 / 媒體合作請寄:</span>
      <a href="mailto:expertise88864@gmail.com" style="color:#0c5159; font-weight:700; text-decoration:underline; margin-left:4px">expertise88864@gmail.com</a>
    </div>
    <div class="mt-4 text-[11.5px] text-ink-500 flex flex-wrap items-center justify-between gap-2">
      <div>本站僅作教育參考,不構成醫療建議。</div>
      <div>© <span id="yr">2026</span> ChenDermatologist · 陳翊嘉 醫師</div>
    </div>
  </div>
</footer>

<script src="/blog/blog-shared.js" defer></script>
<script>document.addEventListener('DOMContentLoaded',function(){if(window.DN)DN.initBlog({});});</script>
</body>
</html>
"@

# ---- Write the article file (UTF-8, no BOM) ----
[System.IO.File]::WriteAllText($path, $template, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "[1/4] Wrote blog\$slug.html" -ForegroundColor Green

# ---- Register in sitemap.xml ----
$sm = Join-Path $PSScriptRoot 'sitemap.xml'
$smc = Get-Content $sm -Raw -Encoding UTF8
$priority = if ($cat -eq 'rx' -or $cat -eq 'product') { '0.9' } else { '0.95' }
$smEntry = "  <url><loc>https://chendermatologist.com/blog/$slug</loc><lastmod>$today</lastmod><changefreq>monthly</changefreq><priority>$priority</priority><image:image><image:loc>https://chendermatologist.com/icon.svg</image:loc><image:title>$title</image:title></image:image></url>"
if ($smc -notmatch [regex]::Escape("/blog/$slug")) {
    $smc = $smc -replace '(?s)(  <!-- 學習筆記)', "$smEntry`n`n`$1"
    [System.IO.File]::WriteAllText($sm, $smc, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "[2/4] Registered in sitemap.xml" -ForegroundColor Green
} else {
    Write-Host "[2/4] Already in sitemap (skipped)" -ForegroundColor DarkGray
}

# ---- Register in sw.js precache ----
$sw = Join-Path $PSScriptRoot 'sw.js'
$swc = Get-Content $sw -Raw -Encoding UTF8
if ($swc -notmatch [regex]::Escape("/blog/$slug'")) {
    $swc = $swc -replace "('/blog/topical-acids-clinical',)", "'/blog/$slug',`n  `$1"
    [System.IO.File]::WriteAllText($sw, $swc, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "[3/4] Registered in sw.js precache" -ForegroundColor Green
} else {
    Write-Host "[3/4] Already in sw.js (skipped)" -ForegroundColor DarkGray
}

# ---- Register in blog/blog-shared.js ARTICLES catalog ----
$bs = Join-Path $PSScriptRoot 'blog\blog-shared.js'
$bsc = Get-Content $bs -Raw -Encoding UTF8
if ($bsc -notmatch [regex]::Escape("slug:'$slug'")) {
    $entry = "    { slug:'$slug', title:'$title', cat:'$cat', tag:'$tag', date:'$today', emoji:'$emoji', tag_en:'$tag' },"
    $bsc = $bsc -replace "(\{ slug:'acne-scar-treatment',[^\}]+\})", "`$1,`n$entry"
    # Different anchor — find the closing of the array
    $bsc = $bsc -replace "(    \{ slug:'acne-scar-treatment',[^\n]+\}\n)(  \];)", "`$1$entry`n`$2"
    [System.IO.File]::WriteAllText($bs, $bsc, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "[4/4] Registered in blog-shared.js ARTICLES" -ForegroundColor Green
} else {
    Write-Host "[4/4] Already in catalog (skipped)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "=== 完成 ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步:" -ForegroundColor Yellow
Write-Host "  1. 編輯 blog\$slug.html 補上實際內容(TOC / myth-cards / 表格 / references)"
Write-Host "  2. (可選) 加文章卡片到 index.html 與 blog\index.html"
Write-Host "  3. (可選) 加入 blog\feed.xml 與 blog\atom.xml 的 <item>"
Write-Host "  4. (可選) 加入 blog\topics.html 對應分類"
Write-Host "  5. 跑 deploy.bat 上傳"
Write-Host ""
