(function () {
var burger = document.getElementById('dn-nav-burger');
var nav = document.querySelector('.dn-nav');
if (burger && nav) {
burger.addEventListener('click', function () {
var open = nav.classList.toggle('open');
burger.setAttribute('aria-expanded', String(open));
});
}
var search = document.getElementById('dn-nav-search');
if (search) search.addEventListener('click', function () {
// Triggers Cmd+K search modal via DN
if (window.DN && DN.openSearch) DN.openSearch();
else { var ev = new KeyboardEvent('keydown', { key: 'k', metaKey: true, ctrlKey: true }); document.dispatchEvent(ev); }
});
var theme = document.getElementById('dn-nav-theme');
if (theme) theme.addEventListener('click', function () {
var cur = document.documentElement.getAttribute('data-theme');
var next = cur === 'dark' ? 'light' : 'dark';
try { localStorage.setItem('dn-theme', next); } catch (e) {}
document.documentElement.setAttribute('data-theme', next);
theme.textContent = next === 'dark' ? '☀' : '🌙';
});
// Initialize theme button label
if (theme) {
var saved = (function(){ try { return localStorage.getItem('dn-theme'); } catch(e) { return null; } })();
var dark = saved === 'dark' || (!saved && window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches);
theme.textContent = dark ? '☀' : '🌙';
}
})();