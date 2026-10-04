// Isolated existing KV read protocol only. No real credentials or network.
const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
const contract = JSON.parse(fs.readFileSync('_site_settings_contract.json', 'utf8'));
const catalog = {version: 1, articles: ['alpha', 'beta', 'gamma'].map(slug => ({slug, title: slug, title_en: slug}))};
const source = fs.readFileSync('api/admin/_site-settings.js', 'utf8') + '\n' + fs.readFileSync('api/admin/popular-picks.js', 'utf8');
function fixture({legacy = true, env = true, payload = {result: JSON.stringify(['beta', 'alpha'])}, status = 200, raw, fault = false} = {}) {
  const calls = [], context = {contract, settingsSource: {version: 1, legacyPicks: legacy, font: {bodyFont: '', headFont: '', bodySize: ''}, order: [], picks: ['alpha']},
    settingsCatalog: JSON.parse(JSON.stringify(catalog)), URL, Response, TextDecoder, Uint8Array, AbortController, setTimeout, clearTimeout,
    process: {env: env ? {KV_REST_API_URL: 'https://kv.fixture.test', KV_REST_API_TOKEN: 'fixture-only'} : {}},
    fetch: async (url, options) => { calls.push({url, options}); if (fault) throw Error('private provider details fixture-only');
      return raw ? new Response(raw, {status}) : Response.json(payload, {status}); }};
  vm.runInNewContext(source.replace(/^import[^\n]+;\s*$/gm, '').replace(/^export \{[^\n]+\};\s*$/gm, '')
    .replace(/\bexport (class|const|function)/g, '$1').replace('export default async function handler', 'async function handler') + '\nthis.handler=handler;', context);
  return {context, calls, request: method => context.handler({method})};
}
for (const method of ['POST', 'PUT', 'PATCH', 'DELETE', 'HEAD']) test('retired direct write endpoint rejects ' + method + ' before any KV access', async () => {
  const h = fixture(); const result = await h.request(method); assert.equal(result.status, 405);
  assert.equal(result.headers.get('allow'), 'GET'); assert.equal(result.headers.get('cache-control'), 'no-store'); assert.equal(h.calls.length, 0);
});
test('bootstrap preserves existing custom legacy selection, with GET-only bounded no-redirect transport', async () => {
  const h = fixture(), result = await h.request('GET'), body = await result.json();
  assert.deepEqual(body.picks, ['beta', 'alpha']); assert.equal(body.fallback, false); assert.equal(body.legacyStatus, 'verified');
  assert.equal(body.source, 'legacy'); assert.equal(h.calls.length, 1); const {url, options} = h.calls[0];
  assert.equal(url, 'https://kv.fixture.test/get/dn%3Apopular-picks'); assert.equal(options.method, 'GET');
  assert.equal(options.redirect, 'error'); assert.equal(options.cache, 'no-store'); assert.equal(options.headers.Authorization, 'Bearer fixture-only');
  assert.ok(options.signal); assert.equal(result.headers.get('access-control-allow-origin'), '*');
  assert.ok(result.headers.get('cache-control').startsWith('public,'));
});
test('explicit source-owned picks never access KV, even if legacy custom selection differs', async () => {
  const h = fixture({legacy: false, fault: true}), result = await h.request('GET'), body = await result.json();
  assert.deepEqual(body.picks, ['alpha']); assert.equal(body.fallback, false); assert.equal(body.source, 'site-settings'); assert.equal(h.calls.length, 0);
});
for (const options of [{env: false}, {status: 503}, {fault: true}, {raw: 'not-json'}, {raw: new Uint8Array([255])}, {raw: ' '.repeat(128001)}]) {
  test('unavailable/malformed legacy read is reported as unverified fallback, never empty: ' + JSON.stringify(options).slice(0, 60), async () => {
    const h = fixture(options), result = await h.request('GET'), body = await result.json();
    assert.deepEqual(body.picks, ['alpha']); assert.equal(body.fallback, true); assert.equal(body.source, 'legacy-fallback');
    assert.equal(body.legacyStatus, 'unavailable'); assert.ok(!JSON.stringify(body).includes('fixture-only'));
  });
}
test('only a successfully parsed null KV result is confirmed empty', async () => {
  const h = fixture({payload: {result: null}}), body = await (await h.request('GET')).json();
  assert.equal(body.legacyStatus, 'empty'); assert.equal(body.fallback, true);
});
for (const value of [[], ['private-draft'], ['alpha', 'alpha'], ['alpha', 1], 'alpha', {script: 'arbitrary'}, ['../alpha']]) {
  test('legacy value must be a complete unique public article selection: ' + JSON.stringify(value), async () => {
    const h = fixture({payload: {result: JSON.stringify(value)}}), body = await (await h.request('GET')).json();
    assert.deepEqual(body.picks, ['alpha']); assert.equal(body.fallback, true); assert.equal(body.legacyStatus, 'invalid');
  });
}
for (const endpoint of ['http://kv.fixture.test', 'https://token@kv.fixture.test', 'https://kv.fixture.test?token=private', 'https://kv.fixture.test/path']) {
  test('misconfigured KV target is never given the credential: ' + endpoint, async () => {
    const h = fixture(); h.context.process.env.KV_REST_API_URL = endpoint;
    const body = await (await h.request('GET')).json(); assert.equal(body.legacyStatus, 'unavailable'); assert.equal(h.calls.length, 0);
  });
}
test('invalid source configuration fails closed rather than falling back to another source', async () => {
  const h = fixture(); h.context.settingsSource.legacyPicks = 'false';
  const result = await h.request('GET'); assert.equal(result.status, 503); assert.equal(h.calls.length, 0);
  assert.equal(result.headers.get('cache-control'), 'no-store');
});

test('a withdrawn article is omitted from approved picks without breaking the public API', async () => {
  const h = fixture({legacy: false});
  h.context.settingsSource.picks = ['alpha', 'beta'];
  h.context.settingsSource.order = ['gamma', 'alpha', 'beta'];
  h.context.settingsCatalog.articles = h.context.settingsCatalog.articles.filter(item => item.slug !== 'alpha');
  h.context.settingsCatalog.articles.push({slug: 'delta', title: 'Delta', title_en: 'Delta'});
  const before = JSON.stringify(h.context.settingsSource), response = await h.request('GET');
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.deepEqual(body.picks, ['beta']);
  assert.equal(body.source, 'site-settings'); assert.equal(body.fallback, false);
  assert.equal(h.calls.length, 0); assert.equal(JSON.stringify(h.context.settingsSource), before);
});

test('all withdrawn recommendations produce an empty list, never unapproved replacement picks', async () => {
  const h = fixture({legacy: false});
  h.context.settingsSource.picks = ['retired-article'];
  const response = await h.request('GET'); assert.equal(response.status, 200);
  const body = await response.json(); assert.deepEqual(body.picks, []);
  assert.equal(body.source, 'site-settings'); assert.equal(body.fallback, false); assert.equal(h.calls.length, 0);
});

for (const invalid of ['../private', '<script>', '', 'a'.repeat(101)]) {
  test('historical picks still reject malformed source slug: ' + JSON.stringify(invalid), async () => {
    const h = fixture({legacy: false}); h.context.settingsSource.picks = [invalid];
    assert.equal((await h.request('GET')).status, 503); assert.equal(h.calls.length, 0);
  });
}

// Public recommendations must keep their fallback when browser fetch throws
// synchronously, as well as when the returned request rejects asynchronously.
const clientSource = fs.readFileSync('blog/blog-shared.js', 'utf8');
function clientFixture(fetch) {
  const lifecycleListeners = new Map();
  const context = {URL, Promise, fetch,
    addEventListener: (name, handler) => {
      if (!lifecycleListeners.has(name)) lifecycleListeners.set(name, []);
      lifecycleListeners.get(name).push(handler);
    },
    dispatchLifecycle: name => (lifecycleListeners.get(name) || []).forEach(handler => handler()),
    location: new URL('https://fixture.test/'),
    navigator: {userAgent: 'Fixture'}, setTimeout, clearTimeout,
    document: {addEventListener() {}, getElementById() { return null; }, querySelector() { return null; }, querySelectorAll() { return []; }}};
  context.window = context;
  vm.runInNewContext(clientSource, context);
  return context;
}
for (const [label, fetch] of [
  ['synchronous browser security failure', () => { throw Error('fixture security restriction'); }],
  ['asynchronous request rejection', () => Promise.reject(Error('fixture offline'))],
  ['unavailable response', async () => ({ok: false})],
  ['malformed JSON response', async () => ({ok: true, json: async () => { throw Error('fixture invalid JSON'); }})],
]) test('public recommendation client preserves fallback: ' + label, async () => {
  const context = clientFixture(fetch), before = JSON.stringify(context.DN.POPULAR_PICKS);
  await assert.doesNotReject(async () => context.DN.refreshPopularPicks());
  assert.equal(JSON.stringify(context.DN.POPULAR_PICKS), before);
});
test('public recommendation client still applies a successful selection', async () => {
  const context = clientFixture(async () => ({ok: true, json: async () => ({picks: ['published-fixture']})}));
  await context.DN.refreshPopularPicks();
  assert.equal(JSON.stringify(context.DN.POPULAR_PICKS), '["published-fixture"]');
});

test('public recommendations skip a departed document and resume after pageshow', async () => {
  let requests = 0;
  const context = clientFixture(async () => {
    requests++;
    return {ok: true, json: async () => ({picks: ['published-lifecycle-fixture']})};
  });
  const before = JSON.stringify(context.DN.POPULAR_PICKS);
  context.dispatchLifecycle('pagehide');
  await context.DN.refreshPopularPicks();
  assert.equal(requests, 0, 'No fetch starts after document departure');
  assert.equal(JSON.stringify(context.DN.POPULAR_PICKS), before);
  context.dispatchLifecycle('pageshow');
  await context.DN.refreshPopularPicks();
  assert.equal(requests, 1, 'A restored document can refresh normally');
  assert.equal(JSON.stringify(context.DN.POPULAR_PICKS), '["published-lifecycle-fixture"]');
});

test('a response settling after pagehide cannot mutate recommendations', async () => {
  let release;
  const context = clientFixture(() => new Promise(resolve => { release = resolve; }));
  const before = JSON.stringify(context.DN.POPULAR_PICKS);
  const pending = context.DN.refreshPopularPicks();
  context.dispatchLifecycle('pagehide');
  release({ok: true, json: async () => ({picks: ['late-departed-fixture']})});
  await pending;
  assert.equal(JSON.stringify(context.DN.POPULAR_PICKS), before);
});

test('a response settling after a BFCache-style return can update the restored document', async () => {
  let release;
  const context = clientFixture(() => new Promise(resolve => { release = resolve; }));
  const pending = context.DN.refreshPopularPicks();
  context.dispatchLifecycle('pagehide');
  context.dispatchLifecycle('pageshow');
  release({ok: true, json: async () => ({picks: ['restored-page-fixture']})});
  await pending;
  assert.equal(JSON.stringify(context.DN.POPULAR_PICKS), '["restored-page-fixture"]');
});
