// Shared generated patient approval contract for Edge and Node runtimes.
// Read-only immutable evidence; approval, CI and publication are separate steps.
const encoder = new TextEncoder();
const sha = value => typeof value === 'string' && /^[a-f0-9]{40}$/.test(value) && value !== '0'.repeat(40);
function equal(left, right) {
  if (left === right) return true;
  if (!left || !right || typeof left !== 'object' || typeof right !== 'object' || Array.isArray(left) !== Array.isArray(right)) return false;
  const keys = Object.keys(left);
  return keys.length === Object.keys(right).length && keys.every(k => Object.hasOwn(right,k) && equal(left[k],right[k]));
}
const assert = {
  ok(value, message) { if (!value) throw Error(message); },
  equal(left,right,message) { if (left !== right) throw Error(message); },
  deepEqual(left,right,message) { if (!equal(left,right)) throw Error(message); },
};
function canonical(raw, pretty) {
  assert.ok(raw instanceof Uint8Array, 'Patient manifest bytes unavailable');
  const text = new TextDecoder('utf-8', { fatal: true }).decode(raw), value = JSON.parse(text);
  assert.equal(JSON.stringify(value,null,pretty ? 2 : undefined)+'\n', text, 'Patient JSON is not canonical');
  return value;
}
const FILE = '.cms-delivery.json', REPO = 'expertise88864/user', MAX_REVIEW_BYTES = 2100000;
const APPROVAL_FIELDS = ['reviewHead','manifestBlobSha','manifestSha256','approvalHead','approvalBlobSha','approvedAt'];
const REQUEST_FIELDS = ['version','file','sourceRequestHead','sourceRequest','reviewHead','manifestBlobSha',
  'manifestSha256','archiveSha256','contentDate','approvedBy','approvedAt','contentApproved'];
const REVIEW_FIELDS = ['version','repository','file','contentDate','archiveSha256','patientManifest'];
const PATIENT_FIELDS = ['version','state','trackedPackage','extraFiles','generationVerified','liveAuthorIntentVerified','contentApproved','ciVerified','published'];
const TRACKED_FIELDS = ['version','repository','file','pipelineHead','sourceHead','generatedHead','generatedTreeSha','sourceEvidence','files','state','generationVerified','contentApproved','ciVerified','published'];
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
    assert.ok([1, 2].includes(entry?.version) && exactKeys(entry, entry.version === 2 ? [...FIELDS, 'patientApproval'] : FIELDS) && entry.repository === 'expertise88864/user' && entry.approvedBy === 'expertise88864' && ['review','schedule','unpublish'].includes(entry.action), 'Invalid CMS request proof');
    if (entry.version === 2) {
      const approval = validateApproval(entry.patientApproval, now);
      assert.ok(entry.action !== 'unpublish' && time(approval.approvedAt) >= time(entry.requestedAt), 'Final patient approval must follow its source request');
    }
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
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const reviewPath = file => '.cms-review/' + slug(file) + '.json';
function validateApproval(value, now) {
  assert.ok(exactKeys(value, APPROVAL_FIELDS), 'Invalid final patient approval identity');
  for (const name of ['reviewHead','manifestBlobSha','approvalHead','approvalBlobSha']) assert.ok(sha(value[name]), 'Invalid patient approval SHA');
  assert.ok(hash(value.manifestSha256), 'Invalid patient manifest digest');
  assert.ok(Number.isFinite(now) && time(value.approvedAt) <= now, 'Patient approval timestamp is in the future');
  return value;
}
function sourceEntry(entry) {
  return Object.fromEntries(Object.entries(entry).filter(([name]) => name !== 'patientApproval').map(([name, value]) => [name, name === 'version' ? 1 : value]));
}
function paths(names) {
  const seen = new Set();
  for (const name of names) {
    assert.ok(typeof name === 'string' && name && encoder.encode(name).length <= 1000 &&
      !name.startsWith('/') && !/[\\:\x00-\x1f\x7f]/.test(name) &&
      name.split('/').every(part => part && part !== '.' && part !== '..'), 'Unsafe patient path');
    const key = name.normalize('NFC').toUpperCase().toLowerCase();
    assert.ok(!seen.has(key), 'Patient paths collide on another filesystem'); seen.add(key);
  }
}
function manifest(raw, now) {
  assert.ok(raw instanceof Uint8Array && raw.length <= MAX_REVIEW_BYTES, 'Patient manifest exceeds its bound');
  const value = canonical(raw, true);
  assert.ok(exactKeys(value, REVIEW_FIELDS) && value.version === 1 && value.repository === REPO, 'Invalid patient review manifest');
  slug(value.file);
  assert.ok(typeof value.contentDate === 'string' && /^\d{4}-\d\d-\d\d$/.test(value.contentDate) &&
    Number.isFinite(Date.parse(value.contentDate)) && new Date(value.contentDate).toISOString().slice(0, 10) === value.contentDate, 'Invalid frozen patient content date');
  assert.ok(hash(value.archiveSha256), 'Invalid complete patient archive digest');
  const descriptor = value.patientManifest, p = descriptor?.trackedPackage;
  assert.ok(exactKeys(descriptor, PATIENT_FIELDS) && descriptor.version === 1 && descriptor.state === 'patient_package_recorded' &&
    ['generationVerified','liveAuthorIntentVerified','contentApproved','ciVerified','published'].every(name => descriptor[name] === false), 'Patient review requires an unapproved complete package');
  assert.ok(exactKeys(p, TRACKED_FIELDS) && p.version === 1 && p.repository === REPO && p.file === value.file && p.state === 'generated_package_recorded' &&
    ['generationVerified','contentApproved','ciVerified','published'].every(name => p[name] === false), 'Invalid recorded patient Git package');
  for (const name of ['pipelineHead','sourceHead','generatedHead','generatedTreeSha']) assert.ok(sha(p[name]), 'Invalid patient package SHA');
  const proof = p.sourceEvidence;
  assert.ok(exactKeys(proof, FIELDS) && proof.version === 1 && proof.file === value.file && proof.action !== 'unpublish' && proof.preparedAgainst === p.pipelineHead, 'Patient review lost its original source approval');
  validateReceiptEntry(proof, now);
  const rows = p.files, extra = descriptor.extraFiles;
  assert.ok(rows && typeof rows === 'object' && !Array.isArray(rows) && Object.keys(rows).length &&
    extra && typeof extra === 'object' && !Array.isArray(extra) && Object.hasOwn(extra, 'pagefind/pagefind.js'), 'Patient review lacks its complete inventory');
  const names = [...Object.keys(rows), ...Object.keys(extra)]; paths(names);
  assert.ok(names.length <= 10000, 'Patient review file count exceeds its bound');
  let total = 0;
  for (const name of names) {
    const tracked = Object.hasOwn(rows, name), row = tracked ? rows[name] : extra[name];
    assert.ok(exactKeys(row, tracked ? ['mode','blobSha','size','sha256'] : ['size','sha256']) &&
      Number.isInteger(row.size) && row.size >= 0 && row.size <= 50000000 && hash(row.sha256), 'Invalid patient output identity');
    assert.ok(tracked ? !name.startsWith('pagefind/') && ['100644','100755'].includes(row.mode) && sha(row.blobSha) : name.startsWith('pagefind/'), 'Invalid patient Git mode or ignored output path');
    total += row.size;
  }
  assert.ok(total <= 256000000, 'Patient review bytes exceed their bound');
  for (const name of [value.file, 'en/' + value.file, FILE]) assert.ok(Object.hasOwn(rows, name) && rows[name].mode === '100644', 'Patient review lacks Chinese, English or source receipt');
  return value;
}
async function parent(api, head, expected) {
  assert.ok(sha(head) && sha(expected), 'Invalid patient history SHA');
  const record = await api('/git/commits/' + head);
  assert.equal(record?.sha, head, 'Patient history commit unavailable');
  assert.deepEqual(record.parents?.map(p => p.sha), [expected], 'Patient history is not the exact direct successor');
  assert.ok(sha(record.tree?.sha), 'Patient history tree unavailable');
  return record;
}
async function changedOne(api, before, after, path, identity) {
  const record = await api('/compare/' + before + '...' + after);
  assert.ok(record?.status === 'ahead' && record.total_commits === 1 && record.merge_base_commit?.sha === before, 'Patient control history invalid');
  assert.deepEqual(record.files?.map(row => row.filename), [path], 'Patient control commit changed other files');
  const row = record.files[0];
  assert.ok(['added','modified'].includes(row.status) && row.sha === identity && Number.isInteger(row.changes) && row.changes > 0 && !Object.hasOwn(row, 'previous_filename'), 'Patient control diff is not ordinary');
}
async function leafTree(api, head, trees, ops) {
  const { tree } = ops;
  const rows = new Map([...await tree(api, head, trees)].filter(([, row]) => row.type !== 'tree'));
  paths([...rows.keys()]); assert.ok(rows.size <= 10000, 'Patient Git tree count exceeds its bound');
  for (const row of rows.values()) assert.ok(row.type === 'blob' && ['100644','100755'].includes(row.mode) && sha(row.sha), 'Patient Git tree contains a link or submodule');
  return rows;
}
const sameEntry = (a, b) => a && b && a.mode === b.mode && a.type === b.type && a.sha === b.sha;
async function loadReview(api, reviewHead, file, trees, expectedSource, now, ops) {
  const { blob, digest } = ops;
  assert.ok(sha(reviewHead), 'Invalid patient review head');
  const path = reviewPath(file), saved = await blob(api, path, reviewHead, MAX_REVIEW_BYTES, trees);
  const value = manifest(saved.raw, now), p = value.patientManifest.trackedPackage, proof = p.sourceEvidence;
  assert.equal(value.file, file, 'Patient review belongs to another article');
  if (expectedSource) assert.deepEqual(proof, expectedSource, 'Patient review belongs to another source request');
  await parent(api, reviewHead, p.generatedHead);
  await changedOne(api, p.generatedHead, reviewHead, path, saved.sha);
  const generated = await parent(api, p.generatedHead, p.sourceHead);
  assert.equal(generated.tree.sha, p.generatedTreeSha, 'Patient generated tree changed');
  await parent(api, p.sourceHead, p.pipelineHead);
  const generatedRows = await leafTree(api, p.generatedHead, trees, ops);
  assert.deepEqual([...generatedRows.keys()].sort(), Object.keys(p.files).sort(), 'Patient review omits or adds a Git output');
  for (const [name, row] of Object.entries(p.files)) assert.ok(generatedRows.get(name)?.mode === row.mode && generatedRows.get(name)?.sha === row.blobSha, 'Patient immutable output changed');
  const source = await leafTree(api, p.sourceHead, trees, ops), pipeline = await leafTree(api, p.pipelineHead, trees, ops);
  for (const [name, row] of generatedRows) if (row.mode === '100755') assert.ok(sameEntry(source.get(name), row), 'Patient generation changed an executable');
  const changed = [...new Set([...source.keys(), ...pipeline.keys()])].filter(name => !sameEntry(source.get(name), pipeline.get(name)));
  assert.ok(changed.includes(FILE) && changed.every(name => name === FILE || Object.hasOwn(proof.sourceSha256, name)), 'Patient source changed unrelated files');
  const receipt = await blob(api, FILE, p.sourceHead, 128000, trees);
  const record = canonical(receipt.raw, true);
  assert.deepEqual(record, { version: 1, requests: [proof] }, 'Patient review must prepare one active source request');
  for (const [name, identity] of Object.entries(proof.sourceSha256)) assert.equal(await digest((await blob(api, name, p.sourceHead, 1500000, trees)).raw), identity, 'Patient source differs from original approval');
  assert.equal(generatedRows.get(FILE)?.sha, source.get(FILE)?.sha, 'Patient generation changed its source receipt');
  return { value, ...saved };
}
function expectedRequest(entry, review) {
  const p = sourceEntry(entry), a = entry.patientApproval;
  const original = { version: 1, file: p.file, action: p.action, draftHead: p.draftHead,
    manifestSha: p.manifestSha, blobSha: p.articleBlobSha, baseSha: p.baseSha, approvedBy: p.approvedBy,
    contentApproved: true, requestedAt: p.requestedAt, scheduledAt: p.scheduledAt };
  return { version: 2, file: p.file, sourceRequestHead: p.requestHead, sourceRequest: original,
    reviewHead: a.reviewHead, manifestBlobSha: a.manifestBlobSha, manifestSha256: a.manifestSha256,
    archiveSha256: review.archiveSha256, contentDate: review.contentDate,
    approvedBy: 'expertise88864', approvedAt: a.approvedAt, contentApproved: true };
}

export { validateApproval, validateReceiptEntry, sourceEntry, manifest, loadReview, expectedRequest,
  parent, changedOne, leafTree, reviewPath, equal, sha, time, slug, exactKeys, FIELDS,
  APPROVAL_FIELDS, REQUEST_FIELDS, REVIEW_FIELDS, MAX_REVIEW_BYTES };
