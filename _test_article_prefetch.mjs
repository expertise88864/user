import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

function fixture(options = {}) {
  const appended = [], handlers = new Map();
  const location = new URL(options.url || 'https://chendermatologist.com/');
  const link = (href, excluded = false) => {
    const anchor = {
      getAttribute: name => name === 'href' ? href : null,
      closest: selector => selector === 'a[href]' ? anchor : excluded ? {} : null,
    };
    return anchor;
  };
  const document = {
    head: {appendChild: node => appended.push(node)},
    createElement: () => ({}),
    querySelector: () => options.nativeRules ? {} : null,
    querySelectorAll: () => [],
    addEventListener: (name, handler) => {
      if (!handlers.has(name)) handlers.set(name, []);
      handlers.get(name).push(handler);
    },
  };
  const window = {DN: {}, HTMLScriptElement: {supports: () => !!options.nativeRules},
    requestIdleCallback: callback => callback()};
  vm.runInNewContext(readFileSync(new URL('./blog/blog-shared.js', import.meta.url), 'utf8'), {
    window, document, location, URL, navigator: {onLine: options.online ?? true, connection: options.connection},
    IntersectionObserver: class {observe() {}}, setTimeout: callback => callback(),
  });
  const dn = window.DN;
  function dispatch(href, event = 'mouseover', excluded = false) {
    (handlers.get(event) || []).forEach(handler => handler({target: link(href, excluded)}));
  }
  return {dn, appended, handlers, dispatch};
}

test('article prefetch makes no startup requests and binds once', () => {
  const f = fixture(); f.dn.prefetchOnIdle(); f.dn.prefetchOnIdle();
  assert.equal(f.appended.length, 0);
  assert.equal(f.handlers.get('mouseover')?.length, 1);
  assert.equal(f.handlers.get('focusin')?.length, 1);
  assert.equal(f.handlers.get('touchstart')?.length, 1);
  f.dispatch('/blog/acne-myths');
  assert.equal(f.appended.length, 1);
  assert.equal(f.appended[0].href, 'https://chendermatologist.com/blog/acne-myths');
  assert.equal(f.appended[0].rel, 'prefetch');
  assert.equal(f.appended[0].as, 'document');
});

test('article prefetch deduplicates fragments and caps incidental intent', () => {
  const f = fixture(); f.dn.prefetchOnIdle();
  for (const event of ['mouseover', 'focusin', 'touchstart']) f.dispatch('/blog/acne-myths#dx', event);
  assert.equal(f.appended.length, 1);
  assert.equal(f.appended[0].href.includes('#'), false);
  for (const article of f.dn.ARTICLES.filter(a => !a.unpublished).slice(0, 10)) f.dispatch('/blog/' + article.slug);
  assert.equal(f.appended.length, 4);
});

test('article prefetch rejects private, unrelated, query, cross-origin and unpublished links', () => {
  const f = fixture(); f.dn.prefetchOnIdle();
  const unpublished = f.dn.ARTICLES.find(a => a.unpublished); assert.ok(unpublished);
  for (const href of ['/', '/blog/', '/about', '/admin', '/api/admin/site-settings', '#dx',
    '//example.com/blog/acne-myths', 'https://chendermatologist.com.example.com/blog/acne-myths',
    'https://user:password@chendermatologist.com/blog/acne-myths', '/blog/acne-myths?q=private',
    'javascript:alert(1)', '/blog/unknown', '/blog/' + unpublished.slug]) f.dispatch(href);
  f.dispatch('/blog/acne-myths', 'focusin', true);
  assert.equal(f.appended.length, 0);
  f.dispatch('/en/blog/acne-myths', 'focusin');
  assert.equal(f.appended.length, 1);
});

test('article prefetch skips current article aliases and works on the local static server', () => {
  const f = fixture({url: 'http://localhost:8080/blog/acne-myths.html'}); f.dn.prefetchOnIdle();
  f.dispatch('/blog/acne-myths#dx'); f.dispatch('/blog/acne-myths.html#when');
  assert.equal(f.appended.length, 0);
  f.dispatch('/blog/sunscreen-myths.html');
  assert.equal(f.appended[0]?.href, 'http://localhost:8080/blog/sunscreen-myths.html');
});

test('article prefetch respects browser-native rules, offline and constrained connections', () => {
  for (const options of [{nativeRules: true}, {online: false}, {connection: {saveData: true}},
    {connection: {effectiveType: '2g'}}, {connection: {effectiveType: 'slow-2g'}}]) {
    const f = fixture(options); f.dn.prefetchOnIdle(); f.dispatch('/blog/acne-myths');
    assert.equal(f.appended.length, 0); assert.equal(f.handlers.size, 0);
  }
});

test('article prefetch rechecks connection preferences after initialization', () => {
  const connection = {saveData: false, effectiveType: '4g'};
  const f = fixture({connection}); f.dn.prefetchOnIdle();
  connection.saveData = true; f.dispatch('/blog/acne-myths');
  assert.equal(f.appended.length, 0);
  connection.saveData = false; connection.effectiveType = '2g'; f.dispatch('/blog/acne-myths');
  assert.equal(f.appended.length, 0);
  connection.effectiveType = '4g'; f.dispatch('/blog/acne-myths');
  assert.equal(f.appended.length, 1);
});

test('offline precache excludes unpublished picks and recent drafts and respects the requested bound', () => {
  const messages = [], window = {DN:{}};
  vm.runInNewContext(readFileSync(new URL('./blog/blog-shared.js', import.meta.url),'utf8'), {
    window, navigator:{serviceWorker:{controller:{postMessage: message => messages.push(message)}}},
    location:{hostname:'localhost',pathname:'/'},
  });
  const dn=window.DN, draft=dn.ARTICLES.find(a=>a.unpublished);assert.ok(draft);
  draft.date='2099-01-01';
  dn.POPULAR_PICKS=[draft.slug,...dn.publishedArticles().slice(0,12).map(a=>a.slug)];
  dn.precacheArticles(8);
  assert.equal(messages.length,1);assert.equal(messages[0].urls.length,8);
  assert.equal(new Set(messages[0].urls).size,8);
  assert.ok(messages[0].urls.every(url=>url.endsWith('.html')&&!url.includes(draft.slug)));
  dn.POPULAR_PICKS=[];dn.precacheArticles(8);
  assert.equal(messages[1].urls.length,8);assert.ok(messages[1].urls.every(url=>!url.includes(draft.slug)));
});

test('public reading count excludes stale, duplicate and unpublished history without erasing it', () => {
  const values=new Map(),events=[],window={DN:{},dispatchEvent:()=>{}};
  const location={pathname:'/blog/acne-myths'};
  vm.runInNewContext(readFileSync(new URL('./blog/blog-shared.js', import.meta.url),'utf8'), {
    window,location,localStorage:{getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value)},
    CustomEvent:class{},gtag:(name,event,data)=>events.push({name,event,data}),
  });
  const dn=window.DN,draft=dn.ARTICLES.find(a=>a.unpublished);assert.ok(draft);
  const publicSlugs=dn.publishedArticles().map(a=>a.slug);
  assert.equal(dn.totalArticles,publicSlugs.length);
  const history=JSON.stringify([publicSlugs[0],publicSlugs[0],draft.slug,'removed-article',null]);
  values.set(dn.READ_KEY,history);
  assert.equal(dn.getReadCount(),1);assert.equal(values.get(dn.READ_KEY),history,'reading does not discard recoverable history');
  const number=dn.getArticleNumber(publicSlugs[1]);dn.markRead(draft.slug);dn.markRead('unknown');
  assert.equal(values.get(dn.READ_KEY),history);assert.equal(events.length,0);
  dn.markRead(publicSlugs[1]);assert.equal(dn.getReadCount(),2);
  assert.equal(events.find(e=>e.event==='article_read').data.total_read,2);
  assert.equal(dn.getArticleNumber(publicSlugs[1]),number,'publication filtering never renumbers article identifiers');
  values.set(dn.READ_KEY,JSON.stringify([...publicSlugs,draft.slug,'removed-article']));
  assert.equal(dn.getReadCount(),dn.totalArticles);
});


test('idle article cache destinations follow URL language on hosted and static origins',()=>{
 for(const hostname of ['chendermatologist.com','localhost','127.0.0.1','[::1]']){
  for(const pathname of ['/blog/acne-myths','/en','/en/blog/acne-myths','/enough/blog/acne-myths']){
   const messages=[],window={DN:{}};
   vm.runInNewContext(readFileSync(new URL('./blog/blog-shared.js', import.meta.url),'utf8'),{
    window,location:{hostname,pathname},navigator:{onLine:true,serviceWorker:{controller:{postMessage:value=>messages.push(value)}}}
   });
   window.DN.precacheArticles(2);assert.equal(messages.length,1);
   const prefix=pathname==='/en'||pathname.startsWith('/en/')?'/en/blog/':'/blog/';
   const suffix=hostname==='chendermatologist.com'?'':'.html';
   assert.deepEqual(Array.from(messages[0].urls),['acne-myths','sunscreen-myths'].map(slug=>prefix+slug+suffix));
  }
 }
});
test('idle article cache does not fetch on offline or data-saving connections',()=>{
 for(const options of [{onLine:false},{connection:{saveData:true}},{connection:{effectiveType:'2g'}},{connection:{effectiveType:'slow-2g'}}]){
  const messages=[],window={DN:{}};
  vm.runInNewContext(readFileSync(new URL('./blog/blog-shared.js', import.meta.url),'utf8'),{
   window,location:{hostname:'chendermatologist.com',pathname:'/en/blog/acne-myths'},
   navigator:{...options,serviceWorker:{controller:{postMessage:value=>messages.push(value)}}}
  });
  window.DN.precacheArticles(2);assert.equal(messages.length,0);
 }
});
