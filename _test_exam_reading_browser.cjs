// Board-exam reading progress in a real browser: the hub's 「繼續閱讀」 card, the
// 閱讀 column / summary / sort of the progress table, and a chapter page's
// reading coverage (dwell time per note section, rounds, toast, reset).
// Serves the generated exam/** pages and assets from disk on a fixture origin
// with the production Content-Security-Policy; nothing leaves the machine and
// time is driven with page.clock.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ORIGIN = 'https://exam-reading.test';
const T0 = new Date('2026-10-20T10:00:00+08:00');
const MIN = 60000, HOUR = 3600000, DAY = 86400000;

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.webmanifest': 'application/manifest+json',
};

module.exports = async function checkExamReading(browser) {
  const root = process.cwd();
  const vercel = JSON.parse(fs.readFileSync('vercel.json', 'utf8'));
  const csp = vercel.headers.find(entry => entry.source === '/(.*)').headers.find(header => header.key === 'Content-Security-Policy').value;

  // ---- what the generator emitted
  const hubSource = fs.readFileSync('exam/index.html', 'utf8');
  // linked: the chapter name is a link (chapters with questions or notes; a
  // chapter with notes but no question is linked and still class="ex-none").
  const rowInfo = [...hubSource.matchAll(/<tr data-ch="(\d+)" data-order="(\d+)" data-qids="([^"]*)"( data-notes="1")?( class="ex-none")?><th scope="row">(<a )?/g)]
    .map(m => ({ ch: Number(m[1]), order: Number(m[2]), notes: !!m[4], linked: !!m[6] }));
  const withNotes = rowInfo.filter(row => row.notes && row.linked).map(row => row.ch);
  const withoutNotes = rowInfo.filter(row => !row.notes && row.linked).map(row => row.ch);
  // Every Fitzpatrick chapter now has notes; the checks for a chapter without
  // notes run only while such a chapter exists (PLAIN_CH undefined otherwise).
  assert.ok(withNotes.length >= 7, 'fixtures need chapters with notes');
  assert.equal(rowInfo.filter(row => row.notes).length, withNotes.length, 'every chapter with notes is linked');
  const NOTE_CH = 52, PLAIN_CH = withoutNotes[0];
  assert.ok(withNotes.includes(NOTE_CH));
  const noteSource = fs.readFileSync('exam/fitz-' + NOTE_CH + '.html', 'utf8');
  const sections = [...noteSource.matchAll(/<section class="ex-note" id="([a-z0-9-]+)" data-w="(\d+)">/g)].map(m => ({ id: m[1], w: Number(m[2]) }));
  assert.ok(sections.length >= 6, 'chapter ' + NOTE_CH + ' should have several note sections');
  const totalW = sections.reduce((sum, s) => sum + s.w, 0);
  const need = s => Math.min(30000, Math.max(5000, 50 * s.w));
  const pctOf = ids => Math.round(100 * sections.filter(s => ids.includes(s.id)).reduce((sum, s) => sum + s.w, 0) / totalW);
  if (PLAIN_CH !== undefined) {
    assert.ok(!fs.readFileSync('exam/fitz-' + PLAIN_CH + '.html', 'utf8').includes('data-w='), 'no weights without notes');
    assert.ok(!fs.readFileSync('exam/fitz-' + PLAIN_CH + '.html', 'utf8').includes('id="ex-reading"'), 'no status line without notes');
  }
  assert.match(hubSource, /<section class="ex-continue" aria-labelledby="ex-continue-h" hidden><\/section>/);
  // the card sits between the disease search box and the progress table's heading
  const cardAt = hubSource.indexOf('<section class="ex-continue"');
  assert.ok(hubSource.indexOf('data-exam-search') < cardAt && cardAt < hubSource.indexOf('依章節瀏覽與讀書進度'), 'card sits after the search box and before 依章節瀏覽');
  assert.ok(cardAt > hubSource.indexOf('id="ex-search-results"'), 'after the whole search box');
  assert.match(hubSource, /<option value="reading">閱讀進度低優先<\/option>/);
  // no static 「有重點」 badge anywhere on the hub (every chapter has notes; the 閱讀 column shows progress)
  assert.ok(!hubSource.includes('有重點') && !hubSource.includes('class="ex-badge"'), 'hub has no 有重點 badge');
  // 出題頻率 rows carry data-ch for exam.js and no badge markup
  const rankChs = [...hubSource.matchAll(/<tr data-ch="(\d+)"><td><a href="\/exam\/fitz-\1">Ch\.\1 [^<]*<\/a><\/td>/g)].map(m => Number(m[1]));
  assert.ok(rankChs.length >= 25, 'ranked rows carry data-ch');
  const rankNotes = withNotes.filter(ch => rankChs.includes(ch));
  assert.ok(rankNotes.length >= 4, 'ranked chapters with notes for the ✓N badge');

  // ---- fixture origin
  const violations = [];
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  const allowedSeed = '/__seed';
  async function routeAll(target) {
    await target.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.origin !== ORIGIN) {
        // Third-party fonts and the like are not part of this test; never reach the network.
        if (url.hostname === 'fonts.googleapis.com') return route.fulfill({ status: 200, contentType: 'text/css', body: '' });
        return route.abort();
      }
      if (url.pathname === allowedSeed) return route.fulfill({ contentType: 'text/html', body: '<!doctype html><title>seed</title>' });
      if (url.pathname.startsWith('/_vercel/')) return route.fulfill({ contentType: 'text/javascript', body: '' });
      let rel = decodeURIComponent(url.pathname).replace(/^\/+/, '').replace(/\/+$/, '');
      if (rel === 'exam') rel = 'exam/index';
      const candidates = [rel, rel + '.html'];
      const file = candidates.map(c => path.resolve(root, c)).find(c => c.startsWith(root + path.sep) && fs.existsSync(c) && fs.statSync(c).isFile());
      if (!file || /\.(py|cjs|mjs|md)$/.test(file) || /node_modules|\.git/.test(rel)) return route.fulfill({ status: 404, body: 'not found' });
      return route.fulfill({ status: 200, contentType: TYPES[path.extname(file)] || 'application/octet-stream',
        body: fs.readFileSync(file), headers: { 'Content-Security-Policy': csp } });
    });
  }
  await routeAll(context);

  const errors = [];
  async function open(url, { seedData, init } = {}) {
    const page = await context.newPage();
    page.on('pageerror', error => {
      // The shared site script updates its service worker when a tab becomes visible
      // again; with service workers blocked for this fixture there is none to update.
      if (/reading 'update'/.test(error.message) && /blog-shared/.test(String(error.stack))) return;
      errors.push('pageerror: ' + error.message + ' @' + page.url());
    });
    page.on('console', message => {
      const text = message.text();
      if (/Content[- ]Security[- ]Policy|Refused to/i.test(text)) violations.push(text);
      if (message.type() === 'error') {
        const where = message.location().url || '';
        // A blocked third-party request is expected; anything from the fixture origin is not.
        if (!(/Failed to load resource/.test(text) && !where.startsWith(ORIGIN))) errors.push('console: ' + text + ' ' + where);
      }
    });
    await page.clock.install({ time: T0 });
    if (seedData !== undefined) {
      await page.goto(ORIGIN + allowedSeed);
      await page.evaluate(data => {
        localStorage.clear();
        Object.keys(data).forEach(key => localStorage.setItem(key, typeof data[key] === 'string' ? data[key] : JSON.stringify(data[key])));
      }, seedData);
    }
    if (init) await page.addInitScript(init);
    await page.goto(ORIGIN + url);
    return page;
  }
  async function freeze(page) {
    const now = await page.evaluate(() => Date.now());
    await page.clock.pauseAt(new Date(now + 50));
  }
  const store = (page, key) => page.evaluate(k => { const raw = localStorage.getItem(k); return raw === null ? null : JSON.parse(raw); }, key);
  const openParts = page => page.locator('.ex-part').evaluateAll(list => list.forEach(node => { node.open = true; }));
  const text = (page, selector) => page.locator(selector).first().innerText().then(t => t.replace(/\s+/g, ' ').trim());

  const results = [];
  try {
    // ============================================================ hub
    {
      // (a) no records: the card stays hidden; reading cells exist only for chapters with notes
      let page = await open('/exam', { seedData: {} });
      assert.equal(await page.locator('.ex-continue').isVisible(), false, 'card hidden with no records');
      assert.equal(await page.locator('.ex-continue').evaluate(node => node.children.length), 0);
      await openParts(page);
      const first = page.locator('.ex-progress tbody tr[data-notes="1"]').first();
      assert.equal(await first.locator('.ex-pg-reading .ex-rd-pct').innerText(), '0%');
      assert.equal(await first.locator('.ex-pg-reading .ex-rd-badge').count(), 0, 'no badge before a finished round');
      if (PLAIN_CH !== undefined) {
        const plain = page.locator('.ex-progress tbody tr[data-ch="' + PLAIN_CH + '"] .ex-pg-reading');
        assert.equal((await plain.textContent()).trim(), '—');
        assert.equal(await plain.getAttribute('title'), '本章尚無重點整理');
      }
      assert.equal(await text(page, '#ex-progress-summary').then(t => t.includes('，重點已讀完 0／' + withNotes.length + ' 章（其中 0 章 2 次以上）')), true);
      assert.equal(await page.locator('.ex-progress-sort option[value="reading"]').innerText(), '閱讀進度低優先');
      assert.equal(await page.locator('#ex-rank .ex-rd-badge').count(), 0, 'no ranking badge without reading records');
      assert.equal(await page.locator('.ex-progress th').filter({ hasText: '有重點' }).count(), 0, 'no 有重點 in the progress table');
      await page.close();

      // no JavaScript: nothing new shows, the table keeps its placeholders
      const plainContext = await browser.newContext({ viewport: { width: 1280, height: 900 }, javaScriptEnabled: false, serviceWorkers: 'block' });
      try {
        await routeAll(plainContext);
        const bare = await plainContext.newPage();
        await bare.goto(ORIGIN + '/exam');
        assert.equal(await bare.locator('.ex-continue').isVisible(), false);
        assert.equal((await bare.locator('.ex-progress tbody tr[data-notes="1"] .ex-pg-reading').first().textContent()).trim(), '—');
        assert.equal(await bare.locator('#ex-rank .ex-rd-badge, #ex-rank .ex-badge').count(), 0, 'no ranking badge without JS');
        await bare.goto(ORIGIN + '/exam/fitz-' + NOTE_CH);
        assert.equal(await bare.locator('#ex-reading').isVisible(), false);
        assert.ok(await bare.locator('.ex-note').count() >= 6, 'notes still render without JS');
      } finally { await plainContext.close(); }

      // (b) seeded places: newest chapter, title, 〈h〉, relative time, coverage, no hash; three recent others
      const titleOf = async (pg, ch) => (await pg.locator('.ex-progress tbody tr[data-ch="' + ch + '"] th a').first().textContent()).replace(/^Ch\.\d+\s*/, '').trim();
      const [c1, c2, c3, c4, c5] = withNotes.slice(1, 6);
      const places = {
        ['fitz-' + c1]: { id: 'x', dy: 0, t: T0.getTime() - 3.5 * HOUR, h: '  Alpha\n  標題  ' },
        ['fitz-' + c2]: { id: 'x', dy: 0, t: T0.getTime() - 10 * MIN },
        ['fitz-' + c3]: { id: 'x', dy: 0, t: T0.getTime() - 2 * DAY, h: 'old record' },
        ['fitz-' + c4]: { id: 'x', dy: 0, t: T0.getTime() - 5 * DAY },
        ['fitz-' + c5]: { id: 'x', dy: 0, t: T0.getTime() - 6 * DAY },
        'fitz-9999': { id: 'x', dy: 0, t: T0.getTime() - 1000, h: 'not a chapter in the table' },
        'fitz-abc': { id: 'x', dy: 0, t: T0.getTime() },
        'year-105': { id: 'x', dy: 0, t: T0.getTime() },
        ['fitz-' + (PLAIN_CH !== undefined ? PLAIN_CH : withNotes[6])]: 'junk',
      };
      const reading = { ['fitz-' + c1]: { r: 1, seen: { a: 1 }, pct: 41, t: 1, done: [5] } };
      page = await open('/exam', { seedData: { dnExamPos: places, dnExamReading: reading } });
      assert.equal(await page.locator('.ex-continue').isVisible(), true);
      assert.equal(await text(page, '.ex-continue h2'), '繼續閱讀');
      // c2 is the newest valid record (10 minutes ago, no h)
      const mainLine = await text(page, '.ex-continue-main');
      assert.equal(mainLine, 'Ch.' + c2 + ' ' + await titleOf(page, c2), 'old record without h renders without 〈〉');
      assert.equal(await text(page, '.ex-continue-sub'), '10 分鐘前 · 本章重點已讀 0%');
      const go = page.locator('.ex-continue a.ex-cta');
      assert.equal(await go.getAttribute('href'), '/exam/fitz-' + c2, 'no hash so the page restores the exact place');
      assert.equal((await go.innerText()).trim(), '繼續 →');
      const more = await page.locator('.ex-continue-more a').evaluateAll(links => links.map(a => ({ href: a.getAttribute('href'), text: a.textContent })));
      assert.deepEqual(more.map(m => m.href), ['/exam/fitz-' + c1, '/exam/fitz-' + c3, '/exam/fitz-' + c4], 'up to 3 more, newest first');
      assert.ok(more.every(m => /^Ch\.\d+ /.test(m.text) && m.text.length <= 40));
      assert.ok((await text(page, '.ex-continue-more')).startsWith('最近也讀過：'));
      assert.equal(await page.locator('.ex-continue-sep').count(), 2);
      assert.equal(await page.locator('.ex-continue [href*="#"]').count(), 0);
      await page.close();

      // the 〈h〉 title and coverage of the newest chapter; each relative-time bucket
      const buckets = [[5000, '剛剛'], [90 * 1000, '1 分鐘前'], [2 * HOUR + 5 * MIN, '2 小時前'], [3 * DAY + HOUR, '3 天前'], [29 * DAY, '29 天前']];
      for (const [age, label] of buckets) {
        page = await open('/exam', { seedData: { dnExamPos: { ['fitz-' + c1]: { id: 'x', dy: 0, t: T0.getTime() - age, h: '  Alpha\n  標題  ' } }, dnExamReading: reading } });
        const sub = await text(page, '.ex-continue-sub');
        assert.equal(sub, label + ' · 本章重點已讀 41%', 'bucket ' + label);
        assert.equal(await text(page, '.ex-continue-main'), 'Ch.' + c1 + ' ' + await titleOf(page, c1) + ' 〈Alpha 標題〉');
        assert.equal(await page.locator('.ex-continue-more').count(), 0, 'no "also read" line with a single record');
        await page.close();
      }
      // >= 30 days: the date
      const oldT = T0.getTime() - 45 * DAY, od = new Date(oldT);
      const oldCh = PLAIN_CH !== undefined ? PLAIN_CH : withNotes[6];
      page = await open('/exam', { seedData: { dnExamPos: { ['fitz-' + oldCh]: { id: 'x', dy: 0, t: oldT, h: 'x'.repeat(300) } } } });
      assert.equal(await text(page, '.ex-continue-sub'), od.getFullYear() + '/' + (od.getMonth() + 1) + '/' + od.getDate() +
        (PLAIN_CH !== undefined ? '' : ' · 本章重點已讀 0%'), 'coverage only for a chapter with notes');
      assert.ok((await text(page, '.ex-continue-main')).length <= 'Ch.000 '.length + (await titleOf(page, oldCh)).length + 125, 'h is capped');
      await page.close();

      // (c) table cells, summary and the new sort order
      const [a, b, c, d] = withNotes.slice(0, 4);
      const seeded = {
        ['fitz-' + a]: { r: 2, seen: {}, pct: 30, t: 1, done: [1, 2] },
        ['fitz-' + b]: { r: 1, seen: {}, pct: 80, t: 1, done: [1] },
        ['fitz-' + c]: { r: 0, seen: {}, pct: 60, t: 1, done: [] },
        ['fitz-' + d]: { r: 'x', seen: {}, pct: 10, t: 1, done: [] },          // malformed -> dropped
        ['fitz-' + withNotes[4]]: { r: 3, seen: { a: 2 }, pct: 5, t: 1, done: [] },  // seen values must be 1 -> kept without ids
      };
      page = await open('/exam', { seedData: { dnExamReading: seeded } });
      await openParts(page);
      const cell = ch => page.locator('.ex-progress tbody tr[data-ch="' + ch + '"] .ex-pg-reading');
      assert.equal((await cell(a).innerText()).replace(/\s+/g, ' ').trim(), '✓2 30%');
      assert.equal(await cell(a).locator('.ex-rd-badge').getAttribute('aria-label'), '讀完 2 次');
      assert.equal(await cell(a).locator('.ex-rd-badge').getAttribute('title'), '讀完 2 次');
      assert.equal(await cell(a).locator('.ex-rd-bar').getAttribute('aria-hidden'), 'true');
      assert.equal(await cell(a).locator('.ex-rd-fill').evaluate(node => node.style.width), '30%');
      assert.ok(await cell(a).locator('.ex-rd-bar').evaluate(node => node.getBoundingClientRect().width) <= 48);
      assert.equal((await cell(b).innerText()).replace(/\s+/g, ' ').trim(), '✓1 80%');
      assert.equal((await cell(c).innerText()).replace(/\s+/g, ' ').trim(), '60%');
      assert.equal((await cell(d).innerText()).replace(/\s+/g, ' ').trim(), '0%', 'malformed record ignored');
      assert.equal((await cell(withNotes[4]).innerText()).replace(/\s+/g, ' ').trim(), '✓3 5%');
      assert.ok((await text(page, '#ex-progress-summary')).endsWith('，重點已讀完 3／' + withNotes.length + ' 章（其中 2 章 2 次以上）'));
      await page.selectOption('.ex-progress-sort', 'reading');
      const orderOk = await page.evaluate(() => Array.from(document.querySelectorAll('.ex-progress')).every(table => {
        const rows = Array.from(table.tBodies[0].rows).map(row => ({
          notes: row.hasAttribute('data-notes'), r: Number(row.dataset.r), pct: Number(row.dataset.rpct), order: Number(row.dataset.order) }));
        for (let i = 1; i < rows.length; i++) {
          const x = rows[i - 1], y = rows[i];
          if (!x.notes && y.notes) return false;
          if (x.notes && y.notes && (x.r - y.r || x.pct - y.pct || x.order - y.order) > 0) return false;
          if (!x.notes && !y.notes && x.order > y.order) return false;
        }
        return true;
      }));
      assert.equal(orderOk, true, 'reading sort: notes first by rounds then coverage, the rest in chapter order');
      const partWithBoth = await page.evaluate(([x, y, z]) => {
        const rows = Array.from(document.querySelector('.ex-progress tbody tr[data-ch="' + x + '"]').closest('tbody').rows).map(r => Number(r.dataset.ch));
        return [x, y, z].map(ch => rows.indexOf(ch));
      }, [a, b, c]);
      if (partWithBoth.every(i => i >= 0)) assert.ok(partWithBoth[2] < partWithBoth[1] && partWithBoth[1] < partWithBoth[0], 'r0 before r1 before r2 within one part');
      await page.selectOption('.ex-progress-sort', 'order');
      const restored = await page.evaluate(() => Array.from(document.querySelectorAll('.ex-progress')).every(t => Array.from(t.tBodies[0].rows).every((row, i, rows) => i === 0 || Number(rows[i - 1].dataset.order) < Number(row.dataset.order))));
      assert.equal(restored, true, 'chapter order restored');
      await page.close();

      // (c2) 出題頻率 table: ✓N (rounds read) after the chapter link, none for 0 rounds
      {
        const [r2, r1, r0, bad] = rankNotes;
        const rankSeed = {
          ['fitz-' + r2]: { r: 2, seen: {}, pct: 30, t: 1, done: [1, 2] },
          ['fitz-' + r1]: { r: 1, seen: {}, pct: 80, t: 1, done: [1] },
          ['fitz-' + r0]: { r: 0, seen: {}, pct: 60, t: 1, done: [] },
          ['fitz-' + bad]: { r: 'x', seen: {}, pct: 10, t: 1, done: [] },  // malformed -> no badge
        };
        page = await open('/exam', { seedData: { dnExamReading: rankSeed } });
        const rankBadge = ch => page.locator('#ex-rank tbody tr[data-ch="' + ch + '"] td:first-child .ex-rd-badge');
        assert.equal(await rankBadge(r2).count(), 1);
        assert.equal((await rankBadge(r2).textContent()).trim(), '✓2', 'badge text carries the count, not only colour');
        assert.equal(await rankBadge(r2).getAttribute('aria-label'), '讀完 2 次');
        assert.equal(await rankBadge(r2).getAttribute('role'), 'img');
        assert.equal((await rankBadge(r1).textContent()).trim(), '✓1');
        assert.equal(await rankBadge(r1).getAttribute('aria-label'), '讀完 1 次');
        assert.equal(await rankBadge(r0).count(), 0, 'no badge for 0 rounds');
        assert.equal(await rankBadge(bad).count(), 0, 'no badge for a malformed record');
        assert.equal(await page.locator('#ex-rank .ex-rd-badge').count(), 2, 'only chapters with finished rounds');
        // the badge follows the link inside the same cell
        assert.equal(await page.locator('#ex-rank tbody tr[data-ch="' + r2 + '"] td:first-child').evaluate(td => td.lastElementChild.className), 'ex-rd-badge');
        // readable in dark mode: text and background differ
        // Save the preference too: the deferred shared runtime applies the saved
        // theme when it initialises, and could otherwise reset a bare attribute.
        await page.evaluate(() => {
          localStorage.setItem('dn-theme', 'dark');
          document.documentElement.setAttribute('data-theme', 'dark');
        });
        const dark = await rankBadge(r2).evaluate(node => { const s = getComputedStyle(node); return [s.color, s.backgroundColor]; });
        assert.deepEqual(dark, ['rgb(220, 252, 231)', 'rgb(20, 83, 45)'], 'dark-mode badge colours');
        // a back-forward restore after another round redraws without duplicates
        await page.evaluate(ch => {
          const all = JSON.parse(localStorage.getItem('dnExamReading'));
          all['fitz-' + ch].r = 3;
          localStorage.setItem('dnExamReading', JSON.stringify(all));
          window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }));
        }, r2);
        assert.equal(await rankBadge(r2).count(), 1);
        assert.equal(await rankBadge(r2).getAttribute('aria-label'), '讀完 3 次');
        await page.close();
      }

      // (g) malformed storage is ignored; storage that throws leaves the page untouched
      page = await open('/exam', { seedData: { dnExamReading: '{not json', dnExamPos: '[1,2]' } });
      assert.equal(await page.locator('.ex-continue').isVisible(), false);
      assert.ok((await text(page, '#ex-progress-summary')).includes('重點已讀完 0／'));
      await page.close();
      page = await open('/exam', { init: () => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('denied'); } }); } });
      assert.equal(await page.locator('.ex-continue').isVisible(), false);
      assert.equal((await page.locator('.ex-progress tbody tr[data-notes="1"] .ex-pg-reading').first().textContent()).trim(), '—');
      assert.equal(await page.locator('#ex-rank .ex-rd-badge').count(), 0, 'no ranking badge without storage');
      await page.close();
      results.push('hub');
    }

    // ============================================================ chapter page
    const status = page => text(page, '.ex-reading-text');
    const scrollTo = async (page, id) => {
      await page.evaluate(sectionId => {
        const node = document.getElementById(sectionId);
        window.scrollTo({ top: node.getBoundingClientRect().top + window.scrollY - 100, behavior: 'instant' });
      }, id);
      await page.waitForTimeout(250);  // let IntersectionObserver report (real time)
    };
    const url = '/exam/fitz-' + NOTE_CH;
    {
      // a chapter without notes does no reading work at all
      const counter = () => {
        window.__io = 0;
        const Real = window.IntersectionObserver;
        window.IntersectionObserver = function (...args) { window.__io += 1; return new Real(...args); };
      };
      let page;
      if (PLAIN_CH !== undefined) {
        page = await open('/exam/fitz-' + PLAIN_CH, { seedData: {}, init: counter });
        assert.equal(await page.locator('#ex-reading').count(), 0);
        assert.equal(await page.evaluate(() => window.__io), 0, 'no observer on a page without notes');
        await page.close();
      }

      page = await open(url, { seedData: {}, init: counter });
      assert.ok(await page.evaluate(() => window.__io) >= 1);
      assert.equal(await page.locator('#ex-reading').isVisible(), true);
      assert.ok(await page.locator('#ex-reading').evaluate(node => node.compareDocumentPosition(document.querySelector('.ex-note')) & Node.DOCUMENT_POSITION_FOLLOWING), 'status line sits before the first note');
      assert.equal(await page.locator('.ex-notes #ex-reading').count(), 1);
      assert.equal(await status(page), '本章重點：第 1 輪，已讀 0%');
      await freeze(page);

      // (d) a fast scroll-through does not count
      for (const s of sections) { await scrollTo(page, s.id); await page.clock.runFor(1500); }
      assert.equal(await status(page), '本章重點：第 1 輪，已讀 0%');
      await page.clock.runFor(2000);
      assert.equal(await store(page, 'dnExamReading'), null, 'nothing is stored before something is read');

      await page.close();

      // staying long enough counts, and only that section (plus any equally visible neighbour)
      page = await open(url, { seedData: {} });
      await freeze(page);
      const target = sections[1];
      await scrollTo(page, target.id);
      await page.clock.runFor(need(target) - 3000);
      assert.equal(await status(page), '本章重點：第 1 輪，已讀 0%', 'not yet at the required dwell');
      // a hidden tab pauses the clock of the section
      await page.evaluate(() => { Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' }); document.dispatchEvent(new Event('visibilitychange')); });
      await page.clock.runFor(120000);
      assert.equal(await status(page), '本章重點：第 1 輪，已讀 0%', 'hidden tab accumulates nothing');
      await page.evaluate(() => { delete document.visibilityState; document.dispatchEvent(new Event('visibilitychange')); });
      await page.clock.runFor(2000);
      assert.equal(await status(page), '本章重點：第 1 輪，已讀 0%', 'resuming does not credit the hidden time');
      await page.clock.runFor(4000);
      await page.clock.runFor(2000);  // debounced save
      const after = await store(page, 'dnExamReading');
      assert.ok(after && after['fitz-' + NOTE_CH], 'record written');
      const rec = after['fitz-' + NOTE_CH];
      assert.equal(rec.seen[target.id], 1);
      assert.equal(rec.r, 0);
      assert.equal(rec.pct, pctOf(Object.keys(rec.seen)));
      assert.ok(rec.pct > 0 && Number.isInteger(rec.t) && Array.isArray(rec.done) && rec.done.length === 0);
      assert.equal(await status(page), '本章重點：第 1 輪，已讀 ' + rec.pct + '%');
      await page.close();

      // (e) reaching 75% finishes the round: r+1, reset, toast; twice, to cover auto-dismiss and the close button
      page = await open(url, { seedData: {} });
      await freeze(page);
      const readRound = async expectedRounds => {
        for (const s of sections) {
          if ((await store(page, 'dnExamReading') || {})['fitz-' + NOTE_CH]?.r === expectedRounds) break;
          await scrollTo(page, s.id);
          // one second at a time, so the test stops right when the round completes
          for (let t = 0; t < need(s) + 3000; t += 1000) {
            await page.clock.runFor(1000);
            if ((await store(page, 'dnExamReading') || {})['fitz-' + NOTE_CH]?.r === expectedRounds) break;
          }
        }
      };
      await readRound(1);
      let saved = (await store(page, 'dnExamReading'))['fitz-' + NOTE_CH];
      assert.equal(saved.r, 1);
      assert.ok(typeof saved.g === 'string' && saved.g.length > 0, 'record carries a generation id');
      assert.deepEqual(saved.seen, {});
      assert.equal(saved.pct, 0);
      assert.equal(saved.done.length, 1);
      const sinceDone = await page.evaluate(() => Date.now()) - saved.done[0];
      assert.ok(sinceDone >= 0 && sinceDone <= 1000, 'completion time recorded (page clock)');
      assert.equal(await status(page), '本章重點：第 2 輪，已讀 0%（已讀完 1 次）');
      const toast = page.locator('.ex-toast');
      assert.equal(await toast.count(), 1);
      assert.equal(await toast.getAttribute('role'), 'status');
      assert.equal((await toast.locator('.ex-resume-text').innerText()).trim(), '本章重點第 1 輪讀完 ✓');
      await page.clock.runFor(6500);
      assert.equal(await page.locator('.ex-toast').count(), 0, 'toast leaves by itself after about 6 s');
      await readRound(2);
      saved = (await store(page, 'dnExamReading'))['fitz-' + NOTE_CH];
      assert.equal(saved.r, 2);
      assert.equal(saved.done.length, 2);
      assert.equal(await status(page), '本章重點：第 3 輪，已讀 0%（已讀完 2 次）');
      assert.equal((await page.locator('.ex-toast .ex-resume-text').innerText()).trim(), '本章重點第 2 輪讀完 ✓');
      await page.locator('.ex-toast .ex-resume-close').click();
      assert.equal(await page.locator('.ex-toast').count(), 0, 'toast can be closed');
      await page.close();

      // (f) reset button: confirm accepted clears only this chapter; declined changes nothing
      const answers = { 'fitz-17': { 'q-1': [1, 5, 'A'] } };
      const other = { r: 1, seen: { def: 1 }, pct: 7, t: 5, done: [9] };
      page = await open(url, { seedData: {
        dnExamReading: { ['fitz-' + NOTE_CH]: { r: 2, seen: { [sections[0].id]: 1, gone: 1 }, pct: 99, t: 5, done: [1, 2] }, 'fitz-17': other },
        dnExamChapterProgress: answers,
      } });
      assert.equal(await status(page), '本章重點：第 3 輪，已讀 ' + pctOf([sections[0].id]) + '%（已讀完 2 次）', 'pct is recomputed against the sections that exist; vanished ids are ignored');
      const dialogs = [];
      let accept = false;
      page.on('dialog', dialog => { dialogs.push(dialog.message()); (accept ? dialog.accept() : dialog.dismiss()).catch(() => {}); });
      await page.locator('.ex-reading-reset').click();
      assert.deepEqual(dialogs, ['重設本章的閱讀次數與進度？作答紀錄不受影響。']);
      assert.equal((await store(page, 'dnExamReading'))['fitz-' + NOTE_CH].r, 2, 'declined');
      accept = true;
      await page.locator('.ex-reading-reset').click();
      const left = await store(page, 'dnExamReading');
      assert.deepEqual(Object.keys(left).sort(), ['fitz-' + NOTE_CH, 'fitz-17'].sort());
      assert.deepEqual(left['fitz-17'], other, 'other chapters untouched');
      const wiped = left['fitz-' + NOTE_CH];
      assert.ok(typeof wiped.g === 'string' && wiped.g.length > 0);
      assert.deepEqual({ r: wiped.r, seen: wiped.seen, pct: wiped.pct, done: wiped.done }, { r: 0, seen: {}, pct: 0, done: [] }, 'reset writes a fresh record');
      assert.deepEqual(await store(page, 'dnExamChapterProgress'), answers, 'answers untouched');
      assert.equal(await status(page), '本章重點：第 1 輪，已讀 0%');
      assert.equal(await page.locator('#ex-reading').isVisible(), true);
      await page.close();

      // ---- several tabs of the same chapter share one record without overwriting each other
      const chapterRecord = p => store(p, 'dnExamReading').then(all => (all || {})['fitz-' + NOTE_CH] || null);
      const blockStorageEvents = () => window.addEventListener('storage', event => event.stopImmediatePropagation(), true);
      // Read one section on page p: scroll to it and let its dwell time pass.
      const readSection = async (p, section) => {
        await scrollTo(p, section.id);
        for (let t = 0; t < need(section) + 4000; t += 1000) {
          await p.clock.runFor(1000);
          const now = await chapterRecord(p);
          if (now && now.seen[section.id] === 1) return;
        }
      };
      const finishRound = async (p, rounds) => {
        for (const section of sections) {
          if ((await chapterRecord(p) || { r: 0 }).r >= rounds) return;
          await scrollTo(p, section.id);
          for (let t = 0; t < need(section) + 4000; t += 1000) {
            await p.clock.runFor(1000);
            if ((await chapterRecord(p) || { r: 0 }).r >= rounds) return;
          }
        }
      };
      // page.clock is shared by the whole context: park the tabs that must stay idle
      // at the bottom of the page (questions, no note section on screen).
      const park = async p => {
        await p.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'instant' }));
        await p.waitForTimeout(250);
      };
      const statusIs = (p, expected) => p.waitForFunction(want => {
        const node = document.querySelector('.ex-reading-text');
        return node && node.textContent === want;
      }, expected, { polling: 100, timeout: 10000 });

      // (a) tab A completes a round; tab B (which may or may not have heard about it) reads one section
      for (const blocked of [true, false]) {
        const A = await open(url, { seedData: {} });
        const B = await open(url, blocked ? { init: blockStorageEvents } : {});
        await freeze(A); await freeze(B);
        await park(B);
        await finishRound(A, 1);
        await park(A);
        const afterA = await chapterRecord(A);
        assert.equal(afterA.r, 1);
        assert.equal(afterA.done.length, 1);
        await readSection(B, sections[0]);
        const merged = await chapterRecord(B);
        assert.equal(merged.r, 1, "B did not overwrite A's finished round (events blocked: " + blocked + ')');
        assert.equal(merged.g, afterA.g, 'same generation');
        assert.deepEqual(merged.done, afterA.done, "A's completion time kept");
        assert.equal(merged.seen[sections[0].id], 1, "B's section is in the new round");
        assert.equal(merged.pct, pctOf(Object.keys(merged.seen)));
        await statusIs(B, '本章重點：第 2 輪，已讀 ' + merged.pct + '%（已讀完 1 次）');
        await A.close(); await B.close();
      }

      // (b) A resets while B holds older state: B must not revive the old rounds or sections
      const oldRecord = { g: 'oldgen1', r: 1, seen: { [sections[0].id]: 1, [sections[1].id]: 1 }, pct: pctOf([sections[0].id, sections[1].id]), t: 5, done: [7] };
      for (const blocked of [true, false]) {
        const A = await open(url, { seedData: { dnExamReading: { ['fitz-' + NOTE_CH]: oldRecord } } });
        const B = await open(url, blocked ? { init: blockStorageEvents } : {});
        await freeze(A); await freeze(B);
        await statusIs(B, '本章重點：第 2 輪，已讀 ' + oldRecord.pct + '%（已讀完 1 次）');
        A.on('dialog', dialog => dialog.accept().catch(() => {}));
        await A.locator('.ex-reading-reset').click();
        await park(A);
        const wiped = await chapterRecord(A);
        assert.ok(wiped.g && wiped.g !== 'oldgen1', 'reset starts a new generation');
        assert.equal(wiped.r, 0);
        if (!blocked) await statusIs(B, '本章重點：第 1 輪，已讀 0%');  // (c) the storage event updated B
        await readSection(B, sections[3]);
        let now = await chapterRecord(B);
        if (blocked) {
          assert.equal(now.g, wiped.g, 'B did not write over the reset record');
          assert.equal(now.r, 0, 'old rounds not revived');
          assert.deepEqual(now.seen, {}, "B's read from before the reset is dropped ");
          assert.deepEqual(now.done, []);
          await statusIs(B, '本章重點：第 1 輪，已讀 0%');
        } else {
          assert.equal(now.g, wiped.g);
          assert.equal(now.r, 0);
          assert.deepEqual(Object.keys(now.seen), [sections[3].id], 'a read after the reset counts');
        }
        // after adopting the new generation B keeps contributing to it
        await readSection(B, sections[4]);
        now = await chapterRecord(B);
        assert.equal(now.g, wiped.g);
        assert.equal(now.r, 0);
        assert.equal(now.seen[sections[4].id], 1);
        assert.equal(now.seen[sections[0].id], undefined, 'old seen not revived');
        assert.equal(now.seen[sections[1].id], undefined, 'old seen not revived');
        await A.close(); await B.close();
      }

      // (c) B's status line follows A through the storage event, and C through becoming visible again
      {
        const A = await open(url, { seedData: {} });
        const B = await open(url);
        const C = await open(url, { init: blockStorageEvents });
        await freeze(A); await freeze(B); await freeze(C);
        await park(B); await park(C);
        await readSection(A, sections[1]);
        const wrote = await chapterRecord(A);
        const expected = '本章重點：第 1 輪，已讀 ' + wrote.pct + '%';
        await statusIs(B, expected);
        assert.deepEqual(await chapterRecord(B), wrote, 'B only displayed; it wrote nothing');
        assert.equal(await status(C), '本章重點：第 1 輪，已讀 0%', 'C heard nothing yet');
        await C.evaluate(() => { Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' }); document.dispatchEvent(new Event('visibilitychange')); });
        await C.evaluate(() => { delete document.visibilityState; document.dispatchEvent(new Event('visibilitychange')); });
        await statusIs(C, expected);
        assert.deepEqual(await chapterRecord(C), wrote, 'C only displayed; it wrote nothing');
        await A.close(); await B.close(); await C.close();
      }

      // (d) a record written before generation ids existed still loads and gets one on the next write
      {
        const legacy = { r: 1, seen: {}, pct: 0, t: 3, done: [3] };
        const A = await open(url, { seedData: { dnExamReading: { ['fitz-' + NOTE_CH]: legacy } } });
        await freeze(A);
        assert.equal(await status(A), '本章重點：第 2 輪，已讀 0%（已讀完 1 次）');
        assert.equal((await chapterRecord(A)).g, undefined, 'nothing written yet');
        await readSection(A, sections[2]);
        const now = await chapterRecord(A);
        assert.ok(typeof now.g === 'string' && now.g.length > 0, 'a generation id is assigned on the first write');
        assert.equal(now.r, 1);
        assert.deepEqual(now.done, [3]);
        assert.equal(now.seen[sections[2].id], 1);
        await A.close();
      }

      // (g) malformed storage and unusable storage on a chapter page
      page = await open(url, { seedData: { dnExamReading: { ['fitz-' + NOTE_CH]: { r: -1, seen: [], pct: 'x' } }, dnExamPos: 'oops' } });
      assert.equal(await status(page), '本章重點：第 1 輪，已讀 0%');
      await page.close();
      page = await open(url, { init: () => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('denied'); } }); } });
      assert.equal(await page.locator('#ex-reading').isVisible(), false, 'no status without storage');
      assert.ok(await page.locator('.ex-note').count() >= 6);
      await page.close();

      // the position record now carries the section title for the hub card
      page = await open(url, { seedData: {} });
      await freeze(page);
      await scrollTo(page, sections[2].id);
      await page.clock.runFor(1000);
      const pos = (await store(page, 'dnExamPos'))['fitz-' + NOTE_CH];
      assert.ok(pos && typeof pos.h === 'string' && pos.h.length > 0 && pos.h.length <= 120, 'saved place has a title');
      assert.ok(typeof pos.id === 'string' && Number.isInteger(pos.t));
      await page.close();
      results.push('chapter');
    }

    // (h) no console errors, no CSP violations
    assert.deepEqual(violations, [], 'no CSP violations under the production policy');
    assert.deepEqual(errors, [], 'no page or console errors');
  } finally { await context.close(); }
  return results;
};
