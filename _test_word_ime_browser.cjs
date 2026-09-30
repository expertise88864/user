// Native Chromium IME and production model; external requests blocked.
const fs=require('node:fs'),assert=require('node:assert/strict');
module.exports=async function checkWordIme(browser){
 const context=await browser.newContext({serviceWorkers:'block'});
 try{
  const page=await context.newPage();await page.route('**/*',route=>route.abort());
  await page.setContent('<div id="pilot"></div>');await page.addScriptTag({content:fs.readFileSync('admin/word-model.bundle.js','utf8')});
  const source='<h2 id="diagnostic" data-zh="標題" data-en="Title">標題</h2><p>原段落</p><svg id="keep"><path d="M0 0"/></svg>';
  await page.evaluate(source=>{window.imeSource=source;window.imeEvents=[];window.pilot=DNWordModel.createEditor(document.getElementById('pilot'),source);for(const name of ['compositionstart','compositionupdate','compositionend','beforeinput','input'])pilot.view.dom.addEventListener(name,event=>imeEvents.push({type:name,data:event.data,inputType:event.inputType}));},source);
  await page.locator('.ProseMirror h2').click();await page.keyboard.press('End');
  const cdp=await page.context().newCDPSession(page);
  await cdp.send('Input.imeSetComposition',{text:'ㄓㄨㄥ',selectionStart:3,selectionEnd:3});
  await page.waitForFunction(()=>pilot.view.composing);
  const composing=await page.evaluate(()=>{
   const before=pilot.view.state.doc;let blocked=false,pasteBlocked=false;
   try{pilot.serialize();}catch(error){blocked=/輸入|composition/i.test(error.message);}
   try{pilot.pasteHTML('<p>另貼文字</p>');}catch(error){pasteBlocked=/輸入/i.test(error.message);}
   const data=new DataTransfer();data.setData('text/html','<p>事件貼上文字</p>');
   const event=new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true});
   const handled=pilot.view.someProp('handlePaste',handler=>handler(pilot.view,event));
   return {composing:pilot.view.composing,uncommittedSnapshotBlocked:blocked,
    programmaticPasteBlocked:pasteBlocked&&pilot.view.state.doc.eq(before),
    pasteHookPreservesComposition:handled===true&&pilot.view.state.doc.eq(before)&&/選字/.test(document.getElementById('pilot').dataset.pasteError||'')};
  });
  await cdp.send('Input.insertText',{text:'中文輸入'});
  await page.waitForFunction(()=>!pilot.view.composing&&pilot.view.state.doc.textContent.includes('中文輸入'));
  const committed=await page.evaluate(()=>{
   const html=pilot.serialize(),head=new DOMParser().parseFromString(html,'text/html').querySelector('h2');
   window.imeCommitted=html;
   return {nativeCompositionEvents:imeEvents.some(e=>e.type==='compositionstart')&&imeEvents.some(e=>e.type==='compositionend'),
    chineseCommittedOnce:head.textContent==='標題中文輸入',zhUpdated:head.dataset.zh===head.textContent,
    englishInvalidated:!head.hasAttribute('data-en')&&head.dataset.translationPending==='true',
    rawSvgPreserved:html.includes('<svg id="keep"><path d="M0 0"/></svg>')};
  });
  const history=await page.evaluate(()=>({undo:pilot.undo()&&pilot.serialize()===imeSource,redo:pilot.redo()&&pilot.serialize()===imeCommitted}));
  await page.locator('.ProseMirror h2').click();await page.keyboard.press('End');
  await cdp.send('Input.imeSetComposition',{text:'取消文字',selectionStart:4,selectionEnd:4});
  await page.waitForFunction(()=>pilot.view.composing);
  await cdp.send('Input.imeSetComposition',{text:'',selectionStart:0,selectionEnd:0});
  await page.waitForFunction(()=>!pilot.view.composing);
  const cancelled=await page.evaluate(()=>({cancelledCompositionPreservesCommitted:pilot.serialize()===imeCommitted}));
  const result={...composing,...committed,...history,...cancelled};
  console.log('Native Chromium IME checks passed:',Object.keys(result).length);
  for(const [name,value] of Object.entries(result))assert.equal(value,true,name);
  await page.evaluate(()=>pilot.destroy());await page.close();

 }finally{await context.close();}
};
