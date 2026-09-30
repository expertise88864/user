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
    for (const route of ['/blog/acne-myths','/en/blog/acne-myths','/en/blog/dupilumab-long-term-maintenance']) {
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror',error=>errors.push(error.message));
      await page.goto('https://reading.test'+route);
      const badge = page.locator('#dn-reading-meta [data-dn-wordcount]');
      await badge.waitFor({state:'attached'});
      assert.equal(await badge.count(),1,'Word count must exist even when the footer bundle is blocked');
      assert.match(await badge.locator('[data-en]').getAttribute('data-en'),/\d[\d,]* (?:words|characters)/);
      const before = await page.locator('#dn-reading-meta').innerHTML();
      await page.evaluate(() => window.DN.addReadingMeta());
      assert.equal(await page.locator('#dn-reading-meta').innerHTML(),before,'Reinitialization must keep one complete metadata bar');
      assert.deepEqual(errors,[],'Reading metadata must not require locale initialization');
      await page.close();
    }
  } finally { await context.close(); }
};
