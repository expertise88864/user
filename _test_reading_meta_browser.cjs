// Isolated article fixture: no credentials, collectors or repository writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async function checkReadingMetadata(browser) {
  const context = await browser.newContext({viewport:{width:390,height:900},serviceWorkers:'block'});
  try {
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== 'https://reading.test' || request.method() !== 'GET' ||
          url.pathname.includes('blog-article-footer')) return route.abort();
      const root = process.cwd();
      let file = path.resolve(root, '.' + url.pathname);
      if (!path.extname(file) && !fs.existsSync(file)) file += '.html';
      if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
        return route.fulfill({status:404,body:''});
      }
      const contentType = file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' :
        file.endsWith('.html') ? 'text/html' : file.endsWith('.svg') ? 'image/svg+xml' : 'application/octet-stream';
      await route.fulfill({status:200,contentType,body:fs.readFileSync(file)});
    });
    await context.addInitScript(() => {
      Number.prototype.toLocaleString = function () { throw Error('Locale formatter must not be needed for reading metadata'); };
    });
    for (const route of ['/blog/acne-overview','/en/blog/acne-overview','/en/blog/dupilumab-long-term-maintenance']) {
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror',error=>errors.push(error.message));
      await page.goto('https://reading.test'+route);
      // Author decision 2026-11-20: no reading-information bar (number, reading time,
      // author link, word count) above articles; the cover alone stays.
      const hero = page.locator('#dn-secondary-meta #dn-article-hero');
      await hero.waitFor({state:'attached'});
      assert.equal(await hero.count(),1,'The cover stays in the secondary meta panel');
      assert.equal(await page.locator('#dn-reading-meta').count(),0,'No reading-information bar');
      assert.equal(await page.locator('[data-dn-wordcount]').count(),0,'No word-count badge');
      const panel = await page.locator('#dn-secondary-meta').textContent();
      assert.doesNotMatch(panel,/閱讀約|min read|№|封面與閱讀資訊|Cover and reading information/);
      if (route.endsWith('/acne-overview')) assert.match(await hero.innerHTML(),/皮膚科疾病完整介紹/,'Overview covers name the series');
      await page.evaluate(() => window.DN.addReadingMeta());
      assert.equal(await page.locator('#dn-reading-meta').count(),0,'Reinitialization adds no bar');
      assert.deepEqual(errors,[],'Reading metadata must not require locale initialization');
      await page.close();
    }
  } finally { await context.close(); }
};
