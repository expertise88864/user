// Exact generated documents; isolated transport blocks every external collector.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const pairs=[['/en','/'],['/en/blog','/blog'],['/en/tools','/tools'],['/en/glossary','/glossary'],
 ['/en/blog/perioral-dermatitis-guide','/blog/perioral-dermatitis-guide'],
 ['/en/blog/dupilumab-long-term-maintenance','/blog/dupilumab-long-term-maintenance']];
async function checkEnglishReturn(browser) {
 const origin='https://en-return.test',root=process.cwd(),results=[];
 for(const javaScriptEnabled of [true,false]) {
  const context=await browser.newContext({javaScriptEnabled,serviceWorkers:'block',reducedMotion:'reduce'});
  try {
   await context.route('**/*',route=>{
    const u=new URL(route.request().url());if(u.origin!==origin||route.request().method()!=='GET')return route.abort();
    let name=decodeURIComponent(u.pathname).slice(1);
    if(!name)name='index.html';else if(['en','blog','en/blog'].includes(name))name+='/index.html';else if(!path.extname(name))name+='.html';
    if(name.includes('\\')||name.split('/').includes('..')||! /^(?:en\/|blog\/|assets\/|index\.html$|tools\.html$|glossary\.html$)/.test(name)||name==='assets/inline/analytics-loader.js')return route.abort();
    const file=path.resolve(root,name);if(!file.startsWith(root+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile())return route.fulfill({status:404,body:''});
    const contentType={'.html':'text/html; charset=utf-8','.js':'application/javascript','.css':'text/css','.svg':'image/svg+xml','.json':'application/json','.webp':'image/webp','.png':'image/png','.woff2':'font/woff2','.ico':'image/x-icon'}[path.extname(file)];
    return contentType?route.fulfill({status:200,contentType,body:fs.readFileSync(file)}):route.abort();
   });
   for(const width of [390,800,1440]) for(const [en,zh] of pairs) {
    const page=await context.newPage();await page.setViewportSize({width,height:900});
    try {
     await page.goto(origin+en+'?from=locale-test#dn-en-banner',{waitUntil:'load'});
     const link=page.locator('#dn-en-banner-zh');assert.equal(await link.count(),1);
     const skip=page.locator('a[href="#main-content"]').first();
     const fragment=await skip.count()?'#main-content':'#kp';
     if(await skip.count()) {await skip.focus();await skip.press('Enter');}
     else {await page.goto(origin+en+'?from=locale-test'+fragment,{waitUntil:'load'});assert.ok(await page.locator(fragment).isVisible());}
     await page.waitForURL(u=>u.hash===fragment);
     await link.click();await page.waitForURL(u=>u.pathname===zh);
     const destination=new URL(page.url());assert.equal(destination.pathname,zh);
     if(javaScriptEnabled){assert.equal(destination.search,'?from=locale-test');assert.equal(destination.hash,fragment);assert.ok(await page.locator(fragment).isVisible());}
     assert.ok(await page.locator('main').isVisible());
     if(javaScriptEnabled&&en.endsWith('/perioral-dermatitis-guide')) {
      await page.goto(origin+en+'?from=locale-test#en-dx',{waitUntil:'load'});
      await page.locator('#dn-en-banner-zh').click();await page.waitForURL(u=>u.pathname===zh&&u.hash==='#dx');
      assert.ok(await page.locator('#dx').isVisible(),'The translated anchor must target the primary Chinese prose');
     }
     results.push({en,zh,width,javaScriptEnabled,passed:true,queryAndFragmentPreserved:javaScriptEnabled,staticFallbackWorks:!javaScriptEnabled,fragment,keyboardSkipPresent:fragment==='#main-content'});
    } finally {await page.close();}
   }
  } finally {await context.close();}
 }
 return {cases:results.length,results};
}
module.exports=checkEnglishReturn;
