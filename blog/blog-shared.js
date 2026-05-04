/* ============================================================
 * ChenDermatologist - shared runtime (zh / en only)
 *   - simple 2-button language toggle (the existing #langToggle in HTML)
 *   - language detection (cookie > localStorage > navigator > zh)
 *   - reading progress bar
 *   - scroll-to-top button
 *   - mobile hamburger drawer
 *   - footer year + service worker registration
 *
 * Usage on every page:
 *   <script src="/blog/blog-shared.js" defer></script>
 *   <script>document.addEventListener('DOMContentLoaded',()=>DN.initBlog({}));</script>
 * ============================================================ */
(function () {
  const DN = (window.DN = window.DN || {});

  DN.LANGS = [
    { code: 'zh', label: '中文',    htmlLang: 'zh-TW' },
    { code: 'en', label: 'English', htmlLang: 'en'    }
  ];
  DN.LANG_KEY = { 'zh': 'zh', 'en': 'en' };

  DN.cookieGet = function (name) {
    const found = document.cookie.split('; ').find(c => c.startsWith(name + '='));
    return found ? decodeURIComponent(found.split('=').slice(1).join('=')) : null;
  };
  DN.cookieSet = function (name, val, days) {
    const exp = new Date(Date.now() + (days || 365) * 86400e3).toUTCString();
    document.cookie = name + '=' + encodeURIComponent(val) + '; expires=' + exp + '; path=/; SameSite=Lax';
  };

  DN.detectLang = function () {
    const fromCookie = DN.cookieGet('dn_lang');
    if (fromCookie && DN.LANG_KEY[fromCookie]) return fromCookie;
    const stored = localStorage.getItem('dn_lang');
    if (stored && DN.LANG_KEY[stored]) return stored;
    const nav = (navigator.language || 'zh').toLowerCase();
    if (nav.startsWith('zh')) return 'zh';
    if (nav.startsWith('en')) return 'en';
    return 'zh';
  };

  DN.setLang = function (code) {
    if (!DN.LANG_KEY[code]) return;
    try { localStorage.setItem('dn_lang', code); } catch (e) { /* ignore */ }
    DN.cookieSet('dn_lang', code);
  };

  DN.translate = function (el, lang) {
    const order = lang === 'en' ? ['en', 'zh'] : ['zh', 'en'];
    for (const k of order) if (el.dataset[k] != null) return el.dataset[k];
    return null;
  };

  DN.applyTextOnly = function (lang) {
    const meta = DN.LANGS.find(function (l) { return l.code === lang; }) || DN.LANGS[0];
    document.documentElement.lang = meta.htmlLang;
    document.querySelectorAll('[data-zh],[data-en]').forEach(function (el) {
      const txt = DN.translate(el, lang);
      if (txt == null) return;
      if (/[<&]/.test(txt) && /<\/?[a-z]/i.test(txt)) el.innerHTML = txt;
      else el.textContent = txt;
    });
  };

  DN.bindLangToggle = function (onChange) {
    const toggle = document.getElementById('langToggle');
    if (!toggle) return;
    // Dropdown form: <select id="langToggle">
    if (toggle.tagName === 'SELECT') {
      toggle.value = DN.detectLang();
      toggle.addEventListener('change', function () {
        const lang = toggle.value;
        if (!DN.LANG_KEY[lang]) return;
        DN.setLang(lang);
        if (typeof onChange === 'function') onChange(lang);
      });
      return;
    }
    // Legacy 2-button form
    const buttons = toggle.querySelectorAll('button[data-lang]');
    function syncActive(curLang) {
      buttons.forEach(function (b) { b.classList.toggle('active', b.dataset.lang === curLang); });
    }
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        const lang = btn.dataset.lang;
        if (!DN.LANG_KEY[lang]) return;
        DN.setLang(lang);
        syncActive(lang);
        if (typeof onChange === 'function') onChange(lang);
      });
    });
    syncActive(DN.detectLang());
  };

  DN.addReadingProgress = function () {
    if (document.getElementById('dn-progress')) return;
    const bar = document.createElement('div');
    bar.id = 'dn-progress';
    bar.style.cssText = 'position:fixed;top:0;left:0;height:3px;background:linear-gradient(90deg,#14b8a6,#0c5159);z-index:60;width:0;transition:width .12s linear;pointer-events:none';
    document.body.appendChild(bar);
    function update() {
      const h = document.documentElement;
      const max = h.scrollHeight - h.clientHeight;
      bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%';
    }
    document.addEventListener('scroll', update, { passive: true });
    update();
  };

  DN.addScrollToTop = function () {
    if (document.getElementById('dn-totop')) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'dn-totop';
    btn.setAttribute('aria-label', 'Scroll to top');
    btn.innerHTML = '↑';
    btn.style.cssText = 'position:fixed;right:18px;bottom:24px;width:42px;height:42px;border-radius:50%;background:linear-gradient(180deg,#a4b5a8,#4d6358);color:#fff;border:1px solid rgba(12,81,89,.5);box-shadow:0 8px 20px -8px rgba(12,81,89,.55);cursor:pointer;display:none;align-items:center;justify-content:center;z-index:50;font-size:18px;line-height:1';
    btn.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
    document.body.appendChild(btn);
    document.addEventListener('scroll', function () {
      btn.style.display = window.scrollY > 800 ? 'flex' : 'none';
    }, { passive: true });
  };

  // -----------------------------------------------------------------------
  // Prefetch popular articles on idle (improves next-page LCP)
  // Only same-origin links visible in viewport that haven't been visited.
  // -----------------------------------------------------------------------
  DN.prefetchOnIdle = function () {
    if (!('IntersectionObserver' in window)) return;
    const idle = window.requestIdleCallback || function (cb) { return setTimeout(cb, 1500); };
    idle(function () {
      const seen = new Set();
      const io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (!e.isIntersecting) return;
          const a = e.target;
          const href = a.getAttribute('href');
          if (!href || seen.has(href)) return;
          seen.add(href);
          // Same-origin, non-anchor, non-mailto
          if (href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
          if (/^https?:\/\//.test(href) && !href.startsWith(location.origin)) return;
          const link = document.createElement('link');
          link.rel = 'prefetch';
          link.href = href;
          link.as = 'document';
          document.head.appendChild(link);
          io.unobserve(a);
        });
      }, { rootMargin: '200px' });
      document.querySelectorAll('a[href^="/"], a[href^="' + location.origin + '"]').forEach(function (a) {
        io.observe(a);
      });
    });
  };

  // -----------------------------------------------------------------------
  // Reveal-on-scroll: add .reveal class to opt-in elements, animate in
  // -----------------------------------------------------------------------
  DN.bindRevealOnScroll = function () {
    if (!('IntersectionObserver' in window)) return;
    const targets = document.querySelectorAll('.reveal, .article-list-item, .myth-card, .scar-card, .home-faq details');
    if (!targets.length) return;
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('visible');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });
    targets.forEach(function (el, i) {
      // Only auto-add reveal animation if not already styled, and skip on tiny screens
      el.style.opacity = el.style.opacity || '0';
      el.style.transform = el.style.transform || 'translateY(10px)';
      el.style.transition = 'opacity .35s cubic-bezier(.2,.7,.2,1) ' + Math.min(i * 25, 200) + 'ms, transform .35s cubic-bezier(.2,.7,.2,1) ' + Math.min(i * 25, 200) + 'ms';
      io.observe(el);
    });
    // Helper: when class .visible applied, reset transform/opacity
    const styleEl = document.createElement('style');
    styleEl.textContent = '.reveal.visible, .article-list-item.visible, .myth-card.visible, .scar-card.visible, .home-faq details.visible { opacity:1 !important; transform:translateY(0) !important; }';
    document.head.appendChild(styleEl);
  };

  // -----------------------------------------------------------------------
  // View Transitions API page transitions (Chrome 111+, Edge, Safari 18+)
  // Falls back to no-op on unsupported browsers
  // -----------------------------------------------------------------------
  DN.bindViewTransitions = function () {
    if (!document.startViewTransition) return;
    document.addEventListener('click', function (e) {
      const a = e.target.closest('a');
      if (!a) return;
      const href = a.getAttribute('href');
      if (!href) return;
      // Only handle same-origin navigations (not anchors, downloads, target=_blank)
      if (a.target === '_blank' || a.hasAttribute('download')) return;
      if (href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('javascript:')) return;
      const url = new URL(href, location.href);
      if (url.origin !== location.origin) return;
      // Only navigations to a different path (skip in-page clicks)
      if (url.pathname === location.pathname && url.search === location.search) return;
      e.preventDefault();
      document.startViewTransition(function () {
        location.href = url.href;
      });
    });
  };

  // -----------------------------------------------------------------------
  // Service worker update toast — prompt user to reload when new SW activates
  // -----------------------------------------------------------------------
  DN.bindSWUpdateToast = function (registration) {
    if (!registration) return;
    function showToast() {
      if (document.getElementById('dn-sw-toast')) return;
      const toast = document.createElement('div');
      toast.id = 'dn-sw-toast';
      toast.style.cssText = 'position:fixed;left:50%;bottom:max(24px,env(safe-area-inset-bottom));transform:translateX(-50%);background:#0c5159;color:#fff;padding:10px 16px 10px 18px;border-radius:9999px;display:flex;align-items:center;gap:12px;font-size:13px;font-weight:600;z-index:60;box-shadow:0 12px 28px -8px rgba(12,81,89,.55);max-width:calc(100vw - 24px);';
      toast.innerHTML = '<span>網站已更新 — </span><button style="background:#fff;color:#4d6358;border:none;padding:5px 12px;border-radius:9999px;font-weight:700;font-size:12px;cursor:pointer">重新載入</button>';
      toast.querySelector('button').addEventListener('click', function () {
        if (registration.waiting) registration.waiting.postMessage({ type: 'SKIP_WAITING' });
        location.reload();
      });
      document.body.appendChild(toast);
    }
    if (registration.waiting) showToast();
    registration.addEventListener('updatefound', function () {
      const sw = registration.installing;
      if (!sw) return;
      sw.addEventListener('statechange', function () {
        if (sw.state === 'installed' && navigator.serviceWorker.controller) showToast();
      });
    });
  };

  DN.injectMobileMenu = function () {
    if (document.getElementById('dnMobileMenuBtn')) return;
    const header = document.querySelector('header.sticky') || document.querySelector('header');
    if (!header) return;
    const headerInner = header.querySelector('.h-16') || header.querySelector('div.flex.items-center.justify-between') || header.firstElementChild;
    if (!headerInner) return;
    const right = headerInner.lastElementChild;

    const btn = document.createElement('button');
    btn.id = 'dnMobileMenuBtn';
    btn.type = 'button';
    btn.className = 'sm:hidden inline-flex items-center justify-center w-9 h-9 rounded-lg border border-[var(--border)] bg-white mr-2';
    btn.setAttribute('aria-label', 'Menu');
    btn.setAttribute('aria-expanded', 'false');
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/></svg>';
    right.parentNode.insertBefore(btn, right);

    const drawer = document.createElement('div');
    drawer.id = 'dnMobileDrawer';
    drawer.className = 'hidden sm:hidden border-t border-[var(--border)]';
    drawer.style.cssText = 'background:rgba(245,251,250,.98);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);max-height:calc(100vh - 64px);overflow-y:auto;-webkit-overflow-scrolling:touch';
    drawer.innerHTML =
      '<nav class="max-w-6xl mx-auto px-5 py-4 flex flex-col gap-1">' +
        '<a href="/" class="block px-3 py-2.5 rounded-lg hover:bg-[var(--mint-soft)] text-[14px] font-semibold text-teal-700" data-zh="首頁" data-en="Home"></a>' +
        '<a href="/blog/" class="block px-3 py-2.5 rounded-lg hover:bg-[var(--mint-soft)] text-[14px] font-semibold text-teal-700" data-zh="衛教文章" data-en="Articles"></a>' +
        '<a href="/about" class="block px-3 py-2 rounded-lg hover:bg-[var(--mint-soft)] text-[14px] font-semibold text-teal-700" data-zh="關於我" data-en="About"></a>' +
        '<a href="/tools" class="block px-3 py-2 rounded-lg hover:bg-[var(--mint-soft)] text-[14px] font-semibold text-teal-700" data-zh="量表計算器" data-en="Calculators"></a>' +
        '<a href="/glossary" class="block px-3 py-2 rounded-lg hover:bg-[var(--mint-soft)] text-[14px] font-semibold text-teal-700" data-zh="詞彙字典" data-en="Glossary"></a>' +
      '</nav>';
    header.appendChild(drawer);

    function open()  { drawer.classList.remove('hidden'); btn.setAttribute('aria-expanded', 'true');  document.body.style.overflow = 'hidden'; }
    function close() { drawer.classList.add('hidden');    btn.setAttribute('aria-expanded', 'false'); document.body.style.overflow = ''; }
    btn.addEventListener('click', function () { drawer.classList.contains('hidden') ? open() : close(); });
    drawer.querySelectorAll('a').forEach(function (a) { a.addEventListener('click', close); });
    window.addEventListener('resize', function () { if (window.innerWidth >= 640) close(); });
  };

  // -----------------------------------------------------------------------
  // Article catalog (single source of truth for related-articles / TOC links).
  // -----------------------------------------------------------------------
  DN.ARTICLES = [
    { slug:'acne-myths',          title:'痘痘 9 大迷思', cat:'myth', tag:'痘痘', date:'2026-05-03', emoji:'', tag_en:'Acne' },
    { slug:'sunscreen-myths',     title:'防曬 8 大迷思', cat:'myth', tag:'防曬', date:'2026-05-03', emoji:'', tag_en:'Sunscreen' },
    { slug:'eczema-myths',        title:'異位性皮膚炎 6 大迷思', cat:'myth', tag:'異膚', date:'2026-05-03', emoji:'', tag_en:'Eczema' },
    { slug:'melasma-myths',       title:'肝斑 7 大迷思', cat:'myth', tag:'肝斑', date:'2026-05-03', emoji:'', tag_en:'Melasma' },
    { slug:'rosacea-myths',       title:'玫瑰痤瘡 6 大迷思', cat:'myth', tag:'酒糟肌', date:'2026-05-03', emoji:'', tag_en:'Rosacea' },
    { slug:'hairloss-myths',      title:'落髮 / 雄性禿 7 大迷思', cat:'myth', tag:'落髮', date:'2026-05-03', emoji:'', tag_en:'Hair loss' },
    { slug:'tinea-myths',         title:'香港腳 / 灰指甲 7 大迷思', cat:'myth', tag:'足癬', date:'2026-05-03', emoji:'', tag_en:'Tinea' },
    { slug:'urticaria-myths',     title:'蕁麻疹 6 大迷思', cat:'myth', tag:'蕁麻疹', date:'2026-05-04', emoji:'', tag_en:'Urticaria' },
    { slug:'psoriasis-myths',     title:'乾癬 7 大迷思', cat:'myth', tag:'乾癬', date:'2026-05-04', emoji:'', tag_en:'Psoriasis' },
    { slug:'warts-myths',         title:'病毒疣 6 大迷思', cat:'myth', tag:'病毒疣', date:'2026-05-04', emoji:'', tag_en:'Warts' },
    { slug:'shingles-myths',      title:'帶狀皰疹 6 大迷思', cat:'myth', tag:'皮蛇', date:'2026-05-04', emoji:'', tag_en:'Shingles' },
    { slug:'topical-acids-patient', title:'外用酸類完整衛教', cat:'product', tag:'酸類', date:'2026-05-02', emoji:'', tag_en:'Topical acids' },
    { slug:'isotretinoin-patient',  title:'口服 A 酸完整衛教', cat:'rx', tag:'口服 A 酸', date:'2026-05-02', emoji:'', tag_en:'Isotretinoin' },
    { slug:'acne-scar-treatment',   title:'痘疤完整治療指引', cat:'rx', tag:'痘疤', date:'2026-05-04', emoji:'', tag_en:'Acne scars' },
    { slug:'alopecia-areata',     title:'圓禿（鬼剃頭）完整衛教', cat:'rx', tag:'圓禿', date:'2026-05-04', emoji:'', tag_en:'Alopecia areata' },
    { slug:'demodex-rosacea',     title:'蠕形蟎蟲與玫瑰斑(酒糟)', cat:'rx', tag:'玫瑰斑', date:'2026-05-04', emoji:'', tag_en:'Demodex rosacea' },
    { slug:'vitiligo', title:'白斑（Vitiligo）完整衛教', cat:'rx', tag:'白斑', date:'2026-05-04', emoji:'', tag_en:'Vitiligo' },
    { slug:'mpox-care', title:'猴痘（Mpox）皮膚照護', cat:'rx', tag:'猴痘', date:'2026-05-04', emoji:'', tag_en:'Mpox' },
    { slug:'hidradenitis-suppurativa', title:'化膿性汗腺炎（HS）完整衛教', cat:'rx', tag:'化膿性汗腺炎', date:'2026-05-04', emoji:'', tag_en:'HS' },
    { slug:'targeted-therapy-skin', title:'標靶藥物（TKI）皮膚副作用', cat:'rx', tag:'標靶藥物', date:'2026-05-04', emoji:'', tag_en:'Targeted therapy skin' },
    { slug:'topical-steroids-guide', title:'外用類固醇完整指南', cat:'rx', tag:'外用類固醇', date:'2026-05-04', emoji:'', tag_en:'Topical steroids' },
    { slug:'biologics-overview', title:'皮膚科生物製劑與小分子標靶藥物總覽', cat:'rx', tag:'生物製劑', date:'2026-05-04', emoji:'', tag_en:'Biologics' },
    { slug:'skin-whitening-agents', title:'美白成分完整解析', cat:'product', tag:'美白', date:'2026-05-04', emoji:'', tag_en:'Whitening agents' },
    { slug:'dermatology-faq', title:'皮膚科 25 個最常見問題', cat:'myth', tag:'常見問題', date:'2026-05-05', emoji:'', tag_en:'FAQ' },
    { slug:'epidermoid-cyst', title:'粉瘤完整衛教', cat:'rx', tag:'粉瘤', date:'2026-05-05', emoji:'', tag_en:'Epidermoid cyst' },
    { slug:'nhi-derm-drugs', title:'皮膚科常用藥物健保規範完整整理', cat:'rx', tag:'健保規範', date:'2026-05-05', emoji:'', tag_en:'NHI rules' },
    { slug:'laser-dermatology', title:'皮膚科雷射完整對照', cat:'rx', tag:'雷射 / 光電', date:'2026-05-05', emoji:'', tag_en:'Laser dermatology' },
    { slug:'pediatric-eczema', title:'嬰幼兒 / 兒童異位性皮膚炎完整照護指南', cat:'rx', tag:'兒童異膚', date:'2026-05-05', emoji:'', tag_en:'Pediatric AD' },
    { slug:'prurigo-nodularis', title:'結節性癢疹完整衛教', cat:'rx', tag:'結節性癢疹', date:'2026-05-07', emoji:'', tag_en:'Prurigo Nodularis' },
    { slug:'cutaneous-t-cell-lymphoma', title:'皮膚 T 細胞淋巴瘤(CTCL/MF)完整衛教', cat:'rx', tag:'皮膚淋巴瘤', date:'2026-05-07', emoji:'', tag_en:'CTCL / MF' }
  ];

  // -----------------------------------------------------------------------
  // Article numbering — assign #001-#NNN by chronological publish order
  // (date asc, then array order as tiebreaker for same-day publishes)
  // -----------------------------------------------------------------------
  // -----------------------------------------------------------------------
  // Reading progress tracker (localStorage) — auto-mark on article view
  // Provides DN.markRead, DN.getReadSlugs, DN.getReadCount, DN.resetRead
  // -----------------------------------------------------------------------
  DN.READ_KEY = 'dn-read-articles-v1';

  DN.getReadSlugs = function () {
    try {
      var raw = localStorage.getItem(DN.READ_KEY);
      if (!raw) return [];
      var arr = JSON.parse(raw);
      return Array.isArray(arr) ? arr : [];
    } catch (e) { return []; }
  };

  DN.markRead = function (slug) {
    if (!slug) return;
    var slugs = DN.getReadSlugs();
    if (slugs.indexOf(slug) !== -1) return;
    slugs.push(slug);
    try {
      localStorage.setItem(DN.READ_KEY, JSON.stringify(slugs));
      // Notify any active progress widgets
      window.dispatchEvent(new CustomEvent('dn-read-updated'));
      if (typeof gtag === 'function') {
        try {
          gtag('event', 'article_read', {
            slug: slug,
            total_read: slugs.length,
            page_path: location.pathname
          });
          // Milestones
          if (slugs.length === 5 || slugs.length === 10 || slugs.length === 20 || slugs.length === DN.totalArticles) {
            gtag('event', 'reading_milestone', { milestone: slugs.length, total: DN.totalArticles });
          }
        } catch (e) {}
      }
    } catch (e) {}
  };

  DN.getReadCount = function () { return DN.getReadSlugs().length; };

  DN.resetRead = function () {
    try { localStorage.removeItem(DN.READ_KEY); window.dispatchEvent(new CustomEvent('dn-read-updated')); } catch (e) {}
  };

  // Reading progress widget — injects into target element with id="dn-read-progress"
  DN.injectReadProgress = function () {
    var host = document.getElementById('dn-read-progress');
    if (!host) return;

    function render() {
      var read = DN.getReadCount();
      var total = DN.totalArticles || 1;
      var pct = Math.round((read / total) * 100);

      host.innerHTML =
        '<div style="background:#fff;border:1px solid var(--border, #dcd5c8);border-radius:14px;padding:18px 22px;box-shadow:0 1px 2px rgba(15,23,42,.04)">' +
          '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px">' +
            '<div>' +
              '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.22em;color:#4d6358;font-weight:700;margin-bottom:2px">閱讀進度</div>' +
              '<div style="font-family:\'Noto Serif TC\',Georgia,serif;font-size:18px;font-weight:700;color:#0f172a">' +
                '已讀 <span style="color:#0c5159">' + read + '</span> / ' + total + ' 篇 ' +
                '<span style="font-size:13px;font-weight:500;color:#5e574e">(' + pct + '%)</span>' +
              '</div>' +
            '</div>' +
            (read > 0
              ? '<button id="dn-read-reset" type="button" style="background:#fff;border:1px solid var(--border, #dcd5c8);color:#5e574e;padding:5px 10px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer">重設進度</button>'
              : '<span style="font-size:12px;color:#8b8378;font-style:italic">逐篇閱讀後自動記錄</span>') +
          '</div>' +
          '<div style="height:8px;background:#f1ece4;border-radius:9999px;overflow:hidden">' +
            '<div style="height:100%;width:' + pct + '%;background:linear-gradient(90deg,#a4b5a8,#0c5159);transition:width .35s ease;"></div>' +
          '</div>' +
        '</div>';

      var resetBtn = document.getElementById('dn-read-reset');
      if (resetBtn) resetBtn.addEventListener('click', function () {
        if (confirm('要重設閱讀進度嗎? 本動作只會清除本裝置的紀錄,不會影響網站。')) {
          DN.resetRead();
        }
      });
    }
    render();
    window.addEventListener('dn-read-updated', render);
    window.addEventListener('storage', function (e) {
      if (e.key === DN.READ_KEY) render();
    });
  };

  DN.numberMap = (function () {
    var sorted = (DN.ARTICLES || []).slice()
      .map(function (a, i) { return { slug: a.slug, date: a.date || '', _orig: i }; })
      .sort(function (a, b) {
        return (a.date.localeCompare(b.date)) || (a._orig - b._orig);
      });
    var map = {};
    sorted.forEach(function (a, i) {
      map[a.slug] = String(i + 1).padStart(3, '0');
    });
    return map;
  })();
  DN.getArticleNumber = function (slug) {
    return DN.numberMap[slug] || null;
  };
  DN.totalArticles = (DN.ARTICLES || []).length;

  DN.currentSlug = function () {
    const m = location.pathname.match(/\/blog\/([a-z0-9-]+)\/?$/i);
    return m ? m[1] : null;
  };

  // -----------------------------------------------------------------------
  // Reading time + last-reviewed badge — injected at top of article hero
  // (right before the disclaimer or right after the H1 lead paragraph)
  // -----------------------------------------------------------------------
  DN.addReadingMeta = function () {
    const proseEl = document.getElementById('proseZh') || document.querySelector('article .prose');
    if (!proseEl) return;
    const text = (proseEl.textContent || '').replace(/\s+/g, '');
    const cjkChars = (text.match(/[一-鿿]/g) || []).length;
    const otherWords = (text.match(/[A-Za-z0-9]+/g) || []).length;
    // Reading speed: ~350 zh chars/min OR ~200 en words/min
    const minutes = Math.max(2, Math.round(cjkChars / 350 + otherWords / 200));

    const slug = DN.currentSlug();
    const meta = (DN.ARTICLES || []).find(function (a) { return a.slug === slug; });
    const reviewedDate = meta ? meta.date : '2026-05-04';

    // Find a good insertion point — right after first <h1> sibling chain
    const h1 = document.querySelector('article h1, section h1');
    const lead = h1 ? h1.parentElement.querySelector('p') : null;
    const target = lead || h1;
    if (!target) return;
    if (document.getElementById('dn-reading-meta')) return;

    const bar = document.createElement('div');
    bar.id = 'dn-reading-meta';
    bar.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:14px 0 8px;font-size:12.5px;color:var(--ink-2);';

    // Article number badge
    const articleNum = DN.getArticleNumber(slug);
    const numBadge = articleNum
      ? '<span style="display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:9999px;background:linear-gradient(180deg,#a4b5a8,#4d6358);color:#fff;font-weight:700;letter-spacing:.04em;font-family:Inter,sans-serif"><span aria-hidden="true">№</span><span>' + articleNum + ' / ' + String(DN.totalArticles).padStart(3,'0') + '</span></span>'
      : '';

    bar.innerHTML =
      numBadge +
      '<span style="display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:9999px;background:#f1ece4;border:1px solid #a5f3fc;color:#4d6358;font-weight:600">' +
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>' +
        '<span data-zh="閱讀約 ' + minutes + ' 分鐘" data-en="' + minutes + ' min read">閱讀約 ' + minutes + ' 分鐘</span>' +
      '</span>' +
      '<span style="display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:9999px;background:#dcfce7;border:1px solid #86efac;color:#14532d;font-weight:600">' +
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>' +
        '<span data-zh="最後審閱 ' + reviewedDate + '" data-en="Last reviewed · ' + reviewedDate + '">最後審閱 ' + reviewedDate + '</span>' +
      '</span>' +
      '<a href="/about" style="display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:9999px;background:#fff;border:1px solid var(--border);color:var(--teal-deep);text-decoration:none;font-weight:600" data-zh="陳翊嘉醫師 →" data-en="Dr. Chen Yi-Jia →">陳翊嘉醫師 →</a>';
    target.parentNode.insertBefore(bar, target.nextSibling);

    // Mark this article as read (localStorage tracker)
    if (slug) DN.markRead(slug);
  };

  // -----------------------------------------------------------------------
  // Inline article TOC ("本篇大綱") + scroll-position memory.
  // Mobile + desktop: inserts a collapsible card at the top of the article
  // listing all H2 headings. Saves scroll position to localStorage and
  // offers a "continue reading" toast if the user reopens the page.
  // -----------------------------------------------------------------------
  DN.addInlineTOC = function () {
    var proseEl = document.getElementById('proseZh') || document.querySelector('article .prose');
    if (!proseEl) return;
    if (document.getElementById('dn-inline-toc')) return;
    var h2s = proseEl.querySelectorAll('h2[id]');
    if (h2s.length < 3) return;

    var details = document.createElement('details');
    details.id = 'dn-inline-toc';
    details.open = true;
    details.style.cssText = 'margin:18px 0 24px;background:linear-gradient(135deg,#f5fbfa 0%,#ecfeff 100%);border:1px solid #a5f3fc;border-radius:14px;padding:0;overflow:hidden';

    var summary = document.createElement('summary');
    summary.style.cssText = 'cursor:pointer;list-style:none;padding:14px 18px;font-size:13px;font-weight:700;color:#0c5159;display:flex;align-items:center;justify-content:space-between;gap:8px;user-select:none';
    summary.innerHTML =
      '<span style="display:inline-flex;align-items:center;gap:8px">' +
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
          '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/>' +
          '<line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>' +
        '</svg>' +
        '<span data-zh="本篇大綱" data-en="In this article">本篇大綱</span>' +
        '<span style="font-size:11px;font-weight:600;color:#4d6358;opacity:.7">· ' + h2s.length + ' 段</span>' +
      '</span>' +
      '<span style="font-size:11px;color:#4d6358;opacity:.7" data-zh="點擊收合" data-en="Click to collapse">點擊收合</span>';
    details.appendChild(summary);

    var ol = document.createElement('ol');
    ol.style.cssText = 'list-style:none;counter-reset:toc;padding:4px 18px 14px;margin:0;display:flex;flex-direction:column;gap:2px';
    h2s.forEach(function (h, i) {
      var li = document.createElement('li');
      li.style.cssText = 'counter-increment:toc;position:relative;padding:5px 4px 5px 32px';
      li.innerHTML =
        '<span style="position:absolute;left:0;top:5px;width:24px;height:22px;display:inline-flex;align-items:center;justify-content:center;font-size:10.5px;font-weight:700;color:#0e7c86;background:#fff;border:1px solid #a5f3fc;border-radius:6px">' + (i + 1) + '</span>' +
        '<a href="#' + h.id + '" data-toc-inline="' + h.id + '" style="display:block;color:var(--ink-2);text-decoration:none;font-size:13.5px;line-height:1.6;font-weight:500">' + (h.textContent || ('Section ' + (i + 1))) + '</a>';
      ol.appendChild(li);
    });
    details.appendChild(ol);

    // Insert at the top of <article> (before the first .prose block content)
    var articleEl = document.querySelector('article');
    if (articleEl && articleEl.firstElementChild) {
      // Place after the H1 if present, else before the first prose block
      var h1 = articleEl.querySelector('h1');
      if (h1 && h1.parentNode) {
        h1.parentNode.insertBefore(details, h1.nextSibling);
      } else {
        articleEl.insertBefore(details, articleEl.firstElementChild);
      }
    } else {
      proseEl.parentNode.insertBefore(details, proseEl);
    }

    // Smooth scroll on link click
    ol.addEventListener('click', function (e) {
      var a = e.target.closest('a[data-toc-inline]');
      if (!a) return;
      e.preventDefault();
      var id = a.dataset.tocInline;
      var target = document.getElementById(id);
      if (target) {
        var top = target.getBoundingClientRect().top + window.pageYOffset - 80;
        window.scrollTo({ top: top, behavior: 'smooth' });
        history.pushState(null, '', '#' + id);
        if (window.gtag) window.gtag('event', 'toc_click', { section_id: id });
      }
    });
  };

  // Save scroll position with localStorage; offer "continue reading" toast
  DN.bindScrollMemory = function () {
    var slug = DN.currentSlug();
    if (!slug) return;
    var proseEl = document.getElementById('proseZh') || document.querySelector('article .prose');
    if (!proseEl) return;
    var KEY = 'dn:scroll:' + slug;
    var MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000; // 14 days

    function saveNow() {
      try {
        var docH = document.documentElement.scrollHeight - window.innerHeight;
        if (docH < 100) return;
        var y = window.pageYOffset;
        var pct = Math.min(100, Math.max(0, Math.round((y / docH) * 100)));
        // Only save meaningful positions
        if (pct < 3 || pct > 97) {
          localStorage.removeItem(KEY);
          return;
        }
        // Find nearest H2 above current position for label
        var h2s = proseEl.querySelectorAll('h2[id]');
        var nearest = null;
        var nearestIdx = 0;
        for (var i = 0; i < h2s.length; i++) {
          var top = h2s[i].getBoundingClientRect().top + window.pageYOffset;
          if (top <= y + 120) { nearest = h2s[i]; nearestIdx = i; }
          else break;
        }
        var data = {
          y: y,
          pct: pct,
          ts: Date.now(),
          h2: nearest ? (nearest.textContent || '').slice(0, 40) : '',
          h2i: nearestIdx
        };
        localStorage.setItem(KEY, JSON.stringify(data));
      } catch (e) { /* quota etc. */ }
    }

    var saveTimer = null;
    window.addEventListener('scroll', function () {
      if (saveTimer) clearTimeout(saveTimer);
      saveTimer = setTimeout(saveNow, 500);
    }, { passive: true });
    window.addEventListener('beforeunload', saveNow);
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'hidden') saveNow();
    });

    // Restore prompt
    function maybePrompt() {
      // Don't prompt if user navigated to an anchor
      if (window.location.hash) return;
      var raw;
      try { raw = localStorage.getItem(KEY); } catch (e) { return; }
      if (!raw) return;
      var data;
      try { data = JSON.parse(raw); } catch (e) { localStorage.removeItem(KEY); return; }
      if (!data || !data.y || !data.pct) return;
      if (Date.now() - (data.ts || 0) > MAX_AGE_MS) { localStorage.removeItem(KEY); return; }
      if (data.pct < 5 || data.pct > 95) return;

      var toast = document.createElement('div');
      toast.id = 'dn-resume-toast';
      toast.style.cssText =
        'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:9999;' +
        'background:#fff;border:1px solid #a5f3fc;border-radius:14px;' +
        'box-shadow:0 18px 40px -16px rgba(12,81,89,.35),0 4px 10px rgba(15,23,42,.08);' +
        'padding:14px 18px;display:flex;align-items:center;gap:14px;flex-wrap:wrap;' +
        'max-width:calc(100vw - 32px);font-size:13.5px;color:var(--ink);' +
        'animation:dn-toast-in .35s cubic-bezier(.2,.7,.3,1)';
      var label = data.h2 ? '「' + data.h2 + '」' : '';
      toast.innerHTML =
        '<div style="display:flex;align-items:center;gap:10px;flex:1;min-width:200px">' +
          '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0e7c86" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<path d="M21 12a9 9 0 1 1-9-9c2.5 0 4.8 1 6.5 2.6L21 8"/><path d="M21 3v5h-5"/>' +
          '</svg>' +
          '<div style="line-height:1.5">' +
            '<div style="font-weight:700;color:#0c5159">上次讀到 ' + data.pct + '%</div>' +
            (label ? '<div style="font-size:12px;color:var(--ink-2);margin-top:2px">' + label + '</div>' : '') +
          '</div>' +
        '</div>' +
        '<div style="display:flex;gap:8px;flex-shrink:0">' +
          '<button data-resume-yes style="padding:7px 14px;border-radius:9999px;background:#0e7c86;color:#fff;border:0;font-weight:700;font-size:12.5px;cursor:pointer">繼續閱讀</button>' +
          '<button data-resume-no style="padding:7px 12px;border-radius:9999px;background:#fff;color:var(--ink-2);border:1px solid var(--border);font-weight:600;font-size:12.5px;cursor:pointer">從頭開始</button>' +
        '</div>';
      // Inject keyframes once
      if (!document.getElementById('dn-resume-style')) {
        var st = document.createElement('style');
        st.id = 'dn-resume-style';
        st.textContent = '@keyframes dn-toast-in{from{opacity:0;transform:translate(-50%,16px)}to{opacity:1;transform:translate(-50%,0)}}';
        document.head.appendChild(st);
      }
      document.body.appendChild(toast);

      function dismiss() { if (toast.parentNode) toast.parentNode.removeChild(toast); }
      toast.querySelector('[data-resume-yes]').addEventListener('click', function () {
        window.scrollTo({ top: data.y, behavior: 'smooth' });
        dismiss();
        if (window.gtag) window.gtag('event', 'resume_reading', { slug: slug, pct: data.pct });
      });
      toast.querySelector('[data-resume-no]').addEventListener('click', function () {
        try { localStorage.removeItem(KEY); } catch (e) {}
        dismiss();
      });
      // Auto-dismiss after 12s
      setTimeout(function () { if (toast.parentNode) toast.style.opacity = '0', setTimeout(dismiss, 350); }, 12000);
    }
    // Slight delay so layout settles
    setTimeout(maybePrompt, 600);
  };

  // -----------------------------------------------------------------------
  // Floating sidebar TOC for desktop (≥1280px). Generated from <h2 id="">
  // inside #proseZh. Smooth-scrolls, highlights current section.
  // -----------------------------------------------------------------------
  DN.addFloatingTOC = function () {
    if (window.innerWidth < 1280) return;
    const proseEl = document.getElementById('proseZh') || document.querySelector('article .prose');
    if (!proseEl) return;
    const h2s = proseEl.querySelectorAll('h2[id]');
    if (h2s.length < 3) return;
    if (document.getElementById('dn-toc-float')) return;

    const aside = document.createElement('aside');
    aside.id = 'dn-toc-float';
    aside.style.cssText = 'position:fixed;left:max(16px,calc(50% - 720px));top:120px;width:200px;max-height:calc(100vh - 160px);overflow-y:auto;padding:14px 16px;background:rgba(255,255,255,.92);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border:1px solid var(--border);border-radius:14px;box-shadow:0 12px 28px -14px rgba(77,99,88,.22);font-size:12.5px;line-height:1.7;z-index:30;';
    let html = '<div style="font-size:10.5px;text-transform:uppercase;letter-spacing:.18em;color:var(--teal-deep);font-weight:700;margin-bottom:8px">本篇大綱</div><ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:5px" id="dn-toc-list">';
    h2s.forEach(function (h, i) {
      html += '<li><a href="#' + h.id + '" data-toc="' + h.id + '" style="display:block;padding:5px 8px;border-radius:6px;color:var(--ink-2);text-decoration:none;border-left:2px solid transparent;transition:all .15s">' + (h.textContent || ('Section ' + (i + 1))).slice(0, 28) + '</a></li>';
    });
    html += '</ul>';
    aside.innerHTML = html;
    document.body.appendChild(aside);

    // Active section tracking via IntersectionObserver
    const links = aside.querySelectorAll('a[data-toc]');
    function setActive(id) {
      links.forEach(function (l) {
        const active = l.dataset.toc === id;
        l.style.color = active ? 'var(--teal-deep)' : 'var(--ink-2)';
        l.style.background = active ? 'var(--mint-soft)' : 'transparent';
        l.style.borderLeftColor = active ? 'var(--teal)' : 'transparent';
        l.style.fontWeight = active ? '700' : '500';
      });
    }
    const io = new IntersectionObserver(function (entries) {
      const visible = entries.filter(function (e) { return e.isIntersecting; });
      if (visible.length) setActive(visible[0].target.id);
    }, { rootMargin: '-30% 0px -50% 0px' });
    h2s.forEach(function (h) { io.observe(h); });

    // Hide on resize below threshold
    window.addEventListener('resize', function () {
      aside.style.display = (window.innerWidth >= 1280) ? '' : 'none';
    });
  };

  // -----------------------------------------------------------------------
  // Related articles section — appended after <article> on blog post pages.
  // Picks 3 articles, prefers same category, excludes current slug.
  // Adds JSON-LD ItemList for SEO.
  // -----------------------------------------------------------------------
  DN.addRelatedArticles = function () {
    const article = document.querySelector('article.max-w-3xl');
    if (!article) return;
    if (document.getElementById('dn-related')) return;
    const slug = DN.currentSlug();
    if (!slug) return;
    const all = DN.ARTICLES || [];
    const cur = all.find(function (a) { return a.slug === slug; });
    if (!cur) return;

    // Score: same category +2, otherwise +1; pick top 3
    const scored = all.filter(function (a) { return a.slug !== slug; })
      .map(function (a) { return { a: a, s: (a.cat === cur.cat ? 2 : 1) + Math.random() * 0.5 }; })
      .sort(function (x, y) { return y.s - x.s; })
      .slice(0, 3)
      .map(function (x) { return x.a; });

    const wrap = document.createElement('section');
    wrap.id = 'dn-related';
    wrap.className = 'max-w-3xl mx-auto px-5 sm:px-8 my-10';
    let html = '<div style="border-top:1px solid var(--line);padding-top:24px"><div style="font-size:11px;text-transform:uppercase;letter-spacing:.22em;color:var(--teal-deep);font-weight:700;margin-bottom:12px" data-zh="你可能也會想看" data-en="Related reads">你可能也會想看</div><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">';
    scored.forEach(function (a) {
      html += '<a href="/blog/' + a.slug + '" style="display:flex;flex-direction:column;gap:6px;padding:14px;background:#fff;border:1px solid var(--border);border-radius:12px;text-decoration:none;color:var(--ink);transition:all .15s;box-shadow:0 1px 2px rgba(15,23,42,.04)" onmouseover="this.style.borderColor=\'rgba(122,146,133,.5)\';this.style.transform=\'translateY(-2px)\';this.style.boxShadow=\'0 10px 20px -10px rgba(77,99,88,.22)\'" onmouseout="this.style.borderColor=\'var(--border)\';this.style.transform=\'\';this.style.boxShadow=\'0 1px 2px rgba(15,23,42,.04)\'">' +
        '<span style="font-size:11px;font-weight:700;letter-spacing:.18em;color:var(--teal-deep);text-transform:uppercase">' + (a.tag_en || a.tag) + '</span>' +
        '<span style="font-size:14px;font-weight:700;line-height:1.4;font-family:Noto Serif TC,Georgia,serif">' + a.title + '</span>' +
        '<span style="font-size:11.5px;color:var(--muted)">' + a.tag + ' · ' + a.date + '</span>' +
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
        '<span style="font-size:12.5px;font-weight:700;color:var(--ink-2);margin-right:6px" data-zh="覺得有幫助? 分享給朋友：" data-en="Found this useful? Share:">覺得有幫助? 分享給朋友：</span>' +
        '<a target="_blank" rel="noopener" href="https://social-plugins.line.me/lineit/share?url=' + url + '" aria-label="LINE" data-share="line" style="display:inline-flex;align-items:center;gap:6px;padding:7px 13px;background:#06c755;color:#fff;border-radius:9999px;font-size:12.5px;font-weight:700;text-decoration:none">LINE</a>' +
        '<a target="_blank" rel="noopener" href="https://www.facebook.com/sharer/sharer.php?u=' + url + '" aria-label="Facebook" data-share="facebook" style="display:inline-flex;align-items:center;gap:6px;padding:7px 13px;background:#1877f2;color:#fff;border-radius:9999px;font-size:12.5px;font-weight:700;text-decoration:none">Facebook</a>' +
        '<a target="_blank" rel="noopener" href="https://twitter.com/intent/tweet?url=' + url + '&text=' + title + '" aria-label="Twitter" data-share="twitter" style="display:inline-flex;align-items:center;gap:6px;padding:7px 13px;background:#1f2937;color:#fff;border-radius:9999px;font-size:12.5px;font-weight:700;text-decoration:none">𝕏</a>' +
        '<button id="dn-copy" data-share="copy" style="display:inline-flex;align-items:center;gap:6px;padding:7px 13px;background:#fff;color:var(--ink);border:1px solid var(--border);border-radius:9999px;font-size:12.5px;font-weight:700;cursor:pointer" data-zh="📋 複製連結" data-en="📋 Copy link">📋 複製連結</button>' +
        (navigator.share ? '<button id="dn-native-share" data-share="native" style="display:inline-flex;align-items:center;gap:6px;padding:7px 13px;background:linear-gradient(180deg,#a4b5a8,#4d6358);color:#fff;border:none;border-radius:9999px;font-size:12.5px;font-weight:700;cursor:pointer">↗ 系統分享</button>' : '') +
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
  // Reads dates from DN.ARTICLES catalog by matching href slug.
  // -----------------------------------------------------------------------
  // -----------------------------------------------------------------------
  // -----------------------------------------------------------------------
  // TDA disease guideline mapping — auto-inject TDA URL block when applicable
  // -----------------------------------------------------------------------
  DN.TDA_GUIDELINE = {
    'acne-myths':                'TDA 痤瘡臨床治療共識(2024)',
    'eczema-myths':              'TDA 異位性皮膚炎診療共識(2020 更新)',
    'rosacea-myths':             'TDA 玫瑰斑(酒糟)治療共識(2022)',
    'demodex-rosacea':           'TDA 玫瑰斑(酒糟)治療共識(2022)',
    'hairloss-myths':            'TDA 圓禿診斷及治療共識(2024)',
    'alopecia-areata':           'TDA 圓禿診斷及治療共識(2024)',
    'urticaria-myths':           'TDA 蕁麻疹定義、分類、診斷暨治療共識(2021)',
    'psoriasis-myths':           'TDA 尋常型乾癬治療共識手冊(2024)',
    'shingles-myths':            'TDA 帶狀疱疹疫苗接種建議(2022)',
    'mpox-care':                 'TDA 猴痘皮膚照護建議指引',
    'vitiligo':                  'TDA 白斑臨床治療共識(2024)',
    'hidradenitis-suppurativa':  'TDA 化膿性汗腺炎臨床診療共識建議',
    'targeted-therapy-skin':     'TLCS + TDA TKI 標靶藥物相關皮膚毒性共識（2024）',
  };
  DN.addTDALink = function () {
    const slug = DN.currentSlug();
    if (!slug || !DN.TDA_GUIDELINE[slug]) return;
    if (document.getElementById('dn-tda-link')) return;
    if (document.getElementById('tda-link')) return;
    const article = document.querySelector('article.max-w-3xl');
    if (!article) return;
    const wrap = document.createElement('section');
    wrap.id = 'dn-tda-link';
    wrap.className = 'max-w-3xl mx-auto px-5 sm:px-8 my-6';
    wrap.innerHTML = '<div style="background:linear-gradient(180deg,#f5fbfa,#fff);border:1px solid var(--border);border-radius:14px;padding:18px 20px"><div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#4d6358;font-weight:700;margin-bottom:6px">📋 臺灣皮膚科醫學會官方資源</div><p style="margin:0 0 10px;font-size:13.5px;line-height:1.7;color:var(--ink-2)">本疾病有 ' + DN.TDA_GUIDELINE[slug] + '。完整官方共識可至以下查詢:</p><a href="https://www.derma.org.tw/clinical/" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:#fff;border:1px solid var(--border);border-radius:9999px;color:var(--teal-deep);font-weight:700;font-size:13px;text-decoration:none">→ 臺灣皮膚科醫學會 診療指引總覽</a></div>';
    article.parentNode.insertBefore(wrap, article.nextSibling);
  };

  // §86 醫療法保護 — auto-inject medical-disclaimer block at end of article
  // (resident-grade safety wording per agent research)
  // -----------------------------------------------------------------------
  // -----------------------------------------------------------------------
  // Interactive clinical calculators — SCORAD / SALT / UAS7
  // Auto-injected into specific articles by slug match.
  // Pure-JS, no backend, results live-update.
  // -----------------------------------------------------------------------
  DN.calcStyles = function () {
    if (document.getElementById('dn-calc-css')) return;
    var st = document.createElement('style');
    st.id = 'dn-calc-css';
    st.textContent =
      '.dn-calc{ background:#fff;border:1px solid var(--border, #dcd5c8);border-radius:14px;padding:18px 22px;margin:24px 0;box-shadow:0 8px 24px -14px rgba(77,99,88,.2) }' +
      '.dn-calc h3.dn-calc-title{ font-family:\'Noto Serif TC\',Georgia,serif;font-size:18px;font-weight:700;color:#0f172a;margin:0 0 4px }' +
      '.dn-calc .dn-calc-sub{ font-size:12.5px;color:#5e574e;margin-bottom:14px;line-height:1.6 }' +
      '.dn-calc-row{ display:grid;grid-template-columns:1fr auto;align-items:center;gap:10px;padding:8px 0;border-top:1px solid #ebe4d8 }' +
      '.dn-calc-row:first-of-type{ border-top:0 }' +
      '.dn-calc-row label{ font-size:13.5px;color:#2a2620;font-weight:600 }' +
      '.dn-calc-row .dn-calc-hint{ display:block;font-size:11.5px;color:#8b8378;font-weight:400;margin-top:2px;line-height:1.4 }' +
      '.dn-calc-input{ width:90px;padding:6px 10px;border:1px solid var(--border, #dcd5c8);border-radius:8px;font-size:14px;text-align:center;color:#0f172a;font-weight:700 }' +
      '.dn-calc-input:focus{ outline:none;border-color:rgba(122,146,133,.6);box-shadow:0 0 0 3px rgba(164,181,168,.20) }' +
      '.dn-calc-result{ margin-top:14px;padding:14px 16px;background:linear-gradient(135deg,#ecfeff,#f5fbfa);border:1px solid #a5f3fc;border-radius:12px }' +
      '.dn-calc-score{ font-family:\'Noto Serif TC\',Georgia,serif;font-size:32px;font-weight:800;color:#0c5159;line-height:1;margin:0 }' +
      '.dn-calc-band{ display:inline-block;margin-left:10px;padding:4px 12px;border-radius:9999px;font-size:12px;font-weight:700;letter-spacing:.04em;vertical-align:middle }' +
      '.dn-calc-interp{ font-size:13px;color:#0f172a;line-height:1.7;margin-top:6px }' +
      '.dn-calc-disclaimer{ font-size:11px;color:#8b8378;margin-top:10px;line-height:1.6;font-style:italic }' +
      '.dn-calc-tools-link{ display:inline-flex;align-items:center;gap:5px;margin-top:10px;padding:6px 12px;border-radius:9999px;background:#ede7da;color:#4d6358;font-size:12px;font-weight:700;text-decoration:none;border:1px solid #a5f3fc }' +
      '.dn-calc-tools-link:hover{ background:#d8d2c5 }' +
      '.dn-radio-group{ display:flex;gap:6px;flex-wrap:wrap }' +
      '.dn-radio-group button{ padding:5px 10px;border-radius:8px;border:1px solid var(--border, #dcd5c8);background:#fff;font-size:12.5px;font-weight:600;color:#5e574e;cursor:pointer;min-width:34px }' +
      '.dn-radio-group button.active{ background:linear-gradient(180deg,#a4b5a8,#4d6358);color:#fff;border-color:transparent }';
    document.head.appendChild(st);
  };

  // SCORAD (Atopic Dermatitis Severity)
  DN.injectSCORAD = function () {
    var slug = DN.currentSlug();
    if (slug !== 'eczema-myths' && slug !== 'pediatric-eczema') return;
    var anchor = document.querySelector('article.max-w-3xl');
    if (!anchor || document.getElementById('dn-scorad')) return;
    DN.calcStyles();

    var box = document.createElement('section');
    box.className = 'max-w-3xl mx-auto px-5 sm:px-8 my-6';
    box.innerHTML =
      '<div class="dn-calc" id="dn-scorad">' +
        '<h3 class="dn-calc-title" data-zh="SCORAD 計算器 — 異膚嚴重度自評" data-en="SCORAD Calculator — AD severity self-assessment">SCORAD 計算器 — 異膚嚴重度自評</h3>' +
        '<div class="dn-calc-sub" data-zh="SCORAD = A/5 + 7B/2 + C。A:受影響面積(0-100%)、B:6 項客觀症狀總分、C:2 項主觀症狀總分。完整版需臨床評估,本工具為簡易自評。" data-en="SCORAD = A/5 + 7B/2 + C. A: BSA, B: 6 objective signs, C: 2 subjective. Self-assessment only.">SCORAD = A/5 + 7B/2 + C。A:受影響面積(0-100%)、B:6 項客觀症狀總分、C:2 項主觀症狀總分。完整版需臨床評估,本工具為簡易自評。</div>' +
        '<div class="dn-calc-row">' +
          '<label data-zh="A · 受影響體表面積(%)" data-en="A · Affected BSA (%)">A · 受影響體表面積(%)<span class="dn-calc-hint" data-zh="0-100,可用九分法估算" data-en="0-100, use rule of nines">0-100,可用九分法估算</span></label>' +
          '<input type="number" min="0" max="100" step="1" value="20" class="dn-calc-input" id="dn-scorad-A" />' +
        '</div>' +
        '<div class="dn-calc-row">' +
          '<label data-zh="B · 6 項客觀症狀總分(0-18)" data-en="B · Objective signs (0-18)">B · 6 項客觀症狀總分<span class="dn-calc-hint" data-zh="紅斑、水腫/丘疹、滲出/結痂、抓痕、苔癬化、乾燥;每項 0-3" data-en="Erythema, edema, oozing, excoriation, lichenification, dryness; each 0-3">紅斑、水腫/丘疹、滲出/結痂、抓痕、苔癬化、乾燥;每項 0-3</span></label>' +
          '<input type="number" min="0" max="18" step="1" value="6" class="dn-calc-input" id="dn-scorad-B" />' +
        '</div>' +
        '<div class="dn-calc-row">' +
          '<label data-zh="C · 主觀症狀總分(0-20)" data-en="C · Subjective (0-20)">C · 主觀症狀總分<span class="dn-calc-hint" data-zh="癢感(0-10)+ 失眠(0-10),取過去 3 天平均" data-en="Itch (0-10) + sleep loss (0-10), past 3 days">癢感(0-10)+ 失眠(0-10),過去 3 天平均</span></label>' +
          '<input type="number" min="0" max="20" step="1" value="6" class="dn-calc-input" id="dn-scorad-C" />' +
        '</div>' +
        '<div class="dn-calc-result">' +
          '<div><span class="dn-calc-score" id="dn-scorad-score">—</span><span class="dn-calc-band" id="dn-scorad-band"></span></div>' +
          '<div class="dn-calc-interp" id="dn-scorad-interp"></div>' +
        '</div>' +
        '<a href="/tools#scorad" class="dn-calc-tools-link" data-zh="📖 查看完整 SCORAD 使用指南 →" data-en="View full SCORAD guide →">查看完整 SCORAD 使用指南 →</a>' +
        '<div class="dn-calc-disclaimer" data-zh="* 本工具僅作衛教自評用途。客觀分數需由皮膚科醫師判讀;治療決策應由主治醫師面對面評估。SCORAD: Stalder JF et al, Dermatology 1993." data-en="* For self-education only. Treatment decisions require an in-person dermatology evaluation.">* 本工具僅作衛教自評用途。客觀分數需由皮膚科醫師判讀;治療決策應由主治醫師面對面評估。SCORAD: Stalder JF et al, Dermatology 1993.</div>' +
      '</div>';
    anchor.parentNode.insertBefore(box, anchor.nextSibling);

    function calc() {
      var A = Math.max(0, Math.min(100, parseFloat(document.getElementById('dn-scorad-A').value) || 0));
      var B = Math.max(0, Math.min(18, parseFloat(document.getElementById('dn-scorad-B').value) || 0));
      var C = Math.max(0, Math.min(20, parseFloat(document.getElementById('dn-scorad-C').value) || 0));
      var score = A / 5 + 7 * B / 2 + C;
      var band, bg, fg, interp;
      if (score < 25) { band = '輕度'; bg = '#dcfce7'; fg = '#14532d'; interp = '輕度異膚 — 多數可用<strong>外用類固醇 + 保濕 + TCI</strong>控制。'; }
      else if (score < 50) { band = '中度'; bg = '#fef9c3'; fg = '#854d0e'; interp = '中度異膚 — 建議搭配 <strong>NB-UVB 光療或主動式類固醇/TCI proactive therapy</strong>。'; }
      else { band = '重度'; bg = '#fee2e2'; fg = '#991b1b'; interp = '重度異膚 — 應與皮膚科討論 <strong>Dupilumab、JAK 抑制劑、Tralokinumab 或 Lebrikizumab</strong>(Werfel 2024 S3)。'; }
      var sEl = document.getElementById('dn-scorad-score');
      var bEl = document.getElementById('dn-scorad-band');
      var iEl = document.getElementById('dn-scorad-interp');
      sEl.textContent = score.toFixed(1);
      bEl.textContent = band;
      bEl.style.background = bg;
      bEl.style.color = fg;
      iEl.innerHTML = interp;
    }
    box.querySelectorAll('input').forEach(function (i) { i.addEventListener('input', calc); });
    calc();
    if (typeof gtag === 'function') {
      try { gtag('event', 'calculator_view', { tool: 'SCORAD', page_path: location.pathname }); } catch (e) {}
    }
  };

  // SALT (Severity of Alopecia Tool)
  DN.injectSALT = function () {
    var slug = DN.currentSlug();
    if (slug !== 'alopecia-areata' && slug !== 'hairloss-myths') return;
    var anchor = document.querySelector('article.max-w-3xl');
    if (!anchor || document.getElementById('dn-salt')) return;
    DN.calcStyles();

    var box = document.createElement('section');
    box.className = 'max-w-3xl mx-auto px-5 sm:px-8 my-6';
    box.innerHTML =
      '<div class="dn-calc" id="dn-salt">' +
        '<h3 class="dn-calc-title" data-zh="SALT 計算器 — 圓禿頭皮禿髮面積" data-en="SALT Calculator — alopecia areata scalp">SALT 計算器 — 圓禿頭皮禿髮面積</h3>' +
        '<div class="dn-calc-sub" data-zh="頭皮分 4 區:頂(40%)、後(24%)、左(18%)、右(18%)。SALT = Σ(各區禿髮 % × 該區權重)。" data-en="Scalp divided into 4 zones: vertex (40%), back (24%), left (18%), right (18%). SALT = sum of each zone hair-loss % × weight.">頭皮分 4 區:頂(40%)、後(24%)、左(18%)、右(18%)。SALT = Σ(各區禿髮 % × 該區權重)。</div>' +
        '<div class="dn-calc-row"><label data-zh="頂部禿髮 %(權重 40)" data-en="Vertex (weight 40)">頂部禿髮 %<span class="dn-calc-hint">權重 0.40</span></label><input type="number" min="0" max="100" step="5" value="0" class="dn-calc-input" id="dn-salt-V" /></div>' +
        '<div class="dn-calc-row"><label data-zh="後部禿髮 %(權重 24)" data-en="Back (weight 24)">後部禿髮 %<span class="dn-calc-hint">權重 0.24</span></label><input type="number" min="0" max="100" step="5" value="0" class="dn-calc-input" id="dn-salt-B" /></div>' +
        '<div class="dn-calc-row"><label data-zh="左側禿髮 %(權重 18)" data-en="Left (weight 18)">左側禿髮 %<span class="dn-calc-hint">權重 0.18</span></label><input type="number" min="0" max="100" step="5" value="0" class="dn-calc-input" id="dn-salt-L" /></div>' +
        '<div class="dn-calc-row"><label data-zh="右側禿髮 %(權重 18)" data-en="Right (weight 18)">右側禿髮 %<span class="dn-calc-hint">權重 0.18</span></label><input type="number" min="0" max="100" step="5" value="0" class="dn-calc-input" id="dn-salt-R" /></div>' +
        '<div class="dn-calc-result">' +
          '<div><span class="dn-calc-score" id="dn-salt-score">—</span><span class="dn-calc-band" id="dn-salt-band"></span></div>' +
          '<div class="dn-calc-interp" id="dn-salt-interp"></div>' +
        '</div>' +
        '<a href="/tools#salt" class="dn-calc-tools-link" data-zh="查看完整 SALT 使用指南 →" data-en="View full SALT guide →">查看完整 SALT 使用指南 →</a>' +
        '<div class="dn-calc-disclaimer" data-zh="* SALT: Olsen EA et al, JAAD 2004. 治療決策應由皮膚科專科醫師評估。" data-en="* SALT: Olsen EA et al, JAAD 2004. Treatment decisions require dermatology evaluation.">* SALT: Olsen EA et al, JAAD 2004. 治療決策應由皮膚科專科醫師評估。</div>' +
      '</div>';
    anchor.parentNode.insertBefore(box, anchor.nextSibling);

    function calc() {
      var V = Math.max(0, Math.min(100, parseFloat(document.getElementById('dn-salt-V').value) || 0));
      var B = Math.max(0, Math.min(100, parseFloat(document.getElementById('dn-salt-B').value) || 0));
      var L = Math.max(0, Math.min(100, parseFloat(document.getElementById('dn-salt-L').value) || 0));
      var R = Math.max(0, Math.min(100, parseFloat(document.getElementById('dn-salt-R').value) || 0));
      var score = V * 0.40 + B * 0.24 + L * 0.18 + R * 0.18;
      var band, bg, fg, interp;
      if (score < 20) { band = '輕度'; bg = '#dcfce7'; fg = '#14532d'; interp = '輕度圓禿(SALT &lt; 20) — 多數可用<strong>病灶內類固醇注射 ± 外用 5% Minoxidil ± DPCP</strong>。'; }
      else if (score < 50) { band = '中度'; bg = '#fef9c3'; fg = '#854d0e'; interp = '中度圓禿(SALT 20-50)— 可考慮口服類固醇橋接、Methotrexate 或<strong>低劑量 oral Minoxidil 輔助</strong>。'; }
      else { band = '重度'; bg = '#fee2e2'; fg = '#991b1b'; interp = '重度圓禿(SALT ≥ 50)— Rudnicka 2024 EU 共識:<strong>Baricitinib(成人)或 Ritlecitinib(≥12 歲)</strong>為首選 JAK 抑制劑。'; }
      document.getElementById('dn-salt-score').textContent = score.toFixed(1);
      var bEl = document.getElementById('dn-salt-band');
      bEl.textContent = band; bEl.style.background = bg; bEl.style.color = fg;
      document.getElementById('dn-salt-interp').innerHTML = interp;
    }
    box.querySelectorAll('input').forEach(function (i) { i.addEventListener('input', calc); });
    calc();
    if (typeof gtag === 'function') {
      try { gtag('event', 'calculator_view', { tool: 'SALT', page_path: location.pathname }); } catch (e) {}
    }
  };

  // UAS7 (Urticaria Activity Score over 7 days)
  DN.injectUAS7 = function () {
    var slug = DN.currentSlug();
    if (slug !== 'urticaria-myths') return;
    var anchor = document.querySelector('article.max-w-3xl');
    if (!anchor || document.getElementById('dn-uas7')) return;
    DN.calcStyles();

    var box = document.createElement('section');
    box.className = 'max-w-3xl mx-auto px-5 sm:px-8 my-6';
    var html =
      '<div class="dn-calc" id="dn-uas7">' +
        '<h3 class="dn-calc-title" data-zh="UAS7 計算器 — 蕁麻疹活動度(過去 7 天)" data-en="UAS7 — Urticaria Activity (7 days)">UAS7 計算器 — 蕁麻疹活動度(過去 7 天)</h3>' +
        '<div class="dn-calc-sub" data-zh="每天評估「風團數」與「癢感」各 0-3 分,連續 7 天加總。最高 42 分。" data-en="Daily wheals (0-3) + itch (0-3), summed over 7 days. Max 42.">每天評估「風團數(0-3)」+「癢感(0-3)」,連續 7 天加總。最高 42 分。</div>';
    for (var i = 1; i <= 7; i++) {
      html +=
        '<div class="dn-calc-row" style="grid-template-columns:1fr auto auto;gap:12px"><label>第 ' + i + ' 天<span class="dn-calc-hint" data-zh="風團 + 癢感" data-en="Wheal + Itch">風團 + 癢感</span></label>' +
        '<input type="number" min="0" max="3" step="1" value="0" class="dn-calc-input" data-day="' + i + '" data-kind="W" placeholder="風團" />' +
        '<input type="number" min="0" max="3" step="1" value="0" class="dn-calc-input" data-day="' + i + '" data-kind="I" placeholder="癢感" /></div>';
    }
    html +=
        '<div class="dn-calc-result">' +
          '<div><span class="dn-calc-score" id="dn-uas7-score">—</span><span class="dn-calc-band" id="dn-uas7-band"></span></div>' +
          '<div class="dn-calc-interp" id="dn-uas7-interp"></div>' +
        '</div>' +
        '<a href="/tools#uas7" class="dn-calc-tools-link" data-zh="查看完整 UAS7 使用指南 →" data-en="View full UAS7 guide →">查看完整 UAS7 使用指南 →</a>' +
        '<div class="dn-calc-disclaimer" data-zh="* UAS7: EAACI/GA²LEN 2022 蕁麻疹指引;Kolkhir 2024 JAMA. 控制目標 UAS7 ≤ 6,理想 0。" data-en="* UAS7: EAACI/GA²LEN 2022 guideline. Target UAS7 ≤ 6, ideal 0.">* UAS7: EAACI/GA²LEN 2022 蕁麻疹指引;Kolkhir 2024 JAMA. 控制目標 UAS7 ≤ 6,理想 0。</div>' +
      '</div>';
    box.innerHTML = html;
    anchor.parentNode.insertBefore(box, anchor.nextSibling);

    function calc() {
      var total = 0;
      box.querySelectorAll('input').forEach(function (i) {
        var v = Math.max(0, Math.min(3, parseFloat(i.value) || 0));
        total += v;
      });
      var band, bg, fg, interp;
      if (total === 0) { band = '完全控制'; bg = '#dcfce7'; fg = '#14532d'; interp = '完全控制(UAS7 = 0)— <strong>理想治療目標</strong>已達成,維持當前治療。'; }
      else if (total <= 6) { band = '良好控制'; bg = '#dcfce7'; fg = '#14532d'; interp = '良好控制(UAS7 ≤ 6)— 維持當前治療,定期回診評估。'; }
      else if (total <= 15) { band = '輕度活動'; bg = '#fef9c3'; fg = '#854d0e'; interp = '輕度活動(UAS7 7-15)— 評估抗組織胺<strong>加量至 4 倍標準劑量</strong>。'; }
      else if (total <= 27) { band = '中度活動'; bg = '#fed7aa'; fg = '#9a3412'; interp = '中度活動(UAS7 16-27)— 高劑量抗組織胺仍無效,考慮加用 <strong>Omalizumab 300mg q4w</strong>。'; }
      else { band = '重度活動'; bg = '#fee2e2'; fg = '#991b1b'; interp = '重度活動(UAS7 ≥ 28)— 應盡快加用 <strong>Omalizumab 或 cyclosporine</strong>(EAACI 2022)。'; }
      document.getElementById('dn-uas7-score').textContent = total + ' / 42';
      var bEl = document.getElementById('dn-uas7-band');
      bEl.textContent = band; bEl.style.background = bg; bEl.style.color = fg;
      document.getElementById('dn-uas7-interp').innerHTML = interp;
    }
    box.querySelectorAll('input').forEach(function (i) { i.addEventListener('input', calc); });
    calc();
    if (typeof gtag === 'function') {
      try { gtag('event', 'calculator_view', { tool: 'UAS7', page_path: location.pathname }); } catch (e) {}
    }
  };

  // -----------------------------------------------------------------------
  // Helper: build a generic calculator with title/sub/inputs/result band
  // -----------------------------------------------------------------------
  DN._buildCalc = function (cfg) {
    DN.calcStyles();
    var anchor = document.querySelector('article.max-w-3xl');
    if (!anchor || document.getElementById(cfg.id)) return null;
    var box = document.createElement('section');
    box.className = 'max-w-3xl mx-auto px-5 sm:px-8 my-6';
    var rowsHTML = cfg.rows.map(function (r) {
      var hint = r.hint ? '<span class="dn-calc-hint">' + r.hint + '</span>' : '';
      if (r.type === 'number') {
        return '<div class="dn-calc-row"><label>' + r.label + hint + '</label>' +
          '<input type="number" min="' + (r.min||0) + '" max="' + (r.max||100) + '" step="' + (r.step||1) + '" value="' + (r.def||0) + '" class="dn-calc-input" data-key="' + r.key + '" /></div>';
      } else if (r.type === 'select') {
        var opts = r.options.map(function (o) { return '<option value="' + o.v + '">' + o.label + '</option>'; }).join('');
        return '<div class="dn-calc-row"><label>' + r.label + hint + '</label>' +
          '<select class="dn-calc-input" data-key="' + r.key + '" style="width:auto;min-width:140px">' + opts + '</select></div>';
      }
      return '';
    }).join('');
    box.innerHTML =
      '<div class="dn-calc" id="' + cfg.id + '">' +
        '<h3 class="dn-calc-title">' + cfg.title + '</h3>' +
        '<div class="dn-calc-sub">' + cfg.sub + '</div>' +
        rowsHTML +
        '<div class="dn-calc-result">' +
          '<div><span class="dn-calc-score" data-result="score">—</span><span class="dn-calc-band" data-result="band"></span></div>' +
          '<div class="dn-calc-interp" data-result="interp"></div>' +
        '</div>' +
        (cfg.toolsAnchor ? '<a href="/tools#' + cfg.toolsAnchor + '" class="dn-calc-tools-link">查看完整 ' + cfg.tool + ' 使用指南 →</a>' : '') +
        '<div class="dn-calc-disclaimer">' + cfg.disclaimer + '</div>' +
      '</div>';
    anchor.parentNode.insertBefore(box, anchor.nextSibling);
    function readVals() {
      var v = {};
      box.querySelectorAll('[data-key]').forEach(function (el) {
        v[el.dataset.key] = el.tagName === 'SELECT' ? el.value : (parseFloat(el.value) || 0);
      });
      return v;
    }
    function update() {
      var r = cfg.calc(readVals());
      box.querySelector('[data-result="score"]').textContent = r.score;
      var bEl = box.querySelector('[data-result="band"]');
      bEl.textContent = r.band;
      bEl.style.background = r.bg;
      bEl.style.color = r.fg;
      box.querySelector('[data-result="interp"]').innerHTML = r.interp;
    }
    box.querySelectorAll('[data-key]').forEach(function (el) { el.addEventListener('input', update); el.addEventListener('change', update); });
    update();
    if (typeof gtag === 'function') {
      try { gtag('event', 'calculator_view', { tool: cfg.tool, page_path: location.pathname }); } catch (e) {}
    }
    return box;
  };

  // PASI (Psoriasis Area Severity Index, 0-72) — psoriasis-myths
  DN.injectPASI = function () {
    if (DN.currentSlug() !== 'psoriasis-myths') return;
    var rows = [];
    [['頭頸 (×0.1)','head'],['上肢 (×0.2)','arm'],['軀幹 (×0.3)','trunk'],['下肢 (×0.4)','leg']].forEach(function (r) {
      rows.push({ type:'number', label: r[0]+' · 紅斑 E (0-4)',  hint:'erythema',     key:r[1]+'_E', min:0, max:4, def:0 });
      rows.push({ type:'number', label: r[0]+' · 浸潤 I (0-4)',  hint:'infiltration', key:r[1]+'_I', min:0, max:4, def:0 });
      rows.push({ type:'number', label: r[0]+' · 鱗屑 D (0-4)',  hint:'desquamation', key:r[1]+'_D', min:0, max:4, def:0 });
      rows.push({ type:'number', label: r[0]+' · 面積 A (0-6)',  hint:'0=0% / 6=90-100%', key:r[1]+'_A', min:0, max:6, def:0 });
    });
    DN._buildCalc({
      id: 'dn-pasi', tool: 'PASI', toolsAnchor: 'pasi',
      title: 'PASI 計算器 — 乾癬嚴重度',
      sub: 'PASI = 0.1×(Eh+Ih+Dh)×Ah + 0.2×(Ea+Ia+Da)×Aa + 0.3×(Et+It+Dt)×At + 0.4×(El+Il+Dl)×Al。最高 72 分。',
      rows: rows,
      calc: function (v) {
        var head = (v.head_E + v.head_I + v.head_D) * v.head_A * 0.1;
        var arm  = (v.arm_E + v.arm_I + v.arm_D) * v.arm_A * 0.2;
        var trunk= (v.trunk_E + v.trunk_I + v.trunk_D) * v.trunk_A * 0.3;
        var leg  = (v.leg_E + v.leg_I + v.leg_D) * v.leg_A * 0.4;
        var s = head + arm + trunk + leg;
        var band, bg, fg, interp;
        if (s < 5) { band='輕度'; bg='#dcfce7'; fg='#14532d'; interp='輕度乾癬(PASI &lt; 5) — 通常以<strong>外用治療</strong>(Daivobet、Calcipotriol、外用類固醇)即可。'; }
        else if (s < 10) { band='中度'; bg='#fef9c3'; fg='#854d0e'; interp='中度乾癬(PASI 5-10) — 加 <strong>NB-UVB 光療 / Acitretin / Methotrexate</strong>;準備生物製劑申請條件。'; }
        else if (s < 20) { band='中重度'; bg='#fed7aa'; fg='#9a3412'; interp='中重度(PASI 10-20) — <strong>健保生物製劑可申請</strong>(IL-17/23 inhibitor),需 PASI ≥ 10 + 兩線傳統治療失敗。'; }
        else { band='重度'; bg='#fee2e2'; fg='#991b1b'; interp='重度(PASI ≥ 20) — 生物製劑優先;<strong>Bimekizumab / Risankizumab / Guselkumab</strong> 三線最強;考慮乾癬性關節炎共病評估。'; }
        return { score: s.toFixed(1), band: band, bg: bg, fg: fg, interp: interp };
      },
      disclaimer: '* PASI: Fredriksson &amp; Pettersson 1978;台灣健保生物製劑申請門檻 PASI ≥ 10 / BSA ≥ 10% / DLQI ≥ 10 + 兩線失敗。'
    });
  };

  // DLQI (Dermatology Life Quality Index, 0-30) — multi-article
  DN.injectDLQI = function () {
    var slug = DN.currentSlug();
    if (!['eczema-myths','psoriasis-myths','urticaria-myths','alopecia-areata','vitiligo','hidradenitis-suppurativa','prurigo-nodularis'].includes(slug)) return;
    var rows = [];
    var qs = [
      '過去 1 週,皮膚<strong>癢、痠痛、刺痛</strong>的程度?',
      '過去 1 週,因皮膚問題<strong>感到困窘、自卑、難為情</strong>的程度?',
      '過去 1 週,皮膚問題影響<strong>購物、家務、整理花園</strong>?',
      '過去 1 週,皮膚問題影響<strong>穿著選擇</strong>?',
      '過去 1 週,皮膚問題影響<strong>社交活動或休閒</strong>?',
      '過去 1 週,皮膚問題影響<strong>運動</strong>?',
      '過去 1 週,皮膚問題使您<strong>無法工作或念書</strong>?',
      '過去 1 週,皮膚問題對您與<strong>伴侶 / 親近的朋友 / 家人</strong>關係的影響?',
      '過去 1 週,皮膚問題對您<strong>性生活</strong>的影響?',
      '過去 1 週,皮膚<strong>治療</strong>對日常生活造成困擾(如花時間、弄髒衣物)?'
    ];
    qs.forEach(function (q, i) {
      rows.push({ type:'select', label: 'Q'+(i+1)+': '+q, key:'q'+(i+1), options:[
        {v:0,label:'0 完全沒有'},{v:1,label:'1 一點點'},{v:2,label:'2 中等'},{v:3,label:'3 非常'}
      ] });
    });
    DN._buildCalc({
      id: 'dn-dlqi', tool: 'DLQI', toolsAnchor: 'dlqi',
      title: 'DLQI 計算器 — 皮膚病生活品質量表(過去 7 天)',
      sub: '10 題自評,每題 0-3 分,總分 0-30。生物製劑健保申請常見門檻 DLQI ≥ 10。',
      rows: rows,
      calc: function (v) {
        var s = 0;
        for (var i = 1; i <= 10; i++) s += parseFloat(v['q'+i]) || 0;
        var band, bg, fg, interp;
        if (s <= 1) { band='無影響'; bg='#dcfce7'; fg='#14532d'; interp='皮膚病對生活品質<strong>無影響</strong>(DLQI 0-1)。'; }
        else if (s <= 5) { band='輕度影響'; bg='#dcfce7'; fg='#14532d'; interp='輕度影響(DLQI 2-5)— 一般治療即可。'; }
        else if (s <= 10) { band='中度影響'; bg='#fef9c3'; fg='#854d0e'; interp='中度影響(DLQI 6-10) — 應與醫師討論升階治療。'; }
        else if (s <= 20) { band='重度影響'; bg='#fed7aa'; fg='#9a3412'; interp='重度影響(DLQI 11-20) — <strong>達生物製劑健保申請門檻</strong>(配合疾病活動度)。'; }
        else { band='極重度'; bg='#fee2e2'; fg='#991b1b'; interp='極重度影響(DLQI ≥ 21) — 生物製劑優先;同時建議<strong>心理共病評估</strong>(PHQ-9/GAD-7)。'; }
        return { score: s + ' / 30', band: band, bg: bg, fg: fg, interp: interp };
      },
      disclaimer: '* DLQI: Finlay &amp; Khan 1994;台灣健保生物製劑申請常見門檻 DLQI ≥ 10。本工具僅作病人自評,不取代專科診斷。'
    });
  };

  // Hurley Stage (HS) — hidradenitis-suppurativa
  DN.injectHurley = function () {
    if (DN.currentSlug() !== 'hidradenitis-suppurativa') return;
    DN._buildCalc({
      id: 'dn-hurley', tool: 'Hurley', toolsAnchor: 'hurley',
      title: 'Hurley 分期 — 化膿性汗腺炎(HS)嚴重度',
      sub: '化膿性汗腺炎臨床上最常用的分期。請選擇最符合您病情的描述。',
      rows: [{ type:'select', label:'目前狀態', key:'stage', options:[
        {v:1,label:'Stage I — 單一或多個獨立膿瘍/結節,無通道、無疤痕'},
        {v:2,label:'Stage II — 反覆膿瘍,形成通道與疤痕,但病灶獨立分隔'},
        {v:3,label:'Stage III — 多個互相連結的通道與膿瘍,大面積疤痕'}
      ] }],
      calc: function (v) {
        var s = parseInt(v.stage) || 1;
        var band, bg, fg, interp;
        if (s === 1) { band='輕度'; bg='#dcfce7'; fg='#14532d'; interp='Stage I — <strong>外用 Clindamycin + 短期口服抗生素</strong>(Doxycycline 50-100 mg BID × 12 週);生活調整(減重、戒菸、寬鬆衣物);切開引流。'; }
        else if (s === 2) { band='中度'; bg='#fef9c3'; fg='#854d0e'; interp='Stage II — <strong>長期口服 Clindamycin + Rifampicin</strong>;Acitretin / 抗雄激素藥;<strong>生物製劑 Adalimumab(已健保條件給付)</strong>;局部 deroofing 手術。'; }
        else { band='重度'; bg='#fee2e2'; fg='#991b1b'; interp='Stage III — <strong>Adalimumab</strong> + 廣泛切除手術 + 皮瓣重建;<strong>Secukinumab(2023 FDA 核准)</strong>為新選項。'; }
        return { score: 'Stage ' + s, band: band, bg: bg, fg: fg, interp: interp };
      },
      disclaimer: '* Hurley 1989;TDA HS 共識;Adalimumab 健保適應症需 Hurley II/III + DLQI ≥ 10 + 兩線傳統治療失敗。'
    });
  };

  // Norwood-Hamilton (Male Pattern Baldness) + Ludwig (Female) — hairloss-myths
  DN.injectHairScale = function () {
    if (DN.currentSlug() !== 'hairloss-myths') return;
    DN._buildCalc({
      id: 'dn-hair-scale', tool: 'Norwood-Ludwig', toolsAnchor: 'norwood',
      title: 'Norwood-Hamilton (男性) / Ludwig (女性) 雄性禿分級',
      sub: '雄性禿臨床分級。男性使用 Norwood-Hamilton,女性使用 Ludwig。',
      rows: [
        { type:'select', label:'性別', key:'sex', options:[
          {v:'M',label:'男性 → Norwood-Hamilton'},
          {v:'F',label:'女性 → Ludwig'}
        ]},
        { type:'select', label:'目前髮量狀態', key:'stage', options:[
          {v:1,label:'I — 正常,無明顯禿髮'},
          {v:2,label:'II — 輕度髮際線後退(M 型微微)'},
          {v:3,label:'III — 明顯 M 型禿 / 頭頂稍稀'},
          {v:4,label:'IV — 髮際線顯著後退 + 頭頂禿髮'},
          {v:5,label:'V — 大面積頭頂禿,僅後方環狀剩餘'},
          {v:6,label:'VI — 頭頂與前方禿髮融合'},
          {v:7,label:'VII — 僅後枕部 / 兩側馬蹄形剩餘'}
        ]}
      ],
      calc: function (v) {
        var s = parseInt(v.stage) || 1;
        var sex = v.sex || 'M';
        var scaleName = sex === 'M' ? 'Norwood ' : 'Ludwig ';
        var roman = ['I','II','III','IV','V','VI','VII'];
        var band, bg, fg, interp;
        if (s <= 2) { band='輕度'; bg='#dcfce7'; fg='#14532d';
          interp = sex === 'M'
            ? '輕度雄性禿 — <strong>外用 Minoxidil 5%</strong>(每日 2 次)± <strong>口服 Finasteride 1 mg/day</strong>(需專科處方);生活型態調整。'
            : '輕度女性禿 — <strong>外用 Minoxidil 2-5%</strong>(每日 1-2 次);<strong>低劑量口服 Minoxidil 0.5-1.25 mg/day</strong>(Olsen 2025);Spironolactone 100 mg。';
        }
        else if (s <= 4) { band='中度'; bg='#fef9c3'; fg='#854d0e';
          interp = sex === 'M'
            ? '中度 — <strong>Finasteride 1 mg/day + Minoxidil 5%</strong> 雙標準;考慮 PRP 注射;規劃植髮諮詢。'
            : '中度 — Minoxidil + Spironolactone 為主軸;考慮 <strong>低劑量 oral Minoxidil</strong> 與 PRP。';
        }
        else { band='重度'; bg='#fee2e2'; fg='#991b1b';
          interp = '重度 — <strong>需植髮搭配藥物維持</strong>(FUE / FUT);Finasteride / Minoxidil 必須持續以避免後方續發禿髮。';
        }
        return { score: scaleName + roman[s-1], band: band, bg: bg, fg: fg, interp: interp };
      },
      disclaimer: '* Norwood 1975 / Ludwig 1977;Olsen 2025 JAAD LDOM 共識;治療需專科醫師個別評估。'
    });
  };

  // Fitzpatrick Skin Type (I-VI) — sunscreen-myths
  DN.injectFitzpatrick = function () {
    if (DN.currentSlug() !== 'sunscreen-myths' && DN.currentSlug() !== 'melasma-myths') return;
    DN._buildCalc({
      id: 'dn-fitzpatrick', tool: 'Fitzpatrick', toolsAnchor: 'fitzpatrick',
      title: 'Fitzpatrick 膚色分型 — 防曬 / 雷射安全參考',
      sub: '依您未曬太陽的皮膚顏色 + 曬太陽 1 小時(初夏中午)後的反應分類。',
      rows: [
        { type:'select', label:'未曬太陽時皮膚', key:'base', options:[
          {v:1,label:'極白(蒼白、雀斑多)'},
          {v:2,label:'白(輕度雀斑)'},
          {v:3,label:'白偏黃 / 米白'},
          {v:4,label:'淺褐 / 偏深'},
          {v:5,label:'褐色(東南亞、拉丁)'},
          {v:6,label:'深褐 / 黑色(非裔)'}
        ]},
        { type:'select', label:'曬太陽 1 小時後反應', key:'sun', options:[
          {v:1,label:'總是曬傷,從不曬黑'},
          {v:2,label:'容易曬傷,輕微曬黑'},
          {v:3,label:'有時曬傷,逐漸曬黑'},
          {v:4,label:'很少曬傷,容易曬黑'},
          {v:5,label:'幾乎不曬傷,深度曬黑'},
          {v:6,label:'從不曬傷'}
        ]}
      ],
      calc: function (v) {
        var b = parseInt(v.base) || 1;
        var s = parseInt(v.sun) || 1;
        var t = Math.round((b + s) / 2);
        var roman = ['I','II','III','IV','V','VI'];
        var band, bg, fg, interp;
        if (t <= 2) { band='I-II 型'; bg='#fee2e2'; fg='#991b1b'; interp='淺膚色 — <strong>每天 SPF 50+、PA++++ 強烈建議</strong>;高風險皮膚癌族群,建議定期皮膚科自我檢查 ABCDE。'; }
        else if (t <= 4) { band='III-IV 型'; bg='#fef9c3'; fg='#854d0e'; interp='中等膚色(亞洲多數人)— <strong>SPF 30-50、PA+++</strong>;雷射 / 化學換膚後容易反黑,需嚴格防曬 4 週以上。'; }
        else { band='V-VI 型'; bg='#dcfce7'; fg='#14532d'; interp='深膚色 — <strong>仍需 SPF 30+ 防曬</strong>(避免 PIH 反黑);1064 nm Nd:YAG 為較安全雷射選擇;532/694/755 nm 易引起色素沉著。'; }
        return { score: 'Type ' + roman[t-1], band: band, bg: bg, fg: fg, interp: interp };
      },
      disclaimer: '* Fitzpatrick 1975;膚色分型主要用於評估光療 / 雷射 / 防曬需求,不代表絕對皮膚癌風險。'
    });
  };

  // GAGS (Global Acne Grading System, 0-44) — acne-myths
  DN.injectGAGS = function () {
    if (DN.currentSlug() !== 'acne-myths') return;
    var sites = [
      ['前額(×2)','forehead'], ['右臉頰(×2)','rcheek'], ['左臉頰(×2)','lcheek'],
      ['鼻部(×1)','nose'], ['下巴(×1)','chin'], ['胸 / 上背(×3)','chest']
    ];
    var rows = sites.map(function (sit) {
      return { type:'select', label: sit[0], key: sit[1], options:[
        {v:0,label:'0 無病灶'},
        {v:1,label:'1 ≥1 個粉刺'},
        {v:2,label:'2 ≥1 個丘疹'},
        {v:3,label:'3 ≥1 個膿皰'},
        {v:4,label:'4 ≥1 個結節'}
      ]};
    });
    DN._buildCalc({
      id: 'dn-gags', tool: 'GAGS', toolsAnchor: 'gags',
      title: 'GAGS 計算器 — 痘痘嚴重度',
      sub: 'GAGS = Σ(部位最嚴重病灶 × 部位權重)。前額 / 兩頰 ×2,鼻 / 下巴 ×1,胸背 ×3。最高 44。',
      rows: rows,
      calc: function (v) {
        var s = (parseInt(v.forehead)||0)*2 + (parseInt(v.rcheek)||0)*2 + (parseInt(v.lcheek)||0)*2 +
                (parseInt(v.nose)||0)*1 + (parseInt(v.chin)||0)*1 + (parseInt(v.chest)||0)*3;
        var band, bg, fg, interp;
        if (s === 0) { band='無'; bg='#dcfce7'; fg='#14532d'; interp='目前無痘痘 — 維持規律保養與防曬。'; }
        else if (s <= 18) { band='輕度'; bg='#dcfce7'; fg='#14532d'; interp='輕度(GAGS 1-18) — 外用 BPO + retinoid 為主(2024 AAD 強建議);可選用 Adapalene + BPO 固定複方。'; }
        else if (s <= 30) { band='中度'; bg='#fef9c3'; fg='#854d0e'; interp='中度(GAGS 19-30) — 加口服 Doxycycline 100 mg BID × 8-12 週;考慮 oral 避孕藥 / Spironolactone(女性);Clascoterone 外用為新選項。'; }
        else if (s <= 38) { band='重度'; bg='#fed7aa'; fg='#9a3412'; interp='重度(GAGS 31-38) — <strong>口服 Isotretinoin 為首選</strong>(健保條件:重度發炎或標準治療失敗)。'; }
        else { band='極重度'; bg='#fee2e2'; fg='#991b1b'; interp='極重度(GAGS ≥ 39) — Isotretinoin 必要 + 病灶內類固醇 + 早期介入避免疤痕。'; }
        return { score: s + ' / 44', band: band, bg: bg, fg: fg, interp: interp };
      },
      disclaimer: '* Doshi-Zaheer-Stiller 1997 GAGS。AAD 2024 (Reynolds) 痘痘指引。'
    });
  };

  // MASI (Melasma Area Severity Index, 0-48) — melasma-myths
  DN.injectMASI = function () {
    if (DN.currentSlug() !== 'melasma-myths') return;
    var sites = [
      ['前額(×0.3)','forehead'],
      ['右臉頰(×0.3)','rcheek'],
      ['左臉頰(×0.3)','lcheek'],
      ['下巴(×0.1)','chin']
    ];
    var rows = [];
    sites.forEach(function (sit) {
      rows.push({ type:'number', label: sit[0]+' · 面積 A (0-6)', hint:'0=0% / 6=90-100%', key:sit[1]+'_A', min:0, max:6, def:0 });
      rows.push({ type:'number', label: sit[0]+' · 深淺 D (0-4)', hint:'darkness',           key:sit[1]+'_D', min:0, max:4, def:0 });
      rows.push({ type:'number', label: sit[0]+' · 同質性 H (0-4)', hint:'homogeneity',     key:sit[1]+'_H', min:0, max:4, def:0 });
    });
    DN._buildCalc({
      id: 'dn-masi', tool: 'MASI', toolsAnchor: 'masi',
      title: 'MASI 計算器 — 肝斑嚴重度',
      sub: 'MASI = 0.3×Af×(Df+Hf) + 0.3×Ar×(Dr+Hr) + 0.3×Al×(Dl+Hl) + 0.1×Ac×(Dc+Hc)。最高 48。',
      rows: rows,
      calc: function (v) {
        var fh = 0.3 * v.forehead_A * (v.forehead_D + v.forehead_H);
        var rc = 0.3 * v.rcheek_A * (v.rcheek_D + v.rcheek_H);
        var lc = 0.3 * v.lcheek_A * (v.lcheek_D + v.lcheek_H);
        var ch = 0.1 * v.chin_A * (v.chin_D + v.chin_H);
        var s = fh + rc + lc + ch;
        var band, bg, fg, interp;
        if (s < 8) { band='輕度'; bg='#dcfce7'; fg='#14532d'; interp='輕度肝斑 — <strong>嚴格防曬(SPF 50+ 含氧化鐵)+ Azelaic acid 15-20% / Niacinamide</strong>。'; }
        else if (s < 24) { band='中度'; bg='#fef9c3'; fg='#854d0e'; interp='中度肝斑 — <strong>Tri-Luma(對苯二酚 4% + Tretinoin + Fluocinolone)8-12 週</strong> + 維持治療;考慮口服 Tranexamic acid。'; }
        else { band='重度'; bg='#fee2e2'; fg='#991b1b'; interp='重度肝斑 — 多管道治療:Tri-Luma + 口服 TXA + 低能量 Q-switched 1064 nm toning;<strong>Cysteamine 5% (Lima 2020)</strong>為新選項。'; }
        return { score: s.toFixed(1), band: band, bg: bg, fg: fg, interp: interp };
      },
      disclaimer: '* Kimbrough-Green 1994;Cysteamine: Lima IJD 2020。Tri-Luma 連續使用 ≤ 12 週後改維持治療。'
    });
  };

  // POEM (Patient-Oriented Eczema Measure, 0-28) — eczema-myths
  DN.injectPOEM = function () {
    var slug = DN.currentSlug();
    if (slug !== 'eczema-myths' && slug !== 'pediatric-eczema') return;
    var qs = [
      'Q1 · 過去 1 週,皮膚<strong>癢</strong>幾天?',
      'Q2 · 過去 1 週,皮膚<strong>讓您睡不好</strong>幾天?',
      'Q3 · 過去 1 週,皮膚有<strong>滲血</strong>幾天?',
      'Q4 · 過去 1 週,皮膚<strong>滲出組織液</strong>幾天?',
      'Q5 · 過去 1 週,皮膚<strong>裂開</strong>幾天?',
      'Q6 · 過去 1 週,皮膚<strong>剝落</strong>幾天?',
      'Q7 · 過去 1 週,皮膚<strong>感覺乾燥或粗糙</strong>幾天?'
    ];
    var rows = qs.map(function (q, i) {
      return { type:'select', label: q, key:'q'+(i+1), options:[
        {v:0,label:'0 天'},{v:1,label:'1-2 天'},{v:2,label:'3-4 天'},{v:3,label:'5-6 天'},{v:4,label:'每天'}
      ] };
    });
    DN._buildCalc({
      id: 'dn-poem', tool: 'POEM', toolsAnchor: 'poem',
      title: 'POEM 計算器 — 異位性皮膚炎病人主觀評估(過去 7 天)',
      sub: 'POEM 是 7 題病人自評(每題 0-4),總分 0-28。最常用於異膚生活影響追蹤,優於 SCORAD 之處在於完全由病人自評。',
      rows: rows,
      calc: function (v) {
        var s = 0;
        for (var i = 1; i <= 7; i++) s += parseFloat(v['q'+i]) || 0;
        var band, bg, fg, interp;
        if (s <= 2) { band='清除 / 接近清除'; bg='#dcfce7'; fg='#14532d'; interp='疾病幾乎完全控制(POEM 0-2)— 維持目前保濕 + 主動式治療即可。'; }
        else if (s <= 7) { band='輕度'; bg='#dcfce7'; fg='#14532d'; interp='輕度異膚(POEM 3-7)— 外用類固醇 + TCI 即可控制。'; }
        else if (s <= 16) { band='中度'; bg='#fef9c3'; fg='#854d0e'; interp='中度(POEM 8-16)— 加 NB-UVB 光療、Proactive therapy 主動式維持。'; }
        else if (s <= 24) { band='重度'; bg='#fed7aa'; fg='#9a3412'; interp='重度(POEM 17-24)— 評估生物製劑(Dupilumab、JAK 抑制劑)健保申請。'; }
        else { band='極重度'; bg='#fee2e2'; fg='#991b1b'; interp='極重度(POEM 25-28)— Dupilumab / JAK 抑制劑優先,可考慮短期 cyclosporine 橋接。'; }
        return { score: s + ' / 28', band: band, bg: bg, fg: fg, interp: interp };
      },
      disclaimer: '* POEM: Charman CR et al, Arch Dermatol 2004. POEM-50 / POEM-90 = 治療後降幅,代表臨床顯著反應。'
    });
  };

  // IHS4 (International Hidradenitis Suppurativa Severity Score System) — HS
  DN.injectIHS4 = function () {
    if (DN.currentSlug() !== 'hidradenitis-suppurativa') return;
    DN._buildCalc({
      id: 'dn-ihs4', tool: 'IHS4', toolsAnchor: 'ihs4',
      title: 'IHS4 計算器 — 化膿性汗腺炎活動度評估',
      sub: 'IHS4 = 結節數 + (膿瘍數 × 2) + (引流通道 × 4)。優於 Hurley 之處在於追蹤活動度而非結構性損傷。',
      rows: [
        { type:'number', label:'結節(nodule)總數', hint:'未感染之硬結節', key:'nodule', min:0, max:50, def:0 },
        { type:'number', label:'膿瘍(abscess)總數', hint:'紅腫熱痛的化膿病灶', key:'abscess', min:0, max:50, def:0 },
        { type:'number', label:'引流通道(draining tunnel)總數', hint:'有膿水滲出的瘺管', key:'tunnel', min:0, max:30, def:0 }
      ],
      calc: function (v) {
        var s = (v.nodule || 0) + (v.abscess || 0) * 2 + (v.tunnel || 0) * 4;
        var band, bg, fg, interp;
        if (s <= 3) { band='輕度'; bg='#dcfce7'; fg='#14532d'; interp='輕度活動(IHS4 ≤ 3)— 外用 Clindamycin + 短期口服抗生素。'; }
        else if (s <= 10) { band='中度'; bg='#fef9c3'; fg='#854d0e'; interp='中度(IHS4 4-10)— 長期口服 Clindamycin + Rifampicin;考慮 Adalimumab(健保條件)。'; }
        else { band='重度'; bg='#fee2e2'; fg='#991b1b'; interp='重度(IHS4 ≥ 11)— Adalimumab + 廣泛切除手術;<strong>Secukinumab(2023 FDA)</strong>為新選項。'; }
        return { score: s + ' 分', band: band, bg: bg, fg: fg, interp: interp };
      },
      disclaimer: '* IHS4: Zouboulis CC et al, Br J Dermatol 2017. HiSCR(降幅 ≥ 50% 且通道未增加)是試驗反應指標。'
    });
  };

  // NAPSI (Nail Psoriasis Severity Index, 0-32) — psoriasis-myths
  DN.injectNAPSI = function () {
    if (DN.currentSlug() !== 'psoriasis-myths') return;
    var rows = [
      { type:'number', label:'指甲基質(matrix)病灶象限數', hint:'點狀凹陷 / 縱向溝紋 / 紅斑 / 白斑;0-4 象限', key:'matrix', min:0, max:4, def:0 },
      { type:'number', label:'指甲床(bed)病灶象限數', hint:'油滴徵 / 甲下角化 / 甲剝離 / 線狀出血;0-4 象限', key:'bed', min:0, max:4, def:0 }
    ];
    DN._buildCalc({
      id: 'dn-napsi', tool: 'NAPSI', toolsAnchor: 'napsi',
      title: 'NAPSI 計算器 — 指甲乾癬嚴重度(單一手指評估)',
      sub: '單一指甲分基質 + 甲床各 4 象限,總分 0-8。十指 / 十趾累計可達 0-160(常用單指或代表指)。',
      rows: rows,
      calc: function (v) {
        var s = (parseInt(v.matrix) || 0) + (parseInt(v.bed) || 0);
        var band, bg, fg, interp;
        if (s === 0) { band='無病灶'; bg='#dcfce7'; fg='#14532d'; interp='本指甲無乾癬病灶。'; }
        else if (s <= 3) { band='輕度'; bg='#dcfce7'; fg='#14532d'; interp='輕度指甲乾癬(NAPSI 1-3)— 外用 Calcipotriol / Clobetasol 6 個月以上。'; }
        else if (s <= 5) { band='中度'; bg='#fef9c3'; fg='#854d0e'; interp='中度(NAPSI 4-5)— 加病灶內類固醇注射 0.5-1 ml;考慮口服 Methotrexate / Acitretin。'; }
        else { band='重度'; bg='#fee2e2'; fg='#991b1b'; interp='重度(NAPSI 6-8)— 全身性治療(Methotrexate、Apremilast)或<strong>生物製劑</strong>對指甲乾癬效果最好(IL-17、IL-23 系列)。'; }
        return { score: s + ' / 8', band: band, bg: bg, fg: fg, interp: interp };
      },
      disclaimer: '* NAPSI: Rich P, Scher RK, JAAD 2003. 指甲乾癬常合併乾癬性關節炎,應評估關節症狀。'
    });
  };

  // PHQ-9 (Patient Health Questionnaire) — psych comorbidity for chronic skin disease
  DN.injectPHQ9 = function () {
    var slug = DN.currentSlug();
    // Show on chronic skin diseases with high psych comorbidity
    if (!['eczema-myths','psoriasis-myths','urticaria-myths','alopecia-areata','vitiligo','hidradenitis-suppurativa','prurigo-nodularis','acne-myths','melasma-myths'].includes(slug)) return;
    var qs = [
      'Q1 · 對事情興趣減少 / 提不起勁',
      'Q2 · 心情低落、沮喪、絕望',
      'Q3 · 入睡困難 / 醒太早 / 睡眠太多',
      'Q4 · 疲倦、覺得沒精力',
      'Q5 · 食慾差或暴食',
      'Q6 · 對自己感到失望、覺得是失敗者',
      'Q7 · 注意力難集中(看書 / 看電視)',
      'Q8 · 動作或說話<strong>慢到別人察覺</strong>;反過來焦躁不安、坐立難安',
      'Q9 · 覺得自己活著很糟糕,或想傷害自己'
    ];
    var rows = qs.map(function (q, i) {
      return { type:'select', label: q, key:'q'+(i+1), options:[
        {v:0,label:'0 完全沒有'},{v:1,label:'1 幾天'},{v:2,label:'2 一半以上的天數'},{v:3,label:'3 幾乎每天'}
      ]};
    });
    DN._buildCalc({
      id: 'dn-phq9', tool: 'PHQ-9', toolsAnchor: 'phq9',
      title: 'PHQ-9 計算器 — 憂鬱症篩檢(過去 2 週)',
      sub: '慢性皮膚病(乾癬、異膚、CSU、結節性癢疹)病人合併憂鬱比率高達 20-30%。本量表為國際標準篩檢,9 題自評,0-27 分。',
      rows: rows,
      calc: function (v) {
        var s = 0;
        for (var i = 1; i <= 9; i++) s += parseFloat(v['q'+i]) || 0;
        var q9 = parseFloat(v.q9) || 0;
        var band, bg, fg, interp;
        if (s <= 4) { band='正常'; bg='#dcfce7'; fg='#14532d'; interp='憂鬱症狀少(0-4)— 維持規律生活、運動、睡眠。'; }
        else if (s <= 9) { band='輕度'; bg='#fef9c3'; fg='#854d0e'; interp='輕度憂鬱(5-9)— 觀察 1-2 週,持續可考慮諮商。'; }
        else if (s <= 14) { band='中度'; bg='#fed7aa'; fg='#9a3412'; interp='中度憂鬱(10-14)— <strong>建議家醫科或精神科評估</strong>。皮膚問題與情緒相互影響,治療皮膚同時請考慮諮商。'; }
        else if (s <= 19) { band='中重度'; bg='#fee2e2'; fg='#991b1b'; interp='中重度憂鬱(15-19)— <strong>應盡快就醫</strong>。皮膚科 + 精神科同步評估常更有效。'; }
        else { band='重度'; bg='#fee2e2'; fg='#991b1b'; interp='重度憂鬱(20-27)— <strong>請務必盡快就醫</strong>。'; }
        if (q9 >= 1) interp += '<br/><strong style="color:#991b1b">⚠ 您回答 Q9 自傷想法 ≥ 1,強烈建議立即就醫;若有自殺念頭,請撥打 安心專線 1925(依舊愛我)或 生命線 1995。</strong>';
        return { score: s + ' / 27', band: band, bg: bg, fg: fg, interp: interp };
      },
      disclaimer: '* PHQ-9: Kroenke K, Spitzer RL, Williams JBW, J Gen Intern Med 2001;繁中翻譯:中華民國臨床心理師公會 2016。本工具為篩檢非診斷,正式診斷需精神科醫師評估。'
    });
  };

  // EASI (Eczema Area & Severity Index, 0-72) — alternative to SCORAD
  DN.injectEASI = function () {
    var slug = DN.currentSlug();
    if (slug !== 'eczema-myths' && slug !== 'pediatric-eczema') return;
    var sites = [
      ['頭頸 (×0.1 成人 / ×0.2 兒童)','head', 0.1],
      ['上肢 (×0.2)','arm', 0.2],
      ['軀幹 (×0.3)','trunk', 0.3],
      ['下肢 (×0.4 成人 / ×0.4 兒童)','leg', 0.4]
    ];
    var rows = [];
    sites.forEach(function (sit) {
      rows.push({ type:'number', label: sit[0]+' · 紅斑 E (0-3)',  hint:'erythema',     key:sit[1]+'_E', min:0, max:3, def:0 });
      rows.push({ type:'number', label: sit[0]+' · 浸潤 I (0-3)',  hint:'infiltration', key:sit[1]+'_I', min:0, max:3, def:0 });
      rows.push({ type:'number', label: sit[0]+' · 抓痕 X (0-3)',  hint:'excoriation',  key:sit[1]+'_X', min:0, max:3, def:0 });
      rows.push({ type:'number', label: sit[0]+' · 苔癬化 L (0-3)',hint:'lichenification', key:sit[1]+'_L', min:0, max:3, def:0 });
      rows.push({ type:'number', label: sit[0]+' · 面積 A (0-6)', hint:'0=0% / 6=90-100%', key:sit[1]+'_A', min:0, max:6, def:0 });
    });
    DN._buildCalc({
      id: 'dn-easi', tool: 'EASI', toolsAnchor: 'easi',
      title: 'EASI 計算器 — 異膚另一標準量表(成人)',
      sub: 'EASI = Σ(部位症狀總分 × 面積 × 部位權重)。最高 72 分。試驗常用 EASI 75 / 90 為反應指標。',
      rows: rows,
      calc: function (v) {
        var head  = (v.head_E + v.head_I + v.head_X + v.head_L) * v.head_A * 0.1;
        var arm   = (v.arm_E + v.arm_I + v.arm_X + v.arm_L) * v.arm_A * 0.2;
        var trunk = (v.trunk_E + v.trunk_I + v.trunk_X + v.trunk_L) * v.trunk_A * 0.3;
        var leg   = (v.leg_E + v.leg_I + v.leg_X + v.leg_L) * v.leg_A * 0.4;
        var s = head + arm + trunk + leg;
        var band, bg, fg, interp;
        if (s < 1.1) { band='清除'; bg='#dcfce7'; fg='#14532d'; interp='幾乎清除(EASI &lt; 1.1)— 維持治療。'; }
        else if (s <= 7) { band='輕度'; bg='#dcfce7'; fg='#14532d'; interp='輕度(EASI 1.1-7)— 外用類固醇 + TCI。'; }
        else if (s <= 21) { band='中度'; bg='#fef9c3'; fg='#854d0e'; interp='中度(EASI 7.1-21)— 加 NB-UVB / Proactive therapy。'; }
        else if (s <= 50) { band='重度'; bg='#fed7aa'; fg='#9a3412'; interp='重度(EASI 21.1-50)— <strong>達生物製劑健保申請門檻</strong>(EASI ≥ 16 + DLQI ≥ 10)。'; }
        else { band='極重度'; bg='#fee2e2'; fg='#991b1b'; interp='極重度(EASI &gt; 50)— Dupilumab / JAK 抑制劑優先。'; }
        return { score: s.toFixed(1), band: band, bg: bg, fg: fg, interp: interp };
      },
      disclaimer: '* EASI: Hanifin JM et al, Exp Dermatol 2001. 試驗常用 EASI-75(降幅 ≥ 75%)為療效指標。'
    });
  };

  // -----------------------------------------------------------------------
  // Homepage spotlight — "最近更新" + "熱門推薦" dual columns
  // (Taiwan KOL pattern; benchmarked against 黃瑽寧 / 邱品齊 / 蔡逸群 sites)
  // Auto-populates from DN.ARTICLES catalog; runs on homepage only.
  // -----------------------------------------------------------------------
  DN.POPULAR_PICKS = ['acne-myths','eczema-myths','hairloss-myths'];

  DN.injectSpotlight = function () {
    var recentEl = document.getElementById('dn-recent-list');
    var popularEl = document.getElementById('dn-popular-list');
    if (!recentEl && !popularEl) return;
    var articles = DN.ARTICLES || [];

    function rowHTML(a, badge) {
      var tagEn = a.tag_en || a.tag || '';
      var dateLabel = a.date || '';
      var title = a.title || a.slug;
      var num = DN.getArticleNumber(a.slug);
      var numStr = num ? '№' + num + ' · ' : '';
      return '<a href="/blog/' + a.slug + '" ' +
        'style="display:flex;flex-direction:column;gap:5px;padding:14px 16px;background:#fff;' +
        'border:1px solid var(--border, #dcd5c8);border-radius:12px;text-decoration:none;color:inherit;' +
        'transition:all .15s;box-shadow:0 1px 2px rgba(15,23,42,.04)" ' +
        'onmouseover="this.style.borderColor=\'rgba(122,146,133,.5)\';this.style.transform=\'translateY(-2px)\';this.style.boxShadow=\'0 8px 18px -10px rgba(77,99,88,.25)\'" ' +
        'onmouseout="this.style.borderColor=\'var(--border, #dcd5c8)\';this.style.transform=\'\';this.style.boxShadow=\'0 1px 2px rgba(15,23,42,.04)\'">' +
        '<div style="display:flex;align-items:center;gap:6px;font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:#4d6358">' +
          (badge ? '<span style="padding:2px 8px;border-radius:9999px;background:' + badge.bg + ';color:' + badge.fg + ';letter-spacing:.08em;font-size:10px">' + badge.label + '</span>' : '') +
          (num ? '<span style="font-family:Inter,sans-serif;letter-spacing:.06em;color:#4d6358;font-weight:800">№' + num + '</span><span style="opacity:.5">·</span>' : '') +
          '<span>' + tagEn + '</span>' +
          '<span style="opacity:.5">·</span>' +
          '<time style="font-weight:500;font-family:Inter,sans-serif;letter-spacing:0">' + dateLabel + '</time>' +
        '</div>' +
        '<div style="font-family:\'Noto Serif TC\',Georgia,serif;font-size:15px;font-weight:700;line-height:1.5;color:#0f172a">' + title + '</div>' +
      '</a>';
    }

    // Recent: top 3 by date desc (string compare works for YYYY-MM-DD)
    if (recentEl) {
      var sorted = articles.slice().sort(function (a, b) { return (b.date || '').localeCompare(a.date || ''); });
      var top3 = sorted.slice(0, 3);
      recentEl.innerHTML = top3.map(function (a, i) {
        return '<li>' + rowHTML(a, i === 0 ? { label: 'NEW', bg: '#fee2e2', fg: '#991b1b' } : null) + '</li>';
      }).join('');
    }
    if (popularEl) {
      var picks = DN.POPULAR_PICKS.map(function (slug) {
        return articles.find(function (a) { return a.slug === slug; });
      }).filter(Boolean);
      popularEl.innerHTML = picks.map(function (a, i) {
        return '<li>' + rowHTML(a, { label: '#' + (i + 1), bg: '#dcfce7', fg: '#14532d' }) + '</li>';
      }).join('');
    }
  };

  // -----------------------------------------------------------------------
  // Font-size adjuster (S / M / L) — elder-friendly, persists in localStorage
  // Sits to the LEFT of existing back-to-top button (right:18px;bottom:24px)
  // -----------------------------------------------------------------------
  DN.addFontSizer = function () {
    if (document.getElementById('dn-font-sizer')) return;
    if (location.pathname.startsWith('/admin')) return;
    // Only show on article pages (where prose is heavy)
    if (!document.querySelector('.prose, #proseZh, .prose-zh')) return;

    var savedSize = localStorage.getItem('dn-font-size') || 'M';
    var sizeMap = { 'S': '15px', 'M': '16.5px', 'L': '18.5px' };
    function applyFontSize(s) {
      var styleEl = document.getElementById('dn-font-size-style');
      if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'dn-font-size-style';
        document.head.appendChild(styleEl);
      }
      styleEl.textContent =
        '.prose, .prose-zh, .prose-en, #proseZh, #proseEn { font-size: ' + sizeMap[s] + ' !important; }' +
        '.prose p, .prose-zh p, .prose-en p, #proseZh p, #proseEn p { font-size: ' + sizeMap[s] + ' !important; }';
      localStorage.setItem('dn-font-size', s);
    }
    applyFontSize(savedSize);

    var wrap = document.createElement('div');
    wrap.id = 'dn-font-sizer';
    wrap.setAttribute('aria-label', '字型大小調整');
    // Position below back-to-top button (which is at right:18px;bottom:24px)
    wrap.style.cssText =
      'position:fixed;right:18px;bottom:74px;z-index:49;display:flex;flex-direction:column;' +
      'background:#fff;border:1px solid var(--border, #dcd5c8);border-radius:22px;' +
      'box-shadow:0 6px 18px -8px rgba(77,99,88,.45);overflow:hidden;opacity:0;' +
      'pointer-events:none;transition:opacity .25s;';

    ['S', 'M', 'L'].forEach(function (s) {
      var b = document.createElement('button');
      b.type = 'button';
      b.dataset.size = s;
      b.style.cssText =
        'width:38px;height:32px;border:0;cursor:pointer;font-weight:700;color:#4d6358;' +
        'background:' + (s === savedSize ? 'linear-gradient(180deg,#a4b5a8,#4d6358)' : 'transparent') + ';' +
        'color:' + (s === savedSize ? '#fff' : '#4d6358') + ';';
      b.style.fontSize = s === 'S' ? '11px' : (s === 'M' ? '13px' : '15px');
      b.textContent = s === 'S' ? '小' : (s === 'M' ? '中' : '大');
      b.setAttribute('aria-label', '字型大小 ' + s);
      b.title = '字型大小 ' + (s === 'S' ? '小' : (s === 'M' ? '中' : '大'));
      b.addEventListener('click', function () {
        applyFontSize(s);
        wrap.querySelectorAll('button').forEach(function (x) {
          x.style.background = 'transparent';
          x.style.color = '#4d6358';
        });
        b.style.background = 'linear-gradient(180deg,#a4b5a8,#4d6358)';
        b.style.color = '#fff';
        if (typeof gtag === 'function') {
          try { gtag('event', 'font_size_change', { size: s, page_path: location.pathname }); } catch (e) {}
        }
      });
      wrap.appendChild(b);
    });
    document.body.appendChild(wrap);

    // Show after scroll > 400 (similar trigger to back-to-top)
    var ticking = false;
    function update() {
      var scrolled = window.scrollY > 400;
      wrap.style.opacity = scrolled ? '1' : '0';
      wrap.style.pointerEvents = scrolled ? 'auto' : 'none';
      ticking = false;
    }
    window.addEventListener('scroll', function () {
      if (!ticking) { requestAnimationFrame(update); ticking = true; }
    }, { passive: true });
    update();
  };

  // -----------------------------------------------------------------------
  // Content feedback button — replaces "LINE consult" pattern with mailto
  // For residents who don't run a clinic — feedback goes to gmail
  // -----------------------------------------------------------------------
  DN.addFeedbackLink = function () {
    var article = document.querySelector('article.max-w-3xl');
    if (!article || document.getElementById('dn-feedback')) return;
    var slug = DN.currentSlug();
    var pageTitle = document.title.split('|')[0].trim();
    var subject = encodeURIComponent('[網站回饋] ' + pageTitle);
    var body = encodeURIComponent(
      '醫師您好,\n\n' +
      '我想針對下列文章提供回饋:\n' +
      '文章: ' + pageTitle + '\n' +
      '網址: ' + location.href + '\n\n' +
      '回饋內容(請填寫):\n' +
      '□ 內容更正建議\n' +
      '□ 引用爭議\n' +
      '□ 過時資訊提醒\n' +
      '□ 其他:_____\n\n' +
      '說明:\n\n\n' +
      '謝謝!'
    );
    var box = document.createElement('section');
    box.id = 'dn-feedback';
    box.className = 'max-w-3xl mx-auto px-5 sm:px-8 my-6';
    box.innerHTML =
      '<div style="background:#fafaf7;border:1px dashed #dcd5c8;border-radius:12px;padding:14px 18px;font-size:13px;color:#5e574e;line-height:1.75;display:flex;align-items:center;gap:14px;flex-wrap:wrap">' +
      '<div style="flex:1;min-width:220px">' +
      '<strong data-zh="發現錯誤、過時資訊、引用爭議?" data-en="Spot an error or outdated info?">發現錯誤、過時資訊、引用爭議?</strong><br/>' +
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
  // 目前金流由歐付寶 ezPay 處理。EZPAY 商店 PG100000760296 審核中,
  // 待通過後把 DN.SUPPORT_URL 換成歐付寶建立的「立即收款」連結即可。
  // 設為 '' 或 null 時,自動隱藏所有「支持作者」按鈕(等待審核期間用)。
  // -----------------------------------------------------------------------
  DN.SUPPORT_URL = '';   // ← 換成歐付寶連結後即上線(例:https://www.ezpay.com.tw/QPay/?code=XXXX)
  DN.BMC_URL = DN.SUPPORT_URL;   // legacy alias (do not delete)

  DN.injectBMCFooter = function () {
    if (!DN.SUPPORT_URL) return;   // 等待 ezPay 審核中,先不注入
    if (document.getElementById('dn-bmc-footer')) return;
    var footer = document.querySelector('footer');
    if (!footer) return;
    var section = document.createElement('section');
    section.id = 'dn-bmc-footer';
    section.style.cssText = 'max-width:780px;margin:0 auto 0;padding:24px 20px 0;text-align:center';
    // Subtle white card matching the rest of the site
    section.innerHTML =
      '<div style="background:#fff;border:1px solid var(--border,#e7e2d8);border-radius:18px;padding:22px 26px;box-shadow:0 4px 14px -8px rgba(15,23,42,.08)">' +
        '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.22em;color:#0e7c86;font-weight:700;margin-bottom:6px" data-zh="如果這個網站對您有幫助" data-en="If this site has helped you">如果這個網站對您有幫助</div>' +
        '<h3 style="font-family:\'Noto Serif TC\',Georgia,serif;font-size:20px;font-weight:700;color:#0f172a;margin:0 0 8px" data-zh="請我喝杯咖啡 ☕" data-en="Buy me a coffee ☕">請我喝杯咖啡 ☕</h3>' +
        '<p style="font-size:13px;color:#5e574e;line-height:1.85;margin:0 auto 14px;max-width:540px" data-zh="本網站<strong>無業配、無贊助</strong>,所有衛教文章與量表計算器都<strong>免費</strong>。本贊助為讀者自願性的內容打賞,<strong>非醫療服務費用</strong>,不涉及任何醫療諮詢、診斷或治療。" data-en="No ads, no sponsorships. All articles and calculators are free. This support is a voluntary content tip, not a medical-service fee, and does not involve any medical consultation, diagnosis, or treatment.">本網站<strong>無業配、無贊助</strong>,所有衛教文章與量表計算器都<strong>免費</strong>。本贊助為讀者自願性的內容打賞,<strong>非醫療服務費用</strong>,不涉及任何醫療諮詢、診斷或治療。</p>' +
        '<a href="' + DN.SUPPORT_URL + '" target="_blank" rel="noopener" data-bmc-footer-link ' +
          'style="display:inline-flex;align-items:center;gap:8px;padding:10px 22px;border-radius:9999px;background:#0e7c86;color:#fff;text-decoration:none;font-size:14px;font-weight:700;border:1px solid #0e7c86;box-shadow:0 4px 12px -4px rgba(14,124,134,.4);transition:background .15s">' +
          '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8h1a4 4 0 0 1 0 8h-1"/><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/></svg>' +
          '<span data-zh="贊助本站" data-en="Support this site">贊助本站</span>' +
        '</a>' +
      '</div>';
    footer.parentNode.insertBefore(section, footer);

    if (typeof gtag === 'function') {
      var link = section.querySelector('[data-bmc-footer-link]');
      if (link) link.addEventListener('click', function () {
        try { gtag('event', 'support_click', { source: 'footer', page_path: location.pathname }); } catch (e) {}
      });
    }
  };

  DN.injectBMC = function () {
    DN.injectBMCFooter();
    if (!DN.SUPPORT_URL) return;   // 等待 ezPay 審核中,先不注入 header pill
    if (document.getElementById('dn-bmc-header')) return;
    var headerInner = document.querySelector('header.sticky .h-16 > div:last-child');
    if (!headerInner) return;
    var a = document.createElement('a');
    a.id = 'dn-bmc-header';
    a.href = DN.SUPPORT_URL;
    a.target = '_blank';
    a.rel = 'noopener';
    a.setAttribute('aria-label', '支持作者');
    // Low-key teal pill matching the existing header nav links — no yellow background
    a.style.cssText =
      'display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:9999px;' +
      'background:transparent;color:#0c5159;text-decoration:none;' +
      'font-size:12px;font-weight:600;border:1px solid #a7d8ce;' +
      'transition:background .15s,color .15s';
    a.onmouseover = function () { a.style.background = '#eaf6f3'; a.style.color = '#0e7c86'; };
    a.onmouseout  = function () { a.style.background = 'transparent'; a.style.color = '#0c5159'; };
    a.innerHTML =
      '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<path d="M18 8h1a4 4 0 0 1 0 8h-1"/><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/>' +
        '<line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/>' +
      '</svg>' +
      '<span class="hidden sm:inline" data-zh="支持作者" data-en="Buy me a coffee">支持作者</span>';
    // Insert immediately AFTER the search button (i.e. between search and language toggle)
    var searchBtn = headerInner.querySelector('button[aria-label="搜尋"]');
    if (searchBtn && searchBtn.parentNode === headerInner) {
      searchBtn.insertAdjacentElement('afterend', a);
    } else {
      // Fallback: place before the language selector
      var langSel = headerInner.querySelector('#langToggle');
      if (langSel) headerInner.insertBefore(a, langSel);
      else headerInner.appendChild(a);
    }

    // GA4 tracking
    if (typeof gtag === 'function') {
      a.addEventListener('click', function () {
        try { gtag('event', 'bmc_click', { source: 'header', page_path: location.pathname }); } catch (e) {}
      });
    }
  };

  // -----------------------------------------------------------------------
  // Sticky bottom CTA bar — mobile-only fixed bar
  // Compliance: no booking, no clinic, no phone — only educational nav
  // (找衛教文章 / 量表計算器 / 詞彙)
  // -----------------------------------------------------------------------
  DN.addStickyCTA = function () {
    if (document.getElementById('dn-sticky-cta')) return;
    if (location.pathname === '/about' || location.pathname === '/about/') return;
    if (location.pathname.startsWith('/admin')) return;

    var bar = document.createElement('div');
    bar.id = 'dn-sticky-cta';
    bar.setAttribute('aria-label', '快速操作工具列');
    bar.style.cssText =
      'position:fixed;bottom:0;left:0;right:0;z-index:50;display:grid;grid-template-columns:1fr 1fr 1fr;' +
      'background:rgba(250,247,242,.96);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);' +
      'border-top:1px solid var(--border, #dcd5c8);box-shadow:0 -4px 20px -8px rgba(77,99,88,.2);' +
      'padding-bottom:env(safe-area-inset-bottom)';
    bar.innerHTML =
      '<a href="/#dn-hub" ' +
        'style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;padding:9px 4px;text-decoration:none;color:#4d6358;font-size:11px;font-weight:700;border-right:1px solid var(--border, #dcd5c8)" ' +
        'data-cta="article-hub" aria-label="找衛教文章">' +
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></svg>' +
        '<span data-zh="找文章" data-en="Find Article">找文章</span>' +
      '</a>' +
      '<a href="/tools" ' +
        'style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;padding:9px 4px;text-decoration:none;color:#4d6358;font-size:11px;font-weight:700;border-right:1px solid var(--border, #dcd5c8)" ' +
        'data-cta="tools" aria-label="量表計算器">' +
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 7h6M9 12h6M9 17h6"/></svg>' +
        '<span data-zh="量表" data-en="Tools">量表</span>' +
      '</a>' +
      '<a href="/glossary" ' +
        'style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;padding:9px 4px;text-decoration:none;color:#4d6358;font-size:11px;font-weight:700" ' +
        'data-cta="glossary" aria-label="詞彙字典">' +
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>' +
        '<span data-zh="詞彙" data-en="Glossary">詞彙</span>' +
      '</a>';

    var style = document.createElement('style');
    style.id = 'dn-sticky-cta-css';
    style.textContent =
      '#dn-sticky-cta a:active{ background:#f1ece4 }' +
      '#dn-sticky-cta a:hover{ background:#f5f1eb }' +
      '@media (min-width: 768px){ #dn-sticky-cta{ display:none !important } body.dn-has-sticky-cta{ padding-bottom:0 !important } }' +
      '@media (max-width: 767px){ body.dn-has-sticky-cta{ padding-bottom:64px } }';
    document.head.appendChild(style);
    document.body.appendChild(bar);
    document.body.classList.add('dn-has-sticky-cta');

    // Track CTA clicks
    if (typeof gtag === 'function') {
      bar.querySelectorAll('a[data-cta]').forEach(function (a) {
        a.addEventListener('click', function () {
          try { gtag('event', 'sticky_cta_click', { cta: a.dataset.cta, page_path: location.pathname }); } catch (e) {}
        });
      });
    }
  };

  // -----------------------------------------------------------------------
  // 中段內嵌 CTA — auto-injected after 50% of article H2's
  // (research-backed: internal CTA from broad-question content → consult)
  // -----------------------------------------------------------------------
  DN.addInlineCTA = function () {
    const prose = document.getElementById('proseZh');
    if (!prose) return;
    const h2s = prose.querySelectorAll('h2');
    if (h2s.length < 4) return;
    // Insert after the H2 closest to 50% of all H2's
    const targetH2 = h2s[Math.floor(h2s.length / 2)];
    if (!targetH2 || targetH2.dataset.dnCtaInserted) return;
    targetH2.dataset.dnCtaInserted = '1';
    const cta = document.createElement('div');
    cta.id = 'dn-inline-cta';
    cta.style.cssText = 'background:linear-gradient(135deg,#ecfeff 0%,#f5fbfa 100%);border:1px solid #a5f3fc;border-radius:14px;padding:16px 20px;margin:22px 0;display:flex;gap:14px;align-items:center;flex-wrap:wrap;';
    cta.innerHTML =
      '<div style="flex:1;min-width:200px">' +
        '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.18em;color:#4d6358;font-weight:700;margin-bottom:4px" data-zh="想評估自己的嚴重度?" data-en="Self-assess severity?">想評估自己的嚴重度?</div>' +
        '<div style="font-size:14px;color:#0f172a;line-height:1.7;margin:0" data-zh="本站提供 <strong>15 個臨床量表計算器</strong>(SCORAD、PASI、DLQI、UAS7 等),可即時自評、了解嚴重度與治療對應。" data-en="This site provides <strong>15 clinical calculators</strong> (SCORAD, PASI, DLQI, UAS7…) for instant self-assessment.">本站提供 <strong>15 個臨床量表計算器</strong>(SCORAD、PASI、DLQI、UAS7 等),可即時自評、了解嚴重度與治療對應。</div>' +
      '</div>' +
      '<a href="/tools" style="flex-shrink:0;padding:10px 18px;border-radius:9999px;background:#0e7c86;color:#fff;text-decoration:none;font-size:13px;font-weight:700;white-space:nowrap" data-zh="量表計算器 →" data-en="Calculators →">量表計算器 →</a>';
    targetH2.parentNode.insertBefore(cta, targetH2);
  };

  // -----------------------------------------------------------------------
  // 作者簡介 / Author Bio (E-A-T signal for medical YMYL content)
  // Auto-injected at end of every article for credentials transparency
  // -----------------------------------------------------------------------
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
            '<span style="font-size:12px;font-weight:600;color:#4d6358;margin-left:8px;padding:2px 8px;border-radius:6px;background:#fff;border:1px solid #a5f3fc;font-family:Inter,sans-serif" data-zh="皮膚科 R2" data-en="Dermatology PGY-2">皮膚科 R2</span>' +
          '</div>' +
          '<div style="font-size:13px;color:#334155;line-height:1.85" data-zh="<strong>現職</strong>:皮膚科 住院醫師(R2)<br/>' +
            '<strong>學歷</strong>:高雄醫學大學醫學系 醫學士(M.D.)<br/>' +
            '<strong>訓練</strong>:高雄醫學大學附設中和紀念醫院 不分科住院醫師(PGY)" data-en="<strong>Current</strong>: Dermatology Resident (PGY-2)<br/><strong>Education</strong>: M.D., Kaohsiung Medical University, College of Medicine<br/><strong>Training</strong>: Kaohsiung Medical University Hospital, Post-Graduate Year (rotating)"><strong>現職</strong>:皮膚科 住院醫師(R2)<br/><strong>學歷</strong>:高雄醫學大學醫學系 醫學士(M.D.)<br/><strong>訓練</strong>:高雄醫學大學附設中和紀念醫院 不分科住院醫師(PGY)</div>' +
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
        '<div data-zh="本文為皮膚科住院醫師的<strong>衛教與學習筆記</strong>,內容依據國際醫學文獻與臨床指引整理,僅作為<strong>一般教育用途</strong>。' +
        '不構成<strong>個別醫療建議、診斷或治療處方</strong>。' +
        '個別病情之評估、藥物選擇、雷射治療、手術等,請務必<strong>面對面看診</strong>由主治醫師依完整病史與檢查決定。' +
        '本網站<strong>不涉及任何藥品、醫療器材、療程或診所之推薦或業配</strong>;若提及商品為公開市售品,僅作教學說明。' +
        '依《醫療法》§85-86 及《醫師法》§17,個別治療效果因人而異,本文不保證任何結果。' +
        '若有不適,請就近至皮膚科專科醫師門診評估。" data-en="This article is a <strong>patient-education and study note</strong> by a dermatology resident, summarizing international medical literature and guidelines for general education only. It is <strong>not individual medical advice, diagnosis, or prescription</strong>. For personal evaluation, medication choice, laser, or surgical procedures, please consult a board-certified dermatologist in person. This site does <strong>not endorse any drug, device, procedure, or clinic</strong>. Per Taiwan Medical Care Act §§85–86 and Physicians Act §17, individual outcomes vary; no result is guaranteed.">本文為皮膚科住院醫師的<strong>衛教與學習筆記</strong>,內容依據國際醫學文獻與臨床指引整理,僅作為<strong>一般教育用途</strong>。不構成<strong>個別醫療建議、診斷或治療處方</strong>。個別病情之評估、藥物選擇、雷射治療、手術等,請務必<strong>面對面看診</strong>由主治醫師依完整病史與檢查決定。本網站<strong>不涉及任何藥品、醫療器材、療程或診所之推薦或業配</strong>;若提及商品為公開市售品,僅作教學說明。依《醫療法》§85-86 及《醫師法》§17,個別治療效果因人而異,本文不保證任何結果。若有不適,請就近至皮膚科專科醫師門診評估。</div>' +
      '</div>';
    article.parentNode.insertBefore(box, article.nextSibling);
  };

  // -----------------------------------------------------------------------
  // GA4 conversion event tracking — booking, email, outbound clicks
  // -----------------------------------------------------------------------
  DN.bindGAEvents = function () {
    if (typeof gtag !== 'function') return;
    function fire(name, params) {
      try { gtag('event', name, params || {}); } catch (e) { /* ignore */ }
    }
    // (Removed for compliance) Booking-related CTA tracking — site no longer
    // includes any booking, appointment, or hospital-affiliation links.
    // Email clicks
    document.querySelectorAll('a[href^="mailto:"]').forEach(function (a) {
      a.addEventListener('click', function () {
        fire('email_click', { email: 'expertise88864', page_path: location.pathname });
      });
    });
    // Newsletter subscribe (data-subscribe-link)
    document.querySelectorAll('[data-subscribe-link]').forEach(function (a) {
      a.addEventListener('click', function () {
        fire('newsletter_subscribe_click', { method: 'mailto', page_path: location.pathname });
      });
    });
    // RSS link click
    document.querySelectorAll('a[href$="/feed.xml"], a[href$="/atom.xml"]').forEach(function (a) {
      a.addEventListener('click', function () {
        fire('rss_subscribe_click', { feed: a.getAttribute('href'), page_path: location.pathname });
      });
    });
    // Lang toggle
    const lt = document.getElementById('langToggle');
    if (lt && lt.tagName === 'SELECT') {
      lt.addEventListener('change', function () {
        fire('lang_switch', { lang: lt.value });
      });
    }
    // Article internal navigation (cross-link clicks)
    document.querySelectorAll('article a[href^="/blog/"]').forEach(function (a) {
      a.addEventListener('click', function () {
        fire('internal_link', { destination: a.getAttribute('href'), source: location.pathname });
      });
    });
    // Track 75% scroll depth on articles (reading completion proxy)
    if (document.querySelector('article .prose')) {
      let fired = false;
      window.addEventListener('scroll', function () {
        if (fired) return;
        const h = document.documentElement;
        const pct = (h.scrollTop + h.clientHeight) / h.scrollHeight;
        if (pct >= 0.75) {
          fired = true;
          fire('article_75pct', { page_path: location.pathname });
        }
      }, { passive: true });
    }
  };

  DN.markNewArticles = function () {
    const NOW = Date.now();
    const SEVEN_DAYS = 7 * 86400 * 1000;
    const cards = document.querySelectorAll('a.article-list-item[href*="/blog/"]');
    if (!cards.length) return;
    const styleEl = document.createElement('style');
    styleEl.textContent = '.dn-new-pulse{display:inline-block;margin-left:6px;padding:1px 7px;border-radius:9999px;background:linear-gradient(135deg,#fbbf24,#f59e0b);color:#fff;font-size:9.5px;font-weight:800;letter-spacing:.04em;line-height:1.5;animation:dnPulse 1.6s ease-in-out infinite;}@keyframes dnPulse{0%,100%{box-shadow:0 0 0 0 rgba(251,191,36,.55)}50%{box-shadow:0 0 0 6px rgba(251,191,36,0)}}';
    document.head.appendChild(styleEl);
    cards.forEach(function (a) {
      const href = a.getAttribute('href') || '';
      const m = href.match(/\/blog\/([a-z0-9-]+)/i);
      if (!m) return;
      const slug = m[1];
      const meta = (DN.ARTICLES || []).find(function (x) { return x.slug === slug; });
      if (!meta) return;
      const pub = Date.parse(meta.date);
      if (!pub || NOW - pub > SEVEN_DAYS) return;
      const h3 = a.querySelector('h3');
      if (!h3 || h3.querySelector('.dn-new-pulse')) return;
      const tag = document.createElement('span');
      tag.className = 'dn-new-pulse';
      tag.textContent = 'NEW';
      h3.appendChild(tag);
    });
  };

  DN.bindWebVitals = function () {
    if (typeof gtag !== 'function') return;
    function send(name, value, id) {
      try {
        gtag('event', name, {
          event_category: 'Web Vitals',
          event_label: id,
          value: Math.round(name === 'CLS' ? value * 1000 : value),
          non_interaction: true
        });
      } catch (e) { /* ignore */ }
    }
    // LCP via PerformanceObserver
    try {
      let lcp = 0;
      const lcpObs = new PerformanceObserver(function (list) {
        const entries = list.getEntries();
        const last = entries[entries.length - 1];
        lcp = last.renderTime || last.loadTime || last.startTime;
      });
      lcpObs.observe({ type: 'largest-contentful-paint', buffered: true });
      addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'hidden' && lcp) {
          send('LCP', lcp, 'lcp-' + Date.now());
          lcp = 0;
        }
      }, { once: true });
    } catch (e) { /* ignore */ }
    // CLS
    try {
      let cls = 0;
      const clsObs = new PerformanceObserver(function (list) {
        list.getEntries().forEach(function (entry) {
          if (!entry.hadRecentInput) cls += entry.value;
        });
      });
      clsObs.observe({ type: 'layout-shift', buffered: true });
      addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'hidden') {
          send('CLS', cls, 'cls-' + Date.now());
        }
      });
    } catch (e) { /* ignore */ }
    // INP (interaction to next paint) via event timing
    try {
      let worstINP = 0;
      const inpObs = new PerformanceObserver(function (list) {
        list.getEntries().forEach(function (entry) {
          if (entry.duration > worstINP) worstINP = entry.duration;
        });
      });
      inpObs.observe({ type: 'event', buffered: true, durationThreshold: 40 });
      addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'hidden' && worstINP) {
          send('INP', worstINP, 'inp-' + Date.now());
          worstINP = 0;
        }
      });
    } catch (e) { /* ignore */ }
  };


  // -----------------------------------------------------------------------
  // 文章快速查找 — search + disease tag chips, auto-injected to #dn-hub
  // -----------------------------------------------------------------------
  DN.TAG_GROUPS = {
    '痘痘 / 痘疤':    ['acne-myths', 'acne-scar-treatment', 'isotretinoin-patient', 'topical-acids-patient'],
    '防曬':           ['sunscreen-myths'],
    '異膚 / 濕疹':    ['eczema-myths', 'pediatric-eczema', 'topical-steroids-guide', 'biologics-overview'],
    '兒童 / 嬰幼兒':  ['pediatric-eczema'],
    '肝斑 / 美白':    ['melasma-myths', 'skin-whitening-agents'],
    '玫瑰斑 / 酒糟':  ['rosacea-myths', 'demodex-rosacea'],
    '落髮 / 圓禿':    ['hairloss-myths', 'alopecia-areata'],
    '蕁麻疹':         ['urticaria-myths'],
    '乾癬':           ['psoriasis-myths', 'biologics-overview'],
    '香港腳 / 灰指甲':['tinea-myths'],
    '病毒疣 / HPV':   ['warts-myths'],
    '帶狀皰疹 / 皮蛇':['shingles-myths'],
    '白斑':           ['vitiligo'],
    '化膿性汗腺炎':   ['hidradenitis-suppurativa'],
    '猴痘 Mpox':      ['mpox-care'],
    '標靶藥物副作用': ['targeted-therapy-skin'],
    '類固醇藥膏':     ['topical-steroids-guide', 'eczema-myths'],
    '生物製劑':       ['biologics-overview'],
    '酸類 / A 酸':    ['topical-acids-patient', 'skin-whitening-agents', 'isotretinoin-patient'],
    '常見問題 FAQ':   ['dermatology-faq'],
    '粉瘤 / 表皮囊腫': ['epidermoid-cyst'],
    '雷射 / 光電':    ['laser-dermatology', 'acne-scar-treatment', 'rosacea-myths'],
    '健保 / 自費':    ['nhi-derm-drugs', 'biologics-overview', 'isotretinoin-patient']
  };

  DN.bindArticleHub = function () {
    var hub = document.getElementById('dn-hub');
    if (!hub) return;
    var articles = DN.ARTICLES || [];
    var mode = hub.dataset.hubMode || 'full';

    if (!document.getElementById('dn-hub-css')) {
      var st = document.createElement('style');
      st.id = 'dn-hub-css';
      st.textContent =
        '#dn-hub{ background:#fff; border:1px solid var(--border); border-radius:18px; padding:18px 18px 14px; margin:18px 0 22px; box-shadow:0 1px 2px rgba(15,23,42,.04), 0 14px 30px -18px rgba(77,99,88,.18); }' +
        '.dn-hub-title{ font-size:11px; text-transform:uppercase; letter-spacing:.22em; font-weight:700; color:#4d6358; margin:0 0 10px; display:flex; align-items:center; gap:6px; }' +
        '.dn-search-row{ display:flex; align-items:center; gap:10px; margin:0 0 12px; flex-wrap:wrap; }' +
        '#dn-search-input{ flex:1; min-width:200px; padding:10px 14px 10px 36px; font-size:14.5px; border:1px solid var(--border); border-radius:10px; outline:none; transition:border-color .15s, box-shadow .15s; background:#fff url("data:image/svg+xml;utf8,<svg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27 fill=%27none%27 stroke=%27%230c5159%27 stroke-width=%272.2%27 stroke-linecap=%27round%27><circle cx=%2711%27 cy=%2711%27 r=%277%27/><line x1=%2721%27 y1=%2721%27 x2=%2716.5%27 y2=%2716.5%27/></svg>") no-repeat 10px center; background-size:18px; }' +
        '#dn-search-input:focus{ border-color:rgba(122,146,133,.6); box-shadow:0 0 0 3px rgba(164,181,168,.20); }' +
        '#dn-search-status{ font-size:11.5px; color:var(--muted); white-space:nowrap; }' +
        '.dn-tag-chips{ display:flex; flex-wrap:wrap; gap:6px; margin:0; }' +
        '.dn-tag-chip{ padding:5px 11px; border-radius:9999px; font-size:12px; font-weight:600; color:var(--ink-2); background:#fff; border:1px solid var(--border); cursor:pointer; transition:all .15s; line-height:1.4; }' +
        '.dn-tag-chip:hover{ border-color:rgba(122,146,133,.45); color:var(--teal-deep); }' +
        '.dn-tag-chip.active{ background:linear-gradient(180deg,#a4b5a8,#4d6358); color:#fff; border-color:transparent; }' +
        '.dn-tag-chip.dn-tag-all{ background:#f1ece4; color:#4d6358; border-color:#a5f3fc; font-weight:700; }' +
        '.dn-tag-chip.dn-tag-all.active{ background:linear-gradient(180deg,#a4b5a8,#4d6358); color:#fff; border-color:transparent; }' +
        '.dn-show-more{ display:block; width:100%; text-align:center; margin:14px auto 0; padding:9px 14px; background:#fff; border:1px solid var(--border); border-radius:10px; font-size:13px; font-weight:600; color:var(--teal-deep); cursor:pointer; transition:all .15s; }' +
        '.dn-show-more:hover{ border-color:rgba(122,146,133,.5); background:var(--mint-soft); }' +
        '@media (max-width:640px){ #dn-search-input{ font-size:14px; padding:8px 12px 8px 32px; background-size:16px; } }';
      document.head.appendChild(st);
    }

    hub.innerHTML =
      '<div class="dn-hub-title"><span data-zh="快速查找皮膚科主題" data-en="Quick find by topic">快速查找皮膚科主題</span></div>' +
      '<div class="dn-search-row">' +
        '<input id="dn-search-input" type="search" placeholder="搜尋文章標題或關鍵字..." aria-label="搜尋文章" />' +
        '<div id="dn-search-status"></div>' +
      '</div>' +
      '<div class="dn-tag-chips" id="dn-tag-chips"></div>';

    var tagsDiv = document.getElementById('dn-tag-chips');
    var allBtn = document.createElement('button');
    allBtn.className = 'dn-tag-chip dn-tag-all active';
    allBtn.dataset.tag = '__all__';
    allBtn.textContent = '全部主題';
    allBtn.addEventListener('click', function () { applyFilter('__all__'); });
    tagsDiv.appendChild(allBtn);

    Object.keys(DN.TAG_GROUPS).forEach(function (tag) {
      var btn = document.createElement('button');
      btn.className = 'dn-tag-chip';
      btn.dataset.tag = tag;
      btn.textContent = tag;
      btn.addEventListener('click', function () { applyFilter(tag); });
      tagsDiv.appendChild(btn);
    });

    var initialLimit = parseInt(hub.dataset.showCount || '6', 10);
    var showingAll = (mode === 'full');
    var showMoreBtn = null;
    var allCards = Array.prototype.slice.call(document.querySelectorAll('.article-list-item'));

    function setActive(tag) {
      var chips = tagsDiv.querySelectorAll('.dn-tag-chip');
      for (var i = 0; i < chips.length; i++) {
        chips[i].classList.toggle('active', chips[i].dataset.tag === tag);
      }
    }
    function setStatus(t) { document.getElementById('dn-search-status').textContent = t; }

    function showBySlugs(slugs) {
      var shown = 0;
      for (var i = 0; i < allCards.length; i++) {
        var href = allCards[i].getAttribute('href') || '';
        var m = href.match(/\/blog\/([a-z0-9-]+)/);
        var slug = m ? m[1] : '';
        var match = slugs === null ? true : slugs.indexOf(slug) !== -1;
        allCards[i].style.display = match ? 'flex' : 'none';
        if (match) shown++;
      }
      return shown;
    }

    function applyFilter(tag) {
      setActive(tag);
      var inp = document.getElementById('dn-search-input');
      if (tag !== '__search__') inp.value = '';

      if (tag === '__all__') {
        if (mode === 'homepage' && !showingAll) {
          var newest = articles.slice().sort(function (a, b) {
            return (b.date || '').localeCompare(a.date || '');
          }).slice(0, initialLimit).map(function (a) { return a.slug; });
          var shown = showBySlugs(newest);
          setStatus('最新 ' + shown + ' 篇 / 共 ' + allCards.length + ' 篇');
          if (showMoreBtn) showMoreBtn.style.display = 'block';
        } else {
          showBySlugs(null);
          setStatus('全部 ' + allCards.length + ' 篇');
          if (showMoreBtn) showMoreBtn.style.display = 'none';
        }
      } else if (tag !== '__search__') {
        var ss = DN.TAG_GROUPS[tag] || [];
        var n = showBySlugs(ss);
        setStatus('找到 ' + n + ' 篇 ' + tag + ' 相關文章');
        if (showMoreBtn) showMoreBtn.style.display = 'none';
        showingAll = true;
      }
    }

    document.getElementById('dn-search-input').addEventListener('input', function (e) {
      var q = e.target.value.trim().toLowerCase();
      if (!q) { applyFilter('__all__'); return; }
      setActive('__search__');
      var matched = articles.filter(function (a) {
        return a.title.toLowerCase().indexOf(q) !== -1 ||
               (a.tag || '').toLowerCase().indexOf(q) !== -1 ||
               (a.tag_en || '').toLowerCase().indexOf(q) !== -1 ||
               a.slug.toLowerCase().indexOf(q) !== -1;
      }).map(function (a) { return a.slug; });
      var shown = showBySlugs(matched);
      setStatus(shown > 0 ? '搜尋「' + q + '」找到 ' + shown + ' 篇' : '「' + q + '」沒有結果');
      if (showMoreBtn) showMoreBtn.style.display = 'none';
      if (typeof gtag === 'function') {
        try { gtag('event', 'site_search', { search_term: q, results_count: shown }); } catch (err) {}
      }
    });

    if (mode === 'homepage') {
      showMoreBtn = document.createElement('button');
      showMoreBtn.className = 'dn-show-more';
      showMoreBtn.textContent = '↓ 顯示全部 ' + allCards.length + ' 篇文章';
      showMoreBtn.addEventListener('click', function () {
        showingAll = true;
        applyFilter('__all__');
        showMoreBtn.style.display = 'none';
      });
      hub.appendChild(showMoreBtn);
    }

    applyFilter('__all__');
  };

  DN.initBlog = function (opts) {
    opts = opts || {};
    let curLang = DN.detectLang();

    function apply(lang) {
      curLang = lang;
      DN.applyTextOnly(lang);
      const isZh = (lang === 'zh');
      const ze = document.getElementById(opts.proseZh || 'proseZh');
      const en = document.getElementById(opts.proseEn || 'proseEn');
      if (ze) ze.style.display = isZh ? '' : 'none';
      if (en) en.style.display = isZh ? 'none' : '';
      if (typeof opts.onChange === 'function') opts.onChange(lang);
    }

    DN.injectMobileMenu();
    DN.injectBMC();
    DN.bindLangToggle(apply);
    apply(curLang);
    DN.addReadingProgress();
    DN.addScrollToTop();
    DN.bindRevealOnScroll();
    DN.prefetchOnIdle();
    DN.bindViewTransitions();

    // Article-only enhancements (auto-detect via .prose presence)
    if (document.getElementById('proseZh') || document.querySelector('article .prose')) {
      DN.addReadingMeta();
      DN.addInlineTOC();
      DN.addFloatingTOC();
      DN.bindScrollMemory();
      DN.addInlineCTA();
      DN.injectSCORAD();
      DN.injectSALT();
      DN.injectUAS7();
      DN.injectPASI();
      DN.injectDLQI();
      DN.injectHurley();
      DN.injectHairScale();
      DN.injectFitzpatrick();
      DN.injectGAGS();
      DN.injectMASI();
      DN.injectPOEM();
      DN.injectEASI();
      DN.injectIHS4();
      DN.injectNAPSI();
      DN.injectPHQ9();
      DN.addAuthorBio();
      DN.addLegalDisclaimer();
      DN.addTDALink();
      DN.addRelatedArticles();
      DN.addShareToolbar();
      DN.addFeedbackLink();
    }
    DN.addFontSizer();
    DN.bindWebVitals();
    DN.bindGAEvents();
    DN.bindArticleHub();
    DN.injectSpotlight();
    DN.injectReadProgress();
    DN.markNewArticles();
    DN.addStickyCTA();

    const yr = document.getElementById('yr');
    if (yr) yr.textContent = new Date().getFullYear();

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').then(function (reg) {
        DN.bindSWUpdateToast(reg);
        // Auto-check for update every 30 min when tab is foregrounded
        setInterval(function () {
          if (document.visibilityState === 'visible') reg.update().catch(function () {});
        }, 30 * 60 * 1000);
      }).catch(function () { /* ignore */ });
    }
    return { applyLang: apply };
  };
})();
