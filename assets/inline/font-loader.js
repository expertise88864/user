// Google Fonts is optional presentation; a slow response must not hide text.
(function () {
  document.querySelectorAll('link[data-dn-fonts]').forEach(function (link) {
    var queued = false;
    function apply() {
      if (queued) return;
      queued = true;
      // Deferred scripts can still execute before first paint. Let the system
      // font page paint before optional font CSS joins the rendering work.
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { link.media = 'all'; });
      });
    }
    link.addEventListener('load', apply, { once: true });
    // The stylesheet may have finished before this deferred script runs.
    if (link.sheet) apply();
  });
})();
