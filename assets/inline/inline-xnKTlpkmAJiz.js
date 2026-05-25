
try {
  localStorage.setItem('dn_lang', 'en');
  document.cookie = 'dn_lang=en;path=/;max-age=31536000;samesite=lax';
} catch (e) {}
document.addEventListener('DOMContentLoaded', function () {
  var sw = document.getElementById('dn-en-banner-zh');
  if (sw) sw.href = location.pathname.replace(/^\/en\//, '/').replace(/^\/en$/, '/');
});
