(function(){
// 2026-05-09 — Bot-aware analytics loader. Skip GA/Clarity/AdSense when:
//   (a) UA matches known bots/crawlers (incl. AI training & SEO scrapers)
//   (b) hostname is localhost / 127.0.0.1 / [::1] (local static tests)
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
function getTrafficType(){
  // Allow flagging via ?ga_internal=1 (sticks via localStorage)
  try {
    if (location.search.indexOf('ga_internal=1') !== -1) {
      localStorage.setItem('dn-ga-internal', '1');
      return 'internal';
    }
    if (location.search.indexOf('ga_internal=0') !== -1) {
      localStorage.removeItem('dn-ga-internal');
    }
    if (localStorage.getItem('dn-ga-internal') === '1') return 'internal';
  } catch(e) {}
  if (isInternalPage()) return 'internal';
  return null;
}
function load() {
  if (isBot() || isLocalStaticHost()) return; // skip everything for bots/local static tests
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
  // Clarity
  (function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
  t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
  y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);})(window,document,"clarity","script","wkvhe0mf7y");
  // GA4
  var ga = document.createElement("script");
  ga.async = true;
  ga.src = "https://www.googletagmanager.com/gtag/js?id=G-XFF3L5QD10";
  document.head.appendChild(ga);
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  window.gtag = gtag;
  gtag("js", new Date());
  var cfg = { anonymize_ip: true };
  var tt = getTrafficType();
  if (tt) cfg.traffic_type = tt; // GA4 picks up traffic_type for "Internal traffic" filter
  gtag("config", "G-XFF3L5QD10", cfg);
  // --- Engagement / key events (GA4). Defensive: only runs once analytics
  // has loaded (i.e. not for bots/localhost). These complement GA4 Enhanced
  // Measurement (which already covers page_view, scroll, outbound clicks,
  // site search via URL, and file downloads). Mark the ones you care about as
  // "key events" in GA4 → Admin → Events.
  try {
    // Internal article navigation — topical journeys (not covered by EM).
    document.addEventListener("click", function (e) {
      var t = e.target;
      var a = (t && t.closest) ? t.closest('a[href]') : null;
      if (!a) return;
      var href = a.getAttribute("href") || "";
      if (/^\/(en\/)?blog\/[a-z0-9-]+/.test(href)) {
        gtag("event", "select_content", { content_type: "article", item_id: href });
      }
    }, { capture: true, passive: true });
    // Search intent — Pagefind opens a JS modal EM cannot see.
    var sb = document.getElementById("dn-nav-search");
    if (sb) sb.addEventListener("click", function () {
      gtag("event", "site_search_open");
    }, { passive: true });
    // Language toggle usage.
    var lt = document.getElementById("langToggle");
    if (lt) lt.addEventListener("change", function () {
      gtag("event", "language_toggle", { language: lt.value });
    }, { passive: true });
  } catch (e) {}
}
// Load 3rd-party after first paint (idle callback or 1s fallback)
if ("requestIdleCallback" in window) {
  requestIdleCallback(load, { timeout: 2500 });
} else {
  setTimeout(load, 1500);
}
})();