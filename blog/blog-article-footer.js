/* ChenDermatologist article footer bundle. Loaded on demand by blog-shared.js. */
(function () {
  var DN = (window.DN = window.DN || {});

  function ensureArticleFooterStyles() {
    if (document.getElementById('dn-article-footer-css')) return;
    var style = document.createElement('style');
    style.id = 'dn-article-footer-css';
    style.textContent = [
      '.dn-related-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}',
      '.dn-related-card:hover{border-color:rgba(122,146,133,.55)!important;transform:translateY(-2px);box-shadow:0 12px 24px -10px rgba(77,99,88,.28)!important}',
      '.dn-next-read-link:hover{border-color:var(--teal)!important;transform:translateX(3px)}',
      '@media (max-width:640px){.dn-related-grid{grid-template-columns:1fr!important}}'
    ].join('\n');
    document.head.appendChild(style);
  }

  DN.addRelatedArticles = function () {
    const article = document.querySelector('article.max-w-3xl');
    if (!article) return;
    if (document.getElementById('dn-related')) return;
    const slug = DN.currentSlug();
    if (!slug) return;
    const all = DN.ARTICLES || [];
    const cur = all.find(function (a) { return a.slug === slug; });
    if (!cur) return;

    // 2026-05-09 — TAG_GROUPS-membership scoring (replaces token-overlap).
    // Why: token-based "overlap" matched articles with shared common Chinese
    // chars like "皮膚" or "腫瘤" — recommending "標靶藥物副作用" as related to
    // "皮膚切片". The new logic uses curated TAG_GROUPS membership as the
    // primary signal, with tag string + category as secondary tiebreakers.
    function tagGroupsContaining(slug) {
      // Returns array of group keys whose article-list contains this slug
      var groups = [];
      try {
        var TG = DN.TAG_GROUPS || {};
        Object.keys(TG).forEach(function (k) {
          if ((TG[k] || []).indexOf(slug) !== -1) groups.push(k);
        });
      } catch (e) {}
      return groups;
    }
    var curGroups = new Set(tagGroupsContaining(cur.slug));
    function tokens(a) {
      // Used only as a weak fallback signal
      var t = (a.title + ' ' + (a.tag || '') + ' ' + (a.tag_en || '')).toLowerCase();
      return new Set(t.split(/[\s\/\-,()·]+/).filter(function (w) { return w.length > 1; })
        .concat((t.match(/[一-鿿]{2,}/g) || [])));
    }
    // Penalize over-common tokens that match too broadly across topics
    var COMMON_TOKENS = new Set(['皮膚', '完整', '衛教', '迷思', '治療', '藥物', '副作用', '常見']);
    var curTok = tokens(cur);
    const scored = all.filter(function (a) { return a.slug !== slug; })
      .map(function (a) {
        // PRIMARY signal: shared TAG_GROUPS membership (huge weight)
        var aGroups = tagGroupsContaining(a.slug);
        var sharedGroups = aGroups.filter(function (g) { return curGroups.has(g); });
        var groupBonus = sharedGroups.length * 20; // 20 points per shared group
        // SECONDARY: same exact tag string
        var tagBonus = (a.tag === cur.tag) ? 12 : 0;
        // TERTIARY: same cat
        var catBonus = (a.cat === cur.cat) ? 2 : 0;
        // FALLBACK (only when no shared group): weak token overlap, common tokens excluded
        var overlap = 0;
        if (sharedGroups.length === 0) {
          var aTok = tokens(a);
          aTok.forEach(function (t) {
            if (curTok.has(t) && !COMMON_TOKENS.has(t)) overlap += 1;
          });
        }
        return { a: a, s: groupBonus + tagBonus + catBonus + overlap };
      })
      // Drop articles with score 0 (no genuine relation) — better to show fewer
      // good relations than fill with random matches.
      .filter(function (x) { return x.s > 0; })
      .sort(function (x, y) {
        if (y.s !== x.s) return y.s - x.s;
        return (y.a.date || '').localeCompare(x.a.date || ''); // tiebreak: newer
      })
      .slice(0, 4)   // 2026-05-08: 4 articles (2×2 grid on desktop, 1-col on mobile) per user
      .map(function (x) { return x.a; });

    const wrap = document.createElement('section');
    wrap.id = 'dn-related';
    wrap.className = 'max-w-3xl mx-auto px-5 sm:px-8 my-10';
    ensureArticleFooterStyles();
    // Find read articles to badge "✓ 已讀" / "新"
    var readSlugs = (DN.getReadSlugs && DN.getReadSlugs()) || [];
    let html = '<div style="border-top:1px solid var(--line);padding-top:28px"><div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:14px"><div style="font-size:11px;text-transform:uppercase;letter-spacing:.22em;color:var(--teal-deep);font-weight:700" data-zh="你可能也會想看" data-en="You might also like">你可能也會想看</div><a href="/blog/" style="font-size:11.5px;color:var(--teal-deep);text-decoration:none;font-weight:600" data-zh="瀏覽全部文章 →" data-en="Browse all →">瀏覽全部文章 →</a></div><div class="dn-related-grid">';
    scored.forEach(function (a, i) {
      var hasRead = readSlugs.indexOf(a.slug) !== -1;
      var badge = hasRead
        ? '<span style="display:inline-block;padding:2px 7px;border-radius:9999px;background:#dcfce7;color:#14532d;font-size:10px;font-weight:700;margin-left:auto" data-zh="✓ 已讀" data-en="✓ Read">✓ 已讀</span>'
        : (i === 0 ? '<span style="display:inline-block;padding:2px 7px;border-radius:9999px;background:#fef3c7;color:#854d0e;font-size:10px;font-weight:700;margin-left:auto" data-zh="最相關" data-en="Top match">最相關</span>' : '');
      html += '<a class="dn-related-card" href="/blog/' + a.slug + '" style="display:flex;flex-direction:column;gap:8px;padding:16px;background:#fff;border:1px solid var(--border);border-radius:12px;text-decoration:none;color:var(--ink);transition:all .15s;box-shadow:0 1px 2px rgba(15,23,42,.04)">' +
        '<div style="display:flex;align-items:center;gap:6px"><span style="font-size:10.5px;font-weight:700;letter-spacing:.18em;color:var(--teal-deep);text-transform:uppercase">' + (a.tag_en || a.tag) + '</span>' + badge + '</div>' +
        '<span data-zh="' + (a.title || '').replace(/"/g,'&quot;') + '" data-en="' + ((a.title_en || a.title) || '').replace(/"/g,'&quot;') + '" style="font-size:14.5px;font-weight:700;line-height:1.4;font-family:Noto Serif TC,Georgia,serif;color:var(--ink);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">' + a.title + '</span>' +
        '<span style="font-size:11.5px;color:var(--muted);margin-top:auto">' + a.tag + ' · ' + a.date + '</span>' +
      '</a>';
    });
    html += '</div></div>';
    wrap.innerHTML = html;
    article.parentNode.insertBefore(wrap, article.nextSibling);

    // ItemList JSON-LD for SEO
    const ld = {
      '@context': 'https://schema.org',
      '@type': 'ItemList',
      'name': 'Related dermatology articles',
      'itemListElement': scored.map(function (a, i) {
        return {
          '@type': 'ListItem',
          'position': i + 1,
          'url': 'https://chendermatologist.com/blog/' + a.slug,
          'name': a.title
        };
      })
    };
    const ldEl = document.createElement('script');
    ldEl.type = 'application/ld+json';
    ldEl.textContent = JSON.stringify(ld);
    document.head.appendChild(ldEl);
  };

  // -----------------------------------------------------------------------
  // Web Vitals → GA4 event reporting
  // CLS, LCP, INP, FCP, TTFB — Core Web Vitals are SEO ranking signals
  // -----------------------------------------------------------------------
  // -----------------------------------------------------------------------

  // Share toolbar — LINE / Facebook / Copy link / Web Share API (mobile)
  // Inserted at end of article. LINE share is critical in Taiwan.
  // -----------------------------------------------------------------------
  DN.addShareToolbar = function () {
    const article = document.querySelector('article.max-w-3xl');
    if (!article || document.getElementById('dn-share')) return;
    const url = encodeURIComponent(location.href);
    const title = encodeURIComponent(document.title);

    const sec = document.createElement('section');
    sec.id = 'dn-share';
    sec.className = 'max-w-3xl mx-auto px-5 sm:px-8 my-6';
    sec.innerHTML =
      '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:14px 18px;background:#fff;border:1px solid var(--border);border-radius:14px;box-shadow:0 1px 2px rgba(15,23,42,.04)">' +
        '<span style="font-size:12.5px;font-weight:700;color:var(--ink-2);margin-right:6px" data-zh="覺得有幫助？ 分享給朋友：" data-en="Found this useful? Share:">覺得有幫助？ 分享給朋友：</span>' +
        '<a target="_blank" rel="noopener noreferrer" href="https://social-plugins.line.me/lineit/share?url=' + url + '" aria-label="LINE" data-share="line" style="display:inline-flex;align-items:center;gap:6px;padding:7px 13px;background:#06c755;color:#fff;border-radius:9999px;font-size:12.5px;font-weight:700;text-decoration:none">LINE</a>' +
        '<a target="_blank" rel="noopener noreferrer" href="https://www.facebook.com/sharer/sharer.php?u=' + url + '" aria-label="Facebook" data-share="facebook" style="display:inline-flex;align-items:center;gap:6px;padding:7px 13px;background:#1877f2;color:#fff;border-radius:9999px;font-size:12.5px;font-weight:700;text-decoration:none">Facebook</a>' +
        '<a target="_blank" rel="noopener noreferrer" href="https://twitter.com/intent/tweet?url=' + url + '&text=' + title + '" aria-label="Twitter" data-share="twitter" style="display:inline-flex;align-items:center;gap:6px;padding:7px 13px;background:#1f2937;color:#fff;border-radius:9999px;font-size:12.5px;font-weight:700;text-decoration:none">𝕏</a>' +
        '<button type="button" id="dn-copy" data-share="copy" style="display:inline-flex;align-items:center;gap:6px;padding:7px 13px;background:#fff;color:var(--ink);border:1px solid var(--border);border-radius:9999px;font-size:12.5px;font-weight:700;cursor:pointer" data-zh="📋 複製連結" data-en="📋 Copy link">📋 複製連結</button>' +
        (navigator.share ? '<button type="button" id="dn-native-share" data-share="native" style="display:inline-flex;align-items:center;gap:6px;padding:7px 13px;background:linear-gradient(180deg,#a4b5a8,#4d6358);color:#fff;border:none;border-radius:9999px;font-size:12.5px;font-weight:700;cursor:pointer">↗ 系統分享</button>' : '') +
      '</div>';
    article.parentNode.insertBefore(sec, article.nextSibling);

    // Track shares to GA4
    sec.querySelectorAll('[data-share]').forEach(function (el) {
      el.addEventListener('click', function () {
        if (typeof gtag === 'function') {
          try { gtag('event', 'share', { method: el.dataset.share, content_type: 'article', item_id: location.pathname }); } catch (e) {}
        }
      });
    });
    // Copy
    const copyBtn = sec.querySelector('#dn-copy');
    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        navigator.clipboard.writeText(location.href).then(function () {
          const orig = copyBtn.textContent;
          copyBtn.textContent = '✓ 已複製';
          setTimeout(function () { copyBtn.textContent = orig; }, 1800);
        }).catch(function () {});
      });
    }
    // Native share (mobile)
    const ns = sec.querySelector('#dn-native-share');
    if (ns) {
      ns.addEventListener('click', function () {
        navigator.share({ title: document.title, url: location.href }).catch(function () {});
      });
    }
  };

  // -----------------------------------------------------------------------
  // Mark "新" badge on article-list-items whose published date is within 7 days.

  DN.injectTipCard = function () {
    if (document.getElementById('dn-tip-card')) return;
    var article = document.querySelector('article.max-w-3xl');
    if (!article) return;

    var card = document.createElement('section');
    card.id = 'dn-tip-card';
    card.style.cssText = 'margin:36px auto 18px;max-width:48rem;padding:24px;background:linear-gradient(135deg,#fef3c7,#fde68a);border:1px solid #fbbf24;border-radius:16px;box-shadow:0 14px 30px -14px rgba(180,83,9,.30);text-align:center';

    // Single CTA → /support page (the centralised hub with Ko-fi + 街口 + FAQ).
    // Avoids duplicating payment options across every article and lets us
    // evolve the support page (add Patreon/LINE Pay etc.) without touching
    // 30+ articles.
    card.innerHTML =
      '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.22em;color:#78350f;font-weight:700;margin-bottom:8px" data-zh="如果這個網站對您有幫助" data-en="If this site has helped you">如果這個網站對您有幫助</div>' +
      '<h3 style="font-family:\'Noto Serif TC\',Georgia,serif;font-size:24px;font-weight:700;margin:0 0 16px;color:#78350f" data-zh="請我喝杯咖啡 ☕" data-en="Buy me a coffee ☕">請我喝杯咖啡 ☕</h3>' +
      '<div style="display:flex;justify-content:center;margin-bottom:14px">' +
        '<a href="/support" data-tip-provider="hub" style="display:inline-flex;align-items:center;gap:8px;padding:12px 26px;background:#0e7c86;color:#fff;border-radius:10px;text-decoration:none;font-weight:700;font-size:14.5px;box-shadow:0 6px 14px -6px rgba(14,124,134,.55);transition:transform .15s">' +
          '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8h1a4 4 0 0 1 0 8h-1"/><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/></svg>' +
          '<span data-zh="到贊助頁支持本站 →" data-en="Support this site →">到贊助頁支持本站 →</span>' +
        '</a>' +
      '</div>' +
      '<p style="font-size:11.5px;color:#92400e;margin:0 auto;line-height:1.7;max-width:42em" data-zh="支援 Ko-fi 國際信用卡 / PayPal 與街口支付台灣本土。本網站無業配、無贊助,所有衛教文章與量表計算器都免費。" data-en="Supports Ko-fi (international card / PayPal) and JKOPay (Taiwan). No ads, no sponsorships — all articles and tools are free.">支援 Ko-fi 國際信用卡 / PayPal 與街口支付台灣本土。本網站無業配、無贊助,所有衛教文章與量表計算器都免費。</p>';

    article.parentNode.appendChild(card);

    // Click tracking + hover animation
    var btn = card.querySelector('a[data-tip-provider]');
    if (btn) {
      btn.addEventListener('mouseenter', function () { btn.style.transform = 'translateY(-2px)'; });
      btn.addEventListener('mouseleave', function () { btn.style.transform = ''; });
      btn.addEventListener('click', function () {
        if (typeof gtag === 'function') {
          try { gtag('event', 'tip_card_click', { provider: 'support_hub', slug: DN.currentSlug && DN.currentSlug() }); } catch (_) {}
        }
      });
    }
  };

  // ─────────────────────────────────────────────────────────────────────
  // H6 — One-click PDF / Print export per article.
  // Uses native print-to-PDF via window.print() — leverages the existing
  // @media print rules already in critical CSS (which hide nav/CTAs/etc).
  // Adds a "下載 PDF" floating button next to the bookmark button.
  // ─────────────────────────────────────────────────────────────────────
  DN.injectPdfButton = function () {
    if (document.getElementById('dn-pdf-btn')) return;
    if (!document.querySelector('article.max-w-3xl')) return;
    var btn = document.createElement('button');
    btn.id = 'dn-pdf-btn';
    btn.type = 'button';
    btn.setAttribute('aria-label', '下載 PDF');
    btn.title = '下載成 PDF · Cmd/Ctrl+P 或點此';
    btn.style.cssText = 'position:fixed;right:18px;bottom:260px;width:42px;height:42px;border-radius:50%;background:#fff;color:var(--teal-deep);border:1px solid var(--border);box-shadow:0 8px 20px -8px rgba(12,81,89,.35);cursor:pointer;display:flex;align-items:center;justify-content:center;z-index:50;font-size:16px;line-height:1;transition:all .15s';
    btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><polyline points="9 15 12 18 15 15"/></svg>';
    btn.addEventListener('mouseenter', function () { btn.style.transform = 'translateY(-2px)'; btn.style.borderColor = 'var(--teal)'; });
    btn.addEventListener('mouseleave', function () { btn.style.transform = ''; btn.style.borderColor = 'var(--border)'; });
    btn.addEventListener('click', function () {
      // GA4 event
      if (typeof gtag === 'function') {
        try { gtag('event', 'pdf_download_click', { slug: DN.currentSlug && DN.currentSlug() }); } catch (e) {}
      }
      // Set a sensible filename via document.title (browsers use it for "Save as PDF")
      var origTitle = document.title;
      var slug = DN.currentSlug && DN.currentSlug();
      if (slug) document.title = 'ChenDermatologist · ' + slug + ' · ' + new Date().toISOString().slice(0, 10);
      window.print();
      // Restore after a tick (browser already snapshot the title)
      setTimeout(function () { document.title = origTitle; }, 1000);
    });
    document.body.appendChild(btn);
  };

  // ─────────────────────────────────────────────────────────────────────
  // H1 — Giscus comments (GitHub Discussions, no backend, free)
  // Setup: enable Discussions in your repo + install Giscus app + paste IDs.
  // The widget loads only on article pages, lazily on scroll-near-bottom.
  // ─────────────────────────────────────────────────────────────────────
  DN.GISCUS_REPO = 'expertise88864/user';   // ← change if your discussions repo differs
  DN.GISCUS_REPO_ID = '';                   // ← from giscus.app config wizard
  DN.GISCUS_CATEGORY_ID = '';               // ← from giscus.app config wizard
  DN.injectGiscus = function () {
    if (!DN.GISCUS_REPO || !DN.GISCUS_REPO_ID || !DN.GISCUS_CATEGORY_ID) return;
    if (document.getElementById('dn-giscus')) return;
    var article = document.querySelector('article.max-w-3xl');
    if (!article) return;
    var slug = DN.currentSlug();
    if (!slug) return;
    // Lazy mount when user scrolls within 800px of the article end
    var anchor = document.createElement('div');
    anchor.id = 'dn-giscus';
    anchor.style.cssText = 'margin:32px auto;max-width:48rem;padding:0 20px;min-height:120px';
    anchor.innerHTML = '<div data-zh="留言載入中..." data-en="Loading comments..." style="color:var(--muted);font-size:13px;text-align:center;padding:24px">留言載入中...</div>';
    article.parentNode.insertBefore(anchor, article.nextSibling);

    function load() {
      var script = document.createElement('script');
      script.src = 'https://giscus.app/client.js';
      script.async = true;
      script.crossOrigin = 'anonymous';
      script.dataset.repo = DN.GISCUS_REPO;
      script.dataset.repoId = DN.GISCUS_REPO_ID;
      script.dataset.category = 'Comments';
      script.dataset.categoryId = DN.GISCUS_CATEGORY_ID;
      script.dataset.mapping = 'pathname';
      script.dataset.strict = '0';
      script.dataset.reactionsEnabled = '1';
      script.dataset.emitMetadata = '0';
      script.dataset.inputPosition = 'top';
      script.dataset.theme = (document.documentElement.getAttribute('data-theme') === 'dark') ? 'dark_dimmed' : 'light';
      script.dataset.lang = (DN.detectLang && DN.detectLang() === 'en') ? 'en' : 'zh-TW';
      anchor.appendChild(script);
    }
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        if (entries[0].isIntersecting) { io.disconnect(); load(); }
      }, { rootMargin: '800px 0px' });
      io.observe(anchor);
    } else {
      setTimeout(load, 2000);
    }
  };

  // ─────────────────────────────────────────────────────────────────────
  // H4 — Enhanced word/character count badge (added to reading meta bar)
  // Appends a "字數 N" chip alongside the existing reading-time chip.
  // ─────────────────────────────────────────────────────────────────────
  DN.injectWordCount = function () {
    var bar = document.getElementById('dn-reading-meta');
    if (!bar || bar.querySelector('[data-dn-wordcount]')) return;
    var proseEl = document.getElementById('proseZh') || document.querySelector('article .prose') || document.querySelector('article.max-w-3xl');
    if (!proseEl) return;
    var text = (proseEl.textContent || '').replace(/\s+/g, '');
    var cjk = (text.match(/[一-鿿]/g) || []).length;
    var en = (text.match(/[A-Za-z0-9]+/g) || []).length;
    var totalLabel = cjk > en * 4
      ? cjk.toLocaleString() + ' 字'
      : (cjk + en).toLocaleString() + ' 字 / words';
    var chip = document.createElement('span');
    chip.setAttribute('data-dn-wordcount', '');
    chip.style.cssText = 'display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:9999px;background:#fef3c7;border:1px solid #fcd34d;color:#854d0e;font-weight:600';
    chip.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="14" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>' +
      '<span data-zh="' + totalLabel + '" data-en="' + (cjk + en).toLocaleString() + ' words">' + totalLabel + '</span>';
    bar.appendChild(chip);
  };

  // ─────────────────────────────────────────────────────────────────────
  // H9 — "Continue reading" recommendation (collaborative-filter-lite)
  // Picks 3 articles user hasn't read yet, biased toward same tag as current.
  // Storage: localStorage.dn-read-articles-v1 (already populated by markRead)
  // ─────────────────────────────────────────────────────────────────────
  DN.injectNextReads = function () {
    var article = document.querySelector('article.max-w-3xl');
    if (!article) return;
    if (document.getElementById('dn-next-reads')) return;
    var slug = DN.currentSlug();
    if (!slug) return;
    var allArticles = (DN.ARTICLES || []).filter(function (a) { return a.slug !== slug; });
    if (!allArticles.length) return;

    var read = (DN.getReadSlugs && DN.getReadSlugs()) || [];
    var current = (DN.ARTICLES || []).find(function (a) { return a.slug === slug; });
    var currentTag = current ? current.tag : '';

    // Score: same tag = 100, unread bonus = 50, recent date = up to 30
    var maxDate = '2026-01-01';
    allArticles.forEach(function (a) { if (a.date && a.date > maxDate) maxDate = a.date; });
    function score(a) {
      var s = 0;
      if (a.tag === currentTag) s += 100;
      if (read.indexOf(a.slug) === -1) s += 50;
      // Recency bonus
      if (a.date && maxDate) {
        var daysFromTop = Math.max(0, 30 - Math.floor((new Date(maxDate) - new Date(a.date)) / 86400000));
        s += daysFromTop;
      }
      return s;
    }
    var ranked = allArticles.map(function (a) { return [score(a), a]; })
      .sort(function (x, y) { return y[0] - x[0]; })
      .slice(0, 3)
      .map(function (p) { return p[1]; });

    var box = document.createElement('section');
    box.id = 'dn-next-reads';
    box.style.cssText = 'margin:32px auto;max-width:48rem;padding:20px 24px;background:linear-gradient(135deg,#f5fbfa 0%,#fff 100%);border:1px solid var(--border);border-radius:16px';
    ensureArticleFooterStyles();
    var html = '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.22em;color:var(--teal-deep);font-weight:700;margin-bottom:10px"><span data-zh="繼續閱讀" data-en="Continue reading">繼續閱讀</span></div>';
    html += '<ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:8px">';
    ranked.forEach(function (a, i) {
      var isUnread = read.indexOf(a.slug) === -1;
      html += '<li><a class="dn-next-read-link" href="/blog/' + a.slug + '" style="display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:10px;background:#fff;border:1px solid var(--border);text-decoration:none;color:inherit;transition:border-color .15s,transform .15s">';
      html += '<span style="font-size:11px;color:var(--teal-deep);font-weight:700;font-family:Inter,sans-serif">0' + (i + 1) + '</span>';
      html += '<span style="flex:1;font-size:14px;font-weight:600;color:var(--ink)">' + a.title + '</span>';
      if (isUnread) html += '<span style="font-size:10px;padding:2px 7px;border-radius:9999px;background:#dcfce7;color:#14532d;font-weight:700" data-zh="新" data-en="NEW">新</span>';
      html += '</a></li>';
    });
    html += '</ul>';
    box.innerHTML = html;
    article.parentNode.insertBefore(box, article.nextSibling);
  };

  // ─────────────────────────────────────────────────────────────────────
  // H2 — Lightweight A/B testing framework
  // Assigns user to a stable variant (hashed by visitor ID), reports to GA4.
  //
  // Usage:
  //   var v = DN.abVariant('hero-cta', ['A', 'B']);   // returns 'A' or 'B'
  //   if (v === 'B') { document.querySelector('.cta').textContent = '免費註閱'; }
  //   DN.abTrack('hero-cta', 'click');                // mark conversion
  // ─────────────────────────────────────────────────────────────────────
  DN.abVariant = function (testName, variants) {
    if (!variants || !variants.length) return null;
    var key = 'dn-ab-' + testName;
    var cached;
    try { cached = localStorage.getItem(key); } catch (e) {}
    if (cached && variants.indexOf(cached) !== -1) return cached;
    // Stable hash — use visitor ID if available, else random
    var visitorId;
    try {
      visitorId = localStorage.getItem('dn-visitor-id');
      if (!visitorId) {
        visitorId = (crypto && crypto.randomUUID) ? crypto.randomUUID() : (Date.now() + '-' + Math.random());
        localStorage.setItem('dn-visitor-id', visitorId);
      }
    } catch (e) { visitorId = String(Math.random()); }
    // Hash visitorId+testName → variant index
    var h = 0;
    var s = visitorId + ':' + testName;
    for (var i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
    var idx = Math.abs(h) % variants.length;
    var picked = variants[idx];
    try { localStorage.setItem(key, picked); } catch (e) {}
    if (typeof gtag === 'function') {
      try { gtag('event', 'ab_assigned', { test: testName, variant: picked }); } catch (e) {}
    }
    return picked;
  };
  DN.abTrack = function (testName, eventLabel) {
    if (typeof gtag !== 'function') return;
    var key = 'dn-ab-' + testName;
    var variant;
    try { variant = localStorage.getItem(key); } catch (e) {}
    try { gtag('event', 'ab_conversion', { test: testName, variant: variant || 'unknown', label: eventLabel || 'click' }); } catch (e) {}
  };

  // ─────────────────────────────────────────────────────────────────────
  // H3 — Email newsletter widget (MailerLite/Buttondown/Mailchimp agnostic)
  // Set DN.NEWSLETTER_PROVIDER + endpoint to wire up. Falls back to mailto.
  // ─────────────────────────────────────────────────────────────────────
  DN.NEWSLETTER_ENDPOINT = '';   // e.g. 'https://app.mailerlite.com/webforms/...'
  DN.injectNewsletterCard = function () {
    var article = document.querySelector('article.max-w-3xl');
    if (!article || document.getElementById('dn-newsletter')) return;
    var card = document.createElement('section');
    card.id = 'dn-newsletter';
    // Slightly smaller margin-top so it sits flush with whatever comes above
    card.style.cssText = 'margin:48px auto 24px;max-width:48rem;padding:24px;background:linear-gradient(135deg,#0c5159,#0e7c86);color:#fff;border-radius:16px;box-shadow:0 14px 30px -14px rgba(12,81,89,.5)';
    card.innerHTML =
      '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.22em;font-weight:700;opacity:.85;margin-bottom:6px" data-zh="訂閱衛教更新" data-en="Subscribe">訂閱衛教更新</div>' +
      '<h3 style="font-family:\'Noto Serif TC\',Georgia,serif;font-size:22px;font-weight:700;margin:0 0 6px" data-zh="新文章上架,Email 通知你" data-en="Get an email when new articles publish">新文章上架,Email 通知你</h3>' +
      '<p style="font-size:13.5px;opacity:.9;margin:0 0 12px;line-height:1.7" data-zh="不會 spam · 不會賣資料 · 隨時取消訂閱" data-en="No spam · no data sale · unsubscribe anytime">不會 spam · 不會賣資料 · 隨時取消訂閱</p>' +
      '<form id="dn-news-form" style="display:flex;gap:8px;flex-wrap:wrap">' +
        '<input type="email" name="email" required placeholder="email@example.com" style="flex:1;min-width:200px;padding:10px 14px;border:1px solid rgba(255,255,255,.4);border-radius:8px;background:rgba(255,255,255,.95);color:#0c5159;font-size:14px;font-family:inherit"/>' +
        '<button type="submit" style="padding:10px 18px;background:#fff;color:#0c5159;border:none;border-radius:8px;font-weight:700;cursor:pointer;font-size:14px" data-zh="訂閱" data-en="Subscribe">訂閱</button>' +
      '</form>' +
      '<div id="dn-news-msg" style="margin-top:8px;font-size:12px;opacity:.85"></div>';
    // Append to end of article's parent (after Giscus, related, push card, etc.)
    // so the newsletter is the LAST card before <footer>.
    var container = article.parentNode;
    container.appendChild(card);

    document.getElementById('dn-news-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var email = e.target.email.value.trim();
      var msg = document.getElementById('dn-news-msg');
      if (!email || !/.@./.test(email)) { msg.textContent = '請輸入有效 email'; return; }
      if (typeof gtag === 'function') {
        try { gtag('event', 'newsletter_subscribe', { source: 'article_card' }); } catch (_) {}
      }
      if (DN.NEWSLETTER_ENDPOINT) {
        fetch(DN.NEWSLETTER_ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: 'email=' + encodeURIComponent(email),
          mode: 'no-cors',
        }).then(function () { msg.textContent = '✓ 訂閱成功!請至信箱確認。'; e.target.reset(); })
          .catch(function () { msg.textContent = '訂閱失敗,請稍後再試或寫信至 expertise88864@gmail.com'; });
      } else {
        // Fallback: open mailto with prefilled body
        location.href = 'mailto:expertise88864@gmail.com?subject=' + encodeURIComponent('訂閱衛教更新') + '&body=' + encodeURIComponent('我想訂閱新文章通知:' + email);
        msg.textContent = '✓ 已開啟郵件 — 請寄出此信完成訂閱。';
      }
    });
  };

  //   2. Permission is still "default" (not yet decided)
  //   3. User dismissed → remember in localStorage so we don't pester
  // Legacy push-subscribe card removed; article footers now avoid notification prompts.

  DN.addFeedbackLink = function () {
    var article = document.querySelector('article.max-w-3xl');
    if (!article || document.getElementById('dn-feedback')) return;
    var slug = DN.currentSlug();
    var pageTitle = document.title.split('|')[0].trim();
    var subject = encodeURIComponent('[網站回饋] ' + pageTitle);
    var body = encodeURIComponent(
      '醫師您好，\n\n' +
      '我想針對下列文章提供回饋：\n' +
      '文章： ' + pageTitle + '\n' +
      '網址： ' + location.href + '\n\n' +
      '回饋內容（請填寫）:\n' +
      '□ 內容更正建議\n' +
      '□ 引用爭議\n' +
      '□ 過時資訊提醒\n' +
      '□ 其他：_____\n\n' +
      '說明：\n\n\n' +
      '謝謝！'
    );
    var box = document.createElement('section');
    box.id = 'dn-feedback';
    box.className = 'max-w-3xl mx-auto px-5 sm:px-8 my-6';
    box.innerHTML =
      '<div style="background:#fafaf7;border:1px dashed #dcd5c8;border-radius:12px;padding:14px 18px;font-size:13px;color:#5e574e;line-height:1.75;display:flex;align-items:center;gap:14px;flex-wrap:wrap">' +
      '<div style="flex:1;min-width:220px">' +
      '<strong data-zh="發現錯誤、過時資訊、引用爭議？" data-en="Spot an error or outdated info?">發現錯誤、過時資訊、引用爭議？</strong><br/>' +
      '<span data-zh="本文歡迎讀者回饋。我會親自閱讀每封信並依據文獻校正。" data-en="Reader feedback welcome. Each email is read personally and corrections are made per current literature.">本文歡迎讀者回饋。我會親自閱讀每封信並依據文獻校正。</span>' +
      '</div>' +
      '<a href="mailto:expertise88864@gmail.com?subject=' + subject + '&body=' + body + '" ' +
      'style="flex-shrink:0;padding:8px 16px;border-radius:9999px;background:#0e7c86;color:#fff;text-decoration:none;font-size:13px;font-weight:700;white-space:nowrap" ' +
      'data-feedback-link data-zh="提交內容回饋 →" data-en="Send feedback →">提交內容回饋 →</a>' +
      '</div>';
    article.parentNode.insertBefore(box, article.nextSibling);
    // GA4 tracking
    var fbLink = box.querySelector('[data-feedback-link]');
    if (fbLink && typeof gtag === 'function') {
      fbLink.addEventListener('click', function () {
        try { gtag('event', 'content_feedback_click', { page_path: location.pathname }); } catch (e) {}
      });
    }
  };

  // -----------------------------------------------------------------------
  // 支持作者 — top-right header pill + footer card (auto-injects)
  // 收款管道:街口支付(JKO Pay)Transfer link
  //   街口代碼 396 / 街口帳號 901070305 / 09****615
  // 街口支援所有銀行 + 電支機構,免手續費、即時入帳。
  // -----------------------------------------------------------------------
  // Centralised support hub — every "贊助本站" / "請我喝杯咖啡" CTA on the
  // site routes through /support so users see the disclaimer and pick their
  // preferred provider (Ko-fi / 街口) in one place. Direct payment URLs are

  DN.addAuthorBio = function () {
    const article = document.querySelector('article.max-w-3xl');
    if (!article || document.getElementById('dn-author-bio')) return;
    const box = document.createElement('section');
    box.id = 'dn-author-bio';
    box.className = 'max-w-3xl mx-auto px-5 sm:px-8 my-6';
    box.innerHTML =
      '<div style="background:linear-gradient(135deg,#ecfeff 0%, #f5fbfa 100%);border:1px solid #a5f3fc;border-radius:18px;padding:22px 24px;display:flex;gap:18px;align-items:flex-start;flex-wrap:wrap;box-shadow:0 1px 2px rgba(15,23,42,.04), 0 14px 30px -18px rgba(77,99,88,.18)">' +
        '<div style="flex-shrink:0;width:64px;height:64px;border-radius:50%;overflow:hidden;background:linear-gradient(135deg,#cffafe,#a5f3fc);box-shadow:0 4px 12px -4px rgba(12,81,89,.25), 0 0 0 3px rgba(20,184,166,.15)">' +
          '<picture>' +
            '<source type="image/webp" srcset="/blog/SUNN1327-400.webp" />' +
            '<img src="/blog/SUNN1327-400.jpg" alt="陳翊嘉醫師" width="64" height="64" loading="lazy" decoding="async" style="width:100%;height:100%;object-fit:cover;object-position:center 18%" />' +
          '</picture>' +
        '</div>' +
        '<div style="flex:1;min-width:240px">' +
          '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.18em;color:#4d6358;font-weight:700;margin-bottom:4px" data-zh="關於作者" data-en="About the author">關於作者</div>' +
          '<div style="font-family:\'Noto Serif TC\',Georgia,serif;font-size:18px;font-weight:700;color:#0f172a;margin-bottom:6px">' +
            '<span data-zh="陳翊嘉 醫師" data-en="Dr. Chen Yi-Chia, M.D.">陳翊嘉 醫師</span>' +
          '</div>' +
          '<div style="font-size:13px;color:#334155;line-height:1.85" data-zh="<strong>現職</strong>：皮膚科 住院醫師<br/>' +
            '<strong>學歷</strong>：高雄醫學大學醫學系 醫學士(M.D.)<br/>' +
            '<strong>訓練</strong>：高雄醫學大學附設中和紀念醫院 不分科住院醫師(PGY)" data-en="<strong>Current</strong>: Dermatology Resident<br/><strong>Education</strong>: M.D., Kaohsiung Medical University, College of Medicine<br/><strong>Training</strong>: Kaohsiung Medical University Hospital, Post-Graduate Year (rotating)"><strong>現職</strong>：皮膚科 住院醫師<br/><strong>學歷</strong>：高雄醫學大學醫學系 醫學士(M.D.)<br/><strong>訓練</strong>：高雄醫學大學附設中和紀念醫院 不分科住院醫師(PGY)</div>' +
          '<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">' +
            '<a href="/about" style="padding:5px 12px;border-radius:9999px;font-size:12px;font-weight:600;background:#0e7c86;color:#fff;text-decoration:none" data-zh="關於我" data-en="About">關於我 →</a>' +
            '<a href="/tools" style="padding:5px 12px;border-radius:9999px;font-size:12px;font-weight:600;background:#fff;color:#4d6358;border:1px solid #a5f3fc;text-decoration:none" data-zh="量表計算器" data-en="Calculators">量表計算器 →</a>' +
          '</div>' +
        '</div>' +
      '</div>';
    article.parentNode.insertBefore(box, article.nextSibling);
  };

  DN.addLegalDisclaimer = function () {
    const article = document.querySelector('article.max-w-3xl');
    if (!article || document.getElementById('dn-legal-disclaimer')) return;
    const box = document.createElement('section');
    box.id = 'dn-legal-disclaimer';
    box.className = 'max-w-3xl mx-auto px-5 sm:px-8 my-6';
    box.innerHTML =
      '<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:14px;padding:14px 18px;font-size:12.5px;line-height:1.85;color:#9a3412">' +
        '<div style="font-weight:700;color:#7c2d12;margin-bottom:6px;letter-spacing:.04em" data-zh="重要聲明" data-en="Important Notice">重要聲明</div>' +
        '<div data-zh="本文為皮膚科住院醫師的<strong>衛教與學習筆記</strong>，內容依據國際醫學文獻與臨床指引整理，僅作為<strong>一般教育用途</strong>。' +
        '不構成<strong>個別醫療建議、診斷或治療處方</strong>。' +
        '個別病情之評估、藥物選擇、雷射治療、手術等，請務必<strong>面對面看診</strong>由主治醫師依完整病史與檢查決定。' +
        '本網站<strong>不涉及任何藥品、醫療器材、療程或診所之推薦或業配</strong>；若提及商品為公開市售品，僅作教學說明。' +
        '依《醫療法》§85-86 及《醫師法》§17，個別治療效果因人而異，本文不保證任何結果。' +
        '若有不適，請就近至皮膚科專科醫師門診評估。" data-en="This article is a <strong>patient-education and study note</strong> by a dermatology resident, summarizing international medical literature and guidelines for general education only. It is <strong>not individual medical advice, diagnosis, or prescription</strong>. For personal evaluation, medication choice, laser, or surgical procedures, please consult a board-certified dermatologist in person. This site does <strong>not endorse any drug, device, procedure, or clinic</strong>. Per Taiwan Medical Care Act §§85–86 and Physicians Act §17, individual outcomes vary; no result is guaranteed.">本文為皮膚科住院醫師的<strong>衛教與學習筆記</strong>，內容依據國際醫學文獻與臨床指引整理，僅作為<strong>一般教育用途</strong>。不構成<strong>個別醫療建議、診斷或治療處方</strong>。個別病情之評估、藥物選擇、雷射治療、手術等，請務必<strong>面對面看診</strong>由主治醫師依完整病史與檢查決定。本網站<strong>不涉及任何藥品、醫療器材、療程或診所之推薦或業配</strong>；若提及商品為公開市售品，僅作教學說明。依《醫療法》§85-86 及《醫師法》§17，個別治療效果因人而異，本文不保證任何結果。若有不適，請就近至皮膚科專科醫師門診評估。</div>' +
      '</div>';
    article.parentNode.insertBefore(box, article.nextSibling);
  };

  // -----------------------------------------------------------------------
  // GA4 conversion event tracking — booking, email, outbound clicks
  // -----------------------------------------------------------------------

})();
