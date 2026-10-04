/* Complete immutable patient output identity. Read-only; no CI/deployment permit.
 * This is the production counterpart of _cms_patient_review.py. The original
 * source request and a later explicit generated-content approval are distinct.
 */
'use strict';
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { blob, tree } = require('./_cms_delivery.cjs');
const contract = require('./api/admin/_patient-review-contract.js');
const { validateApproval, sourceEntry, manifest, expectedRequest, parent, changedOne, reviewPath,
  exactKeys, sha, time, slug, APPROVAL_FIELDS, REQUEST_FIELDS, REVIEW_FIELDS, MAX_REVIEW_BYTES } = contract;
const FILE = '.cms-delivery.json';
const digest = raw => createHash('sha256').update(raw).digest('hex');
const ops = { blob, tree, digest };
const leafTree = (api, head, trees) => contract.leafTree(api, head, trees, ops);
const loadReview = (api, head, file, trees, proof, now) => contract.loadReview(api, head, file, trees, proof, now, ops);
async function verifyDelivery(candidate, api, entry, now, trees) {
  const a = validateApproval(entry.patientApproval, now);
  assert.ok(entry.version === 2 && entry.action !== 'unpublish' && time(a.approvedAt) >= time(entry.requestedAt), 'Patient approval does not follow its source request');
  const review = await loadReview(api, a.reviewHead, entry.file, trees, sourceEntry(entry), now);
  assert.equal(review.sha, a.manifestBlobSha, 'Final patient review blob changed');
  assert.equal(digest(review.raw), a.manifestSha256, 'Final patient review bytes changed');
  const path = '.cms-requests/' + slug(entry.file) + '.json';
  const saved = await blob(api, path, a.approvalHead, 8000, trees);
  assert.equal(saved.sha, a.approvalBlobSha, 'Final patient approval blob changed');
  const record = JSON.parse(saved.raw.toString('utf8'));
  assert.ok(Buffer.from(JSON.stringify(record) + '\n').equals(saved.raw), 'Final patient approval is not canonical');
  assert.ok(exactKeys(record, REQUEST_FIELDS), 'Invalid final patient request schema');
  assert.deepEqual(record, expectedRequest(entry, review.value), 'Patient receipt lost its explicit final author approval');
  await parent(api, a.approvalHead, entry.requestHead);
  await changedOne(api, entry.requestHead, a.approvalHead, path, saved.sha);
  const history = await api('/compare/' + a.reviewHead + '...' + candidate);
  assert.ok(history?.status === 'ahead' && history.merge_base_commit?.sha === a.reviewHead, 'Patient candidate not based on approved review history');
  const actual = await leafTree(api, candidate, trees), rows = review.value.patientManifest.trackedPackage.files;
  const control = new Set([FILE, reviewPath(entry.file)]);
  assert.deepEqual([...actual.keys()].filter(name => !control.has(name)).sort(), Object.keys(rows).filter(name => !control.has(name)).sort(), 'Candidate omits or adds approved patient outputs');
  const manifestRow = actual.get(reviewPath(entry.file));
  assert.ok(manifestRow?.mode === '100644' && manifestRow.sha === review.sha, 'Candidate patient manifest differs');
  for (const [name, row] of Object.entries(rows)) if (!control.has(name)) assert.ok(actual.get(name)?.mode === row.mode && actual.get(name)?.sha === row.blobSha, 'Candidate differs from complete approved patient package');
  return review.value;
}
function sameStat(a, b) {
  return a.dev === b.dev && a.ino === b.ino && a.size === b.size && a.mtimeNs === b.mtimeNs && a.ctimeNs === b.ctimeNs;
}
function outputBytes(root, name, row) {
  const target = path.resolve(root, ...name.split('/'));
  assert.ok(target.startsWith(root + path.sep), 'Patient build file escapes its checkout');
  const before = fs.lstatSync(target, { bigint: true });
  assert.ok(before.isFile() && before.nlink === 1n && fs.realpathSync(target) === target, 'Patient build file is missing or linked');
  assert.equal(before.size, BigInt(row.size), 'Patient build output size differs from final approval');
  if (row.mode && process.platform !== 'win32') assert.equal(Boolean(before.mode & 0o111n), row.mode === '100755', 'Patient build file mode changed');
  const handle = fs.openSync(target, 'r');
  try {
    assert.ok(sameStat(before, fs.fstatSync(handle, { bigint: true })), 'Patient output changed while opening');
    const storage = Buffer.alloc(row.size + 1); let read = 0;
    while (read < storage.length) {
      const count = fs.readSync(handle, storage, read, storage.length - read, null);
      if (!count) break; read += count;
    }
    assert.equal(read, row.size, 'Patient output size changed while reading');
    const raw = storage.subarray(0, read);
    assert.ok(sameStat(before, fs.fstatSync(handle, { bigint: true })) && sameStat(before, fs.lstatSync(target, { bigint: true })), 'Patient output changed while reading');
    assert.equal(digest(raw), row.sha256, 'Patient build output bytes differ from final approval');
  } finally { fs.closeSync(handle); }
}
function outputInventory(root) {
  const found = [], pending = ['']; let directories = 0;
  while (pending.length) {
    const current = pending.pop(), absolute = path.join(root, current);
    assert.ok(++directories <= 10000, 'Patient build directory count exceeds its bound');
    const before = fs.lstatSync(absolute, { bigint: true });
    assert.ok(before.isDirectory() && fs.realpathSync(absolute) === absolute, 'Patient build contains a linked directory');
    for (const item of fs.readdirSync(absolute, { withFileTypes: true })) {
      const name = current ? current + '/' + item.name : item.name;
      // Dependency caches and provider Git/build metadata are not deployed
      // patient outputs. Every expected Git file is still read independently.
      if ((!current && ['.git','node_modules','.vercel'].includes(item.name)) || item.name === '__pycache__') continue;
      if (item.isDirectory()) pending.push(name);
      else { assert.ok(item.isFile(), 'Patient build contains an unrecorded link'); found.push(name); }
      assert.ok(found.length <= 10000, 'Patient build file count exceeds its bound');
    }
    assert.ok(sameStat(before, fs.lstatSync(absolute, { bigint: true })), 'Patient build directory changed while reading');
  }
  return found.sort();
}
async function verifyWorkspace(root, candidate, api, now = Date.now(), { preview = false } = {}) {
  const trees = new Map(), receipt = await blob(api, FILE, candidate, 128000, trees);
  const record = JSON.parse(receipt.raw.toString('utf8'));
  assert.ok(Buffer.from(JSON.stringify(record,null,2)+'\n').equals(receipt.raw) && exactKeys(record,['version','requests']) && record.version === 1 && Array.isArray(record.requests), 'Invalid patient build receipt');
  assert.ok(record.requests.length <= 20, 'Too many patient build requests');
  const seen = new Set();
  for (const entry of record.requests) {
    const { name } = contract.validateReceiptEntry(entry, now);
    assert.ok(!seen.has(name), 'Duplicate CMS request');
    seen.add(name);
  }
  const entries = record.requests.filter(e => e.action !== 'unpublish');
  if (!entries.length) return { patientPackages: 0, outputFilesVerified: 0, published: false };
  root = fs.realpathSync(root);
  let count = 0;
  for (const entry of entries) {
    const pending = preview && entry.version === 1;
    const approved = pending ? (await loadReview(api, candidate, entry.file, trees, entry, now)).value
      : await verifyDelivery(candidate, api, entry, now, trees);
    if (pending) await require('./_cms_delivery.cjs').verifySourceIntent(approved.patientManifest.trackedPackage.sourceHead, api, now);
    const rows = { ...approved.patientManifest.trackedPackage.files, ...approved.patientManifest.extraFiles,
      [FILE]: { mode: '100644', size: receipt.raw.length, sha256: digest(receipt.raw) } };
    const saved = await blob(api, reviewPath(entry.file), candidate, MAX_REVIEW_BYTES, trees);
    rows[reviewPath(entry.file)] = { mode: '100644', size: saved.raw.length, sha256: pending ? digest(saved.raw) : entry.patientApproval.manifestSha256 };
    assert.deepEqual(outputInventory(root), Object.keys(rows).sort(), 'Patient build added or omitted an approved output');
    for (const [name,row] of Object.entries(rows)) outputBytes(root, name, row);
    assert.deepEqual(outputInventory(root), Object.keys(rows).sort(), 'Patient outputs changed during build verification');
    if (pending) await require('./_cms_delivery.cjs').verifySourceIntent(approved.patientManifest.trackedPackage.sourceHead, api, now);
    count += Object.keys(rows).length;
  }
  return { patientPackages: entries.length, outputFilesVerified: count, published: false };
}
module.exports = { validateApproval, sourceEntry, manifest, loadReview, expectedRequest, verifyDelivery,
  verifyWorkspace, parent, changedOne, leafTree, reviewPath, digest, APPROVAL_FIELDS, REQUEST_FIELDS, REVIEW_FIELDS, MAX_REVIEW_BYTES };
