'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { verifySourceIntent } = require('./_cms_delivery.cjs');
const sha = 'a'.repeat(40), head = 'b'.repeat(40), draft = 'c'.repeat(40);
const digest = (algorithm, bytes) => createHash(algorithm).update(bytes).digest('hex');
function stored(path, content) {
  const raw = Buffer.isBuffer(content) ? content : Buffer.from(content);
  return { type: 'file', path, encoding: 'base64', size: raw.length, content: raw.toString('base64'),
    sha: digest('sha1', Buffer.concat([Buffer.from('blob ' + raw.length + '\0'), raw])) };
}
function fixture({ empty = false, large = false } = {}) {
  const file = 'blog/article.html', requestPath = '.cms-requests/article.json';
  const articleText = '<html><p>核可的病人文章</p>' + (large ? 'x'.repeat(1100000) : '') + '</html>';
  const article = stored(file, articleText);
  const record = { version: 1, file, action: 'review', draftHead: draft, manifestSha: 'd'.repeat(40),
    blobSha: article.sha, baseSha: 'e'.repeat(40), approvedBy: 'expertise88864', contentApproved: true,
    requestedAt: '2026-09-30T10:00:00.000Z', scheduledAt: null };
  const request = stored(requestPath, JSON.stringify(record) + '\n');
  const proof = { version: 1, repository: 'expertise88864/user', file, requestHead: head,
    requestBlobSha: request.sha, draftHead: draft, manifestSha: record.manifestSha, articleBlobSha: article.sha,
    baseSha: record.baseSha, preparedAgainst: 'f'.repeat(40), action: 'review', approvedBy: record.approvedBy,
    requestedAt: record.requestedAt, scheduledAt: null, sourceSha256: { [file]: digest('sha256', Buffer.from(articleText)) } };
  const value = { version: 1, requests: empty ? [] : [proof] };
  const responses = {
    '/git/ref/heads/main': { ref: 'refs/heads/main', object: { type: 'commit', sha: '9'.repeat(40) } },
    ['/git/commits/' + '9'.repeat(40)]: { sha: '9'.repeat(40), tree: { sha: '8'.repeat(40) }, parents: [] },
    ['/git/trees/' + '8'.repeat(40) + '?recursive=1']: { sha: '8'.repeat(40), truncated: false, tree: [] },
    ['/compare/' + '9'.repeat(40) + '...' + sha]: { status: 'ahead', merge_base_commit: { sha: '9'.repeat(40) } },
    ['/contents/.cms-delivery.json?ref=' + sha]: stored('.cms-delivery.json', JSON.stringify(value, null, 2) + '\n'),
    ['/contents/' + file + '?ref=' + sha]: article,
    ['/contents/' + requestPath + '?ref=' + head]: request,
    '/git/ref/heads/drafts/article': { ref: 'refs/heads/drafts/article', object: { type: 'commit', sha: head } },
    ['/git/commits/' + head]: { sha: head, tree: { sha: '2'.repeat(40) }, parents: [{ sha: draft }] },
    ['/git/commits/' + sha]: { sha, tree: { sha: '1'.repeat(40) }, parents: [] },
    ['/git/trees/' + '1'.repeat(40) + '?recursive=1']: { sha: '1'.repeat(40), truncated: false, tree: [
      { path: '.cms-delivery.json', type: 'blob', mode: '100644', sha: null },
      { path: file, type: 'blob', mode: '100644', sha: article.sha },
    ] },
    ['/git/trees/' + '2'.repeat(40) + '?recursive=1']: { sha: '2'.repeat(40), truncated: false, tree: [
      { path: requestPath, type: 'blob', mode: '100644', sha: request.sha },
    ] },
    ['/compare/' + draft + '...' + head]: { status: 'ahead', total_commits: 1, merge_base_commit: { sha: draft }, files: [{ filename: requestPath, status: 'added', sha: request.sha, changes: 1 }] },
  };
  function setTree() {
    responses['/git/trees/' + '1'.repeat(40) + '?recursive=1'].tree[0].sha = responses['/contents/.cms-delivery.json?ref=' + sha].sha;
    responses['/git/trees/' + '1'.repeat(40) + '?recursive=1'].tree[1].sha = responses['/contents/' + file + '?ref=' + sha].sha;
  }
  setTree();
  const calls = [];
  return { value, proof, responses, calls,
    setProof() { responses['/contents/.cms-delivery.json?ref=' + sha] = stored('.cms-delivery.json', JSON.stringify(value, null, 2) + '\n'); setTree(); },
    setTree,
    async api(path) { calls.push(path); assert.ok(Object.hasOwn(responses, path), 'Unexpected API request'); return structuredClone(responses[path]); } };
}
const now = Date.parse('2026-09-30T12:00:00.000Z');
test('Source preparation binds immutable input and current intent without final approval', async () => {
  const f = fixture();
  assert.deepEqual(await verifySourceIntent(sha, f.api, now), { sha, activeRequests: 1, authorIntentVerified: true, published: false });
  assert.equal(f.calls.filter(path => path === '/git/ref/heads/drafts/article').length, 2);
});
test('empty proof checks its ordinary immutable blob and does not pretend to deploy', async () => {
  const f = fixture({ empty: true });
  assert.equal((await verifySourceIntent(sha, f.api, now)).activeRequests, 0);
  assert.equal(f.calls.filter(path => path === '/git/ref/heads/main').length, 2);
  assert.equal(f.calls.filter(path => path === '/contents/.cms-delivery.json?ref=' + sha).length, 1);
});
for (const field of ['requestHead','requestBlobSha','manifestSha','articleBlobSha','baseSha','action','approvedBy','repository','file','scheduledAt','requestedAt','sourceSha256']) {
  test('wrong proof field is rejected: ' + field, async () => {
    const f = fixture();
    f.proof[field] = field === 'sourceSha256' ? { 'api/unrelated.js': 'a'.repeat(64) } : 'wrong';
    f.setProof();
    await assert.rejects(verifySourceIntent(sha, f.api, now));
  });
}
test('payload mutation with intact proof never passes', async () => {
  const f = fixture();
  f.responses['/contents/blog/article.html?ref=' + sha] = stored('blog/article.html', '<p>unapproved change</p>');
  f.setTree();
  await assert.rejects(verifySourceIntent(sha, f.api, now), /payload/);
});
test('cancellation and superseding edit invalidate old candidate CI evidence', async () => {
  const f = fixture();
  await verifySourceIntent(sha, f.api, now);
  f.responses['/git/ref/heads/drafts/article'].object.sha = 'd'.repeat(40);
  await assert.rejects(verifySourceIntent(sha, f.api, now), /cancelled or superseded/);
});
test('author cancellation during validation is checked again before accepting source preparation', async () => {
  const f = fixture(); let reads = 0;
  const api = async path => {
    const response = await f.api(path);
    if (path === '/git/ref/heads/drafts/article' && ++reads === 2) response.object.sha = 'd'.repeat(40);
    return response;
  };
  await assert.rejects(verifySourceIntent(sha, api, now), /cancelled or superseded/);
  assert.equal(reads, 2);
});
test('malformed / noncanonical / duplicate JSON / oversized blobs are rejected', async () => {
  for (const bytes of ['{"version":1,"requests":[]}\n', '{"version":1,"version":1,"requests":[]}\n', 'x'.repeat(128001)]) {
    const f = fixture();
    f.responses['/contents/.cms-delivery.json?ref=' + sha] = stored('.cms-delivery.json', bytes);
    await assert.rejects(verifySourceIntent(sha, f.api, now));
  }
});
test('truncated, wrongly typed and non-file response data fails closed', async () => {
  for (const changes of [{ size: true }, { sha: '0'.repeat(40) }, { content: '%%%' }, { type: 'symlink' }, { path: '.cms-drafts/other.json' }]) {
    const f = fixture();
    Object.assign(f.responses['/contents/.cms-delivery.json?ref=' + sha], changes);
    await assert.rejects(verifySourceIntent(sha, f.api, now));
  }
});
test('wrong request parent or extra request commit files never authorize a build', async () => {
  for (const which of ['parent','extra','count']) {
    const f = fixture();
    if (which === 'parent') f.responses['/git/commits/' + head].parents = [];
    else if (which === 'extra') f.responses['/compare/' + draft + '...' + head].files.push({ filename: 'api/unrelated.js' });
    else f.responses['/compare/' + draft + '...' + head].total_commits = 2;
    await assert.rejects(verifySourceIntent(sha, f.api, now));
  }
});
test('duplicate receipts and invalid or not-due schedules are rejected', async () => {
  const f = fixture(); f.value.requests.push({ ...f.proof }); f.setProof();
  await assert.rejects(verifySourceIntent(sha, f.api, now), /Duplicate/);
  for (const at of ['2026-09-30T13:00:00.000Z','2026-09-30T10:00:00.000Z','2028-09-30T11:00:00.000Z','2026-02-30T11:00:00.000Z']) {
    const scheduled = fixture(); scheduled.proof.action = 'schedule'; scheduled.proof.scheduledAt = at; scheduled.setProof();
    await assert.rejects(verifySourceIntent(sha, scheduled.api, now));
  }
});
test('Git tree modes, truncation and duplicate paths cannot hide unsafe sidecars', async () => {
  for (const mode of ['120000','100755','040000']) {
    const f = fixture();
    f.responses['/git/trees/' + '2'.repeat(40) + '?recursive=1'].tree[0].mode = mode;
    await assert.rejects(verifySourceIntent(sha, f.api, now), /ordinary/);
  }
  for (const truncated of [true,null,0]) {
    const f = fixture();
    f.responses['/git/trees/' + '1'.repeat(40) + '?recursive=1'].truncated = truncated;
    await assert.rejects(verifySourceIntent(sha, f.api, now), /incomplete/);
  }
  const f = fixture();
  const tree = f.responses['/git/trees/' + '1'.repeat(40) + '?recursive=1'].tree;
  tree.push({ ...tree[0] });
  await assert.rejects(verifySourceIntent(sha, f.api, now), /ambiguous/);
});
test('request diff status, blob and actual change cannot disguise removals or renames', async () => {
  for (const changes of [{ status: 'removed' },{ status: 'renamed' },{ sha: 'a'.repeat(40) },{ changes: 0 },{ changes: true },{ previous_filename: 'unrelated.txt' }]) {
    const f = fixture();
    Object.assign(f.responses['/compare/' + draft + '...' + head].files[0], changes);
    await assert.rejects(verifySourceIntent(sha, f.api, now), /ordinary added\/modified/);
  }
});
test('large approved article uses an immutable blob fallback without relaxing payload limits', async () => {
  const f = fixture({ large: true });
  const contentPath = '/contents/blog/article.html?ref=' + sha;
  const article = f.responses[contentPath];
  f.responses['/git/blobs/' + article.sha] = { sha: article.sha, size: article.size, encoding: 'base64', content: article.content };
  f.responses[contentPath] = { ...article, content: '', encoding: 'none' };
  assert.equal((await verifySourceIntent(sha, f.api, now)).activeRequests, 1);
  assert.ok(f.calls.includes('/git/blobs/' + article.sha));
  for (const changes of [{ sha: 'd'.repeat(40) },{ size: article.size - 1 },{ encoding: 'none' },{ content: article.content.slice(0, -4) }]) {
    f.responses['/git/blobs/' + article.sha] = { sha: article.sha, size: article.size, encoding: 'base64', content: article.content, ...changes };
    await assert.rejects(verifySourceIntent(sha, f.api, now));
  }
});

test('original source approval cannot authorize generated patient delivery', async () => {
  const f = fixture();
  await verifySourceIntent(sha, f.api, now);
  await assert.rejects(require('./_cms_delivery.cjs').verifyLiveIntent(sha, f.api, now), /Final generated patient content approval/);
});
