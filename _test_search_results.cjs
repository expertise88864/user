// Grouped header search (blog/blog-search.js): exam headings, escaping, ranking.
const test = require('node:test'), assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs');
const source = fs.readFileSync('blog/blog-search.js', 'utf8');
const tick = () => new Promise(r => setImmediate(r));
const norm = v => String(v || '').normalize('NFKC').toLowerCase().replace(/\s+/g, ' ').trim();

const EXAM = [
  [28, 'Psoriasis', [['pustular', '3. Pustular Psoriasis（膿疱型乾癬）']], ['乾癬']],
  [52, 'Pemphigus', [['dx', '5. Diagnosis（診斷）']], []],
  [12, 'Soluble Mediators', [['ps', '16. Psoriasis（乾癬的 cytokines）'], ['bad"id', 'x 乾癬']], []],
];

function setup({ pagefind = null, index = [], exam = EXAM, en = false } = {}) {
  const window = { DN: {} };
  const head = { appendChild() {} };
  const document = { getElementById() { return null; }, createElement() { return {}; }, head };
  const fetch = url => Promise.resolve({ ok: url === '/exam/nav-search.json', json: async () => exam });
  vm.runInNewContext(source, { window, document, fetch, Promise, Object, Math, Array, String, RegExp, Error });
  let epoch = 1;
  const S = {
    results: { innerHTML: '' }, isEn: en, norm, matches: [], renders: 0,
    index: () => index, pagefind: () => pagefind,
    set(m) { this.matches = m; },
    fresh: (q, e) => e === epoch,
    rerender() { this.renders += 1; window.DN.searchRender(S, S.q, epoch); },
  };
  return { DN: window.DN, S, run(q) { S.q = q; epoch += 1; return window.DN.searchRender(S, q, epoch); } };
}

function pf(results) {
  return { search: async () => ({ results: results.map((d, i) => ({ id: 'r' + i, data: async () => d })) }) };
}

test('exam chapters match Chinese headings and aliases before Pagefind loads', async () => {
  const x = setup();
  assert.equal(x.run('乾癬'), true);
  await tick(); await tick();
  assert.equal(x.S.renders, 1, 'exam index arrival re-renders the open query');
  const html = x.S.results.innerHTML;
  assert.match(html, /考試重點/);
  assert.ok(html.indexOf('Ch.28 Psoriasis') < html.indexOf('Ch.12 Soluble'), 'alias match outranks heading-only match');
  assert.match(html, /href="\/exam\/fitz-28#pustular"/);
  assert.doesNotMatch(html, /bad"id|bad&quot;id/, 'unsafe section ids are dropped');
  assert.equal(JSON.stringify(x.S.matches.map(m => m.url)), JSON.stringify(['/exam/fitz-28', '/exam/fitz-12']));
});

test('results escape titles and excerpts but keep Pagefind highlights', async () => {
  const x = setup({ pagefind: pf([{ url: '/blog/acne.html', meta: { title: '<img src=x onerror=alert(1)>痘痘' },
    excerpt: 'A & B <mark>痘痘</mark><script>alert(1)</script>', sub_results: [] }]) });
  x.run('痘痘');
  for (let i = 0; i < 6; i += 1) await tick();
  const html = x.S.results.innerHTML;
  assert.doesNotMatch(html, /<img|<script/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;<mark>痘痘<\/mark>/);
  assert.match(html, /A &amp; B <mark>痘痘<\/mark>alert\(1\)/);
  assert.match(html, /href="\/blog\/acne"/, 'Pagefind file URLs become clean site URLs');
});

test('highlighting never splits an entity and off-site URLs collapse to /', async () => {
  const x = setup({ exam: [], index: [{ title: 'amp & amp', url: '//evil.example/x', search: 'amp & amp', meta: '' }] });
  x.run('amp');
  await tick(); await tick();
  const html = x.S.results.innerHTML;
  assert.match(html, /<mark>amp<\/mark> &amp; <mark>amp<\/mark>/);
  assert.match(html, /href="\/"/);
  assert.doesNotMatch(html, /evil\.example/);
});

test('a top exact Pagefind hit can outrank heading-only exam matches', async () => {
  const x = setup({ pagefind: pf([{ url: '/exam/fitz-52.html', meta: { title: 'Ch.52 Pemphigus' }, excerpt: '天疱瘡', sub_results: [] }]),
    exam: [[105, 'Pregnancy', [['pg', '妊娠類天疱瘡']], []], [52, 'Pemphigus', [], []]] });
  x.run('天疱瘡');
  for (let i = 0; i < 10; i += 1) await tick(); // exam index arrives, then Pagefind
  assert.equal(JSON.stringify(x.S.matches.map(m => m.url)), JSON.stringify(['/exam/fitz-52', '/exam/fitz-105']));
});

test('a stale Pagefind response never replaces a newer query', async () => {
  const pending = [];
  const slow = { search: () => new Promise(r => pending.push(r)) };
  const x = setup({ pagefind: slow, exam: [] });
  x.run('old');
  x.run('new');
  await tick();
  const shown = x.S.results.innerHTML;
  pending[0]({ results: [{ id: 'a', data: async () => ({ url: '/blog/old.html', meta: { title: 'Old' }, excerpt: '' }) }] });
  for (let i = 0; i < 6; i += 1) await tick();
  assert.equal(x.S.results.innerHTML, shown);
});

test('English pages never load or show exam results', async () => {
  const x = setup({ en: true, exam: [[22, 'Acne', [], []]],
    index: [{ title: 'Acne guide', url: '/en/blog/acne', search: 'acne guide', meta: '' }] });
  x.run('acne');
  for (let i = 0; i < 4; i += 1) await tick();
  assert.doesNotMatch(x.S.results.innerHTML, /考試重點|fitz-22/);
  assert.match(x.S.results.innerHTML, /Articles/);
  assert.equal(x.S.renders, 0, 'no exam index request');
});

test('Chinese Pagefind hits that share only single characters are dropped', async () => {
  const x = setup({ exam: [[45, 'Drugs', [['lichenoid', '9. Lichenoid（苔蘚樣藥疹）']], []]],
    pagefind: pf([{ url: '/blog/noise.html', meta: { title: 'Noise' }, excerpt: '雙<mark>樣</mark>本', sub_results: [] },
                  { url: '/blog/real.html', meta: { title: 'Real' }, excerpt: '<mark>苔</mark>​<mark>蘚樣藥疹</mark>', sub_results: [] }]) });
  x.run('苔蘚樣藥疹');
  for (let i = 0; i < 10; i += 1) await tick();
  const urls = JSON.stringify(x.S.matches.map(m => m.url));
  assert.equal(urls, JSON.stringify(['/blog/real', '/exam/fitz-45']));
});
