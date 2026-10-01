// Purpose-specific, cookie-authenticated article drafts. This endpoint cannot
// update main, choose a repository/ref, or publish a production deployment.
import { getSession } from './_session.js';
import { parse } from 'parse5';
import { observePublication } from './_article-publication.js';
import publicationPolicy from '../../_delivery_policy.json';

export const config = { runtime: 'edge' };

const REPO = 'expertise88864/user';
const SHA = /^(?!0{40}$)[a-f0-9]{40}$/;
const MAX_BODY = 3_500_000;
const MAX_API_RESPONSE = 10_000_000;
const MAX_HTML = 1_500_000;
const MAX_MEDIA = 16;
const MAX_MEDIA_BASE64 = 1_900_000;
const MAX_MEDIA_RAW_BYTES = Math.floor(MAX_MEDIA_BASE64 / 4) * 3;
const RESERVED = new Set(['index', 'topics', 'charts']);
const encoder = new TextEncoder();

class DraftError extends Error {
  constructor(status, code) { super(code); this.status = status; this.code = code; }
}
function fail(status, code) { throw new DraftError(status, code); }
function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
    Vary: 'Cookie',
  } });
}
function article(file) {
  const match = typeof file === 'string' && /^blog\/([a-z0-9]+(?:-[a-z0-9]+)*)\.html$/.exec(file);
  if (!match || match[1].length > 100 || RESERVED.has(match[1])) fail(400, 'invalid_article');
  return { file, slug: match[1], branch: 'drafts/' + match[1], manifest: '.cms-drafts/' + match[1] + '.json',
    request: '.cms-requests/' + match[1] + '.json' };
}
function validSha(value, nullable = false) {
  if (nullable && value === null) return value;
  if (typeof value !== 'string' || !SHA.test(value)) fail(400, 'invalid_revision');
  return value;
}
function articleMetadata(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).some(key => !['title_en', 'tag', 'tag_en', 'cat', 'date'].includes(key))) fail(400, 'invalid_article_metadata');
  for (const name of ['title_en', 'tag', 'tag_en']) {
    if (typeof value[name] !== 'string' || !value[name].trim() || value[name].length > (name === 'title_en' ? 180 : 64) || /[\x00-\x1f]/.test(value[name])) fail(400, 'invalid_article_metadata');
  }
  if (!['myth', 'rx', 'product', 'note', 'research'].includes(value.cat) || !/^\d{4}-\d{2}-\d{2}$/.test(value.date || '') ||
      !Number.isFinite(Date.parse(value.date)) || new Date(value.date).toISOString().slice(0, 10) !== value.date) fail(400, 'invalid_article_metadata');
  return { title_en: value.title_en.trim(), tag: value.tag.trim(), tag_en: value.tag_en.trim(), cat: value.cat, date: value.date };
}
function encode(value) {
  const bytes = encoder.encode(value);
  let binary = '';
  for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(binary);
}
function github(pat) {
  return async (method, path, body, missing = false) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12_000);
    try {
      const response = await fetch('https://api.github.com/repos/' + REPO + '/' + path, {
        method, redirect: 'error', cache: 'no-store', signal: controller.signal,
        headers: { Authorization: 'Bearer ' + pat,
          Accept: path.startsWith('contents/') ? 'application/vnd.github.object+json' : 'application/vnd.github+json',
          'Content-Type': 'application/json', 'User-Agent': 'ChenDermatologist-Drafts/1.0', 'Cache-Control': 'no-cache',
          'X-GitHub-Api-Version': '2022-11-28' },
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      if (missing && response.status === 404) return null;
      if (response.status === 409 || response.status === 422) fail(409, 'draft_conflict');
      if (!response.ok) fail(502, 'repository_unavailable');
      if (!response.body) fail(502, 'repository_unavailable');
      const reader = response.body.getReader(), chunks = [];
      let length = 0;
      try {
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          length += value.byteLength;
          if (length > MAX_API_RESPONSE) fail(502, 'repository_unavailable');
          chunks.push(value);
        }
      } finally { await reader.cancel(); }
      const bytes = new Uint8Array(length);
      let offset = 0;
      for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
      return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
    } catch (error) {
      if (error instanceof DraftError) throw error;
      fail(502, 'repository_unavailable');
    } finally { clearTimeout(timeout); }
  };
}
async function ref(api, branch) {
  const data = await api('GET', 'git/ref/heads/' + encodeURIComponent(branch), null, true);
  return data ? validSha(data.object && data.object.sha) : null;
}
async function repositoryBlob(api, data, limit, status, code) {
  if (!data || data.type !== 'file' || !SHA.test(data.sha || '') ||
      !Number.isInteger(data.size) || data.size < 0 || data.size > limit) fail(status, code);
  // Contents omits bytes above 1 MB. Its exact immutable Git blob must agree
  // with that metadata, and the bytes must agree with the Git object digest.
  const blob = data.encoding === 'base64' ? data : await api('GET', 'git/blobs/' + data.sha);
  if (!blob || blob.sha !== data.sha || blob.size !== data.size || blob.encoding !== 'base64' ||
      typeof blob.content !== 'string') fail(status, code);
  const base64 = blob.content.replace(/\s/g, '');
  if (base64.length !== Math.ceil(data.size / 3) * 4 ||
      !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(base64)) fail(status, code);
  let bytes;
  try { bytes = Uint8Array.from(atob(base64), c => c.charCodeAt(0)); }
  catch (_) { fail(status, code); }
  if (bytes.length !== data.size) fail(status, code);
  const header = encoder.encode('blob ' + bytes.length + '\0');
  const object = new Uint8Array(header.length + bytes.length);
  object.set(header); object.set(bytes, header.length);
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-1', object)), b => b.toString(16).padStart(2, '0')).join('');
  if (digest !== data.sha) fail(status, code);
  return { bytes, base64 };
}
async function fileAt(api, file, commit, optional = false) {
  const data = await api('GET', 'contents/' + file + '?ref=' + commit, null, optional);
  if (!data) return null;
  const verified = await repositoryBlob(api, data, MAX_HTML, 502, 'invalid_repository_content');
  let content;
  try { content = new TextDecoder('utf-8', { fatal: true }).decode(verified.bytes); }
  catch (_) { fail(502, 'invalid_repository_content'); }
  return { sha: data.sha, content };
}
function mainIndexable(content) {
  if (content === null) return false;
  const errors = [];
  const doc = parse(content, { sourceCodeLocationInfo: true, onParseError: error => {
    if (error.code === 'duplicate-attribute') errors.push(error.startOffset);
  } });
  let indexable = true;
  function visit(node) {
    if (node.tagName === 'meta') {
      const attrs = Object.fromEntries((node.attrs || []).map(attr => [attr.name, attr.value]));
      const location = node.sourceCodeLocation;
      if (location && errors.some(offset => offset >= location.startOffset && offset < location.endOffset)) indexable = false;
      if (['robots', 'googlebot'].includes((attrs.name || '').toLowerCase()) &&
          /(?:^|[\s,])(?:noindex|none)(?:$|[\s,])/i.test(attrs.content || '')) indexable = false;
    }
    // Template content is a separate fragment and is deliberately not visited.
    for (const child of node.childNodes || []) visit(child);
  }
  visit(doc);
  return indexable;
}
async function state(api, target) {
  const main = await ref(api, 'main');
  if (!main) fail(502, 'main_unavailable');
  const published = await fileAt(api, target.file, main, true);
  const indexed = mainIndexable(published && published.content);
  const head = await ref(api, target.branch);
  if (!head) return { main, head: null, baseSha: published && published.sha,
    blobSha: published && published.sha, content: published && published.content,
    assets: [], metadata: null, manifestSha: null, mainBlobSha: published && published.sha, mainIndexable: indexed, legacy: false, conflict: false };
  const draft = await fileAt(api, target.file, head);
  const manifest = await fileAt(api, target.manifest, head, true);
  // Never infer permission to replace a draft the editor has never loaded.
  if (!manifest) return { main, head, content: draft.content, blobSha: draft.sha,
    baseSha: null, mainBlobSha: published && published.sha, mainIndexable: indexed, assets: [], legacy: true, conflict: true };
  let record;
  try { record = JSON.parse(manifest.content); } catch (_) { fail(409, 'invalid_draft_record'); }
  if (!record || record.version !== 1 || record.file !== target.file ||
      !SHA.test(record.baseMain) || !(record.baseSha === null || SHA.test(record.baseSha)) ||
      record.blobSha !== draft.sha || !Array.isArray(record.assets) || record.assets.length > MAX_MEDIA) {
    fail(409, 'invalid_draft_record');
  }
  for (const asset of record.assets) {
    if (!asset || !mediaPath(asset.path, target.slug) || !SHA.test(asset.sha) ||
        !Number.isInteger(asset.size) || asset.size < 8 || asset.size > MAX_MEDIA_RAW_BYTES) fail(409, 'invalid_draft_record');
  }
  if (record.assets.reduce((sum, asset) => sum + Math.ceil(asset.size / 3) * 4, 0) > MAX_MEDIA_BASE64) fail(413, 'draft_too_large');
  return { main, head, baseSha: record.baseSha, mainBlobSha: published && published.sha, mainIndexable: indexed, blobSha: draft.sha, content: draft.content,
    assets: record.assets, metadata: record.metadata ? articleMetadata(record.metadata) : null, manifestSha: manifest.sha,
    legacy: false, conflict: record.baseSha !== (published && published.sha) };
}
function requestRecord(record, target) {
  const allowed = ['version', 'file', 'action', 'draftHead', 'manifestSha', 'blobSha', 'baseSha',
    'approvedBy', 'contentApproved', 'requestedAt', 'scheduledAt'];
  if (!record || typeof record !== 'object' || Array.isArray(record) ||
      Object.keys(record).some(key => !allowed.includes(key)) || record.version !== 1 || record.file !== target.file ||
      !['review', 'schedule', 'unpublish'].includes(record.action) ||
      !SHA.test(record.draftHead || '') || !SHA.test(record.manifestSha || '') || !SHA.test(record.blobSha || '') ||
      !(record.baseSha === null || SHA.test(record.baseSha || '')) || record.approvedBy !== 'expertise88864' ||
      record.contentApproved !== (record.action !== 'unpublish') ||
      typeof record.requestedAt !== 'string' || !Number.isFinite(Date.parse(record.requestedAt)) ||
      new Date(record.requestedAt).toISOString() !== record.requestedAt ||
      (record.action === 'schedule'
        ? typeof record.scheduledAt !== 'string' || !Number.isFinite(Date.parse(record.scheduledAt)) ||
          new Date(record.scheduledAt).toISOString() !== record.scheduledAt
        : record.scheduledAt !== null)) fail(409, 'invalid_publication_request');
  return record;
}
async function publicationState(api, target, loaded) {
  if (!loaded.head) return null;
  const stored = await fileAt(api, target.request, loaded.head, true);
  if (!stored) return null;
  let record;
  try { record = requestRecord(JSON.parse(stored.content), target); }
  catch (_) { return { status: 'invalidated' }; }
  const parent = await api('GET', 'git/commits/' + loaded.head);
  // A request approves the loaded draft, and its own commit must be the one
  // immediate successor. Later edits or arbitrary branch commits invalidate it.
  if (loaded.legacy || loaded.conflict || record.blobSha !== loaded.blobSha ||
      record.baseSha !== loaded.baseSha || record.manifestSha !== loaded.manifestSha ||
      !Array.isArray(parent.parents) || parent.parents.length !== 1 ||
      parent.parents[0].sha !== record.draftHead) return { status: 'invalidated' };
  return { action: record.action, status: record.action === 'schedule' ? 'schedule_requested' :
    record.action === 'unpublish' ? 'unpublish_requested' : 'awaiting_review',
    requestedAt: record.requestedAt, scheduledAt: record.scheduledAt, blobSha: record.blobSha };
}
async function requestPublication(api, target, input) {
  if (!input || typeof input !== 'object' || Object.keys(input).some(key =>
    !['file', 'action', 'expectedHead', 'baseSha', 'expectedBlob', 'contentApproved', 'confirmed', 'scheduledAt'].includes(key)) ||
    !['review', 'schedule', 'unpublish', 'cancel'].includes(input.action)) fail(400, 'invalid_publication_request');
  validSha(input.expectedHead); validSha(input.baseSha, true); validSha(input.expectedBlob);
  if (['unpublish', 'cancel'].includes(input.action) ? input.confirmed !== true : input.contentApproved !== true) fail(400, 'author_confirmation_required');
  let scheduledAt = null;
  if (input.action === 'schedule') {
    if (typeof input.scheduledAt !== 'string' || !Number.isFinite(Date.parse(input.scheduledAt)) ||
        new Date(input.scheduledAt).toISOString() !== input.scheduledAt ||
        Date.parse(input.scheduledAt) <= Date.now() || Date.parse(input.scheduledAt) > Date.now() + 365 * 86400_000) fail(400, 'invalid_schedule');
    scheduledAt = input.scheduledAt;
  } else if (input.scheduledAt !== undefined && input.scheduledAt !== null) fail(400, 'invalid_schedule');
  const loaded = await state(api, target);
  if (loaded.legacy) fail(409, 'legacy_draft_requires_review');
  if (!loaded.head || loaded.head !== input.expectedHead || loaded.baseSha !== input.baseSha ||
      loaded.blobSha !== input.expectedBlob || (loaded.conflict && input.action !== 'cancel')) fail(409, 'draft_conflict');
  if (input.action === 'unpublish' && loaded.baseSha === null) fail(400, 'article_not_published');
  // A previous request cannot be silently replaced or reconfirmed by a retry.
  const previous = await publicationState(api, target, loaded);
  if (input.action === 'cancel' ? !previous : previous && previous.status !== 'invalidated') fail(409, input.action === 'cancel' ? 'request_missing' : 'request_already_saved');
  if (input.action !== 'cancel') await validateMedia(await draftMedia(api, loaded), target.slug);
  const parent = await api('GET', 'git/commits/' + loaded.head);
  if (!parent.tree || !SHA.test(parent.tree.sha)) fail(502, 'invalid_repository_content');
  const record = { version: 1, file: target.file, action: input.action, draftHead: loaded.head,
    manifestSha: loaded.manifestSha, blobSha: loaded.blobSha, baseSha: loaded.baseSha,
    approvedBy: 'expertise88864', contentApproved: input.action !== 'unpublish',
    requestedAt: new Date().toISOString(), scheduledAt };
  const content = input.action === 'cancel' ? null : JSON.stringify(record) + '\n';
  const tree = await api('POST', 'git/trees', { base_tree: parent.tree.sha,
    tree: [{ path: target.request, mode: '100644', type: 'blob', ...(content === null ? { sha: null } : { content }) }] });
  const commit = await api('POST', 'git/commits', { message: '[request] ' + input.action + ' ' + target.file,
    tree: validSha(tree.sha), parents: [loaded.head] });
  const next = validSha(commit.sha);
  const result = await api('PATCH', 'git/refs/heads/' + encodeURIComponent(target.branch), { sha: next, force: false });
  if (!result.object || result.object.sha !== next) fail(502, 'request_not_verified');
  let accepted;
  try {
    const immutable = await fileAt(api, target.request, next, content === null);
    if (content === null ? immutable !== null : immutable.content !== content) fail(502, 'request_not_verified');
    const after = await state(api, target);
    if (after.head !== next) fail(502, 'request_not_verified');
    accepted = await publicationState(api, target, after);
    if (content === null ? accepted !== null : !accepted || accepted.status === 'invalidated') fail(502, 'request_not_verified');
  } catch (_) { fail(502, 'request_not_verified'); }
  return { file: target.file, head: next, baseSha: loaded.baseSha, blobSha: loaded.blobSha,
    request: accepted, verified: true, published: false };
}
// Start a new editing cycle from an independently verified production version.
// Keep the old draft as a parent; do not rewrite history or retire delivery proof.
async function newVersion(api, target, input) {
  const keys = ['file', 'action', 'expectedHead', 'expectedBlob', 'expectedMain', 'expectedMainBlob', 'confirmed'];
  if (Object.keys(input).some(key => !keys.includes(key))) fail(400, 'invalid_publication_request');
  for (const key of ['expectedHead', 'expectedBlob', 'expectedMain', 'expectedMainBlob']) validSha(input[key]);
  if (input.confirmed !== true) fail(400, 'author_confirmation_required');
  const loaded = await state(api, target);
  if (loaded.legacy) fail(409, 'legacy_draft_requires_review');
  if (loaded.head !== input.expectedHead || loaded.blobSha !== input.expectedBlob ||
      loaded.main !== input.expectedMain || loaded.mainBlobSha !== input.expectedMainBlob) fail(409, 'draft_conflict');
  const proof = await observePublication(api, loaded, publicationPolicy);
  if (proof.state !== 'live' || !proof.ciVerified || !proof.deploymentVerified ||
      proof.mainSha !== input.expectedMain || proof.mainBlobSha !== input.expectedMainBlob) fail(409, 'publication_not_verified');

  const published = await fileAt(api, target.file, loaded.main);
  const productionCommit = await api('GET', 'git/commits/' + loaded.main);
  if (productionCommit.sha !== loaded.main || !SHA.test(productionCommit.tree?.sha || '')) fail(502, 'invalid_repository_content');
  const tree = await api('GET', 'git/trees/' + productionCommit.tree.sha + '?recursive=1');
  if (tree.sha !== productionCommit.tree.sha || tree.truncated !== false ||
      !Array.isArray(tree.tree) || tree.tree.length > 10000) fail(502, 'invalid_repository_content');
  const entries = new Map();
  for (const entry of tree.tree) {
    if (typeof entry.path !== 'string' || entries.has(entry.path)) fail(502, 'invalid_repository_content');
    entries.set(entry.path, entry);
  }
  function ordinary(path, sha) {
    const entry = entries.get(path);
    if (!entry || entry.mode !== '100644' || entry.type !== 'blob' || !SHA.test(entry.sha || '') ||
        (sha && entry.sha !== sha)) fail(409, 'invalid_repository_content');
    return entry;
  }
  ordinary(target.file, published.sha);
  if (published.sha !== input.expectedMainBlob || !mainIndexable(published.content)) fail(409, 'publication_not_verified');
  const receipt = await fileAt(api, '.cms-delivery.json', loaded.main, true);
  if (!receipt) fail(409, 'publication_receipt_not_retired');
  ordinary('.cms-delivery.json', receipt.sha);
  let delivery;
  try { delivery = JSON.parse(receipt.content); } catch (_) { fail(409, 'publication_receipt_not_retired'); }
  if (!delivery || delivery.version !== 1 || Object.keys(delivery).some(key => !['version', 'requests'].includes(key)) ||
      !Array.isArray(delivery.requests) || delivery.requests.some(record => !record ||
        typeof record.file !== 'string' || !/^blog\/[a-z0-9]+(?:-[a-z0-9]+)*\.html$/.test(record.file) || record.file === target.file)) {
    fail(409, 'publication_receipt_not_retired');
  }
  const paths = [...referencedMedia(published.content, target)];
  if (paths.length > MAX_MEDIA) fail(413, 'draft_too_large');
  const assets = paths.map(path => {
    const entry = ordinary(path);
    if (!Number.isInteger(entry.size) || entry.size < 8 || entry.size > MAX_MEDIA_RAW_BYTES) fail(409, 'invalid_draft_media');
    return { path, sha: entry.sha, size: entry.size };
  });
  if (assets.reduce((sum, asset) => sum + Math.ceil(asset.size / 3) * 4, 0) > MAX_MEDIA_BASE64) fail(413, 'draft_too_large');
  const media = await draftMedia(api, { head: loaded.main, assets });
  await validateMedia(media, target.slug);
  const parent = await api('GET', 'git/commits/' + loaded.head);
  if (!SHA.test(parent.tree?.sha || '')) fail(502, 'invalid_repository_content');
  const previousRequest = await fileAt(api, target.request, loaded.head, true);
  async function unchanged() {
    if (await ref(api, 'main') !== loaded.main || await ref(api, target.branch) !== loaded.head) fail(409, 'draft_conflict');
  }
  await unchanged();
  const manifest = JSON.stringify({ version: 1, file: target.file, baseMain: loaded.main,
    baseSha: published.sha, blobSha: published.sha, assets, metadata: null, status: 'draft' }) + '\n';
  const changes = [{ path: target.file, mode: '100644', type: 'blob', sha: published.sha },
    { path: target.manifest, mode: '100644', type: 'blob', content: manifest },
    ...assets.map(asset => ({ path: asset.path, mode: '100644', type: 'blob', sha: asset.sha }))];
  if (previousRequest) changes.push({ path: target.request, mode: '100644', type: 'blob', sha: null });
  const nextTree = await api('POST', 'git/trees', { base_tree: parent.tree.sha, tree: changes });
  const nextCommit = await api('POST', 'git/commits', { message: '[draft] new version ' + target.file,
    tree: validSha(nextTree.sha), parents: [loaded.head] });
  const next = validSha(nextCommit.sha);
  await unchanged();
  const result = await api('PATCH', 'git/refs/heads/' + encodeURIComponent(target.branch), { sha: next, force: false });
  if (result.object?.sha !== next) fail(502, 'new_version_not_verified');
  try {
    const after = await state(api, target);
    const savedManifest = await fileAt(api, target.manifest, next);
    const savedMedia = await draftMedia(api, after);
    if (after.main !== loaded.main || after.head !== next || after.blobSha !== published.sha ||
        after.baseSha !== published.sha || after.conflict || after.content !== published.content ||
        savedManifest.content !== manifest || await fileAt(api, target.request, next, true) !== null ||
        JSON.stringify(savedMedia) !== JSON.stringify(media)) fail(502, 'new_version_not_verified');
  } catch (_) { fail(502, 'new_version_not_verified'); }
  return { file: target.file, head: next, baseSha: published.sha, blobSha: published.sha,
    branch: target.branch, metadata: null, status: 'cloud_draft', verified: true, published: false };
}
async function listDrafts(api, query) {
  const offsetText = query.get('offset') || '0';
  if (!/^(?:0|[1-9]\d{0,2})$/.test(offsetText)) fail(400, 'invalid_list_offset');
  const offset = Number(offsetText), refs = await api('GET', 'git/matching-refs/heads/drafts/');
  if (!Array.isArray(refs) || refs.length > 200) fail(502, 'draft_list_unavailable');
  const valid = refs.filter(item => {
    const match = /^refs\/heads\/drafts\/([a-z0-9]+(?:-[a-z0-9]+)*)$/.exec(item.ref || '');
    return match && match[1].length <= 100 && !RESERVED.has(match[1]);
  });
  if (offset > valid.length) fail(400, 'invalid_list_offset');
  const selected = valid.slice(offset, offset + 20), drafts = [];
  for (let i = 0; i < selected.length; i += 4) {
    const batch = await Promise.all(selected.slice(i, i + 4).map(async item => {
      const slug = item.ref.slice('refs/heads/drafts/'.length), target = article('blog/' + slug + '.html'), head = validSha(item.object && item.object.sha);
      const saved = await fileAt(api, target.manifest, head, true);
      if (!saved) return { file: target.file, head, legacy: true };
      let record;
      try { record = JSON.parse(saved.content); } catch (_) { fail(409, 'invalid_draft_record'); }
      if (!record || record.version !== 1 || record.file !== target.file || !SHA.test(record.blobSha)) fail(409, 'invalid_draft_record');
      return { file: target.file, head, legacy: false };
    }));
    drafts.push(...batch);
  }
  return { drafts, nextOffset: offset + selected.length < valid.length ? offset + selected.length : null,
    unsupportedRefs: refs.length - valid.length };
}
async function draftMedia(api, loaded) {
  const media = [];
  // Read the immutable accepted draft; public URLs do not yet contain uploads.
  // Use a small bounded batch rather than sixteen unbounded parallel requests.
  for (let i = 0; i < loaded.assets.length; i += 4) {
    const batch = await Promise.all(loaded.assets.slice(i, i + 4).map(async asset => {
      const data = await api('GET', 'contents/' + asset.path + '?ref=' + loaded.head);
      if (data.type !== 'file' || data.sha !== asset.sha || data.size !== asset.size) fail(409, 'invalid_draft_media');
      const verified = await repositoryBlob(api, data, MAX_MEDIA_RAW_BYTES, 409, 'invalid_draft_media');
      return { path: asset.path, base64: verified.base64 };
    }));
    media.push(...batch);
    if (encoder.encode(JSON.stringify(media)).length > MAX_MEDIA_BASE64 + 4096) fail(413, 'draft_too_large');
  }
  return media;
}
function mediaPath(path, slug) {
  return typeof path === 'string' && new RegExp('^blog/images/' + slug + '/[a-f0-9]{64}\\.(webp|png|jpg|gif)$').test(path);
}
async function validateMedia(media, slug) {
  if (!Array.isArray(media) || media.length > MAX_MEDIA) fail(400, 'invalid_media');
  const paths = new Set(); let total = 0;
  for (const item of media) {
    if (!item || !mediaPath(item.path, slug) || paths.has(item.path) ||
        typeof item.base64 !== 'string' || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(item.base64)) {
      fail(400, 'invalid_media');
    }
    paths.add(item.path);
    total += item.base64.length;
    if (total > MAX_MEDIA_BASE64) fail(413, 'draft_too_large');
    const bytes = Uint8Array.from(atob(item.base64), c => c.charCodeAt(0));
    if (bytes.length < 8) fail(400, 'invalid_media_type');
    const hex = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), b => b.toString(16).padStart(2, '0')).join('');
    if (!item.path.includes('/' + hex + '.')) fail(400, 'invalid_media_digest');
    // Only raster images; executable SVG/HTML must not enter an upload path.
    const starts = Array.from(bytes.subarray(0, 12));
    const webp = starts.slice(0, 4).join() === '82,73,70,70' && starts.slice(8, 12).join() === '87,69,66,80';
    const png = starts.slice(0, 8).join() === '137,80,78,71,13,10,26,10';
    const jpg = starts[0] === 255 && starts[1] === 216 && starts[2] === 255;
    const gif = starts.slice(0, 6).join() === '71,73,70,56,55,97' || starts.slice(0, 6).join() === '71,73,70,56,57,97';
    const extension = item.path.split('.').pop();
    if (!({ webp, png, jpg, gif })[extension]) fail(400, 'invalid_media_type');
  }
}
async function bodyOf(req) {
  if (!(req.headers.get('content-type') || '').startsWith('application/json')) fail(415, 'json_required');
  const declared = Number(req.headers.get('content-length') || 0);
  if (declared > MAX_BODY) fail(413, 'draft_too_large');
  const reader = req.body && req.body.getReader();
  if (!reader) fail(400, 'invalid_request');
  const chunks = []; let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > MAX_BODY) { await reader.cancel(); fail(413, 'draft_too_large'); }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
  } catch (error) {
    if (error instanceof DraftError) throw error;
    fail(400, 'invalid_request');
  }
}
function referencedMedia(content, target) {
  const references = new Set(), tree = parse(content);
  function url(value) {
    // Parsing decodes entities; URL parsing handles whitespace and relative
    // paths as a browser would. Comments and script strings are not images.
    let parsed;
    try { parsed = new URL(value, 'https://chendermatologist.com/' + target.file); }
    catch (_) { fail(400, 'invalid_article_content'); }
    // Source mode must not bypass the Word editor's active-URL protection.
    // URL parsing also normalizes mixed case, decoded entities and controls.
    if (!['https:', 'http:', 'mailto:', 'tel:'].includes(parsed.protocol)) fail(400, 'invalid_article_content');
    if (parsed.origin !== 'https://chendermatologist.com') return;
    let path;
    try { path = decodeURIComponent(parsed.pathname).replace(/^\//, ''); }
    catch (_) { fail(400, 'invalid_article_content'); }
    if (path.startsWith('blog/images/' + target.slug + '/')) {
      if (!mediaPath(path, target.slug) || parsed.search || parsed.hash) fail(400, 'invalid_media_reference');
      references.add(path);
    }
  }
  function visit(node) {
    for (const attr of node.attrs || []) {
      if (['src', 'href', 'poster', 'xlink:href'].includes(attr.name)) url(attr.value);
      if (attr.name === 'srcset') {
        if (/\b(?:data|blob|file)\s*:/i.test(attr.value)) fail(400, 'invalid_article_content');
        for (const candidate of attr.value.split(',')) {
          const address = candidate.trim().split(/\s+/)[0];
          if (address) url(address);
        }
      }
    }
    for (const child of node.childNodes || []) visit(child);
    if (node.content) visit(node.content); // template content is parsed too.
  }
  visit(tree); return references;
}
async function save(api, target, input) {
  if (!input || typeof input !== 'object' || Object.keys(input).some(k => !['file', 'expectedHead', 'baseSha', 'content', 'media', 'message', 'metadata'].includes(k))) fail(400, 'invalid_request');
  validSha(input.expectedHead, true); validSha(input.baseSha, true);
  if (typeof input.content !== 'string' || !input.content.trim() || encoder.encode(input.content).length > MAX_HTML ||
      !/<html[\s>]/i.test(input.content) || !/<\/html\s*>/i.test(input.content) ||
      /\b(?:src|href)\s*=\s*["']\s*(?:blob:|file:\/\/)/i.test(input.content)) fail(400, 'invalid_article_content');
  const media = input.media || [];
  await validateMedia(media, target.slug);
  const references = referencedMedia(input.content, target);
  if (references.size > MAX_MEDIA) fail(400, 'invalid_media');
  const loaded = await state(api, target);
  if (loaded.legacy) fail(409, 'legacy_draft_requires_review');
  if (loaded.head !== input.expectedHead || loaded.baseSha !== input.baseSha || loaded.conflict) fail(409, 'draft_conflict');
  const metadata = input.metadata === undefined ? loaded.metadata || null : articleMetadata(input.metadata);
  if (loaded.baseSha === null && !metadata) fail(400, 'article_metadata_required');
  const assets = new Map(loaded.assets.filter(a => references.has(a.path)).map(a => [a.path, a]));
  const retained = [...assets.values()], adopted = [];
  for (const item of media) {
    if (!references.has(item.path)) fail(400, 'unreferenced_media');
    if (!assets.has(item.path)) assets.set(item.path, { path: item.path, sha: null,
      size: atob(item.base64).length });
  }
  // A published article may already use this upload namespace. Adopt only
  // immutable main assets, never unlisted orphan files from a draft branch.
  for (const path of references) {
    if (assets.has(path)) continue;
    const existing = await api('GET', 'contents/' + path + '?ref=' + loaded.main, undefined, true);
    if (!existing || existing.type !== 'file' || !SHA.test(existing.sha) || !Number.isInteger(existing.size) || existing.size < 8) fail(400, 'missing_draft_media');
    const asset = { path, sha: existing.sha, size: existing.size };
    assets.set(path, asset); adopted.push(asset);
  }
  if (assets.size > MAX_MEDIA) fail(400, 'invalid_media');
  // The whole saved bundle must remain reloadable, including previously saved
  // images omitted from this incremental request. Do this before any Git writes.
  if ([...assets.values()].reduce((sum, item) => sum + Math.ceil(item.size / 3) * 4, 0) > MAX_MEDIA_BASE64) fail(413, 'draft_too_large');
  // Existing bytes must satisfy the same digest/raster contract as uploads.
  // Their immutable Git SHA and size alone cannot prove a filename's SHA-256.
  if (retained.length) await validateMedia(await draftMedia(api, { head: loaded.head, assets: retained }), target.slug);
  if (adopted.length) await validateMedia(await draftMedia(api, { head: loaded.main, assets: adopted }), target.slug);
  const parentSha = loaded.head || loaded.main;
  const parent = await api('GET', 'git/commits/' + parentSha);
  if (!parent.tree || !SHA.test(parent.tree.sha)) fail(502, 'invalid_repository_content');
  const previousRequest = await fileAt(api, target.request, parentSha, true);
  const articleBlob = await api('POST', 'git/blobs', { content: encode(input.content), encoding: 'base64' });
  const blobSha = validSha(articleBlob.sha);
  const tree = [{ path: target.file, mode: '100644', type: 'blob', sha: blobSha }];
  for (const item of media) {
    const blob = await api('POST', 'git/blobs', { content: item.base64, encoding: 'base64' });
    const sha = validSha(blob.sha);
    assets.set(item.path, { path: item.path, sha, size: atob(item.base64).length });
    tree.push({ path: item.path, mode: '100644', type: 'blob', sha });
  }
  const record = { version: 1, file: target.file, baseMain: loaded.main, baseSha: input.baseSha,
    blobSha, assets: [...assets.values()], metadata, status: 'draft' };
  tree.push({ path: target.manifest, mode: '100644', type: 'blob', content: JSON.stringify(record) + '\n' });
  if (previousRequest) tree.push({ path: target.request, mode: '100644', type: 'blob', sha: null });
  const nextTree = await api('POST', 'git/trees', { base_tree: parent.tree.sha, tree });
  const commit = await api('POST', 'git/commits', { message: '[draft] ' + target.file,
    tree: validSha(nextTree.sha), parents: [parentSha] });
  const next = validSha(commit.sha);
  // Non-force update is a CAS: a concurrent writer makes this sibling commit
  // non-fast-forward. New drafts create the ref only after the complete bundle.
  const result = loaded.head
    ? await api('PATCH', 'git/refs/heads/' + encodeURIComponent(target.branch), { sha: next, force: false })
    : await api('POST', 'git/refs', { ref: 'refs/heads/' + target.branch, sha: next });
  if (!result.object || result.object.sha !== next) fail(502, 'save_not_verified');
  try {
    const accepted = await fileAt(api, target.file, next);
    if (accepted.sha !== blobSha || accepted.content !== input.content) fail(502, 'save_not_verified');
    const acceptedRecord = await fileAt(api, target.manifest, next);
    if (acceptedRecord.content !== JSON.stringify(record) + '\n') fail(502, 'save_not_verified');
    if (previousRequest && await fileAt(api, target.request, next, true)) fail(502, 'save_not_verified');
    const acceptedMedia = await draftMedia(api, { head: next, assets: record.assets });
    for (const item of media) {
      const saved = acceptedMedia.find(a => a.path === item.path);
      if (!saved || saved.base64 !== item.base64) fail(502, 'save_not_verified');
    }
  } catch (_) { fail(502, 'save_not_verified'); }
  return { file: target.file, head: next, baseSha: input.baseSha, blobSha,
    branch: target.branch, metadata, status: 'cloud_draft', verified: true, published: false };
}

export default async function handler(req) {
  if (!['GET', 'POST'].includes(req.method)) return new Response(null, { status: 405, headers: { Allow: 'GET, POST', 'Cache-Control': 'no-store' } });
  try {
    if (req.method === 'POST' && (req.headers.get('origin') !== new URL(req.url).origin ||
        (req.headers.has('sec-fetch-site') && req.headers.get('sec-fetch-site') !== 'same-origin'))) fail(403, 'same_origin_required');
    const session = await getSession(req);
    if (!session || !session.pat || session.login !== 'expertise88864') fail(401, 'login_required');
    const api = github(session.pat);
    if (req.method === 'GET') {
      const query = new URL(req.url).searchParams;
      if (query.get('mode') === 'list') return json(200, await listDrafts(api, query));
      const target = article(new URL(req.url).searchParams.get('file'));
      const loaded = await state(api, target);
      const publication = await publicationState(api, target, loaded);
      if (query.get('mode') === 'publication') return json(200, {
        file: target.file, head: loaded.head, baseSha: loaded.baseSha, blobSha: loaded.blobSha,
        publication: await observePublication(api, loaded, publicationPolicy),
      });
      if (new URL(req.url).searchParams.get('mode') === 'status') return json(200, {
        file: target.file, head: loaded.head, baseSha: loaded.baseSha, blobSha: loaded.blobSha,
        conflict: loaded.conflict, legacy: loaded.legacy, request: publication,
      });
      return json(200, { file: target.file, branch: target.branch, ...loaded, request: publication,
        media: await draftMedia(api, loaded),
        status: loaded.head ? 'cloud_draft' : loaded.content !== null ? 'published_base' : 'not_created',
        sourceOnMain: loaded.mainBlobSha !== null, published: false, deploymentVerified: false });
    }
    const input = await bodyOf(req);
    const target = article(input && input.file);
    return json(200, input.action === undefined ? await save(api, target, input) : input.action === 'new-version'
      ? await newVersion(api, target, input) : await requestPublication(api, target, input));
  } catch (error) {
    return json(error instanceof DraftError ? error.status : 503,
      { ok: false, error: error instanceof DraftError ? error.code : 'draft_unavailable' });
  }
}
