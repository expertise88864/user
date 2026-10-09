// Purpose-specific, cookie-authenticated article drafts. This endpoint cannot
// update main, choose a repository/ref, or publish a production deployment.
import { getSession } from './_session.js';
import { parse } from 'parse5';
import { observePublication } from './_article-publication.js';
import publicationPolicy from '../../_delivery_policy.json';
import * as patientReview from './_patient-review-contract.js';

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
function repositoryRefSha(data, branch) {
  if (!data || data.ref !== 'refs/heads/' + branch || data.object?.type !== 'commit' ||
      typeof data.object.sha !== 'string' || !SHA.test(data.object.sha)) fail(502, 'invalid_repository_ref');
  return data.object.sha;
}
async function ref(api, branch) {
  const data = await api('GET', 'git/ref/heads/' + encodeURIComponent(branch), null, true);
  return data === null ? null : repositoryRefSha(data, branch);
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
function reviewReaders(api) {
  const read = path => api('GET', path.slice(1));
  async function tree(_read, head, cache) {
    if (!cache.has(head)) {
      const commit = await read('/git/commits/' + validSha(head));
      if (commit.sha !== head || !SHA.test(commit.tree?.sha || '')) fail(502, 'invalid_generated_review');
      const data = await read('/git/trees/' + commit.tree.sha + '?recursive=1');
      if (data.sha !== commit.tree.sha || data.truncated !== false || !Array.isArray(data.tree) || data.tree.length > 10000) fail(502, 'invalid_generated_review');
      const rows = new Map();
      for (const row of data.tree) {
        if (!row || typeof row.path !== 'string' || rows.has(row.path)) fail(502, 'invalid_generated_review');
        rows.set(row.path, row);
      }
      cache.set(head, rows);
    }
    return cache.get(head);
  }
  async function blob(_read, path, head, limit, cache) {
    const data = await read('/contents/' + path + '?ref=' + validSha(head));
    const stored = await repositoryBlob(api, data, limit, 502, 'invalid_generated_review');
    const entry = (await tree(read, head, cache)).get(path);
    if (!entry || entry.mode !== '100644' || entry.type !== 'blob' || entry.sha !== data.sha) fail(502, 'invalid_generated_review');
    return { sha: data.sha, raw: stored.bytes };
  }
  const digest = async bytes => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), b => b.toString(16).padStart(2, '0')).join('');
  return { read, ops: { tree, blob, digest } };
}
async function reviewPreview(api, head, branch, main) {
  const prs = await api('GET', 'commits/' + head + '/pulls?per_page=100');
  if (!Array.isArray(prs) || prs.length >= 100) fail(502, 'generated_review_unavailable');
  const matching = prs.filter(p => p.state === 'open' && p.head?.sha === head && p.head?.ref === branch &&
    p.base?.ref === 'main' && p.base?.sha === main && p.head?.repo?.full_name === REPO && p.base?.repo?.full_name === REPO &&
    Number.isInteger(p.number) && p.number > 0);
  if (matching.length !== 1) fail(409, 'generated_review_not_ready');
  const deployments = await api('GET', 'deployments?sha=' + head + '&environment=Preview&per_page=100');
  if (!Array.isArray(deployments) || deployments.length >= 100) fail(502, 'generated_review_unavailable');
  const candidates = deployments.filter(d => d.sha === head && d.environment === 'Preview' && d.production_environment === false &&
    ['vercel[bot]', 'vercel'].includes(d.creator?.login) && Number.isInteger(d.id) && d.id > 0).sort((a,b) => b.id-a.id);
  if (!candidates.length) fail(409, 'generated_review_not_ready');
  const statuses = await api('GET', 'deployments/' + candidates[0].id + '/statuses?per_page=100');
  if (!Array.isArray(statuses) || !statuses.length || statuses.length >= 100 || statuses.some(s => !Number.isInteger(s.id) || s.id <= 0)) fail(502, 'generated_review_unavailable');
  const status = [...statuses].sort((a,b) => b.id-a.id)[0];
  let url;
  try { url = new URL(status.environment_url); } catch (_) { fail(409, 'generated_review_not_ready'); }
  if (status.state !== 'success' || !['vercel[bot]', 'vercel'].includes(status.creator?.login) || url.protocol !== 'https:' ||
      url.username || url.password || url.port || url.search || url.hash || url.pathname !== '/' ||
      !/^chendermatologist-[a-z0-9]{9}-expertise88864s-projects\.vercel\.app$/.test(url.hostname)) fail(409, 'generated_review_not_ready');
  return { origin: url.origin, pr: matching[0].number, deploymentId: candidates[0].id, statusId: status.id };
}
async function generatedReview(api, target, loaded, selected = null) {
  if (!loaded.head || loaded.legacy || loaded.conflict || await deliveryLock(api, target, loaded.main)) fail(409, 'draft_conflict');
  const request = await publicationState(api, target, loaded);
  if (!request || !['awaiting_review', 'schedule_requested'].includes(request.status)) fail(409, 'generated_review_not_ready');
  const prefix = 'codex/cms-review/' + target.slug + '-';
  const refs = await api('GET', 'git/matching-refs/heads/' + prefix);
  if (!Array.isArray(refs) || refs.length > 50) fail(502, 'generated_review_unavailable');
  const candidates = refs.filter(r => typeof r.ref === 'string' && r.ref.startsWith('refs/heads/' + prefix) &&
    /^[a-z0-9-]{1,80}$/.test(r.ref.slice(('refs/heads/' + prefix).length)) && r.object?.type === 'commit' && SHA.test(r.object.sha || ''));
  if (selected !== null) validSha(selected);
  // Do not guess which prepared version the author should approve. An exact
  // loaded selection must still be one of the current repository review refs.
  if (candidates.length !== 1 || selected !== null && candidates[0].object.sha !== selected) fail(409, 'generated_review_changed');
  const branch = candidates[0].ref.slice('refs/heads/'.length), head = candidates[0].object.sha;
  const { read, ops } = reviewReaders(api);
  let saved;
  try { saved = await patientReview.loadReview(read, head, target.file, new Map(), null, Date.now(), ops); }
  catch (_) { fail(409, 'invalid_generated_review'); }
  const proof = saved.value.patientManifest.trackedPackage.sourceEvidence;
  if (saved.value.patientManifest.trackedPackage.pipelineHead !== loaded.main || proof.requestHead !== loaded.head ||
      proof.articleBlobSha !== loaded.blobSha || proof.baseSha !== loaded.baseSha || proof.manifestSha !== loaded.manifestSha) fail(409, 'generated_review_changed');
  const original = await fileAt(api, target.request, loaded.head);
  const approval = { reviewHead: head, manifestBlobSha: saved.sha, manifestSha256: await ops.digest(saved.raw), approvedAt: new Date().toISOString() };
  const expected = patientReview.expectedRequest({ ...proof, patientApproval: approval }, saved.value);
  if (JSON.stringify(expected.sourceRequest) + '\n' !== original.content) fail(409, 'invalid_generated_review');
  const preview = await reviewPreview(api, head, branch, loaded.main);
  const baseline = await ops.tree(read, loaded.main, new Map());
  const rows = saved.value.patientManifest.trackedPackage.files;
  const patientContent = path =>
    (/\.html$/.test(path) && !/^(?:en\/)?(?:admin(?:\/|\.html$)|(?:dashboard|reset-sw|offline|404)\.html$)/.test(path)) ||
    /^ai\/.+\.json$|^assets\/search-index\.json$|^llms(?:-full)?\.txt$|^(?:blog\/)?(?:feed|atom)\.xml$|^\.well-known\/ai\.txt$/.test(path) ||
    /\.(?:svg|png|jpe?g|gif|webp|avif)$/i.test(path) && !/^admin\//.test(path);
  const contentPaths = Object.keys(rows).filter(path => patientContent(path) && baseline.get(path)?.sha !== rows[path].blobSha);
  const removedContentPaths = [...baseline.keys()].filter(path => patientContent(path) && !Object.hasOwn(rows, path));
  for (const path of [target.file, 'en/' + target.file]) if (!contentPaths.includes(path)) contentPaths.push(path);
  await unchangedMain(api, loaded.main);
  if (await ref(api, target.branch) !== loaded.head || await ref(api, branch) !== head) fail(409, 'generated_review_changed');
  return { file: target.file, head: loaded.head, baseSha: loaded.baseSha, blobSha: loaded.blobSha,
    reviewHead: head, manifestBlobSha: saved.sha, manifestSha256: approval.manifestSha256,
    archiveSha256: saved.value.archiveSha256, contentDate: saved.value.contentDate,
    contentPaths: contentPaths.sort(), removedContentPaths: removedContentPaths.sort(),
    outputFiles: Object.keys(saved.value.patientManifest.trackedPackage.files).length + Object.keys(saved.value.patientManifest.extraFiles).length,
    preview, reviewBranch: branch, state: 'awaiting_generated_content_approval', contentApproved: false, ciVerified: false, published: false,
    // Server-only record. The handler omits it from the read response.
    finalRequest: expected };
}
async function unchangedGeneratedReview(api, target, loaded, review) {
  const preview = await reviewPreview(api, review.reviewHead, review.reviewBranch, loaded.main);
  if (preview.origin !== review.preview.origin) fail(409, 'generated_review_changed');
  await unchangedMain(api, loaded.main);
  if (await ref(api, target.branch) !== loaded.head || await ref(api, review.reviewBranch) !== review.reviewHead) {
    fail(409, 'generated_review_changed');
  }
}
async function approveGenerated(api, target, input) {
  const keys = ['file', 'action', 'expectedHead', 'baseSha', 'expectedBlob', 'reviewHead', 'manifestBlobSha', 'manifestSha256', 'contentApproved'];
  if (Object.keys(input).some(k => !keys.includes(k)) || input.contentApproved !== true) fail(400, 'author_confirmation_required');
  for (const name of ['expectedHead','expectedBlob','reviewHead','manifestBlobSha']) validSha(input[name]);
  validSha(input.baseSha, true);
  if (!/^[a-f0-9]{64}$/.test(input.manifestSha256 || '')) fail(400, 'invalid_generated_review');
  const loaded = await state(api, target);
  if (loaded.head !== input.expectedHead || loaded.baseSha !== input.baseSha || loaded.blobSha !== input.expectedBlob) fail(409, 'draft_conflict');
  const review = await generatedReview(api, target, loaded, input.reviewHead);
  if (review.manifestBlobSha !== input.manifestBlobSha || review.manifestSha256 !== input.manifestSha256) fail(409, 'generated_review_changed');
  const parent = await api('GET', 'git/commits/' + loaded.head);
  if (parent.sha !== loaded.head || !SHA.test(parent.tree?.sha || '')) fail(502, 'invalid_generated_review');
  const content = JSON.stringify(review.finalRequest) + '\n';
  await unchangedGeneratedReview(api, target, loaded, review);
  const tree = await api('POST', 'git/trees', { base_tree: parent.tree.sha,
    tree: [{ path: target.request, mode: '100644', type: 'blob', content }] });
  const commit = await api('POST', 'git/commits', { message: '[request] approve generated ' + target.file,
    tree: validSha(tree.sha), parents: [loaded.head] });
  const next = validSha(commit.sha);
  await unchangedGeneratedReview(api, target, loaded, review);
  const result = await api('PATCH', 'git/refs/heads/' + encodeURIComponent(target.branch), { sha: next, force: false });
  if (result.object?.sha !== next) fail(502, 'request_not_verified');
  let accepted;
  try {
    const stored = await fileAt(api, target.request, next);
    const after = await state(api, target);
    accepted = await publicationState(api, target, after);
    if (stored.content !== content || after.head !== next || after.main !== loaded.main ||
        accepted?.status !== 'generated_content_approved') fail(502, 'request_not_verified');
  } catch (_) { fail(502, 'request_not_verified'); }
  await unchangedMain(api, loaded.main);
  return { file: target.file, head: next, baseSha: loaded.baseSha, blobSha: loaded.blobSha, request: accepted, verified: true, published: false };
}
// Identify revisions captured by the main delivery contract. This is a write
// lock, not evidence of CI success or publication. Retirement removes the lock.
async function deliveryLock(api, target, main) {
  const receipt = await fileAt(api, '.cms-delivery.json', main, true);
  if (!receipt) return false;
  const commit = await api('GET', 'git/commits/' + main);
  if (commit.sha !== main || !SHA.test(commit.tree?.sha || '')) fail(502, 'invalid_delivery_receipt');
  const tree = await api('GET', 'git/trees/' + commit.tree.sha + '?recursive=1');
  if (tree.sha !== commit.tree.sha || tree.truncated !== false || !Array.isArray(tree.tree) ||
      tree.tree.length > 10000) fail(502, 'invalid_delivery_receipt');
  const entries = tree.tree.filter(entry => entry.path === '.cms-delivery.json');
  if (entries.length !== 1 || entries[0].mode !== '100644' || entries[0].type !== 'blob' ||
      entries[0].sha !== receipt.sha) fail(502, 'invalid_delivery_receipt');
  let value;
  try { value = JSON.parse(receipt.content); } catch (_) { fail(502, 'invalid_delivery_receipt'); }
  if (!value || Array.isArray(value) || value.version !== 1 ||
      Object.keys(value).some(key => !['version', 'requests'].includes(key)) ||
      !Array.isArray(value.requests) || value.requests.length > 20 ||
      JSON.stringify(value, null, 2) + '\n' !== receipt.content) fail(502, 'invalid_delivery_receipt');
  const files = new Set();
  for (const record of value.requests) {
    if (!record || Array.isArray(record) || typeof record.file !== 'string') fail(502, 'invalid_delivery_receipt');
    try { article(record.file); } catch (_) { fail(502, 'invalid_delivery_receipt'); }
    if (files.has(record.file)) fail(502, 'invalid_delivery_receipt');
    files.add(record.file);
  }
  return files.has(target.file);
}
async function unchangedMain(api, main) {
  if (await ref(api, 'main') !== main) fail(409, 'draft_conflict');
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
  try {
    record = JSON.parse(stored.content);
    if (JSON.stringify(record) + '\n' !== stored.content) throw Error('noncanonical_request');
    if (record.version === 2) {
      if (!patientReview.exactKeys(record, patientReview.REQUEST_FIELDS) || record.file !== target.file ||
          record.approvedBy !== 'expertise88864' || record.contentApproved !== true ||
          !SHA.test(record.sourceRequestHead || '') || !SHA.test(record.reviewHead || '') || !SHA.test(record.manifestBlobSha || '') ||
          !/^[a-f0-9]{64}$/.test(record.manifestSha256 || '') || !/^[a-f0-9]{64}$/.test(record.archiveSha256 || '') ||
          !/^\d{4}-\d\d-\d\d$/.test(record.contentDate || '') ||
          new Date(record.contentDate).toISOString().slice(0, 10) !== record.contentDate ||
          patientReview.time(record.approvedAt) > Date.now()) throw Error('invalid_final_request');
      const original = requestRecord(record.sourceRequest, target);
      if (original.action === 'unpublish' || patientReview.time(record.approvedAt) < patientReview.time(original.requestedAt)) throw Error('invalid_final_request');
      const parent = await api('GET', 'git/commits/' + loaded.head);
      const originalBytes = await fileAt(api, target.request, record.sourceRequestHead);
      if (loaded.legacy || loaded.conflict || original.blobSha !== loaded.blobSha || original.baseSha !== loaded.baseSha ||
          original.manifestSha !== loaded.manifestSha || parent.sha !== loaded.head ||
          parent.parents?.length !== 1 || parent.parents[0].sha !== record.sourceRequestHead ||
          JSON.stringify(original) + '\n' !== originalBytes.content) throw Error('invalid_final_request');
      return { action: 'approve-generated', status: 'generated_content_approved', requestedAt: original.requestedAt,
        scheduledAt: original.scheduledAt, blobSha: original.blobSha, reviewHead: record.reviewHead,
        manifestBlobSha: record.manifestBlobSha, manifestSha256: record.manifestSha256, approvedAt: record.approvedAt };
    }
    record = requestRecord(record, target);
  }
  catch (error) {
    // Unavailable evidence cannot revoke a saved approval or permit replacement.
    if (error instanceof DraftError && error.status >= 500) throw error;
    return { status: 'invalidated' };
  }
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
  if (await deliveryLock(api, target, loaded.main)) fail(409, 'publication_request_locked');
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
  await unchangedMain(api, loaded.main);
  const tree = await api('POST', 'git/trees', { base_tree: parent.tree.sha,
    tree: [{ path: target.request, mode: '100644', type: 'blob', ...(content === null ? { sha: null } : { content }) }] });
  const commit = await api('POST', 'git/commits', { message: '[request] ' + input.action + ' ' + target.file,
    tree: validSha(tree.sha), parents: [loaded.head] });
  const next = validSha(commit.sha);
  await unchangedMain(api, loaded.main);
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
  // Main and the draft ref are separate transactions. Recheck after the write
  // before acknowledging it; a concurrent promotion leaves an unverified draft.
  await unchangedMain(api, loaded.main);
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
    if (!item || typeof item.ref !== 'string') fail(502, 'draft_list_unavailable');
    const match = /^refs\/heads\/drafts\/([a-z0-9]+(?:-[a-z0-9]+)*)$/.exec(item.ref);
    return match && match[1].length <= 100 && !RESERVED.has(match[1]);
  });
  // Validate the whole supported inventory before pagination or content reads.
  for (const item of valid) repositoryRefSha(item, item.ref.slice('refs/heads/'.length));
  if (offset > valid.length) fail(400, 'invalid_list_offset');
  const selected = valid.slice(offset, offset + 20), drafts = [];
  for (let i = 0; i < selected.length; i += 4) {
    const batch = await Promise.all(selected.slice(i, i + 4).map(async item => {
      const slug = item.ref.slice('refs/heads/drafts/'.length), target = article('blog/' + slug + '.html'), head = item.object.sha;
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
  if (await deliveryLock(api, target, loaded.main)) fail(409, 'publication_request_locked');
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
  await unchangedMain(api, loaded.main);
  const articleBlob = await api('POST', 'git/blobs', { content: encode(input.content), encoding: 'base64' });
  const blobSha = validSha(articleBlob.sha);
  const tree = [{ path: target.file, mode: '100644', type: 'blob', sha: blobSha }];
  // An existing draft can predate these verified immutable main assets.
  // Include their blobs explicitly instead of assuming the draft base has them.
  for (const asset of adopted) tree.push({ path: asset.path, mode: '100644', type: 'blob', sha: asset.sha });
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
  await unchangedMain(api, loaded.main);
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
  // Preserve the accepted draft bytes for recovery, but never report a verified
  // save against an obsolete main revision or newly active delivery receipt.
  await unchangedMain(api, loaded.main);
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
      if (query.get('mode') === 'generated') {
        const result = await generatedReview(api, target, loaded);
        const { finalRequest, reviewBranch, ...visible } = result;
        return json(200, visible);
      }
      if (query.get('mode') === 'publication') return json(200, {
        file: target.file, head: loaded.head, baseSha: loaded.baseSha, blobSha: loaded.blobSha,
        publication: await observePublication(api, loaded, publicationPolicy),
      });
      if (new URL(req.url).searchParams.get('mode') === 'status') return json(200, {
        file: target.file, head: loaded.head, baseSha: loaded.baseSha, blobSha: loaded.blobSha,
        conflict: loaded.conflict, legacy: loaded.legacy, request: publication,
        requestLocked: await deliveryLock(api, target, loaded.main),
      });
      return json(200, { file: target.file, branch: target.branch, ...loaded, request: publication,
        requestLocked: await deliveryLock(api, target, loaded.main),
        media: await draftMedia(api, loaded),
        status: loaded.head ? 'cloud_draft' : loaded.content !== null ? 'published_base' : 'not_created',
        sourceOnMain: loaded.mainBlobSha !== null, published: false, deploymentVerified: false });
    }
    const input = await bodyOf(req);
    const target = article(input && input.file);
    return json(200, input.action === undefined ? await save(api, target, input) : input.action === 'new-version'
      ? await newVersion(api, target, input) : input.action === 'approve-generated'
        ? await approveGenerated(api, target, input) : await requestPublication(api, target, input));
  } catch (error) {
    return json(error instanceof DraftError ? error.status : 503,
      { ok: false, error: error instanceof DraftError ? error.code : 'draft_unavailable' });
  }
}
