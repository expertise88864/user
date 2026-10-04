'use strict';
// Actual utility HTML and CSS: catch Tailwind control resets hiding recovery buttons.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

module.exports = async function testRecoveryPages(browser) {
  const root = __dirname;
  const origin = 'https://recovery-pages.invalid';
  const types = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8',
    '.js':'application/javascript; charset=utf-8','.svg':'image/svg+xml','.png':'image/png'};
  const recoveryRoutes = {'/404':'404.html','/offline':'offline.html',
    '/en/missing-recovery-fixture':'404.html','/en/blog/unvisited-recovery-fixture':'offline.html'};
  let cases = 0;
  for (const width of [390, 800, 1440]) {
    const context = await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});
    try {
      await context.route('**/*', async route => {
        const request = route.request(), url = new URL(request.url());
        if (url.origin !== origin || request.method() !== 'GET') {await route.abort();return;}
        const rel = decodeURIComponent(url.pathname).replace(/^\/+/, '');
        if (!recoveryRoutes[url.pathname] && !rel.startsWith('assets/')) {await route.abort();return;}
        const file = path.resolve(root, recoveryRoutes[url.pathname] || rel);
        const fromRoot = path.relative(root,file);
        if (fromRoot.startsWith('..') || path.isAbsolute(fromRoot) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
          await route.abort();return;
        }
        await route.fulfill({status:200,contentType:types[path.extname(file)]||'application/octet-stream',body:fs.readFileSync(file)});
      });
      const page = await context.newPage();
      for (const utility of ['404','offline']) for (const locale of ['zh','en']) {
        const route = locale==='zh' ? '/'+utility : utility==='404' ? '/en/missing-recovery-fixture' : '/en/blog/unvisited-recovery-fixture';
        const prefix = locale==='en' ? '/en' : '';
        // Saved preferences cannot turn a Chinese URL into English or vice versa.
        await context.addCookies([{name:'dn_lang',value:locale==='en'?'zh':'en',url:origin}]);
        await page.goto(origin+route,{waitUntil:'load'});
        assert.equal(await page.locator('html').getAttribute('lang'),locale==='en'?'en':'zh-Hant-TW');
        assert.equal(await page.locator('.skip-to-main').textContent(),locale==='en'?'Skip to main content':'跳至主要內容');
        assert.equal(await page.title(),(utility==='404' ? locale==='en'?'Page not found':'找不到頁面' : locale==='en'?'Offline':'離線中')+' · ChenDermatologist');
        assert.equal(await page.locator('a[href="'+prefix+'/blog"]').count(),1);
        assert.equal(await page.locator('a[href="'+prefix+'/"]').count(),1);
        const button = page.locator(utility==='404' ? 'form button[type="submit"]' : '#retryConnection');
        assert.equal(await button.count(),1);
        const styles = await button.evaluate(el => {
          const s=getComputedStyle(el);
          return {color:s.color,background:s.backgroundColor,image:s.backgroundImage,text:el.textContent.trim()};
        });
        assert(styles.text.length>0);
        assert.equal(styles.image,'none','Recovery label needs a known readable solid background');
        const rgb = value => {
          const match=value.match(/^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/);
          assert(match, 'Contrast calculation requires opaque RGB, got '+value);
          return match.slice(1).map(Number);
        };
        const luminance = color => rgb(color).map(v=>v/255).map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4)
          .reduce((total,v,i)=>total+v*[0.2126,0.7152,0.0722][i],0);
        const a=luminance(styles.color),b=luminance(styles.background);
        const ratio=(Math.max(a,b)+0.05)/(Math.min(a,b)+0.05);
        assert(ratio>=4.5, utility+' '+width+' button contrast '+ratio);
        for (let i=0;i<10 && !(await button.evaluate(el=>el===document.activeElement));i++) await page.keyboard.press('Tab');
        assert(await button.evaluate(el=>el===document.activeElement), 'Keyboard can reach the recovery button');
        assert(await button.evaluate(el=>getComputedStyle(el).outlineStyle!=='none'), 'Keyboard focus remains visible');
        if (utility==='404') {
          assert.equal(styles.text,locale==='en'?'Search':'Google 搜尋');
          assert.equal(await page.getByRole('searchbox').getAttribute('placeholder'),locale==='en'?'Search the site…':'搜尋本站文章…');
          assert.equal(await page.getByRole('searchbox').getAttribute('aria-label'),locale==='en'?'Search the site':'搜尋本站文章 / Search the site','The accessible search name follows the rendered URL locale');
          assert.equal(await page.locator('a[href="mailto:expertise88864@gmail.com"]').count(),1,'Locale changes retain the usable contact link');
          const notice=page.locator('p.mt-10');
          assert.equal(await notice.count(),1);
          assert(await notice.evaluate(el=>parseFloat(getComputedStyle(el).fontSize)>=13.5));
          const color=await notice.evaluate(el=>getComputedStyle(el).color);
          const background=await page.locator('body').evaluate(el=>getComputedStyle(el).backgroundColor);
          const x=luminance(color),y=luminance(background);
          assert((Math.max(x,y)+0.05)/(Math.min(x,y)+0.05)>=4.5, 'Recovery notice contrast');
          const query = 'UI test 中文 & literal=1';
          await page.getByRole('searchbox').fill(query);
          const entries = await page.locator('form').evaluate(form => Array.from(new FormData(form).entries()));
          const params = new URLSearchParams(entries);
          assert.equal(params.getAll('q').length, 0, 'No duplicated Google search parameter');
          assert.deepEqual(params.getAll('as_q'), [query]);
          assert.deepEqual(params.getAll('as_sitesearch'), ['chendermatologist.com']);
          const [request] = await Promise.all([
            context.waitForEvent('request', {predicate: request => {
              const url = new URL(request.url());
              return url.origin === 'https://www.google.com' && url.pathname === '/search';
            }}),
            button.press('Enter'),
          ]);
          const submitted = new URL(request.url());
          assert.equal(request.method(), 'GET');
          assert.deepEqual(submitted.searchParams.getAll('as_q'), [query]);
          assert.deepEqual(submitted.searchParams.getAll('as_sitesearch'), ['chendermatologist.com']);
          // The fixture router aborts every external request, including this
          // harmless query; nothing reaches Google or a real analytics collector.
        } else {
          assert.equal(styles.text,locale==='en'?'↻ Retry connection':'↻ 重新嘗試連線');
          assert.equal(await page.locator('a[href="'+prefix+'/blog/atopic-dermatitis-overview"]').textContent(),'異位性皮膚炎 6 大迷思','Authored medical label remains exact pending separate disposition');
          const navigation = page.waitForNavigation({waitUntil:'load'});
          await page.keyboard.press('Enter');
          await navigation;
          assert.equal(page.url(),origin+route, 'Explicit retry preserves the route while reloading');
        }
        cases++;
      }
    } finally {await context.close();}
  }
  return {cases,isolatedSources:true,vendorTraffic:false,physicalPhoneAcceptance:false};
};
