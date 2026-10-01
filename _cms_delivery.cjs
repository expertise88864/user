/* Live author-intent recheck AFTER exact-SHA CI has validated the entire proof.
 * This is not an independent publication permit. The Python CI gate validates
 * immutable approval inputs/media/payload; production still requires CI + PR.
 * No writes, raw content logs, redirects or credentials in evidence output.
 */
'use strict';
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const FILE = '.cms-delivery.json';
const sha = value => typeof value === 'string' && /^[a-f0-9]{40}$/.test(value) && value !== '0'.repeat(40);
const hash = (algorithm, value) => createHash(algorithm).update(value).digest('hex');
const FIELDS = ['version','repository','file','requestHead','requestBlobSha','draftHead','manifestSha',
  'articleBlobSha','baseSha','preparedAgainst','action','approvedBy','requestedAt','scheduledAt','sourceSha256'];
const exactKeys = (value, keys) => value && typeof value === 'object' && !Array.isArray(value) &&
  Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
function slug(file) {
  assert.equal(typeof file, 'string', 'Invalid CMS article path');
  const match = /^blog\/([a-z0-9]+(?:-[a-z0-9]+)*)\.html$/.exec(file);
  assert.ok(match && match[1].length <= 100 && !['index','topics','charts'].includes(match[1]), 'Invalid CMS article path');
  return match[1];
}
function time(value) {
  assert.ok(typeof value === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(value), 'Invalid CMS timestamp');
  const stamp = Date.parse(value);
  assert.ok(Number.isFinite(stamp) && new Date(stamp).toISOString() === value, 'Invalid CMS timestamp');
  return stamp;
}
function validateReceiptEntry(entry, now) {
    assert.ok(exactKeys(entry, FIELDS) && entry.version === 1 && entry.repository === 'expertise88864/user' && entry.approvedBy === 'expertise88864' && ['review','schedule','unpublish'].includes(entry.action), 'Invalid CMS request proof');
    const name = slug(entry.file);
    for (const field of ['requestHead','requestBlobSha','draftHead','manifestSha','articleBlobSha','preparedAgainst']) assert.ok(sha(entry[field]), 'Invalid CMS proof SHA');
    assert.ok(entry.baseSha === null || sha(entry.baseSha), 'Invalid CMS article base');
    assert.ok(entry.action !== 'unpublish' || entry.baseSha !== null, 'Cannot unpublish a new article');
    const created = time(entry.requestedAt);
    assert.ok(created <= now, 'CMS request is in the future');
    if (entry.action === 'schedule') {
      const due = time(entry.scheduledAt);
      assert.ok(created < due && due <= created + 365 * 86400000 && due <= now, 'CMS schedule is not valid / due');
    } else assert.equal(entry.scheduledAt, null, 'Unexpected CMS schedule');
    assert.ok(entry.sourceSha256 && typeof entry.sourceSha256 === 'object' && !Array.isArray(entry.sourceSha256) && Object.hasOwn(entry.sourceSha256, entry.file), 'Missing CMS source evidence');
    const sources = Object.entries(entry.sourceSha256);
    assert.ok(sources.length >= 1 && sources.length <= 18, 'Invalid CMS source count');
    for (const [path, digest] of sources) {
      assert.ok((path === entry.file || path === 'blog/blog-shared.js' || new RegExp('^blog/images/' + name + '/[a-f0-9]{64}\\.(png|jpg|gif|webp)$').test(path)) && typeof digest === 'string' && /^[a-f0-9]{64}$/.test(digest), 'Invalid CMS source identity');
    }
    return { name, sources };
}
async function blob(api, path, commit, limit, trees) {
  assert.ok(sha(commit), 'CMS requires an exact SHA');
  const data = await api('/contents/' + path + '?ref=' + commit);
  assert.ok(data && data.type === 'file' && data.path === path && ['base64','none'].includes(data.encoding) && sha(data.sha), 'CMS immutable blob unavailable');
  assert.ok(Number.isInteger(data.size) && data.size >= 0 && data.size <= limit && typeof data.content === 'string' && data.content.length <= limit * 2, 'CMS blob size invalid');
  let content = data.content;
  if (data.encoding === 'none') {
    assert.equal(content, '', 'Invalid CMS object metadata');
    const payload = await api('/git/blobs/' + data.sha);
    assert.ok(payload?.sha === data.sha && payload.encoding === 'base64' && Number.isInteger(payload.size) && payload.size === data.size && typeof payload.content === 'string' && payload.content.length <= limit * 2, 'CMS exact-blob fallback does not match metadata');
    content = payload.content;
  }
  const encoded = content.replace(/[\r\n]/g, '');
  const raw = Buffer.from(encoded, 'base64');
  assert.ok(raw.length === data.size && raw.toString('base64') === encoded, 'CMS blob encoding invalid');
  assert.equal(hash('sha1', Buffer.concat([Buffer.from('blob ' + raw.length + '\0'), raw])), data.sha, 'CMS immutable digest invalid');
  const entries = await tree(api, commit, trees);
  const entry = entries.get(path);
  assert.ok(entry?.mode === '100644' && entry.type === 'blob' && entry.sha === data.sha, 'CMS inputs must be ordinary non-executable Git blobs');
  return { sha: data.sha, raw };
}
async function tree(api, commit, trees) {
  if (!trees.has(commit)) {
    const record = await api('/git/commits/' + commit);
    assert.ok(record?.sha === commit && sha(record.tree?.sha), 'CMS commit tree unavailable');
    const tree = await api('/git/trees/' + record.tree.sha + '?recursive=1');
    assert.ok(tree?.sha === record.tree.sha && tree.truncated === false && Array.isArray(tree.tree) && tree.tree.length <= 10000, 'CMS Git tree evidence incomplete');
    const paths = new Map();
    for (const entry of tree.tree) {
      assert.ok(entry && typeof entry.path === 'string' && !paths.has(entry.path), 'CMS Git tree paths ambiguous');
      paths.set(entry.path, entry);
    }
    trees.set(commit, paths);
  }
  return trees.get(commit);
}
async function verifyLiveIntent(candidate, api, now = Date.now()) {
  assert.ok(sha(candidate) && Number.isFinite(now), 'Invalid CMS candidate or clock');
  const trees = new Map();
  const { raw } = await blob(api, FILE, candidate, 128000, trees);
  // Canonical bytes also reject duplicate JSON properties and invalid UTF-8.
  const value = JSON.parse(raw.toString('utf8'));
  assert.equal(Buffer.from(JSON.stringify(value, null, 2) + '\n').equals(raw), true, 'CMS proof is not canonical');
  assert.ok(exactKeys(value, ['version','requests']) && value.version === 1 && Array.isArray(value.requests) && value.requests.length <= 20, 'Invalid CMS proof');
  await require('./_cms_retirement.cjs').verifyTransition(candidate, api, value.requests, now, trees);
  const seen = new Set();
  async function live(entry) {
    const name = 'refs/heads/drafts/' + slug(entry.file);
    const ref = await api('/git/ref/heads/drafts/' + slug(entry.file));
    assert.ok(ref?.ref === name && ref.object?.type === 'commit' && ref.object.sha === entry.requestHead, 'CMS author request cancelled or superseded');
  }
  for (const entry of value.requests) {
    const { name, sources } = validateReceiptEntry(entry, now);
    assert.ok(!seen.has(name), 'Duplicate CMS request');
    seen.add(name);
    for (const [path, digest] of sources) {
      const payload = await blob(api, path, candidate, 1500000, trees);
      assert.equal(hash('sha256', payload.raw), digest, 'CMS payload changed after preparation');
    }
    await live(entry);
    const requestPath = '.cms-requests/' + name + '.json';
    const request = await blob(api, requestPath, entry.requestHead, 8000, trees);
    assert.equal(request.sha, entry.requestBlobSha, 'CMS approved request changed');
    const record = JSON.parse(request.raw.toString('utf8'));
    // The owner-only API writes this exact compact form. Unlike the receipt,
    // requiring pretty JSON here would reject every legitimate API request.
    assert.equal(Buffer.from(JSON.stringify(record) + '\n').equals(request.raw), true, 'CMS request JSON is not canonical');
    const expected = { version: 1, file: entry.file, action: entry.action, draftHead: entry.draftHead,
      manifestSha: entry.manifestSha, blobSha: entry.articleBlobSha, baseSha: entry.baseSha,
      approvedBy: entry.approvedBy, contentApproved: entry.action !== 'unpublish', requestedAt: entry.requestedAt, scheduledAt: entry.scheduledAt };
    assert.deepEqual(record, expected, 'CMS receipt does not bind the approved request');
    const commit = await api('/git/commits/' + entry.requestHead);
    assert.equal(commit?.sha, entry.requestHead, 'CMS request commit unavailable');
    assert.deepEqual(commit.parents?.map(parent => parent.sha), [entry.draftHead], 'CMS request is not the direct successor of its draft');
    const compare = await api('/compare/' + entry.draftHead + '...' + entry.requestHead);
    assert.ok(compare?.status === 'ahead' && compare.total_commits === 1 && compare.merge_base_commit?.sha === entry.draftHead, 'CMS request history invalid');
    assert.deepEqual(compare.files?.map(file => file.filename), [requestPath], 'CMS request changed more than intent');
    const changed = compare.files[0];
    assert.ok(['added','modified'].includes(changed.status) && changed.sha === entry.requestBlobSha && Number.isInteger(changed.changes) && changed.changes >= 1 && !Object.hasOwn(changed, 'previous_filename'), 'CMS request diff is not an ordinary added/modified intent file');
  }
  // Always query the live refs again; immutable CI success is not current intent.
  for (const entry of value.requests) await live(entry);
  return { sha: candidate, activeRequests: value.requests.length, authorIntentVerified: true, published: false };
}
module.exports = { verifyLiveIntent, validateReceiptEntry, blob, tree, exactKeys, sha, time, slug, FIELDS };
