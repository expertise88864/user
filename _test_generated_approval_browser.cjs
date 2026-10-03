// Real author confirmation UI with isolated source/API/collectors.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async function checkGeneratedApproval(browser, options = {}) {
  for (const width of [390,800,1440]) {
    const context = await browser.newContext({viewport:{width,height:1100},serviceWorkers:'block'});
    const HEAD='a'.repeat(40), BASE='b'.repeat(40), BLOB='c'.repeat(40), NEXT='9'.repeat(40);
    const FILE='blog/example.html', REVIEW='d'.repeat(40), MANIFEST='e'.repeat(40), DIGEST='f'.repeat(64);
    const origin='https://chendermatologist-fixture00-expertise88864s-projects.vercel.app';
    const contentPaths=[FILE,'en/'+FILE,'ai/example.json','assets/search-index.json','glossary.html','tools.html','index.html'];
    const html='<!doctype html><html lang="zh-Hant"><head><title>Fixture</title></head><body><div id="proseZh"><h1>文章測試</h1><p>非醫療測試原稿</p></div></body></html>';
    const writes=[],externalWrites=[];
    let head=HEAD,failed=false,pause=false,release;
    try {
      const page=await context.newPage();
      await page.addInitScript(()=>{
        sessionStorage.setItem('cd_gh_pat','fixture-only-not-a-real-token');
        sessionStorage.setItem('cd_gh_pat_exp',String(Date.now()+600000));
      });
      page.on('dialog',dialog=>dialog.accept());
      await page.route('**/*',async route=>{
        const request=route.request(),url=new URL(request.url());
        if(url.origin==='https://api.github.com') {
          if(request.method()!=='GET'){externalWrites.push(url.href);return route.abort();}
          return route.fulfill({json:[]});
        }
        if(url.origin!=='https://generated-admin.test')return route.abort();
        if(url.pathname==='/api/admin/login')return route.fulfill({json:{ok:true,login:'expertise88864'}});
        if(url.pathname==='/api/admin/article-draft') {
          if(request.method()==='GET') {
            const mode=url.searchParams.get('mode');
            if(mode==='list')return route.fulfill({json:{drafts:[],nextOffset:null,unsupportedRefs:0}});
            if(mode==='generated') {
              if(pause){pause=false;await new Promise(resolve=>{release=resolve;});}
              if(failed)return route.fulfill({status:409,json:{error:'generated_review_changed'}});
              return route.fulfill({json:{file:FILE,head,baseSha:BASE,blobSha:BLOB,
                reviewHead:REVIEW,manifestBlobSha:MANIFEST,manifestSha256:DIGEST,
                state:'awaiting_generated_content_approval',contentApproved:false,ciVerified:false,published:false,
                contentPaths,removedContentPaths:['blog/retired-fixture.html'],preview:{origin}}});
            }
            return route.fulfill({json:{file:FILE,head,baseSha:BASE,blobSha:BLOB,content:html,
              media:[],legacy:false,conflict:false,request:{status:'awaiting_review'}}});
          }
          const data=request.postDataJSON();writes.push(data);
          assert.equal(data.action,'approve-generated');assert.equal(data.contentApproved,true);
          assert.equal(data.expectedHead,HEAD);assert.equal(data.reviewHead,REVIEW);
          assert.equal(data.manifestBlobSha,MANIFEST);assert.equal(data.manifestSha256,DIGEST);
          assert.equal(data.approvedBy,undefined);head=NEXT;
          return route.fulfill({json:{file:FILE,head,baseSha:BASE,blobSha:BLOB,verified:true,published:false,
            request:{action:'approve-generated',status:'generated_content_approved',blobSha:BLOB,
              reviewHead:REVIEW,manifestBlobSha:MANIFEST,manifestSha256:DIGEST}}});
        }
        if(request.method()!=='GET'){externalWrites.push(url.href);return route.abort();}
        const root=process.cwd(),file=path.resolve(root,'.'+url.pathname);
        if(!file.startsWith(root+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile())return route.fulfill({status:404,body:''});
        return route.fulfill({contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html',body:fs.readFileSync(file)});
      });
      await page.goto('https://generated-admin.test/admin.html');
      await page.waitForFunction(()=>!!window.DNEditorDraftBridge);
      assert.equal(await page.evaluate(()=>loadFile('blog/example.html')),true);
      const button=page.locator('#generatedReviewBtn');
      await button.click();
      const dialog=page.getByRole('dialog',{name:'核可生成內容'});
      await dialog.waitFor();
      const before=await page.evaluate(()=>getCurrentEditorContent());
      assert.equal(await dialog.locator('#requestApproval').isChecked(),false);
      assert.equal(await dialog.locator('a').count(),contentPaths.length);
      for(const label of ['本文中文預覽','本文英文預覽','搜尋結果摘要','詞彙預覽','工具預覽','首頁預覽']) {
        assert.equal(await dialog.getByRole('link',{name:label,exact:true}).count(),1);
      }
      assert.ok((await dialog.innerText()).includes('此版本也會移除以下內容'));
      assert.ok((await dialog.innerText()).includes('blog/retired-fixture.html'));
      assert.equal(await dialog.locator('a[href*="retired-fixture"]').count(),0);
      for(const link of await dialog.locator('a').all()) {
        assert.ok((await link.getAttribute('href')).startsWith(origin+'/'));
        assert.equal(await link.getAttribute('rel'),'noopener noreferrer');
      }
      assert.equal(await page.locator('#saveBtn').evaluate(element=>element.closest('[inert]')!==null),true);
      await dialog.locator('summary').focus();await page.keyboard.press('Shift+Tab');
      assert.equal(await page.evaluate(()=>document.activeElement.id),'requestConfirm');
      await page.keyboard.press('Tab');
      assert.equal(await page.evaluate(()=>document.activeElement.tagName),'SUMMARY');
      await dialog.locator('#requestConfirm').click();
      assert.ok((await dialog.locator('#requestError').innerText()).includes('請先勾選'));
      assert.equal(writes.length,0);
      await page.keyboard.press('Control+s');
      assert.ok((await dialog.locator('#requestError').innerText()).includes('核可視窗'));
      assert.equal(writes.length,0,'An open confirmation cannot trigger a background save');
      if(options.screenshotDir){fs.mkdirSync(options.screenshotDir,{recursive:true});await page.screenshot({path:path.join(options.screenshotDir,width+'.png')});}
      await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});
      assert.equal(await page.evaluate(()=>document.activeElement.id),'generatedReviewBtn');
      assert.equal(await page.locator('#saveBtn').evaluate(element=>element.closest('[inert]')!==null),false);
      assert.equal(await page.evaluate(()=>getCurrentEditorContent()),before);
      failed=true;await button.click();await page.waitForFunction(()=>!document.getElementById('generatedReviewBtn').disabled);
      assert.equal(await page.getByRole('dialog').count(),0);assert.equal(writes.length,0);failed=false;
      pause=true;await button.click();
      await page.waitForFunction(()=>document.getElementById('generatedReviewBtn').disabled);
      while(!release)await new Promise(resolve=>setTimeout(resolve,20));
      await page.frameLocator('iframe.editor').locator('#proseZh p').click();
      await page.keyboard.press('End');await page.keyboard.insertText('新編輯保留');
      release();release=null;
      await page.waitForFunction(()=>!document.getElementById('generatedReviewBtn').disabled);
      assert.equal(await page.getByRole('dialog').count(),0);assert.equal(writes.length,0);
      assert.ok((await page.evaluate(()=>getCurrentEditorContent())).includes('新編輯保留'));
      // Restore through an explicit article reload, then approve the currently
      // displayed complete version. This is synthetic confirmation only.
      assert.equal(await page.evaluate(()=>{clearAutosaveFor(CURRENT_FILE);DIRTY=false;return loadFile('blog/example.html');}),true);
      await button.click();await dialog.waitFor();
      await dialog.locator('#requestApproval').check();await dialog.locator('#requestConfirm').click();
      await dialog.waitFor({state:'detached'});
      assert.equal(writes.length,1);
      assert.equal(await page.evaluate(()=>DNArticleDrafts.localState(CURRENT_FILE).head),NEXT);
      assert.ok((await page.locator('#publicationState').innerText()).includes('等待發布驗證'));
      assert.deepEqual(externalWrites,[]);
      console.log('Actual generated approval UI passed at '+width+'px: unchecked confirmation, Preview links, Tab/Esc/inert/focus, stale read, explicit fixture-only draft request; main writes=0');
    } finally {if(release)release();await context.close();}
  }
};
