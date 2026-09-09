import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const source = readFileSync(new URL('./admin.html', import.meta.url), 'utf8');
const start = source.indexOf('function generateNewArticleSkeleton(opts){');
const end = source.indexOf('// ───', start);
const context = vm.createContext({});
vm.runInContext(source.slice(start, end), context);
const opts = {slug:'new-article', date:'2026-09-06', title:'A "quote" & <tag>',
  sub:'A subtitle', tag:'Example', desc:'A backslash \\ and </script> in prose'};

for (const type of ['myth','rx','overview','note','research']) {
  test(`article skeleton: ${type}`, () => {
    const html = context.generateNewArticleSkeleton({...opts,type});
    const json = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/)[1];
    const schema = JSON.parse(json);
    assert.equal(schema['@type'], type === 'research' ? 'MedicalScholarlyArticle' : 'MedicalWebPage');
    assert.equal(schema.description, opts.desc);
    assert.equal(schema.headline, opts.title + ' — ' + opts.sub);
    assert.equal((html.match(/id="refs"/g) || []).length, 1);
    assert.ok(html.includes('A &quot;quote&quot; &amp; &lt;tag&gt;'));
    const image = html.match(/property="og:image" content="([^"]+)"/)[1];
    assert.ok(image.endsWith('.png'));
    assert.ok(readFileSync(new URL('.' + new URL(image).pathname, import.meta.url)).length > 0);
    assert.ok(html.includes('name="twitter:image" content="' + image + '"'));
    assert.ok(html.includes('class="dn-nav"'));
    assert.ok(html.includes('id="dn-nav-burger"'));
    assert.ok(html.includes('id="dn-nav-theme"'));
    assert.ok(html.includes('id="dn-nav-critical"'));
    assert.ok(html.includes('/assets/inline/nav-burger.js?v=202609100440'));
  });
}
test('unsafe slug rejected before constructing markup', () => {
  assert.throws(() => context.generateNewArticleSkeleton({...opts,slug:'../"bad'}));
});

// Execute the legacy editor's real loading/export functions with isolated I/O.
const editorSource = readFileSync(new URL('./admin/edit.html', import.meta.url), 'utf8');
function editorFunction(name) {
  const start = editorSource.indexOf('function ' + name + '(');
  const next = /\nfunction [A-Za-z_$][\w$]*\(/g;
  next.lastIndex = start + 1;
  const end = next.exec(editorSource)?.index;
  assert.ok(start >= 0 && end > start, 'function boundary: ' + name);
  return editorSource.slice(start, end);
}
function editorFixture(drafts = {}) {
  const requests = [], downloads = [], messages = [], writes = [];
  let blob;
  const ctx = {
    state:{loadId:0}, $editor:{innerHTML:''}, $empty:{}, $toolbar:{}, $meta:{}, $statusBar:{}, $lastSaved:{},
    localStorage:{getItem:key=>drafts[key] ?? null, setItem:(...args)=>writes.push(args)},
    confirm:()=>true, toast:msg=>messages.push(msg), console:{error(){}},
    fetch:url=>new Promise((resolve,reject)=>requests.push({url,resolve:html=>resolve({ok:true,text:()=>Promise.resolve(html)}),reject})),
    sanitizeEditableHtml:html=>html,
    Blob:function(parts) { blob = parts.join(''); },
    URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},
    document:{createElement:()=>({click(){downloads.push({filename:this.download,html:blob});}}),body:{appendChild(){},removeChild(){}}},
  };
  ctx.applyEditorContent = html => {ctx.$editor.innerHTML=html;ctx.$editor.hidden=false;};
  ctx.markDirty = dirty => {ctx.state.dirty=dirty;};
  vm.runInNewContext(['loadArticle','resetArticle','fetchAndRender','saveDraft','exportHTML','copyBody'].map(editorFunction).join('\n'), ctx);
  return {ctx,requests,downloads,messages,writes};
}
const articleHTML = slug => `<html><head><title>${slug}</title><link rel="canonical" href="https://example.invalid/${slug}"></head><main><p>${slug}</p></main></html>`;

for (const priorArticle of [false,true]) {
  test(`restored draft exports its own title and canonical (prior article: ${priorArticle})`, async () => {
    const {ctx,requests,downloads} = editorFixture({'dn-admin-draft:b':'<p>Draft B</p>'});
    if (priorArticle) {
      const first=ctx.loadArticle('a'); requests.at(-1).resolve(articleHTML('a')); await first;
    }
    const pending=ctx.loadArticle('b');
    ctx.exportHTML(); assert.equal(downloads.length,0);
    requests.at(-1).resolve(articleHTML('b')); await pending;
    ctx.exportHTML();
    assert.deepEqual(downloads,[{filename:'b.html',html:articleHTML('b').replace('<p>b</p>','<p>Draft B</p>')}]);
  });
}

test('late article responses and errors cannot replace the selected article', async () => {
  const {ctx,requests,messages} = editorFixture();
  const a=ctx.loadArticle('a'), b=ctx.loadArticle('b');
  requests[1].resolve(articleHTML('b')); await b;
  requests[0].resolve(articleHTML('a')); await a;
  assert.equal(ctx.state.originalHTML,articleHTML('b'));
  const c=ctx.loadArticle('c'), d=ctx.loadArticle('d');
  requests[3].resolve(articleHTML('d')); await d;
  const count=messages.length;
  requests[2].reject(new Error('stale request')); await c;
  assert.equal(messages.length,count);
  assert.equal(ctx.state.originalHTML,articleHTML('d'));
});

test('failed or malformed loads cannot save, copy or export stale article data', async () => {
  for (const failure of ['network','malformed']) {
    const {ctx,requests,downloads,writes} = editorFixture({'dn-admin-draft:b':'<p>Preserve draft</p>'});
    const a=ctx.loadArticle('a'); requests[0].resolve(articleHTML('a')); await a;
    const b=ctx.loadArticle('b');
    ctx.saveDraft();ctx.copyBody();ctx.exportHTML();
    if (failure==='network') requests[1].reject(new Error('offline'));
    else requests[1].resolve('<html>Missing main</html>');
    await b;
    ctx.saveDraft();ctx.copyBody();ctx.exportHTML();
    assert.equal(ctx.state.originalHTML,null);
    assert.equal(ctx.$editor.hidden,true);
    assert.equal(writes.length,0);assert.equal(downloads.length,0);
  }
});

test('clearing the article selection invalidates pending loads', async () => {
  const {ctx,requests,downloads} = editorFixture();
  const pending=ctx.loadArticle('a');ctx.resetArticle(null);
  requests[0].resolve(articleHTML('a'));await pending;
  ctx.exportHTML();
  assert.equal(ctx.state.currentSlug,null);assert.equal(ctx.state.originalHTML,null);
  assert.equal(ctx.$editor.hidden,true);assert.equal(downloads.length,0);
});

test('empty saved draft is restored; declining a draft or unavailable storage loads the source', async () => {
  for (const mode of ['empty','decline','unavailable']) {
    const {ctx,requests} = editorFixture({'dn-admin-draft:b':mode==='empty'?'':'<p>Draft</p>'});
    if (mode==='decline') ctx.confirm=()=>false;
    if (mode==='unavailable') ctx.localStorage.getItem=()=>{throw new Error('blocked');};
    const pending=ctx.loadArticle('b');requests[0].resolve(articleHTML('b'));await pending;
    assert.equal(ctx.$editor.innerHTML,mode==='empty'?'':'<p>b</p>');
    assert.equal(ctx.state.originalHTML,articleHTML('b'));
  }
});

const extras = readFileSync(new URL('./admin/admin-extras.js', import.meta.url), 'utf8');
const seoContext = vm.createContext({URL});
vm.runInContext(extras.slice(extras.indexOf('  function analyzeSeoFacts('), extras.indexOf('  function runSeoCheck(')), seoContext);
const seoFacts = () => ({file:'blog/example.html',title:'短標題',description:'清楚的摘要',text:'文章內容',h1Count:1,h2Count:1,
  links:['/blog/related'],images:[],canonicals:['https://chendermatologist.com/blog/example'],jsonld:['{"@context":"https://schema.org","@type":"MedicalWebPage"}']});
const seoCheck = (facts,id) => seoContext.analyzeSeoFacts(facts).find(c=>c.id===id);

test('SEO guidance does not require filler words, headings or nofollow on editorial references', () => {
  const facts=seoFacts();facts.links=['https://pubmed.ncbi.nlm.nih.gov/123/'];
  assert.equal(seoCheck(facts,'title').ok,'ok');assert.equal(seoCheck(facts,'body').ok,'ok');
  assert.equal(seoCheck(facts,'links').ok,'ok');assert.equal(seoCheck(facts,'citations').ok,'ok');
  assert.equal(seoContext.analyzeSeoFacts(facts).some(c=>c.msg.includes('缺 nofollow')),false);
});
test('SEO link classification uses exact origin and excludes same-page anchors', () => {
  const facts=seoFacts();facts.links=['#section','https://chendermatologist.com/blog/example#other','/blog/related','relative',
    'https://chendermatologist.com.example.invalid/x','https://example.invalid/?q=chendermatologist.com','//example.invalid/a','javascript:alert(1)',''];
  const result=seoCheck(facts,'links');assert.equal(result.ok,'err');
  assert.match(result.msg,/2 個站內頁面、3 個外部參考、2 個無效或不安全網址/);
});
test('canonical rejects absent, blank, unsafe, multiple and wrong-origin values', () => {
  for(const canonicals of [[],[''],['javascript:alert(1)'],['/blog/example'],['https://chendermatologist.com.evil.invalid/blog/example'],
    ['https://chendermatologist.com/blog/example#fragment'],['https://chendermatologist.com/blog/example?a=1'],
    ['https://user:password@chendermatologist.com/blog/example'],['https://chendermatologist.com/blog/example','https://chendermatologist.com/blog/example']]) {
    assert.equal(seoCheck({...seoFacts(),canonicals},'canonical').ok,'err');
  }
  assert.equal(seoCheck({...seoFacts(),canonicals:['https://chendermatologist.com/blog/other']},'canonical').ok,'warn');
  for(const [file,url] of [['index.html','/'],['en/index.html','/en'],['blog/index.html','/blog'],['en/blog/example.html','/en/blog/example']]) {
    assert.equal(seoCheck({...seoFacts(),file,canonicals:['https://chendermatologist.com'+url]},'canonical').ok,'ok');
  }
});
test('JSON-LD checks parsing and basic structure rather than script presence', () => {
  for(const raw of ['{bad','null','[]','{}','"MedicalWebPage"','{"@graph":[]}','{"@type":[]}']) {
    assert.equal(seoCheck({...seoFacts(),jsonld:[raw]},'jsonld').ok,'err');
  }
  for(const raw of ['{"@type":"MedicalWebPage"}','{"@graph":[{"@type":"MedicalWebPage"},{"@id":"#author"}]}','[{"@type":["Article","MedicalWebPage"]}]']) {
    assert.equal(seoCheck({...seoFacts(),jsonld:[raw]},'jsonld').ok,'ok');
  }
});
test('missing alt is an error; decorative empty alt needs human confirmation', () => {
  assert.equal(seoCheck({...seoFacts(),images:[null]},'alt').ok,'err');
  assert.equal(seoCheck({...seoFacts(),images:['']},'alt').ok,'ok');
  assert.equal(seoCheck({...seoFacts(),images:['']},'decorative').ok,'warn');
  assert.equal(seoCheck({...seoFacts(),text:''},'body').ok,'err');
});
