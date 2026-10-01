// Isolated CMS fixture: no credentials, external network, or repository writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async function checkEditorSnapshots(browser) {
  const context = await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});
  try {
    const page = await context.newPage();
    await page.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== 'https://editor.test' || request.method() !== 'GET') return route.abort();
      const root = process.cwd(), file = path.resolve(root, '.' + url.pathname);
      if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
        return route.fulfill({status:404,body:''});
      }
      const contentType = file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.html') ? 'text/html' : 'application/octet-stream';
      await route.fulfill({status:200,contentType,body:fs.readFileSync(file)});
    });
    await page.goto('https://editor.test/admin.html');
    await page.locator('#axSeoRefresh').waitFor({state:'attached'});
    await page.evaluate(() => {
      CURRENT_FILE = 'blog/example.html';
      CURRENT_CONTENT = '<html lang="zh-Hant"><head><title>Editor fixture</title></head><body><main><div id="proseZh"><p>Initial</p></div></main></body></html>';
      document.getElementById('filePath').textContent = CURRENT_FILE;
      document.getElementById('patModal').style.display = 'none';
      mountIframe(CURRENT_CONTENT);
      document.getElementById('axPanel').classList.remove('collapsed');
    });
    const editor = page.frameLocator('iframe.editor').locator('[data-cd-editable="1"]');
    await editor.waitFor();
    await page.locator('#axSeoTitle').getByText('Editor fixture',{exact:true}).waitFor();
    await page.waitForFunction(() => document.getElementById('axPanel')._enhanced);
    await page.evaluate(() => document.getElementById('axSeoTitle').textContent='awaiting input check');
    await editor.click();
    await editor.press('End');
    await editor.pressSequentially(' typed');
    const capture = () => editor.evaluate(region => {
      const doc=region.ownerDocument, selection=doc.getSelection();
      window.__caret = {node:selection.anchorNode,offset:selection.anchorOffset,attrs:region.outerHTML};
      window.__mutations = [];
      window.__observer = new MutationObserver(records => window.__mutations.push(...records.map(r=>r.attributeName)));
      window.__observer.observe(region,{attributes:true});
      return doc.activeElement === region;
    });
    assert.equal(await capture(),true,'typing must focus editor');
    await page.locator('#axSeoTitle').getByText('Editor fixture',{exact:true}).waitFor();
    await page.waitForTimeout(850); // Cross the real 600 ms input debounce.
    assert.deepEqual(await editor.evaluate(region => {
      const selection=region.ownerDocument.getSelection(), saved=window.__caret;
      window.__observer.disconnect();
      return {focused:region.ownerDocument.activeElement===region,
        selection:selection.anchorNode===saved.node && selection.anchorOffset===saved.offset,
        unchanged:region.outerHTML===saved.attrs,mutations:window.__mutations};
    }),{focused:true,selection:true,unchanged:true,mutations:[]});
    // Schedule while open, then collapse before the debounce fires.
    await editor.pressSequentially(' pending');
    await page.evaluate(() => {
      document.getElementById('axPanel').classList.add('collapsed');
      document.getElementById('axSeoTitle').textContent='collapsed sentinel';
    });
    await page.waitForTimeout(850);
    assert.equal(await page.locator('#axSeoTitle').textContent(),'collapsed sentinel');
    await editor.pressSequentially(' hidden');
    await page.waitForTimeout(850);
    assert.equal(await page.locator('#axSeoTitle').textContent(),'collapsed sentinel');
    await page.evaluate(() => document.getElementById('axPanel').classList.remove('collapsed'));
    await page.locator('#axSeoTitle').getByText('Editor fixture',{exact:true}).waitFor();
    console.log('PASS CMS caret/selection/attributes survive SEO debounce; collapsed panel skips work and refreshes on reopening.');
    // Actual root editor/controller: undo from A must never enter B's source.
    await page.evaluate(() => {
      CURRENT_FILE='blog/article-a.html';EDITOR_LOAD_ID++;
      CURRENT_CONTENT='<html lang="zh-Hant"><head><title>A</title></head><body><main><article id="proseZh"><p>EASI First fixture</p></article></main></body></html>';
      document.getElementById('filePath').textContent=CURRENT_FILE;mountIframe(CURRENT_CONTENT);
    });
    await page.frameLocator('iframe.editor').locator('article').waitFor();
    await page.locator('.ax-tabs button[data-tab="dict"]').click();
    await page.locator('#axDictRun').click();
    assert.equal(await page.frameLocator('iframe.editor').locator('dfn').count(),1);
    await page.evaluate(() => {
      CURRENT_FILE='blog/article-b.html';EDITOR_LOAD_ID++;
      CURRENT_CONTENT='<html lang="zh-Hant"><head><title>B</title></head><body><main><article id="proseZh"><p>Keep second fixture</p></article></main></body></html>';
      document.getElementById('filePath').textContent=CURRENT_FILE;mountIframe(CURRENT_CONTENT);
    });
    await page.frameLocator('iframe.editor').locator('article').getByText('Keep second fixture',{exact:true}).waitFor();
    const untouched=await page.evaluate(()=>window.adminState.editedContent);
    await page.locator('#axDictUndo').click();
    assert.equal(await page.evaluate(()=>window.adminState.editedContent),untouched,'Actual root saved source preserves B after A dictionary undo');
    console.log('PASS actual root dictionary undo cannot cross article/load identity.');
  } finally { await context.close(); }
};

if (require.main === module) (async () => {
  const browser=await require('playwright').chromium.launch();
  try { await module.exports(browser); } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
