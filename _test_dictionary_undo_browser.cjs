// Real dictionary module/native buttons; isolated fixtures, no auth or network.
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');

module.exports=async function checkDictionaryUndo(browser){
 const context=await browser.newContext({viewport:{width:800,height:900},serviceWorkers:'block'});
 const source=fs.readFileSync('admin/admin-extras.js','utf8');
 try{
  for(const scenario of ['ordinary','repeat','later-format','other-article','reload-same-file',
    'replaced-region','changed-tooltip','removed-node','stale-session','changed-controller','no-file','word-active']){
   const page=await context.newPage();await page.route('**/*',route=>route.abort());
   await page.setContent('<!doctype html><html><head></head><body><div id="editorPane"></div><span id="filePath">blog/article-a.html</span><div class="frame-wrap"><iframe class="editor" srcdoc="<html><head></head><body><article><p>EASI Original fixture</p><p>Keep this paragraph</p></article></body></html>"></iframe></div></body></html>');
   await page.evaluate(()=>{
    window.fixtureGeneration=1;
    window.DNEditorDraftBridge={identity:()=>({generation:window.fixtureGeneration}),isCurrent:identity=>identity.generation===window.fixtureGeneration};
   });
   await page.addScriptTag({content:source});
   await page.locator('#axPanel header').click();await page.locator('.ax-tabs button[data-tab="dict"]').click();
   const article=page.frameLocator('iframe.editor').locator('article');
   const original=await article.evaluate(el=>el.innerHTML);
   if(scenario==='no-file')await page.evaluate(()=>document.getElementById('filePath').textContent='尚未選擇檔案');
   if(scenario==='word-active')await page.evaluate(()=>window.DNWordEditor={active:()=>true});
   await page.locator('#axDictRun').click();
   if(['no-file','word-active'].includes(scenario)){
    assert.equal(await article.evaluate(el=>el.innerHTML),original,scenario);await page.close();continue;
   }
   assert.equal(await article.locator('dfn').count(),1,scenario+' first scan');
   if(scenario==='repeat')await page.locator('#axDictRun').click();
   if(scenario==='later-format')await article.evaluate(el=>{
    const doc=el.ownerDocument,node=el.querySelector('dfn'),strong=doc.createElement('strong');
    strong.textContent='EASI Author edited text';node.replaceChildren(strong);
    const p=doc.createElement('p');p.textContent='Later author paragraph';el.append(p);
   });
   if(scenario==='other-article')await page.evaluate(()=>{
    document.getElementById('filePath').textContent='blog/article-b.html';
    const doc=document.querySelector('iframe.editor').contentDocument;doc.querySelector('article').textContent='Keep second article';
   });
   if(scenario==='reload-same-file'){
    await page.locator('iframe.editor').evaluate(frame=>frame.srcdoc='<html><head></head><body><article>Keep new same-file document</article></body></html>');
    await article.getByText('Keep new same-file document',{exact:true}).waitFor();
   }
   if(scenario==='replaced-region')await article.evaluate(el=>{
    const replacement=el.ownerDocument.createElement('article');replacement.textContent='Keep replaced region';el.replaceWith(replacement);
   });
   if(scenario==='changed-tooltip')await article.locator('dfn').evaluate(el=>el.setAttribute('title','Author edited tooltip'));
   if(scenario==='removed-node')await article.locator('dfn').evaluate(el=>el.replaceWith(el.ownerDocument.createTextNode('Author replacement')));
   if(scenario==='stale-session')await page.evaluate(()=>window.fixtureGeneration++);
   if(scenario==='changed-controller')await page.evaluate(()=>window.DNEditorDraftBridge={identity:()=>({}),isCurrent:()=>true});
   const before=await article.evaluate(el=>el.innerHTML);
   let expected=before;
   if(['ordinary','repeat','later-format'].includes(scenario))expected=await article.evaluate(el=>{
    const clone=el.cloneNode(true);clone.querySelector('dfn').replaceWith(...clone.querySelector('dfn').childNodes);return clone.innerHTML;
   });
   await page.locator('#axDictUndo').click();
   assert.equal(await article.evaluate(el=>el.innerHTML),expected,scenario+' must preserve exact unrelated/current authored markup');
   if(['ordinary','repeat'].includes(scenario))assert.equal(expected,original,scenario);
   if(scenario==='later-format')assert.equal(await article.locator('strong').innerText(),'EASI Author edited text');
   await page.close();
  }
  console.log('PASS dictionary undo:12 fixture scenarios preserve later edits, other documents/regions, current session and Word isolation.');
 }finally{await context.close();}
};

if(require.main===module)(async()=>{
 const browser=await require('playwright').chromium.launch();
 try{await module.exports(browser);}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
