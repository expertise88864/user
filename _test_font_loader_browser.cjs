'use strict';
// Isolated native paint fixture; no third-party requests or analytics collectors.
const assert = require('node:assert/strict');
const fs = require('node:fs');

module.exports = async function checkFontLoading(browser) {
  const source = fs.readFileSync('assets/inline/font-loader.js', 'utf8');
  const cases = [
    { name: 'cached-css', delay: 0 },
    { name: 'slow-css', delay: 500 },
    { name: 'missing-paint-observer', delay: 0, unsupported: true },
    { name: 'duplicate-loader', delay: 0, duplicate: true },
    { name: 'failed-css', delay: 0, failed: true },
    { name: 'late-loader', delay: 0, late: true },
  ];
  const results = [];
  for (const scenario of cases) {
    const context = await browser.newContext({ serviceWorkers: 'block' });
    try {
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.origin !== 'https://font-loading.test') return route.abort();
        if (url.pathname === '/optional.css') {
          if (scenario.failed) return route.abort();
          if (scenario.delay) await new Promise(resolve => setTimeout(resolve, scenario.delay));
          return route.fulfill({ contentType: 'text/css', body: '#fixture-text{font-family:Georgia,serif}' });
        }
        if (url.pathname !== '/') return route.fulfill({ status: 404, body: '' });
        // Hide actual content briefly to make early RAF callbacks an inadequate
        // paint signal. Native FCP is measured independently of the tested loader.
        const body = `<!doctype html><html><head><style>body{visibility:hidden}</style>
          <link rel="stylesheet" data-dn-fonts href="/optional.css" media="print">
          <script>
          window.fontProbe={writes:[],paints:[],reveal:null};
          const fontLink=document.querySelector('link[data-dn-fonts]');
          new MutationObserver(records=>{
            for(const record of records) if(record.attributeName==='media')
              fontProbe.writes.push({media:fontLink.media,time:performance.now()});
          }).observe(fontLink,{attributes:true});
          try { new PerformanceObserver(list=>fontProbe.paints.push(...list.getEntries()
            .map(entry=>({name:entry.name,time:entry.startTime})))).observe({type:'paint',buffered:true}); } catch(_) {}
          ${scenario.unsupported ? 'window.PerformanceObserver=undefined;' : ''}
          ${scenario.late ? '' : source}
          ${scenario.duplicate ? source : ''}
          window.addEventListener('load',()=>setTimeout(()=>{
            document.body.style.visibility='visible';fontProbe.reveal=performance.now();
          },150),{once:true});
          </script></head><body><p id="fixture-text">Existing readable fixture text</p></body></html>`;
        return route.fulfill({ contentType: 'text/html', body });
      });
      await page.goto('https://font-loading.test/');
      await page.waitForFunction(() => window.fontProbe.reveal !== null);
      if (scenario.late) {
        // Allow native rendering before installing the actual loader.
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        await page.addScriptTag({ content: source });
      }
      if (scenario.failed) {
        await page.waitForTimeout(2300);
        assert.equal(await page.locator('link[data-dn-fonts]').getAttribute('media'), 'print');
      } else {
        await page.waitForFunction(() => document.querySelector('link[data-dn-fonts]').media === 'all');
        await page.waitForFunction(() => getComputedStyle(document.getElementById('fixture-text')).fontFamily.includes('Georgia'));
        assert.match(await page.locator('#fixture-text').evaluate(el => getComputedStyle(el).fontFamily), /Georgia/);
      }
      const probe = await page.evaluate(() => window.fontProbe);
      const fcp = probe.paints.find(entry => entry.name === 'first-contentful-paint');
      assert.equal(await page.locator('#fixture-text').textContent(), 'Existing readable fixture text');
      assert.equal(await page.locator('#fixture-text').evaluate(el => getComputedStyle(el).visibility), 'visible');
      assert.deepEqual(errors, []);
      assert.equal(probe.writes.length, scenario.failed ? 0 : 1, scenario.name);
      if (!scenario.failed) {
        assert.ok(probe.writes[0].time >= probe.reveal, `${scenario.name}: optional CSS must follow visible text`);
        if (fcp && !scenario.unsupported)
          assert.ok(probe.writes[0].time >= fcp.time, `${scenario.name}: optional CSS must follow actual FCP`);
      }
      results.push({ scenario: scenario.name, nativePaintReported: Boolean(fcp), ...probe });
    } finally { await context.close(); }
  }
  return results;
};
