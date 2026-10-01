const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const FILE = 'blog/example.html', BASE = 'a'.repeat(40), HEAD = 'b'.repeat(40), BLOB = 'c'.repeat(40);
function fixture(overrides = {}) {
  const requests = [];
  const context = { window: {}, AbortController, TextEncoder, Uint8Array, Blob,
    setTimeout, clearTimeout, atob, btoa, crypto: overrides.crypto || crypto.webcrypto,
    fetch: (url, options) => new Promise((resolve, reject) => requests.push({ url, options, resolve, reject })) };
  vm.runInNewContext(fs.readFileSync('admin/article-drafts.js', 'utf8'), context);
  const api = context.window.DNArticleDrafts;
  const loaded = { file: FILE, head: null, baseSha: BASE, blobSha: BLOB, content: '<html><body><main>original</main></body></html>', media: [], legacy: false, conflict: false };
  const respond = (request, body, status = 200) => request.resolve(Response.json(body, { status }));
  const load = async (extra = {}) => { const p = api.load(FILE); respond(requests.at(-1), { ...loaded, ...extra }); return p; };
  return { api, requests, respond, load, loaded };
}

function publicationResult(h, extra = {}) {
  return { file: FILE, head: h.loaded.head, baseSha: BASE, blobSha: BLOB,
    publication: { mainSha: 'f'.repeat(40), mainBlobSha: BLOB, matchesLoadedVersion: true, sourceIndexable: true,
      ciVerified: true, deploymentVerified: true, published: true, state: 'live', checks: [], observedAt: new Date().toISOString(), ...extra } };
}
function newVersionObservation() {
  return { file: FILE, head: HEAD, baseSha: BASE, blobSha: BLOB,
    publication: { state: 'live', ciVerified: true, deploymentVerified: true, sourceIndexable: true,
      mainSha: 'd'.repeat(40), mainBlobSha: 'e'.repeat(40) } };
}
function newVersionAcceptance(extra = {}) {
  return { file: FILE, head: 'f'.repeat(40), baseSha: 'e'.repeat(40), blobSha: 'e'.repeat(40),
    status: 'cloud_draft', verified: true, published: false, ...extra };
}
test('new-version capture allows a published stale base but never changes the loaded CAS automatically', async () => {
  const h = fixture(); await h.load({ head: HEAD, conflict: true });
  const snapshot = h.api.captureNewVersion(FILE, newVersionObservation()), pending = h.api.startNewVersion(snapshot);
  const request = h.requests.at(-1), payload = JSON.parse(request.options.body);
  assert.deepEqual(payload, { file: FILE, action: 'new-version', expectedHead: HEAD, expectedBlob: BLOB,
    expectedMain: 'd'.repeat(40), expectedMainBlob: 'e'.repeat(40), confirmed: true });
  assert.equal(request.options.credentials, 'same-origin');
  h.respond(request, newVersionAcceptance()); assert.equal((await pending).verified, true);
  assert.equal(h.api.localState(FILE).head, HEAD, 'caller must preserve new typing and explicitly re-read before activating');
});
test('new-version capture rejects unseen drafts, incomplete production evidence and mismatched loaded snapshots', async () => {
  for (const kind of ['missing', 'legacy', 'failed', 'head', 'blob', 'base', 'zero']) {
    const h = fixture(); await h.load({ head: kind === 'missing' ? null : HEAD, legacy: kind === 'legacy' });
    const observed = newVersionObservation();
    if (kind === 'failed') observed.publication.ciVerified = false;
    if (['head', 'blob', 'base'].includes(kind)) observed[{ head: 'head', blob: 'blobSha', base: 'baseSha' }[kind]] = 'f'.repeat(40);
    if (kind === 'zero') observed.publication.mainSha = '0'.repeat(40);
    assert.throws(() => h.api.captureNewVersion(FILE, observed), kind);
    assert.equal(h.requests.filter(request => request.options.method === 'POST').length, 0);
  }
});
test('a reloaded context invalidates a previously captured new version before POST', async () => {
  const h = fixture(); await h.load({ head: HEAD });
  const snapshot = h.api.captureNewVersion(FILE, newVersionObservation()); await h.load({ head: HEAD });
  await assert.rejects(h.api.startNewVersion(snapshot), error => error.code === 'publication_changed');
  assert.equal(h.requests.filter(request => request.options.method === 'POST').length, 0);
});
test('ambiguous and malformed new-version acceptance never retries or replaces the local revision', async () => {
  for (const kind of ['network', 'gateway', 'same-head', 'wrong-blob', 'published', 'not-verified']) {
    const h = fixture(); await h.load({ head: HEAD });
    const pending = h.api.startNewVersion(h.api.captureNewVersion(FILE, newVersionObservation()));
    const rejected = assert.rejects(pending, error => error.code === 'new_version_not_verified');
    const request = h.requests.at(-1);
    if (kind === 'network') request.reject(Error('private provider detail'));
    else if (kind === 'gateway') h.respond(request, {}, 503);
    else h.respond(request, newVersionAcceptance({
      ...kind === 'same-head' ? { head: HEAD } : {}, ...kind === 'wrong-blob' ? { blobSha: BASE } : {},
      ...kind === 'published' ? { published: true } : {}, ...kind === 'not-verified' ? { verified: false } : {},
    }));
    await rejected; assert.equal(h.api.localState(FILE).head, HEAD);
    assert.equal(h.requests.filter(request => request.options.method === 'POST').length, 1);
  }
});
test('publication reads cookie-authenticated exact saved revision without advancing CAS or writing', async () => {
  const h = fixture(); await h.load();
  const before = h.api.capture(FILE, 'later local edits'), pending = h.api.observe(FILE), request = h.requests.at(-1);
  assert.match(request.url, /&mode=publication$/); assert.equal(request.options.method, 'GET'); assert.equal(request.options.credentials, 'same-origin');
  h.respond(request, publicationResult(h)); const result = await pending;
  assert.equal(result.publication.published, true); assert.match(h.api.publicationMessage(result.publication), /已正式上線/);
  const after = h.api.capture(FILE, 'later local edits'); assert.equal(after.expectedHead, before.expectedHead); assert.equal(after.baseSha, before.baseSha);
});
test('publication mismatched or impossible evidence is rejected rather than displayed as live', async () => {
  for (const patch of [{ mainSha: '0'.repeat(40) }, { state: 'unknown' }, { ciVerified: false }, { deploymentVerified: false }, { published: 'true' },
                       { sourceIndexable: false }, { matchesLoadedVersion: false }, { observedAt: 'invalid' }, { state: 'ci_failed' }]) {
    const h = fixture(); await h.load(); const pending = h.api.observe(FILE), rejected = assert.rejects(pending, e => e.code === 'publication_unavailable');
    h.respond(h.requests.at(-1), publicationResult(h, patch)); await rejected;
  }
});
test('version changing locally or remotely during publication observation preserves the old revision', async () => {
  for (const local of [false, true]) {
    const h = fixture(); await h.load(); const pending = h.api.observe(FILE), request = h.requests.at(-1);
    const rejected = assert.rejects(pending, e => e.code === 'publication_changed');
    if (local) await h.load({ head: HEAD });
    h.respond(request, { ...publicationResult(h), head: local ? null : HEAD }); await rejected;
    assert.equal(h.api.localState(FILE).head, local ? HEAD : null);
    assert.equal(h.requests.filter(item => item.options.method !== 'GET').length, 0);
  }
});
test('publication network failure is sanitized and never retries or mutates a draft', async () => {
  const h = fixture(); await h.load(); const pending = h.api.observe(FILE), rejected = assert.rejects(pending, e => e.code === 'publication_unavailable' && !e.message.includes('private'));
  h.requests.at(-1).reject(Error('private credential detail')); await rejected;
  assert.equal(h.requests.length, 2); assert.equal(h.api.localState(FILE).head, null);
});
test('publication labels distinguish failure, unknown, noindex and live source with a newer draft', () => {
  const h = fixture();
  assert.match(h.api.publicationMessage({ state: 'ci_failed' }), /驗證未通過/);
  assert.match(h.api.publicationMessage({ state: 'live_noindex' }), /不列入公開索引/);
  assert.match(h.api.publicationMessage({ state: 'live', published: false }), /目前草稿尚未上線/);
  assert.match(h.api.publicationMessage({ state: 'unverified' }), /尚未確認/);
});
test('creating an article cannot overwrite an existing published article or cloud draft', async () => {
  for (const extra of [{}, { head: HEAD, content: null }]) {
    const h = fixture(), pending = h.api.create(FILE, '<html>new</html>', {}), rejected = assert.rejects(pending, e => e.code === 'article_exists');
    h.respond(h.requests.at(-1), { ...h.loaded, ...extra }); await rejected;
    assert.equal(h.requests.length, 1, 'no POST on a reused slug');
  }
  const h = fixture(), metadata = { title_en: 'New', tag: '標籤', tag_en: 'Topic', cat: 'myth', date: '2026-09-30' };
  const pending = h.api.create(FILE, '<html>new</html>', metadata);
  h.respond(h.requests.at(-1), { ...h.loaded, baseSha: null, blobSha: null, content: null });
  await new Promise(resolve => setImmediate(resolve));
  const request = h.requests.at(-1), body = JSON.parse(request.options.body);
  assert.equal(body.expectedHead, null); assert.equal(body.baseSha, null); assert.deepEqual(body.metadata, metadata);
  h.respond(request, { file: FILE, head: HEAD, blobSha: BLOB, baseSha: null, metadata, status: 'cloud_draft', verified: true, published: false });
  assert.equal((await pending).head, HEAD);
});
test('draft list pagination cannot silently duplicate, loop or change an editor context', async () => {
  const h = fixture(); await h.load(); const pending = h.api.list();
  h.respond(h.requests.at(-1), { drafts: [{ file: FILE, head: HEAD, legacy: false }], nextOffset: 20, unsupportedRefs: 0 });
  await new Promise(resolve => setImmediate(resolve));
  h.respond(h.requests.at(-1), { drafts: [], nextOffset: null, unsupportedRefs: 0 });
  assert.equal((await pending).drafts.length, 1); assert.equal(h.api.capture(FILE, '<html></html>').expectedHead, null);
  assert.ok(h.requests.slice(1).every(request => request.options.method === 'GET' && request.options.credentials === 'same-origin'));
  const bad = h.api.list(), rejected = assert.rejects(bad); h.respond(h.requests.at(-1), { drafts: [], nextOffset: 0 }); await rejected;
});
test('client loads through cookie API and keeps a fixed expected revision in each snapshot', async () => {
  const h = fixture(); await h.load();
  const snapshot = h.api.capture(FILE, '<html><body>edited</body></html>');
  assert.ok(Object.isFrozen(snapshot)); assert.ok(Object.isFrozen(snapshot.media));
  const p = h.api.save(snapshot), request = h.requests.at(-1);
  assert.match(request.url, /^\/api\/admin\/article-draft$/);
  assert.equal(request.options.credentials, 'same-origin'); assert.equal(request.options.redirect, 'error');
  const body = JSON.parse(request.options.body);
  assert.equal(body.expectedHead, null); assert.equal(body.baseSha, BASE); assert.equal(body.branch, undefined);
  h.respond(request, { file: FILE, head: HEAD, blobSha: BLOB, baseSha: BASE, status: 'cloud_draft', verified: true, published: false });
  await p;
  assert.equal(h.api.capture(FILE, '<html><body>typed during save</body></html>').expectedHead, HEAD);
  assert.equal(snapshot.expectedHead, null, 'prior immutable snapshot must stay unchanged');
});
test('requests use only a saved snapshot and advance the loaded CAS without changing content', async () => {
  const h = fixture(); await h.load({ head: HEAD });
  const snapshot = h.api.captureRequest(FILE, h.loaded.content, { action: 'review', contentApproved: true });
  assert.ok(Object.isFrozen(snapshot)); assert.equal(snapshot.expectedHead, HEAD); assert.equal(snapshot.expectedBlob, BLOB);
  const pending = h.api.submit(snapshot), posted = h.requests.at(-1), body = JSON.parse(posted.options.body);
  assert.equal(body.action, 'review'); assert.equal(body.contentApproved, true); assert.equal(body.content, undefined); assert.equal(body.context, undefined);
  const NEXT = 'd'.repeat(40), request = { action: 'review', status: 'awaiting_review', blobSha: BLOB };
  h.respond(posted, { file: FILE, head: NEXT, baseSha: BASE, blobSha: BLOB, request, verified: true, published: false });
  await pending; assert.equal(h.api.localState(FILE).head, NEXT); assert.equal(h.api.localState(FILE).request.status, 'awaiting_review');
  assert.equal(h.api.capture(FILE, 'later editing').expectedHead, NEXT); assert.equal(snapshot.expectedHead, HEAD);
});
test('request capture refuses unsaved edits and a source with no cloud draft before POST', async () => {
  const h = fixture(); await h.load();
  assert.throws(() => h.api.captureRequest(FILE, h.loaded.content, { action: 'review' }), e => e.code === 'cloud_draft_required');
  await h.load({ head: HEAD });
  assert.throws(() => h.api.captureRequest(FILE, '<html>new local changes</html>', { action: 'review' }), e => e.code === 'unsaved_request');
  assert.equal(h.requests.filter(r => r.options.method === 'POST').length, 0);
});
test('a loaded view projection handles rendering whitespace without replacing cloud bytes or allowing later edits', async () => {
  const h = fixture(); await h.load({ head: HEAD });
  const rendered = '<html><body><main>\noriginal\n</main></body></html>';
  assert.equal(h.api.bindView(FILE, rendered, 'd'.repeat(40)), false);
  assert.equal(h.api.bindView(FILE, rendered, HEAD), true);
  assert.equal(h.api.hasUnsavedChanges(FILE, rendered), false, 'mounted whitespace is not a new author edit');
  assert.equal(h.api.hasUnsavedChanges(FILE, rendered.replace('original', 'changed')), true, 'actual content changes remain dirty');
  const request = h.api.captureRequest(FILE, rendered, { action: 'review', contentApproved: true });
  assert.equal(request.expectedBlob, BLOB); assert.equal(request.expectedHead, HEAD); assert.equal(h.requests.length, 1);
  assert.throws(() => h.api.captureRequest(FILE, rendered.replace('original', 'new edit'), { action: 'review' }), e => e.code === 'unsaved_request');
  assert.equal(h.api.localState(FILE).head, HEAD); assert.equal(h.api.localState(FILE).blobSha, BLOB);
});
test('changed file context or revision invalidates a previously captured request', async () => {
  const h = fixture(); await h.load({ head: HEAD });
  const snapshot = h.api.captureRequest(FILE, h.loaded.content, { action: 'review', contentApproved: true });
  await h.load({ head: 'd'.repeat(40) });
  await assert.rejects(h.api.submit(snapshot), e => e.code === 'editor_changed');
  assert.equal(h.requests.filter(r => r.options.method === 'POST').length, 0);
});
test('request network and malformed acceptance keep the prior revision and never retry', async () => {
  for (const mode of ['network', 'non-json', 'mismatched-blob', 'unverified']) {
    const h = fixture(); await h.load({ head: HEAD });
    const snapshot = h.api.captureRequest(FILE, h.loaded.content, { action: 'review', contentApproved: true });
    const pending = h.api.submit(snapshot), posted = h.requests.at(-1);
    const rejected = assert.rejects(pending, e => e.code === 'request_not_verified' && !e.message.includes('private'));
    if (mode === 'network') posted.reject(Error('private token detail'));
    else if (mode === 'non-json') posted.resolve(new Response('private token detail', { status: 200 }));
    else h.respond(posted, { file: FILE, head: 'd'.repeat(40), baseSha: BASE,
      blobSha: mode === 'mismatched-blob' ? 'e'.repeat(40) : BLOB,
      request: { action: 'review', status: 'awaiting_review', blobSha: BLOB }, verified: false, published: false });
    await rejected; assert.equal(h.api.localState(FILE).head, HEAD); assert.equal(h.requests.length, 2);
  }
});
test('cancellation advances the head, clears only request state, and later edits require a save', async () => {
  const h = fixture(); await h.load({ head: HEAD, request: { action: 'review', status: 'awaiting_review', blobSha: BLOB } });
  const snapshot = h.api.captureRequest(FILE, h.loaded.content, { action: 'cancel', confirmed: true });
  const pending = h.api.submit(snapshot), posted = h.requests.at(-1);
  assert.equal(JSON.parse(posted.options.body).confirmed, true);
  h.respond(posted, { file: FILE, head: 'd'.repeat(40), baseSha: BASE, blobSha: BLOB, request: null, verified: true, published: false });
  await pending; assert.equal(h.api.localState(FILE).request, null);
  assert.equal(h.api.captureRequest(FILE, h.loaded.content, { action: 'review', contentApproved: true }).expectedHead, 'd'.repeat(40));
  assert.throws(() => h.api.captureRequest(FILE, '<html>later</html>', { action: 'review', contentApproved: true }), e => e.code === 'unsaved_request');
});
test('an ordinary verified save invalidates old request state and updates requestable content', async () => {
  const h = fixture(); await h.load({ head: HEAD, request: { status: 'awaiting_review' } });
  const content = '<html><body>new saved article</body></html>', pending = h.api.save(h.api.capture(FILE, content));
  h.respond(h.requests.at(-1), { file: FILE, head: 'd'.repeat(40), blobSha: 'e'.repeat(40), baseSha: BASE, status: 'cloud_draft', verified: true, published: false });
  await pending; assert.equal(h.api.localState(FILE).request, null);
  const request = h.api.captureRequest(FILE, content, { action: 'review', contentApproved: true });
  assert.equal(request.expectedHead, 'd'.repeat(40)); assert.equal(request.expectedBlob, 'e'.repeat(40));
});
test('a late load response cannot replace a more recently loaded draft', async () => {
  const h = fixture(), first = h.api.load(FILE), old = h.requests.at(-1);
  const rejection = assert.rejects(first, e => e.code === 'editor_changed');
  await h.load({ head: HEAD }); h.respond(old, h.loaded); await rejection;
  assert.equal(h.api.capture(FILE, '<html></html>').expectedHead, HEAD);
});
test('conflicts, ambiguous network results and malformed acceptance retain the loaded revision', async () => {
  for (const mode of ['conflict', 'network', 'non-json', 'json-5xx', 'unverified']) {
    const h = fixture(); await h.load(); const snapshot = h.api.capture(FILE, '<html></html>');
    const p = h.api.save(snapshot), request = h.requests.at(-1), rejection = assert.rejects(p);
    if (mode === 'conflict') h.respond(request, { error: 'draft_conflict' }, 409);
    else if (mode === 'network') request.reject(Error('unknown network outcome'));
    else if (mode === 'non-json') request.resolve(new Response('<html>private gateway detail</html>', { status: 502, headers: { 'Content-Type': 'text/html' } }));
    else if (mode === 'json-5xx') h.respond(request, { error: 'repository_unavailable' }, 502);
    else h.respond(request, { file: FILE, head: HEAD, blobSha: BLOB, baseSha: BASE, status: 'cloud_draft', verified: false, published: false });
    await rejection;
    assert.equal(h.api.capture(FILE, '<html></html>').expectedHead, null);
    assert.equal(h.requests.length, 2, 'no automatic write retry');
  }
});
test('non-JSON accepted POST responses get an ambiguous-save message without leaking details or retrying', async () => {
  const h = fixture(); await h.load(); const snapshot = h.api.capture(FILE, '<html></html>');
  const p = h.api.save(snapshot), request = h.requests.at(-1);
  const rejection = assert.rejects(p, e => e.code === 'save_not_verified' && !e.message.includes('private-provider'));
  request.resolve(new Response('private-provider token detail', { status: 200 })); await rejection;
  assert.equal(h.api.capture(FILE, '<html></html>').expectedHead, null);
  assert.equal(h.requests.length, 2);
});
test('invalid recovery is atomic and image bytes must match the canonical digest before registration', async () => {
  const h = fixture(); await h.load();
  await h.api.stage(FILE, new Blob([Uint8Array.from([137,80,78,71,13,10,26,10])], { type: 'image/png' }));
  const saved = h.api.localState(FILE);
  for (const second of [{ path: '../outside.png', base64: 'aA==' },
    { ...saved.media[0], path: saved.media[0].path.replace(/[a-f0-9]{64}/, '0'.repeat(64)) },
    { ...saved.media[0], base64: '@@@@' },
    { ...saved.media[0], base64: btoa('not an actual PNG') },
    { ...saved.media[0], base64: saved.media[0].base64.repeat(200000) }]) {
    const target = fixture(); await target.load(); const before = target.api.localState(FILE);
    await assert.rejects(async () => target.api.restore(FILE, { ...saved, media: [saved.media[0], second] }));
    assert.deepEqual(target.api.localState(FILE), before, 'no first-image mutation before a later validation failure');
    assert.equal(target.requests.length, 1, 'recovery never sends POST');
  }
});

test('recovery hash validation preserves a newer load, newly staged images and intervening editor input', async () => {
  const origin = fixture(); await origin.load();
  await origin.api.stage(FILE, new Blob([Uint8Array.from([137,80,78,71,13,10,26,10])], { type: 'image/png' }));
  const saved = origin.api.localState(FILE);
  for (const mode of ['load', 'stage', 'typing']) {
    let release, hold = true;
    const h = fixture({ crypto: { subtle: { digest: (...args) => hold ? new Promise(resolve => {
      release = () => crypto.webcrypto.subtle.digest(...args).then(resolve);
    }) : crypto.webcrypto.subtle.digest(...args) } } });
    await h.load(); let isCurrent = true;
    const pending = h.api.restore(FILE, saved, { isCurrent: () => isCurrent });
    const rejected = assert.rejects(pending, e => e.code === 'editor_changed');
    assert.equal(typeof release, 'function'); hold = false;
    if (mode === 'load') await h.load({ head: HEAD });
    if (mode === 'stage') await h.api.stage(FILE, new Blob([Uint8Array.from([137,80,78,71,13,10,26,10,1])], { type: 'image/png' }));
    if (mode === 'typing') isCurrent = false;
    const before = h.api.localState(FILE); release(); await rejected;
    assert.deepEqual(h.api.localState(FILE), before, 'stale recovery must not register any images or change current state');
    assert.equal(h.requests.filter(request => request.options.method === 'POST').length, 0);
  }
});

test('whole recovery count and encoded budget reject before any registry mutation', async () => {
  const h = fixture(); await h.load(); const before = h.api.localState(FILE);
  const bytes = new Uint8Array(800000); bytes.set([137,80,78,71,13,10,26,10]);
  const media = [];
  for (let index = 0; index < 2; index++) {
    bytes[8] = index; const hash = crypto.createHash('sha256').update(bytes).digest('hex');
    media.push({ path: 'blog/images/example/' + hash + '.png', base64: Buffer.from(bytes).toString('base64') });
  }
  for (const items of [media, Array(17).fill(media[0])]) {
    await assert.rejects(h.api.restore(FILE, { head: null, baseSha: BASE, blobSha: BLOB, media: items }), e => e.code === 'invalid_local_draft');
    assert.deepEqual(h.api.localState(FILE), before);
  }
});

test('a present malformed recovery blob SHA is rejected without changing source revision or media', async () => {
  const h = fixture(); await h.load(); const before = h.api.localState(FILE);
  for (const blobSha of ['not-a-sha', '', 123, {}, 'A'.repeat(40)]) {
    await assert.rejects(async () => h.api.restore(FILE, { head: null, baseSha: BASE, blobSha, media: [] }), e => e.code === 'invalid_local_draft');
    assert.deepEqual(h.api.localState(FILE), before);
  }
});

test('staging an image is local only and serializes its final path without changing other document text', async () => {
  const h = fixture(); await h.load();
  const png = new Blob([Uint8Array.from([137,80,78,71,13,10,26,10])], { type: 'image/png' });
  const image = await h.api.stage(FILE, png);
  assert.equal(h.requests.length, 1, 'no upload before the article snapshot is saved');
  const html = '<html><body><img src="' + image.url + '" alt="圖片"><script>const keep="' + image.url + '"</script></body></html>';
  const snapshot = h.api.capture(FILE, html);
  assert.ok(snapshot.content.includes('src="' + image.path + '"'));
  assert.ok(snapshot.content.includes('const keep="' + image.url + '"'), 'unrelated source and scripts remain byte-for-byte');
  assert.equal(snapshot.media.length, 1);
  const state = h.api.localState(FILE);
  assert.equal(state.media.length, 1); assert.equal(state.media[0].accepted, false);
  const reloaded = fixture(); await reloaded.load();
  assert.equal((await reloaded.api.restore(FILE, state)).conflict, false);
  assert.equal(reloaded.api.capture(FILE, html).media.length, 1, 'unsaved images survive local draft restoration');
});
test('only images included in a save snapshot become accepted; later edits remain unsaved', async () => {
  const h = fixture(); await h.load();
  const a = await h.api.stage(FILE, new Blob([Uint8Array.from([137,80,78,71,13,10,26,10])], { type: 'image/png' }));
  const snapshot = h.api.capture(FILE, '<html><img src="' + a.url + '"></html>');
  const p = h.api.save(snapshot), request = h.requests.at(-1);
  const b = await h.api.stage(FILE, new Blob([Uint8Array.from([137,80,78,71,13,10,26,10,1])], { type: 'image/png' }));
  h.respond(request, { file: FILE, head: HEAD, blobSha: BLOB, baseSha: BASE, status: 'cloud_draft', verified: true, published: false }); await p;
  const next = h.api.capture(FILE, '<html><img src="' + a.url + '"><img src="' + b.url + '"></html>');
  assert.equal(next.media.length, 1); assert.equal(next.media[0].path, b.path.slice(1));
  assert.equal(next.expectedHead, HEAD);
});
test('restoring a local draft from another cloud revision preserves images but blocks automatic overwrite', async () => {
  const h = fixture(); await h.load(); await h.api.stage(FILE, new Blob([Uint8Array.from([137,80,78,71,13,10,26,10])], { type: 'image/png' }));
  const saved = h.api.localState(FILE), newer = fixture(); await newer.load({ head: HEAD });
  assert.equal((await newer.api.restore(FILE, saved)).conflict, true);
  assert.equal(newer.api.localState(FILE).media.length, 1);
  assert.throws(() => newer.api.capture(FILE, '<html></html>'), e => e.code === 'draft_conflict');
});
test('legacy drafts are readable but neither silently replaced nor treated as published', async () => {
  const h = fixture(); const data = await h.load({ head: HEAD, legacy: true, conflict: true });
  assert.equal(data.legacy, true);
  assert.throws(() => h.api.capture(FILE, '<html></html>'), e => e.code === 'legacy_draft_requires_review');
  assert.equal(h.requests.length, 1);
});
test('remote inspection does not replace the editor revision or staged images', async () => {
  const h = fixture(); await h.load();
  const image = await h.api.stage(FILE, new Blob([Uint8Array.from([137,80,78,71,13,10,26,10])], { type: 'image/png' }));
  const before = h.api.localState(FILE), p = h.api.inspect(FILE), request = h.requests.at(-1);
  assert.ok(request.url.endsWith('&mode=status'));
  h.respond(request, { file: FILE, head: HEAD, baseSha: BASE, conflict: false }); await p;
  assert.deepEqual(h.api.localState(FILE), before);
  assert.equal(h.api.capture(FILE, '<html><img src="' + image.url + '"></html>').expectedHead, null);
});
test('a deferred reload preserves the outgoing revision and image mapping until the editor activates it', async () => {
  const h = fixture(); await h.load();
  const image = await h.api.stage(FILE, new Blob([Uint8Array.from([137,80,78,71,13,10,26,10])], { type: 'image/png' }));
  const before = h.api.localState(FILE), p = h.api.load(FILE, { activate: false });
  h.respond(h.requests.at(-1), { ...h.loaded, head: HEAD }); const next = await p;
  assert.deepEqual(h.api.localState(FILE), before, 'incoming response must not replace the live serializer mapping');
  assert.ok(h.api.canonical(FILE, '<img src="' + image.url + '">').includes(image.path));
  h.api.activate(next); assert.equal(h.api.localState(FILE).head, HEAD);
});
