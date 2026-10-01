// Google Fonts is optional presentation; a slow response must not hide text.
(function () {
  if (window.dnFontsInstalled) return;
  var links = document.querySelectorAll('link[data-dn-fonts]');
  if (!links.length) return;
  window.dnFontsInstalled = true;
  var painted = false;
  var observer = null;
  var fallbackTimer = null;
  var waiting = [];
  function release() {
    if (painted) return;
    painted = true;
    if (observer) observer.disconnect();
    if (fallbackTimer !== null) clearTimeout(fallbackTimer);
    waiting.forEach(function (apply) { apply(); });
    waiting = [];
  }
  links.forEach(function (link) {
    var loaded = false;
    var applied = false;
    function apply() {
      if (!painted || !loaded || applied) return;
      applied = true;
      link.media = 'all';
    }
    waiting.push(apply);
    link.addEventListener('load', function () { loaded = true; apply(); }, { once: true });
    // Cached CSS may finish before this deferred script runs.
    if (link.sheet) { loaded = true; apply(); }
  });
  // Two animation frames do not prove that text has painted: a busy initial
  // layout can postpone FCP until after both callbacks. Wait for actual paint.
  try {
    if (performance.getEntriesByName('first-contentful-paint').length) {
      release();
      return;
    }
    if (PerformanceObserver.supportedEntryTypes.indexOf('paint') !== -1) {
      observer = new PerformanceObserver(function (list) {
        if (list.getEntries().some(function (entry) { return entry.name === 'first-contentful-paint'; })) release();
      });
      observer.observe({ type: 'paint', buffered: true });
    }
  } catch (_) { /* Paint timing is optional; the post-load fallback remains. */ }
  // Unsupported/broken paint reporting must not disable optional fonts forever.
  // This compatibility path runs after load, outside the initial parser work.
  function fallback() {
    if (painted) return;
    fallbackTimer = setTimeout(function () {
      requestAnimationFrame(function () { requestAnimationFrame(release); });
    }, 2000);
  }
  if (document.readyState === 'complete') fallback();
  else window.addEventListener('load', fallback, { once: true });
})();
