// Real admin.html + admin/*.js with an isolated repository and draft API: the
// sidebar groups saveable articles apart from view-only pages and hides
// engineering files. No credentials, no external network, no writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async function checkFileGroups(browser) {
  const HEAD = 'b'.repeat(40);
  const file = (name, dir = '') => ({ type: 'file', name, path: dir + name });
  const rootFiles = ['zz-last.html', 'privacy.html', 'about.html', 'index.html', 'glossary.html', 'admin.html', '404.html',
    'offline.html', 'reset-sw.html', 'sitemap.xml', 'robots.txt', 'package.json', 'README.md', 'sw.js', 'llms.txt'].map(name => file(name));
  rootFiles.push({ type: 'dir', name: 'blog', path: 'blog' });
  const blogFiles = ['zebra-care.html', 'acne-myths.html', 'index.html', 'topics.html', 'charts.html', 'blog-shared.js', 'feed.xml',
    'Upper-Case.html', 'bad_slug.html'].map(name => file(name, 'blog/'));
  let drafts = [{ file: 'blog/mid-draft.html', head: HEAD, legacy: false }], failRepository = false, failDrafts = false;
  const writes = [];
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block' });
  try {
    const page = await context.newPage();
    await page.addInitScript(() => {
      sessionStorage.setItem('cd_gh_pat', 'fixture-only-not-a-real-token');
      sessionStorage.setItem('cd_gh_pat_exp', String(Date.now() + 600000));
    });
    await page.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin === 'https://api.github.com') {
        if (request.method() !== 'GET') { writes.push(request.url()); return route.abort(); }
        if (/\/contents\/?$/.test(url.pathname) || /\/contents\/blog\/?$/.test(url.pathname)) {
          if (failRepository) return route.fulfill({ status: 503, json: { message: 'Isolated repository-list failure' } });
          return route.fulfill({ status: 200, json: /\/blog\/?$/.test(url.pathname) ? blogFiles : rootFiles });
        }
        return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      }
      if (url.origin !== 'https://file-groups.test') return route.abort();
      if (url.pathname === '/api/admin/login') return route.fulfill({ status: 200, json: { ok: true, login: 'expertise88864' } });
      if (url.pathname === '/api/admin/article-draft') {
        if (request.method() !== 'GET') { writes.push(request.url()); return route.abort(); }
        if (url.searchParams.get('mode') === 'list') {
          if (failDrafts) return route.fulfill({ status: 503, json: { ok: false, error: 'draft_list_unavailable' } });
          return route.fulfill({ status: 200, json: { drafts, nextOffset: null, unsupportedRefs: 0 } });
        }
        return route.fulfill({ status: 404, json: { ok: false, error: 'draft_unavailable' } });
      }
      if (request.method() !== 'GET') return route.abort();
      const root = process.cwd(), target = path.resolve(root, '.' + url.pathname);
      if (!target.startsWith(root + path.sep) || !fs.existsSync(target) || !fs.statSync(target).isFile()) return route.fulfill({ status: 404, body: '' });
      const contentType = target.endsWith('.js') ? 'application/javascript' : target.endsWith('.css') ? 'text/css' : target.endsWith('.html') ? 'text/html' : 'application/octet-stream';
      return route.fulfill({ status: 200, contentType, body: fs.readFileSync(target) });
    });
    const snapshot = () => page.evaluate(() => Array.from(document.getElementById('fileList').children).map(node => node.classList.contains('file-group-title')
      ? { heading: node.textContent, role: node.getAttribute('role'), level: node.getAttribute('aria-level') }
      : { path: node.dataset.path, badge: node.querySelectorAll('[data-cd-readonly-label]').length,
          badgeText: (node.querySelector('[data-cd-readonly-label]') || {}).textContent || null,
          title: node.getAttribute('title'), draft: node.querySelectorAll('[data-cd-draft-label]').length }));

    await page.goto('https://file-groups.test/admin.html');
    // The load-time refresh starts before the grouping wrapper exists; wait for
    // the cloud-draft row and the final count rather than the first grouping.
    await page.waitForFunction(() => document.getElementById('status').textContent.startsWith('文章 3 篇') &&
      !!document.querySelector('#fileList [data-cd-draft-label]'));
    const expectedArticles = ['blog/acne-myths.html', 'blog/mid-draft.html', 'blog/zebra-care.html'];
    // blog/index|topics|charts, Upper-Case and bad_slug fail the shared article test.
    const expectedPages = ['index.html', 'about.html', 'privacy.html', 'blog/Upper-Case.html', 'blog/bad_slug.html', 'blog/charts.html',
      'blog/index.html', 'blog/topics.html', 'glossary.html', 'zz-last.html'];
    const expectedGrouped = [
      { heading: '文章（3）', role: 'heading', level: '3' },
      ...expectedArticles.map(p => ({ path: p, badge: 0, badgeText: null, title: null, draft: p === 'blog/mid-draft.html' ? 1 : 0 })),
      { heading: '頁面（10）', role: 'heading', level: '3' },
      ...expectedPages.map(p => ({ path: p, badge: 1, badgeText: '唯讀', title: '頁面僅供檢視；修改請走專案候選發布流程', draft: 0 })),
    ];
    // Pinned pages keep index, about, privacy first; the rest follow by path.
    assert.deepEqual(await snapshot(), expectedGrouped);
    const sorted = [...expectedPages.slice(3)].sort();
    assert.deepEqual(expectedPages.slice(3), sorted, 'fixture expectation is path-sorted');
    for (const hidden of ['admin.html', '404.html', 'offline.html', 'reset-sw.html', 'sitemap.xml', 'robots.txt', 'package.json', 'README.md',
      'sw.js', 'llms.txt', 'blog/blog-shared.js', 'blog/feed.xml']) {
      assert.equal(await page.locator('.file-item[data-path="' + hidden + '"]').count(), 0, hidden + ' is hidden');
    }
    assert.equal(await page.locator('#status').textContent(), '文章 3 篇、頁面 10 個 — 點選文章開始編輯');
    assert.equal(await page.locator('#statusbar').getAttribute('class'), 'statusbar ok');

    // Retained rows: a failed repository refresh keeps the DOM, then a second
    // pass must change nothing, keep node identity, listeners and .active.
    await page.evaluate(() => {
      window.__loaded = []; loadFile = async p => { window.__loaded.push(p); };
      window.__identity = new Map(Array.from(document.querySelectorAll('#fileList .file-item')).map(n => [n.dataset.path, n]));
      document.querySelector('.file-item[data-path="blog/acne-myths.html"]').classList.add('active');
    });
    failRepository = true;
    for (let i = 0; i < 2; i++) {
      await page.evaluate(() => refreshFileList());
      assert.deepEqual(await snapshot(), expectedGrouped, 'repeated refresh is idempotent');
    }
    assert.equal(await page.evaluate(() => Array.from(document.querySelectorAll('#fileList .file-item'))
      .every(n => window.__identity.get(n.dataset.path) === n)), true, 'rows are moved, never cloned');
    assert.equal(await page.locator('.file-item.active').getAttribute('data-path'), 'blog/acne-myths.html', 'active state survives');
    assert.equal(await page.locator('#status').textContent(), '讀取失敗，請稍後再試', 'an error message is not replaced');
    assert.equal(await page.locator('#statusbar').getAttribute('class'), 'statusbar err');

    // Draft rows appended after the groups were built join the article group.
    drafts = [{ file: 'blog/mid-draft.html', head: HEAD, legacy: false }, { file: 'blog/zz-second-draft.html', head: HEAD, legacy: true }];
    await page.evaluate(() => refreshFileList());
    const withSecond = await snapshot();
    assert.equal(withSecond[0].heading, '文章（4）');
    assert.deepEqual(withSecond.slice(1, 5).map(row => row.path), [...expectedArticles, 'blog/zz-second-draft.html']);
    assert.equal(withSecond[4].draft, 1);
    assert.equal(withSecond[5].heading, '頁面（10）');
    assert.equal((await page.locator('.file-group-title').allTextContents()).length, 2, 'headings are never duplicated');
    assert.equal(await page.locator('[data-cd-readonly-label]').count(), 10, 'badges are never duplicated');
    await page.evaluate(() => refreshFileList());
    assert.deepEqual(await snapshot(), withSecond);

    // The row listeners, with and without the mobile delegated handler.
    await page.locator('.file-item[data-path="blog/zebra-care.html"]').click();
    await page.locator('.file-item[data-path="privacy.html"]').click();
    assert.deepEqual(await page.evaluate(() => window.__loaded), ['blog/zebra-care.html', 'privacy.html']);
    await page.setViewportSize({ width: 600, height: 900 });
    await page.evaluate(() => document.getElementById('sidebar').classList.remove('mobile-hidden'));
    await page.locator('.file-item[data-path="blog/acne-myths.html"]').click();
    assert.equal(await page.evaluate(() => document.getElementById('sidebar').classList.contains('mobile-hidden')), true, 'delegated mobile handler still closes the sidebar');
    assert.equal((await page.evaluate(() => window.__loaded)).at(-1), 'blog/acne-myths.html');
    await page.setViewportSize({ width: 1440, height: 1000 });

    // A cloud-draft failure message is not overwritten by the plain count.
    failRepository = false; failDrafts = true;
    await page.evaluate(() => refreshFileList());
    assert.match(await page.locator('#status').textContent(), /^雲端草稿清單讀取未完成/);
    assert.equal(await page.locator('#statusbar').getAttribute('class'), 'statusbar err');
    assert.equal((await snapshot())[0].heading.startsWith('文章（'), true);

    // Fresh success restores the grouped count message.
    failDrafts = false; drafts = [];
    await page.evaluate(() => refreshFileList());
    assert.equal(await page.locator('#status').textContent(), '文章 2 篇、頁面 10 個 — 點選文章開始編輯');
    assert.deepEqual(writes, []);
    console.log('CMS file list: articles and view-only pages grouped, engineering files hidden; idempotent across refreshes and draft rows; listeners, active state and status preserved');
  } finally { await context.close(); }
};

if (require.main === module) (async () => {
  const browser = await require('playwright').chromium.launch();
  try { await module.exports(browser); } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
