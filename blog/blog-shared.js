/* ============================================================
 * DermNotes — shared blog runtime
 *   - language detection (cookie > localStorage > navigator > en)
 *   - language preference persistence
 *   - 10-language dropdown (replaces #langToggle)
 *   - reading progress bar
 *   - scroll-to-top button
 *   - mobile hamburger drawer
 *   - footer year + service worker registration
 *
 * Usage on every blog page:
 *   <script src="/blog/blog-shared.js" defer></script>
 *   <script>DN.initBlog({ proseZh:'proseZh', proseEn:'proseEn' });</script>
 * ============================================================ */
(function () {
  const DN = (window.DN = window.DN || {});

  DN.LANGS = [
    { code: 'zh',    label: '中文(繁體)',  htmlLang: 'zh-TW' },
    { code: 'zh-cn', label: '简体中文',       htmlLang: 'zh-CN' },
    { code: 'en',    label: 'English',         htmlLang: 'en'    },
    { code: 'ja',    label: '日本語',          htmlLang: 'ja'    },
    { code: 'ko',    label: '한국어',          htmlLang: 'ko'    },
    { code: 'th',    label: 'ภาษาไทย',         htmlLang: 'th'    },
    { code: 'vi',    label: 'Tiếng Việt',      htmlLang: 'vi'    },
    { code: 'de',    label: 'Deutsch',         htmlLang: 'de'    },
    { code: 'fr',    label: 'Français',        htmlLang: 'fr'    },
    { code: 'es',    label: 'Español',         htmlLang: 'es'    }
  ];
  DN.LANG_KEY = {
    'zh':'zh', 'zh-cn':'zhcn', 'en':'en', 'ja':'ja', 'ko':'ko',
    'th':'th', 'vi':'vi', 'de':'de', 'fr':'fr', 'es':'es'
  };

  DN.cookieGet = function (name) {
    const found = document.cookie.split('; ').find(c => c.startsWith(name + '='));
    return found ? decodeURIComponent(found.split('=').slice(1).join('=')) : null;
  };
  DN.cookieSet = function (name, val, days) {
    const exp = new Date(Date.now() + (days || 365) * 86400e3).toUTCString();
    document.cookie = `${name}=${encodeURIComponent(val)}; expires=${exp}; path=/; SameSite=Lax`;
  };

  DN.detectLang = function () {
    const fromCookie = DN.cookieGet('dn_lang');
    if (fromCookie && DN.LANG_KEY[fromCookie]) return fromCookie;
    const stored = localStorage.getItem('dn_lang');
    if (stored && DN.LANG_KEY[stored]) return stored;
    const nav = (navigator.language || 'en').toLowerCase();
    if (nav.startsWith('zh-cn') || nav.startsWith('zh-hans')) return 'zh-cn';
    if (nav.startsWith('zh')) return 'zh';
    if (nav.startsWith('ja')) return 'ja';
    if (nav.startsWith('ko')) return 'ko';
    if (nav.startsWith('th')) return 'th';
    if (nav.startsWith('vi')) return 'vi';
    if (nav.startsWith('de')) return 'de';
    if (nav.startsWith('fr')) return 'fr';
    if (nav.startsWith('es')) return 'es';
    return 'en';
  };

  DN.setLang = function (code) {
    if (!DN.LANG_KEY[code]) return;
    try { localStorage.setItem('dn_lang', code); } catch (e) { /* ignore */ }
    DN.cookieSet('dn_lang', code);
  };

  DN.translate = function (el, lang) {
    const order = lang === 'zh-cn' ? ['zhcn', 'zh', 'en']
                : lang === 'zh'    ? ['zh', 'zhcn', 'en']
                : [DN.LANG_KEY[lang], 'en', 'zh'];
    for (const k of order) if (k && el.dataset[k] != null) return el.dataset[k];
    return null;
  };

  DN.applyTextOnly = function (lang) {
    const meta = DN.LANGS.find(l => l.code === lang) || DN.LANGS[2];
    document.documentElement.lang = meta.htmlLang;
    document.querySelectorAll('[data-zh],[data-en]').forEach(el => {
      const txt = DN.translate(el, lang);
      if (txt == null) return;
      if (/[<&]/.test(txt) && /<\/?[a-z]/i.test(txt)) el.innerHTML = txt;
      else el.textContent = txt;
    });
  };

  DN.injectLangDropdown = function (onChange) {
    const old = document.getElementById('langToggle');
    if (!old) return;
    const wrap = document.createElement('div');
    wrap.className = 'relative';
    wrap.id = 'dnLangWrap';
    wrap.innerHTML = `
      <button id="dnLangTrigger" type="button"
        class="lang-toggle inline-flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-semibold cursor-pointer"
        aria-haspopup="listbox" aria-expanded="false">
        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a13 13 0 0 1 0 18M12 3a13 13 0 0 0 0 18"/></svg>
        <span id="dnLangLabel">中文</span>
        <span style="color:#94a3b8">▾</span>
      </button>
      <div id="dnLangMenu" class="hidden absolute right-0 top-full mt-2 card p-1.5 z-50 min-w-[180px] max-h-[60vh] overflow-y-auto" role="listbox"></div>
    `;
    old.parentNode.replaceChild(wrap, old);

    const trig = wrap.querySelector('#dnLangTrigger');
    const menu = wrap.querySelector('#dnLangMenu');
    const lbl  = wrap.querySelector('#dnLangLabel');
    function rebuild(curLang) {
      const meta = DN.LANGS.find(l => l.code === curLang) || DN.LANGS[2];
      lbl.textContent = meta.label;
      menu.innerHTML = '';
      DN.LANGS.forEach(L => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'block w-full text-left px-3 py-1.5 rounded-md text-[12.5px] hover:bg-[var(--mint-soft)]'
                       + (curLang === L.code ? ' text-teal-700 font-semibold bg-[var(--mint-soft)]' : ' text-ink-700');
        item.textContent = L.label;
        item.addEventListener('click', () => {
          DN.setLang(L.code);
          menu.classList.add('hidden');
          rebuild(L.code);
          if (typeof onChange === 'function') onChange(L.code);
        });
        menu.appendChild(item);
      });
    }
    trig.addEventListener('click', () => {
      const open = menu.classList.contains('hidden');
      menu.classList.toggle('hidden');
      trig.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    document.addEventListener('click', (e) => {
      if (!wrap.contains(e.target)) menu.classList.add('hidden');
    });
    rebuild(DN.detectLang());
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
    btn.style.cssText = 'position:fixed;right:18px;bottom:24px;width:42px;height:42px;border-radius:50%;background:linear-gradient(180deg,#14b8a6,#0c5159);color:#fff;border:1px solid rgba(12,81,89,.5);box-shadow:0 8px 20px -8px rgba(12,81,89,.55);cursor:pointer;display:none;align-items:center;justify-content:center;z-index:50;font-size:18px;line-height:1;transition:transform .15s ease';
    btn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    document.body.appendChild(btn);
    document.addEventListener('scroll', () => {
      btn.style.display = window.scrollY > 800 ? 'flex' : 'none';
    }, { passive: true });
  };

  DN.injectMobileMenu = function () {
    if (document.getElementById('dnMobileMenuBtn')) return;
    const header = document.querySelector('header.sticky') || document.querySelector('header');
    if (!header) return;
    const headerInner = header.querySelector('div.flex.items-center.justify-between') || header.firstElementChild;
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
    drawer.style.cssText = 'background:rgba(245,251,250,.98);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);max-height:calc(100vh - 64px);overflow-y:auto;-webkit-overflow-scrolling:touch;';
    drawer.innerHTML = `
      <nav class="max-w-5xl mx-auto px-5 py-4 flex flex-col gap-1">
        <a href="/" class="block px-3 py-2.5 rounded-lg hover:bg-[var(--mint-soft)] text-[14px] font-semibold text-teal-700"
           data-zh="🏠 回首頁(關於我)" data-en="🏠 Home (about)" data-zhcn="🏠 回首页"></a>
        <a href="/blog/" class="block px-3 py-2.5 rounded-lg hover:bg-[var(--mint-soft)] text-[14px] font-semibold text-teal-700"
           data-zh="📚 全部文章" data-en="📚 All articles" data-zhcn="📚 全部文章"></a>

        <div class="mt-2 px-3 pt-2 border-t border-[var(--border)]">
          <div class="text-[10.5px] uppercase tracking-[.22em] text-teal-700 font-semibold mb-2"
               data-zh="衛教 · 民眾版" data-en="Patient education" data-zhcn="健康教育"></div>
          <a href="/blog/isotretinoin-patient" class="block py-1.5 text-[13px] text-ink-700"
             data-zh="① 口服 A 酸完整衛教" data-en="① Oral isotretinoin — patient guide"></a>
          <a href="/blog/topical-acids-patient" class="block py-1.5 text-[13px] text-ink-700"
             data-zh="② 外用酸類完整衛教(A酸/A醇/杜鵑花酸/果酸/水楊酸)" data-en="② Topical acids — patient guide"></a>
        </div>

        <div class="mt-2 px-3 pt-2 border-t border-[var(--border)]">
          <div class="text-[10.5px] uppercase tracking-[.22em] text-teal-700 font-semibold mb-2"
               data-zh="學習筆記 · 醫師版" data-en="Study notes · for clinicians" data-zhcn="学习笔记"></div>
          <a href="/blog/isotretinoin-clinical" class="block py-1.5 text-[13px] text-ink-700"
             data-zh="① Oral Isotretinoin 完整學理整理" data-en="① Oral isotretinoin — clinical notes"></a>
          <a href="/blog/topical-acids-clinical" class="block py-1.5 text-[13px] text-ink-700"
             data-zh="② Topical retinoids &amp; acid actives 整理" data-en="② Topical retinoids &amp; acid actives — clinical notes"></a>
        </div>

        <a href="/blog/feed.xml" class="mt-3 mx-3 inline-flex items-center justify-center gap-2 py-2.5 rounded-lg border border-[var(--border)] text-[12.5px] font-semibold text-ink-700">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="#0e7c86"><circle cx="6" cy="18" r="2.5"/><path d="M3 13a8 8 0 0 1 8 8h-3a5 5 0 0 0-5-5v-3zm0-6a14 14 0 0 1 14 14h-3a11 11 0 0 0-11-11V7z"/></svg>
          <span data-zh="RSS 訂閱" data-en="RSS feed"></span>
        </a>
      </nav>
    `;
    header.appendChild(drawer);

    function open()  { drawer.classList.remove('hidden'); btn.setAttribute('aria-expanded', 'true');  document.body.style.overflow = 'hidden'; }
    function close() { drawer.classList.add('hidden');    btn.setAttribute('aria-expanded', 'false'); document.body.style.overflow = ''; }
    btn.addEventListener('click', () => drawer.classList.contains('hidden') ? open() : close());
    drawer.querySelectorAll('a').forEach(a => a.addEventListener('click', close));
    window.addEventListener('resize', () => { if (window.innerWidth >= 640) close(); });
  };

  DN.initBlog = function (opts) {
    opts = opts || {};
    let curLang = DN.detectLang();

    function apply(lang) {
      curLang = lang;
      DN.applyTextOnly(lang);
      const isZh = (lang === 'zh' || lang === 'zh-cn');
      const ze = document.getElementById(opts.proseZh || 'proseZh');
      const en = document.getElementById(opts.proseEn || 'proseEn');
      if (ze) ze.style.display = isZh ? '' : 'none';
      if (en) en.style.display = isZh ? 'none' : '';
      if (typeof opts.onChange === 'function') opts.onChange(lang);
    }

    DN.injectMobileMenu();
    DN.injectLangDropdown(apply);
    apply(curLang);
    DN.addReadingProgress();
    DN.addScrollToTop();

    const yr = document.getElementById('yr');
    if (yr) yr.textContent = new Date().getFullYear();

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }

    return { applyLang: apply };
  };
})();
