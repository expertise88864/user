// Exact compiled public runtime and real DOM; every destination is intercepted.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async function checkArticlePrefetch(browser) {
  const context = await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'});
  try {
    const page = await context.newPage();
    const origin = 'https://article-prefetch.test';
    let releaseHub;
    const hubReady = new Promise(resolve => {releaseHub = resolve;});
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin !== origin) return route.abort();
      const name = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
      if (name === 'blog/blog-hub.min.js') await hubReady;
      const root = process.cwd(), file = path.resolve(root,name);
      if (!file.startsWith(root+path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return route.fulfill({status:404,body:''});
      const contentType = file.endsWith('.js') ? 'application/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.html') ? 'text/html' : 'application/octet-stream';
      return route.fulfill({contentType,body:fs.readFileSync(file)});
    });
    await page.goto(origin + '/');
    await page.waitForFunction(() => !!window.DN?.prefetchOnIdle);
    const initial = await page.evaluate(() => {
      DN.prefetchOnIdle();
      return document.querySelectorAll('link[rel="prefetch"][as="document"]').length;
    });
    assert.equal(initial,0,'Loading the public homepage must not manually prefetch navigation documents');
    assert.equal(await page.evaluate(() => typeof DN.injectReadProgress),'undefined',
      'The shared runtime must not carry the hub-only reading progress renderer');
    assert.equal(await page.locator('#dn-read-progress').textContent(),'',
      'Reading progress must wait for the actual lazy hub bundle');
    releaseHub();
    await page.waitForFunction(() => !!document.querySelector('#dn-read-progress [data-zh]'));
    // Exercise the fallback independently of each engine's feature availability.
    // Removing only the optional rules tag avoids substituting runtime bytes.
    await page.evaluate(() => {
      document.querySelectorAll('script[type="speculationrules"]').forEach(node => node.remove());
      DN.prefetchOnIdle();
      const host = document.createElement('section');host.id='prefetch-fixture';document.body.appendChild(host);
      for (const href of ['/', '/admin', '/blog/acne-myths?q=private', '/blog/severe-scabies-treatment',
        'https://article-prefetch.test.example.com/blog/acne-myths', '/blog/acne-myths#dx']) {
        const a=document.createElement('a');a.href=href;a.textContent='Fixture article';host.appendChild(a);
        a.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));
      }
    });
    assert.deepEqual(await page.locator('link[rel="prefetch"][as="document"]').evaluateAll(nodes => nodes.map(node => node.href)),
      [origin+'/blog/acne-myths'],'Only an explicit published article intent may create a manual hint');
    await page.evaluate(() => {
      const a=document.querySelector('#prefetch-fixture a:last-child');a.dispatchEvent(new FocusEvent('focusin',{bubbles:true}));
      a.dispatchEvent(new Event('touchstart',{bubbles:true}));
    });
    assert.equal(await page.locator('link[rel="prefetch"][as="document"]').count(),1,'Pointer, keyboard and touch hints must deduplicate');
    assert.equal(new URL(page.url()).pathname,'/','Hints must not navigate or intercept reader clicks');
    // Exercise actual progress clicks after counting hints: native pointer
    // movement over real article cards is itself a legitimate prefetch intent.
    await page.evaluate(() => {
      const draft=DN.ARTICLES.find(article => article.unpublished);
      localStorage.setItem(DN.READ_KEY,JSON.stringify(['acne-myths','acne-myths',draft.slug,'unknown']));
      window.dispatchEvent(new CustomEvent('dn-read-updated'));
    });
    assert.match(await page.locator('#dn-read-progress').textContent(),/已讀 1 篇 \(2%\)/);
    assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem(DN.READ_KEY)).length),4,
      'Filtering public progress must preserve historical reading records');
    page.once('dialog',dialog => dialog.accept());
    await page.locator('#dn-read-reset').click();
    assert.match(await page.locator('#dn-read-progress').textContent(),/已讀 0 篇 \(0%\)/);
    assert.equal(await page.evaluate(() => localStorage.getItem(DN.READ_KEY)),null);
    return {startupHints:0,intentHints:1,compiledRuntime:true,lazyReadingProgress:true};
  } finally {await context.close();}
};
