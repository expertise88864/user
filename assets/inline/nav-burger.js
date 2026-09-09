(function () {
var burger = document.getElementById('dn-nav-burger');
var nav = document.querySelector('.dn-nav');
var closeMenu = function () {};
if (burger && nav) {
var mobile = window.matchMedia('(max-width:899px)');
var header = nav.closest('header');
nav.id = nav.id || 'dn-main-navigation';
burger.setAttribute('aria-controls', nav.id);
function setMenu(open, restoreFocus) {
nav.classList.toggle('open', open);
nav.classList.remove('dn-nav-open');
if (header) header.classList.toggle('dn-nav-expanded', open);
burger.setAttribute('aria-expanded', String(open));
var zh = open ? '關閉選單' : '開啟選單';
var en = open ? 'Close menu' : 'Open menu';
burger.setAttribute('data-zh-aria-label', zh);
burger.setAttribute('data-en-aria-label', en);
burger.setAttribute('aria-label', document.documentElement.lang.indexOf('en') === 0 ? en : zh);
if (restoreFocus) burger.focus();
}
closeMenu = function (restoreFocus) {
if (nav.classList.contains('open')) setMenu(false, restoreFocus);
};
setMenu(false, false);
burger.addEventListener('click', function () {
var open = !nav.classList.contains('open');
setMenu(open, false);
if (open) {
var first = nav.querySelector('a,button,select');
if (first) first.focus();
}
});
nav.addEventListener('click', function (event) {
if (event.target.closest('a')) closeMenu(false);
});
document.addEventListener('keydown', function (event) {
if (!nav.classList.contains('open')) return;
if (event.key === 'Escape') { closeMenu(true); event.preventDefault(); }
else if (event.key.toLowerCase() === 'k' && (event.metaKey || event.ctrlKey)) closeMenu(false);
});
document.addEventListener('click', function (event) {
if (!nav.contains(event.target) && !burger.contains(event.target)) closeMenu(false);
});
document.addEventListener('focusin', function (event) {
if (!nav.contains(event.target) && !burger.contains(event.target)) closeMenu(false);
});
function onBreakpointChange() {
setMenu(false, mobile.matches && nav.contains(document.activeElement));
}
if (typeof mobile.addEventListener === 'function') mobile.addEventListener('change', onBreakpointChange);
else if (typeof mobile.addListener === 'function') mobile.addListener(onBreakpointChange);
}
var search = document.getElementById('dn-nav-search');
if (search) search.addEventListener('click', function () {
closeMenu(false);
// Triggers Cmd+K search modal via DN
if (window.DN && window.DN.openSearch) window.DN.openSearch();
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
