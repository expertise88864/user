/* ChenDermatologist blog hub helpers: homepage/topic filtering + recent/popular spotlight. */
(function () {
  'use strict';
  var DN = window.DN = window.DN || {};

  // Keep query preparation and scoring independent of the DOM. All matching
  // uses the catalog plus its generated descriptions, not a second keyword list.
  DN.normalizeSearchText = function (value) {
    return String(value || '').normalize('NFKC').toLowerCase().trim();
  };
  DN.searchArticleCatalog = function (articles, query, descriptions) {
    var normalized = DN.normalizeSearchText(query).slice(0, 120);
    var terms = normalized.split(/[\s,，、;；]+/).filter(Boolean);
    var compact = normalized.replace(/\s+/g, '');
    if (!terms.length) return articles.filter(function (a) { return !a.unpublished; });
    return articles.filter(function (a) { return !a.unpublished; }).map(function (a, i) {
      var title = DN.normalizeSearchText(a.title + ' ' + (a.title_en || ''));
      var desc = (descriptions || {})[a.slug] || {};
      var text = DN.normalizeSearchText([title, a.tag, a.tag_en, a.slug, desc.desc, desc.desc_en].filter(Boolean).join(' '));
      var tight = text.replace(/\s+/g, '');
      var match = terms.every(function (term) { return tight.includes(term); });
      return {article:a, index:i, score:match ? (title.replace(/\s+/g, '').includes(compact) ? 3 : terms.every(function (term) { return title.includes(term); }) ? 2 : 1) : 0};
    }).filter(function (entry) { return entry.score; }).sort(function (a, b) {
      return b.score - a.score || a.index - b.index;
    }).map(function (entry) { return entry.article; });
  };

  // Tag the newest articles with a yellow "NEW" pulse badge on any card list.
  // Moved here 2026-05-16 from blog-shared.js — only useful where article cards
  // are rendered, so it does not need to run as part of the first-paint runtime.
  DN.markNewArticles = function () {
    var NOW = Date.now();
    var SEVEN_DAYS = 7 * 86400 * 1000;
    var cards = document.querySelectorAll('a.article-list-item[href*="/blog/"]');
    if (!cards.length) return;
    if (!document.getElementById('dn-new-pulse-css')) {
      var styleEl = document.createElement('style');
      styleEl.id = 'dn-new-pulse-css';
      styleEl.textContent = '.dn-new-pulse{display:inline-block;margin-left:6px;padding:1px 7px;border-radius:9999px;background:linear-gradient(135deg,#fbbf24,#f59e0b);color:#fff;font-size:9.5px;font-weight:800;letter-spacing:.04em;line-height:1.5;animation:dnPulse 1.6s ease-in-out infinite;}@keyframes dnPulse{0%,100%{box-shadow:0 0 0 0 rgba(251,191,36,.55)}50%{box-shadow:0 0 0 6px rgba(251,191,36,0)}}';
      document.head.appendChild(styleEl);
    }
    cards.forEach(function (a) {
      var href = a.getAttribute('href') || '';
      var m = href.match(/\/blog\/([a-z0-9-]+)/i);
      if (!m) return;
      var slug = m[1];
      var meta = (DN.ARTICLES || []).find(function (x) { return x.slug === slug; });
      if (!meta) return;
      var pub = Date.parse(meta.date);
      if (!pub || NOW - pub > SEVEN_DAYS) return;
      var h3 = a.querySelector('h3');
      if (!h3 || h3.querySelector('.dn-new-pulse')) return;
      var tag = document.createElement('span');
      tag.className = 'dn-new-pulse';
      tag.textContent = 'NEW';
      h3.appendChild(tag);
    });
  };

  DN.injectSpotlight = function () {
    var recentEl = document.getElementById('dn-recent-list');
    var popularEl = document.getElementById('dn-popular-list');
    if (!recentEl && !popularEl) return;
    // Filter out unpublished articles so they don't appear in the homepage
    // "recent" / "popular" spotlights.
    var articles = (DN.ARTICLES || []).filter(function (a) { return !a.unpublished; });
    if (!document.getElementById('dn-spotlight-card-css')) {
      var spotlightStyle = document.createElement('style');
      spotlightStyle.id = 'dn-spotlight-card-css';
      spotlightStyle.textContent =
        '.dn-spotlight-card:hover,.dn-spotlight-card:focus-visible{' +
        'border-color:rgba(122,146,133,.5)!important;' +
        'transform:translateY(-2px)!important;' +
        'box-shadow:0 8px 18px -10px rgba(77,99,88,.25)!important;' +
        'outline:none}';
      document.head.appendChild(spotlightStyle);
    }

    // SVG icon library — keyed by article tag (Chinese match) or fallback
    // 32x32 illustrative line-art icons in teal palette
    var TAG_SVG = {
      '痘痘':       '<circle cx="16" cy="16" r="11" fill="#fff" stroke="#4d6358" stroke-width="1.6"/><circle cx="13" cy="14" r="2.5" fill="#a4b5a8"/><circle cx="20" cy="18" r="1.8" fill="#7a9285"/><circle cx="17" cy="20" r="1.2" fill="#4d6358"/>',
      '防曬':       '<circle cx="16" cy="16" r="6" fill="#a4b5a8" stroke="#4d6358" stroke-width="1.5"/><line x1="16" y1="2" x2="16" y2="6" stroke="#4d6358" stroke-width="2" stroke-linecap="round"/><line x1="16" y1="26" x2="16" y2="30" stroke="#4d6358" stroke-width="2" stroke-linecap="round"/><line x1="2" y1="16" x2="6" y2="16" stroke="#4d6358" stroke-width="2" stroke-linecap="round"/><line x1="26" y1="16" x2="30" y2="16" stroke="#4d6358" stroke-width="2" stroke-linecap="round"/><line x1="6" y1="6" x2="9" y2="9" stroke="#4d6358" stroke-width="2" stroke-linecap="round"/><line x1="23" y1="23" x2="26" y2="26" stroke="#4d6358" stroke-width="2" stroke-linecap="round"/><line x1="6" y1="26" x2="9" y2="23" stroke="#4d6358" stroke-width="2" stroke-linecap="round"/><line x1="23" y1="9" x2="26" y2="6" stroke="#4d6358" stroke-width="2" stroke-linecap="round"/>',
      '異膚':       '<path d="M5 22 Q9 13 16 13 Q23 13 27 22 Z" fill="#fde68a" stroke="#4d6358" stroke-width="1.5" stroke-linejoin="round"/><circle cx="11" cy="20" r="1.4" fill="#dc2626"/><circle cx="18" cy="19" r="1.2" fill="#dc2626"/><circle cx="22" cy="21" r="1" fill="#dc2626"/>',
      '兒童異膚':   '<circle cx="16" cy="13" r="6" fill="#cffafe" stroke="#4d6358" stroke-width="1.5"/><circle cx="14" cy="12" r="0.8" fill="#0f172a"/><circle cx="18" cy="12" r="0.8" fill="#0f172a"/><path d="M14 15 Q16 17 18 15" fill="none" stroke="#0f172a" stroke-width="1.2" stroke-linecap="round"/><path d="M10 26 Q16 21 22 26" fill="none" stroke="#4d6358" stroke-width="1.5" stroke-linecap="round"/>',
      '肝斑 / 美白':'<circle cx="16" cy="16" r="11" fill="#fff" stroke="#4d6358" stroke-width="1.5"/><path d="M10 14 Q12 12 14 13 Q12 16 10 14 Z" fill="#9a3412"/><path d="M19 17 Q22 15 23 18 Q21 20 19 17 Z" fill="#7c2d12"/><circle cx="16" cy="20" r="1.5" fill="#9a3412"/>',
      '玫瑰斑':     '<circle cx="16" cy="16" r="11" fill="#fee2e2" stroke="#dc2626" stroke-width="1.5"/><circle cx="12" cy="14" r="0.8" fill="#dc2626"/><circle cx="20" cy="14" r="0.8" fill="#dc2626"/><circle cx="16" cy="18" r="0.6" fill="#dc2626"/><line x1="10" y1="10" x2="14" y2="12" stroke="#dc2626" stroke-width="1" stroke-linecap="round"/><line x1="22" y1="10" x2="18" y2="12" stroke="#dc2626" stroke-width="1" stroke-linecap="round"/>',
      '落髮':       '<path d="M8 22 Q8 8 16 8 Q24 8 24 22" fill="none" stroke="#4d6358" stroke-width="1.5" stroke-linecap="round"/><line x1="11" y1="9" x2="10" y2="13" stroke="#4d6358" stroke-width="1" stroke-linecap="round"/><line x1="13" y1="8" x2="13" y2="13" stroke="#4d6358" stroke-width="1" stroke-linecap="round"/><line x1="16" y1="8" x2="16" y2="14" stroke="#4d6358" stroke-width="1" stroke-linecap="round"/><line x1="19" y1="8" x2="19" y2="13" stroke="#4d6358" stroke-width="1" stroke-linecap="round"/><line x1="21" y1="9" x2="22" y2="13" stroke="#4d6358" stroke-width="1" stroke-linecap="round"/>',
      '圓禿':       '<circle cx="16" cy="16" r="11" fill="#fff" stroke="#4d6358" stroke-width="1.5"/><circle cx="16" cy="16" r="5" fill="#fde68a" stroke="#9a3412" stroke-width="1"/><line x1="9" y1="9" x2="11" y2="12" stroke="#4d6358" stroke-width="1"/><line x1="23" y1="9" x2="21" y2="12" stroke="#4d6358" stroke-width="1"/>',
      '蕁麻疹':     '<circle cx="11" cy="12" r="3" fill="#fee2e2" stroke="#dc2626" stroke-width="1.2"/><circle cx="20" cy="14" r="3.5" fill="#fee2e2" stroke="#dc2626" stroke-width="1.2"/><circle cx="14" cy="20" r="2.5" fill="#fee2e2" stroke="#dc2626" stroke-width="1.2"/><circle cx="22" cy="22" r="2" fill="#fee2e2" stroke="#dc2626" stroke-width="1.2"/>',
      '乾癬':       '<rect x="6" y="6" width="20" height="20" rx="2" fill="#fee2e2" stroke="#dc2626" stroke-width="1.5"/><line x1="9" y1="10" x2="22" y2="10" stroke="#fef3c7" stroke-width="1.5"/><line x1="10" y1="14" x2="20" y2="14" stroke="#fef3c7" stroke-width="1.5"/><line x1="9" y1="18" x2="23" y2="18" stroke="#fef3c7" stroke-width="1.5"/><line x1="11" y1="22" x2="21" y2="22" stroke="#fef3c7" stroke-width="1.5"/>',
      '香港腳 / 灰指甲':'<path d="M8 24 Q6 18 9 14 Q12 10 17 11 Q21 12 22 16 Q23 22 19 25 Z" fill="#ebe4d8" stroke="#4d6358" stroke-width="1.5"/><circle cx="13" cy="14" r="1" fill="#16a34a"/><circle cx="17" cy="16" r="0.8" fill="#16a34a"/><circle cx="14" cy="20" r="0.6" fill="#16a34a"/>',
      '病毒疣 / HPV':'<circle cx="16" cy="16" r="11" fill="#fff" stroke="#4d6358" stroke-width="1.5"/><circle cx="13" cy="14" r="1.5" fill="#7a9285"/><circle cx="19" cy="13" r="1.2" fill="#7a9285"/><circle cx="17" cy="18" r="1.8" fill="#a4b5a8"/><circle cx="14" cy="20" r="1" fill="#7a9285"/><circle cx="20" cy="20" r="1.2" fill="#7a9285"/>',
      '帶狀皰疹 / 皮蛇':'<path d="M5 16 Q10 8 16 16 Q22 24 27 16" fill="none" stroke="#dc2626" stroke-width="2.2" stroke-linecap="round"/><circle cx="10" cy="14" r="1.2" fill="#fee2e2" stroke="#dc2626"/><circle cx="16" cy="18" r="1.2" fill="#fee2e2" stroke="#dc2626"/><circle cx="22" cy="14" r="1.2" fill="#fee2e2" stroke="#dc2626"/>',
      '白斑':       '<circle cx="16" cy="16" r="11" fill="#a4b5a8" stroke="#4d6358" stroke-width="1.5"/><circle cx="13" cy="13" r="3" fill="#fff"/><circle cx="20" cy="18" r="2.5" fill="#fff"/><circle cx="14" cy="20" r="1.5" fill="#fff"/>',
      '化膿性汗腺炎':'<circle cx="11" cy="14" r="2.5" fill="#fee2e2" stroke="#dc2626" stroke-width="1.5"/><circle cx="21" cy="14" r="2.5" fill="#fee2e2" stroke="#dc2626" stroke-width="1.5"/><circle cx="16" cy="20" r="2" fill="#fee2e2" stroke="#dc2626" stroke-width="1.5"/><line x1="11" y1="14" x2="21" y2="14" stroke="#9a3412" stroke-width="1" stroke-dasharray="2 2"/><line x1="11" y1="14" x2="16" y2="20" stroke="#9a3412" stroke-width="1" stroke-dasharray="2 2"/><line x1="21" y1="14" x2="16" y2="20" stroke="#9a3412" stroke-width="1" stroke-dasharray="2 2"/>',
      '猴痘 Mpox':  '<circle cx="11" cy="11" r="2.2" fill="#fef3c7" stroke="#9a3412" stroke-width="1.2"/><circle cx="21" cy="11" r="2.2" fill="#fef3c7" stroke="#9a3412" stroke-width="1.2"/><circle cx="16" cy="16" r="2.5" fill="#fef3c7" stroke="#9a3412" stroke-width="1.2"/><circle cx="11" cy="22" r="2" fill="#fef3c7" stroke="#9a3412" stroke-width="1.2"/><circle cx="21" cy="22" r="2" fill="#fef3c7" stroke="#9a3412" stroke-width="1.2"/>',
      '生物製劑':   '<rect x="9" y="6" width="14" height="20" rx="3" fill="#cffafe" stroke="#0c5159" stroke-width="1.5"/><rect x="11" y="9" width="10" height="3" fill="#0c5159"/><circle cx="16" cy="18" r="2" fill="#0c5159"/><rect x="14" y="22" width="4" height="3" rx="0.5" fill="#0c5159"/>',
      '酸類 / A 酸':'<path d="M11 5 L11 18 Q11 24 16 24 Q21 24 21 18 L21 5 Z" fill="#cffafe" stroke="#0c5159" stroke-width="1.5"/><path d="M11 5 L21 5" stroke="#0c5159" stroke-width="1.5"/><line x1="13" y1="14" x2="19" y2="14" stroke="#0c5159" stroke-width="1"/><circle cx="14" cy="19" r="0.8" fill="#0c5159"/><circle cx="18" cy="20" r="0.8" fill="#0c5159"/>',
      '常見問題 FAQ':'<circle cx="16" cy="16" r="11" fill="#fff" stroke="#4d6358" stroke-width="1.5"/><path d="M13 13 Q13 10 16 10 Q19 10 19 13 Q19 15 16 16 L16 18" fill="none" stroke="#4d6358" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="16" cy="22" r="1.2" fill="#4d6358"/>',
      '粉瘤 / 表皮囊腫':'<ellipse cx="16" cy="17" rx="9" ry="7" fill="#ebe4d8" stroke="#4d6358" stroke-width="1.5"/><circle cx="16" cy="13" r="1.5" fill="#9a3412"/><line x1="16" y1="11" x2="16" y2="13" stroke="#4d6358" stroke-width="1"/>',
      '雷射 / 光電':'<rect x="6" y="14" width="14" height="4" rx="1" fill="#a4b5a8" stroke="#4d6358" stroke-width="1.2"/><line x1="20" y1="16" x2="28" y2="16" stroke="#dc2626" stroke-width="2" stroke-linecap="round"/><circle cx="28" cy="16" r="1.5" fill="#dc2626"/>',
      '健保 / 自費':'<rect x="6" y="9" width="20" height="14" rx="2" fill="#cffafe" stroke="#0c5159" stroke-width="1.5"/><line x1="6" y1="13" x2="26" y2="13" stroke="#0c5159" stroke-width="1.2"/><line x1="9" y1="18" x2="15" y2="18" stroke="#0c5159" stroke-width="1.2"/><circle cx="22" cy="19" r="1.5" fill="#0c5159"/>',
      '標靶藥物副作用':'<circle cx="16" cy="16" r="11" fill="#fee2e2" stroke="#9a3412" stroke-width="1.5"/><line x1="10" y1="10" x2="22" y2="22" stroke="#9a3412" stroke-width="2" stroke-linecap="round"/><line x1="22" y1="10" x2="10" y2="22" stroke="#9a3412" stroke-width="2" stroke-linecap="round"/>',
      '類固醇藥膏': '<rect x="11" y="5" width="10" height="22" rx="2" fill="#cffafe" stroke="#0c5159" stroke-width="1.5"/><rect x="13" y="3" width="6" height="3" fill="#0c5159"/><line x1="13" y1="11" x2="19" y2="11" stroke="#0c5159" stroke-width="0.8"/><line x1="13" y1="14" x2="19" y2="14" stroke="#0c5159" stroke-width="0.8"/><line x1="13" y1="17" x2="19" y2="17" stroke="#0c5159" stroke-width="0.8"/>',
      '皮膚鏡 AI':   '<rect x="5" y="7" width="22" height="18" rx="5" fill="#eef2ff" stroke="#4d6358" stroke-width="1.5"/><circle cx="11" cy="15" r="2" fill="#a4b5a8"/><circle cx="17" cy="12" r="1.5" fill="#7a9285"/><circle cx="21" cy="18" r="2.4" fill="#4d6358"/><path d="M9 22 C13 18 18 21 24 14" stroke="#0e7c86" stroke-width="1.4" fill="none" stroke-linecap="round"/>'
    };
    // Aliases for tag variants in DN.ARTICLES that don't exactly match TAG_SVG keys
    var TAG_ALIAS = {
      '異位性皮膚炎':   '異膚',
      '健保規範':     '健保 / 自費',
      '口服 A 酸':    '酸類 / A 酸',
      '酸類':         '酸類 / A 酸',
      '外用類固醇':   '類固醇藥膏',
      '常見問題':     '常見問題 FAQ',
      '標靶藥物':     '標靶藥物副作用',
      '猴痘':         '猴痘 Mpox',
      '病毒疣':       '病毒疣 / HPV',
      '皮蛇':         '帶狀皰疹 / 皮蛇',
      '粉瘤':         '粉瘤 / 表皮囊腫',
      '足癬':         '香港腳 / 灰指甲',
      '酒糟肌':       '玫瑰斑',
      '肝斑':         '肝斑 / 美白',
      '美白':         '肝斑 / 美白',
      '痘疤':         '痘痘',
      '結節性癢疹':   '異膚',
      '皮膚淋巴瘤':   '生物製劑',
      'AI 與皮膚科':  '皮膚鏡 AI'
    };
    function svgFor(tag) {
      var resolvedTag = TAG_ALIAS[tag] || tag;
      var content = TAG_SVG[resolvedTag] || TAG_SVG['常見問題 FAQ'];
      return '<svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true" style="flex-shrink:0">' + content + '</svg>';
    }

    function escapeHtml(value) {
      return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function safeSlug(value) {
      var slug = String(value || '');
      return /^[a-z0-9-]+$/.test(slug) ? slug : '';
    }

    function rowHTML(a, badge) {
      var slug = safeSlug(a.slug);
      if (!slug) return '';
      var tagZh = escapeHtml(a.tag || '');
      var tagEn = escapeHtml(a.tag_en || a.tag || '');
      var dateLabel = escapeHtml(a.date || '');
      var titleZh = escapeHtml(a.title || a.slug);
      var titleEn = escapeHtml(a.title_en || a.title || a.slug);
      var num = escapeHtml(DN.getArticleNumber(slug));
      var iconSvg = svgFor(a.tag);
      return '<a class="dn-spotlight-card" href="/blog/' + slug + '" ' +
        'style="display:flex;flex-direction:column;gap:5px;padding:14px 16px;background:#fff;' +
        'border:1px solid var(--border, #dcd5c8);border-radius:12px;text-decoration:none;color:inherit;' +
        'transition:all .15s;box-shadow:0 1px 2px rgba(15,23,42,.04)">' +
        '<div style="display:flex;align-items:center;gap:6px;font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:#4d6358">' +
          (badge ? '<span style="padding:2px 8px;border-radius:9999px;background:' + badge.bg + ';color:' + badge.fg + ';letter-spacing:.08em;font-size:10px">' + badge.label + '</span>' : '') +
          (num ? '<span style="font-family:Inter,sans-serif;letter-spacing:.06em;color:#4d6358;font-weight:800">№' + num + '</span><span style="opacity:.5">·</span>' : '') +
          '<span data-zh="' + tagZh + '" data-en="' + tagEn + '">' + tagZh + '</span>' +
          '<span style="opacity:.5">·</span>' +
          '<time style="font-weight:500;font-family:Inter,sans-serif;letter-spacing:0">' + dateLabel + '</time>' +
        '</div>' +
        '<div style="display:flex;align-items:center;gap:10px">' +
          iconSvg +
          '<div data-zh="' + titleZh + '" data-en="' + titleEn + '" style="font-family:\'Noto Serif TC\',Georgia,serif;font-size:15px;font-weight:700;line-height:1.5;color:#0f172a;flex:1">' + titleZh + '</div>' +
        '</div>' +
      '</a>';
    }

    // Recent: top 2 by date desc (string compare works for YYYY-MM-DD)
    if (recentEl) {
      var sorted = articles.slice().sort(function (a, b) { return (b.date || '').localeCompare(a.date || ''); });
      var topRecent = sorted.slice(0, 2);
      recentEl.innerHTML = topRecent.map(function (a, i) {
        return '<li>' + rowHTML(a, i === 0 ? { label: 'NEW', bg: '#fee2e2', fg: '#991b1b' } : null) + '</li>';
      }).join('');
    }
    // Popular: top 2 from curated DN.POPULAR_PICKS (KV-overridable)
    if (popularEl) {
      var picks = DN.POPULAR_PICKS.map(function (slug) {
        return articles.find(function (a) { return a.slug === slug; });
      }).filter(Boolean).slice(0, 2);
      popularEl.innerHTML = picks.map(function (a, i) {
        return '<li>' + rowHTML(a, { label: '#' + (i + 1), bg: '#dcfce7', fg: '#14532d' }) + '</li>';
      }).join('');
    }
    try { DN.markNewArticles(); } catch (e) { /* ignore */ }
  };


  // Bilingual labels for tag chips. Maps ZH tag → EN tag. Keep in sync with
  // tag keys in DN.TAG_CATEGORIES below.
  DN.TAG_EN = {
    '痘痘 / 痘疤': 'Acne / scars',
    '異位性皮膚炎 / 濕疹': 'Atopic dermatitis / eczema',
    '乾癬': 'Psoriasis',
    '蕁麻疹': 'Urticaria',
    '接觸性皮膚炎': 'Contact dermatitis',
    '玫瑰斑 / 酒糟': 'Rosacea',
    '病毒疣 / HPV': 'Warts / HPV',
    '帶狀皰疹 / 皮蛇': 'Shingles',
    '香港腳 / 灰指甲': 'Tinea / onychomycosis',
    '落髮 / 圓禿': 'Hair loss / alopecia areata',
    '白斑': 'Vitiligo',
    '皮膚癌 / AK': 'Skin cancer / AK',
    '肝斑 / 美白': 'Melasma / whitening',
    '化膿性汗腺炎': 'Hidradenitis suppurativa',
    '兒童 / 嬰幼兒': 'Children / infants',
    '猴痘 Mpox': 'Mpox',
    '處置 / 手術': 'Procedures / surgery',
    '雷射 / 光電': 'Laser / energy devices',
    '類固醇藥膏': 'Topical steroids',
    '生物製劑': 'Biologics',
    '酸類 / A 酸': 'Topical acids / isotretinoin',
    '防曬': 'Sunscreen',
    '標靶藥物副作用': 'Targeted therapy AE',
    '粉瘤 / 表皮囊腫': 'Epidermoid cyst',
    '健保 / 自費': 'NHI / self-pay',
    '常見問題 FAQ': 'FAQ',
    '學習筆記': 'Study notes',
    '最新研究': 'Latest research',
    '全部主題': 'All topics'
  };

  DN.TAG_CATEGORIES = [
    {
      label: '常見疾病',
      label_en: 'Common diseases',
      tags: {
        '痘痘 / 痘疤':       ['acne-myths', 'acne-scar-treatment', 'isotretinoin-patient', 'topical-acids-patient'],
        '異位性皮膚炎 / 濕疹': ['atopic-dermatitis-overview', 'atopic-dermatitis-topical', 'atopic-dermatitis-systemic', 'atopic-dermatitis-special-populations', 'pediatric-eczema', 'topical-steroids-guide', 'biologics-overview', 'prurigo-nodularis', 'dupilumab-long-term-maintenance'],
        '乾癬':              ['psoriasis-overview', 'psoriasis-topical', 'psoriasis-systemic', 'psoriasis-special-populations', 'psoriasis-myths', 'biologics-overview', 'psoriasis-biologic-monitoring'],
        '蕁麻疹':            ['urticaria-myths'],
        '接觸性皮膚炎':      ['contact-dermatitis'],
        '玫瑰斑 / 酒糟':     ['rosacea-myths'],
        '病毒疣 / HPV':      ['warts-myths'],
        '帶狀皰疹 / 皮蛇':   ['shingles-myths'],
        '香港腳 / 灰指甲':   ['tinea-myths', 'toenail-mechanical-disorders'],
        '落髮 / 圓禿':       ['hairloss-myths', 'alopecia-areata'],
        '白斑':              ['vitiligo'],
        '皮膚癌 / AK':       ['actinic-keratosis-scc', 'cutaneous-t-cell-lymphoma', 'targeted-therapy-skin', 'ai-dermatology-roles'],
        '肝斑 / 美白':       ['melasma-myths', 'skin-whitening-agents'],
        '化膿性汗腺炎':      ['hidradenitis-suppurativa'],
        '兒童 / 嬰幼兒':     ['pediatric-eczema'],
        '猴痘 Mpox':         ['mpox-care'],
        '病毒性皮膚感染':    ['warts-myths', 'shingles-myths', 'mpox-care']
      }
    },
    {
      label: '處置 / 治療 / 主題',
      label_en: 'Procedures / Treatments / Topics',
      tags: {
        '處置 / 手術':       ['skin-biopsy-excision', 'epidermoid-cyst', 'actinic-keratosis-scc'],
        '雷射 / 光電':       ['laser-dermatology', 'acne-scar-treatment', 'rosacea-myths'],
        '類固醇藥膏':        ['topical-steroids-guide', 'atopic-dermatitis-overview'],
        '生物製劑':          ['biologics-overview', 'atopic-dermatitis-systemic', 'psoriasis-systemic', 'prurigo-nodularis', 'dupilumab-long-term-maintenance', 'psoriasis-biologic-monitoring', 'hidradenitis-suppurativa'],
        '酸類 / A 酸':       ['topical-acids-patient', 'skin-whitening-agents', 'isotretinoin-patient'],
        '防曬':              ['sunscreen-myths'],
        '標靶藥物副作用':    ['targeted-therapy-skin'],
        '粉瘤 / 表皮囊腫':   ['epidermoid-cyst'],
        '健保 / 自費':       ['nhi-derm-drugs', 'biologics-overview', 'isotretinoin-patient'],
        '常見問題 FAQ':      ['dermatology-faq', 'ai-dermatology-roles'],
        '皮膚科 AI / 數位工具': ['ai-dermatology-roles', 'dermatology-faq']
      }
    },
    {
      // ─── 內容深度（2026-05-11 新增）─────────────────────────────
      // 學習筆記 = 較深度的疾病內容（教學用）
      // 最新研究 = 最新 JAAD / BJD / JEADV 等期刊摘要
      // 這兩個分類用 cat 欄位驅動：articles with cat: 'note' 自動歸到 學習筆記，
      // cat: 'research' 自動歸到 最新研究。Lists are computed dynamically below.
      label: '內容深度',
      label_en: 'Content depth',
      computed: true,  // mark for dynamic resolution
      tags: {
        '學習筆記':         { _from_cat: 'note' },
        '最新研究':         { _from_cat: 'research' }
      }
    }
  ];

  // Backward-compat flat alias — flatten TAG_CATEGORIES into the original TAG_GROUPS shape.
  // Tags whose value is `{ _from_cat: 'note' }` get dynamically resolved to a list of
  // slugs by scanning DN.ARTICLES for matching cat. This lets us drive 學習筆記 / 最新研究
  // entirely from the article's own `cat` field instead of maintaining a separate slug list.
  DN.TAG_GROUPS = (function () {
    var flat = {};
    DN.TAG_CATEGORIES.forEach(function (cat) {
      Object.keys(cat.tags).forEach(function (k) {
        var v = cat.tags[k];
        if (v && typeof v === 'object' && !Array.isArray(v) && v._from_cat) {
          flat[k] = (DN.ARTICLES || []).filter(function (a) {
            return a.cat === v._from_cat;
          }).map(function (a) { return a.slug; });
        } else {
          flat[k] = v;
        }
      });
    });
    return flat;
  })();

  DN.bindArticleHub = function () {
    var hub = document.getElementById('dn-hub');
    if (!hub) return;
    // Exclude unpublished articles from hub spotlight + topic filters.
    var articles = (DN.ARTICLES || []).filter(function (a) { return !a.unpublished; });
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
        '.dn-tag-chips-group{ display:flex; flex-direction:column; gap:10px; margin:0; }' +
        '.dn-tag-chips-row{ display:flex; flex-wrap:wrap; gap:6px; }' +
        '.dn-tag-chips-row-label{ font-size:10.5px; letter-spacing:.18em; text-transform:uppercase; font-weight:700; color:var(--muted,#71695e); margin:6px 0 -2px; padding-top:8px; border-top:1px dashed var(--line, #ebe4d8); width:100%; }' +
        '.dn-tag-chips-row-secondary .dn-tag-chip{ background:#f8fafc; color:#5e574e; font-size:11.5px; padding:4px 10px; border-color:#ebe4d8; }' +
        '.dn-tag-chips-row-secondary .dn-tag-chip.active{ background:linear-gradient(180deg,#94a3b8,#475569); color:#fff; border-color:transparent; }' +
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
        '<input id="dn-search-input" type="search" maxlength="120" placeholder="搜尋症狀、疾病或藥名..." aria-label="搜尋文章" aria-describedby="dn-search-status" />' +
        '<div id="dn-search-status" role="status" aria-live="polite"></div>' +
      '</div>' +
      '<p id="dn-search-help" hidden><a href="' + (document.documentElement.lang.startsWith('en') ? '/en' : '') + '/blog/topics" data-zh="試試較短的詞，或依主題找文章 →" data-en="Try fewer words, or browse by topic →">試試較短的詞，或依主題找文章 →</a></p>' +
      '<div class="dn-tag-chips-group" id="dn-tag-chips"></div>';

    var tagsDiv = document.getElementById('dn-tag-chips');

    // ─── Two-tier rendering (2026-05-09) ─────────────────────────────
    // If DN.TAG_CATEGORIES is defined (new structure), render diseases on
    // a primary row and procedures/topics on a secondary row with a divider.
    // Falls back to flat DN.TAG_GROUPS rendering if categories absent.
    var categories = DN.TAG_CATEGORIES;
    if (categories && categories.length) {
      categories.forEach(function (cat, ci) {
        var rowWrap = document.createElement('div');
        rowWrap.className = 'dn-tag-chips-row' + (ci === 0 ? ' dn-tag-chips-row-primary' : ' dn-tag-chips-row-secondary');

        // Section label (only for secondary group; primary just has [全部主題] and disease chips)
        if (ci > 0) {
          var label = document.createElement('div');
          label.className = 'dn-tag-chips-row-label';
          label.setAttribute('data-zh', cat.label);
          label.setAttribute('data-en', cat.label_en || cat.label);
          label.textContent = cat.label;
          tagsDiv.appendChild(label);
        }

        // Primary row gets the [全部主題] chip first
        if (ci === 0) {
          var allBtn = document.createElement('button');
          allBtn.type = 'button';
          allBtn.className = 'dn-tag-chip dn-tag-all active';
          allBtn.dataset.tag = '__all__';
          allBtn.textContent = '全部主題';
          allBtn.setAttribute('data-zh', '全部主題');
          allBtn.setAttribute('data-en', 'All topics');
          allBtn.addEventListener('click', function () {
        // Explicit 全部主題 click on homepage unconditionally shows ALL
        // visible cards (initial 5-curation only applies on first paint).
        showingAll = true;
        applyFilter('__all__');
        if (showMoreBtn) showMoreBtn.style.display = 'none';
      });
          rowWrap.appendChild(allBtn);
        }

        Object.keys(cat.tags).forEach(function (tag) {
          var btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'dn-tag-chip';
          btn.dataset.tag = tag;
          btn.textContent = tag;
          btn.setAttribute('data-zh', tag);
          btn.setAttribute('data-en', (DN.TAG_EN && DN.TAG_EN[tag]) || tag);
          btn.addEventListener('click', function () {
            applyFilter(tag);
            try { if (typeof gtag === 'function') gtag('event', 'tag_chip_click', { tag: tag, page_path: location.pathname }); } catch (e) {}
          });
          rowWrap.appendChild(btn);
        });

        tagsDiv.appendChild(rowWrap);
      });
    } else {
      // Fallback (single-row, original behavior)
      var allBtn = document.createElement('button');
      allBtn.type = 'button';
      allBtn.className = 'dn-tag-chip dn-tag-all active';
      allBtn.dataset.tag = '__all__';
      allBtn.textContent = '全部主題';
      allBtn.addEventListener('click', function () {
        // Explicit 全部主題 click on homepage unconditionally shows ALL
        // visible cards (initial 5-curation only applies on first paint).
        showingAll = true;
        applyFilter('__all__');
        if (showMoreBtn) showMoreBtn.style.display = 'none';
      });
      tagsDiv.appendChild(allBtn);

      Object.keys(DN.TAG_GROUPS).forEach(function (tag) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'dn-tag-chip';
        btn.dataset.tag = tag;
        btn.textContent = tag;
        btn.setAttribute('data-zh', tag);
        btn.setAttribute('data-en', (DN.TAG_EN && DN.TAG_EN[tag]) || tag);
        btn.addEventListener('click', function () { applyFilter(tag); });
        tagsDiv.appendChild(btn);
      });
    }

    var initialLimit = parseInt(hub.dataset.showCount || '6', 10);
    var showingAll = (mode === 'full');
    var showMoreBtn = null;
    var allCards = Array.prototype.slice.call(document.querySelectorAll('.article-list-item'));
    var searchTimer = null;
    var lastTrackedQuery = '';

    function setActive(tag) {
      var chips = tagsDiv.querySelectorAll('.dn-tag-chip');
      for (var i = 0; i < chips.length; i++) {
        chips[i].classList.toggle('active', chips[i].dataset.tag === tag);
      }
    }
    function setStatus(t) { document.getElementById('dn-search-status').textContent = t; }

    function showBySlugs(slugs) {
      // Keep visual, keyboard and screen-reader order identical. Restore the
      // original catalog order when a topic filter replaces a ranked search.
      var order = slugs || [];
      var parents = new Set(allCards.map(function (card) { return card.parentNode; }));
      parents.forEach(function (parent) {
        allCards.filter(function (card) { return card.parentNode === parent; }).sort(function (a, b) {
          function rank(card) {
            var match = (card.getAttribute('href') || '').match(/\/blog\/([a-z0-9-]+)/);
            var index = match ? order.indexOf(match[1]) : -1;
            return slugs && index !== -1 ? index : order.length + allCards.indexOf(card);
          }
          return rank(a) - rank(b);
        }).forEach(function (card) { parent.appendChild(card); });
      });
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
      clearTimeout(searchTimer);
      document.getElementById('dn-search-help').hidden = true;
      setActive(tag);
      var inp = document.getElementById('dn-search-input');
      if (tag !== '__search__') inp.value = '';

      if (tag === '__all__') {
        if (mode === 'homepage' && !showingAll) {
          showBySlugs(null);
          // Initial homepage paint only: show first N curated cards in
          // DOM order. EXPLICIT 全部主題 click sets showingAll=true (see
          // chip-click handler) → falls through to the else branch.
          // SKIP unpublished slugs from counting toward the limit so the
          // visible card count stays at N even when an article is hidden.
          var unpub = (DN.unpublishedSlugs && DN.unpublishedSlugs()) || [];
          var shown = 0;
          for (var i = 0; i < allCards.length; i++) {
            var href = allCards[i].getAttribute('href') || '';
            var mSlug = href.match(/\/blog\/([a-z0-9-]+)/);
            var cardSlug = mSlug ? mSlug[1] : '';
            var isUnpub = cardSlug && unpub.indexOf(cardSlug) !== -1;
            var visible = !isUnpub && shown < initialLimit;
            if (!isUnpub) allCards[i].style.display = visible ? 'flex' : 'none';
            if (visible) shown++;
          }
          setStatus(shown + ' 篇精選文章');
          if (showMoreBtn) showMoreBtn.style.display = 'block';
        } else {
          showBySlugs(null);
          // Count visible cards (skipping unpublished, which CSS hides)
          var unpubAll = (DN.unpublishedSlugs && DN.unpublishedSlugs()) || [];
          var totalShown = 0;
          for (var ai = 0; ai < allCards.length; ai++) {
            var hrefA = allCards[ai].getAttribute('href') || '';
            var mSlugA = hrefA.match(/\/blog\/([a-z0-9-]+)/);
            var sA = mSlugA ? mSlugA[1] : '';
            if (sA && unpubAll.indexOf(sA) === -1) totalShown++;
          }
          setStatus(totalShown + ' 篇文章');
          if (showMoreBtn) showMoreBtn.style.display = 'none';
        }
      } else if (tag !== '__search__') {
        var ss = DN.TAG_GROUPS[tag] || [];
        var n = showBySlugs(ss);
        setStatus(tag + ' 相關文章');
        if (showMoreBtn) showMoreBtn.style.display = 'none';
        showingAll = true;
      }
    }

    function search(query) {
      var q = DN.normalizeSearchText(query).slice(0, 120);
      clearTimeout(searchTimer);
      if (!q) { applyFilter('__all__'); return; }
      setActive('__search__');
      var matched = DN.searchArticleCatalog(articles, q, DN.ARTICLES_DESC).map(function (a) { return a.slug; });
      var shown = showBySlugs(matched);
      setStatus(document.documentElement.lang.startsWith('en') ? shown + ' results' : '找到 ' + shown + ' 篇文章');
      document.getElementById('dn-search-help').hidden = shown > 0;
      if (showMoreBtn) showMoreBtn.style.display = 'none';
      // Record one settled query, without sending free-form health information.
      searchTimer = setTimeout(function () {
        if (q === lastTrackedQuery || typeof gtag !== 'function') return;
        lastTrackedQuery = q;
        try { gtag('event', 'site_search', { results_count: shown, search_surface: 'article_hub' }); } catch (err) {}
      }, 700);
    }
    var searchInput = document.getElementById('dn-search-input');
    if (document.documentElement.lang.startsWith('en')) {
      searchInput.placeholder = 'Search symptoms, conditions or medicines…';
      searchInput.setAttribute('aria-label', 'Search articles');
    }
    searchInput.addEventListener('input', function (e) {
      if (!e.isComposing) search(e.target.value);
    });
    searchInput.addEventListener('compositionstart', function () { clearTimeout(searchTimer); });
    searchInput.addEventListener('compositionend', function () { search(searchInput.value); });
    var homeSearch = document.getElementById('dn-home-search');
    if (homeSearch) homeSearch.addEventListener('submit', function (e) {
      e.preventDefault();
      searchInput.value = homeSearch.querySelector('input').value;
      search(searchInput.value);
      hub.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block:'start'});
      searchInput.focus({preventScroll:true});
    });

    if (mode === 'homepage') {
      showMoreBtn = document.createElement('button');
      showMoreBtn.type = 'button';
      showMoreBtn.className = 'dn-show-more';
      showMoreBtn.textContent = '↓ 瀏覽全部文章 →';
      showMoreBtn.addEventListener('click', function () {
        // 2026-05-17 — user wants the show-more action to take them to
        // the full /blog/ index (which has every article sorted by date),
        // rather than expanding inline on the homepage. /blog/ is the
        // canonical "browse all" experience.
        window.location.href = '/blog/';
      });
      hub.appendChild(showMoreMakeAccessibility(showMoreBtn));
    }

    // 2026-05-17 — On /blog/ (mode='full'), sort existing cards by
    // DN.ARTICLES date desc AND inject minimal cards for any published
    // article that isn't in the static HTML yet. Fixes:
    //   (a) Random order ("文章排序依據要用更新日期")
    //   (b) /blog/ static HTML missed psoriasis-biologic-monitoring,
    //       dupilumab-long-term-maintenance, perioral-dermatitis-guide,
    //       toenail-mechanical-disorders, dermatologic-oral-examination
    //       (newest 5 were written after this listing was last hand-edited)
    if (mode === 'full') {
      try { sortAndCompleteFullList(); } catch (e) { /* ignore */ }
      allCards = Array.prototype.slice.call(document.querySelectorAll('.article-list-item'));
    }

    applyFilter('__all__');
    try { DN.markNewArticles(); } catch (e) { /* ignore */ }
  };

  // Accessibility passthrough — kept inline so the click handler binding
  // above stays a one-liner. Returns the same element.
  function showMoreMakeAccessibility(btn) {
    btn.setAttribute('data-zh', '↓ 瀏覽全部文章 →');
    btn.setAttribute('data-en', '↓ Browse all articles →');
    btn.setAttribute('aria-label', '瀏覽全部文章');
    return btn;
  }

  // For /blog/ index: reorder existing .article-list-item cards by date
  // (newest first) and inject minimal cards for slugs in DN.ARTICLES that
  // have no static markup yet.
  function sortAndCompleteFullList() {
    var listEl = document.getElementById('dn-article-list')
      || document.querySelector('.article-list');
    if (!listEl) return;
    var articles = (DN.ARTICLES || []).slice().filter(function (a) {
      return !a.unpublished;
    });
    if (articles.length === 0) return;
    var dateBySlug = {};
    articles.forEach(function (a) { dateBySlug[a.slug] = a.date || '1970-01-01'; });

    // Gather existing cards by slug
    var existing = {};
    var cards = Array.prototype.slice.call(listEl.querySelectorAll('a.article-list-item'));
    cards.forEach(function (c) {
      var m = (c.getAttribute('href') || '').match(/\/blog\/([a-z0-9-]+)/);
      if (m) existing[m[1]] = c;
    });

    // Build minimal card for any article missing from DOM
    var generic_svg = '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg" width="40" height="40" fill="none">'
      + '<rect x="6" y="6" width="28" height="28" rx="6" fill="#f1ece4" stroke="#4d6358" stroke-width="1.4"/>'
      + '<line x1="11" y1="14" x2="29" y2="14" stroke="#4d6358" stroke-width="1.4" stroke-linecap="round"/>'
      + '<line x1="11" y1="20" x2="29" y2="20" stroke="#4d6358" stroke-width="1.4" stroke-linecap="round"/>'
      + '<line x1="11" y1="26" x2="22" y2="26" stroke="#4d6358" stroke-width="1.4" stroke-linecap="round"/>'
      + '</svg>';
    var catLabelZh = { rx: '處置 / 治療', myth: '迷思破解', research: '最新研究', note: '學習筆記' };
    var catLabelEn = { rx: 'Treatment', myth: 'Myth-busting', research: 'Latest Research', note: 'Study Notes' };
    articles.forEach(function (a) {
      if (existing[a.slug]) return;
      var card = document.createElement('a');
      card.href = '/blog/' + a.slug;
      card.className = 'article-list-item';
      card.dataset.cat = a.cat || 'note';
      if (a.tag_en) card.dataset.tagEn = a.tag_en;
      var clz = catLabelZh[a.cat || 'note'] || '文章';
      var cle = catLabelEn[a.cat || 'note'] || 'Article';
      // CODE_REVIEW — descriptions live in DN.ARTICLES_DESC (defined at
      // the bottom of THIS file via build-side _normalize_articles_desc.py)
      // instead of DN.ARTICLES to avoid bloating the shared runtime.
      // Cards on /blog/ + homepage need desc; article pages don't.
      var descRec = (DN.ARTICLES_DESC && DN.ARTICLES_DESC[a.slug]) || {};
      var descZh = descRec.desc || '';
      var descEn = descRec.desc_en || descRec.desc || '';
      var cat = escapeHtml(a.cat || 'note');
      var tagZh = escapeHtml(a.tag || '');
      var tagEn = escapeHtml(a.tag_en || a.tag || '');
      var titleZh = escapeHtml(a.title || '');
      var titleEn = escapeHtml(a.title_en || a.title || '');
      var date = escapeHtml(a.date || '');
      var catZh = escapeHtml(clz);
      var catEn = escapeHtml(cle);
      descZh = escapeHtml(descZh);
      descEn = escapeHtml(descEn);
      card.innerHTML =
        '<div class="al-icon cat-' + cat + '">' + generic_svg + '</div>' +
        '<div class="al-body"><div class="al-meta">' +
          '<span class="chip cat-' + cat + '" data-zh="' + catZh + '" data-en="' + catEn + '">' + catZh + '</span>' +
          (tagZh ? '<span class="chip tag" data-zh="' + tagZh + '" data-en="' + tagEn + '">' + tagZh + '</span>' : '') +
          '<time>' + date + '</time>' +
        '</div>' +
        '<h2 data-zh="' + titleZh + '" data-en="' + titleEn + '">' + titleZh + '</h2>' +
        (descZh ? '<p data-zh="' + descZh + '" data-en="' + descEn + '">' + descZh + '</p>' : '') +
        '</div><div class="al-arrow">→</div>';
      listEl.appendChild(card);
      existing[a.slug] = card;
    });

    // Sort: descending by date (newest first), tie-break by slug for stability
    var ordered = Array.prototype.slice.call(listEl.querySelectorAll('a.article-list-item'))
      .sort(function (a, b) {
        var sa = (a.getAttribute('href') || '').match(/\/blog\/([a-z0-9-]+)/);
        var sb = (b.getAttribute('href') || '').match(/\/blog\/([a-z0-9-]+)/);
        var da = sa ? (dateBySlug[sa[1]] || '0000-00-00') : '0000-00-00';
        var db = sb ? (dateBySlug[sb[1]] || '0000-00-00') : '0000-00-00';
        if (da !== db) return db < da ? -1 : 1;
        return (sa ? sa[1] : '') < (sb ? sb[1] : '') ? -1 : 1;
      });
    ordered.forEach(function (c) { listEl.appendChild(c); }); // re-append = move to end in new order
  }

// dn-articles-desc:start
  DN.ARTICLES_DESC = {
    'acne-myths': {desc:'痘痘擠掉就好？牙膏點痘有效？青春期才會長？整理 8 個常見痘痘迷思，從保養、飲食、藥膏、A 酸、抗生素到就醫時機，說明哪些作法可能讓發炎與痘疤惡化，幫助民眾避開擠痘、過度清潔與錯誤偏方，並建立較安全的治療期待。',desc_en:'Clear answers to common acne myths: popping pimples, toothpaste spot treatment, dry skin acne, washing frequency, supplements, scars, and when to see a dermatologist.'},
    'acne-scar-treatment': {desc:'痘疤完整治療指引：冰鑿 / 廂車 / 滾動凹疤怎麼分？紅疤、黑色素沉著、肥厚疤、蟹足腫如何處理？4 種凹疤治療對照表 + 飛梭雷射 / TCA CROSS / 皮下分離選擇邏輯。',desc_en:'Acne can be treated, but acne scars are the trickiest. The key is to identify the scar type first — ice-pick, boxcar, rolling, hypertrophic, post-inflammatory...'},
    'actinic-keratosis-scc': {desc:'日光性角化症是皮膚癌前病變、會進展為鱗狀細胞癌。整合 BAD 2017 / AAD 2021 / BAD 2022 五大指引：Olsen 分級、cryotherapy / 5-FU / imiquimod / PDT / Mohs 切除選擇。',desc_en:'Actinic keratosis (AK) precancerous skin lesion Bowen disease cutaneous SCC in situ cutaneous squamous cell carcinoma (cSCC) the same UV-driven carcinogenic spectrum'},
    'ai-dermatology-roles': {desc:'2026 三篇 JAAD 研究綜合：Kremer 眼動追蹤（DEXI 熱圖 r=0.540、5/20 顆黑色素瘤誤判）、Mahajan 多模態 LLM 看 12 種發炎性皮膚病（GPT-5 46.2%、深膚色準確率掉 13%）、Cao 數位轉錄秘書。AI 在皮膚科的三條前線與限制。',desc_en:'Resident-level research review integrating 2026 JAAD Reviews and the JAAD eye-tracking study comparing dermatologist gaze maps with DEXI dermoscopy AI heat maps...'},
    'alopecia-areata': {desc:'圓禿(Alopecia areata、俗稱鬼剃頭)是自體免疫疾病、台灣終生風險 1.7-2.1%。SALT 分級評估嚴重度、輕中度用病灶內類固醇注射 + Minoxidil、重度用 JAK 抑制劑(Baricitinib)。',desc_en:'Alopecia areata (AA) is an autoimmune-driven hair loss. Lifetime risk in Taiwan is ~1.7-2.1%, and 85.5% of patients develop disease before age 40. Mild cases can...'},
    'atopic-dermatitis-overview': {desc:'異位性皮膚炎完整概論：Th2/IL-4/IL-13 為核心的免疫機轉、filaggrin 基因突變、皮膚微生物失衡、Hanifin & Rajka 與 UK Working Party 診斷標準、EASI / SCORAD / IGA / POEM / DLQI 評分系統、4 大誘發因子與分型。陳翊嘉醫師整理。',desc_en:'Atopic dermatitis (AD) is the most common chronic inflammatory skin disease in children. Global pediatric prevalence is 15–30% (2–10% in adults); Taiwan pediatric...'},
    'atopic-dermatitis-special-populations': {desc:'異位性皮膚炎不只是皮膚病：氣喘、過敏性鼻炎、食物過敏、嗜伊紅性食道炎、憂鬱、心血管、感染、白內障；懷孕哺乳藥物、嬰幼兒、老年人。整合 AAD 2022 + 2023 兒童指引。',desc_en:'AD is the skin manifestation of systemic Th2 hyperactivity . AAD 2022 comorbidities guideline (Davis): seven essential screens — asthma (30-50%), allergic rhinitis...'},
    'atopic-dermatitis-systemic': {desc:'異位性皮膚炎中重度全身治療：4 種生物製劑（dupilumab / tralokinumab / lebrikizumab / nemolizumab）、3 種 JAK 抑制劑、光療詳細比較 — 機轉、頻率、療效、副作用、台灣自費年費一次看完。',desc_en:'When AD remains moderate-severe (EASI ≥ 16, IGA ≥ 3) or significantly impacts sleep/work after 4-8 weeks of adequate topical care, step up to systemic therapy. AAD...'},
    'atopic-dermatitis-topical': {desc:'異位性皮膚炎外用治療階梯：保濕（每天 ≥ 250 g）、外用類固醇 1-7 級、TCI、PDE4i、外用 JAK 抑制劑、tapinarof、roflumilast、wet wrap — 依 AAD 2023 + UpToDate 2024 整理。',desc_en:'80% of atopic dermatitis is controlled with topical therapy . Three pillars: (1) Daily moisturizer ≥ 250 g/week, soak-and-seal within 3 minutes after bathing; (2)...'},
    'bimekizumab-hidradenitis-suppurativa': {desc:'化膿性汗腺炎（HS）新生物製劑 bimekizumab 同時抑制 IL-17A 與 IL-17F。2026 BJD 評讀 BE-HEARD I/II 三期試驗：第 16 週約半數達 HiSCR 50、DLQI 與疼痛改善；但安慰劑反應高達 31%、candida 感染常見、長期續用率下降。含台灣定位。',desc_en:'Bimekizumab is a newer biologic that inhibits both IL-17A and IL-17F. A 2026 British Journal of Dermatology critically appraised topic (McCarthy & Ring) reviews its...'},
    'biologics-overview': {desc:'皮膚科生物製劑 + 小分子標靶藥完整總覽：Dupilumab、Secukinumab、Guselkumab、Risankizumab、Adalimumab、JAK 抑制劑等 — 機轉、適應症、施打頻率、健保 / 自費價格、副作用、必要篩檢一次看完。',desc_en:'Over the past decade, the biggest revolution in dermatology has been the arrival of biologics and small-molecule targeted therapies. From psoriasis, atopic...'},
    'contact-dermatitis': {desc:'接觸性皮膚炎分過敏型(ACD)與刺激型(ICD)兩大類：常見過敏原(鎳、香料、防腐劑、染髮劑)、Patch Test 判讀、避開過敏原、外用類固醇 / TCI、光療。整理 BAD 2017 指引。',desc_en:'Contact dermatitis is redness, itching, and scaling caused by skin contact with an external substance. It has two major types: allergic contact dermatitis (ACD), in...'},
    'cutaneous-t-cell-lymphoma': {desc:'皮膚 T 細胞淋巴瘤（CTCL）75% 為蕈狀肉芽腫（MF）。本文整理 TDA 2024 共識的診斷、TNMB 分期、外用 / NB-UVB / PUVA、Bexarotene、Methotrexate、生物製劑與鑑別診斷重點。皮膚科醫師整理。',desc_en:'Cutaneous T-cell lymphoma (CTCL) is a rare non-Hodgkin lymphoma arising from malignant T cells in the skin. 75% are mycosis fungoides (MF); the remainder are Sézary...'},
    'dermatologic-oral-examination': {desc:'嘴破超過兩週沒好、嘴唇白色蕾絲狀紋路、牙齦反覆剝離流血，可能不是牙科而是皮膚科問題。整理口腔扁平苔癬、復發性口瘡、口腔白斑（檳榔風險）、類天疱瘡、光線性唇炎等 6 大病灶圖鑑與切片時機。整合 2026 JAAD CME。',desc_en:'An ulcer not healing in 2 weeks, white lacy oral patches, or peeling gums often belong to dermatology, not dentistry. Patient-friendly guide to 6 oral mucosal...'},
    'dermatology-faq': {desc:'皮膚科 25 個民眾最常見問題一次解答：A 酸為什麼晚上擦？類固醇能擦多久？保養品順序？痘痘可以擠嗎？防曬要卸妝嗎？孕婦可以擦什麼？健保 vs 自費？陳翊嘉醫師整理。',desc_en:'A curated collection of the 25 most-searched dermatology questions on PTT, Dcard, and Google. Grouped into 5 categories: medication use, skincare combinations, acne...'},
    'dupilumab-long-term-maintenance': {desc:'杜避炎（dupilumab）治療後，什麼時候會討論減量或停藥？整理維持治療與復發研究、研究限制及台灣健保資訊，協助你在回診時與醫師討論療程。',desc_en:'When is reducing or stopping dupilumab discussed? Review maintenance and relapse research, its limitations, and questions to discuss with your doctor.'},
    'epidermoid-cyst': {desc:'粉瘤（表皮囊腫，epidermoid cyst)是皮下圓形腫塊，常被誤認為痘痘而擠破。本文解釋粉瘤跟痘痘怎麼分、為什麼自己擠會反覆復發、發炎時的處置、何時該開刀完整切除、健保給付條件。陳翊嘉醫師（皮膚科）整理。',desc_en:'An epidermoid cyst is a round, mobile subcutaneous mass often mistaken for a pimple — but the two are fundamentally different. The cyst has a complete wall; without...'},
    'hairloss-myths': {desc:'一天掉幾根算正常？染髮會掉髮？戴帽悶了會禿？雄性禿吃中藥就好？Minoxidil 副作用很多？圓禿是壓力造成的？植髮一次解決？7 個民眾最常誤會的落髮觀念，陳翊嘉醫師（皮膚科）整理，附口服+外用治療階梯與植髮指南。',desc_en:'Hair loss is a worry shared by both men and women. New ”hair tonics”, ”follicle serums” appear every month — but only a handful are evidence-based . This article...'},
    'hidradenitis-suppurativa': {desc:'化膿性汗腺炎（HS，反常性痤瘡）盛行率 0.3%，腋下 / 鼠蹊反覆紅腫膿瘡。整理 Hurley 分期、Secukinumab（健保自 2025/7/1 給付）、Adalimumab、手術選擇與台灣健保現況。',desc_en:'Hidradenitis suppurativa (HS, also called acne inversa) is a chronic, relapsing inflammatory follicular disease occurring in friction-prone fold areas (axillae...'},
    'isotretinoin-patient': {desc:'口服 A 酸（Isotretinoin / 羅可坦 / Acnetane）痘痘最強武器完整衛教：誰適合吃、累積劑量怎麼算、肝指數血脂追蹤頻率、避孕至少一個月、雷射禁忌、停藥復發率、台灣健保與自費差別、6 大民眾迷思澄清一次解答。',desc_en:'Oral isotretinoin is the most effective treatment we have for moderate-to-severe acne, the only drug that hits all four causes simultaneously (sebum, keratinization...'},
    'jaki-switching-alopecia-areata': {desc:'重度圓禿第一種 JAK 抑制劑沒效，換第二種值得嗎？2026 JAAD 6 中心 108 人回溯研究：換第二種 48.8% 達 SALT≤20、換第三種 52.4%。第一種有反應是最強預測因子（OR 3.33）。整理換藥路徑、安全性與台灣品名。',desc_en:'When the first JAK inhibitor fails in severe alopecia areata, does switching help? June-2026 JAAD multicenter retrospective (Martin et al., 6 US clinics, n=108)...'},
    'laser-dermatology': {desc:'皮膚科雷射完整對照：532 / 595 / 755 / 1064 / 1550 / 2940 / 10600 nm 等 11 種波長，每個對應哪些斑、痘疤、刺青、毛、紅、痣、疣的適應症與證據強度。依 2022 德國 S2k 雷射指引整理。',desc_en:'Lasers are not the more expensive or newer the better — different wavelengths target different chromophores (pigment, hemoglobin, water), and picking the wrong one...'},
    'melasma-myths': {desc:'肝斑(melasma)是亞洲女性最常見的色素困擾。雷射打一次就消？三合一藥膏越濃越好？停藥反黑？男生不會長？懷孕生完會自己消？7 個最常誤會的肝斑觀念 + 治療階梯。',desc_en:'Melasma is the most common pigmentary concern in Asian women. The questions most often heard in clinic are — ”Is this melasma?”, ”Will one laser session clear it?”...'},
    'mpox-care': {desc:'Mpox 猴痘皮膚照護衛教：整理傳染途徑、皮疹變化、居家傷口照護、何時就醫、隔離注意事項、疫苗與皮膚科常見問題，協助患者與照護者降低傳播、搔抓感染與併發症風險，並掌握需要醫療評估的警訊與追蹤重點流程。',desc_en:'Mpox virus infection causes lymphadenopathy, fever, headache, myalgia, and a skin rash. Most patients recover within weeks on their own. While there is no specific...'},
    'nail-psoriasis-topical-intralesional': {desc:'指甲乾癬擦藥沒效要打針嗎？2026 JAAD 編輯評論整理指甲乾癬的局部與病灶內治療：維生素 D 藥膏、局部 methotrexate + CO2 雷射輔助穿透、病灶內 MTX/類固醇注射，含甲基質麻醉技巧與台灣健保自費實況。',desc_en:'Nail psoriasis is hard to treat because creams cannot cross the thick nail plate and the matrix sits deep. A June-2026 JAAD Letter from the Editor (Elston) reviews...'},
    'nhi-derm-drugs': {desc:'台灣健保皮膚科常用藥物完整規範 — 口服 A 酸、Dupilumab、Adalimumab、Omalizumab、JAK 抑制劑、IL-17 / IL-23 生物製劑、Tacrolimus、MTX、Cyclosporine 給付條件、PASS 流程一次查清楚。',desc_en:'A complete reference of Taiwan NHI rules for commonly prescribed dermatology drugs. Each entry lists: indication, ICD-10 code, NHI coverage criteria, dose, course...'},
    'pediatric-eczema': {desc:'嬰幼兒(0-5 歲)異位性皮膚炎完整照護指南：診斷標準、好發部位、洗澡保濕、外用類固醇 / TCI 安全用法、過敏原檢測、Dupilumab 嬰幼兒適應症、共病風險。整理 2024 德國 S3 指引。',desc_en:'Atopic dermatitis is the most common pediatric skin disease — global childhood prevalence ~10-20% (Germany 13%), Taiwan ~7-10%. Most cases start in infancy (birth to...'},
    'perioral-dermatitis-guide': {desc:'嘴角、鼻翼周圍反覆紅疹，是口周皮膚炎、痘痘還是濕疹？整理常見表現、可能誘因、鑑別重點與就醫時機，並說明醫師如何評估治療。',desc_en:'Recurring rash around the mouth or nose: perioral dermatitis, acne or eczema? Read about symptoms, possible triggers, diagnosis and when to seek care.'},
    'photodynamic-therapy-overview': {desc:'光動力治療（PDT）原理機轉、ALA 與 MAL 光敏劑、紅光與藍光選擇、12 大適應症按證據等級（AK、BCC、Bowen disease、痘痘、酒紅斑、光老化等）完整整理。整合 2026 JAAD 兩篇 CME Review。患者 7 題 FAQ + 臨床雙軌寫法。',desc_en:'In June 2026, the Journal of the American Academy of Dermatology published two CME Reviews on photodynamic therapy (PDT): Part I covers mechanism and photosensitizers...'},
    'prurigo-nodularis': {desc:'Prurigo nodularis（PN）中文是結節性癢疹。整理疾病定義、搔癢與結節表現、診斷評估及治療選項，附醫學文獻與量表說明。',desc_en:'Prurigo nodularis (PN) is called 結節性癢疹 in Chinese. Read about its definition, itch and nodules, diagnostic assessment, treatment options and references.'},
    'psoriasis-biologic-monitoring': {desc:'打乾癬生物製劑要不要每年抽血？2026 JAAD 系統性回顧用 USPSTF 評級重新看：TNF-α 仍需結核 + B 肝；IL-17 問口腔念珠菌 + 腸道症狀；IL-23 大多不必。整合台灣健保落差。',desc_en:'This systematic review (Duong JQ et al, JAAD 2026;94:1438-46; published online January 2026, in print May 2026) applies USPSTF A/B/C/D/I evidence grades to the...'},
    'psoriasis-myths': {desc:'乾癬是癬嗎？會傳染？要避開太陽？類固醇會傷皮膚？生物製劑會傷免疫？7 個最常誤會的乾癬(psoriasis)觀念 + IL-17 / IL-23 致病機轉圖 + 健保給付條件。',desc_en:'Immune system dysregulation Plain-language dermatology patient education by Dr. Yi-Jia Chen, summarized from medical literature and clinical guidelines.'},
    'psoriasis-overview': {desc:'乾癬（psoriasis）是免疫介導 Th17 / IL-23 慢性發炎皮膚病。本文整理 6 大臨床亞型、嚴重度評估（BSA / PASI / IGA / DLQI）、誘發因子、合併症警訊、鑑別診斷重點。皮膚科醫師整理。',desc_en:'Psoriasis is an immune-mediated chronic inflammatory skin disease — sharply demarcated erythematous plaques with silvery scale on scalp/elbows/knees/lower back. It is...'},
    'psoriasis-special-populations': {desc:'乾癬合併症(乾癬性關節炎 PsA、心血管、代謝症候群、肝病、憂鬱、IBD)篩檢與處理；特殊族群(懷孕、哺乳、兒童、指甲乾癬、紅皮症型)治療策略。整理 AAD-NPF 2019-2020 指引。',desc_en:'Psoriasis comorbidities and special populations: psoriatic arthritis screening, cardiovascular risk, pregnancy / breastfeeding biologic safety, pediatric...'},
    'psoriasis-systemic': {desc:'乾癬中重度全身性治療完整衛教：光療（NB-UVB / PUVA / Excimer）、口服 MTX / cyclosporine / acitretin / apremilast / deucravacitinib、生物製劑、台灣健保給付完整解析。',desc_en:'For moderate-to-severe psoriasis (BSA &gt; 10%, PASI &gt; 10, DLQI &gt; 10) or topical-refractory disease, three modern options: (1) Phototherapy NB-UVB (first-line...'},
    'psoriasis-topical': {desc:'乾癬外用治療階梯：類固醇 1-7 級、calcipotriol / calcitriol、強強複方（Daivobet）、tazarotene、TCI、coal tar 與特殊部位（臉、皺褶、頭皮、指甲）治療 — 依 AAD-NPF 2021 整理。',desc_en:'Topical therapy controls 80% of mild-moderate psoriasis . Three pillars per AAD-NPF 2021 (Elmets): (1) topical corticosteroids (potency 1-7 by site), (2) vitamin D...'},
    'rosacea-myths': {desc:'玫瑰痤瘡（酒糟）會自己好嗎？要用類固醇嗎？整理 BAD 2021 + TDA 2022 共識：表現型分類、Demodex 角色、外用 Ivermectin / Metronidazole / Azelaic acid、口服低劑量 doxycycline、雷射 6 大迷思。',desc_en:'Rosacea myth-busting: subtype identification, ETR vs PPR vs phymatous vs ocular, treatment ladder (topical metronidazole / ivermectin / brimonidine, oral doxycycline...'},
    'semaglutide-hair-loss': {desc:'2026 JAAD 兩篇 TriNetX 研究：semaglutide / tirzepatide 1 年新發掉髮風險 1.77–1.98 倍、雄性禿 anytime 2.41 倍；但對已有疤痕性禿髮患者反而降低治療需求 30–47%。患者 7 題 FAQ + 機轉雙路徑解析。',desc_en:'In June 2026 the Journal of the American Academy of Dermatology published two large TriNetX cohort studies whose conclusions look contradictory but are in fact...'},
    'severe-scabies-treatment': {desc:'嚴重疥瘡反覆治不好？廣泛 + 結痂型疥瘡標準治療：口服 ivermectin（D0 / 7 / 14）+ 外用 5% permethrin（D0 / 7），Day 28 治癒率 ~82%。依 2026 NEJM GALE CRUSTED RCT 整理。',desc_en:'Severe scabies (profuse or crusted, with hundreds to thousands of mites) does not respond to single-dose treatment. Patient-friendly guide based on the May 2026 NEJM...'},
    'shingles-myths': {desc:'皮蛇繞一圈會死？是壓力造成？年輕人不會得？抗病毒藥要 72 小時內吃？Shingrix 疫苗值得嗎？6 個最常誤會的帶狀皰疹(herpes zoster)觀念 + 治療階梯 + 疫苗比較。',desc_en:'Shingles varicella zoster virus (VZV) Antiviral not started within 72 hours Plain-language dermatology patient education by Dr. Yi-Jia Chen, summarized from medical...'},
    'skin-biopsy-excision': {desc:'皮膚切片(shave / punch / excisional)與良性腫瘤切除手術完整衛教：4 種切片技術、痣 / 老人斑 / 脂肪瘤、ABCDE 警訊、梭形切除、麻醉、縫合、術後敷料、拆線時間、健保自費。',desc_en:'Patient-friendly dermatology guide to skin biopsy and tumor excision: indications, technique, post-op wound care, scar care, and follow-up. Integrates AAD biopsy...'},
    'skin-whitening-agents': {desc:'美白淡斑成分大解析：氫醌、傳明酸、杜鵑花酸、維他命 C、菸鹼醯胺、A 酸、麴酸、熊果素 — 每個成分機轉、有效濃度、副作用、孕期能否使用、混搭禁忌、藥用 vs 醫美 vs 保養品差別、痘疤與肝斑適用一次看完。',desc_en:'For brightening, fading post-inflammatory marks, melasma, and sun spots — which ingredients actually work, and which are marketing fluff? This article reviews the...'},
    'spironolactone-dermatology-safety': {desc:'2026 JAAD 兩篇研究：≥45 歲女性吃 spironolactone 整體高血鉀 10.1%、≥65 歲 + 共病 28.1%；但 97.5% 屬輕度、62.5% 不影響處置。合併低劑量 minoxidil 同時起始反而少 64.8% 多毛。含分層監測與台灣自費實況。',desc_en:'Two June-2026 JAAD studies from Mass General Brigham synthesized: Gregoire et al. (n=398) — in women ≥45 on spironolactone for dermatologic indications, overall...'},
    'sunscreen-myths': {desc:'防曬 8 大迷思完整整理：室內陰天要不要擦、防曬係數 SPF 怎麼選、物理與化學防曬差異、補擦時機、敏感肌選擇與常見錯誤觀念，協助建立更穩定的日常防曬習慣，降低曬傷、曬黑與光老化風險，提升防曬執行度。',desc_en:'A dermatologist explains sunscreen myths about indoor light, cloudy days, SPF numbers, UVA and PA ratings, mineral versus chemical filters, acne-prone skin, and melasma.'},
    'targeted-therapy-skin': {desc:'肺癌 NSCLC TKI 標靶藥(Gefitinib、Erlotinib、Afatinib、Osimertinib)常引起皮膚副作用：痤瘡樣皮疹、乾皮、甲溝炎、手足症候群。整合臺灣肺癌學會 + 皮膚科醫學會 2024 共識。',desc_en:'Targeted therapy (TKIs, EGFR inhibitors) is mainstay treatment for non-small-cell lung cancer (NSCLC) in Taiwan but commonly causes skin side effects — papulopustular...'},
    'tinea-myths': {desc:'香港腳是穿不透氣鞋造成的？灰指甲塗藥膏就好？會傳染給家人？熱水泡腳能殺菌？口服抗黴菌藥傷肝？7 個最常誤會的香港腳 / 灰指甲觀念 + 口服外用治療階梯。',desc_en:'Athletes foot (tinea pedis) and nail fungus (onychomycosis) are the most common fungal skin infections in Taiwan, yet many people fail treatment — not because the...'},
    'toenail-mechanical-disorders': {desc:'腳趾甲變黃變厚不一定是灰指甲——9 成趾甲變形其實來自鞋子壓迫與腳型。整理 12 種常見趾甲變形（剝離、嵌甲、Beau’s line、夾擊甲等）、4 種足部結構異常與糖尿病趾甲照護，含台灣健保藥品與商品名。整合 2026 JAAD review。',desc_en:'Over 90% of toenail dystrophy is mechanical, not fungal. Patient-friendly guide to the 12 most common types (onycholysis, subungual heloma, Beau lines, retronychia...'},
    'topical-acids-patient': {desc:'A酸、A醇、杜鵑花酸、果酸與水楊酸有什麼差別？從五大酸類比較、入門方式、搭配問題到使用時的不適，依照你的問題找到對應段落。',desc_en:'Compare retinoids, retinol, azelaic acid, AHA and salicylic acid. Find sections on their differences, getting started, combining products and irritation.'},
    'topical-steroids-guide': {desc:'類固醇藥膏怎麼分強弱？臉 / 身體 / 手腳該用哪一級？指尖單位(FTU)怎麼算？可以擦多久？懷孕能用嗎？7 級類固醇藥膏分類 + 台灣常見品名 + 停藥反彈 + 類固醇恐懼症解析。',desc_en:'Topical corticosteroids are among the most prescribed drugs in dermatology, but topical steroid phobia (TCS phobia) drives many patients to stop early or seek folk...'},
    'urticaria-myths': {desc:'蕁麻疹一定是過敏？反覆發作是免疫力差？抗組織胺會嗜睡上癮？會傳染？慢性蕁麻疹治不好？食物過敏檢測有用嗎？6 個最常誤會的蕁麻疹(風疹塊)觀念 + 治療階梯。',desc_en:'Urticaria (hives) is one of the most common skin complaints in Taiwan dermatology clinics, with a lifetime prevalence of 15-20%. But many patients ask: Did I eat...'},
    'vitiligo': {desc:'白斑(Vitiligo)是自體免疫色素脫失疾病、全球盛行率 1-2%。依臺灣皮膚科醫學會 2024 共識整理：分節 vs 非分節型、外用 Ruxolitinib / Tacrolimus、NB-UVB / 308nm Excimer。',desc_en:'Vitiligo is autoimmune-driven depigmentation of the skin. Global prevalence is 1-2%, affecting all ages, sexes, and ethnicities. While not painful or...'},
    'vitiligo-maintenance-clinical': {desc:'非分節型白斑治療成功後仍約三分之一會復發。整理 Shih HY、Ng CY 2026 Br J Dermatol 長庚 809 人世代：手腳病灶、甲狀腺、其他自體免疫是三大預測因子；手腳合併甲狀腺 2.5 倍。',desc_en:'After 6 months of stability following successful repigmentation, about one-third (32.9%) of patients with non-segmental vitiligo experience recurrence/relapse within...'},
    'warts-myths': {desc:'病毒疣會自己好嗎？香蕉皮、大蒜可以治嗎？冷凍要打幾次？雷射打一次就消嗎？HPV 跟疫苗有關嗎？6 個民眾最常誤會的病毒疣（HPV viral warts）觀念，陳翊嘉醫師（皮膚科）整理，附 HPV 型別與部位對照、冷凍 / 雷射 / 免疫療法治療階梯。',desc_en:'Common warts (HPV) myth-busting: does banana peel work, can one laser session cure, will warts self-resolve, when to see a dermatologist. Treatment ladder included.'},
  };
  // dn-articles-desc:end

})();
