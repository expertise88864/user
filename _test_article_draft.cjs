// Isolated in-memory GitHub: never contacts KV, GitHub, or production collectors.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
let parse;
test.before(async () => { ({ parse } = await import('parse5')); });
const FILE = 'blog/example.html';
const HTML = '<html lang="zh-Hant"><head><title>Fixture</title></head><body><main>本機測試</main></body></html>';
const source = fs.readFileSync('api/admin/article-draft.js', 'utf8')
  .replace(/import[^;]+;/g, '').replace('export const config', 'const config')
  .replace('export default async function handler', 'async function handler');
const sha = value => crypto.createHash('sha1').update(value).digest('hex');
const blobSha = bytes => sha(Buffer.concat([Buffer.from('blob ' + bytes.length + '\0'), bytes]));
const publicationPolicy = JSON.parse(fs.readFileSync('_delivery_policy.json', 'utf8'));
const publicationContext = { URL, Date };
vm.runInNewContext(fs.readFileSync('api/admin/_article-publication.js', 'utf8').replace('export async function', 'async function') + '\nthis.observePublication=observePublication;', publicationContext);
function fixture() {
  const calls = [], blobs = new Map(), trees = new Map(), commits = new Map(), refs = new Map();
  const store = value => { const bytes = Buffer.isBuffer(value) ? value : Buffer.from(value); const id = blobSha(bytes); blobs.set(id, bytes); return id; };
  const mainBlob = store(HTML), mainTree = sha('main-tree'), main = sha('main');
  trees.set(mainTree, new Map([[FILE, mainBlob]])); commits.set(main, { tree: { sha: mainTree }, parents: [] }); refs.set('main', main);
  const h = { calls, blobs, trees, commits, refs, mainBlob, main, session: true, race: false, corrupt: false, corruptRecord: false, corruptRequest: false, outcomeUnknown: false, failBlob: false, failWrite: null };
  async function fetch(url, options) {
    assert.equal(new URL(url).origin, 'https://api.github.com');
    assert.equal(options.redirect, 'error');
    assert.equal(options.headers.Authorization, 'Bearer fixture-secret');
    const u = new URL(url), path = decodeURIComponent(u.pathname.replace('/repos/expertise88864/user/', ''));
    if (path.startsWith('contents/')) assert.equal(options.headers.Accept, 'application/vnd.github.object+json', 'large Contents files require the supported object media type');
    const body = options.body && JSON.parse(options.body);
    calls.push({ method: options.method, path, body });
    if (options.method !== 'GET' && path === h.failWrite) return Response.json({ message: 'private upstream detail' }, { status: 503 });
    let result;
    if (path === 'actions/runs') {
      result = { workflow_runs: h.workflowRuns || [] };
    } else if (path.includes('/jobs')) {
      result = { jobs: h.workflowJobs?.get(Number(path.split('/')[2])) || [] };
    } else if (path === 'deployments') {
      result = h.deployments || [];
    } else if (path.startsWith('deployments/') && path.endsWith('/statuses')) {
      result = h.deploymentStatuses || [];
    } else if (path === 'git/matching-refs/heads/drafts/') {
      result = [...refs].filter(([name]) => name.startsWith('drafts/')).map(([name, id]) => ({ ref: 'refs/heads/' + name, object: { sha: id } }));
    } else if (path.startsWith('git/ref/heads/')) {
      const value = refs.get(path.slice(14));
      if (!value) return Response.json({}, { status: 404 });
      result = { object: { sha: value } };
    } else if (path.startsWith('contents/')) {
      const commit = commits.get(u.searchParams.get('ref'));
      assert.ok(commit, 'read must use a known immutable commit');
      const id = trees.get(commit.tree.sha).get(path.slice(9));
      if (!id) return Response.json({}, { status: 404 });
      const bytes = blobs.get(id);
      result = { type: 'file', sha: id, size: bytes.length, encoding: 'base64',
        content: ((h.corrupt && path === 'contents/' + FILE) || (h.corruptRecord && path.startsWith('contents/.cms-drafts/')) ||
          (h.corruptRequest && path.startsWith('contents/.cms-requests/'))) && u.searchParams.get('ref') !== h.main ? Buffer.from('corrupt').toString('base64') : bytes.toString('base64') };
      if (bytes.length > 1_000_000) { result.encoding = 'none'; result.content = ''; }
    } else if (path.startsWith('git/blobs/')) {
      if (h.failBlob) return Response.json({ message: 'private upstream detail' }, { status: 503 });
      const id = path.slice(10), bytes = blobs.get(id);
      assert.ok(bytes); result = { sha: id, size: bytes.length, encoding: 'base64', content: bytes.toString('base64') };
    } else if (path.startsWith('git/commits/')) {
      const value = commits.get(path.slice(12));
      result = { sha: path.slice(12), ...value, parents: (value.parents || []).map(sha => ({ sha })) };
    } else if (path.startsWith('git/trees/')) {
      const id = path.slice(10);
      result = { sha: id, truncated: false, tree: [...trees.get(id)].map(([path, sha]) => ({
        path, sha, type: 'blob', mode: '100644', size: blobs.get(sha).length,
      })) };
    }
    else if (path === 'git/blobs') result = { sha: store(Buffer.from(body.content, 'base64')) };
    else if (path === 'git/trees') {
      const tree = new Map(trees.get(body.base_tree));
      for (const entry of body.tree) {
        if (entry.sha === null) tree.delete(entry.path);
        else tree.set(entry.path, entry.sha || store(entry.content));
      }
      const id = sha(JSON.stringify([...tree])); trees.set(id, tree); result = { sha: id };
    } else if (path === 'git/commits') {
      const id = sha(JSON.stringify(body)); commits.set(id, { tree: { sha: body.tree }, parents: body.parents }); result = { sha: id };
    } else if (path === 'git/refs' || path.startsWith('git/refs/heads/')) {
      const branch = path === 'git/refs' ? body.ref.replace('refs/heads/', '') : path.slice(15);
      assert.equal(branch, 'drafts/example', 'write must never target main or an arbitrary ref');
      assert.ok(body.force === undefined || body.force === false);
      if (h.race || (path === 'git/refs' && refs.has(branch)) ||
          (path !== 'git/refs' && commits.get(body.sha).parents[0] !== refs.get(branch))) return Response.json({}, { status: 422 });
      refs.set(branch, body.sha); result = { object: { sha: body.sha } };
      if (h.outcomeUnknown) throw Error('private provider detail / fixture-secret');
    } else assert.fail('unexpected GitHub API path: ' + path);
    if (h.tamper) result = h.tamper(path, result);
    return Response.json(result);
  }
  const context = { URL, Request, Response, TextEncoder, TextDecoder, Uint8Array, AbortController,
    setTimeout, clearTimeout, atob, btoa, crypto: crypto.webcrypto, fetch, parse,
    observePublication: publicationContext.observePublication, publicationPolicy,
    getSession: async () => h.session ? { pat: 'fixture-secret', login: 'expertise88864' } : null };
  vm.runInNewContext(source + '\nthis.handler=handler;', context);
  h.request = (input, extra = {}) => context.handler(new Request('https://editor.test/api/admin/article-draft' + (input ? '' : '?file=' + FILE + (extra.query || '')), {
    method: input ? 'POST' : 'GET', headers: { origin: 'https://editor.test', 'content-type': 'application/json', ...extra.headers },
    ...(input ? { body: JSON.stringify(input) } : {}), ...Object.fromEntries(Object.entries(extra).filter(([k]) => k !== 'headers' && k !== 'query')),
  }));
  h.input = (extra = {}) => ({ file: FILE, expectedHead: null, baseSha: mainBlob, content: HTML.replace('本機測試', '已編輯'), media: [], ...extra });
  return h;
}
function verifiedProduction(h) {
  h.workflowRuns = publicationPolicy.workflows.map((entry, index) => ({ id: 100 + index, run_attempt: 1,
    path: entry.path, head_sha: h.main, head_branch: 'main', event: 'push',
    head_repository: { full_name: publicationPolicy.repository }, status: 'completed', conclusion: 'success' }));
  h.workflowJobs = new Map(h.workflowRuns.map((run, index) => [run.id, publicationPolicy.workflows[index].jobs.map(name => ({
    name, head_sha: h.main, status: 'completed', conclusion: (publicationPolicy.workflows[index].main_skips || []).includes(name) ? 'skipped' : 'success',
    steps: publicationPolicy.workflows[index].steps[name].required.map(name => ({ name, status: 'completed', conclusion: 'success' })),
  }))]));
  h.deployments = [{ id: 700, sha: h.main, environment: 'Production', production_environment: true, creator: { login: 'vercel[bot]' } }];
  h.deploymentStatuses = [{ id: 800, state: 'success', creator: { login: 'vercel[bot]' }, environment_url: 'https://chendermatologist-fixture-expertise88864s-projects.vercel.app' }];
}
for (const address of ['javascript:alert(1)', 'JavaScript:alert(1)', 'java&#115;cript:alert(1)',
  'java&#9;script:alert(1)', 'vbscript:msgbox(1)', 'data:text/html,test', 'blob:local', 'file:///tmp/link']) {
  test('source drafts reject active link schemes before repository writes: '+address,async()=>{
    const h=fixture();
    const content=HTML.replace('本機測試','<a href="'+address+'">Fixture link</a>');
    assert.equal((await h.request(h.input({content}))).status,400);
    assert.ok(h.calls.every(call=>call.method==='GET'),'Unsafe source must not create objects or update refs');
  });
}
for (const address of ['https://example.test/paper','http://example.test/paper','mailto:example@example.test',
  'tel:+88612345678','#main-content','/blog/acne-myths']) {
  test('source drafts preserve ordinary reference links: '+address,async()=>{
    const h=fixture();
    const content=HTML.replace('本機測試','<a href="'+address+'">Fixture link</a>');
    const response=await h.request(h.input({content}));
    assert.equal(response.status,200);
    const saved=await response.json();assert.equal(h.blobs.get(saved.blobSha).toString(),content);
  });
}
function putMain(h, file, content) {
  const bytes = Buffer.from(content), id = blobSha(bytes); h.blobs.set(id, bytes);
  h.trees.get(h.commits.get(h.main).tree.sha).set(file, id);
  return id;
}
async function newVersionFixture() {
  const h = fixture();
  putMain(h, '.cms-delivery.json', '{"version":1,"requests":[]}\n');
  let saved = await (await h.request(h.input())).json();
  saved = await (await h.request(publicationInput(saved))).json();
  const oldHead = saved.head, oldMain = h.main;
  const nextMain = sha('published main'), nextTree = sha('published tree');
  const tree = new Map(h.trees.get(h.commits.get(oldMain).tree.sha));
  const bytes = Buffer.from(HTML.replace('本機測試', '正式版內容')), published = blobSha(bytes);
  h.blobs.set(published, bytes); tree.set(FILE, published);
  h.trees.set(nextTree, tree); h.commits.set(nextMain, { tree: { sha: nextTree }, parents: [oldMain] });
  h.main = nextMain; h.mainBlob = published; h.refs.set('main', nextMain);
  verifiedProduction(h);
  h.newInput = extra => ({ file: FILE, action: 'new-version', expectedHead: oldHead,
    expectedBlob: saved.blobSha, expectedMain: nextMain, expectedMainBlob: published, confirmed: true, ...extra });
  h.oldHead = oldHead; h.start = h.calls.length;
  return h;
}
test('new editing cycle copies verified production, retains history, removes only the old draft request', async () => {
  const h = await newVersionFixture();
  assert.equal((await (await h.request()).json()).conflict, true, 'reproduces the post-publication stale base');
  const response = await h.request(h.newInput()), result = await response.json();
  assert.equal(response.status, 200); assert.equal(result.verified, true); assert.equal(result.published, false);
  assert.equal(result.blobSha, h.mainBlob); assert.equal(result.baseSha, h.mainBlob);
  assert.equal(h.commits.get(result.head).parents[0], h.oldHead); assert.equal(h.refs.get('main'), h.main);
  const after = await (await h.request()).json();
  assert.equal(after.conflict, false); assert.equal(after.request, null); assert.equal(after.metadata, null);
  assert.equal(after.content, h.blobs.get(h.mainBlob).toString());
  assert.ok(h.trees.get(h.commits.get(h.oldHead).tree.sha).has('.cms-requests/example.json'), 'old request remains in history');
  const writes = h.calls.slice(h.start).filter(call => call.method !== 'GET');
  assert.deepEqual(writes.map(call => call.path), ['git/trees', 'git/commits', 'git/refs/heads/drafts/example']);
  assert.ok(writes[0].body.tree.every(entry => entry.path !== '.cms-delivery.json'));
});
test('new version fails closed before writes for unverified production, active receipts and stale expectations', async () => {
  for (const kind of ['ci', 'deployment', 'receipt', 'missing-receipt', 'bad-receipt', 'main', 'blob', 'head', 'confirm', 'extra', 'noindex', 'symlink', 'truncated']) {
    const h = await newVersionFixture(); let extra = {};
    if (kind === 'ci') h.workflowRuns[0].conclusion = 'failure';
    if (kind === 'deployment') h.deploymentStatuses[0].state = 'pending';
    if (kind === 'receipt') putMain(h, '.cms-delivery.json', JSON.stringify({ version: 1, requests: [{ file: FILE }] }));
    if (kind === 'missing-receipt') h.trees.get(h.commits.get(h.main).tree.sha).delete('.cms-delivery.json');
    if (kind === 'bad-receipt') putMain(h, '.cms-delivery.json', '{"version":2,"requests":[]}');
    if (kind === 'main') extra.expectedMain = sha('stale');
    if (kind === 'blob') extra.expectedMainBlob = sha('stale');
    if (kind === 'head') extra.expectedHead = sha('stale');
    if (kind === 'confirm') extra.confirmed = false;
    if (kind === 'extra') extra.content = 'unapproved content';
    if (kind === 'noindex') { const id = putMain(h, FILE, HTML.replace('</head>', '<meta name="robots" content="noindex"></head>')); extra.expectedMainBlob = id; }
    if (['symlink', 'truncated'].includes(kind)) h.tamper = (path, result) => {
      if (path.startsWith('git/trees/')) {
        if (kind === 'truncated') result.truncated = true;
        else result.tree.find(entry => entry.path === FILE).mode = '120000';
      }
      return result;
    };
    const before = h.calls.length, response = await h.request(h.newInput(extra));
    assert.ok(response.status >= 400, kind);
    assert.ok(h.calls.slice(before).every(call => call.method === 'GET'), kind + ' must not write');
    assert.equal(h.refs.get('drafts/example'), h.oldHead);
  }
});
test('new version rechecks main before writes and refuses concurrent draft updates without force', async () => {
  for (const kind of ['main', 'draft']) {
    const h = await newVersionFixture();
    if (kind === 'main') h.tamper = (path, result) => {
      if (path.startsWith('git/trees/')) h.refs.set('main', sha('advanced main'));
      return result;
    };
    else h.race = true;
    const response = await h.request(h.newInput());
    assert.equal(response.status, 409, kind);
    assert.equal(h.refs.get('drafts/example'), h.oldHead);
    if (kind === 'main') assert.ok(h.calls.slice(h.start).every(call => call.method === 'GET'));
  }
});
test('accepted new version with a lost response is unknown, never retried or reported verified', async () => {
  const h = await newVersionFixture(); h.outcomeUnknown = true;
  const response = await h.request(h.newInput());
  assert.equal(response.status, 502); assert.notEqual(h.refs.get('drafts/example'), h.oldHead);
  assert.equal(h.calls.slice(h.start).filter(call => call.method === 'PATCH').length, 1);
  assert.ok(!(await response.text()).includes('fixture-secret'));
});
test('new version adopts only verified ordinary production images, preserving their exact bytes', async () => {
  for (const kind of ['valid', 'bad-digest', 'executable', 'advance-after-patch']) {
    const h = await newVersionFixture();
    const bytes = Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64');
    const digest = crypto.createHash('sha256').update(bytes).digest('hex');
    const path = 'blog/images/example/' + (kind === 'bad-digest' ? '0'.repeat(64) : digest) + '.gif';
    const id = blobSha(bytes); h.blobs.set(id, bytes); h.trees.get(h.commits.get(h.main).tree.sha).set(path, id);
    const published = putMain(h, FILE, HTML.replace('</main>', '<img src="/' + path + '" alt="Fixture"></main>'));
    h.tamper = (apiPath, result) => {
      if (kind === 'executable' && apiPath.startsWith('git/trees/')) result.tree.find(entry => entry.path === path).mode = '100755';
      if (kind === 'advance-after-patch' && apiPath.startsWith('git/refs/heads/')) {
        const next = sha('concurrent production'); h.commits.set(next, h.commits.get(h.main)); h.refs.set('main', next);
      }
      return result;
    };
    const response = await h.request(h.newInput({ expectedMainBlob: published }));
    if (kind === 'valid') {
      assert.equal(response.status, 200); const result = await response.json();
      const loaded = await (await h.request()).json();
      assert.equal(loaded.blobSha, published); assert.equal(loaded.assets.length, 1);
      assert.equal(loaded.media[0].base64, bytes.toString('base64')); assert.equal(loaded.media[0].path, path);
      assert.equal(h.trees.get(h.commits.get(result.head).tree.sha).get(path), id);
    } else if (kind === 'advance-after-patch') {
      assert.equal(response.status, 502); assert.equal((await response.json()).error, 'new_version_not_verified');
      assert.equal(h.calls.slice(h.start).filter(call => call.method === 'PATCH').length, 1);
    } else {
      assert.ok(response.status >= 400, kind);
      assert.ok(h.calls.slice(h.start).every(call => call.method === 'GET'));
    }
  }
});
test('a missing article is not reported as published and can become a new draft', async () => {
  const h = fixture(); h.trees.get(h.commits.get(h.main).tree.sha).delete(FILE);
  const response = await h.request(), body = await response.json();
  assert.equal(response.status, 200); assert.equal(body.status, 'not_created');
  assert.equal(body.published, false); assert.equal(body.content, null); assert.equal(body.baseSha, null);
  assert.ok(h.calls.every(c => c.method === 'GET'));
  const saved = await (await h.request(h.input({ baseSha: null, metadata: { title_en: 'New article', tag: '標籤', tag_en: 'Topic', cat: 'myth', date: '2026-09-30' } }))).json();
  assert.equal(saved.status, 'cloud_draft'); assert.equal(saved.verified, true); assert.equal(saved.published, false);
  assert.equal(h.refs.get('main'), h.main);
});
test('first save creates a complete verified draft and never writes main', async () => {
  const h = fixture(); const result = await h.request(h.input()); const body = await result.json();
  assert.equal(result.status, 200); assert.equal(body.status, 'cloud_draft');
  assert.equal(body.verified, true); assert.equal(body.published, false); assert.equal(h.refs.get('main'), h.main);
  const ref = h.calls.findIndex(c => c.path === 'git/refs');
  assert.ok(ref > h.calls.findIndex(c => c.path === 'git/trees'));
  assert.ok(h.calls.slice(ref + 1).some(c => c.path === 'contents/' + FILE), 'immutable accepted content must be verified');
  const loaded = await (await h.request()).json();
  assert.equal(loaded.head, body.head); assert.equal(loaded.baseSha, h.mainBlob); assert.equal(loaded.content, h.input().content);
});
const publicationInput = (saved, action = 'review', extra = {}) => ({
  file: FILE, action, expectedHead: saved.head, expectedBlob: saved.blobSha, baseSha: saved.baseSha,
  ...(action === 'unpublish' || action === 'cancel' ? { confirmed: true } : { contentApproved: true }), ...extra,
});
test('main source existence is not reported as verified production publication', async () => {
  const h = fixture(), result = await (await h.request()).json();
  assert.equal(result.sourceOnMain, true); assert.equal(result.mainBlobSha, h.mainBlob);
  assert.equal(result.published, false); assert.equal(result.deploymentVerified, false);
  assert.ok(h.calls.every(c => c.method === 'GET'));
});
test('main indexability honors live robots directives and rejects ambiguous attributes', async () => {
  const cases = [
    ['<meta content="none" name="GOOGLEBOT">', false],
    ['<meta name="robots" content="index,follow"><meta name="robots" content="NOINDEX">', false],
    ['<meta name="robots" content="index" content="noindex">', false],
    ['<meta name="googlebot" name="robots" content="noindex">', false],
    ['<template><meta name="robots" content="noindex"></template>', true],
    ['<!-- <meta name="robots" content="noindex"> -->', true],
    ['<meta name="robots" content="index,follow">', true],
  ];
  for (const [markup, indexable] of cases) {
    const h = fixture(), bytes = Buffer.from(HTML.replace('</head>', markup + '</head>')), blob = blobSha(bytes);
    h.blobs.set(blob, bytes); h.trees.get(h.commits.get(h.main).tree.sha).set(FILE, blob);
    const response = await h.request(), result = await response.json();
    assert.equal(response.status, 200); assert.equal(result.mainIndexable, indexable, markup);
    assert.equal(result.published, false); assert.ok(h.calls.every(call => call.method === 'GET'));
  }
});
test('explicit publication observation is authenticated, read-only and cannot infer deployment from main', async () => {
  const h = fixture(), response = await h.request(null, { query: '&mode=publication' }), result = await response.json();
  assert.equal(response.status, 200); assert.equal(result.publication.state, 'ci_missing');
  assert.equal(result.publication.mainSha, h.main); assert.equal(result.publication.mainBlobSha, h.mainBlob);
  assert.equal(result.publication.published, false); assert.equal(result.publication.deploymentVerified, false);
  assert.equal(result.content, undefined); assert.equal(result.media, undefined);
  assert.ok(h.calls.every(call => call.method === 'GET'));
  h.session = false;
  const before = h.calls.length;
  assert.equal((await h.request(null, { query: '&mode=publication' })).status, 401);
  assert.equal(h.calls.length, before);
});
test('publication observation distinguishes indexable deployed source, noindex and a newer draft', async () => {
  const h = fixture();
  h.workflowRuns = publicationPolicy.workflows.map((entry, index) => ({ id: 100 + index, run_attempt: 1,
    path: entry.path, head_sha: h.main, head_branch: 'main', event: 'push',
    head_repository: { full_name: publicationPolicy.repository }, status: 'completed', conclusion: 'success' }));
  h.workflowJobs = new Map(h.workflowRuns.map((run, index) => [run.id, publicationPolicy.workflows[index].jobs.map(name => ({
    name, head_sha: h.main, status: 'completed', conclusion: (publicationPolicy.workflows[index].main_skips || []).includes(name) ? 'skipped' : 'success',
    steps: publicationPolicy.workflows[index].steps[name].required.map(name => ({ name, status: 'completed', conclusion: 'success' })),
  }))]));
  h.deployments = [{ id: 700, sha: h.main, environment: 'Production', production_environment: true, creator: { login: 'vercel[bot]' } }];
  h.deploymentStatuses = [{ id: 800, state: 'success', creator: { login: 'vercel[bot]' }, environment_url: 'https://chendermatologist-fixture-expertise88864s-projects.vercel.app' }];
  let observed = await (await h.request(null, { query: '&mode=publication' })).json();
  assert.equal(observed.publication.state, 'live'); assert.equal(observed.publication.published, true);
  const draft = await (await h.request(h.input())).json();
  observed = await (await h.request(null, { query: '&mode=publication' })).json();
  assert.equal(observed.head, draft.head); assert.equal(observed.publication.state, 'live');
  assert.equal(observed.publication.published, false); assert.equal(observed.publication.matchesLoadedVersion, false);
  const html = HTML.replace('</head>', '<meta name="robots" content="noindex,follow"></head>');
  const bytes = Buffer.from(html), noindex = blobSha(bytes); h.blobs.set(noindex, bytes);
  h.trees.get(h.commits.get(h.main).tree.sha).set(FILE, noindex);
  observed = await (await h.request(null, { query: '&mode=publication' })).json();
  assert.equal(observed.publication.state, 'live_noindex'); assert.equal(observed.publication.published, false);
  assert.ok(h.calls.filter(call => call.path.startsWith('actions/') || call.path.startsWith('deployments')).every(call => call.method === 'GET'));
});
test('author request binds immutable article and manifest, without changing article or main', async () => {
  const h = fixture(), saved = await (await h.request(h.input())).json(), before = h.calls.length;
  const response = await h.request(publicationInput(saved)), result = await response.json();
  assert.equal(response.status, 200); assert.equal(result.verified, true); assert.equal(result.published, false);
  assert.equal(result.blobSha, saved.blobSha); assert.notEqual(result.head, saved.head);
  assert.equal(result.request.status, 'awaiting_review');
  const tree = h.trees.get(h.commits.get(result.head).tree.sha);
  assert.equal(tree.get(FILE), saved.blobSha);
  const record = JSON.parse(h.blobs.get(tree.get('.cms-requests/example.json')).toString());
  assert.equal(record.draftHead, saved.head); assert.equal(record.blobSha, saved.blobSha);
  assert.equal(record.manifestSha, tree.get('.cms-drafts/example.json')); assert.equal(record.approvedBy, 'expertise88864');
  assert.equal(record.contentApproved, true); assert.equal(h.refs.get('main'), h.main);
  assert.ok(h.calls.slice(before).filter(c => c.method !== 'GET').every(c => !c.path.includes('main')));
  const loaded = await (await h.request()).json(); assert.equal(loaded.request.status, 'awaiting_review');
  const observed = await (await h.request(null, { query: '&mode=status' })).json(); assert.equal(observed.request.blobSha, saved.blobSha);
});
test('request confirmation, revision and action contract fail before Git mutations', async () => {
  const h = fixture(), saved = await (await h.request(h.input())).json();
  for (const input of [publicationInput(saved, 'review', { contentApproved: false }),
    publicationInput(saved, 'review', { expectedBlob: '0'.repeat(40) }),
    publicationInput(saved, 'review', { branch: 'main' }), publicationInput(saved, 'arbitrary'),
    publicationInput(saved, 'unpublish', { confirmed: false })]) {
    const before = h.calls.length, response = await h.request(input);
    assert.ok([400, 409].includes(response.status)); assert.ok(h.calls.slice(before).every(c => c.method === 'GET'));
    assert.equal(h.refs.get('drafts/example'), saved.head);
  }
  h.session = false; assert.equal((await h.request(publicationInput(saved))).status, 401);
  h.session = true; assert.equal((await h.request(publicationInput(saved), { headers: { origin: 'https://elsewhere.test' } })).status, 403);
});
test('scheduled request requires an explicit bounded future UTC time', async () => {
  const h = fixture(), saved = await (await h.request(h.input())).json();
  for (const scheduledAt of [undefined, 'tomorrow', '2020-01-01T00:00:00.000Z',
    new Date(Date.now() + 366 * 86400_000).toISOString(), new Date(Date.now() + 3600_000).toISOString().replace('Z', '+00:00')]) {
    const before = h.calls.length;
    assert.equal((await h.request(publicationInput(saved, 'schedule', { scheduledAt }))).status, 400);
    assert.ok(h.calls.slice(before).every(c => c.method === 'GET'));
  }
  const scheduledAt = new Date(Date.now() + 3600_000).toISOString();
  const result = await (await h.request(publicationInput(saved, 'schedule', { scheduledAt }))).json();
  assert.equal(result.request.status, 'schedule_requested'); assert.equal(result.request.scheduledAt, scheduledAt);
  assert.equal(result.published, false); assert.equal(h.refs.get('main'), h.main);
});
test('a later edit deletes its request and needs new author confirmation', async () => {
  const h = fixture(), saved = await (await h.request(h.input())).json();
  const requested = await (await h.request(publicationInput(saved))).json();
  const edited = await (await h.request(h.input({ expectedHead: requested.head, content: HTML.replace('本機測試', '再修改') }))).json();
  assert.equal(edited.verified, true);
  assert.equal(h.trees.get(h.commits.get(edited.head).tree.sha).has('.cms-requests/example.json'), false);
  const loaded = await (await h.request()).json(); assert.equal(loaded.request, null);
  assert.equal((await h.request(publicationInput(requested))).status, 409);
  const next = await (await h.request(publicationInput(edited))).json(); assert.equal(next.request.status, 'awaiting_review');
});
test('cancellation removes only the saved request and advances CAS without publishing', async () => {
  const h = fixture(), saved = await (await h.request(h.input())).json();
  const requested = await (await h.request(publicationInput(saved))).json();
  const cancelled = await (await h.request(publicationInput(requested, 'cancel'))).json();
  assert.equal(cancelled.verified, true); assert.equal(cancelled.request, null); assert.equal(cancelled.blobSha, saved.blobSha);
  assert.equal((await (await h.request()).json()).request, null); assert.equal(h.refs.get('main'), h.main);
  const before = h.calls.length;
  assert.equal((await h.request(publicationInput(cancelled, 'cancel'))).status, 409);
  assert.ok(h.calls.slice(before).every(c => c.method === 'GET'));
});
test('an active request cannot be silently replaced and a concurrent request cannot force the ref', async () => {
  const h = fixture(), saved = await (await h.request(h.input())).json();
  const requested = await (await h.request(publicationInput(saved))).json(), before = h.calls.length;
  assert.equal((await h.request(publicationInput(requested, 'unpublish'))).status, 409);
  assert.ok(h.calls.slice(before).every(c => c.method === 'GET'));
  const other = fixture(), initial = await (await other.request(other.input())).json(); other.race = true;
  assert.equal((await other.request(publicationInput(initial))).status, 409);
  assert.equal(other.refs.get('drafts/example'), initial.head); assert.equal(other.calls.filter(c => c.method === 'PATCH').length, 1);
});
test('an unrelated successor commit invalidates a request even if article bytes are unchanged', async () => {
  const h = fixture(), saved = await (await h.request(h.input())).json(), requested = await (await h.request(publicationInput(saved))).json();
  const changed = sha('unrelated-after-request'); h.commits.set(changed, { ...h.commits.get(requested.head), parents: [requested.head] });
  h.refs.set('drafts/example', changed); const before = h.calls.length;
  const result = await (await h.request(null, { query: '&mode=status' })).json(); assert.equal(result.request.status, 'invalidated');
  assert.ok(h.calls.slice(before).every(c => c.method === 'GET'));
});
test('unpublish is a request only, and a new never-published article cannot be withdrawn', async () => {
  const h = fixture(), saved = await (await h.request(h.input())).json();
  const withdrawn = await (await h.request(publicationInput(saved, 'unpublish'))).json();
  assert.equal(withdrawn.request.status, 'unpublish_requested'); assert.equal(withdrawn.published, false);
  assert.equal(h.refs.get('main'), h.main); assert.equal(h.trees.get(h.commits.get(withdrawn.head).tree.sha).get(FILE), saved.blobSha);
  const fresh = fixture(); fresh.trees.get(fresh.commits.get(fresh.main).tree.sha).delete(FILE);
  const initial = await (await fresh.request(fresh.input({ baseSha: null,
    metadata: { title_en: 'New', tag: '標籤', tag_en: 'Topic', cat: 'note', date: '2026-09-30' } }))).json();
  const before = fresh.calls.length;
  assert.equal((await fresh.request(publicationInput(initial, 'unpublish'))).status, 400);
  assert.ok(fresh.calls.slice(before).every(c => c.method === 'GET'));
});
for (const path of ['git/trees', 'git/commits', 'git/refs/heads/drafts/example']) test('request provider failure at ' + path + ' never claims acceptance or changes main', async () => {
  const h = fixture(), saved = await (await h.request(h.input())).json(); h.failWrite = path;
  const result = await h.request(publicationInput(saved)); assert.equal(result.status, 502);
  assert.equal(h.refs.get('drafts/example'), saved.head); assert.equal(h.refs.get('main'), h.main);
  assert.ok(!(await result.text()).includes('private upstream detail'));
});
test('an ambiguous accepted request is not retried and can be verified by a later read', async () => {
  const h = fixture(), saved = await (await h.request(h.input())).json(); h.outcomeUnknown = true;
  const response = await h.request(publicationInput(saved)); assert.equal(response.status, 502);
  assert.equal(h.calls.filter(c => c.method === 'PATCH').length, 1);
  assert.equal((await (await h.request()).json()).request.status, 'awaiting_review');
  assert.equal(h.refs.get('main'), h.main);
});
test('failed immutable request verification stays ambiguous and preserves recovery by exact reload', async () => {
  const h = fixture(), saved = await (await h.request(h.input())).json(); h.corruptRequest = true;
  const response = await h.request(publicationInput(saved)); assert.equal(response.status, 502);
  assert.equal((await response.json()).error, 'request_not_verified'); assert.notEqual(h.refs.get('drafts/example'), saved.head);
  assert.equal(h.calls.filter(c => c.method === 'PATCH').length, 1);
  h.corruptRequest = false; assert.equal((await (await h.request()).json()).request.status, 'awaiting_review');
  assert.equal(h.refs.get('main'), h.main);
});
for (const path of ['git/blobs', 'git/trees', 'git/commits', 'git/refs']) test('draft creation provider failure at ' + path + ' preserves main and never exposes a partial draft branch', async () => {
  const h = fixture(); h.failWrite = path;
  const response = await h.request(h.input()); assert.equal(response.status, 502);
  assert.equal(h.refs.get('main'), h.main); assert.equal(h.refs.has('drafts/example'), false);
  assert.equal(h.calls.filter(c => c.path === path && c.method !== 'GET').length, 1);
  assert.ok(!(await response.text()).includes('private upstream detail'));
});
test('new-article metadata is required, validated and retained with the immutable draft', async () => {
  const h = fixture(); h.trees.get(h.commits.get(h.main).tree.sha).delete(FILE);
  const metadata = { title_en: 'New article', tag: '分類', tag_en: 'Topic', cat: 'note', date: '2026-09-30' };
  assert.equal((await h.request(h.input({ baseSha: null }))).status, 400);
  for (const bad of [{ ...metadata, date: '2026-02-30' }, { ...metadata, cat: 'arbitrary' }, { ...metadata, branch: 'main' }, { ...metadata, title_en: '' }]) {
    assert.equal((await h.request(h.input({ baseSha: null, metadata: bad }))).status, 400);
  }
  assert.ok(h.calls.every(c => c.method === 'GET'));
  const first = await (await h.request(h.input({ baseSha: null, metadata }))).json();
  assert.equal(first.verified, true); assert.deepEqual(first.metadata, metadata);
  assert.equal((await h.request(h.input({ baseSha: null, expectedHead: first.head }))).status, 200);
  const loaded = await (await h.request()).json(); assert.deepEqual(loaded.metadata, metadata);
  assert.equal(h.refs.get('main'), h.main);
});
test('existing product category remains product across save, reload and later editing',async()=>{
  const h=fixture();h.trees.get(h.commits.get(h.main).tree.sha).delete(FILE);
  const metadata={title_en:'Ingredient fixture',tag:'Fixture',tag_en:'Fixture',cat:'product',date:'2026-09-30'};
  const response=await h.request(h.input({baseSha:null,metadata}));assert.equal(response.status,200);
  const saved=await response.json();assert.deepEqual(saved.metadata,metadata);
  const loaded=await (await h.request()).json();assert.deepEqual(loaded.metadata,metadata);
  assert.equal((await h.request(h.input({baseSha:null,expectedHead:saved.head}))).status,200);
  assert.deepEqual((await (await h.request()).json()).metadata,metadata);assert.equal(h.refs.get('main'),h.main);
});
test('draft list is cookie-authenticated, immutable, bounded and reports unsupported engineering drafts', async () => {
  const h = fixture(), first = await (await h.request(h.input())).json();
  h.refs.set('drafts/index', h.main);
  const before = h.calls.length, response = await h.request(null, { query: '&mode=list' }), body = await response.json();
  assert.equal(response.status, 200); assert.deepEqual(body.drafts, [{ file: FILE, head: first.head, legacy: false }]);
  assert.equal(body.unsupportedRefs, 1); assert.equal(body.nextOffset, null);
  assert.ok(h.calls.slice(before).every(c => c.method === 'GET'));
  const reads = h.calls.length; assert.equal((await h.request(null, { query: '&mode=list&offset=-1' })).status, 400); assert.equal(h.calls.length, reads);
  h.session = false; assert.equal((await h.request(null, { query: '&mode=list' })).status, 401);
});
test('status inspection returns revisions without loading draft images or changing refs', async () => {
  const h = fixture(), first = await (await h.request(h.input())).json(), before = h.calls.length;
  const response = await h.request(null, { query: '&mode=status' }), body = await response.json();
  assert.equal(body.head, first.head); assert.equal(body.baseSha, h.mainBlob);
  assert.equal(body.content, undefined); assert.equal(body.media, undefined);
  assert.ok(h.calls.slice(before).every(c => c.method === 'GET'));
  assert.equal(h.refs.get('main'), h.main);
});
test('two tabs cannot overwrite a draft using the same loaded head', async () => {
  const h = fixture(), first = await (await h.request(h.input())).json();
  const input = h.input({ expectedHead: first.head, content: HTML.replace('本機測試', '第二次') });
  assert.equal((await h.request(input)).status, 200);
  const before = h.calls.length;
  assert.equal((await h.request({ ...input, content: HTML.replace('本機測試', '過期分頁') })).status, 409);
  assert.equal(h.calls.slice(before).filter(c => c.method !== 'GET').length, 0);
});
test('a concurrent ref update is rejected without force or a retry write', async () => {
  const h = fixture(), first = await (await h.request(h.input())).json(); h.race = true;
  const response = await h.request(h.input({ expectedHead: first.head }));
  assert.equal(response.status, 409); assert.equal(h.refs.get('drafts/example'), first.head);
  assert.equal(h.calls.filter(c => c.method === 'PATCH').length, 1);
});
test('an unseen legacy draft stays intact and requires explicit review', async () => {
  const h = fixture(); h.refs.set('drafts/example', h.main);
  const loaded = await (await h.request()).json(); assert.equal(loaded.legacy, true);
  const before = h.calls.length, result = await h.request(h.input({ expectedHead: h.main }));
  assert.equal(result.status, 409); assert.equal((await result.json()).error, 'legacy_draft_requires_review');
  assert.ok(h.calls.slice(before).every(c => c.method === 'GET'));
});
test('changes to the published article block stale draft saves', async () => {
  const h = fixture(), first = await (await h.request(h.input())).json();
  h.trees.get(h.commits.get(h.main).tree.sha).set(FILE, (() => { const bytes = Buffer.from('Changed main'); const id = blobSha(bytes); h.blobs.set(id, bytes); return id; })());
  const before = h.calls.length;
  assert.equal((await h.request(h.input({ expectedHead: first.head }))).status, 409);
  assert.ok(h.calls.slice(before).every(c => c.method === 'GET'));
});
test('immutable content verification failures do not claim a clean save', async () => {
  const h = fixture(); h.corrupt = true;
  const response = await h.request(h.input());
  assert.equal(response.status, 502); assert.equal((await response.json()).error, 'save_not_verified');
});
test('immutable manifest verification failure preserves an ambiguous accepted save', async () => {
  const h = fixture(); h.corruptRecord = true;
  const response = await h.request(h.input());
  assert.equal(response.status, 502); assert.equal((await response.json()).error, 'save_not_verified');
  assert.ok(h.refs.has('drafts/example')); assert.equal(h.refs.get('main'), h.main);
});
test('authentication, CSRF, arbitrary paths/refs and unknown fields fail before repository mutations', async () => {
  const h = fixture(); h.session = false;
  assert.equal((await h.request(h.input())).status, 401); assert.equal(h.calls.length, 0); h.session = true;
  for (const origin of ['https://evil.test', 'null', '']) assert.equal((await h.request(h.input(), { headers: { origin } })).status, 403);
  for (const file of ['admin.html', 'blog/index.html', 'en/blog/example.html', 'blog/../example.html']) assert.equal((await h.request(h.input({ file }))).status, 400);
  assert.equal((await h.request(h.input({ branch: 'main' }))).status, 400);
  assert.equal((await h.request(h.input({ repository: 'other/repo' }))).status, 400);
  assert.equal(h.calls.length, 0);
});
test('size limits apply to actual bytes rather than trusting Content-Length', async () => {
  const h = fixture();
  assert.equal((await h.request(h.input({ content: 'x'.repeat(3_500_001) }))).status, 413);
  assert.equal(h.calls.length, 0);
});
test('media and HTML enter one immutable draft commit, with digest/type validation', async () => {
  const h = fixture(), png = Buffer.from([137,80,78,71,13,10,26,10,0,0,0,0]);
  const path = 'blog/images/example/' + crypto.createHash('sha256').update(png).digest('hex') + '.png';
  const media = [{ path, base64: png.toString('base64') }];
  const response = await h.request(h.input({ media, content: HTML.replace('</main>', '<img src="/' + path + '" alt="fixture"></main>') }));
  assert.equal(response.status, 200);
  const loaded = await (await h.request()).json();
  assert.deepEqual(loaded.assets, [{ path, sha: blobSha(png), size: png.length }]);
  assert.deepEqual(loaded.media, media, 'draft images must reload before their public URLs exist');
  assert.equal(h.calls.filter(c => c.path === 'git/refs').length, 1);
  const bad = fixture(); assert.equal((await bad.request(bad.input({ media: [{ path: 'blog/images/other/' + path.split('/').pop(), base64: png.toString('base64') }] }))).status, 400);
  assert.equal(bad.calls.length, 0);
  assert.equal((await bad.request(bad.input({ media: [{ path: path.replace(/[a-f0-9]{64}/, '0'.repeat(64)), base64: png.toString('base64') }] }))).status, 400);
});
test('unknown network outcome does not retry a write or expose provider details', async () => {
  const h = fixture(); h.outcomeUnknown = true;
  const response = await h.request(h.input());
  assert.equal(response.status, 502); assert.equal((await response.json()).error, 'repository_unavailable');
  assert.equal(h.calls.filter(c => c.path === 'git/refs').length, 1);
  assert.ok(h.refs.has('drafts/example'), 'the write may already be accepted');
  const before = h.calls.length;
  assert.equal((await h.request(h.input())).status, 409, 'retry requires reloading the accepted draft first');
  assert.ok(h.calls.slice(before).every(c => c.method === 'GET'));
});
test('a racing first-save create cannot replace an existing draft ref', async () => {
  const h = fixture(); h.race = true;
  assert.equal((await h.request(h.input())).status, 409);
  assert.equal(h.refs.get('main'), h.main); assert.equal(h.refs.has('drafts/example'), false);
  assert.equal(h.calls.filter(c => c.path === 'git/refs').length, 1);
});
test('unsupported methods and cross-site fetch metadata cannot mutate repository data', async () => {
  const h = fixture();
  const method = await h.request(null, { method: 'DELETE' });
  assert.equal(method.status, 405); assert.equal(method.headers.get('allow'), 'GET, POST');
  assert.equal((await h.request(h.input(), { headers: { 'sec-fetch-site': 'cross-site' } })).status, 403);
  assert.equal(h.calls.length, 0);
});
test('embedded images and missing managed paths cannot be verified as complete drafts', async () => {
  for (const src of ['data:image/gif;base64,R0lGODlh', 'd&#97;ta:image/gif;base64,R0lGODlh', 'blob:local', 'file:///tmp/image.gif']) {
    const h = fixture();
    assert.equal((await h.request(h.input({ content: HTML.replace('</main>', '<img src="' + src + '"></main>') }))).status, 400);
    assert.equal(h.calls.length, 0);
  }
  for (const attribute of ['src="/blog/images/example/' + 'a'.repeat(64) + '.gif"', 'src=/blog/images/example/' + 'a'.repeat(64) + '.gif', 'srcset="/blog/images/example/' + 'a'.repeat(64) + '.gif 1x"']) {
    const h = fixture();
    const response = await h.request(h.input({ content: HTML.replace('</main>', '<img ' + attribute + '></main>') }));
    assert.equal(response.status, 400); assert.equal((await response.json()).error, 'missing_draft_media');
    assert.ok(h.calls.every(c => c.method === 'GET'));
  }
});
test('accepted images remain in the immutable manifest when omitted from an incremental POST', async () => {
  const h = fixture(), gif = Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64');
  const path = 'blog/images/example/' + crypto.createHash('sha256').update(gif).digest('hex') + '.gif';
  const content = HTML.replace('</main>', '<img src="/' + path + '"></main>');
  const first = await (await h.request(h.input({ content, media: [{ path, base64: gif.toString('base64') }] }))).json();
  assert.equal((await h.request(h.input({ content, expectedHead: first.head }))).status, 200);
  const loaded = await (await h.request()).json(); assert.deepEqual(loaded.assets.map(a => a.path), [path]);
  assert.deepEqual(loaded.media, [{ path, base64: gif.toString('base64') }]);
});
test('an existing immutable main image is adopted into the first draft manifest', async () => {
  const h = fixture(), gif = Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64');
  const path = 'blog/images/example/' + crypto.createHash('sha256').update(gif).digest('hex') + '.gif';
  const id = blobSha(gif); h.blobs.set(id, gif); h.trees.get(h.commits.get(h.main).tree.sha).set(path, id);
  const content = HTML.replace('</main>', '<img src="/' + path + '"></main>');
  assert.equal((await h.request(h.input({ content }))).status, 200);
  assert.deepEqual((await (await h.request()).json()).assets, [{ path, sha: id, size: gif.length }]);
});
test('existing main images with wrong digest or raster signature fail before any Git writes', async () => {
  for (const invalidType of [false, true]) {
    const h = fixture();
    const bytes = invalidType ? Buffer.from('<html>not an image</html>') : Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64');
    const digest = invalidType ? crypto.createHash('sha256').update(bytes).digest('hex') : 'a'.repeat(64);
    const path = 'blog/images/example/' + digest + '.gif', id = blobSha(bytes);
    h.blobs.set(id, bytes); h.trees.get(h.commits.get(h.main).tree.sha).set(path, id);
    const content = HTML.replace('</main>', '<img src="/' + path + '"></main>');
    const response = await h.request(h.input({ content }));
    assert.equal(response.status, 400);
    assert.equal((await response.json()).error, invalidType ? 'invalid_media_type' : 'invalid_media_digest');
    assert.ok(h.calls.every(c => c.method === 'GET')); assert.equal(h.refs.has('drafts/example'), false);
  }
});
test('managed references are bounded before immutable repository lookups', async () => {
  const h = fixture(), images = Array.from({ length: 17 }, (_, i) => '<img src="/blog/images/example/' + i.toString(16).padStart(64, '0') + '.gif">').join('');
  assert.equal((await h.request(h.input({ content: HTML.replace('</main>', images + '</main>') }))).status, 400);
  assert.equal(h.calls.length, 0);
});
test('unreferenced, executable or mismatched raster uploads are rejected before Git writes', async () => {
  const h = fixture();
  const bytes = Buffer.from('<svg onload="alert(1)"></svg>');
  const path = 'blog/images/example/' + crypto.createHash('sha256').update(bytes).digest('hex') + '.png';
  assert.equal((await h.request(h.input({ media: [{ path, base64: bytes.toString('base64') }] }))).status, 400);
  const png = Buffer.from([137,80,78,71,13,10,26,10]);
  const pngPath = 'blog/images/example/' + crypto.createHash('sha256').update(png).digest('hex') + '.png';
  assert.equal((await h.request(h.input({ media: [{ path: pngPath, base64: png.toString('base64') }] }))).status, 400);
  assert.ok(h.calls.every(c => c.method === 'GET'));
});
test('cumulative media limits reject an incremental save before it creates an unreloadable bundle', async () => {
  const h = fixture();
  const item = suffix => {
    const bytes = Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]), Buffer.alloc(800_000, suffix)]);
    const path = 'blog/images/example/' + crypto.createHash('sha256').update(bytes).digest('hex') + '.png';
    return { path, base64: bytes.toString('base64') };
  };
  const a = item(1), b = item(2);
  const first = await (await h.request(h.input({ media: [a], content: HTML.replace('</main>', '<img src="/' + a.path + '"></main>') }))).json();
  assert.ok(first.head);
  const before = h.calls.length;
  const response = await h.request(h.input({ expectedHead: first.head, media: [b],
    content: HTML.replace('</main>', '<img src="/' + a.path + '"><img src="/' + b.path + '"></main>') }));
  assert.equal(response.status, 413);
  assert.ok(h.calls.slice(before).every(c => c.method === 'GET'));
  assert.equal(h.refs.get('drafts/example'), first.head);
  // Deleting the first image allows the replacement bundle without publishing
  // that orphan file. The old branch tree may retain it, the manifest does not.
  assert.equal((await h.request(h.input({ expectedHead: first.head, media: [b],
    content: HTML.replace('</main>', '<img src="/' + b.path + '"></main>') }))).status, 200);
  const loaded = await (await h.request()).json(); assert.deepEqual(loaded.assets.map(a => a.path), [b.path]);
});
for (const failure of [false, true]) test('image larger than 1 MB uses immutable blob fallback' + (failure ? ' and preserves an unverified accepted save on failure' : ''), async () => {
  const h = fixture(); h.failBlob = failure;
  const gif = Buffer.concat([Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64'), Buffer.alloc(1_100_000)]);
  const path = 'blog/images/example/' + crypto.createHash('sha256').update(gif).digest('hex') + '.gif';
  const media = [{ path, base64: gif.toString('base64') }];
  const response = await h.request(h.input({ media, content: HTML.replace('</main>', '<img src="/' + path + '"></main>') }));
  assert.ok(h.calls.some(c => c.path === 'git/blobs/' + blobSha(gif)));
  assert.ok(h.refs.has('drafts/example')); assert.equal(h.refs.get('main'), h.main);
  if (failure) { assert.equal(response.status, 502); assert.equal((await response.json()).error, 'save_not_verified'); }
  else { assert.equal(response.status, 200); const loaded = await (await h.request()).json(); assert.deepEqual(loaded.media, media); }
});

for (const issue of ['content', 'size', 'negative-size', 'zero-sha', 'base64']) test('article reload rejects inconsistent immutable bytes: ' + issue, async () => {
  const h = fixture(), saved = await (await h.request(h.input())).json();
  const before = h.calls.length;
  h.tamper = (path, data) => {
    if (path !== 'contents/' + FILE) return data;
    if (issue === 'content') { const bytes = Buffer.from(data.content, 'base64'); bytes[0] ^= 1; return { ...data, content: bytes.toString('base64') }; }
    if (issue === 'size') return { ...data, size: data.size + 1 };
    if (issue === 'negative-size') return { ...data, size: -1 };
    if (issue === 'zero-sha') return { ...data, sha: '0'.repeat(40) };
    return { ...data, content: data.content + '#' };
  };
  const response = await h.request();
  assert.equal(response.status, 502); assert.equal((await response.json()).error, 'invalid_repository_content');
  assert.ok(h.calls.slice(before).every(c => c.method === 'GET'));
  assert.equal(h.refs.get('drafts/example'), saved.head); assert.equal(h.refs.get('main'), h.main);
});
for (const issue of ['sha', 'size', 'content']) test('large article fallback verifies the exact requested Git blob: ' + issue, async () => {
  const h = fixture(); const large = HTML.replace('</main>', 'a'.repeat(1_020_000) + '</main>');
  const bytes = Buffer.from(large), id = blobSha(bytes); h.blobs.set(id, bytes); h.trees.get(h.commits.get(h.main).tree.sha).set(FILE, id);
  h.tamper = (path, data) => {
    if (path !== 'git/blobs/' + id) return data;
    if (issue === 'sha') return { ...data, sha: sha('wrong blob') };
    if (issue === 'size') return { ...data, size: data.size + 1 };
    const changed = Buffer.from(data.content, 'base64'); changed[0] ^= 1; return { ...data, content: changed.toString('base64') };
  };
  const response = await h.request(); assert.equal(response.status, 502); assert.equal((await response.json()).error, 'invalid_repository_content');
  assert.ok(h.calls.every(c => c.method === 'GET')); assert.equal(h.refs.get('main'), h.main);
});
test('draft image reload rejects same-size corrupted Git bytes before returning media', async () => {
  const h = fixture(), gif = Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64');
  const path = 'blog/images/example/' + crypto.createHash('sha256').update(gif).digest('hex') + '.gif';
  const saved = await (await h.request(h.input({ content: HTML.replace('</main>', '<img src="/' + path + '"></main>'), media: [{ path, base64: gif.toString('base64') }] }))).json();
  const before = h.calls.length;
  h.tamper = (key, data) => { if (key !== 'contents/' + path) return data;
    const bytes = Buffer.from(data.content, 'base64'); bytes[bytes.length - 1] ^= 1; return { ...data, content: bytes.toString('base64') }; };
  const response = await h.request(); assert.equal(response.status, 409); assert.equal((await response.json()).error, 'invalid_draft_media');
  assert.ok(h.calls.slice(before).every(c => c.method === 'GET')); assert.equal(h.refs.get('drafts/example'), saved.head);
});
