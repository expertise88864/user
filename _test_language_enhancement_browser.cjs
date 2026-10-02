// Delayed enhancements use the real shared runtime and isolated local documents.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async function checkLanguageEnhancements(browser, { sharedSource } = {}) {
  const origin = 'https://language-enhancement.test';
  const root = process.cwd();
  const rows = [];
  let failSupportOnce = false, supportRequests = 0;
  const context = await browser.newContext({ serviceWorkers: 'block', reducedMotion: 'reduce' });
  try {
    // Reproduce an enhancement delayed beyond both language retry timers.
    await context.addInitScript(() => { window.requestIdleCallback = () => 1; });
    await context.route('**/*', route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== origin || request.method() !== 'GET') return route.abort();
      if (url.pathname === '/blog/blog-support.min.js') {
        supportRequests++;
        if (failSupportOnce) { failSupportOnce = false; return route.abort(); }
      }
      let name = decodeURIComponent(url.pathname).slice(1);
      if (!name) name = 'index.html';
      else if (name === 'en') name = 'en/index.html';
      else if (!path.extname(name)) name += '.html';
      if (name.includes('\\') || name.split('/').some(part => part.startsWith('.')) ||
          !/^(?:en\/|blog\/|assets\/)/.test(name) || name === 'assets/inline/analytics-loader.js') return route.abort();
      if (name === 'blog/blog-shared.min.js') name = 'blog/blog-shared.js';
      const file = path.resolve(root, name);
      if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return route.fulfill({ status: 404, body: '' });
      const contentType = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json', '.webp': 'image/webp' }[path.extname(file)];
      if (!contentType) return route.abort();
      return route.fulfill({ status: 200, contentType, body: name === 'blog/blog-shared.js' && sharedSource !== undefined ? sharedSource : fs.readFileSync(file) });
    });
    for (const width of [390, 800, 1440]) {
      for (const address of ['/en/about', '/en/glossary']) {
        const page = await context.newPage();
        try {
          await page.setViewportSize({ width, height: 900 });
          assert.equal((await page.goto(origin + address, { waitUntil: 'load' })).status(), 200);
          await page.waitForTimeout(1700);
          assert.equal(await page.locator('#dn-bmc-footer').count(), 0, 'The optional support UI is deferred');
          if (width === 390 && address === '/en/about') {
            failSupportOnce = true;
            await page.evaluate(() => DN.injectBMC());
            assert.equal(await page.locator('#dn-bmc-footer').count(), 0, 'A failed optional request does not insert partial UI');
          }
          const requestsBefore = supportRequests;
          const firstDisplay = await page.evaluate(async () => {
            const footer = document.querySelector('footer');
            const parent = footer.parentNode, insert = parent.insertBefore;
            let observation;
            parent.insertBefore = function (node, reference) {
              if (node.id === 'dn-bmc-footer') observation = { title: node.querySelector('h3').textContent, href: node.querySelector('[data-bmc-footer-link]').getAttribute('href'), paragraph: node.querySelector('p').textContent };
              return insert.call(this, node, reference);
            };
            try { await Promise.all([DN.injectBMC(), DN.injectBMC()]); } finally { parent.insertBefore = insert; }
            return observation;
          });
          assert.equal(firstDisplay.title, 'Buy me a coffee ☕', 'The English enhancement is translated before its first insertion');
          assert.equal(supportRequests - requestsBefore, 1, 'Concurrent callers share one request; a previous failed request can retry');
          assert.equal(firstDisplay.href, '/en/support', 'The support link preserves the reader language');
          assert.ok(firstDisplay.paragraph.startsWith('No ads, no sponsorships.'));
          assert.equal(await page.locator('#dn-bmc-footer').count(), 1);
          await page.locator('#dn-bmc-footer').scrollIntoViewIfNeeded();
          assert.ok(await page.locator('#dn-bmc-footer h3').isVisible());
          const box = await page.locator('#dn-bmc-footer').boundingBox();
          assert.ok(box.x >= -1 && box.x + box.width <= width + 1);
          const hostileUrl = '/support?note="/><img data-support-injected src=x>';
          const urlResult = await page.evaluate(url => {
            document.getElementById('dn-bmc-footer').remove();
            DN.SUPPORT_URL = url;
            DN.injectSupportUI();
            const card = document.getElementById('dn-bmc-footer');
            return { href: card.querySelector('[data-bmc-footer-link]').getAttribute('href'), injected: card.querySelectorAll('[data-support-injected]').length, paths: Array.from(card.querySelectorAll('svg path'), node => node.getAttribute('d')), lines: card.querySelectorAll('svg line').length };
          }, hostileUrl);
          assert.deepEqual(urlResult, { href: hostileUrl, injected: 0, paths: ['M18 8h1a4 4 0 0 1 0 8h-1', 'M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z'], lines: 3 });
          rows.push({ address, width, lateEnhancementTranslatedBeforeInsertion: true, sameLanguageSupportLink: true, duplicateSuppressed: true, supportUrlCannotInjectHTML: true, originalIconGeometryPreserved: true });
        } finally { await page.close(); }
      }
      const page = await context.newPage();
      try {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(origin + '/en', { waitUntil: 'load' });
        await page.waitForTimeout(1700);
        const scoped = await page.evaluate(() => {
          const sentinel = document.createElement('span');
          sentinel.id = 'translation-outside-scope';
          sentinel.dataset.zh = '範圍以外'; sentinel.dataset.en = 'Outside scope'; sentinel.textContent = '範圍以外';
          document.body.appendChild(sentinel);
          const fragment = document.createDocumentFragment();
          const root = document.createElement('span');
          root.dataset.zh = '根節點'; root.dataset.en = 'Root node'; root.textContent = '根節點';
          fragment.appendChild(root);
          DN.applyTextOnly('en', fragment);
          const element = document.createElement('button');
          element.dataset.zh = '按鈕'; element.dataset.en = 'Button'; element.textContent = '按鈕';
          element.setAttribute('data-en-aria-label', 'Translated label');
          element.setAttribute('data-zh-aria-label', '按鈕標籤');
          DN.applyTextOnly('en', element);
          const literal = document.createElement('span');
          literal.setAttribute('data-dn-text-only', '');
          literal.dataset.zh = '原文'; literal.dataset.en = '<img src=x onerror=alert(1)>'; literal.textContent = '原文';
          DN.applyTextOnly('en', literal);
          const custom = document.createElement('span');
          custom.dataset.zh = '原文'; custom.dataset.en = 'Boilerplate'; custom.innerHTML = '<b>Author edit</b>';
          DN.applyTextOnly('en', custom);
          return { root: root.textContent, element: element.textContent, label: element.getAttribute('aria-label'), literal: literal.textContent, literalImages: literal.querySelectorAll('img').length, custom: custom.innerHTML, outside: sentinel.textContent };
        });
        assert.deepEqual(scoped, { root: 'Root node', element: 'Button', label: 'Translated label', literal: '<img src=x onerror=alert(1)>', literalImages: 0, custom: '<b>Author edit</b>', outside: '範圍以外' });
        await page.evaluate(() => {
          window.translationDocumentScans = 0;
          const query = document.querySelectorAll.bind(document);
          document.querySelectorAll = selector => {
            if (/data-(?:zh|en)/.test(selector)) window.translationDocumentScans++;
            return query(selector);
          };
          const first = document.createElement('span');
          first.id = 'translation-batch-first'; first.dataset.zh = '批次一'; first.dataset.en = 'Batch one'; first.textContent = '批次一';
          document.getElementById('dn-hub').appendChild(first);
          // Arrive after the observer schedules its batch, before it flushes.
          setTimeout(() => {
            const second = document.createElement('span');
            second.id = 'translation-batch-second'; second.dataset.zh = '批次二'; second.dataset.en = 'Batch two'; second.textContent = '批次二';
            const group = document.createElement('div');
            group.id = 'translation-batch-group';
            document.getElementById('dn-hub').appendChild(group);
            group.appendChild(second);
            const label = document.createElement('button');
            label.id = 'translation-batch-label'; label.setAttribute('data-en-aria-label', 'English-only label');
            group.appendChild(label);
          }, 20);
        });
        await page.waitForFunction(() => document.getElementById('translation-batch-second')?.textContent === 'Batch two');
        assert.equal(await page.locator('#translation-batch-first').textContent(), 'Batch one');
        assert.equal(await page.locator('#translation-batch-label').getAttribute('aria-label'), 'English-only label');
        assert.equal(await page.locator('#translation-outside-scope').textContent(), '範圍以外');
        assert.equal(await page.evaluate(() => window.translationDocumentScans), 0, 'An injected subtree must not rescan every bilingual element in the document');
        rows.push({ address: '/en', width, scopedTranslation: true, elementAndFragmentRoots: true, authorMarkupPreserved: true, literalMarkupRemainsText: true, observerSecondBatchPreserved: true, documentTranslationScans: 0 });
      } finally { await page.close(); }
    }
  } finally { await context.close(); }
  return { cases: rows.length, rows };
};
