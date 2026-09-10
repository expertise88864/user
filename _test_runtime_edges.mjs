import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';

const hubContext = {window:{DN:{ARTICLES:[]}}};
vm.runInNewContext(readFileSync(new URL('./blog/blog-hub.js', import.meta.url),'utf8'), hubContext);
const searchCatalog = hubContext.window.DN.searchArticleCatalog;
test('language refresh avoids redundant mutations but translates new content and repairs labels', () => {
  let lang = 'zh-TW', langWrites = 0, attrWrites = 0;
  const attrs = new Map([['aria-label', '搜尋'], ['data-zh-aria-label', '搜尋'], ['data-en-aria-label', 'Search']]);
  const label = { getAttribute: name => attrs.get(name) ?? null,
    setAttribute: (name, value) => { attrWrites++; attrs.set(name, value); } };
  const text = { dataset: {zh:'原文',en:'Original'}, textContent:'原文' };
  const edited = { dataset: {zh:'舊文',en:'Old'}, textContent:'醫師修改內容' };
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
  content.push({dataset:{zh:'新增',en:'Added'},textContent:'新增'});
  attrs.set('aria-label', 'stale label');
  dn.applyTextOnly('en');
  assert.equal(content[2].textContent, 'Added');
  assert.equal(attrs.get('aria-label'), 'Search');
  assert.equal(langWrites, 1);
  assert.equal(attrWrites, 2);
  dn.applyTextOnly('en');
  assert.equal(attrWrites, 2);
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

test('optional font CSS applies on load and when already cached', () => {
  const listeners = new Map();
  const frames = [];
  const links = [false, true].map(cached => ({media:'print', sheet:cached ? {} : null,
    addEventListener(name, fn) { listeners.set(this, {name, fn}); }}));
  vm.runInNewContext(readFileSync(new URL('./assets/inline/font-loader.js', import.meta.url), 'utf8'),
    {document:{querySelectorAll(){return links;}},requestAnimationFrame:fn=>frames.push(fn)});
  assert.equal(links[0].media, 'print');
  assert.equal(links[1].media, 'print');
  frames.shift()();
  assert.equal(links[1].media, 'print');
  frames.shift()();
  assert.equal(links[1].media, 'all');
  assert.equal(listeners.get(links[0]).name, 'load');
  listeners.get(links[0]).fn();
  assert.equal(links[0].media, 'print');
  frames.shift()(); frames.shift()();
  assert.equal(links[0].media, 'all');
});

async function installWorker(offlineFails) {
  const listeners = {};
  let stored = false;
  const cache = {
    async add(url) {
      if (url !== '/offline.html' || offlineFails) throw new Error('network unavailable');
      stored = true;
    },
    async match() { return stored ? {} : undefined; },
  };
  const context = {self:{addEventListener(name, fn){listeners[name]=fn;},skipWaiting(){}},
    caches:{async open(){return cache;}}, URL, console};
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

function runtime(cookie, pathname = '/blog/acne-myths', language = 'zh-TW') {
  const context = {
    window: {}, document: { cookie }, location: { pathname },
    navigator: { language }, localStorage: { getItem: () => 'en' },
    console,
  };
  vm.runInNewContext(readFileSync(new URL('./blog/blog-shared.js', import.meta.url), 'utf8'), context);
  return context.window.DN;
}

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

function searchModalHarness({idleReady = true, analytics = true} = {}) {
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
  const ctx = {DN:{ARTICLES:[]},document:doc,window:win,
    fetch:()=>Promise.resolve({ok:false}),idle:fn=>{idle=fn;},console};
  const initStart = source.indexOf('  DN.initCmdK = function () {');
  const initEnd = source.indexOf('\n  // -----------------------------------------------------------------------',initStart);
  const bootstrapStart = source.indexOf('    var cmdkReady = false;');
  const bootstrapEnd = source.indexOf('    // 2026-05-17 — wire up the SearchAction',bootstrapStart);
  assert.ok(initStart>=0 && initEnd>initStart && bootstrapStart>initEnd && bootstrapEnd>bootstrapStart);
  vm.runInNewContext(source.slice(initStart,initEnd)+source.slice(bootstrapStart,bootstrapEnd),ctx);
  if(idleReady)idle();
  const dispatch = (type,extra={})=>{
    const e={key:'k',ctrlKey:true,preventDefault(){},...extra};
    // DOM listeners added during dispatch do not run on that same target/event.
    for(const fn of [...(listeners.get(type)||[])]) fn(e);
  };
  return {ctx,events,input,open:()=>classes.has('open'),
    key:extra=>dispatch('keydown',extra),
    click:()=>dispatch('click',{target:{closest:()=>({})}})};
}

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
