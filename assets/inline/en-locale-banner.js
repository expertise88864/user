
try {
  localStorage.setItem('dn_lang', 'en');
  document.cookie = 'dn_lang=en;path=/;max-age=31536000;samesite=lax';
} catch (e) {}
document.addEventListener('DOMContentLoaded', function () {
  var sw = document.getElementById('dn-en-banner-zh');
  if (!sw) return;
  var target = new URL(sw.href);
  if (target.origin !== location.origin) return;
  var fragments = {};
  try { fragments = JSON.parse(sw.getAttribute('data-dn-zh-fragments') || '{}'); } catch (e) {}
  function updateReturnLink() {
    var fragment = location.hash;
    try {
      var id = decodeURIComponent(fragment.slice(1));
      if (fragments && Object.prototype.hasOwnProperty.call(fragments, id) && typeof fragments[id] === 'string') {
        fragment = '#' + encodeURIComponent(fragments[id]);
      }
    } catch (e) {}
    sw.href = target.pathname + location.search + fragment;
  }
  updateReturnLink();
  window.addEventListener('hashchange', updateReturnLink);
  sw.addEventListener('click', updateReturnLink);
});
