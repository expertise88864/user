// Isolated homepage fixture: a pointer resting just inside the edge a hover lift
// moves away from must keep the card still. Lifting the hover area out from under
// the pointer used to end the hover, drop the card back and lift it again, so the
// card shook for as long as the pointer stayed there (seen by readers and as
// "element is not stable" in the Preview browser check).
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ORIGIN = 'https://hover.test';
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.ico': 'image/x-icon',
  '.woff2': 'font/woff2', '.xml': 'application/xml', '.txt': 'text/plain' };
// Each case names the edge the lift uncovers: a translateY(-n) lift uncovers the
// bottom edge, a translateX(+n) slide uncovers the left edge.
const CASES = [
  { width: 1440, js: true, selector: '#dn-hub .dn-tag-card', pick: 'first', edge: 'bottom' },
  { width: 1440, js: true, selector: '#dn-hub .dn-tag-card', pick: 'last', edge: 'bottom' },
  { width: 1440, js: true, selector: '.mag-ctas .btn-teal', pick: 'first', edge: 'bottom' },
  { width: 1440, js: true, selector: '.mag-ctas .btn-ghost', pick: 'first', edge: 'bottom' },
  { width: 1440, js: true, selector: '.mag-feature > .mag-card', pick: 'first', edge: 'bottom' },
  { width: 1440, js: true, selector: '#dn-article-list > .article-list-item', pick: 'first', edge: 'bottom' },
  { width: 1440, js: false, selector: '#dn-article-list > .article-list-item', pick: 'first', edge: 'bottom' },
  { width: 1440, js: false, selector: '#dn-article-list > .article-list-item', pick: 'first', edge: 'left' },
  { width: 600, js: false, selector: '#dn-article-list > .article-list-item', pick: 'first', edge: 'left' },
];
const FRAMES = 60;
// The lifts are 1-3 px; a pointer resting 1-2 px inside the edge sits in that band.
const INSETS = [1, 2];

function defaultRead(name) {
  const root = process.cwd(), file = path.resolve(root, name);
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return null;
  return fs.readFileSync(file);
}

async function serve(context, read) {
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    // Fonts, analytics and other third parties never leave the runner.
    if (url.origin !== ORIGIN || request.method() !== 'GET') return route.abort();
    let name = decodeURIComponent(url.pathname).replace(/^\/+/, '');
    if (!name || name.endsWith('/')) name += 'index.html';
    else if (!path.posix.extname(name)) name += '.html';
    const body = read(name);
    if (body === null) return route.fulfill({ status: 404, body: '' });
    return route.fulfill({ status: 200, contentType: TYPES[path.posix.extname(name)] || 'application/octet-stream', body });
  });
}

// Rect and hover state of the element on each of `frames` consecutive frames.
// Pages with JavaScript disabled run no animation-frame callbacks, so they are
// sampled from the runner instead, at least one frame (16 ms) apart.
async function samples(page, handle, frames, js) {
  if (js) return handle.evaluate(sample, frames);
  const rows = [];
  while (rows.length < frames) {
    rows.push(await handle.evaluate(element => {
      const rect = element.getBoundingClientRect();
      return { top: rect.top, left: rect.left, bottom: rect.bottom, right: rect.right, hover: element.matches(':hover') };
    }));
    await page.waitForTimeout(16);
  }
  return rows;
}
function sample(element, frames) {
  return new Promise(resolve => {
    const rows = [];
    (function frame() {
      const rect = element.getBoundingClientRect();
      rows.push({ top: rect.top, left: rect.left, bottom: rect.bottom, right: rect.right, hover: element.matches(':hover') });
      if (rows.length === frames) resolve(rows); else requestAnimationFrame(frame);
    })();
  });
}

async function checkCase(browser, read, spec) {
  const context = await browser.newContext({ viewport: { width: spec.width, height: 900 }, javaScriptEnabled: spec.js,
    serviceWorkers: 'block', reducedMotion: 'no-preference', locale: 'zh-TW' });
  try {
    await serve(context, read);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(ORIGIN + '/', { waitUntil: 'load' });
    const all = page.locator(spec.selector + ':visible');
    await all.first().waitFor();
    const target = spec.pick === 'last' ? all.last() : all.first();
    const handle = await target.elementHandle();
    // Park the pointer away from the page, then bring the element to the middle of
    // the viewport and let scroll-linked entry animations and reveals settle.
    await page.mouse.move(0, 0);
    await handle.evaluate(element => element.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' }));
    await page.waitForTimeout(900);
    const [rest] = await samples(page, handle, 1, spec.js);
    assert.equal(rest.hover, false, 'The pointer must start outside the element');
    for (const inset of INSETS) {
      // Just inside the edge the lift moves away from.
      const x = spec.edge === 'left' ? rest.left + inset : (rest.left + rest.right) / 2;
      const y = spec.edge === 'left' ? (rest.top + rest.bottom) / 2 : rest.bottom - inset;
      await page.mouse.move(x, y);
      await page.waitForTimeout(700);  // longer than every hover transition
      const rows = await samples(page, handle, FRAMES, spec.js);
      const label = spec.selector + ' (' + spec.pick + ', ' + inset + ' px inside the ' + spec.edge + ' edge, ' +
        spec.width + 'px, JavaScript ' + (spec.js ? 'on' : 'off') + ')';
      assert.ok(rows.every(row => row.hover), 'Hover must persist while the pointer rests inside: ' + label);
      const moved = rows.filter(row => row.top !== rows[0].top || row.left !== rows[0].left);
      assert.deepEqual(moved, [], 'Element must stay still for ' + FRAMES + ' frames: ' + label);
      assert.ok(rows[0].top < rest.top || rows[0].left > rest.left || rows[0].bottom > rest.bottom,
        'The hover effect must actually apply (otherwise this check proves nothing): ' + label);
      await page.mouse.move(0, 0);
      await page.waitForTimeout(700);
      const [after] = await samples(page, handle, 1, spec.js);
      assert.deepEqual(after, rest, 'Leaving must return the element to rest: ' + label);
    }
    assert.deepEqual(errors, [], 'Page JavaScript errors');
  } finally { await context.close(); }
}

module.exports = async function checkHoverStability(browser, { read = defaultRead } = {}) {
  for (const spec of CASES) {
    try { await checkCase(browser, read, spec); }
    catch (error) { error.message = spec.selector + ' ' + spec.edge + ' ' + spec.width + 'px JS=' + spec.js + ': ' + error.message; throw error; }
  }
  console.log('Hover hit areas stay put: ' + CASES.length + ' cases, ' + FRAMES + ' still frames each');
  return CASES.length;
};
module.exports.CASES = CASES;
