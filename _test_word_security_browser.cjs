// Real editor DOM and attempted requests; never contact an external collector.
const assert = require('node:assert/strict');
const fs = require('node:fs');

module.exports = async function checkWordSecurity(browser) {
  const context = await browser.newContext({serviceWorkers:'block'});
  const attempts=[];
  try {
    const page=await context.newPage();
    await page.route('**/*',route=>{
      const url=route.request().url();
      if(url==='https://word-security.test/')return route.fulfill({contentType:'text/html',body:'<!doctype html><main id="editor"></main>'});
      attempts.push(url);return route.abort();
    });
    await page.goto('https://word-security.test/');
    await page.addScriptTag({content:fs.readFileSync('admin/word-model.bundle.js','utf8')});
    const unsafe=[
      '<p style="background-image:url(https://sink-leak.test/image)">CSS image</p>',
      '<p style="background-image:u\\72l(https://sink-leak.test/escaped)">Escaped CSS</p>',
      '<p style="background-image:image-set(\'https://sink-leak.test/image-set\' 1x)">CSS image set</p>',
      '<p style="behavior:url(https://sink-leak.test/behavior)">Behavior</p>',
      '<p style="-moz-binding:url(https://sink-leak.test/binding)">Binding</p>',
      '<p><a href="javascript:window.WORD_UNSAFE=1">JavaScript</a></p>',
      '<p><a href="java&#9;script:window.WORD_UNSAFE=1">Control character</a></p>',
      '<p><a href="data:text/html,unsafe">Data document</a></p>',
      '<p><a href="vbscript:unsafe">Legacy script</a></p>',
      '<p><a href="/blog" ping="https://sink-leak.test/ping">Ping</a></p>',
      '<p><img src="data:image/svg+xml,unsafe" alt="Original"></p>',
      '<p><img src="/safe.png" srcset="https://sink-leak.test/srcset 1x" alt="Original"></p>',
      '<p autofocus contenteditable="true" id="authPane">Clobber</p>',
      '<div data-pilot-protected="forged">Reserved editor marker</div>',
      '<table><tbody><tr><td style="background:url(https://sink-leak.test/table)">Table</td></tr></tbody></table>',
      '<table background="https://sink-leak.test/legacy-background"><tbody><tr><td>Table</td></tr></tbody></table>',
      '<ul><li><a href="javascript:unsafe">Nested list</a></li></ul>',
      '<p onclick="window.WORD_UNSAFE=1">Event</p>',
      '<script>window.WORD_UNSAFE=1</script>',
      '<svg onload="window.WORD_UNSAFE=1"><text>Original</text></svg>',
    ];
    const results=[];
    for(const source of unsafe)results.push(await page.evaluate(source=>{
      const mount=document.getElementById('editor');mount.replaceChildren();
      try {
        const input='<p>Before</p>'+source+'<p>After</p>';
        const model=DNWordModel.createEditor(mount,input);
        const protectedOriginal=[...model.protectedSource.values()].some(raw=>raw.length>0&&source.includes(raw));
        const exact=model.serialize()===input;
        model.insert('EDIT');
        const retained=model.serialize().includes(source);
        const unsafeLive=[...model.view.dom.querySelectorAll('*')].some(el=>[...el.attributes].some(a=>
          /^on/i.test(a.name)||['background','ping','srcset','autofocus'].includes(a.name)||
          ['href','src'].includes(a.name)&&/^(?:javascript|vbscript|data):/i.test(a.value.replace(/[\s\x00-\x1f]/g,''))||
          a.name==='style'&&/(?:url|image(?:-set)?)\s*\(|\\|behavior\s*:|-moz-binding\s*:/i.test(a.value)));
        const result={protectedOriginal,exact,retained,unsafeLive,executed:window.WORD_UNSAFE!==undefined};
        model.destroy();return result;
      } catch(error){return {error:error.message};}
    },source));
    const dropResult=await page.evaluate(()=>{
      const mount=document.getElementById('editor');mount.replaceChildren();
      const original='<p>Original drop content</p>',model=DNWordModel.createEditor(mount,original);
      let parsedHTML=0;
      model.view.setProps({transformPastedHTML(html){parsedHTML++;return html;}});
      const data=new DataTransfer();data.setData('text/html','<p style="background-image:url(https://sink-leak.test/drop)"><img src="https://sink-leak.test/drop-image">Drop</p>');
      const box=model.view.dom.getBoundingClientRect();
      const event=new DragEvent('drop',{dataTransfer:data,bubbles:true,cancelable:true,clientX:box.left+4,clientY:box.top+4});
      Object.defineProperty(event,'dataTransfer',{value:data});
      model.view.dom.dispatchEvent(event);
      const result={parsedHTML,prevented:event.defaultPrevented,retained:model.serialize()===original,notice:!!mount.dataset.pasteError};
      model.destroy();return result;
    });
    const pasteResults=[];
    for(const source of unsafe)pasteResults.push(await page.evaluate(source=>{
      const mount=document.getElementById('editor');mount.replaceChildren();
      const model=DNWordModel.createEditor(mount,'<p>Original</p>');
      const clipboard=new DataTransfer();clipboard.setData('text/html',source);
      const event=new ClipboardEvent('paste',{clipboardData:clipboard,bubbles:true,cancelable:true});
      // Firefox ignores the ClipboardEvent initializer's data for synthetic
      // events. Supply the fixture explicitly, and assert it before dispatch.
      Object.defineProperty(event,'clipboardData',{value:clipboard});
      if(event.clipboardData.getData('text/html')!==source)throw Error('Clipboard fixture lost HTML');
      model.view.dom.dispatchEvent(event);
      const output=model.serialize();
      const result={handled:event.defaultPrevented,originalRetained:output.includes('Original'),
        unsafeLive:!!model.view.dom.querySelector('[background],[style],[onclick],[srcset],[ping],script,svg,img'),
        badLink:[...model.view.dom.querySelectorAll('a[href]')].some(el=>/^(?:javascript|data|vbscript):/i.test(el.getAttribute('href').replace(/[\s\x00-\x1f]/g,''))),
        executed:window.WORD_UNSAFE!==undefined};
      model.destroy();return result;
    },source));
    // Let browser rendering expose CSS/image requests while every destination
    // remains aborted by the route above.
    await page.screenshot();
    assert.deepEqual(attempts,[],'Source must not trigger active CSS/image network requests in the editor');
    assert.deepEqual(dropResult,{parsedHTML:0,prevented:true,retained:true,notice:true},'Drop must be blocked before vendor clipboard HTML parsing');
    for(const [i,result]of results.entries()) {
      assert.equal(result.error,undefined,unsafe[i]);
      assert.equal(result.protectedOriginal,true,unsafe[i]);
      assert.equal(result.exact,true,unsafe[i]);
      assert.equal(result.retained,true,unsafe[i]);
      assert.equal(result.unsafeLive,false,unsafe[i]);
      assert.equal(result.executed,false,unsafe[i]);
    }
    for(const [i,result]of pasteResults.entries()) {
      assert.equal(result.handled,true,unsafe[i]);
      assert.equal(result.originalRetained,true,unsafe[i]);
      assert.equal(result.unsafeLive,false,unsafe[i]);
      assert.equal(result.badLink,false,unsafe[i]);
      assert.equal(result.executed,false,unsafe[i]);
    }
    console.log(JSON.stringify({wordSecuritySources:results.length,nativePasteCases:pasteResults.length,externalAttempts:attempts.length}));
  } finally {await context.close();}
};
