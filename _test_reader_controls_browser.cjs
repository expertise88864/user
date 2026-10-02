// Real reading runtime and native controls; synthetic text/local storage only.
const assert = require('node:assert/strict');
const fs = require('node:fs');
module.exports = async function checkReaderControls(browser, { readingSource } = {}) {
  const source = readingSource || fs.readFileSync('blog/blog-article-reading.js', 'utf8');
  const results = [];
  for (const width of [390,800,1440]) {
    const context = await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});
    try {
      await context.route('**/*', route => {
        const url = new URL(route.request().url());
        if (url.origin !== 'https://reader-controls.test') return route.abort();
        if (url.pathname === '/runtime.js') return route.fulfill({contentType:'application/javascript; charset=utf-8',body:source});
        if (url.pathname !== '/fixture') return route.fulfill({status:404,body:''});
        return route.fulfill({contentType:'text/html; charset=utf-8',body:'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>Isolated reader</title></head><body><details id="dn-reading-settings"><summary>閱讀設定</summary></details><article id="proseZh" class="prose"><h2 id="section">Fixture heading</h2><p>Fixture paragraph</p></article><div style="height:5000px"></div><script src="/runtime.js"></script></body></html>'});
      });
      const page = await context.newPage(), errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto('https://reader-controls.test/fixture');
      assert.deepEqual(errors,[], 'The fixture must load the actual reading runtime before exercising controls');
      await page.evaluate(() => { DN.currentSlug=()=> 'reader-fixture'; DN.addFontSizer(); DN.addFontSizer(); });
      await page.locator('#dn-reading-settings summary').click();
      const large = page.locator('#dn-font-sizer button[data-size="XL"]');
      assert.equal(await page.locator('#dn-font-sizer').count(),1);
      assert.equal(await large.isVisible(),true);
      assert.equal(await large.evaluate(el => getComputedStyle(el.parentElement).opacity),'1');
      assert.equal(await large.evaluate(el => getComputedStyle(el.parentElement).pointerEvents),'auto');
      await large.focus(); await large.press('Enter');
      assert.equal(await large.getAttribute('aria-pressed'),'true');
      assert.equal(await page.locator('#proseZh').evaluate(el => getComputedStyle(el).fontSize),'21px');
      assert.equal(await page.evaluate(()=>localStorage.getItem('dn-font-size')),'XL');
      await page.locator('#dn-font-sizer button[data-size="M"]').click();
      assert.equal(await page.locator('#dn-font-size-style').count(),0);
      await context.addInitScript(() => {
        localStorage.setItem('dn:scroll:reader-fixture', JSON.stringify({y:600,pct:'<img src=x onerror="window.RESTORE_INJECTED=1">',ts:Date.now(),h2:'Fixture'}));
      });
      await page.reload(); await page.evaluate(()=>{ DN.currentSlug=()=> 'reader-fixture'; DN.bindScrollMemory(); });
      await page.waitForTimeout(750);
      assert.equal(await page.locator('#dn-resume-toast').count(),0,'Invalid saved percentage must never become HTML');
      assert.equal(await page.evaluate(()=>window.RESTORE_INJECTED || 0),0);
      // Replace the init script's hostile value only after this new document.
      await page.evaluate(()=>{
        localStorage.setItem('dn:scroll:reader-fixture',JSON.stringify({y:600,pct:35,ts:Date.now(),h2:'<img src=x onerror="bad">'}));
        window.gtag=()=>{throw Error('blocked analytics');};
        DN.bindScrollMemory();
      });
      await page.locator('#dn-resume-toast').waitFor();
      assert.match(await page.locator('#dn-resume-toast').textContent(),/35%/);
      assert.equal(await page.locator('#dn-resume-toast img').count(),0,'Saved heading stays plain text');
      await page.locator('#dn-resume-toast [data-resume-yes]').click();
      await page.waitForFunction(()=>window.scrollY>=500);
      assert.equal(await page.locator('#dn-resume-toast').count(),0);
      assert.deepEqual(errors,[]);
      results.push({width,settingsFontVisibleAndUsable:true,invalidStorageRejected:true,validResumeAndBlockedAnalytics:true});
    } finally { await context.close(); }
  }
  return {cases:results.length,results};
};
