import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';

const hubContext = {window:{DN:{ARTICLES:[]}}};
vm.runInNewContext(readFileSync(new URL('./blog/blog-hub.js', import.meta.url),'utf8'), hubContext);
const searchCatalog = hubContext.window.DN.searchArticleCatalog;

test('English return links preserve current URL context and map only explicit primary IDs', () => {
  const source = readFileSync(new URL('./assets/inline/en-locale-banner.js', import.meta.url), 'utf8');
  const events = {}, location = {origin:'https://example.test',search:'?from=reader',hash:'#en-dx'};
  const link = {href:'https://example.test/blog/example', getAttribute:()=>'{"en-dx":"dx"}',
    addEventListener:(name, handler)=>{events[name]=handler;}};
  const context = {URL,location,window:{addEventListener:(name,handler)=>{events[name]=handler;}},
    localStorage:{setItem(){}},document:{getElementById:()=>link,addEventListener:(name,handler)=>{events[name]=handler;}}};
  vm.runInNewContext(source,context);events.DOMContentLoaded();
  assert.equal(link.href,'/blog/example?from=reader#dx');
  location.hash='#term-%E8%95%88';events.hashchange();assert.equal(link.href,'/blog/example?from=reader#term-%E8%95%88');
  location.search='?from=changed';location.hash='#main-content';events.click();assert.equal(link.href,'/blog/example?from=changed#main-content');
  location.hash='#bad%ZZ';events.click();assert.equal(link.href,'/blog/example?from=changed#bad%ZZ');
});

test('English return-link helper leaves foreign-origin links untouched', () => {
  const source = readFileSync(new URL('./assets/inline/en-locale-banner.js', import.meta.url), 'utf8');
  let boot;const link={href:'https://foreign.test/'};
  const context={URL,location:{origin:'https://example.test'},localStorage:{setItem(){}},
    document:{getElementById:()=>link,addEventListener:(name,handler)=>{boot=handler;}}};
  vm.runInNewContext(source,context);boot();assert.equal(link.href,'https://foreign.test/');
});

test('article numbering keeps ISO-date order without initializing locale collation', () => {
  const source = readFileSync(new URL('./blog/blog-shared.js', import.meta.url), 'utf8');
  const context = vm.createContext({window:{DN:{}}});
  vm.runInContext("String.prototype.localeCompare = function () { throw new Error('Unexpected locale collation during startup'); };", context);
  vm.runInContext(source, context);
  const dn = context.window.DN;
  // VM intrinsics are isolated. This callback runs in the host realm; retain
  // the old locale comparator as an independent article-numbering oracle.
  const expected = [...dn.ARTICLES].sort((a,b) => (a.date || '').localeCompare(b.date || ''));
  expected.forEach((article,index) => assert.equal(dn.getArticleNumber(article.slug), String(index+1).padStart(3,'0')));
  assert.equal(dn.compareDates('2026-01-31','2026-02-01'), -1);
  assert.equal(dn.compareDates('2026-09-30','2025-12-31'), 1);
  assert.equal(dn.compareDates('2026-09-30','2026-09-30'), 0);
  assert.equal(dn.compareDates(undefined,'2026-09-30'), -1);
  assert.equal(dn.compareDates(null,''), 0);
});
test('language refresh avoids redundant mutations but translates new content and repairs labels', () => {
  let lang = 'zh-TW', langWrites = 0, attrWrites = 0;
  const attrs = new Map([['aria-label', '搜尋'], ['data-zh-aria-label', '搜尋'], ['data-en-aria-label', 'Search']]);
  const label = { getAttribute: name => attrs.get(name) ?? null,
    setAttribute: (name, value) => { attrWrites++; attrs.set(name, value); } };
  const text = { dataset: {zh:'原文',en:'Original'}, textContent:'原文', hasAttribute:() => false };
  const edited = { dataset: {zh:'舊文',en:'Old'}, textContent:'醫師修改內容', hasAttribute:() => false };
  const content = [text, edited];
  const document = {
    documentElement: { get lang() { return lang; }, set lang(value) { langWrites++; lang = value; } },
    querySelectorAll: selector => selector === '[data-zh],[data-en]' ? content
      : selector.includes('aria-label') ? [label] : [],
  };
  const window = {DN:{}};
  vm.runInNewContext(readFileSync(new URL('./blog/blog-shared.js', import.meta.url), 'utf8'), {window,document});
  const dn = window.DN;
  dn.applyTextOnly('zh');
  assert.equal(langWrites, 0);
  assert.equal(attrWrites, 0);
  dn.applyTextOnly('en');
  assert.equal(lang, 'en');
  assert.equal(text.textContent, 'Original');
  assert.equal(edited.textContent, '醫師修改內容');
  assert.equal(attrs.get('aria-label'), 'Search');
  assert.equal(langWrites, 1);
  assert.equal(attrWrites, 1);
  content.push({dataset:{zh:'新增',en:'Added'},textContent:'新增',hasAttribute:() => false});
  attrs.set('aria-label', 'stale label');
  dn.applyTextOnly('en');
  assert.equal(content[2].textContent, 'Added');
  assert.equal(attrs.get('aria-label'), 'Search');
  assert.equal(langWrites, 1);
  assert.equal(attrWrites, 2);
  dn.applyTextOnly('en');
  assert.equal(attrWrites, 2);
  const plainText={dataset:{zh:'文字',en:'<img src="x"> & text'},textContent:'文字',
    hasAttribute:name => name==='data-dn-text-only',
    set innerHTML(value) { throw new Error('Plain catalogue text must never use innerHTML: '+value); }};
  content.push(plainText);
  dn.applyTextOnly('en');
  assert.equal(plainText.textContent,'<img src="x"> & text');
  dn.applyTextOnly('zh');
  assert.equal(plainText.textContent,'文字');
  plainText.textContent='Custom visible text';
  dn.applyTextOnly('en');
  assert.equal(plainText.textContent,'Custom visible text');
});

test('reading metadata counts spaced English words and includes the badge without locale initialization', () => {
  const bars = [];
  const prose = {textContent:'皮'.repeat(3500) + ' ' + Array(800).fill('word').join(' ')};
  const lead = {};
  const h1 = {parentElement:{querySelector:()=>lead}};
  const doc = {
    getElementById:id=>id==='proseZh'?prose:id==='dn-reading-meta'?bars[0]:id==='dn-secondary-meta'?{appendChild:bar=>bars.push(bar)}:null,
    querySelector:selector=>selector==='article h1, section h1'?h1:null,
    createElement:()=>({style:{},innerHTML:''})
  };
  const context = vm.createContext({window:{DN:{currentSlug:()=>null,getArticleNumber:()=>null,ARTICLES:[]}},document:doc});
  vm.runInContext("Number.prototype.toLocaleString=function(){throw Error('Unexpected locale formatter');};",context);
  vm.runInContext(readFileSync(new URL('./blog/blog-article-reading.js',import.meta.url),'utf8'),context);
  context.window.DN.addReadingMeta();
  assert.equal(bars.length,1);
  assert.match(bars[0].innerHTML,/14 min read/);
  assert.match(bars[0].innerHTML,/data-dn-wordcount/);
  assert.match(bars[0].innerHTML,/3,500 characters \/ 800 words/);
  context.window.DN.addReadingMeta();
  assert.equal(bars.length,1,'Repeated initialization must not duplicate metadata');
  bars.length=0;
  prose.textContent=Array(1000).fill('word').join(' ');
  context.window.DN.addReadingMeta();
  assert.match(bars[0].innerHTML,/5 min read/);
  assert.match(bars[0].innerHTML,/1,000 words/);
});
test('reading completion requires foreground dwell and scroll, and fires once', () => {
  let now = 0, tick, reads = 0, events = 0, visibleBottom = 200;
  const documentListeners = new Map(), windowListeners = new Map();
  const article = {scrollHeight:1000, getBoundingClientRect:()=>({top:0})};
  const lead = {parentNode:{insertBefore(){}}};
  const doc = {
    hidden:false,
    getElementById:id=>id==='proseZh' ? {textContent:'閱讀內容'} : null,
    querySelector:selector=>selector.includes('h1') ? {parentElement:{querySelector:()=>lead}} : article,
    createElement:()=>({style:{}}),
    addEventListener:(name,fn)=>documentListeners.set(name,fn),
    removeEventListener:(name,fn)=>{if(documentListeners.get(name)===fn) documentListeners.delete(name);},
  };
  const win = {DN:{currentSlug:()=> 'article',getArticleNumber:()=>null,markRead:()=>reads++},scrollY:0,
    get innerHeight(){return visibleBottom;},
    addEventListener:(name,fn)=>windowListeners.set(name,fn),
    removeEventListener:(name,fn)=>{if(windowListeners.get(name)===fn) windowListeners.delete(name);}};
  vm.runInNewContext(readFileSync(new URL('./blog/blog-article-reading.js',import.meta.url),'utf8'), {
    window:win,document:doc,performance:{now:()=>now},gtag:()=>events++,
    setInterval:fn=>{tick=fn;return 1;},clearInterval(){},requestAnimationFrame:fn=>fn(),
  });
  win.DN.addReadingMeta();
  now=10000; doc.hidden=true; documentListeners.get('visibilitychange')();
  now=100000; tick(); assert.equal(reads,0);
  doc.hidden=false; documentListeners.get('visibilitychange')();
  now=119000; visibleBottom=800; tick(); assert.equal(reads,0);
  now=120000; visibleBottom=200; tick(); assert.equal(reads,0);
  visibleBottom=800; tick(); assert.equal(reads,1);
  now=150000; tick(); assert.equal(reads,1); assert.equal(events,1);
  assert.equal(windowListeners.has('scroll'),false);
  assert.equal(documentListeners.has('visibilitychange'),false);
});
const searchFixtures = [
  {slug:'dupilumab-long-term-maintenance',title:'杜避炎要打多久？停藥、減量與維持治療',tag:'異位性皮膚炎'},
  {slug:'topical-acids-patient',title:'A酸、A醇、杜鵑花酸怎麼選？',tag:'酸類'},
  {slug:'perioral-dermatitis-guide',title:'嘴角紅疹是痘痘還是濕疹？',tag:'口周皮膚炎'},
  {slug:'draft',title:'杜避炎 打多久',unpublished:true},
];
test('patient search accepts whitespace, multiple words and full-width characters', () => {
  for (const [query, slug] of [['杜避炎 打多久','dupilumab-long-term-maintenance'], ['Ａ　醇','topical-acids-patient'], ['嘴角 紅疹','perioral-dermatitis-guide']]) {
    assert.equal(searchCatalog(searchFixtures,query,{})[0]?.slug, slug);
  }
  assert.equal(searchCatalog(searchFixtures,'沒有符合的問題',{}).length,0);
  assert.equal(searchCatalog(searchFixtures,'   ',{}).length,3);
});
test('patient search ranks title matches before descriptions and keeps drafts private', () => {
  const descriptions={'topical-acids-patient':{desc:'杜避炎 打多久'}};
  const results=searchCatalog(searchFixtures,'杜避炎 打多久',descriptions);
  assert.equal(results[0].slug,'dupilumab-long-term-maintenance');
  assert.equal(results[1].slug,'topical-acids-patient');
  assert.equal(results.some(a=>a.slug==='draft'),false);
});

test('optional font CSS preserves cached and later loads after content paints', () => {
  const listeners = new Map();
  const frames = [];
  let paint;
  class PaintObserver {
    static supportedEntryTypes = ['paint'];
    constructor(callback) { paint = callback; }
    observe() {}
    disconnect() {}
  }
  const links = [false, true].map(cached => ({media:'print', sheet:cached ? {} : null,
    addEventListener(name, fn) { listeners.set(this, {name, fn}); }}));
  vm.runInNewContext(readFileSync(new URL('./assets/inline/font-loader.js', import.meta.url), 'utf8'),
    {window:{addEventListener(){}},document:{querySelectorAll(){return links;}},
      performance:{getEntriesByName(){return [];}},PerformanceObserver:PaintObserver,
      clearTimeout(){},requestAnimationFrame:fn=>frames.push(fn)});
  assert.equal(links[0].media, 'print');
  assert.equal(links[1].media, 'print');
  // RAF callbacks alone must never substitute for an actual content paint.
  while (frames.length) frames.shift()();
  assert.equal(links[1].media, 'print');
  paint({getEntries(){return [{name:'first-contentful-paint'}];}});
  assert.equal(links[1].media, 'all');
  assert.equal(listeners.get(links[0]).name, 'load');
  listeners.get(links[0]).fn();
  assert.equal(links[0].media, 'all');
});

async function installWorker(offlineFails) {
  const listeners = {};
  let stored = false;
  const cache = {
    async add(request) {
      assert.equal(request.redirect, 'error');
      if (new URL(request.url).pathname !== '/offline' || offlineFails) throw new Error('network unavailable');
      stored = true;
    },
    async match() { return stored ? {} : undefined; },
  };
  const context = {self:{addEventListener(name, fn){listeners[name]=fn;},skipWaiting(){}},
    caches:{async open(){return cache;}}, URL, console,
    Request: class extends Request { constructor(url, options) {super(new URL(url,'https://site.test'),options);} }};
  vm.runInNewContext(readFileSync(new URL('./sw.js', import.meta.url),'utf8'), context);
  let completion;
  listeners.install({waitUntil(promise){completion=promise;}});
  await completion;
}

test('service worker cannot activate without its required offline fallback', async () => {
  await assert.rejects(installWorker(true), /network unavailable/);
});
test('optional precache failures do not prevent installation with an offline fallback', async () => {
  await installWorker(false);
});

test('navigation ignores a followed redirect in cache and preserves valid cached HTML', async () => {
  for (const redirected of [true, false]) {
    const handlers = {}, waits = [];
    const cached = {redirected}, fresh = {ok:false,status:0,type:'opaqueredirect'};
    const cache = {match: async () => cached};
    vm.runInNewContext(readFileSync(new URL('./sw.js', import.meta.url),'utf8'), {
      self:{addEventListener:(name,fn)=>handlers[name]=fn},
      caches:{open:async()=>cache},location:{origin:'https://site.test'},URL,
      fetch:async()=>fresh,
    });
    let response;
    handlers.fetch({request:{method:'GET',url:'https://site.test/blog/',mode:'navigate'},
      respondWith:p=>response=p,waitUntil:p=>waits.push(p)});
    assert.equal(await response, redirected ? fresh : cached);
    await Promise.all(waits);
  }
});

async function offlineAssetResponse(pathname, cached) {
  const handlers = {};
  vm.runInNewContext(readFileSync(new URL('./sw.js', import.meta.url), 'utf8'), {
    self: {addEventListener:(name,fn)=>handlers[name]=fn},
    location: {origin:'https://site.test'}, URL, Response,
    caches: {match:async()=>cached},
    fetch: async()=>{throw Error('network disconnected');},
  });
  let response;
  handlers.fetch({request:{method:'GET',url:'https://site.test'+pathname,mode:'cors',headers:{get:()=>null}},
    respondWith:p=>response=p,waitUntil(){}});
  return response;
}

test('offline navigation returns a Response even when both fallback cache entries are absent', async () => {
  for (const available of [null, '/offline', '/']) {
    const handlers = {}, cached = new Response('cached fallback');
    const cache = { match: async key => key === available ? cached : undefined };
    vm.runInNewContext(readFileSync(new URL('./sw.js', import.meta.url), 'utf8'), {
      self: { addEventListener: (name, fn) => handlers[name] = fn },
      location: { origin: 'https://site.test' }, URL, Response,
      caches: { open: async () => cache },
      fetch: async () => { throw Error('network disconnected'); },
    });
    let response;
    handlers.fetch({ request: { method: 'GET', url: 'https://site.test/blog/uncached', mode: 'navigate' },
      respondWith: promise => response = promise, waitUntil() {} });
    const result = await response;
    assert.ok(result instanceof Response, 'respondWith must not resolve to undefined');
    if (available) assert.equal(result, cached);
    else { assert.equal(result.type, 'error'); assert.equal(result.status, 0); }
  }
});

for (const pathname of ['/assets/search-index.json','/_vercel/speed-insights/script.js']) {
  test(`offline cache miss returns a valid network-error response (${pathname})`,async()=>{
    const response=await offlineAssetResponse(pathname);
    assert.ok(response instanceof Response,'respondWith must never resolve to undefined');
    assert.equal(response.type,'error');
    assert.equal(response.status,0,'Missing content must not become a synthetic success');
  });
  test(`offline cached content remains readable (${pathname})`,async()=>{
    const cached=new Response('existing cached bytes');
    assert.equal(await offlineAssetResponse(pathname,cached),cached);
  });
}
test('offline versioned cache miss keeps the same network-error contract',async()=>{
  const response=await offlineAssetResponse('/assets/local.js?v=202610020910');
  assert.ok(response instanceof Response);
  assert.equal(response.type,'error');
});

function runtime(cookie, pathname = '/blog/acne-myths', language = 'zh-TW') {
  const context = {
    window: {}, document: { cookie }, location: { pathname },
    navigator: { language }, localStorage: { getItem: () => 'en' },
    console,
  };
  vm.runInNewContext(readFileSync(new URL('./blog/blog-shared.js', import.meta.url), 'utf8'), context);
  return context.window.DN;
}

test('reading memory rejects malformed storage and safely tolerates blocked cleanup', () => {
  const valid = {y:600,pct:35,ts:Date.now(),h2:'Heading'};
  for (const raw of ['{bad', JSON.stringify(null), JSON.stringify([]),
    ...[{pct:'<img src=x onerror="bad">'},{pct:'35'},{pct:101},{pct:-1},{pct:5.5},
      {y:'600'},{y:-1},{y:null},{ts:'recent'},{ts:Date.now()+86400000},{ts:1},{h2:[]}]
      .map(extra=>JSON.stringify({...valid,...extra}))]) {
    const timers = [], created = [], prose = {};
    const win = {DN:{},location:{hash:''},addEventListener(){}};
    const document = {getElementById:id=>id==='proseZh'?prose:null,
      querySelector:()=>prose,addEventListener(){},createElement:tag=>{created.push(tag);return {};}};
    vm.runInNewContext(readFileSync(new URL('./blog/blog-article-reading.js',import.meta.url),'utf8'), {
      window:win,document,setTimeout:fn=>timers.push(fn),
      localStorage:{getItem:()=>raw,removeItem(){throw Error('storage cleanup blocked');}},
    });
    win.DN.currentSlug=()=> 'fixture'; win.DN.bindScrollMemory();
    assert.doesNotThrow(()=>timers.shift()(),raw);
    assert.deepEqual(created,[], 'Invalid storage must not create a restore prompt');
  }
});

test('malformed language cookie does not abort language detection', () => {
  const dn = runtime('dn_lang=%E0%A4%A');
  assert.equal(dn.cookieGet('dn_lang'), null);
  assert.equal(dn.detectLang(), 'zh');
});

test('cookie reader preserves encoded values and tolerates delimiter spacing', () => {
  const dn = runtime('other=1;dn_lang=en; value=a%3Db');
  assert.equal(dn.detectLang(), 'zh');
  assert.equal(dn.cookieGet('value'), 'a=b');
  assert.equal(dn.cookieGet('missing'), null);
});

test('URL language stays stable across browser language and saved preferences', () => {
  for (const path of ['/', '/tools', '/blog/acne-myths', '/enough']) {
    assert.equal(runtime('dn_lang=en', path, 'en-US').detectLang(), 'zh');
  }
  for (const path of ['/en', '/en/', '/en/tools', '/en/blog/acne-myths']) {
    assert.equal(runtime('dn_lang=zh', path, 'zh-TW').detectLang(), 'en');
  }
});

// Exercise the exact server path resolver on both platforms, without opening
// a listener or relying on the host OS to reproduce Windows drive paths.
function resolver(platform, root) {
  const source = readFileSync(new URL('./_serve.mjs', import.meta.url), 'utf8');
  const fn = source.slice(source.indexOf('function safePath('), source.indexOf('\nasync function resolveFile'));
  return vm.runInNewContext(`${fn}; safePath`, { path: platform, ROOT: root });
}

test('Windows absolute paths cannot escape into a similarly named sibling', () => {
  const resolve = resolver(path.win32, 'C:\\site');
  assert.equal(resolve('/C:/site-private/secret.txt'), null);
  assert.equal(resolve('/C:/other/secret.txt'), null);
  assert.equal(resolve('/blog/article.html'), 'C:\\site\\blog\\article.html');
});

test('malformed percent escapes fail closed and normal encoded assets resolve', () => {
  const resolve = resolver(path.posix, '/site');
  assert.equal(resolve('/%E0%A4%A'), null);
  assert.equal(resolve('/assets/a%20b.png'), '/site/assets/a b.png');
});

function searchModalHarness({idleReady = true, analytics = true, articles = []} = {}) {
  const source = readFileSync(new URL('./blog/blog-shared.js', import.meta.url), 'utf8');
  const listeners = new Map(), elements = new Map(), classes = new Set(), events = [];
  const input = {value:'', addEventListener(){}, focus(){doc.activeElement = input;}, tagName:'INPUT'};
  const results = {innerHTML:'', querySelectorAll:()=>[]};
  const overlay = {classList:{contains:x=>classes.has(x),add:x=>classes.add(x),remove:x=>classes.delete(x)},
    querySelector:s=>s.includes('input') ? input : results, addEventListener(){}};
  const doc = {activeElement:{tagName:'BODY'},
    getElementById:id=>elements.get(id),
    createElement:tag=>tag==='style' ? {} : overlay,
    head:{appendChild:el=>elements.set(el.id,el)}, body:{appendChild:el=>elements.set(el.id,el)},
    addEventListener:(name,fn)=>{if(!listeners.has(name))listeners.set(name,[]);listeners.get(name).push(fn);}};
  let idle;
  const win = analytics ? {gtag:(...args)=>events.push(args)} : {};
  const ctx = {DN:{ARTICLES:articles},document:doc,window:win,
    fetch:()=>Promise.resolve({ok:false}),idle:fn=>{idle=fn;},console};
  const initStart = source.indexOf('  DN.initCmdK = function () {');
  const initEnd = source.indexOf('\n  // -----------------------------------------------------------------------',initStart);
  const bootstrapStart = source.indexOf('    var cmdkReady = false;');
  const bootstrapEnd = source.indexOf('    // 2026-05-17 — wire up the SearchAction',bootstrapStart);
  assert.ok(initStart>=0 && initEnd>initStart && bootstrapStart>initEnd && bootstrapEnd>bootstrapStart);
  const searchSelectors = source.match(/^  const NAV_SEARCH_SELECTOR = [^\n]+;$/gm) || [];
  assert.equal(searchSelectors.length,1,'Search bootstrap must share its actual navigation selector');
  vm.runInNewContext(searchSelectors[0]+'\n'+source.slice(initStart,initEnd)+source.slice(bootstrapStart,bootstrapEnd),ctx);
  if(idleReady)idle();
  const dispatch = (type,extra={})=>{
    const e={key:'k',ctrlKey:true,preventDefault(){},...extra};
    // DOM listeners added during dispatch do not run on that same target/event.
    for(const fn of [...(listeners.get(type)||[])]) fn(e);
  };
  return {ctx,events,input,results,open:()=>classes.has('open'),
    key:extra=>dispatch('keydown',extra),
    click:()=>dispatch('click',{target:{closest:()=>({})}})};
}

test('shortcut search excludes unpublished entries without CSS hiding',()=>{
  const h=searchModalHarness({articles:[
    {slug:'draft-fixture',title:'Unpublished fixture',unpublished:true},
    {slug:'public-fixture',title:'Published fixture'}
  ]});
  h.key();
  assert.ok(h.results.innerHTML.includes('/blog/public-fixture'));
  assert.ok(!h.results.innerHTML.includes('/blog/draft-fixture'));
  assert.ok(!h.results.innerHTML.includes('Unpublished fixture'));
});

for(const idleReady of [false,true]) {
  test(`search shortcut opens and toggles once (${idleReady ? 'after' : 'before'} idle init)`,()=>{
    const h=searchModalHarness({idleReady});
    h.key(); assert.equal(h.open(),true); assert.equal(h.events.length,1);
    h.key(); assert.equal(h.open(),false); assert.equal(h.events.length,1);
    h.key({ctrlKey:false,metaKey:true}); assert.equal(h.open(),true); assert.equal(h.events.length,2);
  });
}
test('overlapping header handlers count one opening and preserve an active query',()=>{
  const h=searchModalHarness(); h.click();
  assert.equal(h.open(),true); assert.deepEqual(h.events,[['event','site_search_open']]);
  h.input.value='private query'; h.click(); h.ctx.DN.openSearch();
  assert.equal(h.input.value,'private query'); assert.equal(h.events.length,1);
  h.ctx.DN.closeSearch(); h.click(); assert.equal(h.events.length,2);
  assert.equal(JSON.stringify(h.events).includes('private query'),false);
});
test('search works when analytics is absent or throws',()=>{
  const h=searchModalHarness({analytics:false}); h.key(); assert.equal(h.open(),true);
  h.ctx.DN.closeSearch(); h.ctx.window.gtag=()=>{throw new Error('blocked');};
  h.click(); assert.equal(h.open(),true);
});

test('reading progress defers geometry and batches scroll and resize updates',()=>{
  const source=readFileSync(new URL('./blog/blog-shared.js',import.meta.url),'utf8');
  const start=source.indexOf('  DN.addReadingProgress = function () {');
  const end=source.indexOf('  DN.addScrollToTop = function () {',start);
  const frames=[],listeners={},elements=new Map();let reads=0,scrollTop=0,height=2000;
  const doc={getElementById:id=>elements.get(id),createElement:()=>({style:{}}),
    body:{appendChild:e=>elements.set(e.id,e)},
    documentElement:{get scrollHeight(){reads++;return height;},clientHeight:1000,get scrollTop(){return scrollTop;}},
    addEventListener:(name,fn)=>listeners[name]=fn};
  const ctx={DN:{},document:doc,window:{addEventListener:(name,fn)=>listeners[name]=fn},requestAnimationFrame:fn=>frames.push(fn)};
  vm.runInNewContext(source.slice(start,end),ctx);ctx.DN.addReadingProgress();
  assert.equal(reads,0);assert.equal(frames.length,1);
  scrollTop=250;listeners.scroll();listeners.scroll();listeners.resize();assert.equal(frames.length,1);
  frames.shift()();assert.equal(elements.get('dn-progress').style.width,'25%');assert.equal(reads,1);
  height=1500;listeners.resize();frames.shift()();assert.equal(elements.get('dn-progress').style.width,'50%');
  ctx.DN.addReadingProgress();assert.equal(elements.size,1);assert.equal(frames.length,0);
});

test('font controls defer geometry, restore visibility and preserve size selection', () => {
  const nodes = new Map(), frames = [], listeners = new Map(), storage = new Map();
  let y = 700, scrollReads = 0;
  function node() {
    return {style:{},dataset:{},children:[],attrs:{},handlers:{},
      remove(){nodes.delete(this.id);},
      setAttribute(k,v){this.attrs[k]=v;},
      appendChild(child){this.children.push(child);if(child.id) nodes.set(child.id,child);},
      addEventListener(k,v){this.handlers[k]=v;},
      querySelectorAll(){return this.children;}};
  }
  const doc = {documentElement:{lang:'zh-Hant'},head:node(),body:node(),
    getElementById:id=>nodes.get(id)||null, querySelector:()=>({}),createElement:node};
  const win = {DN:{},get scrollY(){scrollReads++;return y;},
    matchMedia:()=>({matches:true}),addEventListener:(k,v)=>listeners.set(k,v)};
  vm.runInNewContext(readFileSync(new URL('./blog/blog-article-reading.js',import.meta.url),'utf8'), {
    window:win,document:doc,location:{pathname:'/blog/acne-myths'},
    localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
    requestAnimationFrame:fn=>frames.push(fn),
  });
  win.DN.addFontSizer();
  const controls = nodes.get('dn-font-sizer');
  assert.equal(nodes.has('dn-font-size-style'),false,'default M must use the initial stylesheet');
  assert.equal(scrollReads,0);
  listeners.get('scroll')(); listeners.get('scroll')();
  assert.equal(frames.length,1);
  frames.shift()();
  assert.equal(controls.style.opacity,'1');
  assert.equal(controls.style.pointerEvents,'auto');
  const xl = controls.children.find(b=>b.dataset.size==='XL');
  xl.handlers.click();
  assert.equal(storage.get('dn-font-size'),'XL');
  assert.equal(xl.attrs['aria-pressed'],'true');
  assert.match(nodes.get('dn-font-size-style').textContent,/21px/);
  const medium = controls.children.find(b=>b.dataset.size==='M');
  medium.handlers.click();
  assert.equal(nodes.has('dn-font-size-style'),false,'returning to M removes the custom heading and body overrides');
  assert.equal(storage.get('dn-font-size'),'M');
  assert.equal(medium.attrs['aria-pressed'],'true');
  assert.equal(xl.attrs['aria-pressed'],'false');
  y=0; listeners.get('scroll')(); frames.shift()();
  assert.equal(controls.style.opacity,'0');
  assert.equal(controls.style.pointerEvents,'none');
  win.DN.addFontSizer();
  assert.equal(doc.body.children.length,1);
});

function toolbarHarness(pathname = '/', narrow = true) {
  const source = readFileSync(new URL('./blog/blog-shared.js', import.meta.url), 'utf8');
  const nodes = new Map(), listeners = new Map(), frames = [];
  let y = 0, reads = 0;
  const mobile = {matches:narrow};
  const node = () => ({style:{}, attrs:{}, setAttribute(k,v){this.attrs[k]=v;}, querySelectorAll(){return [];}});
  const document = {getElementById:id=>nodes.get(id),createElement:node,
    head:{appendChild:n=>nodes.set(n.id,n)},body:{appendChild:n=>nodes.set(n.id,n),classList:{add(){}}},
    documentElement:{get scrollHeight(){reads++;return 2400;}}};
  const window = {DN:{},matchMedia:()=>mobile,innerHeight:800,
    get scrollY(){reads++;return y;},addEventListener:(n,fn)=>listeners.set(n,fn)};
  const start=source.indexOf('  DN.addStickyCTA = function () {');
  const end=source.indexOf('\n  // -----------------------------------------------------------------------',start);
  window.DN.detectLang=()=>pathname === '/en' || pathname.startsWith('/en/') ? 'en' : 'zh';
  vm.runInNewContext(source.slice(start,end),{DN:window.DN,window,document,location:{pathname},requestAnimationFrame:fn=>frames.push(fn)});
  window.DN.addStickyCTA();
  return {nodes,listeners,frames,mobile,setY(v){y=v;},reads:()=>reads,init:()=>window.DN.addStickyCTA()};
}
test('mobile toolbar defers geometry, batches scrolls and restores navigation at the bottom',()=>{
  const h=toolbarHarness();const bar=h.nodes.get('dn-sticky-cta');
  assert.equal(h.reads(),0);assert.equal(h.frames.length,1);
  h.frames.shift()();
  h.setY(400);h.listeners.get('scroll')();h.listeners.get('scroll')();
  assert.equal(h.frames.length,1);h.frames.shift()();assert.equal(bar.style.transform,'translateY(110%)');
  h.setY(350);h.listeners.get('scroll')();h.frames.shift()();assert.equal(bar.style.transform,'translateY(0)');
  h.setY(1550);h.listeners.get('scroll')();h.frames.shift()();assert.equal(bar.style.transform,'translateY(0)');
  h.init();assert.equal(h.nodes.size,2);assert.equal(h.frames.length,0);
});
test('desktop toolbar avoids geometry and resumes safely after viewport changes',()=>{
  const h=toolbarHarness('/',false);h.listeners.get('scroll')();
  assert.equal(h.reads(),0);assert.equal(h.frames.length,0);
  h.mobile.matches=true;h.setY(400);h.listeners.get('resize')();h.frames.shift()();
  const bar=h.nodes.get('dn-sticky-cta');assert.equal(bar.style.transform,'translateY(0)');
  h.setY(500);h.listeners.get('scroll')();h.frames.shift()();assert.equal(bar.style.transform,'translateY(110%)');
  h.mobile.matches=false;h.listeners.get('resize')();const count=h.reads();h.listeners.get('scroll')();
  assert.equal(h.frames.length,0);assert.equal(h.reads(),count);assert.equal(bar.style.transform,'translateY(0)');
});
test('toolbar links and accessible labels stay in the rendered language',()=>{
  for(const path of ['/en','/en/','/en/blog/acne-myths']){
    const bar=toolbarHarness(path).nodes.get('dn-sticky-cta');
    assert.equal(bar.attrs['aria-label'],'Quick navigation');
    assert.match(bar.innerHTML,/href="\/en"/);assert.match(bar.innerHTML,/href="\/en\/blog\/"/);
    assert.match(bar.innerHTML,/href="\/en\/about"/);assert.match(bar.innerHTML,/aria-label="Latest articles"/);
    assert.match(bar.innerHTML,/>Home<\/span>/);
  }
  const bar=toolbarHarness('/blog/acne-myths').nodes.get('dn-sticky-cta');
  assert.match(bar.innerHTML,/href="\/blog\/"/);assert.match(bar.innerHTML,/aria-label="最新文章"/);
});
test('toolbar consistently excludes about and admin routes in both languages',()=>{
  for(const path of ['/about','/about/','/about.html','/en/about','/en/about/','/en/about.html','/admin.html','/en/admin']){
    const h=toolbarHarness(path);assert.equal(h.nodes.size,0,path);assert.equal(h.reads(),0);assert.equal(h.frames.length,0);
  }
});
