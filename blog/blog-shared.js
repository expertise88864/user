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
    btn.style.cssText = 'position:fixed;right:18px;bottom:24px;width:42px;height:42px;border-radius:50%;background:linear-gradient(180deg,#14b8a6,#0c5159);color:#fff;border:1px solid rgba(12,81,89,.5);box-shadow:0 8px 20px -8px rgba(12,81,89,.55);cursor:pointer;display:none;align-items:center;justify-content:center;z-index:50;font-size:18px;line-height:1';
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
      toast.innerHTML = '<span>網站已更新 — </span><button style="background:#fff;color:#0c5159;border:none;padding:5px 12px;border-radius:9999px;font-weight:700;font-size:12px;cursor:pointer">重新載入</button>';
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
        '<a href="/" class="block px-3 py-2.5 rounded-lg hover:bg-[var(--mint-soft)] text-[14px] font-semibold text-teal-700" data-zh="🏠 首頁" data-en="🏠 Home"></a>' +
        '<a href="/blog/" class="block px-3 py-2.5 rounded-lg hover:bg-[var(--mint-soft)] text-[14px] font-semibold text-teal-700" data-zh="📚 衛教文章" data-en="📚 Articles"></a>' +
        '<a href="https://www.cmuh.cmu.edu.tw/Department/Team?detail=77&amp;current=0&amp;source=dep" target="_blank" rel="noopener" class="block px-3 py-2.5 rounded-lg bg-teal-600 text-white text-[14px] font-semibold hover:bg-teal-700 mt-2" data-zh="📅 中國醫皮膚部 預約掛號 →" data-en="📅 Book at CMUH Dermatology →"></a>' +
        '<a href="/about" class="block px-3 py-2 rounded-lg text-[13.5px] text-ink-700 mt-2" data-zh="聯絡 / 看診資訊" data-en="Contact / Clinic info"></a>' +
        '<a href="/privacy" class="block px-3 py-2 rounded-lg text-[13.5px] text-ink-700" data-zh="隱私權政策" data-en="Privacy Policy"></a>' +
        '<a href="/blog/feed.xml" class="block px-3 py-2 rounded-lg text-[13.5px] text-ink-700">RSS</a>' +
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
    { slug:'acne-myths',          title:'痘痘 9 大迷思', cat:'myth', tag:'痘痘', date:'2026-05-03', emoji:'🩹', tag_en:'Acne' },
    { slug:'sunscreen-myths',     title:'防曬 8 大迷思', cat:'myth', tag:'防曬', date:'2026-05-03', emoji:'☀️', tag_en:'Sunscreen' },
    { slug:'eczema-myths',        title:'異位性皮膚炎 6 大迷思', cat:'myth', tag:'異膚', date:'2026-05-03', emoji:'🌿', tag_en:'Eczema' },
    { slug:'melasma-myths',       title:'肝斑 7 大迷思', cat:'myth', tag:'肝斑', date:'2026-05-03', emoji:'🟫', tag_en:'Melasma' },
    { slug:'rosacea-myths',       title:'玫瑰痤瘡 6 大迷思', cat:'myth', tag:'酒糟肌', date:'2026-05-03', emoji:'🌹', tag_en:'Rosacea' },
    { slug:'hairloss-myths',      title:'落髮 / 雄性禿 7 大迷思', cat:'myth', tag:'落髮', date:'2026-05-03', emoji:'💇', tag_en:'Hair loss' },
    { slug:'tinea-myths',         title:'香港腳 / 灰指甲 7 大迷思', cat:'myth', tag:'足癬', date:'2026-05-03', emoji:'👣', tag_en:'Tinea' },
    { slug:'urticaria-myths',     title:'蕁麻疹 6 大迷思', cat:'myth', tag:'蕁麻疹', date:'2026-05-04', emoji:'🐝', tag_en:'Urticaria' },
    { slug:'psoriasis-myths',     title:'乾癬 7 大迷思', cat:'myth', tag:'乾癬', date:'2026-05-04', emoji:'🧱', tag_en:'Psoriasis' },
    { slug:'warts-myths',         title:'病毒疣 6 大迷思', cat:'myth', tag:'病毒疣', date:'2026-05-04', emoji:'🦠', tag_en:'Warts' },
    { slug:'shingles-myths',      title:'帶狀皰疹 6 大迷思', cat:'myth', tag:'皮蛇', date:'2026-05-04', emoji:'⚡', tag_en:'Shingles' },
    { slug:'topical-acids-patient', title:'外用酸類完整衛教', cat:'product', tag:'酸類', date:'2026-05-02', emoji:'🧴', tag_en:'Topical acids' },
    { slug:'isotretinoin-patient',  title:'口服 A 酸完整衛教', cat:'rx', tag:'口服 A 酸', date:'2026-05-02', emoji:'💊', tag_en:'Isotretinoin' },
    { slug:'acne-scar-treatment',   title:'痘疤完整治療指引', cat:'rx', tag:'痘疤', date:'2026-05-04', emoji:'🎯', tag_en:'Acne scars' }
  ];

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
    bar.innerHTML =
      '<span style="display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:9999px;background:#ecfeff;border:1px solid #a5f3fc;color:#0c5159;font-weight:600">' +
        '<span aria-hidden="true">⏱</span><span data-zh="閱讀約 ' + minutes + ' 分鐘" data-en="' + minutes + ' min read">閱讀約 ' + minutes + ' 分鐘</span>' +
      '</span>' +
      '<span style="display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:9999px;background:#dcfce7;border:1px solid #86efac;color:#14532d;font-weight:600">' +
        '<span aria-hidden="true">📅</span><span data-zh="更新於 ' + reviewedDate + '" data-en="Updated · ' + reviewedDate + '">更新於 ' + reviewedDate + '</span>' +
      '</span>' +
      '<a href="/about" style="display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:9999px;background:#fff;border:1px solid var(--border);color:var(--teal-deep);text-decoration:none;font-weight:600" data-zh="關於作者 →" data-en="About the author →">關於作者 →</a>';
    target.parentNode.insertBefore(bar, target.nextSibling);
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
    aside.style.cssText = 'position:fixed;left:max(16px,calc(50% - 720px));top:120px;width:200px;max-height:calc(100vh - 160px);overflow-y:auto;padding:14px 16px;background:rgba(255,255,255,.92);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border:1px solid var(--border);border-radius:14px;box-shadow:0 12px 28px -14px rgba(12,81,89,.22);font-size:12.5px;line-height:1.7;z-index:30;';
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
    let html = '<div style="border-top:1px solid var(--line);padding-top:24px"><div style="font-size:11px;text-transform:uppercase;letter-spacing:.22em;color:var(--teal-deep);font-weight:700;margin-bottom:12px" data-zh="📖 你可能也會想看" data-en="📖 Related reads">📖 你可能也會想看</div><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">';
    scored.forEach(function (a) {
      html += '<a href="/blog/' + a.slug + '" style="display:flex;flex-direction:column;gap:6px;padding:14px;background:#fff;border:1px solid var(--border);border-radius:12px;text-decoration:none;color:var(--ink);transition:all .15s;box-shadow:0 1px 2px rgba(15,23,42,.04)" onmouseover="this.style.borderColor=\'rgba(14,124,134,.5)\';this.style.transform=\'translateY(-2px)\';this.style.boxShadow=\'0 10px 20px -10px rgba(12,81,89,.22)\'" onmouseout="this.style.borderColor=\'var(--border)\';this.style.transform=\'\';this.style.boxShadow=\'0 1px 2px rgba(15,23,42,.04)\'">' +
        '<span style="font-size:22px;line-height:1">' + (a.emoji || '📄') + '</span>' +
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
        (navigator.share ? '<button id="dn-native-share" data-share="native" style="display:inline-flex;align-items:center;gap:6px;padding:7px 13px;background:linear-gradient(180deg,#14b8a6,#0c5159);color:#fff;border:none;border-radius:9999px;font-size:12.5px;font-weight:700;cursor:pointer">↗ 系統分享</button>' : '') +
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
  // §86 醫療法保護 — auto-inject medical-disclaimer block at end of article
  // (resident-grade safety wording per agent research)
  // -----------------------------------------------------------------------
  DN.addLegalDisclaimer = function () {
    const article = document.querySelector('article.max-w-3xl');
    if (!article || document.getElementById('dn-legal-disclaimer')) return;
    const box = document.createElement('section');
    box.id = 'dn-legal-disclaimer';
    box.className = 'max-w-3xl mx-auto px-5 sm:px-8 my-6';
    box.innerHTML =
      '<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:14px;padding:14px 18px;font-size:12.5px;line-height:1.85;color:#9a3412">' +
        '<div style="font-weight:700;color:#7c2d12;margin-bottom:6px;letter-spacing:.04em">⚠ 重要聲明</div>' +
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
    // Booking CTA clicks (CMUH dermatology)
    document.querySelectorAll('a[href*="cmuh.cmu.edu.tw"]').forEach(function (a) {
      a.addEventListener('click', function () {
        fire('booking_click', { destination: 'CMUH Dermatology', page_path: location.pathname });
      });
    });
    // Email clicks
    document.querySelectorAll('a[href^="mailto:"]').forEach(function (a) {
      a.addEventListener('click', function () {
        fire('email_click', { email: 'expertise88864', page_path: location.pathname });
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
      DN.addFloatingTOC();
      DN.addLegalDisclaimer();
      DN.addRelatedArticles();
      DN.addShareToolbar();
    }
    DN.bindWebVitals();
    DN.bindGAEvents();
    DN.markNewArticles();

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
