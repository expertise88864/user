// Corpus compatibility uses local article bytes and blocked external requests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

module.exports = async function checkWordEditor(browser) {
  const match = fs.readFileSync('blog/blog-shared.js', 'utf8').match(/DN\.ARTICLES\s*=\s*(\[[\s\S]*?\]);/);
  assert.ok(match, 'public catalog must exist');
  const catalog = vm.runInNewContext('(' + match[1] + ')', {}, {timeout: 1000});
  const context = await browser.newContext({serviceWorkers: 'block'});
  const results = [];
  try {
    const page = await context.newPage();
    await page.route('**/*', route => route.request().url() === 'https://word-editor.test/'
      ? route.fulfill({contentType: 'text/html', body: '<!doctype html><main id="editor"></main>'}) : route.abort());
    await page.goto('https://word-editor.test/');
    await page.addScriptTag({content: fs.readFileSync('admin/word-model.bundle.js', 'utf8')});
    for (const article of catalog.filter(item => !item.unpublished)) {
      const file = 'blog/' + article.slug + '.html';
      const source = fs.readFileSync(file, 'utf8');
      results.push(await page.evaluate(({file, source}) => {
        let region;
        try { region = DNWordModel.articleRegion(source); } catch (error) { return {file, failed: ['region'], error: error.message}; }
        const mount = document.getElementById('editor');
        mount.replaceChildren();
        const editor = DNWordModel.createEditor(mount, region.inner);
        const exact = region.assemble(editor.serialize()) === source;
        const firstText = editor.view.state.selection.constructor.findFrom(editor.view.state.doc.resolve(0),1,true);
        editor.view.dispatch(editor.view.state.tr.setSelection(firstText));
        editor.insert('WORD_CORPUS_MARKER');
        const changed = editor.serialize();
        const parse = value => new DOMParser().parseFromString(value, 'text/html');
        const before = parse(region.inner), after = parse(changed);
        const attrs = (document, selector) => [...document.querySelectorAll(selector)].map(node =>
          [node.localName, [...node.attributes].map(attr => [attr.name, attr.value]).filter(([name]) => !['colwidth','data-zh','data-en','data-translation-pending'].includes(name)).sort()]);
        const ids = document => [...document.querySelectorAll('[id]')].map(node => node.id).sort();
        const links = document => [...document.querySelectorAll('a[href]')].map(node => node.getAttribute('href')).sort();
        const count = document => ['table','thead','tbody','tfoot','tr','td','th','li','ul','ol','sup','sub','section'].map(tag => [tag, document.querySelectorAll(tag).length]);
        const normalize = value => value.replace(/\s/g, '');
        const checks = {exact,
          text: normalize(after.body.textContent).replace('WORD_CORPUS_MARKER','') === normalize(before.body.textContent),
          ids: JSON.stringify(ids(before)) === JSON.stringify(ids(after)),
          links: JSON.stringify(links(before)) === JSON.stringify(links(after)),
          structure: JSON.stringify(count(before)) === JSON.stringify(count(after)),
          tableAttributes: JSON.stringify(attrs(before, 'table,thead,tbody,tfoot,tr,td,th')) === JSON.stringify(attrs(after, 'table,thead,tbody,tfoot,tr,td,th')),
          protected: [...editor.protectedSource.values()].every(raw => changed.includes(raw)),
          shell: region.assemble(changed).startsWith(source.slice(0, source.indexOf(region.inner))),
          undo: editor.undo() && editor.serialize() === region.inner};
        checks.redo = editor.redo() && editor.serialize() === changed;
        const failed = Object.entries(checks).filter(([,value]) => value !== true).map(([name]) => name);
        const oldTable = attrs(before, 'table,thead,tbody,tfoot,tr,td,th'), newTable = attrs(after, 'table,thead,tbody,tfoot,tr,td,th');
        const tableIndex = oldTable.findIndex((row,index) => JSON.stringify(row) !== JSON.stringify(newTable[index]));
        const diagnostics = failed.length ? {firstTableDifference: {before: oldTable[tableIndex], after: newTable[tableIndex]}} : null;
        editor.destroy();
        return {file, checks, failed, diagnostics};
      }, {file, source}));
    }
    const failures = results.filter(row => row.failed.length);
    console.log(JSON.stringify({wordEditorCorpus: results.length, failures}, null, 2));
    assert.equal(failures.length, 0, 'Every public article must preserve source, text, IDs, links, tables and protected bytes');
    const edgeCases=await page.evaluate(()=>{
      const mount=document.getElementById('editor'),checks={};
      const editor=DNWordModel.createEditor(mount,'<p id="first">first</p><p id="second">second</p>');
      const caret=editor.view.state.selection.constructor.findFrom(editor.view.state.doc.resolve(8),1,true);
      editor.view.dispatch(editor.view.state.tr.setSelection(caret));editor.insert('HERE');
      const parsed=new DOMParser().parseFromString(editor.serialize(),'text/html');
      checks.activeSelection=parsed.getElementById('first').textContent==='first'&&parsed.getElementById('second').textContent==='HEREsecond';editor.destroy();
      for(const [index,comment]of ['<!-- authored comment -->','<!---->','<!-- nested <!-- retained -->','<!-- unterminated'].entries()){
        const source='<p>Text</p>'+comment,model=DNWordModel.createEditor(mount,source);
        const exact=model.serialize()===source;model.insert('Edit');
        checks['comment'+index]=exact&&model.serialize().includes(comment)&&model.protectedSource.size===1;model.destroy();
      }
      const link=DNWordModel.createEditor(mount,'<p><a href="/blog/tinea-myths">Keep</a></p>');
      const handled=link.view.dom.querySelector('a').dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
      checks.linkActivationBlocked=handled===false&&window.NAVIGATED===undefined;
      const before=link.serialize(),drop=new DragEvent('drop',{bubbles:true,cancelable:true});
      checks.dropBlocked=link.view.someProp('handleDrop',handler=>handler(link.view,drop))===true&&link.serialize()===before;
      link.destroy();return checks;
    });
    for(const [name,result]of Object.entries(edgeCases))assert.equal(result,true,name);
    console.log('Word model selection/comment/link/drop edge checks:',Object.keys(edgeCases).length);
  } finally { await context.close(); }
};
