// Exact compiled public runtime and real DOM; every destination is intercepted.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');

module.exports = async function checkArticlePrefetch(browser) {
  const staticFixture=JSON.parse(execFileSync('python',['_test_hub_catalog.py','--browser-fixture'],{encoding:'utf8',timeout:15000}));
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
    // WebKit includes the deliberately held dynamic script in the load event.
    // DOM readiness lets us assert the pre-hub state before releasing it.
    await page.goto(origin + '/', {waitUntil:'domcontentloaded'});
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
    await page.goto(origin+'/en/blog/index.html');
    await page.waitForFunction(() => !!window.DN?.bindArticleHub && !!DN.ARTICLES_DESC?.['psoriasis-systemic']);
    const fallback = await page.evaluate(() => {
      const cards = () => Array.from(document.querySelectorAll('a.article-list-item'))
        .filter(card => /\/blog\/psoriasis-systemic\/?$/.test(new URL(card.href).pathname));
      cards().forEach(card => card.remove());
      DN.bindArticleHub();DN.bindArticleHub();DN.applyTextOnly('en');
      return {count:cards().length,text:cards()[0]?.querySelector('p')?.textContent,
        expected:DN.ARTICLES_DESC['psoriasis-systemic'].desc_en};
    });
    assert.equal(fallback.count,1,'A missing public card must be recreated once, including repeat binding');
    assert.equal(fallback.text,fallback.expected,'The recreated card must translate using its generated description');
    assert.doesNotMatch(fallback.text,/&(?:gt|lt|amp|quot);/,'Generated descriptions must not display double-escaped entities');
    const safeText = await page.evaluate(() => {
      const article=DN.ARTICLES.find(row => row.slug==='psoriasis-systemic');
      const payload='<img src="x" onerror="window.__cardInjected=1"> & "quoted"';
      Object.assign(article,{title:'Fixture title',title_en:payload,tag:'Fixture tag',tag_en:payload});
      DN.ARTICLES_DESC[article.slug]={desc:'Fixture description',desc_en:payload};
      document.querySelectorAll('a.article-list-item').forEach(card => {
        if (/\/blog\/psoriasis-systemic\/?$/.test(new URL(card.href).pathname)) card.remove();
      });
      DN.bindArticleHub();DN.applyTextOnly('en');
      const card=Array.from(document.querySelectorAll('a.article-list-item'))
        .find(node => /\/blog\/psoriasis-systemic\/?$/.test(new URL(node.href).pathname));
      const result={payload,title:card.querySelector('h2').textContent,description:card.querySelector('p').textContent,
        tag:card.querySelector('.tag').textContent,images:card.querySelectorAll('img').length,
        injected:!!window.__cardInjected};
      DN.applyTextOnly('zh');result.zhTitle=card.querySelector('h2').textContent;
      card.querySelector('h2').textContent='Custom author wording';
      DN.applyTextOnly('en');result.customTitle=card.querySelector('h2').textContent;
      const popular=document.createElement('ul');popular.id='dn-popular-list';document.body.appendChild(popular);
      DN.POPULAR_PICKS=[article.slug];DN.injectSpotlight();DN.applyTextOnly('en');
      const fields=Array.from(popular.querySelectorAll('[data-dn-text-only]'));
      result.spotlightText=fields.map(node => node.textContent);
      result.spotlightImages=popular.querySelectorAll('img').length;
      return result;
    });
    for (const field of ['title','description','tag']) assert.equal(safeText[field],safeText.payload,
      'Public catalogue strings must remain text through translation');
    assert.equal(safeText.images,0);assert.equal(safeText.injected,false);
    assert.equal(safeText.zhTitle,'Fixture title');
    assert.equal(safeText.customTitle,'Custom author wording','Translation must preserve custom visible wording');
    assert.deepEqual(safeText.spotlightText,[safeText.payload,safeText.payload]);
    assert.equal(safeText.spotlightImages,0,'Spotlight catalogue fields must also remain plain text');
    const staticPage=await context.newPage();
    await staticPage.route('**/*',route => route.abort());
    for (const card of staticFixture.cards) {
      await staticPage.setContent('<html lang="zh-Hant"><body><section id="static-card-fixture">'+card+'</section></body></html>');
      await staticPage.addScriptTag({content:fs.readFileSync('blog/blog-shared.min.js','utf8')});
      const result=await staticPage.evaluate(() => {
        const host=document.querySelector('#static-card-fixture');DN.applyTextOnly('en');
        const title=host.querySelector('h2,h3'),tag=host.querySelector('.tag');
        const result={title:title.textContent,tag:tag?.textContent,
          images:host.querySelectorAll('img').length,injected:!!window.__staticCardInjected};
        DN.applyTextOnly('zh');result.zhTitle=title.textContent;
        title.textContent='Custom static author wording';DN.applyTextOnly('en');result.customTitle=title.textContent;
        return result;
      });
      assert.equal(result.title,staticFixture.payload,'Generated static titles must remain text after language switching');
      if (result.tag !== undefined) assert.equal(result.tag,staticFixture.payload);
      assert.equal(result.images,0);assert.equal(result.injected,false);
      assert.equal(result.zhTitle,'Fixture title');assert.equal(result.customTitle,'Custom static author wording');
    }
    await staticPage.close();
    return {startupHints:0,intentHints:1,compiledRuntime:true,lazyReadingProgress:true,missingCardFallback:true,plainCatalogueTranslation:true,staticPlainCatalogueTranslation:true};
  } finally {await context.close();}
};
