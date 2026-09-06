import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';

const hubContext = {window:{DN:{ARTICLES:[]}}};
vm.runInNewContext(readFileSync(new URL('./blog/blog-hub.js', import.meta.url),'utf8'), hubContext);
const searchCatalog = hubContext.window.DN.searchArticleCatalog;
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
