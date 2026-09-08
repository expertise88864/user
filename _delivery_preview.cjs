/* Read-only preview acceptance; never submits forms or changes visual baselines. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
// Never attach the preview credential to analytics, images, or redirect hosts.
function previewHeaders(url, origin, secret) {
  return secret && new URL(url).origin === origin
    ? { 'x-vercel-protection-bypass': secret } : {};
}
module.exports = { previewHeaders };

if (require.main === module) (async () => {
  const { chromium } = require('playwright');
  const base = new URL(process.env.PW_BASE_URL);
  assert.equal(base.protocol, 'https:');
  assert.ok(base.hostname.endsWith('.vercel.app'));
  const policy = JSON.parse(fs.readFileSync('_delivery_policy.json', 'utf8'));
  fs.mkdirSync('delivery-preview', { recursive: true });
  const browser = await chromium.launch();
  try {
    for (const width of [390, 800, 1440]) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, locale: 'zh-TW' });
      try {
        await context.route('**/*', async route => {
          const request = route.request();
          const headers = { ...request.headers() };
          delete headers['x-vercel-protection-bypass'];
          Object.assign(headers, previewHeaders(request.url(), base.origin, process.env.VERCEL_AUTOMATION_BYPASS_SECRET));
          // A redirect becomes a fresh intercepted browser request. Never let
          // the API client follow it while carrying the preview credential.
          const response = await route.fetch({ headers, maxRedirects: 0 });
          await route.fulfill({ response });
        });
        for (const [index, route] of policy.preview_paths.entries()) {
          const page = await context.newPage();
          const errors = [];
          page.on('pageerror', e => errors.push(e.message));
          const response = await page.goto(new URL(route, base).href, { waitUntil: 'load' });
          assert.ok(response && response.status() === 200, route + ' must return HTTP 200');
          assert.equal(new URL(page.url()).hostname, base.hostname, 'Preview must not redirect to production/login');
          assert.ok((await page.title()).trim().length > 0, 'Document title missing');
          assert.ok(await page.locator('main').count() > 0, 'Main content missing');
          const nav = page.locator('nav.dn-nav');
          if (await nav.count()) {
            const burger = page.locator('#dn-nav-burger');
            const search = page.locator('#dn-nav-search');
            if (width <= 899) {
              assert.ok(await burger.isVisible(), 'Mobile/tablet menu control missing');
              assert.equal(await nav.isVisible(), false, 'Mobile/tablet menu must start collapsed');
              await burger.click();
              assert.ok(await nav.isVisible(), 'Mobile/tablet menu did not open');
              assert.ok(await search.evaluate(el => el.getBoundingClientRect().width > 100
                && getComputedStyle(el, '::after').display !== 'none'), 'Menu labels must have room');
              for (const id of ['dn-nav-search', 'dn-nav-support', 'dn-nav-theme']) {
                assert.ok(await page.locator('#' + id).evaluate(el =>
                  getComputedStyle(el, '::after').content === JSON.stringify(el.getAttribute('aria-label'))),
                  'Visible menu label must match the current page language: ' + id);
              }
              await burger.click();
              assert.equal(await nav.isVisible(), false, 'Mobile/tablet menu did not close');
            } else {
              assert.ok(await nav.isVisible(), 'Desktop navigation missing');
              assert.equal(await burger.isVisible(), false, 'Desktop hamburger should be hidden');
              assert.equal(await search.evaluate(el => getComputedStyle(el, '::after').display),
                'none', 'Desktop icon labels must not overflow compact buttons');
            }
          }
          await page.screenshot({ path: 'delivery-preview/' + width + '-' + index + '.png', fullPage: true });
          assert.deepEqual(errors, [], 'Page JavaScript errors');
          await page.close();
        }
      } finally { await context.close(); }
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
