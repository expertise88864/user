import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';

test('optional font CSS applies on load and when already cached', () => {
  const listeners = new Map();
  const links = [false, true].map(cached => ({media:'print', sheet:cached ? {} : null,
    addEventListener(name, fn) { listeners.set(this, {name, fn}); }}));
  vm.runInNewContext(readFileSync(new URL('./assets/inline/font-loader.js', import.meta.url), 'utf8'),
    {document:{querySelectorAll(){return links;}}});
  assert.equal(links[0].media, 'print');
  assert.equal(links[1].media, 'all');
  assert.equal(listeners.get(links[0]).name, 'load');
  listeners.get(links[0]).fn();
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

function runtime(cookie) {
  const context = {
    window: {}, document: { cookie }, location: { pathname: '/blog/acne-myths' },
    navigator: { language: 'zh-TW' }, localStorage: { getItem: () => null },
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
  assert.equal(dn.detectLang(), 'en');
  assert.equal(dn.cookieGet('value'), 'a=b');
  assert.equal(dn.cookieGet('missing'), null);
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
