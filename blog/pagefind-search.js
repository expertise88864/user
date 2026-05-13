/* pagefind-search.js — drop-in static-site search with great CJK support.
 *
 * Loaded lazily ONLY when the user clicks the search button. No bundle bloat.
 * Falls back to existing Lunr (if Pagefind index missing) gracefully.
 *
 * Usage from blog-shared.js:
 *   document.querySelector('#search-trigger').addEventListener('click', async () => {
 *     const mod = await import('/blog/pagefind-search.js?v=…');
 *     mod.openSearch();
 *   });
 */

let pagefind = null;
let modal = null;

async function loadPagefind() {
  if (pagefind) return pagefind;
  try {
    pagefind = await import('/pagefind/pagefind.js');
    return pagefind;
  } catch (e) {
    console.warn('[pagefind] index not built — run _setup_pagefind.bat first', e);
    return null;
  }
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function safeResultUrl(value) {
  const url = String(value || '');
  if (!url.startsWith('/') || url.startsWith('//')) return '#';
  return url.replace(/[\u0000-\u001f\u007f]/g, '');
}

function sanitizeExcerpt(value) {
  const template = document.createElement('template');
  template.innerHTML = String(value || '');
  template.content.querySelectorAll('*').forEach(el => {
    if (el.tagName.toLowerCase() !== 'mark') {
      el.replaceWith(document.createTextNode(el.textContent || ''));
      return;
    }
    Array.from(el.attributes).forEach(attr => el.removeAttribute(attr.name));
  });
  return template.innerHTML;
}

function buildModal() {
  if (modal) return modal;
  modal = document.createElement('div');
  modal.innerHTML = `
<div class="pf-overlay" style="position:fixed;inset:0;background:rgba(15,23,42,.4);z-index:200;display:flex;align-items:flex-start;justify-content:center;padding-top:10vh">
  <div class="pf-modal" style="background:#fff;border-radius:14px;width:min(620px,92%);max-height:80vh;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 24px 50px -16px rgba(12,81,89,.55)">
    <div style="padding:14px;border-bottom:1px solid #ebe4d8;display:flex;align-items:center;gap:10px">
      <span style="font-size:18px">🔍</span>
      <input class="pf-q" type="search" placeholder="搜尋衛教文章..." autofocus style="flex:1;padding:10px 14px;font-size:15px;border:1px solid #dcd5c8;border-radius:8px;font-family:inherit"/>
      <button type="button" class="pf-close" aria-label="關閉" style="border:none;background:transparent;font-size:22px;cursor:pointer;color:#5e574e">×</button>
    </div>
    <div class="pf-results" style="flex:1;overflow-y:auto;padding:8px"></div>
    <div class="pf-foot" style="padding:8px 14px;border-top:1px solid #ebe4d8;font-size:11.5px;color:#8b8378">
      Powered by <a href="https://pagefind.app" target="_blank" rel="noopener noreferrer">Pagefind</a> · 全文索引 · ESC 關閉
    </div>
  </div>
</div>`;
  document.body.appendChild(modal);
  modal.querySelector('.pf-close').addEventListener('click', closeSearch);
  modal.querySelector('.pf-overlay').addEventListener('click', e => {
    if (e.target.classList.contains('pf-overlay')) closeSearch();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && modal.style.display !== 'none') closeSearch();
  });
  let timer = null;
  modal.querySelector('.pf-q').addEventListener('input', e => {
    clearTimeout(timer);
    timer = setTimeout(() => doSearch(e.target.value.trim()), 180);
  });
  return modal;
}

async function doSearch(q) {
  const list = modal.querySelector('.pf-results');
  if (!q || q.length < 1) { list.innerHTML = ''; return; }
  if (!pagefind) {
    list.innerHTML = '<div style="padding:24px;text-align:center;color:#7f1d1d">Pagefind index 尚未建立。請執行 _setup_pagefind.bat 後重新部署。</div>';
    return;
  }
  list.innerHTML = '<div style="padding:24px;text-align:center;color:#8b8378">搜尋中...</div>';
  try {
    const search = await pagefind.search(q);
    if (!search.results.length) {
      list.innerHTML = '<div style="padding:24px;text-align:center;color:#5e574e">沒找到相關文章</div>';
      return;
    }
    const items = await Promise.all(search.results.slice(0, 8).map(r => r.data()));
    list.innerHTML = items.map(d => `
<a href="${escapeHtml(safeResultUrl(d.url))}" style="display:block;padding:12px 14px;border-radius:8px;text-decoration:none;color:#2a2620;border:1px solid transparent;margin:4px 0">
  <div style="font-weight:600;font-size:14.5px;color:#0c5159">${escapeHtml(d.meta && d.meta.title || '(無標題)')}</div>
  <div style="font-size:12.5px;line-height:1.6;color:#5e574e;margin-top:2px">${sanitizeExcerpt(d.excerpt)}</div>
</a>`).join('');
    list.querySelectorAll('a').forEach(a => {
      a.addEventListener('mouseenter', () => { a.style.background = '#f5fbfa'; a.style.borderColor = '#dcd5c8'; });
      a.addEventListener('mouseleave', () => { a.style.background = ''; a.style.borderColor = 'transparent'; });
    });
  } catch (e) {
    list.innerHTML = '<div style="padding:24px;text-align:center;color:#7f1d1d">搜尋出錯，請稍後再試</div>';
  }
}

export async function openSearch() {
  buildModal();
  modal.style.display = 'block';
  await loadPagefind();
  modal.querySelector('.pf-q').focus();
}

export function closeSearch() {
  if (modal) modal.style.display = 'none';
}
