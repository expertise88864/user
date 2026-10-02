// Actual page markup and shared source; all requests are local fixtures.
// Exercise both lazy bootstrap and already-installed search in both languages.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async function checkNavSearch(browser, {sharedSource} = {}) {
  const root = process.cwd(), results = [];
  for (const helperAvailable of [false,true]) for (const initialized of [false, true]) for (const nativeDialogAvailable of [true,false]) {
    const context = await browser.newContext({serviceWorkers:'block'});
    try {
      await context.addInitScript(nativeDialogAvailable => {
        // Keep the real bootstrap pending until the first click. Do not change
        // source handlers or mock the button/modal behavior under test.
        window.requestIdleCallback = () => 1;
        window.cancelIdleCallback = () => {};
        if (!nativeDialogAvailable) HTMLDialogElement.prototype.showModal = undefined;
      }, nativeDialogAvailable);
      await context.route('**/*', async route => {
        const request = route.request(), url = new URL(request.url());
        if (url.origin !== 'https://nav-search.test' || request.method() !== 'GET') return route.abort();
        // Verify the real catalog fallback when optional search data is absent.
        if (url.pathname.startsWith('/pagefind/') || url.pathname === '/assets/search-index.json') return route.abort();
        // Desktop search must also work if its optional header helper fails.
        // Mobile menu behavior is tested only with its required helper loaded.
        if (!helperAvailable && url.pathname === '/assets/inline/nav-burger.js') return route.abort();
        let name = decodeURIComponent(url.pathname).slice(1);
        if (!name) name = 'index.html';
        if (!path.extname(name)) name += fs.existsSync(path.join(root,name,'index.html')) ? '/index.html' : '.html';
        if (name === 'blog/blog-shared.min.js') name = 'blog/blog-shared.js';
        const file = path.resolve(root,name);
        if (!file.startsWith(root + path.sep) || name.includes('\\') || name.split('/').some(p=>p.startsWith('.')) ||
            !fs.existsSync(file) || !fs.statSync(file).isFile()) return route.fulfill({status:404,body:''});
        const contentType = file.endsWith('.js') ? 'text/javascript' : file.endsWith('.html') ? 'text/html' :
          file.endsWith('.css') ? 'text/css' : 'application/octet-stream';
        const body = name === 'blog/blog-shared.js' && sharedSource !== undefined ? sharedSource : fs.readFileSync(file);
        await route.fulfill({status:200,contentType,body});
      });
      for (const width of helperAvailable ? [390,800,1440] : [1440]) for (const address of ['/en','/','/en/blog','/blog','/en/blog/acne-myths','/blog/acne-myths']) {
        const page = await context.newPage(), errors = [];
        page.on('pageerror',error=>errors.push(error.message));
        try {
          await page.setViewportSize({width,height:900});
          assert.equal((await page.goto('https://nav-search.test'+address,{waitUntil:'load'})).status(),200);
          if (initialized) await page.evaluate(()=>window.DN.initCmdK());
          else assert.equal(await page.locator('#dn-cmdk-overlay').count(),0,'Exercise the actual first-click bootstrap');
          if (width < 900) await page.locator('#dn-nav-burger').click();
          const search = page.locator('#dn-nav-search');
          assert.equal(await search.getAttribute('aria-label'),address.startsWith('/en')?'Search':'搜尋');
          await page.evaluate(()=>{window.navSearchEvents=[]; window.gtag=(...args)=>window.navSearchEvents.push(args);});
          // Click the SVG child to verify delegated target resolution too.
          await search.locator('svg').click();
          assert.equal(await page.locator('#dn-cmdk-overlay').isVisible(),true,address+' '+width+' initialized='+initialized+' helperAvailable='+helperAvailable+': nav click opens search');
          assert.equal(await page.locator('#dn-cmdk-input').evaluate(el=>el===document.activeElement),true);
          const overlay = page.locator('#dn-cmdk-overlay');
          assert.equal(await overlay.getAttribute('role'),'dialog');
          assert.equal(await overlay.getAttribute('aria-modal'),'true');
          assert.equal(await overlay.evaluate(el=>el.tagName==='DIALOG'),nativeDialogAvailable);
          await page.keyboard.press('Shift+Tab');
          assert.equal(await overlay.evaluate(el=>el.contains(document.activeElement)),true,'Reverse Tab stays inside search');
          assert.equal(await page.locator('#dn-cmdk-close').evaluate(el=>el===document.activeElement),true);
          await page.keyboard.press('Tab');
          assert.equal(await page.locator('#dn-cmdk-input').evaluate(el=>el===document.activeElement),true,'Tab wraps to search input');
          await page.evaluate(()=>document.querySelector('a[href]').focus());
          assert.equal(await overlay.evaluate(el=>el.contains(document.activeElement)),true,'Background content cannot take focus');
          assert.equal(await page.evaluate(()=>window.navSearchEvents.filter(args=>args[1]==='site_search_open').length),1,'One open event despite bootstrap + installed handlers');
          await page.locator('#dn-cmdk-input').fill('severe-scabies-treatment');
          // Fuzzy matching may offer other public articles; the draft itself
          // must never appear, even when CSS would otherwise conceal its row.
          assert.equal(await page.locator('#dn-cmdk-results a[href*="severe-scabies-treatment"]').count(),0,'Unpublished article is absent from the actual fallback results, not merely CSS-hidden');
          await page.locator('#dn-cmdk-input').fill('痘痘');
          await page.locator('#dn-cmdk-results a').first().waitFor({state:'visible'});
          // WebKit follows the platform setting that may Tab through form
          // controls only. Focus an actual result to test Escape independently
          // of that setting; the boundary Tab checks above remain mandatory.
          await page.locator('#dn-cmdk-results a').first().focus();
          assert.equal(await page.evaluate(()=>document.activeElement.matches('#dn-cmdk-results a')),true);
          await page.keyboard.press('Escape');
          assert.equal(await page.locator('#dn-cmdk-overlay').isVisible(),false);
          assert.equal(await page.evaluate(()=>document.activeElement.id),width<900?'dn-nav-burger':'dn-nav-search','Closing returns to a visible navigation control');
          if (!(await search.isVisible())) await page.locator('#dn-nav-burger').click();
          await search.click();
          assert.equal(await page.locator('#dn-cmdk-overlay').isVisible(),true,'Installed click handler still works after closing');
          assert.equal(await page.evaluate(()=>window.navSearchEvents.filter(args=>args[1]==='site_search_open').length),2);
          await page.locator('#dn-cmdk-close').click();
          assert.equal(await overlay.isVisible(),false,'Visible close button works without a keyboard');
          assert.equal(await page.evaluate(()=>document.activeElement.id),width<900?'dn-nav-burger':'dn-nav-search');
          if(width<900)await page.locator('#dn-nav-burger').click();
          await search.click();
          await page.mouse.click(5,5);
          assert.equal(await overlay.isVisible(),false,'Background click closes search');
          assert.deepEqual(errors,[],'Search navigation has no page errors');
          results.push({address,width,initialized,helperAvailable,nativeDialogAvailable,passed:true});
        } finally { await page.close(); }
      }
    } finally { await context.close(); }
  }
  return {cases:results.length,results};
};
