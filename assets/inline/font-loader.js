// Google Fonts is optional presentation; a slow response must not hide text.
(function () {
  document.querySelectorAll('link[data-dn-fonts]').forEach(function (link) {
    function apply() { link.media = 'all'; }
    link.addEventListener('load', apply, { once: true });
    // The stylesheet may have finished before this deferred script runs.
    if (link.sheet) apply();
  });
})();
