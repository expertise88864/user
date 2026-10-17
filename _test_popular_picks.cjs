// 熱門推薦 (homepage recommendations) was retired 2026-10-17 by user decision.
// Guards that its public KV endpoint, settings fields, admin controls and the
// runtime read stay removed. No credentials, KV or network access.
const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const contract = JSON.parse(fs.readFileSync('_site_settings_contract.json', 'utf8'));
const read = file => fs.readFileSync(file, 'utf8');

test('the public recommendations endpoint and its KV key are gone from every serverless function', () => {
  assert.equal(fs.existsSync('api/admin/popular-picks.js'), false);
  const functions = fs.readdirSync('api', {recursive: true}).filter(file => file.endsWith('.js'));
  assert.ok(functions.includes(path.join('admin', 'site-settings.js')), 'fixture reads the real api/ tree');
  for (const file of functions) assert.doesNotMatch(read(path.join('api', file)), /popular-picks|POPULAR_PICKS/, file);
});

test('settings contract and source carry only font and homepage order', () => {
  assert.equal(Object.hasOwn(contract, 'maxPicks'), false);
  const source = JSON.parse(read(contract.source));
  assert.deepEqual(Object.keys(source).sort(), ['font', 'order', 'version']);
});

test('the shared settings grammar rejects the retired fields instead of ignoring them', () => {
  const context = {contract};
  vm.runInNewContext(read('api/admin/_site-settings.js').replace(/^import[^\n]+;\s*$/gm, '').replace(/^export \{[^\n]+\};\s*$/gm, '')
    .replace(/\bexport (class|const|function)/g, '$1') + '\nthis.settingsRecord=settingsRecord;', context);
  const current = {version: 1, font: {bodyFont: '', headFont: '', bodySize: ''}, order: []};
  assert.deepEqual(JSON.parse(JSON.stringify(context.settingsRecord(current))), current);
  for (const retired of [{legacyPicks: true, picks: ['acne-myths']}, {picks: ['acne-myths']}, {legacyPicks: false}])
    assert.throws(() => context.settingsRecord({...current, ...retired}), /invalid_settings/);
});

// The public runtime must neither define the old curated list nor request the
// removed endpoint; offline precache uses newest published articles instead.
function runtime(file) {
  const requests = [];
  const context = {URL, Promise, setTimeout, clearTimeout, fetch: url => { requests.push(String(url)); return Promise.reject(Error('fixture')); },
    addEventListener() {}, location: new URL('https://fixture.test/'), navigator: {userAgent: 'Fixture'},
    document: {addEventListener() {}, getElementById() { return null; }, querySelector() { return null; }, querySelectorAll() { return []; }}};
  context.window = context;
  vm.runInNewContext(read(file), context);
  return {DN: context.DN, requests};
}
for (const file of ['blog/blog-shared.js', 'blog/blog-shared.min.js']) test('public runtime has no 熱門推薦 list or refresh: ' + file, () => {
  const {DN, requests} = runtime(file);
  assert.equal(typeof DN.precacheArticles, 'function');
  assert.equal(DN.POPULAR_PICKS, undefined); assert.equal(DN.refreshPopularPicks, undefined);
  assert.deepEqual(requests, []);
  assert.doesNotMatch(read(file), /\/api\/admin\/popular-picks/);
});

test('admin offers no recommendations tab, controls or save kind', () => {
  const extras = read('admin/admin-extras.js');
  assert.doesNotMatch(extras, /data-tab="picks"|axPicks|熱門推薦/);
  for (const file of ['admin/settings-panel.js', 'admin/settings-drafts.js', 'api/admin/site-settings.js'])
    assert.doesNotMatch(read(file), /picks|熱門推薦/i, file);
});
