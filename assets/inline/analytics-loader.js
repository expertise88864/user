(function(){
if (window.dnAnalyticsInstalled) return;
window.dnAnalyticsInstalled = true;
// 2026-05-09 — Bot-aware analytics loader. Skip GA/Clarity/AdSense when:
//   (a) UA matches known bots/crawlers (incl. AI training & SEO scrapers)
//   (b) hostname is localhost / 127.0.0.1 / [::1] (local static tests)
//   (c) origin differs from the canonical HTTPS production site. Preview and
//       alias traffic must not enter the production GA4 or Clarity property.
// CODE_REVIEW TD-51 — this header used to claim /admin and /reset-sw were
// SKIPPED too. They are not: isInternalPage() only TAGS the session as
// traffic_type="internal". Those pages simply never include this file, which
// is what actually keeps trackers off them — now asserted by
// _check_third_party.py instead of being left to a comment.
// Tag GA traffic_type="internal" when ?ga_internal=1 or localStorage flag.
// This dramatically reduces bot noise in GA4 (the platform's built-in
// "filter known bots" only covers IAB/ABC list, missing AI crawlers + scrapers).
var BOT_RE = /bot|crawl|spider|slurp|mediapartners|adsbot|yandex|bingbot|googlebot|duckduckbot|baiduspider|facebookexternalhit|twitterbot|telegrambot|whatsapp|linkedinbot|applebot|petalbot|ahrefsbot|semrushbot|mj12bot|dotbot|seznambot|gptbot|chatgpt|ccbot|claudebot|claude-web|anthropic-ai|perplexitybot|bytespider|amazonbot|cohere-ai|diffbot|datasforseo|blexbot|zoominfobot|barkrowler|timpibot|omgili|headlesschrome|phantomjs|puppeteer|electron|jsdom/i;
function isBot(){ try{ return BOT_RE.test(navigator.userAgent || ''); }catch(e){ return false; } }
function isInternalPage(){
  var p = location.pathname;
  return p.indexOf('/admin') === 0 || p.indexOf('/reset-sw') === 0;
}
function isLocalStaticHost(){
  return /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname);
}
function isProductionOrigin(){
  return location.origin === 'https://chendermatologist.com';
}
function getTrafficType(){
  // Allow flagging via ?ga_internal=1 (sticks via localStorage)
  try {
    var internalFlag = new URL(location.href).searchParams.get('ga_internal');
    if (internalFlag === '1') {
      localStorage.setItem('dn-ga-internal', '1');
      return 'internal';
    }
    if (internalFlag === '0') {
      localStorage.removeItem('dn-ga-internal');
    }
    if (localStorage.getItem('dn-ga-internal') === '1') return 'internal';
  } catch(e) {}
  if (isInternalPage()) return 'internal';
  return null;
}
// Install the event facade before deferred page initialization. Tracker scripts
// still wait for idle; a slow or blocked request must not change UI bindings.
// The bounded pre-load queue also prevents unlimited retention when blocked.
var pending = [];
var started = false;
var ready = false;
var enabled = !isBot() && !isLocalStaticHost() && isProductionOrigin();
function cleanUrl(value) {
  if (!value) return '';
  try {
    var url = new URL(value, location.href);
    if (!/^https?:$/.test(url.protocol)) return '';
    return url.origin + url.pathname;
  } catch (_) { return ''; }
}
function safeParams(params) {
  var safe = {};
  Object.keys(params || {}).forEach(function (key) {
    // Free-form medical searches and URL query/fragment values are private.
    if (/search_term|search_query|query|email/i.test(key) || /^(lcp_element|lcp_url|cls_target|inp_target)$/.test(key)) return;
    var value = params[key];
    if (typeof value === 'string') {
      if (/url|destination|item_id|page_location|page_referrer|feed|lcp_url/.test(key)) {
        value = cleanUrl(value);
      }
      safe[key] = value.slice(0, 100);
    } else if (typeof value === 'boolean' || (typeof value === 'number' && isFinite(value))) {
      safe[key] = value;
    }
  });
  return safe;
}
function push(command) {
  if (ready || window.dataLayer.length < 100) {
    // Match Google's documented gtag queue shape (Arguments, not an object).
    (function () { window.dataLayer.push(arguments); }).apply(null, command);
  }
}
window.gtag = function (kind, name, params) {
  // Public callers send events only; configuration stays owned by this loader.
  if (!enabled || kind !== 'event' || !/^[A-Za-z][A-Za-z0-9_]{0,39}$/.test(name)) return;
  var command = ['event', name, safeParams(params)];
  if (started) push(command);
  else if (pending.length < 100) pending.push(command);
};
function load() {
  if (isBot() || isLocalStaticHost()) return; // skip everything for bots/local static tests
  if (!isProductionOrigin()) return;
  if (started) return;
  started = true;
  // AdSense — DISABLED until AdSense approval (audit period).
  // Re-enable by uncommenting the block below. Visible placeholders
  // are also hidden via .ad-slot{display:none!important} in tw-mini.css.
  /* AdSense disabled:
  var ad = document.createElement("script");
  ad.async = true;
  ad.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8223268344248663";
  ad.crossOrigin = "anonymous";
  document.head.appendChild(ad);
  */
  // Session replay is disabled under the search/PII exclusion policy.
  // DOM masking does not protect all page/referrer/clicked URL values.
  // Public content performance remains measured by sanitized GA events below.
  // GA4
  var ga = document.createElement("script");
  ga.async = true;
  ga.src = "https://www.googletagmanager.com/gtag/js?id=G-XFF3L5QD10";
  ga.onload = function () { ready = true; };
  window.dataLayer = window.dataLayer || [];
  push(['js', new Date()]);
  var cfg = {
    anonymize_ip: true,
    page_location: cleanUrl(location.href),
    page_referrer: cleanUrl(document.referrer || ''),
    // Send the initial page view explicitly with sanitized URLs. The GA stream's
    // Enhanced Measurement settings must separately disable URL-based search.
    send_page_view: false
  };
  var tt = getTrafficType();
  if (tt) cfg.traffic_type = tt; // GA4 picks up traffic_type for "Internal traffic" filter
  push(['config', 'G-XFF3L5QD10', cfg]);
  push(['event', 'page_view', {
    page_location: cfg.page_location,
    page_referrer: cfg.page_referrer
  }]);
  pending.forEach(push);
  pending = [];
  document.head.appendChild(ga);
}
// Bind once, before idle. Queued events are delivered only if the visitor stays
// until GA loads; navigating away first still discards this in-memory queue.
if (enabled) try {
    // Internal article navigation — topical journeys (not covered by EM).
    document.addEventListener("click", function (e) {
      var t = e.target;
      var a = (t && t.closest) ? t.closest('a[href]') : null;
      if (!a) return;
      var href = a.getAttribute("href") || "";
      if (/^\/(en\/)?blog\/[a-z0-9-]+/.test(href)) {
        var area = a.closest('#article-quick-links, #dn-related-static, #dn-related, .dn-home-topics, .article-list, article');
        var surface = area ? (area.id || (area.matches('.dn-home-topics') ? 'home_topics' : area.matches('.article-list') ? 'article_list' : 'article_body')) : 'navigation';
        window.gtag("event", "select_content", { content_type: "article", item_id: href, navigation_area: surface });
      }
    }, { capture: true, passive: true });
    // site_search_open is emitted by the modal's actual opening transition,
    // covering every header button and keyboard entry without double counting.
    // Language toggle usage.
    var lt = document.getElementById("langToggle");
    if (lt) lt.addEventListener("change", function () {
      window.gtag("event", "language_toggle", { language: lt.value });
    }, { passive: true });
  } catch (e) {}
// Load 3rd-party after first paint (idle callback or 1s fallback)
if ("requestIdleCallback" in window) {
  requestIdleCallback(load, { timeout: 2500 });
} else {
  setTimeout(load, 1500);
}
})();
