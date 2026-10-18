// Group the sidebar file list into saveable articles and view-only pages, and
// hide engineering files. Presentation only: it moves the rows that
// refreshFileList() and the draft bridge already built, so their listeners,
// data-path and .active state are untouched, and it never grants a save path.
// Loaded after draft-editor.js so this wrapper is the outermost refreshFileList
// and runs once the repository rows and the cloud-draft rows are both present.
// draft-editor.js starts one refresh while loading, before this wrapper exists,
// so a childList observer also regroups rows that arrive outside the wrapper.
(function () {
  'use strict';
  const list = document.getElementById('fileList');
  const drafts = window.DNArticleDrafts;
  // Without the shared article test the list is left exactly as built.
  if (!list || !drafts || typeof drafts.isArticle !== 'function' || typeof refreshFileList !== 'function') return;

  const READONLY_TITLE = '頁面僅供檢視；修改請走專案候選發布流程';
  const PIN = ['index.html', 'about.html', 'privacy.html'];
  const HIDDEN_ROOT = new Set(['admin.html', '404.html', 'offline.html', 'reset-sw.html']);
  // Only the plain success message set by refreshFileList(); anything else
  // (errors, draft-status notices) was written after it and must stay.
  const PLAIN_STATUS = /^共 \d+ 個檔案/;
  let ownStatus = null; // our last count message, kept current when rows change later

  const byPath = (a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0);
  function pinRank(path) { const index = PIN.indexOf(path); return index === -1 ? PIN.length : index; }

  function heading(text) {
    const title = document.createElement('div');
    title.className = 'file-group-title';
    title.setAttribute('role', 'heading');
    title.setAttribute('aria-level', '3');
    title.textContent = text;
    return title;
  }

  let running = false, scheduled = false;
  function regroup() {
    running = true;
    try { group(); } finally { running = false; observer.takeRecords(); }
  }
  function group() {
    // Drop what a previous pass added so repeated refreshes stay idempotent.
    list.querySelectorAll('.file-group-title').forEach(node => node.remove());
    list.querySelectorAll('[data-cd-readonly-label]').forEach(node => node.remove());
    const articles = [], pages = [];
    for (const item of Array.from(list.querySelectorAll('.file-item'))) {
      const path = item.dataset.path || '';
      if (item.getAttribute('title') === READONLY_TITLE) item.removeAttribute('title');
      const hidden = !/\.html$/i.test(path) || (HIDDEN_ROOT.has(path));
      if (hidden) { item.remove(); continue; }
      (drafts.isArticle(path) ? articles : pages).push({ path, item });
    }
    articles.sort(byPath);
    pages.sort((a, b) => pinRank(a.path) - pinRank(b.path) || byPath(a, b));
    const ordered = [];
    if (articles.length) ordered.push(heading('文章（' + articles.length + '）'), ...articles.map(entry => entry.item));
    if (pages.length) {
      ordered.push(heading('頁面（' + pages.length + '）'));
      for (const { item } of pages) {
        const badge = document.createElement('span');
        badge.setAttribute('data-cd-readonly-label', '');
        badge.textContent = '唯讀';
        item.appendChild(badge);
        item.setAttribute('title', READONLY_TITLE);
        ordered.push(item);
      }
    }
    // append() moves nodes that are already children, preserving identity.
    list.append(...ordered);
    const status = document.getElementById('status');
    if (status && (PLAIN_STATUS.test(status.textContent) || status.textContent === ownStatus)) {
      ownStatus = '文章 ' + articles.length + ' 篇、頁面 ' + pages.length + ' 個 — 點選文章開始編輯';
      status.textContent = ownStatus;
    }
  }

  // Rows built or appended by any unwrapped caller are regrouped once, after
  // the synchronous work that added them (including the plain status message).
  const observer = new MutationObserver(() => {
    if (running || scheduled) return;
    scheduled = true;
    queueMicrotask(() => { scheduled = false; regroup(); });
  });
  observer.observe(list, { childList: true });

  const originalRefresh = refreshFileList;
  refreshFileList = async function () {
    try { await originalRefresh(); } finally { regroup(); }
  };
  regroup();
})();
