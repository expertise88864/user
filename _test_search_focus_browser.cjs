// Late search data must not steal keyboard focus from a result link.
// Real page markup and search sources; the full-text index and a stand-in
// Pagefind module are held until the test releases them, so the order
// "focus a result, then the background load settles" is deterministic.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const PAGEFIND_STUB = `
const gate = new Promise(resolve => { window.__releasePagefind = resolve; });
export async function search() {
  await gate;
  return { results: [{ data: async () => ({ url: '/blog/acne-overview', meta: { title: 'Pagefind result' }, excerpt: 'late full-text match' }) }] };
}
window.__pagefindLoaded = true;
`;

module.exports = async function checkSearchFocus(browser) {
  const root = process.cwd();
  const context = await browser.newContext({ serviceWorkers: 'block', viewport: { width: 1440, height: 900 } });
  let releaseIndex;
  const indexGate = new Promise(resolve => { releaseIndex = resolve; });
  try {
    await context.addInitScript(() => { window.requestIdleCallback = () => 1; window.cancelIdleCallback = () => {}; });
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== 'https://search-focus.test' || request.method() !== 'GET') return route.abort();
      if (url.pathname === '/pagefind/pagefind.js') return route.fulfill({ status: 200, contentType: 'text/javascript', body: PAGEFIND_STUB });
      if (url.pathname.startsWith('/pagefind/')) return route.abort();
      if (url.pathname === '/assets/search-index.json') {
        await indexGate;
        return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      }
      let name = decodeURIComponent(url.pathname).slice(1);
      if (!name) name = 'index.html';
      if (!path.extname(name)) name += fs.existsSync(path.join(root, name, 'index.html')) ? '/index.html' : '.html';
      if (name === 'blog/blog-shared.min.js') name = 'blog/blog-shared.js';
      if (name === 'blog/blog-search.min.js') name = 'blog/blog-search.js';
      const file = path.resolve(root, name);
      if (!file.startsWith(root + path.sep) || name.split('/').some(p => p.startsWith('.')) ||
          !fs.existsSync(file) || !fs.statSync(file).isFile()) return route.fulfill({ status: 404, body: '' });
      const contentType = file.endsWith('.js') ? 'text/javascript' : file.endsWith('.html') ? 'text/html' :
        file.endsWith('.css') ? 'text/css' : 'application/octet-stream';
      return route.fulfill({ status: 200, contentType, body: fs.readFileSync(file) });
    });
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('https://search-focus.test/blog', { waitUntil: 'load' });
    await page.evaluate(() => { window.DN.initCmdK(); window.DN.openSearch(); });
    await page.waitForFunction(() => window.__pagefindLoaded && typeof window.DN.searchRender === 'function');
    await page.locator('#dn-cmdk-input').fill('痘痘');
    const first = page.locator('#dn-cmdk-results a[href]').first();
    await first.waitFor({ state: 'visible' });
    await first.focus();
    const focusedHref = () => page.evaluate(() => {
      const a = document.activeElement;
      return a && a.closest && a.closest('#dn-cmdk-results') ? a.getAttribute('href') : null;
    });
    const href = await focusedHref();
    assert.ok(href, 'a result link has focus before the late loads');
    await page.evaluate(() => window.__releasePagefind());
    await page.waitForTimeout(400);
    assert.equal(await focusedHref(), href, 'a late Pagefind result keeps the focused result link');
    assert.equal(await page.locator('#dn-cmdk-results .dn-sp').count(), 0, 'the full-text search is no longer shown as pending');
    releaseIndex();
    await page.waitForTimeout(400);
    assert.equal(await focusedHref(), href, 'a late full-text index keeps the focused result link');
    // Typing again shows the refined results, including the late Pagefind match
    // (its excerpt exists only in the stand-in module, not in the local catalog).
    await page.locator('#dn-cmdk-input').fill('痘痘 ');
    await page.locator('#dn-cmdk-results', { hasText: 'late full-text match' }).waitFor({ state: 'visible', timeout: 5000 });
    assert.deepEqual(errors, []);
    console.log('Search focus checks passed: late Pagefind and full-text loads keep keyboard focus');
  } finally {
    releaseIndex();
    await context.close();
  }
};
