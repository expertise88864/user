// Board-exam 考點 pages in a real browser (split 2026-10-28): the hub's
// cross-page search over exam/concepts-index.json, old /exam/concepts#c-<id>
// links redirected to the concept's part page, and the part page's own
// filter (?ch=) and reveal of #c-<id>. Serves the generated exam/** pages from
// disk on a fixture origin with the production Content-Security-Policy.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ORIGIN = 'https://exam-concepts.test';
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.webmanifest': 'application/manifest+json',
};

module.exports = async function checkExamConcepts(browser) {
  const root = process.cwd();
  const vercel = JSON.parse(fs.readFileSync('vercel.json', 'utf8'));
  const csp = vercel.headers.find(entry => entry.source === '/(.*)').headers.find(header => header.key === 'Content-Security-Policy').value;
  const index = JSON.parse(fs.readFileSync('exam/concepts-index.json', 'utf8'));
  // A concept from a late part, so the old link cannot work by accident.
  const target = index.concepts.find(row => row[6] === 20);
  assert.ok(target, 'index has a Part 20 concept');
  const part20 = fs.readFileSync('exam/concepts-p20.html', 'utf8');
  assert.ok(part20.includes('<li id="c-' + target[0] + '"'), 'the concept is on its part page');
  assert.ok(!fs.readFileSync('exam/concepts.html', 'utf8').includes('<li id="c-'), 'the hub carries no full concept');

  const violations = [];
  const errors = [];
  const requested = [];
  const context = await browser.newContext({ serviceWorkers: 'block', viewport: { width: 1280, height: 900 } });
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin !== ORIGIN) {
      if (url.hostname === 'fonts.googleapis.com') return route.fulfill({ status: 200, contentType: 'text/css', body: '' });
      return route.abort();
    }
    requested.push(url.pathname);
    if (url.pathname.startsWith('/_vercel/')) return route.fulfill({ contentType: 'text/javascript', body: '' });
    let rel = decodeURIComponent(url.pathname).replace(/^\/+/, '').replace(/\/+$/, '');
    if (rel === 'exam') rel = 'exam/index';
    const file = [rel, rel + '.html'].map(c => path.resolve(root, c)).find(c => c.startsWith(root + path.sep) && fs.existsSync(c) && fs.statSync(c).isFile());
    if (!file || /\.(py|cjs|mjs|md)$/.test(file) || /node_modules|\.git/.test(rel)) return route.fulfill({ status: 404, body: 'not found' });
    return route.fulfill({ status: 200, contentType: TYPES[path.extname(file)] || 'application/octet-stream',
      body: fs.readFileSync(file), headers: { 'Content-Security-Policy': csp } });
  });
  async function open(url) {
    const page = await context.newPage();
    page.on('pageerror', error => {
      if (/reading 'update'/.test(error.message) && /blog-shared/.test(String(error.stack))) return;
      errors.push('pageerror: ' + error.message + ' @' + page.url());
    });
    page.on('console', message => {
      const text = message.text();
      if (/Content[- ]Security[- ]Policy|Refused to/i.test(text)) violations.push(text);
      if (message.type() === 'error') {
        const where = message.location().url || '';
        if (!(/Failed to load resource/.test(text) && !where.startsWith(ORIGIN))) errors.push('console: ' + text + ' ' + where);
      }
    });
    await page.goto(ORIGIN + url);
    await page.waitForLoadState('load');
    return page;
  }
  try {
    // ---- hub: no index request until the reader searches
    {
      const page = await open('/exam/concepts');
      await page.waitForSelector('[data-cx-tools]:not([hidden])');
      assert.ok(!requested.some(p => p === '/exam/concepts-index.json'), 'index is loaded lazily');
      assert.ok(await page.locator('#cx-results').isHidden(), 'no result list before a search');
      await page.fill('#cx-q', 'pemphigus');
      await page.waitForSelector('#cx-results:not([hidden]) li');
      const hrefs = await page.locator('#cx-results a').evaluateAll(list => list.map(a => a.getAttribute('href')));
      const expected = index.concepts.filter(r => (r[1] + ' ' + r[2]).toLowerCase().includes('pemphigus'));
      assert.ok(expected.length > 0, 'fixture query matches something');
      assert.equal(hrefs.length, Math.min(expected.length, 50), 'first page of matches');
      assert.deepEqual(hrefs, expected.slice(0, 50).map(r => '/exam/concepts-p' + r[6] + '#c-' + r[0]), 'links go to part pages');
      assert.match(await page.locator('.cx-status').textContent(), new RegExp('找到 ' + expected.length + ' 個考點'));
      assert.match(page.url(), /\?kw=pemphigus$/, 'query mirrored in the address');
      // Chapter filter across parts: every concept involving Ch.52.
      await page.fill('#cx-q', '');
      await page.selectOption('.cx-ch-select', '52');
      await page.waitForFunction(() => /找到/.test(document.querySelector('.cx-status').textContent));
      const n52 = index.concepts.filter(r => r[4].includes(52)).length;
      assert.match(await page.locator('.cx-status').textContent(), new RegExp('找到 ' + n52 + ' 個考點'));
      await page.close();
    }
    // ---- old link: /exam/concepts#c-<id> lands on the part page with the concept open
    {
      const page = await open('/exam/concepts#c-' + target[0]);
      await page.waitForURL(ORIGIN + '/exam/concepts-p20#c-' + target[0]);
      await page.waitForFunction(id => {
        const li = document.getElementById(id);
        return li && !li.hidden && li.querySelector('details').open;
      }, 'c-' + target[0]);
      await page.close();
    }
    // ---- old chapter filter link keeps working on the hub
    {
      const page = await open('/exam/concepts?ch=52');
      await page.waitForSelector('#cx-results:not([hidden]) li');
      assert.equal(await page.locator('.cx-ch-select').inputValue(), '52');
      await page.close();
    }
    // ---- part page: ?ch= filter (the chapter pages link here)
    {
      const page = await open('/exam/concepts-p9?ch=52');
      await page.waitForSelector('[data-cx-tools]:not([hidden])');
      assert.equal(await page.locator('.cx-ch-select').inputValue(), '52');
      const visible = await page.locator('#cx-all > li:not([hidden])').evaluateAll(list => list.map(li => li.getAttribute('data-ch')));
      assert.ok(visible.length > 0, 'chapter 52 concepts shown');
      assert.ok(visible.every(chs => chs.split(' ').includes('52')), 'only concepts involving Ch.52');
      await page.close();
    }
    assert.deepEqual(violations, [], 'no CSP violations');
    assert.deepEqual(errors, [], 'no page errors');
  } finally {
    await context.close();
  }
  console.log('exam concepts browser: hub search, old-link redirect and part-page filter OK');
};
