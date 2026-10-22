// Board-exam chapter outline (本章目錄) in a real browser: English-only labels
// with the full heading in the tooltip / accessible name, compact typography,
// and the scrollspy (aria-current + highlight, sidebar-only auto-scroll).
// Serves the generated exam/** pages from disk on a fixture origin with the
// production Content-Security-Policy; nothing leaves the machine.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ORIGIN = 'https://exam-toc.test';
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.webmanifest': 'application/manifest+json',
};
const CJK = '\\u3400-\\u9fff\\uf900-\\ufaff';

function decode(text) {
  return text.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
}

// Independent of the generator: what an entry should read, from the page's own <h2>.
function expectedLabel(headingHtml) {
  const full = decode(headingHtml.replace(/<[^>]+>/g, '')).replace(/\s+/g, ' ').trim();
  let label = full.replace(new RegExp('（[^（）]*[' + CJK + '][^（）]*）', 'g'), '');
  label = label.replace(/\s+/g, ' ').replace(/\s+([：；，、])/g, '$1').trim().replace(/[\s：；，、:;,]+$/, '');
  if (!/[A-Za-z]/.test(label.replace(/^\d+\.\s*/, ''))) label = full;
  return { full, label };
}

module.exports = async function checkExamToc(browser) {
  const root = process.cwd();
  const vercel = JSON.parse(fs.readFileSync('vercel.json', 'utf8'));
  const csp = vercel.headers.find(entry => entry.source === '/(.*)').headers.find(header => header.key === 'Content-Security-Policy').value;

  // ---- what the generator emitted, for every chapter page that has an outline
  let checked = 0, trimmed = 0, kept = 0;
  for (const name of fs.readdirSync('exam').filter(n => /^fitz-\d+\.html$/.test(n))) {
    const html = fs.readFileSync(path.join('exam', name), 'utf8');
    const heads = new Map([...html.matchAll(/<section class="ex-note" id="([a-z0-9-]+)"[^>]*>\s*<h2>(.*?)<\/h2>/gs)].map(m => [m[1], m[2]]));
    if (!heads.size) continue;
    for (const side of [true, false]) {
      const block = html.match(new RegExp('<details class="ex-toc ex-toc-' + (side ? 'side' : 'mobile') + '"[^>]*>.*?</details>', 's'));
      assert.ok(block, name + ': outline present');
      const entries = [...block[0].matchAll(/<li><a href="#([a-z0-9-]+)"([^>]*)>(.*?)<\/a><\/li>/g)];
      assert.equal(entries.length, heads.size, name + ': one entry per note section');
      for (const [, id, attrs, inner] of entries) {
        const want = expectedLabel(heads.get(id));
        assert.equal(decode(inner.replace(/<[^>]+>/g, '')), want.label, name + '#' + id + ': label');
        if (want.label !== want.full) {
          assert.ok(attrs.includes('title="' + heads.get(id).replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim() + '"'), name + '#' + id + ': full heading in title');
          assert.ok(attrs.includes('aria-label="'), name + '#' + id + ': full heading in accessible name');
          if (side) trimmed++;
        } else {
          assert.ok(!attrs.includes('title='), name + '#' + id + ': unchanged entries carry no redundant tooltip');
          if (side) kept++;
        }
        assert.ok(!new RegExp('（[^（）]*[' + CJK + ']').test(inner) || want.label === want.full, name + '#' + id + ': no Chinese parenthetical left');
      }
      if (side) checked++;
    }
  }
  assert.ok(checked >= 100, 'outline checked on every chapter page with notes');
  assert.ok(trimmed > 1000 && kept >= 1, 'both trimmed and untouched entries exist');
  // The in-page headings stay English（中文）.
  const ch45 = fs.readFileSync('exam/fitz-45.html', 'utf8');
  assert.match(ch45, /<h2>9\. Drug-Induced Lichenoid Eruptions（苔蘚樣藥疹）<\/h2>/);
  assert.match(ch45, /<a href="#lichenoid" title="9\. Drug-Induced Lichenoid Eruptions（苔蘚樣藥疹）" aria-label="9\. Drug-Induced Lichenoid Eruptions（苔蘚樣藥疹）">9\. Drug-Induced Lichenoid Eruptions<\/a>/);
  assert.match(ch45, /<a href="#concepts-h">本章考點（\d+）<\/a>/);
  assert.match(ch45, /<a href="#qs-h">考題（\d+ 題）<\/a>/);
  // A Chinese-only heading keeps its full text (no English part to fall back to).
  const ch11 = fs.readFileSync('exam/fitz-11.html', 'utf8');
  assert.match(ch11, /<a href="#cell-quick-ref">14\. 皮膚免疫細胞位置速記<\/a>/);
  // An abbreviation in a parenthetical stays; only the Chinese gloss goes.
  assert.match(ch11, /<a href="#nk-cells"[^>]*>7\. Natural Killer（NK）Cells<\/a>/);
  // Organism names keep their italics.
  assert.match(fs.readFileSync('exam/fitz-156.html', 'utf8'), /<a href="#vibrio"[^>]*>11\. <em>Vibrio vulnificus<\/em> Infections<\/a>/);

  // ---- fixture origin
  const violations = [];
  const errors = [];
  async function newContext(options) {
    const context = await browser.newContext({ serviceWorkers: 'block', ...options });
    await context.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.origin !== ORIGIN) {
        if (url.hostname === 'fonts.googleapis.com') return route.fulfill({ status: 200, contentType: 'text/css', body: '' });
        return route.abort();
      }
      if (url.pathname.startsWith('/_vercel/')) return route.fulfill({ contentType: 'text/javascript', body: '' });
      let rel = decodeURIComponent(url.pathname).replace(/^\/+/, '').replace(/\/+$/, '');
      if (rel === 'exam') rel = 'exam/index';
      const file = [rel, rel + '.html'].map(c => path.resolve(root, c)).find(c => c.startsWith(root + path.sep) && fs.existsSync(c) && fs.statSync(c).isFile());
      if (!file || /\.(py|cjs|mjs|md)$/.test(file) || /node_modules|\.git/.test(rel)) return route.fulfill({ status: 404, body: 'not found' });
      return route.fulfill({ status: 200, contentType: TYPES[path.extname(file)] || 'application/octet-stream',
        body: fs.readFileSync(file), headers: { 'Content-Security-Policy': csp } });
    });
    return context;
  }
  async function open(context, url) {
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
  // Put the top of #id at `frac` of the window height.
  const placeAt = (page, id, frac) => page.evaluate(([target, f]) => {
    const node = document.getElementById(target);
    window.scrollTo(0, node.getBoundingClientRect().top + window.pageYOffset - f * window.innerHeight);
  }, [id, frac]);
  // Which entries of the visible outline are marked, as hrefs.
  const marked = (page, selector) => page.locator(selector + ' a[aria-current="location"]').evaluateAll(list => list.map(a => a.getAttribute('href')));
  async function expectMarked(page, selector, href) {
    await page.waitForFunction(([sel, h]) => {
      const list = [...document.querySelectorAll(sel + ' a[aria-current="location"]')];
      return list.length === 1 && list[0].getAttribute('href') === h;
    }, [selector, href], { timeout: 4000 }).catch(async () => {
      assert.deepEqual(await marked(page, selector), [href], 'marked entry');
    });
    assert.deepEqual(await marked(page, selector), [href]);
  }

  const SIDE = '.ex-toc-side';
  const results = [];
  const desktop = await newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' });
  try {
    // ============================================================ desktop
    {
      const page = await open(desktop, '/exam/fitz-45');
      assert.equal(await page.locator(SIDE).isVisible(), true, 'sidebar outline visible on desktop');
      assert.equal(await page.locator('.ex-toc-mobile').isVisible(), false, 'mobile outline hidden on desktop');
      // English-only labels, Chinese only in the tooltip.
      const link = page.locator(SIDE + ' a[href="#lichenoid"]');
      assert.equal(await link.innerText(), '9. Drug-Induced Lichenoid Eruptions');
      assert.equal(await link.getAttribute('title'), '9. Drug-Induced Lichenoid Eruptions（苔蘚樣藥疹）');
      assert.equal(await link.getAttribute('aria-label'), '9. Drug-Induced Lichenoid Eruptions（苔蘚樣藥疹）');
      const texts = await page.locator(SIDE + ' li:not(.ex-toc-cx):not(.ex-toc-qs) a').allInnerTexts();
      assert.ok(texts.length >= 10 && texts.every(t => !new RegExp('[' + CJK + ']').test(t)), 'no Chinese in chapter 45 outline labels');
      // Compact type: 13px / 1.45, and most entries on one or two lines.
      const type = await page.locator(SIDE + ' a').first().evaluate(a => { const s = getComputedStyle(a); return [s.fontSize, parseFloat(s.lineHeight) / parseFloat(s.fontSize)]; });
      assert.equal(type[0], '13px');
      assert.ok(Math.abs(type[1] - 1.45) < 0.01, 'line-height 1.45');
      const lines = await page.locator(SIDE + ' li:not(.ex-toc-cx):not(.ex-toc-qs) a').evaluateAll(list =>
        list.map(a => Math.round(a.getBoundingClientRect().height / parseFloat(getComputedStyle(a).lineHeight))));
      assert.ok(lines.every(n => n <= 3) && lines.filter(n => n <= 2).length >= lines.length * 0.8, 'entries wrap to at most a few lines: ' + lines.join(','));
      assert.equal(await page.locator(SIDE + ' a[aria-current]').count(), 0, 'nothing marked above the notes');

      // Scrollspy: a section whose top passed 30% of the window is current.
      await placeAt(page, 'lichenoid', 0.2);
      await expectMarked(page, SIDE, '#lichenoid');
      assert.deepEqual(await marked(page, '.ex-toc-mobile'), ['#lichenoid'], 'the hidden mobile outline follows too');
      const bold = await link.evaluate(a => [getComputedStyle(a).fontWeight, getComputedStyle(a).backgroundColor]);
      assert.equal(bold[0], '600');
      assert.notEqual(bold[1], 'rgba(0, 0, 0, 0)', 'highlight background');
      // Before the line: still the previous section.
      await placeAt(page, 'lichenoid', 0.45);
      await expectMarked(page, SIDE, '#pigmentation');
      await placeAt(page, 'lichenoid', 0.29);
      await expectMarked(page, SIDE, '#lichenoid');
      // 本章考點 and 考題 anchors.
      await placeAt(page, 'concepts-h', 0.1);
      await expectMarked(page, SIDE, '#concepts-h');
      await placeAt(page, 'qs-h', 0.1);
      await expectMarked(page, SIDE, '#qs-h');
      // Back to the top: nothing is marked.
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForFunction(() => !document.querySelector('.ex-toc-side a[aria-current]'), null, { timeout: 4000 });
      // Following an outline link marks its section.
      await page.locator(SIDE + ' a[href="#onset-table"]').click();
      await expectMarked(page, SIDE, '#onset-table');

      // Dark mode: the highlight has its own colours.
      const light = await page.locator(SIDE + ' a[aria-current]').evaluate(a => [getComputedStyle(a).backgroundColor, getComputedStyle(a).color]);
      await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
      const dark = await page.locator(SIDE + ' a[aria-current]').evaluate(a => [getComputedStyle(a).backgroundColor, getComputedStyle(a).color]);
      assert.notDeepEqual(dark, light, 'dark highlight differs from light');
      assert.equal(dark[0], 'rgba(164, 181, 168, 0.2)');
      assert.equal(dark[1], 'rgb(238, 243, 239)');
      await page.evaluate(() => document.documentElement.removeAttribute('data-theme'));
      await page.close();
      results.push('desktop labels, typography, scrollspy, dark mode');
    }

    // ============================================================ short window: the sidebar follows, the page does not
    for (const reduced of [true, false]) {
      const context = reduced ? desktop : await newContext({ viewport: { width: 1280, height: 520 }, reducedMotion: 'no-preference' });
      const page = await open(context, '/exam/fitz-45');
      if (reduced) await page.setViewportSize({ width: 1280, height: 520 });
      const box = page.locator(SIDE);
      const overflow = await box.evaluate(node => node.scrollHeight - node.clientHeight);
      assert.ok(overflow > 40, 'outline taller than the window overflows its own box (' + overflow + 'px)');
      assert.equal(await box.evaluate(node => node.scrollTop), 0);
      await placeAt(page, 'concepts-h', 0.1);
      await expectMarked(page, SIDE, '#concepts-h');
      const pageY = await page.evaluate(() => window.pageYOffset);
      await page.waitForFunction(() => {
        const side = document.querySelector('.ex-toc-side');
        const a = side.querySelector('a[aria-current]');
        const b = side.getBoundingClientRect(), r = a.getBoundingClientRect();
        return side.scrollTop > 0 && r.top >= b.top - 1 && r.bottom <= b.bottom + 1;
      }, null, { timeout: 5000 });
      assert.equal(await page.evaluate(() => window.pageYOffset), pageY, 'page scroll position not hijacked by the outline');
      // Scroll back up: the sidebar brings the earlier entry back into view.
      await placeAt(page, 'overview', 0.1);
      await expectMarked(page, SIDE, '#overview');
      await page.waitForFunction(() => {
        const side = document.querySelector('.ex-toc-side');
        const a = side.querySelector('a[aria-current]');
        const b = side.getBoundingClientRect(), r = a.getBoundingClientRect();
        return r.top >= b.top - 1 && r.bottom <= b.bottom + 1;
      }, null, { timeout: 5000 });
      await page.close();
      if (!reduced) await context.close();
      results.push('sidebar follows (' + (reduced ? 'reduced motion' : 'smooth') + ')');
    }

    // ============================================================ fallback entries
    {
      const page = await open(desktop, '/exam/fitz-11');
      const quick = page.locator(SIDE + ' a[href="#cell-quick-ref"]');
      assert.equal(await quick.innerText(), '14. 皮膚免疫細胞位置速記', 'Chinese-only heading keeps its full text');
      assert.equal(await quick.getAttribute('title'), null);
      const nk = page.locator(SIDE + ' a[href="#nk-cells"]');
      assert.equal(await nk.innerText(), '7. Natural Killer（NK）Cells');
      assert.equal(await nk.getAttribute('title'), '7. Natural Killer（NK）Cells（自然殺手細胞）');
      await placeAt(page, 'cell-quick-ref', 0.1);
      await expectMarked(page, SIDE, '#cell-quick-ref');
      await page.close();
      results.push('fallback and abbreviation entries');
    }
  } finally {
    await desktop.close();
  }

  // ================================================================ phone
  const phone = await newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce' });
  try {
    const page = await open(phone, '/exam/fitz-45');
    assert.equal(await page.locator(SIDE).isVisible(), false, 'no sidebar on a phone');
    const toc = page.locator('.ex-toc-mobile');
    assert.equal(await toc.isVisible(), true);
    assert.equal(await toc.evaluate(node => node.open), false, 'collapsed until opened');
    await toc.locator('summary').click();
    assert.equal(await toc.evaluate(node => node.open), true);
    const link = toc.locator('a[href="#lichenoid"]');
    assert.equal(await link.innerText(), '9. Drug-Induced Lichenoid Eruptions');
    assert.equal(await link.getAttribute('title'), '9. Drug-Induced Lichenoid Eruptions（苔蘚樣藥疹）');
    const heights = await toc.locator('a').evaluateAll(list => list.map(a => a.getBoundingClientRect().height));
    assert.ok(heights.every(h => h >= 32), 'tap targets are at least 32px tall: min ' + Math.min(...heights));
    await placeAt(page, 'lichenoid', 0.2);
    await expectMarked(page, '.ex-toc-mobile', '#lichenoid');
    const y = await page.evaluate(() => window.pageYOffset);
    await page.waitForTimeout(300);
    assert.equal(await page.evaluate(() => window.pageYOffset), y, 'phone page scroll untouched');
    await page.close();
    results.push('phone outline');
  } finally {
    await phone.close();
  }

  assert.deepEqual(violations, [], 'no CSP violations');
  assert.deepEqual(errors, [], 'no console or page errors');
  console.log('Exam outline browser checks passed: ' + results.join('; '));
};

if (require.main === module) (async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch();
  try { await module.exports(browser); } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
