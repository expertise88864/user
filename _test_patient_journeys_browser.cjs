// Read the real article documents. All requests stay inside a local fixture;
// no author credentials, production collectors or repository writes are used.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const journeys = [
  ['dupilumab-long-term-maintenance', ['patient', 'relapse', 'design'], ['patient', 'relapse', 'design']],
  ['perioral-dermatitis-guide', ['dx', 'when', 'qa'], ['en-dx', 'en-when', 'en-qa']],
  ['topical-acids-patient', ['overview', 'combo', 'start'], ['why-en', 'combine-en', 'howto-en']],
  ['prurigo-nodularis', ['what', 'dx', 'tx'], ['what-en', 'dx-en', 'tx-en']],
  ['tinea-myths', ['tx', 'm3', 'end', 'lt2'], ['tx-en', 'm3-en', 'end-en', 'm2-en']],
  ['skin-biopsy-excision', ['indications', 'postop', 'biopsy-vs-excision'], ['indications-en', 'postop-en', 'biopsy-vs-excision-en']],
];

async function localDocuments(context) {
  const root = process.cwd();
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin !== 'https://patient-journey.test' || request.method() !== 'GET') return route.abort();
    let name = decodeURIComponent(url.pathname).slice(1);
    if (!path.extname(name)) name += '.html';
    // Never let a document fixture expose private files or execute a collector.
    if (name.includes('\\') || name.split('/').includes('..') ||
        !/^(?:en\/blog\/|blog\/|assets\/)/.test(name) ||
        name === 'assets/inline/analytics-loader.js') return route.abort();
    const file = path.resolve(root, name);
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      return route.fulfill({status:404, body:''});
    }
    const contentType = {'.html':'text/html; charset=utf-8', '.js':'application/javascript',
      '.css':'text/css', '.svg':'image/svg+xml', '.json':'application/json',
      '.png':'image/png', '.jpg':'image/jpeg', '.webp':'image/webp', '.woff2':'font/woff2'}[path.extname(file)];
    if (!contentType) return route.abort();
    return route.fulfill({status:200, contentType, body:fs.readFileSync(file)});
  });
}

async function checkPatientJourneys(browser) {
  const results = [];
  for (const javaScriptEnabled of [true, false]) {
    const context = await browser.newContext({javaScriptEnabled, serviceWorkers:'block',
      viewport:{width:390, height:900}, reducedMotion:'reduce'});
    try {
      await localDocuments(context);
      for (const width of [390, 800, 1440]) for (const language of ['zh', 'en']) {
        for (const [slug, zhAnchors, enAnchors] of journeys) {
          const anchors = language === 'en' ? enAnchors : zhAnchors;
          const page = await context.newPage(), errors = [];
          let stage = 'initial';
          page.on('pageerror', error => errors.push({message:error.stack || error.message, stage, url:page.url()}));
          try {
            await page.setViewportSize({width, height:900});
            const address = 'https://patient-journey.test' + (language === 'en' ? '/en' : '') + '/blog/' + slug;
            assert.equal((await page.goto(address, {waitUntil:'load'})).status(), 200);
            const nav = page.locator('#article-quick-links');
            assert.equal(await nav.count(), 1, 'One question entry per article');
            const label = await nav.getAttribute('aria-labelledby');
            assert.ok(label && (await page.locator('#' + label).textContent()).trim(), 'Question entry has a visible name');
            assert.deepEqual(await nav.locator('a').evaluateAll(nodes => nodes.map(node => node.getAttribute('href'))),
              anchors.map(anchor => '#' + anchor), slug + ': preserve the approved question destinations');
            const entry = await nav.boundingBox();
            assert.ok(entry && entry.x >= 0 && entry.x + entry.width <= width + 1,
              'Question entry fits the viewport');
            assert.ok(entry.y >= 0 && entry.y < 900,
              slug + ' ' + language + ' ' + width + ' JS=' + javaScriptEnabled + ': entry begins in the first screen ' + JSON.stringify(entry));
            if (language === 'zh') assert.ok(entry.y + entry.height <= 900,
              'The primary patient-language question links fit in the first screen');
            for (const anchor of anchors) {
              stage = 'question:' + anchor;
              const link = nav.locator('a[href="#' + anchor + '"]');
              assert.ok((await link.textContent()).trim(), 'Question link must retain visible text');
              const target = page.locator('[id="' + anchor + '"]');
              assert.equal(await target.count(), 1, 'Question destination is unique');
              // Focus setup, followed by native keyboard activation: no hash or
              // scrolling is injected, including in the no-JavaScript case.
              await link.focus();
              await page.keyboard.press('Enter');
              await page.waitForURL(address + '#' + anchor);
              await page.waitForFunction(id => {
                const target = document.getElementById(id), rect = target.getBoundingClientRect();
                const header = document.querySelector('header'), h = header?.getBoundingClientRect();
                const boundary = h && getComputedStyle(header).position === 'sticky' ? Math.max(0, h.bottom) : 0;
                return rect.top >= boundary - 1 && rect.bottom <= innerHeight;
              }, anchor);
              assert.ok(await target.isVisible(), 'Native question destination is readable');
            }
            // A bookmarked patient link must work on a fresh document too.
            stage = 'bookmark';
            await page.goto(address + '#' + anchors[0], {waitUntil:'load'});
            assert.ok(await page.locator('[id="' + anchors[0] + '"]').isVisible());
            const related = page.locator('#dn-related-static a.dn-related-card[href]');
            const recommendations = await related.evaluateAll(nodes => nodes.map(node => ({href:node.getAttribute('href'), text:node.textContent.trim()})));
            assert.ok(recommendations.length > 0 && recommendations.every(item => item.text &&
              item.href.startsWith(language === 'en' ? '/en/blog/' : '/blog/')),
            'Existing next-article suggestions retain named native article links');
            const next = new URL(recommendations[0].href, address).href;
            stage = 'next-article';
            await related.first().focus();
            await page.keyboard.press('Enter');
            await page.waitForURL(next);
            assert.ok((await page.locator('h1').textContent()).trim(), 'Next article opens with its visible heading');
            assert.deepEqual(errors, [], slug + ' ' + language + ': article must not throw while following its questions');
            results.push({slug, language, width, javaScriptEnabled, anchors:anchors.length,
              nextArticle:recommendations[0].href, passed:true});
          } finally { await page.close(); }
        }
      }
    } finally { await context.close(); }
  }
  return results;
}

module.exports = checkPatientJourneys;
