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
    try {
      const found = document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith(name + '='));
      return found ? decodeURIComponent(found.slice(name.length + 1)) : null;
    } catch (_) {
      // Invalid or inaccessible cookies must not disable the article runtime.
      return null;
    }
  };
  DN.cookieSet = function (name, val, days) {
    const exp = new Date(Date.now() + (days || 365) * 86400e3).toUTCString();
    document.cookie = name + '=' + encodeURIComponent(val) + '; expires=' + exp + '; path=/; SameSite=Lax';
  };

  // URL is the source of truth for which language the user is currently
  // viewing. /en/* paths serve pre-translated mirrors; everything else
  // is ZH. Cookie/localStorage are only consulted when there's no URL
  // hint (e.g., first-time visitor on the homepage redirected to /).
  DN.detectLang = function () {
    if (location.pathname.startsWith('/en/') ||
        location.pathname === '/en') return 'en';
    const fromCookie = DN.cookieGet('dn_lang');
    if (fromCookie && DN.LANG_KEY[fromCookie]) return fromCookie;
    // CODE_REVIEW Phase 5 — guard localStorage access. Every other
    // localStorage read/write in this file is wrapped; this one wasn't, so a
    // browser with storage fully blocked (SecurityError on access) threw here
    // and, because detectLang() runs first inside initBlog(), took the whole
    // interactive layer (menu / lang toggle / search) down with it.
    let stored = null;
    try { stored = localStorage.getItem('dn_lang'); } catch (e) { /* storage blocked/disabled */ }
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
    const otherLang = lang === 'en' ? 'zh' : 'en';
    function plain(s) { return String(s || '').replace(/<[^>]+>/g, ''); }
    document.querySelectorAll('[data-zh],[data-en]').forEach(function (el) {
      const txt = DN.translate(el, lang);
      if (txt == null) return;
      const txtPlain = plain(txt);
      const elText = el.textContent;
      // Case A: visible text already matches target language → already correct,
      // skip (preserves inline edits like <b>/<br> the editor added).
      if (elText === txtPlain) return;
      // Case B: visible text matches the OTHER language → genuine language
      // switch. Run the swap.
      const otherSrc = el.dataset[otherLang];
      if (otherSrc != null && elText === plain(otherSrc)) {
        if (/[<&]/.test(txt) && /<\/?[a-z]/i.test(txt)) el.innerHTML = txt;
        else el.textContent = txt;
        return;
      }
      // Case C: visible text matches NEITHER stored language → element has
      // been customized in admin.html (text changes the editor saved into
      // visible textContent but didn't push back into data-zh / data-en).
      // Trust the customization and don't overwrite. Without this, every
      // page load would silently revert the editor's wording / formatting
      // changes back to the data-zh boilerplate. Fixes 2026-05-14 incident.
      return;
    });
    // Also swap placeholder / aria-label / title attributes when bilingual
    // variants are provided as data-zh-* / data-en-* attrs.
    ['placeholder', 'aria-label', 'title', 'alt'].forEach(function (attr) {
      const sel = '[data-zh-' + attr + '],[data-en-' + attr + ']';
      document.querySelectorAll(sel).forEach(function (el) {
        const order = lang === 'en' ? ['en', 'zh'] : ['zh', 'en'];
        for (const k of order) {
          const v = el.getAttribute('data-' + k + '-' + attr);
          if (v != null) { el.setAttribute(attr, v); return; }
        }
      });
    });
  };

  // Key Fact box styling — runs on EVERY page (article + index + homepage).
  // Was previously inside bindArticleHub which only ran when #dn-hub existed
  // (i.e. NOT on individual article pages where Key Fact actually appears).
  // Key-fact styles ship in the shared stylesheet before the first paint.
  DN.injectKeyFactCSS = function () {};

  // Sticky-scroll table wrapper for tall comparison charts (2026-05-10).
  // Keeps the horizontal scrollbar within the viewport (max-height: 78vh)
  // and pins thead so column names stay visible while scrolling vertically
  // inside the table. Used by psoriasis-systemic + atopic-dermatitis-systemic
  // biologics comparison tables.
  DN.injectChartScrollCSS = function () {
    if (document.getElementById('dn-chart-scroll-css')) return;
    var s = document.createElement('style');
    s.id = 'dn-chart-scroll-css';
    s.textContent =
      '.dn-chart-scroll{ max-height:78vh; overflow:auto; position:relative; margin:6px 0 4px; border-radius:10px; border:1px solid var(--line,#ebe4d8); -webkit-overflow-scrolling:touch; background:#fff }' +
      // CRITICAL: override the global table.dn `overflow:hidden` which becomes a
      // scroll container and breaks position:sticky on descendants. Also
      // border-collapse:collapse (the global default) breaks sticky on table
      // cells in some browsers. Force separate + visible inside our wrapper.
      '.dn-chart-scroll table{ margin:0 !important; border-collapse:separate !important; border-spacing:0 !important; overflow:visible !important; box-shadow:none !important; border-radius:0 !important }' +
      '.dn-chart-scroll thead th{ position:-webkit-sticky !important; position:sticky !important; top:0 !important; z-index:3 !important; background:#f1ece4 !important; box-shadow:inset 0 -1px 0 var(--line,#ebe4d8) }' +
      '@media (max-width:640px){ .dn-chart-scroll{ max-height:70vh } }';
    document.head.appendChild(s);
  };





  // 2026-05-24 — Switched from in-place `applyTextOnly()` swap to full
  // navigation between /<path> and /en/<path>. The in-place swap only
  // translated elements with `data-en` attributes (typically 30-70% of
  // article body) which left H2/H3/FAQ/SVG/related-articles in Chinese
  // when viewing the "EN" version. Navigating to the pre-translated
  // /en/ mirror gives 100% English content (the mirror is built by
  // _gen_en_pages.py from the ZH source with full translation pipeline).
  DN.bindLangToggle = function (onChange) {
    const toggle = document.getElementById('langToggle');
    if (!toggle) return;

    function targetUrlFor(lang) {
      const path = location.pathname;
      const isCurrentlyEn = path.startsWith('/en/') || path === '/en';
      if (lang === 'en' && !isCurrentlyEn) {
        // Add /en prefix. Handle root '/' specially (→ '/en').
        const newPath = path === '/' ? '/en' : '/en' + path;
        return newPath + location.search + location.hash;
      }
      if (lang === 'zh' && isCurrentlyEn) {
        // Strip /en prefix. '/en' or '/en/' → '/'.
        let newPath = path.replace(/^\/en(?=\/|$)/, '') || '/';
        if (!newPath.startsWith('/')) newPath = '/' + newPath;
        return newPath + location.search + location.hash;
      }
      return null;  // already on correct lang, no-op
    }

    function switchTo(lang) {
      if (!DN.LANG_KEY[lang]) return;
      DN.setLang(lang);
      const target = targetUrlFor(lang);
      if (target) {
        location.href = target;
      } else if (typeof onChange === 'function') {
        // Same language — call onChange but skip navigation
        onChange(lang);
      }
    }

    // Dropdown form: <select id="langToggle">
    if (toggle.tagName === 'SELECT') {
      toggle.value = DN.detectLang();
      toggle.addEventListener('change', function () {
        switchTo(toggle.value);
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
        switchTo(btn.dataset.lang);
        syncActive(btn.dataset.lang);
      });
    });
    syncActive(DN.detectLang());
  };

  // ─────────────────────────────────────────────────────────────────────
  // Article image enlarger + a11y / perf attrs
  // - Sizes inline images in .prose to fill content width (80%-100%)
  // - Adds loading="lazy" / decoding="async" if missing
  // - Adds wide max for SVG infographics
  // - Adds light box-shadow + rounded corners for visual polish
  // ─────────────────────────────────────────────────────────────────────
  // ─────────────────────────────────────────────────────────────────────
  // Medical SVG diagram library — reusable, evidence-based mechanism diagrams
  // Each diagram is named, auto-keyed to relevant article slugs, and inserted
  // at strategic h2 boundaries inside the article body.
  // Sources noted in comments — based on AAD / DermNet / 2024 guidelines.
  // ─────────────────────────────────────────────────────────────────────
  // Medical diagrams live in blog-diagrams(.min).js and are loaded on demand.
  // Medical diagram injector lives in blog-article-reading(.min).js and loads SVG diagrams on demand.

  // ─────────────────────────────────────────────────────────────────────
  // Magazine cover/feature illustrations — 400x300 SVGs themed per article tag.
  // Used by index.html randomization script to swap .mag-card-cover content
  // so the cover-story / editor-pick illustrations always match the picked
  // article. Cream + teal palette to match magazine layout.
  // ─────────────────────────────────────────────────────────────────────
  // Article hero covers and image lightbox live in blog-article-visuals(.min).js.
  DN.ensureArticleVisualBundle = function () {
    if (DN.injectArticleHero && DN.enhanceArticleImages) return Promise.resolve();
    if (!DN._articleVisualBundleLoading) {
      DN._articleVisualBundleLoading = new Promise(function (resolve, reject) {
        var s = document.createElement('script');
        s.src = '/blog/blog-article-visuals.min.js?v=202609060300';
        s.defer = true;
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
      }).catch(function (err) {
        // CODE_REVIEW — reset on failure so transient network errors
        // (offline blip, slow DNS) don't permanently block the bundle
        // for the rest of the session. Next caller retries cleanly.
        DN._articleVisualBundleLoading = null;
        throw err;
      });
    }
    return DN._articleVisualBundleLoading;
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
    btn.title = '回到頂端';
    btn.innerHTML = '↑';
    // Position adapts:
    //   - desktop article: font-sizer at bottom:24px (~130px tall) → totop at 182px above
    //   - mobile article: font-sizer pushed to bottom:88px (above sticky-CTA bar 64px)
    //     → totop sits at bottom:240px to clear the font-sizer (88+130+gap)
    //   - mobile non-article: no font-sizer, sticky-CTA at bottom — totop at bottom:88px
    //   - desktop non-article: nothing in the way → totop at bottom:24px
    var hasFontSizer = !!document.querySelector('.prose, #proseZh, .prose-zh');
    var isMobile = (typeof window !== 'undefined') && window.matchMedia && window.matchMedia('(max-width: 767px)').matches;
    // 2026-05-08 — bumped clearances so 回到頂端 button doesn't visually overlap
    // the font-sizer (S/M/L/XL pill, ~132px tall). Was 182/240; now 196/260
    // to leave a comfortable ~12-16px gap above the font-sizer.
    var bottomPos = hasFontSizer
      ? (isMobile ? '260px' : '200px')
      : (isMobile ? '96px'  : '24px');
    btn.style.cssText = 'position:fixed;right:18px;bottom:' + bottomPos + ';width:42px;height:42px;border-radius:50%;background:linear-gradient(180deg,#a4b5a8,#4d6358);color:#fff;border:1px solid rgba(12,81,89,.5);box-shadow:0 8px 20px -8px rgba(12,81,89,.55);cursor:pointer;display:none;align-items:center;justify-content:center;z-index:50;font-size:18px;line-height:1;transition:transform .2s,opacity .2s';
    btn.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
    btn.addEventListener('mouseenter', function () { btn.style.transform = 'translateY(-2px) scale(1.05)'; });
    btn.addEventListener('mouseleave', function () { btn.style.transform = ''; });
    document.body.appendChild(btn);
    var threshold = hasFontSizer ? 800 : 600;
    window.addEventListener('scroll', function () {
      btn.style.display = window.scrollY > threshold ? 'flex' : 'none';
    }, { passive: true });
  };

  // -----------------------------------------------------------------------
  // Cmd+K / Ctrl+K full-text search modal
  // Searches DN.ARTICLES (title + tag) and headers (h2) on current page.
  // -----------------------------------------------------------------------
  DN.initCmdK = function () {
    if (document.getElementById('dn-cmdk-style')) return;
    var st = document.createElement('style');
    st.id = 'dn-cmdk-style';
    st.textContent =
      '#dn-cmdk-overlay{position:fixed;inset:0;background:rgba(42,38,32,.55);z-index:9998;display:none;align-items:flex-start;justify-content:center;padding:88px 18px 18px;backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px)}' +
      '#dn-cmdk-overlay.open{display:flex}' +
      '#dn-cmdk-modal{width:100%;max-width:640px;background:var(--surface,#fff);border:1px solid var(--border,#dcd5c8);border-radius:14px;box-shadow:0 30px 80px -20px rgba(0,0,0,.35);overflow:hidden;font-family:Inter,system-ui,sans-serif}' +
      '#dn-cmdk-input{width:100%;padding:18px 20px;border:0;border-bottom:1px solid var(--border,#dcd5c8);font-size:16px;outline:none;background:transparent;color:var(--ink,#2a2620);font-family:inherit}' +
      '#dn-cmdk-results{max-height:60vh;overflow:auto;padding:8px 0}' +
      '#dn-cmdk-results .row{display:flex;flex-direction:column;gap:2px;padding:10px 20px;cursor:pointer;border-left:3px solid transparent;text-decoration:none;color:var(--ink,#2a2620)}' +
      '#dn-cmdk-results .row.active{background:var(--mint-soft,#dcd9d1);border-left-color:var(--teal-deep,#4d6358)}' +
      '#dn-cmdk-results .row .t{font-family:"Noto Serif TC",Georgia,serif;font-size:14.5px;font-weight:600;line-height:1.4}' +
      '#dn-cmdk-results .row .m{font-size:11.5px;color:var(--muted,#8b8378);font-family:Inter,monospace;letter-spacing:.06em}' +
      '#dn-cmdk-empty{padding:24px;text-align:center;font-size:13px;color:var(--muted,#8b8378)}' +
      '#dn-cmdk-foot{padding:10px 20px;border-top:1px solid var(--border,#dcd5c8);font-size:11px;color:var(--muted,#8b8378);font-family:Inter,monospace;letter-spacing:.04em;display:flex;gap:14px;flex-wrap:wrap;background:var(--paper-deep,#ede7da)}' +
      '#dn-cmdk-foot kbd{padding:1px 6px;border:1px solid var(--border,#dcd5c8);border-radius:3px;background:#fff;font-family:inherit;font-size:10.5px}';
    document.head.appendChild(st);

    var overlay = document.createElement('div');
    overlay.id = 'dn-cmdk-overlay';
    var isEn = (DN.detectLang && DN.detectLang() === 'en');
    var ph = isEn
      ? 'Search articles / topics / calculators… (press Esc to close)'
      : '搜尋文章 / 主題 / 量表⋯ （按 Esc 關閉）';
    overlay.innerHTML =
      '<div id="dn-cmdk-modal" role="dialog" aria-label="' + (isEn ? 'Search' : '搜尋') + '">' +
        '<input id="dn-cmdk-input" type="text" aria-label="搜尋 / Search" placeholder="' + ph + '" autocomplete="off" spellcheck="false" data-zh-placeholder="搜尋文章 / 主題 / 量表⋯ （按 Esc 關閉）" data-en-placeholder="Search articles / topics / calculators… (press Esc to close)" />' +
        '<div id="dn-cmdk-results"></div>' +
        '<div id="dn-cmdk-foot">' +
          '<span><kbd>↑</kbd><kbd>↓</kbd> <span data-zh="移動" data-en="navigate">移動</span></span>' +
          '<span><kbd>Enter</kbd> <span data-zh="開啟" data-en="open">開啟</span></span>' +
          '<span><kbd>Esc</kbd> <span data-zh="關閉" data-en="close">關閉</span></span>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);

    var input = overlay.querySelector('#dn-cmdk-input');
    var results = overlay.querySelector('#dn-cmdk-results');
    var activeIdx = 0;
    var currentMatches = [];

    function escapeHtml(value) {
      return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function safeSiteUrl(value) {
      var url = String(value || '').replace(/[\u0000-\u001f\u007f]/g, '');
      if (url[0] !== '/' || url[1] === '/' || url.includes('\\')) return '/';
      return url;
    }

    function safeSlug(value) {
      var slug = String(value || '');
      return /^[a-z0-9-]+$/.test(slug) ? slug : '';
    }

    function buildIndex() {
      var idx = [];
      // From DN.ARTICLES
      (DN.ARTICLES || []).forEach(function (a) {
        var slug = safeSlug(a.slug);
        if (!slug) return;
        idx.push({
          title: a.title || a.slug,
          meta: (a.tag || '') + ' · ' + (a.date || ''),
          url: '/blog/' + slug,
          search: ((a.title || '') + ' ' + (a.tag || '') + ' ' + (a.tag_en || '') + ' ' + slug).toLowerCase()
        });
      });
      // Tools / glossary / about / dashboard quick-jumps
      [
        { title: '量表計算器', meta: 'Tools · 10 個臨床量表', url: '/tools', search: 'tools 量表 計算 scorad pasi dlqi' },
        { title: '醫學詞彙白話字典', meta: 'Glossary', url: '/glossary', search: 'glossary 詞彙 字典 名詞' },
        { title: '主題地圖', meta: 'Topic Map', url: '/blog/topics', search: 'topics 主題 地圖' },
        { title: '關於作者', meta: 'About', url: '/about', search: 'about 作者 陳翊嘉' },
        { title: '衛教文章索引', meta: 'Articles', url: '/blog/', search: 'blog articles 文章 索引' },
      ].forEach(function (it) { idx.push(it); });
      return idx;
    }
    var INDEX = null;
    var FULLTEXT_LOADED = false;

    // Lazy-load /assets/search-index.json on first open. Merges H2/H3 headings +
    // snippet into existing entries by slug match, so search hits article body content.
    function loadFulltextIndex() {
      if (FULLTEXT_LOADED) return Promise.resolve();
      // CODE_REVIEW 2026-05-26 — latch FULLTEXT_LOADED only on SUCCESS. It was
      // set true synchronously before the fetch, so one transient failure
      // (offline at the first Cmd-K) latched it forever and the full-text index
      // never loaded again that session, permanently degrading search to
      // title/tag-only. A failed attempt now leaves it false so search retries.
      return fetch('/assets/search-index.json', { credentials: 'omit' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (!Array.isArray(data) || !INDEX) return;
          FULLTEXT_LOADED = true;
          var bySlug = {};
          data.forEach(function (e) { bySlug[e.slug] = e; });
          INDEX.forEach(function (it) {
            var slug = it.url.replace(/^\/blog\//, '').replace(/\/$/, '');
            var e = bySlug[slug];
            if (e) {
              var extra = ' ' + (e.h || []).join(' ') + ' ' + (e.snippet || '');
              it.search = (it.search + extra).toLowerCase();
              if (e.snippet && !it.meta.includes('—')) it.meta = it.meta + ' — ' + e.snippet.slice(0, 50);
            }
          });
        })
        .catch(function () { /* offline ok */ });
    }

    // 2026-05-17 — Pagefind integration. Lazy-load /pagefind/pagefind.js on
    // first open() so the substring fallback works immediately while
    // the CJK-aware BM25 index loads in the background. When pagefind
    // resolves, future renders use pagefind.search() instead of the
    // INDEX substring scan.
    var PAGEFIND = null;
    var PAGEFIND_LOADING = false;
    function loadPagefind() {
      if (PAGEFIND || PAGEFIND_LOADING) return;
      PAGEFIND_LOADING = true;
      // Use fetch+import dance because Vite/Pagefind module path is hard-coded.
      import('/pagefind/pagefind.js').then(function (mod) {
        PAGEFIND = mod;
        // Re-render with pagefind if the overlay is still open
        if (overlay.classList.contains('open')) render(input.value);
      }).catch(function () {
        // Index not built locally (dev) — silently fall back to INDEX.
        PAGEFIND_LOADING = false;
      });
    }

    function open() {
      if (!INDEX) INDEX = buildIndex();
      overlay.classList.add('open');
      input.value = '';
      input.focus();
      render('');
      // Kick off lazy loads — both pagefind (preferred) and the legacy
      // fulltext json (fallback). Whichever responds first wins next render.
      loadPagefind();
      loadFulltextIndex().then(function () { if (overlay.classList.contains('open')) render(input.value); });
    }
    function close() {
      overlay.classList.remove('open');
    }

    function renderPagefind(q) {
      if (!PAGEFIND) return false;  // signal fallback to substring path
      // PAGEFIND.search is async; show "searching" placeholder, then update
      PAGEFIND.search(q).then(function (res) {
        if (!overlay.classList.contains('open') || input.value.toLowerCase().trim() !== q) return;
        Promise.all(res.results.slice(0, 10).map(function (r) { return r.data(); })).then(function (datas) {
          // CODE_REVIEW Phase 5 — re-check freshness AFTER the r.data() batch
          // resolves, not just after PAGEFIND.search(). A slower earlier query
          // could otherwise land its data() here and clobber a newer query's
          // results. (blog/pagefind-search.js already re-checks at both stages.)
          if (!overlay.classList.contains('open') || input.value.toLowerCase().trim() !== q) return;
          var matches = datas.map(function (d) {
            // Drop the URL query/hash; show title + excerpt as meta
            var clean = d.url.split('?')[0].split('#')[0];
            return { url: clean, title: d.meta.title || clean, meta: d.excerpt || (d.meta.description || '').slice(0, 80) };
          });
          currentMatches = matches; activeIdx = 0;
          if (matches.length === 0) {
            results.innerHTML = '<div id="dn-cmdk-empty">找不到符合的內容</div>';
            return;
          }
          results.innerHTML = matches.map(function (m, i) {
            return '<a class="row' + (i === 0 ? ' active' : '') + '" href="' + escapeHtml(safeSiteUrl(m.url)) + '" data-idx="' + i + '">' +
              '<span class="t">' + escapeHtml(m.title) + '</span>' +
              // CODE_REVIEW Phase 5 — the pagefind excerpt was inserted raw.
              // Strip its <mark> highlight tags, then escape, so the sink is safe
              // AND we don't render literal "<mark>…</mark>" text. Highlight is
              // dropped here (matches the substring path + stays within the
              // shared-runtime size budget, TD-12); the dedicated /search modal
              // (pagefind-search.js) keeps highlights via its own sanitizer.
              '<span class="m">' + escapeHtml(String(m.meta || '').replace(/<\/?mark>/gi, '')) + '</span>' +
              '</a>';
          }).join('');
        });
      });
      return true;
    }

    function render(q) {
      q = (q || '').toLowerCase().trim();
      // Prefer pagefind once it's loaded
      if (q && renderPagefind(q)) return;
      var matches;
      if (!q) {
        matches = INDEX.slice(0, 8);
      } else {
        matches = INDEX
          .map(function (it) { return { it: it, s: it.search.indexOf(q) >= 0 ? (it.search.indexOf(q) === 0 ? 100 : 50) : (q.split('').every(function (c) { return it.search.indexOf(c) >= 0; }) ? 1 : 0) }; })
          .filter(function (x) { return x.s > 0; })
          .sort(function (x, y) { return y.s - x.s; })
          .slice(0, 10)
          .map(function (x) { return x.it; });
      }
      currentMatches = matches;
      activeIdx = 0;
      if (matches.length === 0) {
        results.innerHTML = '<div id="dn-cmdk-empty">找不到符合的內容</div>';
        return;
      }
      results.innerHTML = matches.map(function (m, i) {
        return '<a class="row' + (i === 0 ? ' active' : '') + '" href="' + escapeHtml(safeSiteUrl(m.url)) + '" data-idx="' + i + '">' +
          '<span class="t">' + escapeHtml(m.title) + '</span>' +
          '<span class="m">' + escapeHtml(m.meta || '') + '</span>' +
        '</a>';
      }).join('');
    }
    function setActive(i) {
      activeIdx = Math.max(0, Math.min(currentMatches.length - 1, i));
      var rows = results.querySelectorAll('.row');
      rows.forEach(function (r, j) { r.classList.toggle('active', j === activeIdx); });
      var act = rows[activeIdx];
      if (act) act.scrollIntoView({ block: 'nearest' });
    }
    function go() {
      var m = currentMatches[activeIdx];
      if (m) {
        try {
          if (typeof gtag === 'function') gtag('event', 'search_result_click', {
            search_term: (input.value || '').slice(0, 80),
            result_url: m.url,
            result_position: activeIdx,
          });
        } catch (e) {}
        location.href = safeSiteUrl(m.url);
      }
    }

    // Public API for static nav button to call
    DN.openSearch = open;
    DN.closeSearch = close;

    input.addEventListener('input', function () { render(input.value); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setActive(activeIdx + 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(activeIdx - 1); }
      else if (e.key === 'Enter') { e.preventDefault(); go(); }
      else if (e.key === 'Escape') { close(); }
    });
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close();
    });

    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (overlay.classList.contains('open')) close(); else open();
      } else if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        open();
      }
    });

    // Wire up search button in header (button[aria-label="搜尋"])
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('button[aria-label="搜尋"]');
      if (btn) { e.preventDefault(); open(); }
    });
  };

  // -----------------------------------------------------------------------
  // Dark Mode — prefers-color-scheme auto + manual toggle (☀ ↔ 🌙)
  // Persists choice to localStorage. Overrides --bg/--ink/--surface tokens.
  // -----------------------------------------------------------------------
  DN.initDarkMode = function () {
    if (document.getElementById('dn-dark-style')) return;
    var st = document.createElement('style');
    st.id = 'dn-dark-style';
    st.textContent =
      ':root[data-theme="dark"] { --bg:#1f1c17; --surface:#27231d; --ink:#ede7da; --ink-2:#c9c2b3; --muted:#8b8378; --teal:#a4b5a8; --teal-deep:#c9d6cf; --teal-bright:#7a9285; --mint-soft:#3a352c; --border:#3a352c; --line:#2e2924; }' +
      ':root[data-theme="dark"] body{ background:var(--bg); color:var(--ink); }' +
      ':root[data-theme="dark"] body::before{ background:radial-gradient(800px 500px at 12% -8%, rgba(164,181,168,.08), transparent 60%), linear-gradient(180deg,#1f1c17 0%, #27231d 40%, #1f1c17 100%) !important; }' +
      ':root[data-theme="dark"] .card, :root[data-theme="dark"] .mag-card, :root[data-theme="dark"] .cv-card{ background:var(--surface); }' +
      ':root[data-theme="dark"] header.sticky{ background:rgba(31,28,23,.92) !important; }' +
      ':root[data-theme="dark"] .hover\\:bg-mint-100:hover{ background:#3a352c !important; }' +
      ':root[data-theme="dark"] .text-ink-700, :root[data-theme="dark"] .text-ink-900{ color:var(--ink) !important; }' +
      ':root[data-theme="dark"] .text-ink-500{ color:var(--ink-2) !important; }' +
      ':root[data-theme="dark"] .text-teal-700{ color:var(--teal-deep) !important; }' +
      ':root[data-theme="dark"] .bg-mint-50, :root[data-theme="dark"] .bg-mint-100{ background:var(--surface) !important; }' +
      ':root[data-theme="dark"] .bg-white{ background:var(--surface) !important; }' +
      // Inline white-bg cards — match boundary so #fff7ed / #fff3c7 (warning shades) are NOT caught
      ':root[data-theme="dark"] [style*="background:#fff;"], :root[data-theme="dark"] [style*="background: #fff;"], :root[data-theme="dark"] [style*="background:#fff\""], :root[data-theme="dark"] [style*="background:#FFFFFF;"], :root[data-theme="dark"] [style*="background:white;"], :root[data-theme="dark"] [style*="background: white;"], :root[data-theme="dark"] [style*="background-color:#fff;"], :root[data-theme="dark"] [style*="background-color:#fff\""]{ background:var(--surface) !important; color:var(--ink) !important; }' +
      // Inline color:#0f172a / #1f2937 (slate ink for cards) — flip to light text in dark mode
      ':root[data-theme="dark"] [style*="color:#0f172a"], :root[data-theme="dark"] [style*="color:#1f2937"], :root[data-theme="dark"] [style*="color:#111827"]{ color:var(--ink) !important; }' +
      // Tables with white bg + dark text
      ':root[data-theme="dark"] table[style*="background:#fff"]{ background:var(--surface) !important; color:var(--ink) !important; }' +
      ':root[data-theme="dark"] th[style*="background:#fff"], :root[data-theme="dark"] td[style*="background:#fff"]{ background:var(--surface) !important; color:var(--ink) !important; }' +
      // Warning / info / success tinted boxes — keep tint but darken slightly so contrast works
      ':root[data-theme="dark"] [style*="background:#fff7ed"]{ background:#3a2818 !important; color:#fed7aa !important; border-color:#9a3412 !important; }' +
      ':root[data-theme="dark"] [style*="background:#fef3c7"], :root[data-theme="dark"] [style*="background:#fef9c3"]{ background:#332a14 !important; color:#fde68a !important; }' +
      ':root[data-theme="dark"] [style*="background:#fee2e2"], :root[data-theme="dark"] [style*="background:#fef2f2"]{ background:#3a1a1a !important; color:#fca5a5 !important; }' +
      ':root[data-theme="dark"] [style*="background:#dcfce7"], :root[data-theme="dark"] [style*="background:#ecfdf5"]{ background:#0f2a1a !important; color:#86efac !important; }' +
      ':root[data-theme="dark"] [style*="background:#cffafe"], :root[data-theme="dark"] [style*="background:#ecfeff"]{ background:#0c2a2e !important; color:#a5f3fc !important; }' +
      ':root[data-theme="dark"] [style*="background:#ebe4d8"], :root[data-theme="dark"] [style*="background:#dcd9d1"]{ background:#2e2924 !important; color:var(--ink) !important; }' +
      '#dn-theme-toggle{ background:transparent; border:1px solid var(--border); border-radius:9999px; width:32px;height:32px;padding:0;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;font-size:14px;line-height:1;transition:background .15s,border-color .15s;color:var(--ink) }' +
      '#dn-theme-toggle:hover{ background:var(--mint-soft); border-color:var(--teal-deep); }' +
      '@media (prefers-reduced-motion: no-preference){ html { transition:background-color .25s, color .25s } }';
    document.head.appendChild(st);

    function getPref() {
      try { return localStorage.getItem('dn-theme'); } catch (e) { return null; }
    }
    function setPref(v) {
      try { v ? localStorage.setItem('dn-theme', v) : localStorage.removeItem('dn-theme'); } catch (e) {}
    }
    function detect() {
      var saved = getPref();
      if (saved === 'dark' || saved === 'light') return saved;
      return (window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
    }
    function apply(theme) {
      document.documentElement.setAttribute('data-theme', theme);
      var btn = document.getElementById('dn-theme-toggle');
      if (btn) {
        btn.textContent = theme === 'dark' ? '☀' : '🌙';
        var isEn = (DN.detectLang && DN.detectLang() === 'en');
        var zhLabel = theme === 'dark' ? '切換到亮色' : '切換到暗色';
        var enLabel = theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
        btn.setAttribute('data-zh-aria-label', zhLabel);
        btn.setAttribute('data-en-aria-label', enLabel);
        btn.setAttribute('aria-label', isEn ? enLabel : zhLabel);
      }
    }
    apply(detect());

    // R25: skip injecting a separate toggle — static #dn-nav-theme button handles UX.
    // Just keep the auto-apply + media-query sync logic above.

    // Sync with system theme changes (only if no manual pref)
    if (window.matchMedia) {
      matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
        if (!getPref()) apply(e.matches ? 'dark' : 'light');
      });
    }
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
      toast.innerHTML = '<span>網站已更新 — </span><button type="button" style="background:#fff;color:#4d6358;border:none;padding:5px 12px;border-radius:9999px;font-weight:700;font-size:12px;cursor:pointer">重新載入</button>';
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
    // R25: skip — static <nav class="dn-nav"> now handles flat + mobile burger
    if (document.querySelector('.dn-nav') || document.getElementById('dn-nav-burger')) return;
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
  // Slug allow-lists for the heavy on-demand bundles. Kept in sync (by hand
  // — there's a Python audit) with the keys of DN.MED_DIAGRAM_MAP (in
  // blog-diagrams.js) and DN.CALC_ORDER (in blog-calculators.js). Before
  // these existed, every article paid for the ~100 KB diagrams bundle and
  // the ~57 KB calculators bundle even when its slug had no entry in the
  // respective map — pure overhead on ~21 and ~30 articles respectively.
  //
  // If you add a new article that needs diagrams or a calculator, ALSO add
  // its slug here. Drift is caught by check_diagram_calc_slug_lists() in
  // _check_meta.py.
  // -----------------------------------------------------------------------
  DN.DIAGRAM_SLUGS = ['acne-myths','acne-scar-treatment','alopecia-areata','atopic-dermatitis-overview','biologics-overview','cutaneous-t-cell-lymphoma','epidermoid-cyst','hairloss-myths','hidradenitis-suppurativa','isotretinoin-clinical','isotretinoin-patient','laser-dermatology','melasma-myths','mpox-care','pediatric-eczema','prurigo-nodularis','psoriasis-myths','rosacea-myths','shingles-myths','sunscreen-myths','targeted-therapy-skin','tinea-myths','topical-acids-clinical','topical-acids-patient','topical-steroids-guide','urticaria-myths','vitiligo','warts-myths'];
  DN.CALC_SLUGS    = ['acne-myths','acne-scar-treatment','alopecia-areata','atopic-dermatitis-overview','biologics-overview','cutaneous-t-cell-lymphoma','dermatology-faq','epidermoid-cyst','hairloss-myths','hidradenitis-suppurativa','isotretinoin-clinical','isotretinoin-patient','laser-dermatology','melasma-myths','mpox-care','nhi-derm-drugs','pediatric-eczema','prurigo-nodularis','psoriasis-myths','rosacea-myths','shingles-myths','skin-whitening-agents','sunscreen-myths','targeted-therapy-skin','tinea-myths','topical-acids-clinical','topical-acids-patient','topical-steroids-guide','urticaria-myths','vitiligo','warts-myths'];

  // -----------------------------------------------------------------------
  // Article catalog (single source of truth for related-articles / TOC links).
  // -----------------------------------------------------------------------
  DN.ARTICLES = [
    { slug:'acne-myths',          title:'痘痘 8 大迷思', title_en:'8 Acne Myths', cat:'myth', tag:'痘痘', date:'2026-05-07', emoji:'', tag_en:'Acne' },
    { slug:'sunscreen-myths',     title:'防曬 8 大迷思', title_en:'8 Sunscreen Myths', cat:'myth', tag:'防曬', date:'2026-05-03', emoji:'', tag_en:'Sunscreen' },
    { slug:'melasma-myths',       title:'肝斑 7 大迷思', title_en:'7 Melasma Myths', cat:'myth', tag:'肝斑', date:'2026-05-03', emoji:'', tag_en:'Melasma' },
    { slug:'rosacea-myths',       title:'玫瑰痤瘡 6 大迷思', title_en:'Rosacea myths', cat:'myth', tag:'酒糟肌', date:'2026-05-03', emoji:'', tag_en:'Rosacea' },
    { slug:'perioral-dermatitis-guide', title:'嘴角紅疹是痘痘還是濕疹？口周皮膚炎完整衛教', title_en:'Perioral / Periorificial dermatitis: complete guide', cat:'rx', tag:'口周皮膚炎', date:'2026-05-13', emoji:'', tag_en:'Perioral dermatitis' },
    { slug:'toenail-mechanical-disorders', title:'腳趾甲變形 12 種型態完整圖鑑 — 從鞋子、腳型、關節到糖尿病', title_en:'Toenail mechanical disorders: complete patient guide', cat:'rx', tag:'趾甲與足部', date:'2026-05-13', emoji:'', tag_en:'Toenail disorders' },
    { slug:'dermatologic-oral-examination', title:'嘴破、白斑、牙齦剝離 — 什麼時候該找皮膚科？口腔黏膜檢查與切片完整指南', title_en:'Oral mucosa: when to see a dermatologist — exam and biopsy guide', cat:'rx', tag:'口腔黏膜', date:'2026-05-13', emoji:'', tag_en:'Oral mucosa' },
    { slug:'severe-scabies-treatment', title:'嚴重疥瘡為什麼治不好？口服 ivermectin + 外用 permethrin 完整治療指南', title_en:'Severe scabies: complete ivermectin + permethrin treatment guide', cat:'rx', tag:'疥瘡', date:'2026-05-13', emoji:'', tag_en:'Scabies', unpublished:true },
    { slug:'dupilumab-long-term-maintenance', title:'杜避炎要打多久？停藥、減量與維持治療的研究整理', title_en:'Dupilumab: How Long, When to Stop, and Maintenance Treatment', cat:'research', tag:'dupilumab', date:'2026-05-15', emoji:'', tag_en:'Dupilumab' },
    { slug:'psoriasis-biologic-monitoring', title:'打乾癬生物製劑要不要每年抽血？2026 JAAD 證據評級重新看這件事', title_en:'Do you really need annual blood tests on psoriasis biologics? A 2026 JAAD evidence-grade reappraisal', cat:'research', tag:'生物製劑安全', date:'2026-05-16', emoji:'', tag_en:'Biologic safety' },
    { slug:'ai-dermatology-roles', title:'AI 現在能幫皮膚科醫師看病嗎？2026 三篇 JAAD 研究的綜合解答', title_en:'Can AI help dermatologists today? A synthesis of three 2026 JAAD studies', cat:'research', tag:'AI 與皮膚科', date:'2026-05-23', emoji:'', tag_en:'AI in dermatology' },
    { slug:'vitiligo-maintenance-clinical', title:'白斑停藥後會復發嗎？維持治療與復發風險評估', title_en:'Does vitiligo relapse after stopping? Maintenance and risk assessment', cat:'research', tag:'白斑復發', date:'2026-05-23', emoji:'', tag_en:'Vitiligo relapse' },
    { slug:'semaglutide-hair-loss', title:'打瘦瘦針會掉頭髮嗎？2026 兩篇 TriNetX 大型研究的雙向解答', title_en:'Does semaglutide cause hair loss? Bidirectional answer from two 2026 TriNetX studies', cat:'research', tag:'GLP-1 與落髮', date:'2026-05-23', emoji:'', tag_en:'GLP-1 & hair loss' },
    { slug:'spironolactone-dermatology-safety', title:'Spironolactone 在皮膚科安全嗎？2026 JAAD 兩篇研究：≥45 歲女性高血鉀風險與合併 minoxidil 開立指南', title_en:'Is spironolactone safe in dermatology? JAAD 2026: hyperkalemia in women ≥45 and combination LDOM prescribing', cat:'research', tag:'Spironolactone 安全性', date:'2026-05-26', emoji:'', tag_en:'Spironolactone safety' },
    { slug:'jaki-switching-alopecia-areata', title:'第一種 JAK 抑制劑治圓禿失敗，換第二種有用嗎？2026 JAAD 108 人換藥真實數據', title_en:'Does switching JAK inhibitors work for alopecia areata? Real-world data from 108 switches (JAAD 2026)', cat:'research', tag:'圓禿 JAK 換藥', date:'2026-05-26', emoji:'', tag_en:'JAKi switching' },
    { slug:'nail-psoriasis-topical-intralesional', title:'指甲乾癬怎麼治？擦藥、病灶內注射到雷射輔助穿透：2026 JAAD 評論的局部治療整理', title_en:'How is nail psoriasis treated? Topical, intralesional, and laser-assisted delivery — a 2026 JAAD editorial review', cat:'research', tag:'指甲乾癬治療', date:'2026-05-31', emoji:'', tag_en:'Nail psoriasis therapy' },
    { slug:'bimekizumab-hidradenitis-suppurativa', title:'化膿性汗腺炎打 bimekizumab 有效嗎？IL-17A/F 雙抑制與 BE-HEARD I/II 三期試驗的嚴格評讀', title_en:'Does bimekizumab work for hidradenitis suppurativa? A critical appraisal of the BE-HEARD I/II phase III trials', cat:'research', tag:'化膿性汗腺炎生物製劑', date:'2026-06-05', emoji:'', tag_en:'HS biologic (bimekizumab)' },
    { slug:'photodynamic-therapy-overview', title:'光動力治療（PDT）皮膚科完整指南 — 從 AK、BCC 到痘痘的 2026 JAAD 雙篇 Review 整合', title_en:'Photodynamic Therapy (PDT) Complete Guide — from AK and BCC to acne, synthesis of two 2026 JAAD Reviews', cat:'research', tag:'光動力治療', date:'2026-05-23', emoji:'', tag_en:'Photodynamic therapy' },
    { slug:'hairloss-myths',      title:'落髮 / 雄性禿 7 大迷思', title_en:'7 Hair Loss & Male Pattern Baldness Myths', cat:'myth', tag:'落髮', date:'2026-05-03', emoji:'', tag_en:'Hair loss' },
    { slug:'tinea-myths',         title:'香港腳 / 灰指甲 7 大迷思', title_en:'7 Athlete\'s Foot / Nail Fungus Myths', cat:'myth', tag:'足癬', date:'2026-05-03', emoji:'', tag_en:'Tinea' },
    { slug:'urticaria-myths',     title:'蕁麻疹 6 大迷思', title_en:'6 Urticaria (Hives) Myths', cat:'myth', tag:'蕁麻疹', date:'2026-05-07', emoji:'', tag_en:'Urticaria' },
    { slug:'psoriasis-myths',     title:'乾癬 7 大迷思', title_en:'7 Psoriasis Myths', cat:'myth', tag:'乾癬', date:'2026-05-07', emoji:'', tag_en:'Psoriasis' },
    { slug:'warts-myths',         title:'病毒疣 6 大迷思', title_en:'Warts myths', cat:'myth', tag:'病毒疣', date:'2026-05-04', emoji:'', tag_en:'Warts' },
    { slug:'contact-dermatitis',  title:'接觸性皮膚炎(過敏 vs 刺激)完整衛教', title_en:'Contact dermatitis', cat:'rx', tag:'接觸性皮膚炎', date:'2026-05-08', emoji:'', tag_en:'Contact dermatitis' },
    { slug:'actinic-keratosis-scc', title:'日光性角化症 AK + 鱗狀細胞癌 SCC 完整衛教', title_en:'Actinic keratosis + cutaneous squamous cell carcinoma', cat:'rx', tag:'皮膚癌', date:'2026-05-08', emoji:'', tag_en:'AK / SCC' },
    { slug:'skin-biopsy-excision', title:'皮膚切片與腫瘤切除手術完整衛教 — 為什麼要切？怎麼切？術後怎麼照顧？', title_en:'Skin biopsy & tumor excision: complete guide', cat:'rx', tag:'處置 / 手術', date:'2026-05-09', emoji:'', tag_en:'Skin biopsy & excision' },
    { slug:'psoriasis-overview',  title:'乾癬完整衛教 — 分型、嚴重度、誘發因子', title_en:'Psoriasis: complete guide', cat:'rx', tag:'乾癬', date:'2026-05-09', emoji:'', tag_en:'Psoriasis overview' },
    { slug:'psoriasis-topical',   title:'乾癬外用藥治療 — 類固醇、維生素 D、特殊部位', title_en:'Topical therapy for psoriasis', cat:'rx', tag:'乾癬', date:'2026-05-09', emoji:'', tag_en:'Psoriasis topical' },
    { slug:'psoriasis-systemic',  title:'乾癬全身性治療 — 光療、口服、生物製劑', title_en:'Systemic therapy for psoriasis', cat:'rx', tag:'乾癬', date:'2026-05-09', emoji:'', tag_en:'Psoriasis systemic' },
    { slug:'psoriasis-special-populations', title:'乾癬合併症與特殊族群 — PsA、心血管、懷孕、兒童、指甲、紅皮症', title_en:'Psoriasis comorbidities & special populations', cat:'rx', tag:'乾癬', date:'2026-05-09', emoji:'', tag_en:'Psoriasis special populations' },
    { slug:'shingles-myths',      title:'帶狀皰疹 6 大迷思', title_en:'6 Shingles (Herpes Zoster) Myths', cat:'myth', tag:'皮蛇', date:'2026-05-04', emoji:'', tag_en:'Shingles' },
    { slug:'topical-acids-patient', title:'A酸、A醇、杜鵑花酸怎麼選？五大酸類差別與搭配', title_en:'Retinoids, Retinol and Azelaic Acid: Differences and Combinations', cat:'product', tag:'酸類', date:'2026-05-07', emoji:'', tag_en:'Topical acids' },
    { slug:'isotretinoin-patient',  title:'口服 A 酸完整衛教', title_en:'Oral Isotretinoin', cat:'rx', tag:'口服 A 酸', date:'2026-05-07', emoji:'', tag_en:'Isotretinoin' },
    { slug:'acne-scar-treatment',   title:'痘疤完整治療指引', title_en:'Acne scar treatment', cat:'rx', tag:'痘疤', date:'2026-05-07', emoji:'', tag_en:'Acne scars' },
    { slug:'alopecia-areata',     title:'圓禿（鬼剃頭）完整衛教', title_en:'Alopecia areata', cat:'rx', tag:'圓禿', date:'2026-05-04', emoji:'', tag_en:'Alopecia areata' },
    { slug:'vitiligo', title:'白斑（Vitiligo）完整衛教', title_en:'Vitiligo', cat:'rx', tag:'白斑', date:'2026-05-07', emoji:'', tag_en:'Vitiligo' },
    { slug:'mpox-care', title:'猴痘（Mpox）皮膚照護', title_en:'Monkeypox (Mpox) skin-care complete guide', cat:'rx', tag:'猴痘', date:'2026-05-04', emoji:'', tag_en:'Mpox' },
    { slug:'hidradenitis-suppurativa', title:'化膿性汗腺炎（HS）完整衛教', title_en:'Hidradenitis suppurativa (HS)', cat:'rx', tag:'化膿性汗腺炎', date:'2026-05-04', emoji:'', tag_en:'HS' },
    { slug:'targeted-therapy-skin', title:'標靶藥物（TKI）皮膚副作用', title_en:'Targeted-therapy (TKI) cutaneous side effects', cat:'rx', tag:'標靶藥物', date:'2026-05-04', emoji:'', tag_en:'Targeted therapy skin' },
    { slug:'topical-steroids-guide', title:'外用類固醇完整指南', title_en:'Topical steroids: complete guide', cat:'rx', tag:'外用類固醇', date:'2026-05-04', emoji:'', tag_en:'Topical steroids' },
    { slug:'biologics-overview', title:'皮膚科生物製劑與小分子標靶藥物總覽', title_en:'Dermatology biologics and small-molecule targeted drugs', cat:'rx', tag:'生物製劑', date:'2026-05-04', emoji:'', tag_en:'Biologics' },
    { slug:'skin-whitening-agents', title:'美白成分完整解析', title_en:'Brightening ingredients', cat:'product', tag:'美白', date:'2026-05-04', emoji:'', tag_en:'Whitening agents' },
    { slug:'dermatology-faq', title:'皮膚科 25 個最常見問題', title_en:'25 Most-asked Dermatology Questions', cat:'myth', tag:'常見問題', date:'2026-05-05', emoji:'', tag_en:'FAQ' },
    { slug:'epidermoid-cyst', title:'粉瘤完整衛教', title_en:'Epidermoid cyst', cat:'rx', tag:'粉瘤', date:'2026-05-05', emoji:'', tag_en:'Epidermoid cyst' },
    { slug:'nhi-derm-drugs', title:'皮膚科常用藥物健保規範完整整理', title_en:'Taiwan NHI rules for common dermatology drugs', cat:'rx', tag:'健保規範', date:'2026-05-07', emoji:'', tag_en:'NHI rules' },
    { slug:'laser-dermatology', title:'皮膚科雷射完整對照', title_en:'Dermatologic laser comparison', cat:'rx', tag:'雷射 / 光電', date:'2026-05-05', emoji:'', tag_en:'Laser dermatology' },
    { slug:'pediatric-eczema', title:'嬰幼兒 / 兒童異位性皮膚炎完整照護指南', title_en:'Infant & pediatric atopic dermatitis', cat:'rx', tag:'異位性皮膚炎', date:'2026-05-05', emoji:'', tag_en:'Atopic dermatitis' },
    { slug:'prurigo-nodularis', title:'結節性癢疹是什麼？Prurigo nodularis 中文、症狀與治療', title_en:'Prurigo Nodularis: Meaning, Symptoms and Treatment', cat:'rx', tag:'結節性癢疹', date:'2026-05-07', emoji:'', tag_en:'Prurigo Nodularis' },
    { slug:'cutaneous-t-cell-lymphoma', title:'皮膚 T 細胞淋巴瘤(CTCL/MF)完整衛教', title_en:'Cutaneous T-cell lymphoma (CTCL / MF)', cat:'rx', tag:'皮膚淋巴瘤', date:'2026-05-07', emoji:'', tag_en:'CTCL / MF' },
    { slug:'atopic-dermatitis-overview', title:'異位性皮膚炎完整指引 — 治療、共病評估、6 大迷思', title_en:'Atopic dermatitis: complete guide — treatment, comorbidities, 6 myths', cat:'rx', tag:'異位性皮膚炎', date:'2026-05-03', emoji:'', tag_en:'AD complete guide' },
    { slug:'atopic-dermatitis-topical',  title:'異位性皮膚炎外用治療 — 保濕、類固醇、TCI、PDE4、JAK 軟膏', title_en:'Topical therapy for atopic dermatitis', cat:'rx', tag:'異位性皮膚炎', date:'2026-05-09', emoji:'', tag_en:'AD topical' },
    { slug:'atopic-dermatitis-systemic', title:'異位性皮膚炎全身性治療 — 生物製劑、JAK 抑制劑、光療', title_en:'Systemic therapy for atopic dermatitis', cat:'rx', tag:'異位性皮膚炎', date:'2026-05-09', emoji:'', tag_en:'AD systemic' },
    { slug:'atopic-dermatitis-special-populations', title:'異位性皮膚炎合併症與特殊族群 — 過敏進行曲、心理、懷孕、感染', title_en:'AD comorbidities & special populations', cat:'rx', tag:'異位性皮膚炎', date:'2026-05-09', emoji:'', tag_en:'AD special populations' },  ];

  // -----------------------------------------------------------------------
  // Article numbering — assign #001-#NNN by chronological publish order
  // (date asc, then array order as tiebreaker for same-day publishes)
  // -----------------------------------------------------------------------
  // -----------------------------------------------------------------------
  // Publish state — admin can mark an article {unpublished:true} in the
  // catalog above to hide it from the live site (listings, sitemap, feeds,
  // related-articles, popular picks) without deleting. Admin can still
  // open and edit it normally. Direct URL still resolves but the article
  // gets a banner injected on initBlog().
  // -----------------------------------------------------------------------
  DN.isPublished = function (slug) {
    if (!slug) return true;
    var a = (DN.ARTICLES || []).find(function (x) { return x.slug === slug; });
    return !(a && a.unpublished);
  };
  DN.publishedArticles = function () {
    return (DN.ARTICLES || []).filter(function (a) { return !a.unpublished; });
  };
  DN.unpublishedSlugs = function () {
    return (DN.ARTICLES || []).filter(function (a) { return a.unpublished; }).map(function (a) { return a.slug; });
  };

  // Inject "本文暫時下架" banner at top of article body when the current
  // article is marked unpublished. Banner is visible to anyone who lands
  // on the direct URL (e.g. via bookmark) so they know it's not public.
  DN.injectUnpublishedBanner = function () {
    try {
      var slug = DN.currentSlug && DN.currentSlug();
      if (!slug) return;
      if (DN.isPublished(slug)) return;
      if (document.getElementById('dn-unpub-banner')) return;
      var b = document.createElement('div');
      b.id = 'dn-unpub-banner';
      b.style.cssText = 'position:sticky;top:0;z-index:60;background:#fef3c7;border-bottom:2px solid #ca8a04;color:#7c4a03;padding:10px 18px;font-size:13.5px;font-weight:600;text-align:center;font-family:Inter,"Noto Sans TC",sans-serif;line-height:1.6';
      b.setAttribute('data-zh', '⚠️ 本文目前已暫時下架，僅作者可見。一般訪客連結至此會看到此提示。');
      b.setAttribute('data-en', '⚠️ This article is temporarily unpublished. Only the author should see this URL.');
      b.textContent = '⚠️ 本文目前已暫時下架，僅作者可見。一般訪客連結至此會看到此提示。';
      var first = document.body.firstElementChild;
      document.body.insertBefore(b, first);
      // Also add noindex meta if not already there
      if (!document.querySelector('meta[name="robots"][content*="noindex"]')) {
        var m = document.createElement('meta');
        m.name = 'robots';
        m.content = 'noindex,nofollow';
        document.head.appendChild(m);
      }
    } catch (e) { /* ignore */ }
  };

  // -----------------------------------------------------------------------
  // Hide hardcoded homepage / blog-index article cards AND topic chips for
  // unpublished articles. Implemented via <style> injection so the rules
  // carry !important and reliably override per-element inline styles.
  // -----------------------------------------------------------------------
  DN.hideUnpublishedCards = function () {
    try {
      var slugs = DN.unpublishedSlugs();
      if (!slugs.length) return;
      if (document.getElementById('dn-unpub-css')) {
        document.getElementById('dn-unpub-css').remove();
      }
      var css = '';
      slugs.forEach(function (s) {
        // Article cards on homepage / blog index
        css += 'a.article-list-item[href="/blog/' + s + '"]{display:none!important}\n';
        css += 'a.article-list-item[href="/blog/' + s + '.html"]{display:none!important}\n';
        // Hub spotlight cards
        css += 'a.dn-spotlight-card[href="/blog/' + s + '"]{display:none!important}\n';
        css += 'li:has(> a.dn-spotlight-card[href="/blog/' + s + '"]){display:none!important}\n';
        // Topic chips on homepage (chip strip) — direct child of flex
        // container, not inside prose. Hide any link to the unpublished slug
        // EXCEPT inside header/main-prose (so admin-internal links stay).
        css += 'a[href="/blog/' + s + '"]:not(article a):not(.prose a):not(header a):not(blockquote a){display:none!important}\n';
      });
      var styleEl = document.createElement('style');
      styleEl.id = 'dn-unpub-css';
      styleEl.textContent = css;
      (document.head || document.documentElement).appendChild(styleEl);
    } catch (e) { /* ignore */ }
  };

  // Eagerly inject hide-unpublished CSS as soon as blog-shared.js finishes
  // parsing — DN.ARTICLES is already defined by then. This means hidden
  // cards never paint, even before DOMContentLoaded.
  try { DN.hideUnpublishedCards(); } catch (e) { /* ignore */ }

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

      var readZh = '已讀 ' + read + ' 篇 (' + pct + '%)';
      var readEn = read + ' read (' + pct + '%)';
      host.innerHTML =
        '<div style="background:#fff;border:1px solid var(--border, #dcd5c8);border-radius:14px;padding:18px 22px;box-shadow:0 1px 2px rgba(15,23,42,.04)">' +
          '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px">' +
            '<div>' +
              '<div data-zh="閱讀進度" data-en="Reading progress" style="font-size:11px;text-transform:uppercase;letter-spacing:.22em;color:#4d6358;font-weight:700;margin-bottom:2px">閱讀進度</div>' +
              '<div data-zh="' + readZh + '" data-en="' + readEn + '" style="font-family:\'Noto Serif TC\',Georgia,serif;font-size:18px;font-weight:700;color:#0f172a">' + readZh + '</div>' +
            '</div>' +
            (read > 0
              ? '<button id="dn-read-reset" type="button" data-zh="重設進度" data-en="Reset" style="background:#fff;border:1px solid var(--border, #dcd5c8);color:#5e574e;padding:5px 10px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer">重設進度</button>'
              : '<span data-zh="逐篇閱讀後自動記錄" data-en="Auto-tracked as you read" style="font-size:12px;color:var(--muted,#71695e);font-style:italic">逐篇閱讀後自動記錄</span>') +
          '</div>' +
          '<div style="height:8px;background:#f1ece4;border-radius:9999px;overflow:hidden">' +
            '<div style="height:100%;width:' + pct + '%;background:linear-gradient(90deg,#a4b5a8,#0c5159);transition:width .35s ease;"></div>' +
          '</div>' +
        '</div>';

      var resetBtn = document.getElementById('dn-read-reset');
      if (resetBtn) resetBtn.addEventListener('click', function () {
        var msg = (DN.detectLang && DN.detectLang() === 'en')
          ? 'Reset reading progress? This only clears local records on this device.'
          : '要重設閱讀進度嗎？ 本動作只會清除本裝置的紀錄，不會影響網站。';
        if (confirm(msg)) {
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
  // Article reading UI helpers live in blog-article-reading(.min).js and load on article pages only.
  DN.ensureArticleReadingBundle = function () {
    if (DN.addReadingMeta && DN.addInlineTOC && DN.addFontSizer) return Promise.resolve();
    if (!DN._articleReadingBundleLoading) {
      // CODE_REVIEW — reset promise cache on failure (see ensureArticleVisualBundle).
      DN._articleReadingBundleLoading = new Promise(function (resolve, reject) {
        var s = document.createElement('script');
        s.src = '/blog/blog-article-reading.min.js?v=202609060300';
        s.defer = true;
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
      }).catch(function (err) {
        DN._articleReadingBundleLoading = null;
        throw err;
      });
    }
    return DN._articleReadingBundleLoading;
  };

  // Legacy disabled article controls were removed to keep the shared runtime small.

  // R32: Lazy-load audit - patch any non-eager <img> missing loading attr.
  DN.lazyLoadAudit = function () {
    var imgs = document.querySelectorAll('img:not([loading]):not([data-no-lazy])');
    imgs.forEach(function (img, i) {
      // Skip first image (likely above fold / LCP candidate) unless explicitly fetchpriority="low"
      if (i === 0 && !img.hasAttribute('fetchpriority')) {
        img.setAttribute('fetchpriority', 'high');
      } else {
        img.setAttribute('loading', 'lazy');
        img.setAttribute('decoding', 'async');
      }
    });
  };

  // Article footer helpers live in blog-article-footer(.min).js and load on demand.
  DN.ensureArticleFooterBundle = function () {
    if (DN.addRelatedArticles && DN.addShareToolbar && DN.addAuthorBio && DN.addLegalDisclaimer) return Promise.resolve();
    if (!DN._articleFooterBundleLoading) {
      // CODE_REVIEW — reset promise cache on failure.
      DN._articleFooterBundleLoading = new Promise(function (resolve, reject) {
        var s = document.createElement('script');
        s.src = '/blog/blog-article-footer.min.js?v=202609060300';
        s.defer = true;
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
      }).catch(function (err) {
        DN._articleFooterBundleLoading = null;
        throw err;
      });
    }
    return DN._articleFooterBundleLoading;
  };

  // Reads dates from DN.ARTICLES catalog by matching href slug.
  // 2026-05-16 — DN.TDA_GUIDELINE + DN.addTDALink removed (dead code).
  // The TDA-link block was never called from initBlog or any HTML; the
  // 「官方資源」 section is now hand-authored at the end of each article body
  // instead. Saved ~2.4 KB minified from the shared runtime.

  // §86 醫療法保護 — auto-inject medical-disclaimer block at end of article
  // (resident-grade safety wording per agent research)
  // -----------------------------------------------------------------------
  // -----------------------------------------------------------------------
  // Clinical calculators live in blog-calculators(.min).js and are loaded on demand.
  DN.ensureCalculatorBundle = function () {
    if (DN.injectDLQI && DN.injectSCORAD) return Promise.resolve();
    if (!DN._calculatorBundleLoading) {
      // CODE_REVIEW — reset promise cache on failure.
      DN._calculatorBundleLoading = new Promise(function (resolve, reject) {
        var s = document.createElement('script');
        s.src = '/blog/blog-calculators.min.js?v=202609060300';
        s.defer = true;
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
      }).catch(function (err) {
        DN._calculatorBundleLoading = null;
        throw err;
      });
    }
    return DN._calculatorBundleLoading;
  };

  DN.injectCalculatorByName = function (name) {
    var CALC_FN = {
      SCORAD: DN.injectSCORAD, EASI: DN.injectEASI, POEM: DN.injectPOEM,
      PASI: DN.injectPASI, NAPSI: DN.injectNAPSI,
      SALT: DN.injectSALT, HairScale: DN.injectHairScale,
      UAS7: DN.injectUAS7,
      GAGS: DN.injectGAGS, MASI: DN.injectMASI,
      Hurley: DN.injectHurley, IHS4: DN.injectIHS4,
      Fitzpatrick: DN.injectFitzpatrick,
      VAS: DN.injectVASPruritus,
      IGA: DN.injectIGA,
      ASIS: DN.injectASIS,
      VASI: DN.injectVASI,
      DLQI: DN.injectDLQI
    };
    var fn = CALC_FN[name];
    if (typeof fn !== 'function') return;
    DN._forceInject = true;
    try {
      fn();
    } catch (e) {
      // CODE_REVIEW — was silently swallowed. A calculator render
      // error means an article's tool doesn't show up, which the user
      // notices immediately. Surface to console (guarded to prod
      // hosts to avoid noisy local-dev) without crashing the page.
      if (location.hostname.indexOf('chendermatologist.com') !== -1 ||
          location.hostname === 'localhost') {
        try { console.warn('[DN] Calculator ' + name + ' failed to render:', e); } catch (_) {}
      }
    }
    DN._forceInject = false;
  };

  // Homepage spotlight — "最近更新" + "熱門推薦" dual columns
  // (Taiwan KOL pattern; benchmarked against 黃瑽寧 / 邱品齊 / 蔡逸群 sites)
  // Auto-populates from DN.ARTICLES catalog; runs on homepage only.
  // -----------------------------------------------------------------------
  // ─────────────────────────────────────────────────────────────────
  // 熱門推薦 — 手動精選的 evergreen 高搜尋量主題(基於 Google 搜尋量 +
  // 台灣皮膚科 PTT/Dcard 詢問頻度,並非 newest)。每季度根據 GA4 數據
  // 重新評估排序。寫入新文章不會改變這個 list — 必須手動更新。
  // 每季度依 GA4 報表人工調整，避免新增一個只為排序而存在的公開 API。
  // ─────────────────────────────────────────────────────────────────
  DN.POPULAR_PICKS = [
    'acne-myths',          // 痘痘 — 最高搜尋量
    'sunscreen-myths',     // 防曬 — 公眾衛教高需求
    'atopic-dermatitis-overview',        // 異膚 — 兒童 + 成人共通
    'topical-steroids-guide', // 類固醇恐懼症 — 高度誤解
    'hairloss-myths'       // 落髮 — 男性女性共通
  ];

  DN.isLocalStaticHost = function () {
    return /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname);
  };

  DN.articleUrlForRuntime = function (slug) {
    return '/blog/' + slug + (DN.isLocalStaticHost() ? '.html' : '');
  };

  // I11 — Tell the SW to precache N popular + recent articles when idle.
  // Lets future navigation be instant + works offline.
  DN.precacheArticles = function (n) {
    if (!('serviceWorker' in navigator) || !navigator.serviceWorker.controller) return;
    var limit = n || 10;
    var urls = [];
    var seen = {};
    // Popular picks first
    (DN.POPULAR_PICKS || []).forEach(function (s) {
      if (!seen[s]) { seen[s] = 1; urls.push(DN.articleUrlForRuntime(s)); }
    });
    // Then recent by date
    (DN.ARTICLES || []).slice()
      .sort(function (a, b) { return (b.date || '').localeCompare(a.date || ''); })
      .forEach(function (a) {
        if (!seen[a.slug] && urls.length < limit) {
          seen[a.slug] = 1;
          urls.push(DN.articleUrlForRuntime(a.slug));
        }
      });
    try {
      navigator.serviceWorker.controller.postMessage({ type: 'PRECACHE', urls: urls });
    } catch (e) {}
  };

  // G2 — Refresh DN.POPULAR_PICKS from /api/admin/popular-picks (KV-backed).
  // Allows admin to change the curated list without a redeploy.
  // Falls back silently to the hard-coded list above if KV is empty or fetch fails.
  DN.refreshPopularPicks = function () {
    if (!('fetch' in window)) return Promise.resolve();
    if (DN.isLocalStaticHost()) return Promise.resolve();
    // CODE_REVIEW 2026-05-31 - dropped { cache: 'no-cache' }. Runs on every
    // page load (idle in DOMContentLoaded); no-cache bypassed Vercel's CDN and
    // hit the edge fn + Upstash KV per page view. Endpoint already sets
    // s-maxage=60, stale-while-revalidate=300, so a plain fetch lets the CDN
    // serve it ~60s across visitors. Admin writes are a POST (not CDN-cached).
    return fetch('/api/admin/popular-picks')
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (data && Array.isArray(data.picks) && data.picks.length) {
          DN.POPULAR_PICKS = data.picks;
          // Re-render spotlight if already on a page that has it.
          if (document.getElementById('dn-popular-list')) {
            if (typeof DN.injectSpotlight === 'function') {
              try { DN.injectSpotlight(); } catch (e) {}
            } else if (typeof DN.ensureHubBundle === 'function') {
              DN.ensureHubBundle().then(function () {
                if (typeof DN.injectSpotlight === 'function') DN.injectSpotlight();
              }).catch(function () {});
            }
          }
        }
      })
      .catch(function () { /* keep fallback */ });
  };

  // Homepage / article-hub helpers live in blog-hub(.min).js and load on demand.
  DN.ensureHubBundle = function () {
    if (DN.injectSpotlight && DN.bindArticleHub) return Promise.resolve();
    if (!DN._hubBundleLoading) {
      // CODE_REVIEW — reset promise cache on failure.
      DN._hubBundleLoading = new Promise(function (resolve, reject) {
        var s = document.createElement('script');
        s.src = '/blog/blog-hub.min.js?v=202609060300';
        s.defer = true;
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
      }).catch(function (err) {
        DN._hubBundleLoading = null;
        throw err;
      });
    }
    return DN._hubBundleLoading;
  };

  // Article font-size adjuster lives in blog-article-reading(.min).js.

  // -----------------------------------------------------------------------

  // Content feedback button — replaces "LINE consult" pattern with mailto
  // For residents who don't run a clinic — feedback goes to gmail
  // -----------------------------------------------------------------------
  // Subscribe-to-notifications opt-in card. Only visible when:
  //   1. Browser supports PushManager + Notification API
  // ─────────────────────────────────────────────────────────────────────
  // Visible "Buy Me a Coffee" tip CARD (separate from the floating button).
  // Renders inline at the article footer per user spec.
  // ─────────────────────────────────────────────────────────────────────
  // Pre-set Ko-fi + 街口支付 URLs (replace BMC entirely — Ko-fi is 0% commission)
  DN.KOFI_URL = 'https://ko-fi.com/expertise88864';
  DN.JKO_URL = 'https://service.jkopay.com/r/transfer?j=Transfer:901070305';

  // exposed as DN.KOFI_URL / DN.JKO_URL but only used on /support itself.
  DN.SUPPORT_URL = '/support';
  DN.SUPPORT_PROVIDER = '街口支付';

  DN.injectBMCFooter = function () {
    if (!DN.SUPPORT_URL) return;   // 等待 ezPay 審核中,先不注入
    if (document.getElementById('dn-bmc-footer')) return;
    var footer = document.querySelector('footer');
    if (!footer) return;
    var section = document.createElement('section');
    section.id = 'dn-bmc-footer';
    // 2026-05-08 — align width + horizontal padding with addAuthorBio for visual
    // consistency (same .max-w-3xl mx-auto px-5 sm:px-8 my-6 wrapper).
    section.className = 'max-w-3xl mx-auto px-5 sm:px-8 my-6';
    section.style.cssText = 'text-align:center';
    // Subtle white card matching the rest of the site
    section.innerHTML =
      '<div style="background:#fff;border:1px solid var(--border,#e7e2d8);border-radius:18px;padding:22px 24px;box-shadow:0 1px 2px rgba(15,23,42,.04), 0 14px 30px -18px rgba(77,99,88,.18)">' +
        '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.22em;color:#0e7c86;font-weight:700;margin-bottom:6px" data-zh="如果這個網站對您有幫助" data-en="If this site has helped you">如果這個網站對您有幫助</div>' +
        '<h3 style="font-family:\'Noto Serif TC\',Georgia,serif;font-size:20px;font-weight:700;color:#0f172a;margin:0 0 8px" data-zh="請我喝杯咖啡 ☕" data-en="Buy me a coffee ☕">請我喝杯咖啡 ☕</h3>' +
        '<p style="font-size:13px;color:#5e574e;line-height:1.85;margin:0 auto 14px;max-width:540px" data-zh="本網站<strong>無業配、無贊助</strong>，所有衛教文章與量表計算器都<strong>免費</strong>。本贊助為讀者自願性的內容打賞，<strong>非醫療服務費用</strong>，不涉及任何醫療諮詢、診斷或治療。" data-en="No ads, no sponsorships. All articles and calculators are free. This support is a voluntary content tip, not a medical-service fee, and does not involve any medical consultation, diagnosis, or treatment.">本網站<strong>無業配、無贊助</strong>，所有衛教文章與量表計算器都<strong>免費</strong>。本贊助為讀者自願性的內容打賞，<strong>非醫療服務費用</strong>，不涉及任何醫療諮詢、診斷或治療。</p>' +
        '<a href="' + DN.SUPPORT_URL + '" data-bmc-footer-link ' +
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
    if (!DN.SUPPORT_URL) return;
    // R25: skip header pill — static #dn-nav-support icon already covers this slot
    if (document.getElementById('dn-nav-support')) return;
    if (document.getElementById('dn-bmc-header')) return;
    var headerInner = document.querySelector('header.sticky .h-16 > div:last-child');
    if (!headerInner) return;
    if (!document.getElementById('dn-bmc-header-css')) {
      var supportStyle = document.createElement('style');
      supportStyle.id = 'dn-bmc-header-css';
      supportStyle.textContent =
        '.dn-bmc-header-link:hover,.dn-bmc-header-link:focus-visible{' +
        'background:#eaf6f3!important;color:#0e7c86!important;outline:none}';
      document.head.appendChild(supportStyle);
    }
    var a = document.createElement('a');
    a.id = 'dn-bmc-header';
    a.className = 'dn-bmc-header-link';
    a.href = DN.SUPPORT_URL;
    // Same-tab navigation: /support is an internal page now.
    a.setAttribute('aria-label', '支持作者');
    a.setAttribute('data-zh-aria-label', '支持作者');
    a.setAttribute('data-en-aria-label', 'Support the author');
    // Low-key teal pill matching the existing header nav links — no yellow background
    a.style.cssText =
      'display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:9999px;' +
      'background:transparent;color:#0c5159;text-decoration:none;' +
      'font-size:12px;font-weight:600;border:1px solid #a7d8ce;' +
      'transition:background .15s,color .15s';
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
      'padding-bottom:env(safe-area-inset-bottom);' +
      'transform:translateY(0);transition:transform .25s ease';
    bar.innerHTML =
      '<a href="/" ' +
        'style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;padding:9px 4px;text-decoration:none;color:#4d6358;font-size:11px;font-weight:700;border-right:1px solid var(--border, #dcd5c8)" ' +
        'data-cta="home" aria-label="首頁">' +
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>' +
        '<span data-zh="首頁" data-en="Home">首頁</span>' +
      '</a>' +
      '<a href="/blog/" ' +
        'style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;padding:9px 4px;text-decoration:none;color:#4d6358;font-size:11px;font-weight:700;border-right:1px solid var(--border, #dcd5c8)" ' +
        'data-cta="latest" aria-label="最新文章">' +
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/></svg>' +
        '<span data-zh="最新文章" data-en="Latest">最新文章</span>' +
      '</a>' +
      '<a href="/about" ' +
        'style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;padding:9px 4px;text-decoration:none;color:#4d6358;font-size:11px;font-weight:700" ' +
        'data-cta="about" aria-label="關於我">' +
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v2"/></svg>' +
        '<span data-zh="關於我" data-en="About">關於我</span>' +
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

    // Auto-hide on scroll-down, show on scroll-up (mobile reading mode).
    // Always reveal at the very top + when nearly at page bottom.
    var lastY = window.scrollY || 0;
    var ticking = false;
    function onScroll() {
      var y = window.scrollY || 0;
      var dy = y - lastY;
      var nearBottom = (window.innerHeight + y) >= (document.documentElement.scrollHeight - 80);
      if (y < 120 || nearBottom) {
        bar.style.transform = 'translateY(0)';
      } else if (dy > 6) {
        bar.style.transform = 'translateY(110%)'; // hide
      } else if (dy < -6) {
        bar.style.transform = 'translateY(0)'; // show
      }
      lastY = y;
      ticking = false;
    }
    window.addEventListener('scroll', function () {
      if (!ticking) { requestAnimationFrame(onScroll); ticking = true; }
    }, { passive: true });

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
  // Legacy inline CTA injection removed; calculator CTAs now live in the article footer/tool flow.

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
    // CODE_REVIEW — collapsed two separate `document.click` delegated
    // handlers (related-card + outbound) into one. Saves one event-
    // listener pass per click; both checks share `e.target.closest`
    // walk. Also dropped `capture:true` from the outbound branch —
    // related-card handler used bubble phase and they're independent
    // anyway. `{passive:true}` is honored.
    document.addEventListener('click', function (e) {
      var target = e.target;
      if (!target || !target.closest) return;

      // Related-articles card (SSG #dn-related-static + JS #dn-related)
      var card = target.closest('a.dn-related-card');
      if (card) {
        fire('related_card_click', {
          destination: card.getAttribute('href') || '',
          source: location.pathname,
        });
      }

      // Outbound link — any <a> pointing off-host. Single closest()
      // call shared with the card check above when the card is also
      // an outbound link (rare but possible for future link types).
      var a = target.closest('a[href]');
      if (!a) return;
      var href = a.getAttribute('href') || '';
      if (!/^https?:\/\//i.test(href)) return;  // relative / mailto / tel
      try {
        var u = new URL(href, location.href);
        if (u.host === location.host) return;
        fire('outbound_click', {
          destination: u.host + u.pathname,
          host: u.host,
          page_path: location.pathname,
        });
      } catch (err) { /* malformed URL — skip */ }
    }, { passive: true });
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

  // DN.markNewArticles moved to blog-hub.js (only fires on card list pages).

  DN.bindWebVitals = function () {
    if (typeof gtag !== 'function') return;
    // CODE_REVIEW Tier 1A — official GoogleChrome/web-vitals library
    // (attribution build) loaded via <script defer src="/assets/
    // web-vitals.iife.js">. Replaces ~85 lines of hand-rolled
    // PerformanceObserver code with:
    //   • bfcache restore handling (re-fires with new metric id)
    //   • Cross-browser parity (Chromium / Firefox / Safari)
    //   • `.attribution` debug data — WHICH element caused poor LCP,
    //     which interactionTarget caused INP, which layout-shift source
    //     caused CLS. Turns GA4 into actionable diagnostics.
    //   • Standardized algorithm matching the CrUX dataset.
    var lib = window.webVitals;
    if (!lib) {
      // <script defer> hasn't finished loading yet. Retry once.
      setTimeout(function () {
        if (window.webVitals) DN.bindWebVitals();
      }, 800);
      return;
    }
    function send(metric) {
      try {
        var attr = metric.attribution || {};
        var params = {
          event_category: 'Web Vitals',
          event_label: metric.id,
          // CLS is unitless; scale to ms-equivalent for GA4.
          value: Math.round(metric.name === 'CLS' ? metric.value * 1000 : metric.value),
          metric_rating: metric.rating,       // good / needs-improvement / poor
          metric_delta: metric.delta,
          navigation_type: metric.navigationType,
          non_interaction: true,
        };
        // Per-metric attribution. Bounded ≤100 chars per GA4 param limit.
        if (metric.name === 'LCP' && attr.element) {
          params.lcp_element = String(attr.element).slice(0, 100);
          params.lcp_url = (attr.url || '').slice(0, 100);
          params.lcp_ttfb = Math.round(attr.timeToFirstByte || 0);
          params.lcp_render_delay = Math.round(attr.elementRenderDelay || 0);
        } else if (metric.name === 'CLS' && attr.largestShiftTarget) {
          params.cls_target = String(attr.largestShiftTarget).slice(0, 100);
          params.cls_time = Math.round(attr.largestShiftTime || 0);
        } else if (metric.name === 'INP' && attr.interactionTarget) {
          params.inp_target = String(attr.interactionTarget).slice(0, 100);
          params.inp_type = attr.interactionType || '';
          params.inp_input_delay = Math.round(attr.inputDelay || 0);
          params.inp_processing = Math.round(attr.processingDuration || 0);
          params.inp_presentation = Math.round(attr.presentationDelay || 0);
        }
        gtag('event', metric.name, params);
      } catch (e) { /* ignore */ }
    }
    try { lib.onLCP(send); } catch (e) {}
    try { lib.onCLS(send); } catch (e) {}
    try { lib.onINP(send); } catch (e) {}
    try { lib.onFCP(send); } catch (e) {}
    try { lib.onTTFB(send); } catch (e) {}
  };


  // -----------------------------------------------------------------------
  // 文章快速查找 — search + disease tag chips, auto-injected to #dn-hub
  // -----------------------------------------------------------------------
  // Disease/topic tag catalog and article-hub binding live in blog-hub(.min).js.

  DN.initBlog = function (opts) {
    DN.injectKeyFactCSS();
    DN.injectChartScrollCSS();
    opts = opts || {};
    let curLang = DN.detectLang();

    function apply(lang) {
      curLang = lang;
      DN.applyTextOnly(lang);
      const isZh = (lang === 'zh');
      const ze = document.getElementById(opts.proseZh || 'proseZh');
      const en = document.getElementById(opts.proseEn || 'proseEn');
      // Two article patterns supported:
      //   (A) Older: proseEn contains a separately-rendered English mirror →
      //       toggle visibility of ze/en.
      //   (B) Newer: proseZh has data-zh + data-en on every block; proseEn is
      //       empty or absent. applyTextOnly() does an in-place swap, so we
      //       must KEEP proseZh visible regardless of language.
      const enHasContent = !!(en && en.children && en.children.length > 0);
      if (enHasContent) {
        if (ze) ze.style.display = isZh ? '' : 'none';
        en.style.display = isZh ? 'none' : '';
      }
      if (typeof opts.onChange === 'function') opts.onChange(lang);
    }

    // F1 INP optimization: split init into critical (immediate) vs deferred (idle)
    // Reduces long-task blocking during first interaction window.
    var idle = window.requestIdleCallback || function (cb) { return setTimeout(cb, 1); };
    // ─── Critical (visual / first-interaction) ───
    DN.injectMobileMenu();
    DN.bindLangToggle(apply);
    apply(curLang);
    DN.addReadingProgress();

    // CODE_REVIEW — initCmdK builds the entire search index, injects
    // ~30-line <style>, builds the overlay DOM, and attaches global
    // keydown + click listeners. That's the biggest INP contributor
    // during first-paint. Moved to idle queue with a bootstrap so the
    // search button still works instantly on first click.
    //
    // Bootstrap strategy:
    //   - Pre-bind a one-shot capture on document for the search button
    //     and Cmd+K / `/` shortcut.
    //   - On first trigger, synchronously run initCmdK() (idempotent
    //     via its `dn-cmdk-style` early return) then dispatch openSearch.
    //   - Idle queue still runs initCmdK at idle so the second click is
    //     no-bootstrap-cost.
    var cmdkReady = false;
    function ensureCmdK() {
      if (!cmdkReady) {
        DN.initCmdK();
        cmdkReady = true;
      }
    }
    function bootstrapClick(e) {
      var btn = e.target.closest && e.target.closest('button[aria-label="搜尋"]');
      if (btn) {
        e.preventDefault();
        ensureCmdK();
        DN.openSearch && DN.openSearch();
      }
    }
    function bootstrapKey(e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        ensureCmdK();
        DN.openSearch && DN.openSearch();
      } else if (e.key === '/' &&
                 document.activeElement &&
                 document.activeElement.tagName !== 'INPUT' &&
                 document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        ensureCmdK();
        DN.openSearch && DN.openSearch();
      }
    }
    document.addEventListener('click', bootstrapClick, { capture: true });
    document.addEventListener('keydown', bootstrapKey);
    // Schedule the real init for idle — once it runs, the bootstrap
    // handlers above stay attached but each call's `if (!cmdkReady)`
    // gate becomes a no-op. initCmdK is internally idempotent too.
    idle(function () { ensureCmdK(); }, { timeout: 800 });

    // 2026-05-17 — wire up the SearchAction declared in WebSite JSON-LD.
    // Google's sitelinks search box sends users to /?q=keyword. Auto-open
    // Cmd+K and seed the query so the contract is honored.
    try {
      var qp = new URLSearchParams(location.search).get('q');
      if (qp && qp.trim()) {
        // ?q= flow needs cmdk RIGHT NOW (not at idle) so the user sees
        // the search panel open with their query pre-filled on first paint.
        ensureCmdK();
        setTimeout(function () {
          DN.openSearch && DN.openSearch();
          var inp = document.getElementById('dn-cmdk-input');
          if (inp) {
            inp.value = qp;
            inp.dispatchEvent(new Event('input', { bubbles: true }));
          }
        }, 50);
      }
    } catch (e) { /* ignore */ }
    DN.injectUnpublishedBanner();
    DN.hideUnpublishedCards();
    // ─── Deferred (no first-paint impact) ───
    idle(function () { DN.injectBMC(); }, { timeout: 1200 });
    idle(function () { DN.addScrollToTop(); }, { timeout: 1500 });
    idle(function () { DN.bindRevealOnScroll(); }, { timeout: 800 });
    idle(function () { DN.prefetchOnIdle(); }, { timeout: 2500 });
    idle(function () { DN.bindViewTransitions(); }, { timeout: 1500 });
    idle(function () { DN.initDarkMode(); }, { timeout: 1500 });
    // 2026-05-07 — bottom-right floating push-bell ("提醒") removed per user.
    // Push subscription is still wired (sw.js handler stays); users who want
    // it can opt in from a future settings page.
    idle(function () { DN.refreshPopularPicks && DN.refreshPopularPicks(); }, { timeout: 3000 });
    idle(function () { DN.precacheArticles && DN.precacheArticles(8); }, { timeout: 6000 });

    // Article-only enhancements (auto-detect via .prose presence).
    // Match articles whose <article> root has .prose, OR has a .prose descendant,
    // OR uses #proseZh. NOT matched by homepage (which has article.max-w-3xl
    // without .prose class).
    var hasArticleProse = document.getElementById('proseZh') || document.querySelector('article.prose') || document.querySelector('article .prose');
    if (hasArticleProse) {
      // Reading UI is article-only and split out of the shared runtime.
      DN.ensureArticleReadingBundle().then(function () {
        DN.addReadingMeta && DN.addReadingMeta();
        DN.addInlineTOC && DN.addInlineTOC();
        // 2026-05-08 ? ?? TOC (left-side fixed) disabled per user. The inline
        // collapsible TOC at the top of each article is enough; having both was
        // confusing ("?????????????????????").
        DN.addFloatingTOC && DN.addFloatingTOC();
        DN.addFontSizer && DN.addFontSizer();
        try { DN.applyTextOnly(curLang); } catch (e) {}
        idle(function () { DN.bindScrollMemory && DN.bindScrollMemory(); }, { timeout: 1500 });
      }).catch(function () {});
      idle(function () {
        DN.ensureArticleVisualBundle().then(function () {
          DN.injectArticleHero();
          DN.enhanceArticleImages();
          try { DN.applyTextOnly(curLang); } catch (e) {}
        }).catch(function () {});
      }, { timeout: 1500 });
      // 2026-05-17 perf — gate the 100 KB diagrams bundle on a static
      // slug allow-list (kept in sync with blog-diagrams.js MED_DIAGRAM_MAP)
      // so articles without diagrams don't pay for the bundle. ~21 articles
      // saved ~100 KB each before this change.
      if (DN.DIAGRAM_SLUGS && DN.DIAGRAM_SLUGS.indexOf(DN.currentSlug && DN.currentSlug()) !== -1) {
        idle(function () {
          DN.ensureArticleReadingBundle().then(function () {
            DN.injectMedDiagrams && DN.injectMedDiagrams();
          }).catch(function () {});
        }, { timeout: 2000 });
      }
      // Floating BMC button disabled — replaced by the visible tip CARD
      // (DN.injectTipCard) at article footer with Ko-fi + 街口 side-by-side.
      // H4 word count badge, H1 Giscus, H6 PDF — all article-page only
      idle(function () {
        DN.ensureArticleFooterBundle().then(function () {
          DN.injectWordCount && DN.injectWordCount();
          DN.injectGiscus && DN.injectGiscus();
          try { DN.applyTextOnly(curLang); } catch (e) {}
        }).catch(function () {});
      }, { timeout: 1800 });
      // 2026-05-08 — PDF / 列印 download button removed per user (overlapped font sizer + back-to-top).
      // idle(function () { DN.injectPdfButton && DN.injectPdfButton(); }, { timeout: 1800 });
      // 2026-05-07 — article-footer email newsletter card disabled per user.
      // The homepage newsletter already covers this surface; prompting again
      // at every article end was noisy.
      // idle(function () { DN.injectNewsletterCard && DN.injectNewsletterCard(); }, { timeout: 4500 });

      // Per-article calculator priority lives in blog-calculators.js
      // (DN.CALC_ORDER + DN.autoInjectCalculators) — keeps the per-slug data
      // table out of the shared first-paint runtime.

      // Article-footer order (top → bottom, per user spec 2026-05-08):
      //   ↓ Official sources / authoritative guidelines (in article body)
      //   ↓ References (in article body)
      //   1. 計算器(single, injected last so it sits CLOSEST to article)
      //   2. 你可能會想看(RelatedArticles)
      //   3. 分享給朋友(ShareToolbar)
      //   4. 發現錯誤、過時資訊、引用爭議(FeedbackLink)
      //   5. 關於作者(AuthorBio)
      //   6. 重要聲明(LegalDisclaimer)
      //   7. 贊助本站(injectBMCFooter — runs at site-footer level)
      //   8. 頁面底部(static <footer>)
      // All inject via article.parentNode.insertBefore(box, article.nextSibling)
      // — which means each call pushes earlier-injected boxes further down. To
      // achieve the desired top-to-bottom order, we call in REVERSE order
      // (Disclaimer first → Calculator last).
      // 2026-05-08 — DN.injectNextReads (繼續閱讀) removed per user; the single
      // RelatedArticles block already covers "what to read next".
      idle(function () {
        DN.ensureArticleFooterBundle().then(function () {
          DN.addLegalDisclaimer();
          DN.addAuthorBio();
          DN.addFeedbackLink();
          DN.addShareToolbar();
          DN.addRelatedArticles();
          try { DN.applyTextOnly(curLang); } catch (e) {}
        }).catch(function () {});
      }, { timeout: 1500 });
      // Calculator goes LAST (so it ends up immediately under the article).
      // 2026-05-17 perf — gate the 57 KB calculators bundle on a static
      // slug allow-list (kept in sync with blog-calculators.js CALC_ORDER)
      // so articles without calculators don't pay for the bundle. ~30
      // articles saved ~57 KB each before this change.
      if (DN.CALC_SLUGS && DN.CALC_SLUGS.indexOf(DN.currentSlug && DN.currentSlug()) !== -1) {
        idle(function () {
          DN.ensureCalculatorBundle().then(function () {
            if (typeof DN.autoInjectCalculators === 'function') {
              DN.autoInjectCalculators(DN.currentSlug());
            }
            try { DN.applyTextOnly(curLang); } catch (e) {}
          }).catch(function () {});
        }, { timeout: 1800 });
      }
      // 2026-05-07 — yellow article-footer tip card disabled per user.
      // The teal-bordered DN.injectBMCFooter card on every page is enough;
      // no need for a second 「請我喝杯咖啡」 inside articles.
      // DN.injectTipCard && DN.injectTipCard();
      // Floating buttons (don't affect DOM order).
      // 2026-05-07 — bookmark + print floating buttons removed per user
      // request: they were stacking on top of the font-size adjuster
      // (bottom:80px / 130px overlapped with the new bottom:24px sizer).
      // Bookmark feature was UI-only (no list page consumed the localStorage
      // key), and print is still reachable via Cmd/Ctrl+P natively.
      // Inline push-subscribe card also removed (same 2026-05-07 cleanup).
    }
    DN.lazyLoadAudit();
    DN.bindWebVitals();
    DN.bindGAEvents();
    if (document.getElementById('dn-hub') || document.getElementById('dn-recent-list') || document.getElementById('dn-popular-list')) {
      idle(function () {
        DN.ensureHubBundle().then(function () {
          if (typeof DN.bindArticleHub === 'function') DN.bindArticleHub();
          if (typeof DN.injectSpotlight === 'function') DN.injectSpotlight();
          try { DN.applyTextOnly(curLang); } catch (e) {}
        }).catch(function () {});
      }, { timeout: 800 });
    }
    DN.injectReadProgress();

    // ── Re-apply language to ALL injected content (related/share/author-bio/etc.)
    // 2026-05-17 — trimmed from 5 timers [100,600,1500,3000,5000] to 2.
    // The SAFE MutationObserver below catches every new [data-zh] node and
    // re-runs applyTextOnly within 80ms of injection, so the late-timer
    // safety net was redundant. Keep only:
    //   100ms — covers any synchronous post-DOMContentLoaded inject
    //           (e.g. CSS-driven layout reads)
    //   1500ms — fallback safety in case the MutationObserver missed an
    //            edge-case insertion (e.g. innerHTML replacement that
    //            doesn't trigger childList mutations for individual
    //            descendants we care about)
    // Net effect: −3 setTimeout invocations per page → ~0.5ms saved on
    // 3G CPU, but more importantly the 5000ms timer was firing well after
    // first-interaction and contributing to TBT in some profiles.
    [100, 1500].forEach(function (ms) {
      setTimeout(function () {
        try { DN.applyTextOnly(curLang); } catch (e) {}
      }, ms);
    });
    // SAFE MutationObserver: debounced + checks for unprocessed [data-zh] only.
    //
    // CODE_REVIEW — scope was `document.body, subtree:true`, which fires on
    // EVERY DOM insertion site-wide (calculator live results, lightbox open,
    // dark-mode toggle, every chart redraw). Calculator-heavy pages were
    // doing `n.querySelector('[data-zh]')` 50+ times per recalc.
    //
    // Narrow to the actual hot spots that legitimately inject data-zh
    // content: the prose container (#proseZh or #proseEn), the page footer,
    // and #dn-hub if present (homepage). All other site UI is hand-coded
    // and never injects new data-zh nodes — the existing fallback
    // applyTextOnly() retries at the bottom of initBlog catch any miss.
    if ('MutationObserver' in window) {
      var pending = false;
      var obs = new MutationObserver(function (mutations) {
        if (pending) return;
        var hasNew = false;
        for (var i = 0; i < mutations.length && !hasNew; i++) {
          var added = mutations[i].addedNodes;
          for (var j = 0; j < added.length; j++) {
            var n = added[j];
            if (n.nodeType !== 1) continue;
            if (n.hasAttribute && n.hasAttribute('data-zh')) { hasNew = true; break; }
            if (n.querySelector && n.querySelector('[data-zh]')) { hasNew = true; break; }
          }
        }
        if (hasNew) {
          pending = true;
          // Debounce 80ms — skip applyTextOnly's own mutations (they
          // change textContent, not addedNodes)
          setTimeout(function () {
            try { DN.applyTextOnly(curLang); } catch (e) {}
            pending = false;
          }, 80);
        }
      });
      // Watch only the containers that legitimately receive data-zh
      // injections. Each target is observed independently with subtree.
      var targets = [
        document.getElementById('proseZh'),
        document.getElementById('proseEn'),
        document.getElementById('dn-hub'),
        document.querySelector('article'),
        document.querySelector('footer'),
      ].filter(Boolean);
      // Fallback: if no specific targets exist (rare pages), keep body
      // scope but bail early on every mutation via the hasNew filter.
      if (targets.length === 0) targets = [document.body];
      targets.forEach(function (t) {
        obs.observe(t, { childList: true, subtree: true });
      });
    }
    // DN.markNewArticles() now runs inside blog-hub.js (only when card lists exist).
    DN.addStickyCTA();

    const yr = document.getElementById('yr');
    if (yr) yr.textContent = new Date().getFullYear();

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').then(function (reg) {
        DN.bindSWUpdateToast(reg);
        // CODE_REVIEW — was setInterval(reg.update, 30 min) which never
        // got cleared and kept firing forever (even after the tab was
        // hidden for hours; the visibility check just skipped the call
        // but the interval kept running). Now schedule a single timeout
        // and reschedule via visibilitychange so a backgrounded tab is
        // truly idle.
        var updateTimer = null;
        function scheduleNextUpdate() {
          if (updateTimer) clearTimeout(updateTimer);
          updateTimer = setTimeout(function () {
            if (document.visibilityState === 'visible') {
              reg.update().catch(function () {});
            }
            scheduleNextUpdate();
          }, 30 * 60 * 1000);
        }
        scheduleNextUpdate();
        // Re-check on tab refocus too — if the user comes back after
        // a day, they get the latest SW within seconds, not 30 min.
        document.addEventListener('visibilitychange', function () {
          if (document.visibilityState === 'visible') {
            reg.update().catch(function () {});
            scheduleNextUpdate();
          }
        });
      }).catch(function (err) {
        // CODE_REVIEW — was silently swallowed. SW registration failure
        // means no offline support, no push, no precache. Warn so it
        // surfaces in DevTools without breaking the page.
        if (location.hostname.indexOf('chendermatologist.com') !== -1 ||
            location.hostname === 'localhost') {
          try { console.warn('[DN] Service Worker register failed:', err); } catch (e) {}
        }
      });
    }
    return { applyLang: apply };
  };
})();
