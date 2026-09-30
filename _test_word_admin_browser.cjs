// Actual admin + production Word bundle. No real credentials, collectors or writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async function checkWordAdmin(browser, options = {}) {
  for (const width of [390,800,1440]) {
    const context = await browser.newContext({viewport:{width,height:1100},serviceWorkers:'block'});
    const HEAD='a'.repeat(40), BASE='b'.repeat(40), BLOB='c'.repeat(40), NEXT='d'.repeat(40);
    const source='<!doctype html><html lang="zh-Hant"><head><title>Fixture</title></head><body><header>Immutable header 😀</header><div id="proseZh"><p id="intro">原稿文字</p><section id="semantic"><h2>小標</h2><p>保留 section</p></section><svg id="art"><path d="M0 0"/></svg><script>window.CLINICAL_RUN=1</script></div><div id="proseEn">English remains</div><footer>Immutable footer</footer></body></html>';
    let head=HEAD, accepted=source, releaseSave, rejectBundle=true, failRead=false;
    const writes=[], externalWrites=[];
    try {
      const page=await context.newPage();
      await page.addInitScript(()=>{
        sessionStorage.setItem('cd_gh_pat','fixture-only-not-a-real-token');
        sessionStorage.setItem('cd_gh_pat_exp',String(Date.now()+600000));
      });
      await page.route('**/*',async route=>{
        const request=route.request(),url=new URL(request.url());
        if(url.origin==='https://api.github.com') {
          if(request.method()!=='GET'){externalWrites.push(request.url());return route.abort();}
          return route.fulfill({json:[]});
        }
        if(url.origin!=='https://word-admin.test')return route.abort();
        if(url.pathname==='/api/admin/login')return route.fulfill({json:{ok:true,login:'expertise88864'}});
        if(url.pathname==='/api/admin/article-draft') {
          if(request.method()==='GET') {
            if(failRead){failRead=false;return route.fulfill({status:503,json:{error:'draft_unavailable'}});}
            if(url.searchParams.get('mode')==='list')return route.fulfill({json:{drafts:[],nextOffset:null,unsupportedRefs:0}});
            return route.fulfill({json:{file:'blog/example.html',head,baseSha:BASE,blobSha:BLOB,content:accepted,media:[],legacy:false,conflict:false,request:null}});
          }
          const body=request.postDataJSON();writes.push(body);
          assert.equal(body.file,'blog/example.html');assert.equal(body.expectedHead,HEAD);assert.equal(body.baseSha,BASE);
          await new Promise(resolve=>{releaseSave=resolve;});
          accepted=body.content;head=NEXT;
          return route.fulfill({json:{file:body.file,head,baseSha:BASE,blobSha:BLOB,verified:true,published:false,status:'cloud_draft'}});
        }
        if(request.method()!=='GET'){externalWrites.push(request.url());return route.abort();}
        if(url.pathname==='/admin/word-model.bundle.js'&&rejectBundle){rejectBundle=false;return route.fulfill({status:503,body:'temporarily unavailable'});}
        const root=process.cwd(),file=path.resolve(root,'.'+url.pathname);
        if(!file.startsWith(root+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile())return route.fulfill({status:404,body:''});
        return route.fulfill({contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html',body:fs.readFileSync(file)});
      });
      await page.goto('https://word-admin.test/admin.html');
      await page.waitForFunction(()=>!!window.DNWordEditor);
      assert.equal(await page.evaluate(()=>loadFile('blog/example.html')),true);
      await page.frameLocator('iframe.editor').locator('#proseZh[data-cd-editable]').waitFor();
      await page.locator('#wordEditBtn').click();
      await page.waitForFunction(()=>!document.getElementById('wordEditBtn').disabled);
      assert.equal(await page.evaluate(()=>DNWordEditor.active()),false,'failed lazy load must preserve original editor');
      assert.equal(await page.evaluate(()=>CURRENT_CONTENT),source,'failed lazy load leaves exact loaded source intact');
      await page.locator('#wordEditBtn').click();
      await page.locator('.word-document .ProseMirror').waitFor();
      assert.equal(await page.evaluate(()=>DNWordEditor.active()),true);
      assert.equal(await page.evaluate(()=>getCurrentEditorContent()),source,'opening Word mode preserves exact full source');
      assert.equal(await page.evaluate(()=>window.CLINICAL_RUN),undefined,'protected script must never execute');
      assert.ok(await page.locator('#metaBtn').isDisabled());
      assert.ok(await page.locator('#axDictRun').isDisabled(),'legacy helper must not mutate the hidden preview in Word mode');
      await page.evaluate(()=>{document.getElementById('axBodySize').value='17px';document.getElementById('axFontApply').click();});
      const fontDraft=await page.evaluate(()=>JSON.parse(localStorage.getItem('cd_admin_settings_draft_font')));
      assert.equal(fontDraft.bodySize,'17px');assert.equal(fontDraft.version,1);assert.equal(fontDraft.kind,'font');
      await page.evaluate(base=>{
        const list=document.getElementById('axReorderList');list.replaceChildren();
        for(const slug of ['second','first']){const item=document.createElement('li');item.dataset.slug=slug;list.appendChild(item);}
        document.getElementById('axReorderSave')._sha=base;document.getElementById('axReorderSave').click();
      },BASE);
      const orderDraft=await page.evaluate(()=>JSON.parse(localStorage.getItem('cd_admin_settings_draft_reorder')));
      assert.deepEqual(orderDraft.order,['second','first']);assert.equal(orderDraft.baseSha,BASE);assert.equal(orderDraft.kind,'reorder');
      const editor=page.locator('.word-document .ProseMirror');
      await editor.locator('#intro').click();await editor.press('End');await editor.pressSequentially(' Word編輯');
      await page.locator('#boldBtn').click();await editor.pressSequentially('粗體');
      const gif=Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7','base64');
      await page.locator('#imageInput').setInputFiles([{name:'one.gif',mimeType:'image/gif',buffer:gif},{name:'two.gif',mimeType:'image/gif',buffer:gif}]);
      await editor.locator('img[src]').first().waitFor();
      await page.waitForFunction(()=>!DNWordEditor.status().pastePending);
      assert.equal(await editor.locator('img[src]').count(),2,'multiple image positions remain even when bytes deduplicate');
      assert.equal(await editor.locator('.ProseMirror-separator').evaluateAll(nodes=>nodes.every(node=>node.getBoundingClientRect().width===0&&node.getBoundingClientRect().height===0)),true,'upstream editor separators must not inflate image paragraphs');
      assert.equal(await page.evaluate(()=>DNArticleDrafts.localState(CURRENT_FILE).media.length),1);
      assert.match(await editor.locator('img[src]').first().getAttribute('src'),/^data:image\/gif;base64,/);
      await page.getByRole('button',{name:'圖片說明／排序',exact:true}).click();
      await page.locator('.word-image-row input').first().fill('第一張圖片');
      await page.locator('.word-image-row').first().getByRole('button',{name:'套用說明'}).click();
      assert.equal(await editor.locator('img[src]').first().getAttribute('alt'),'第一張圖片');
      const frozen=await page.evaluate(()=>getCurrentEditorContent());
      assert.ok(frozen.includes('<strong>'));assert.ok(frozen.includes('Word編輯'));
      assert.ok(frozen.includes('<section id="semantic">'));assert.ok(frozen.includes('<svg id="art"><path d="M0 0"/></svg>'));
      assert.ok(frozen.includes('<script>window.CLINICAL_RUN=1</script>'));assert.ok(frozen.includes('<div id="proseEn">English remains</div>'));
      assert.ok(!frozen.includes('src="data:'));assert.equal(writes.length,0,'formatting, images and alt text remain local');
      const overflow=await page.locator('.word-editor-panel').evaluate(element=>element.scrollWidth>element.clientWidth+2);
      assert.equal(overflow,false,'Word pane must fit '+width+'px viewport');
      assert.equal(await page.locator('.word-editor-panel').evaluate(element=>{
        const host=element.parentElement.getBoundingClientRect(),panel=element.getBoundingClientRect();
        return getComputedStyle(element).overflowY==='auto'&&panel.top>=host.top-1&&panel.bottom<=host.bottom+1;
      }),true,'long documents must scroll inside the fixed editor pane, including mobile');
      if(options.capture)await options.capture(page,width);
      page.once('dialog',dialog=>dialog.accept());failRead=true;
      assert.equal(await page.evaluate(()=>loadFile('blog/example.html')),false);
      assert.equal(await page.evaluate(()=>getCurrentEditorContent()),frozen,'failed article load keeps the surviving Word editor recoverable');
      const saving=page.evaluate(()=>DNEditorDraftBridge.save());
      await page.waitForFunction(()=>SAVE_PENDING);
      await editor.locator('#intro').click();await editor.press('End');await editor.pressSequentially(' 存檔中繼續編輯');
      releaseSave();await saving;
      assert.equal(writes.length,1);assert.equal(writes[0].content,frozen);assert.equal(writes[0].media.length,1);
      assert.ok(await page.evaluate(()=>getCurrentEditorContent().includes('存檔中繼續編輯')));
      assert.equal(await page.evaluate(()=>DIRTY),true,'typing during save remains dirty');
      const recovery=await page.evaluate(()=>JSON.parse(localStorage.getItem('cd_admin_draft_blog/example.html')));
      assert.ok(recovery.content.includes('存檔中繼續編輯'));assert.equal(recovery.draft.media.length,1);
      await page.locator('#sourceBtn').click();
      assert.equal(await page.evaluate(()=>DNWordEditor.active()),false);assert.ok(await page.locator('textarea.source').inputValue().then(value=>value.includes('存檔中繼續編輯')));
      assert.equal(await page.locator('#metaBtn').isDisabled(),false,'leaving Word mode restores existing controls');
      assert.equal(await page.locator('#axDictRun').isDisabled(),false);
      const afterSave=await page.locator('textarea.source').inputValue();
      await page.locator('#wordEditBtn').click();await page.locator('.word-document .ProseMirror').waitFor();
      assert.equal(await page.evaluate(()=>getCurrentEditorContent()),afterSave,'dirty source mode can re-enter Word without losing protected bytes');
      assert.deepEqual(externalWrites,[],'editor must not write GitHub/main directly');
      console.log('Actual Word admin flow passed at '+width+'px');
    } finally {await context.close();}
  }
};
