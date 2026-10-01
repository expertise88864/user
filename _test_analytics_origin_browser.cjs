// Isolated native documents. Every request is fulfilled locally before egress;
// no user cookies, actual collectors, vendor code or account settings are used.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('assets/inline/analytics-loader.js', 'utf8');

module.exports = async function checkAnalyticsOrigins(browser) {
  const cases = [
    ['https://chendermatologist.com', true],
    ['https://chendermatologist.com:443', true],
    ['https://chendermatologist-clpruakvg-expertise88864s-projects.vercel.app', false],
    ['https://chendermatologist.com.attacker.test', false],
    ['https://www.chendermatologist.com', false],
    ['https://chendermatologist.com:444', false],
    ['http://chendermatologist.com', false],
    ['http://localhost:60326', false],
  ];
  for (const [origin, production] of cases) {
    const context = await browser.newContext({serviceWorkers: 'block',
      // The native test runner must exercise the ordinary-reader branch.
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'});
    const vendor = [], errors = [];
    try {
      await context.addInitScript(() => { window.requestIdleCallback = callback => setTimeout(callback, 0); });
      await context.route('**/*', route => {
        const request = route.request(), url = new URL(request.url());
        if (request.isNavigationRequest()) return route.fulfill({contentType: 'text/html', body:
          '<!doctype html><title>Analytics origin fixture</title><main><p>Fixture only.</p></main>' +
          '<script src="/assets/inline/analytics-loader.js"></script>' +
          '<script>setTimeout(function(){window.fixtureIdleComplete=true;},50)</script>'});
        if (url.origin === new URL(origin).origin && url.pathname === '/assets/inline/analytics-loader.js') {
          return route.fulfill({contentType: 'text/javascript', body: source});
        }
        vendor.push({host: url.hostname, path: url.pathname, method: request.method()});
        return route.fulfill({status: 200, contentType: 'text/javascript', body: ''});
      });
      const page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(origin + '/blog/example?q=fixture-only#fixture', {waitUntil: 'load'});
      await page.waitForFunction(() => window.fixtureIdleComplete === true);
      await page.evaluate(() => window.gtag('event', 'article_read_threshold', {slug: 'example'}));
      const commands = await page.evaluate(() => Array.from(window.dataLayer || [], args => Array.from(args)));
      assert.deepEqual(errors, [], 'the production guard must not break page initialization');
      if (production) {
        assert.deepEqual(vendor.map(item => item.host).sort(), ['www.clarity.ms', 'www.googletagmanager.com']);
        assert.equal(commands.filter(item => item[1] === 'page_view').length, 1);
        assert.equal(commands.filter(item => item[1] === 'article_read_threshold').length, 1);
        assert.equal(commands.find(item => item[1] === 'page_view')[2].page_location,
          'https://chendermatologist.com/blog/example');
        assert.doesNotMatch(JSON.stringify(commands), /fixture-only|#fixture/);
      } else {
        assert.deepEqual(vendor, [], 'preview and aliases must load no telemetry providers');
        assert.deepEqual(commands, [], 'preview and aliases must queue no telemetry');
        assert.equal(await page.evaluate(() => typeof window.clarity), 'undefined');
      }
    } finally { await context.close(); }
  }
  console.log('Analytics production origin checks passed: ' + cases.length + ' isolated documents');
  return {cases: cases.length, collectorsBlockedBeforeEgress: true};
};
