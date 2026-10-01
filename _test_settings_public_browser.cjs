// Compile actual public sources into isolated responses, then exercise the
// actual runtime. All outbound requests are blocked; no author settings saved.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {execFileSync}=require('node:child_process');

module.exports=async function checkPublicSettings(browser){
 const root=process.cwd(),fixture=JSON.parse(execFileSync('python',['_site_settings_browser_fixture.py'],{encoding:'utf8',timeout:20000,maxBuffer:10000000}));
 const context=await browser.newContext({serviceWorkers:'block'}),results=[];
 try{
  await context.route('**/*',async route=>{
   const request=route.request(),url=new URL(request.url());
   if(url.origin!=='https://public-settings.test'||request.method()!=='GET')return route.abort();
   if(fixture.pages[url.pathname])return route.fulfill({status:200,contentType:'text/html',body:fixture.pages[url.pathname]});
   if(url.pathname==='/assets/dn-below-fold.css')return route.fulfill({status:200,contentType:'text/css',body:fixture.css});
   let name=decodeURIComponent(url.pathname).slice(1);
   if(name==='blog/blog-hub.min.js')name='blog/blog-hub.js';
   if(name==='blog/blog-shared.min.js')name='blog/blog-shared.js';
   const file=path.resolve(root,name);
   if(!file.startsWith(root+path.sep)||name.includes('\\')||name.split('/').some(p=>p.startsWith('.'))||
      !fs.existsSync(file)||!fs.statSync(file).isFile())return route.fulfill({status:404,body:''});
   const contentType=file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'application/octet-stream';
   await route.fulfill({status:200,contentType,body:fs.readFileSync(file)});
  });
  for(const width of [390,800,1440])for(const address of ['/','/blog','/blog/acne-myths']){
   const page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));
   try{
    await page.setViewportSize({width,height:900});
    assert.equal((await page.goto('https://public-settings.test'+address,{waitUntil:'load'})).status(),200);
    const fonts=await page.evaluate(()=>({body:getComputedStyle(document.body).fontFamily,head:getComputedStyle(document.querySelector('h1')).fontFamily}));
    const firstFamily=value=>value.split(',')[0].replace(/["']/g,'').trim();
    assert.equal(firstFamily(fonts.body),'Georgia');assert.equal(firstFamily(fonts.head),'Inter');
    if(address==='/blog/acne-myths'){
     assert.equal(await page.locator('article p').first().evaluate(el=>getComputedStyle(el).fontSize),'18px');
    }else{
     await page.waitForFunction(()=>window.DN&&typeof window.DN.bindArticleHub==='function');
     await page.evaluate(()=>window.DN.bindArticleHub());
     const actual=await page.evaluate(()=>{
      const list=document.querySelector('#dn-article-list,#articleList'),cards=[];
      for(const child of list.children){
       if(child.matches('a.article-list-item'))cards.push(child);
       else if(child.tagName==='TEMPLATE')cards.push(...child.content.querySelectorAll('a.article-list-item'));
      }
      return cards.map(card=>card.getAttribute('href').split('/').pop());
     });
     assert.deepEqual(actual,fixture.order,'Runtime must keep the complete author order and homepage deferred cards');
    }
    assert.deepEqual(errors,[],'Public settings must not break the real page runtime');
    results.push({width,address,passed:true});
   }finally{await page.close();}
  }
 }finally{await context.close();}
 return{cases:results.length,results};
};
