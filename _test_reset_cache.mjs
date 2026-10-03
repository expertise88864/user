import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

// Only disposable objects are used here: never open the real reset utility or
// access a user's browser storage while reproducing its destructive behavior.
async function resetFixture(file, options = {}) {
  const html = readFileSync(new URL(file, import.meta.url), 'utf8');
  const elements = new Map();
  function element() {
    let value = '';
    const node = {children: [], events: new Map(), dataset: {}, disabled: false,
      className: '', appendChild(child) {this.children.push(child);},
      addEventListener(name, listener) {this.events.set(name, listener);}};
    Object.defineProperty(node, 'textContent', {
      get() {return value + this.children.map(child => child.textContent).join('');},
      set(next) {value = next; this.children = [];},
    });
    return node;
  }
  for (const match of html.matchAll(/\bid="([^"]+)"/g)) elements.set(match[1], element());
  const draft = JSON.stringify({content: '<p>Unsaved author draft</p>', sha: 'original'});
  const local = new Map([['cd_admin_draft_blog/example.html', draft], ['cd-admin-pat', 'fixture-only-token']]);
  const session = new Map([['editor-session', 'fixture-session']]);
  const databases = new Set(['editor-images']);
  const cached = new Set(['cd-v201', 'cd-runtime-v199', 'another-app-cache']);
  const operations = [];
  const own = {scope: 'https://site.test/', active: {scriptURL: 'https://site.test/sw.js'},
    async unregister() {
      operations.push('unregister:site');
      if (options.registrationThrows) throw Error('fixture failure');
      return !options.registrationFalse;
    }};
  const unrelated = {scope: 'https://site.test/other/', active: {scriptURL: 'https://site.test/other/sw.js'},
    async unregister() {operations.push('unregister:other'); return true;}};
  const caches = {
    async keys() {if (options.cacheThrows) throw Error('fixture failure'); return [...cached];},
    async delete(name) {operations.push('cache:' + name); return options.cacheFalse ? false : cached.delete(name);},
  };
  function storage(map, type) {
    return {get length() {return map.size;}, clear() {operations.push('clear:' + type); map.clear();}};
  }
  const context = {
    document: {documentElement: {lang: file.startsWith('en/') ? 'en' : 'zh-Hant-TW'},
      getElementById: id => elements.get(id), createElement: element},
    location: {pathname: options.pathname || (file.startsWith('en/') ? '/en/reset-sw' : '/reset-sw'),
      origin: 'https://site.test'}, URL, console,
    navigator: options.noAPIs ? {} : {serviceWorker: {async getRegistrations() {operations.push('registrations'); return [own, unrelated];}}},
    localStorage: storage(local, 'local'), sessionStorage: storage(session, 'session'),
    indexedDB: {async databases() {operations.push('databases'); return [...databases].map(name => ({name}));},
      deleteDatabase(name) {operations.push('delete-db:' + name); databases.delete(name);}},
  };
  if (!options.noAPIs) context.caches = caches;
  context.window = context;
  const sandbox = vm.createContext(context);
  async function load() {
    for (const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) {
      const result = vm.runInContext(match[1], sandbox);
      if (result && typeof result.then === 'function') await result;
    }
  }
  await load();
  return {elements, operations, local, session, databases, cached, draft, html, load,
    async click() {
      const start = elements.get('resetStart');
      assert.ok(start, 'Reset must have an explicit start control');
      assert.ok(start.events.has('click'), 'Reset control must be wired on its own page');
      return start.events.get('click')();
    }};
}

function assertDraftsPreserved(fixture) {
  assert.equal(fixture.local.get('cd_admin_draft_blog/example.html'), fixture.draft);
  assert.equal(fixture.local.get('cd-admin-pat'), 'fixture-only-token');
  assert.equal(fixture.session.get('editor-session'), 'fixture-session');
  assert.ok(fixture.databases.has('editor-images'));
  assert.ok(!fixture.operations.some(op => /^(clear:|databases|delete-db:)/.test(op)));
}

for (const file of ['reset-sw.html', 'en/reset-sw.html']) {
  test(`${file}: opening the utility performs no destructive operations`, async () => {
    const fixture = await resetFixture(file);
    assert.deepEqual(fixture.operations, []);
    assertDraftsPreserved(fixture);
  });
  test(`${file}: explicit reset preserves author data and unrelated caches/workers`, async () => {
    const fixture = await resetFixture(file);
    await fixture.click();
    assertDraftsPreserved(fixture);
    assert.ok(!fixture.cached.has('cd-v201'));
    assert.ok(!fixture.cached.has('cd-runtime-v199'));
    assert.ok(fixture.cached.has('another-app-cache'));
    assert.ok(fixture.operations.includes('unregister:site'));
    assert.ok(!fixture.operations.includes('unregister:other'));
    assert.equal(fixture.elements.get('r4').children[0].className, 'ok');
  });
  for (const failure of ['registrationFalse', 'registrationThrows', 'cacheFalse', 'cacheThrows']) {
    test(`${file}: ${failure} cannot be reported as complete`, async () => {
      const fixture = await resetFixture(file, {[failure]: true});
      await fixture.click();
      assertDraftsPreserved(fixture);
      assert.equal(fixture.elements.get('r4').children[0].className, 'err');
      assert.equal(fixture.elements.get('resetStart').disabled, false, 'Failed reset must remain retryable');
    });
  }
  test(`${file}: unsupported APIs preserve author data`, async () => {
    const fixture = await resetFixture(file, {noAPIs: true});
    await fixture.click();
    assertDraftsPreserved(fixture);
    assert.deepEqual(fixture.operations, []);
  });
  test(`${file}: repeated initialization binds one reset and repeated clicks stay inert`, async () => {
    const fixture = await resetFixture(file);
    await fixture.load();
    await Promise.all([fixture.click(), fixture.click()]);
    assert.equal(fixture.operations.filter(op => op === 'registrations').length, 1);
    await fixture.click();
    assert.equal(fixture.operations.filter(op => op === 'registrations').length, 1);
    assertDraftsPreserved(fixture);
  });
  for (const pathname of ['/admin', '/blog/acne-myths']) {
    test(`${file}: replay on ${pathname} is inert`, async () => {
      const fixture = await resetFixture(file, {pathname});
      assert.deepEqual(fixture.operations, []);
      assert.ok(!fixture.elements.get('resetStart')?.events.has('click'));
      assertDraftsPreserved(fixture);
    });
  }
}
