// Cookie-authenticated exam drafts for the admin editor: chapter study notes
// (data/exam/notes/fitz-<N>.frag) and one question's explanation at a time
// (data/exam/explanations.json). Writes go only to the branch cms-exam/drafts;
// this endpoint cannot update main, choose another repository/ref, or publish.
// The maintainer integrates a draft with _pull_exam_drafts.py on a codex/*
// branch, then regenerates (_gen_exam.py), runs CI and the PR review.
import { getSession } from './_session.js';
import { githubRequest, GitHubRequestError } from './_github-fetch.js';
import { ExamContentError, QUESTION_ID, validateNote, replaceExplanation, readExplanation, composeExplanations } from './_exam-content.js';

export const config = { runtime: 'edge' };

const REPO = 'expertise88864/user';
const OWNER = 'expertise88864';
const BRANCH = 'cms-exam/drafts';
const MANIFEST = '.cms-exam/drafts.json';
const NOTES_DIR = 'data/exam/notes';
const EXPLANATIONS = 'data/exam/explanations.json';
const CHAPTERS = 'data/exam/fitz_chapters.json';
const SHA = /^(?!0{40}$)[a-f0-9]{40}$/;
const CHAPTER = /^[1-9]\d{0,2}$/;
const MAX_BODY = 600_000;
const MAX_NOTE_FILE = 1_000_000;
const MAX_EXPLANATIONS_FILE = 3_000_000;
const MAX_SMALL_FILE = 200_000;
const MAX_API_RESPONSE = 6_000_000;
const encoder = new TextEncoder();

class DraftError extends Error {
  constructor(status, code, reason) { super(code); this.status = status; this.code = code; this.reason = reason; }
}
function fail(status, code, reason) { throw new DraftError(status, code, reason); }
function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff', Vary: 'Cookie',
  } });
}
function validSha(value) {
  if (typeof value !== 'string' || !SHA.test(value)) fail(400, 'invalid_revision');
  return value;
}
function encode(value) {
  const bytes = encoder.encode(value);
  let binary = '';
  for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(binary);
}
function github(pat) {
  return async (method, path, body, missing = false) => {
    try {
      return await githubRequest({ endpoint: 'exam-draft', url: 'https://api.github.com/repos/' + REPO + '/' + path, path,
        method, pat, body: body ? JSON.stringify(body) : undefined, timeoutMs: 12_000, maxBytes: MAX_API_RESPONSE, optional: missing,
        accept: path.startsWith('contents/') ? 'application/vnd.github.object+json' : 'application/vnd.github+json',
        userAgent: 'ChenDermatologist-ExamDrafts/1.0' });
    } catch (error) {
      if (error instanceof GitHubRequestError) fail(error.conflict ? 409 : 502, error.conflict ? 'conflict' : error.code);
      fail(502, 'github_fetch_failed');
    }
  };
}
async function ref(api, branch) {
  const data = await api('GET', 'git/ref/heads/' + encodeURIComponent(branch), null, true);
  if (data === null) return null;
  if (!data || data.ref !== 'refs/heads/' + branch || data.object?.type !== 'commit' ||
      typeof data.object.sha !== 'string' || !SHA.test(data.object.sha)) fail(502, 'invalid_repository_ref');
  return data.object.sha;
}
// Contents omits bytes above 1 MB; then the immutable Git blob is read and its
// bytes must hash to the advertised blob SHA.
async function file(api, path, commit, limit, optional = false) {
  const data = await api('GET', 'contents/' + path + '?ref=' + commit, null, optional);
  if (data === null) return null;
  if (!data || data.type !== 'file' || !SHA.test(data.sha || '') || !Number.isInteger(data.size) ||
      data.size < 0 || data.size > limit) fail(502, 'invalid_repository_content');
  const blob = data.encoding === 'base64' ? data : await api('GET', 'git/blobs/' + data.sha);
  if (!blob || blob.sha !== data.sha || blob.size !== data.size || blob.encoding !== 'base64' ||
      typeof blob.content !== 'string') fail(502, 'invalid_repository_content');
  const base64 = blob.content.replace(/\s/g, '');
  if (base64.length !== Math.ceil(data.size / 3) * 4 ||
      !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(base64)) fail(502, 'invalid_repository_content');
  let bytes;
  try { bytes = Uint8Array.from(atob(base64), c => c.charCodeAt(0)); } catch (_) { fail(502, 'invalid_repository_content'); }
  if (bytes.length !== data.size) fail(502, 'invalid_repository_content');
  const header = encoder.encode('blob ' + bytes.length + '\0');
  const object = new Uint8Array(header.length + bytes.length);
  object.set(header); object.set(bytes, header.length);
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-1', object)), b => b.toString(16).padStart(2, '0')).join('');
  if (digest !== data.sha) fail(502, 'invalid_repository_content');
  let text;
  try { text = new TextDecoder('utf-8', { fatal: true }).decode(bytes); } catch (_) { fail(502, 'invalid_repository_content'); }
  return { sha: data.sha, text };
}

// The draft record lists exactly which sources differ from main; only those
// are read from the branch (others come from current main) and only those are
// integrated. Anything malformed stops the endpoint instead of being guessed.
function manifestText(record) { return JSON.stringify(record, null, 1) + '\n'; }
function parseManifest(text) {
  let record;
  try { record = JSON.parse(text); } catch (_) { fail(502, 'invalid_draft_record'); }
  const keys = ['version', 'baseMain', 'updated', 'notes', 'explanations'];
  if (!record || typeof record !== 'object' || Array.isArray(record) || Object.keys(record).join() !== keys.join() ||
      record.version !== 1 || !SHA.test(record.baseMain || '') || typeof record.updated !== 'string' ||
      !Number.isFinite(Date.parse(record.updated)) || !Array.isArray(record.notes) || !Array.isArray(record.explanations) ||
      record.notes.some(n => !Number.isInteger(n) || !CHAPTER.test(String(n))) ||
      record.explanations.some(id => typeof id !== 'string' || !QUESTION_ID.test(id)) ||
      manifestText(record) !== text) fail(502, 'invalid_draft_record');
  return record;
}
function view(record) {
  return record ? { exists: true, notes: record.notes, explanations: record.explanations, updated: record.updated }
    : { exists: false, notes: [], explanations: [], updated: null };
}
async function state(api) {
  const main = await ref(api, 'main');
  if (!main) fail(502, 'invalid_repository_ref');
  const head = await ref(api, BRANCH);
  let record = null;
  if (head) {
    const stored = await file(api, MANIFEST, head, MAX_SMALL_FILE, true);
    if (!stored) fail(502, 'invalid_draft_record');
    record = parseManifest(stored.text);
  }
  return { main, head, record };
}
function chapter(value) {
  const raw = typeof value === 'number' ? String(value) : value;
  if (typeof raw !== 'string' || !CHAPTER.test(raw)) fail(400, 'invalid_chapter');
  return Number(raw);
}
function notePath(ch) { return NOTES_DIR + '/fitz-' + ch + '.frag'; }
async function readNote(api, loaded, ch) {
  const fromDraft = !!loaded.record && loaded.record.notes.includes(ch);
  const stored = await file(api, notePath(ch), fromDraft ? loaded.head : loaded.main, MAX_NOTE_FILE, true);
  if (!stored) fail(404, 'unknown_note');
  return { ...stored, source: fromDraft ? 'draft' : 'main' };
}
// A drafted id is read from the draft copy (its blob is the revision token);
// any other id is read from current main.
async function readExplanations(api, loaded, id) {
  const fromDraft = !!loaded.record && loaded.record.explanations.includes(id);
  const stored = await file(api, EXPLANATIONS, fromDraft ? loaded.head : loaded.main, MAX_EXPLANATIONS_FILE);
  return { ...stored, source: fromDraft ? 'draft' : 'main' };
}

async function list(api) {
  const loaded = await state(api);
  // The object+json media type returns a directory as {type:'dir', entries}.
  const listing = await api('GET', 'contents/' + NOTES_DIR + '?ref=' + loaded.main);
  const rows = Array.isArray(listing) ? listing : listing && listing.type === 'dir' && Array.isArray(listing.entries) ? listing.entries : null;
  if (!rows) fail(502, 'invalid_repository_content');
  const chapters = rows.map(row => row && row.type === 'file' && /^fitz-([1-9]\d{0,2})\.frag$/.exec(row.name || ''))
    .filter(Boolean).map(match => Number(match[1])).sort((a, b) => a - b);
  let titles = new Map();
  try {
    const stored = await file(api, CHAPTERS, loaded.main, MAX_SMALL_FILE, true);
    if (stored) titles = new Map(JSON.parse(stored.text).map(row => [row.chapter, String(row.title || '').slice(0, 200)]));
  } catch (_) { titles = new Map(); } // titles are decoration only
  return { ok: true, notes: chapters.map(ch => titles.has(ch) ? { ch, title: titles.get(ch) } : { ch }), draft: view(loaded.record) };
}

async function bodyOf(req) {
  if (!(req.headers.get('content-type') || '').startsWith('application/json')) fail(415, 'json_required');
  if (Number(req.headers.get('content-length') || 0) > MAX_BODY) fail(413, 'too_large');
  const reader = req.body && req.body.getReader();
  if (!reader) fail(400, 'invalid_request');
  const chunks = []; let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > MAX_BODY) { await reader.cancel(); fail(413, 'too_large'); }
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

async function save(api, input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) fail(400, 'invalid_request');
  const fields = input.kind === 'note' ? ['kind', 'ch', 'content', 'baseBlobSha'] : input.kind === 'expl' ? ['kind', 'id', 'entry', 'baseBlobSha'] : null;
  if (!fields || Object.keys(input).some(k => !fields.includes(k)) || fields.some(k => !(k in input))) fail(400, 'invalid_request');
  validSha(input.baseBlobSha);
  const loaded = await state(api);
  let path, text, record;
  const previous = loaded.record || { version: 1, baseMain: loaded.main, updated: '', notes: [], explanations: [] };
  if (input.kind === 'note') {
    const ch = chapter(input.ch);
    const current = await readNote(api, loaded, ch);
    if (current.sha !== input.baseBlobSha) fail(409, 'conflict');
    text = validateNote(input.content);
    path = notePath(ch);
    record = { ...previous, notes: [...new Set([...previous.notes, ch])].sort((a, b) => a - b) };
  } else {
    if (typeof input.id !== 'string' || !QUESTION_ID.test(input.id)) fail(400, 'invalid_id');
    const current = await readExplanations(api, loaded, input.id);
    if (current.sha !== input.baseBlobSha) fail(409, 'conflict');
    // Rebuild from current main plus the drafted entries, then change this one.
    const drafted = loaded.record ? loaded.record.explanations : [];
    const draftCopy = !drafted.length ? null : current.source === 'draft' ? current
      : await file(api, EXPLANATIONS, loaded.head, MAX_EXPLANATIONS_FILE);
    const mainCopy = current.source === 'main' ? current : await file(api, EXPLANATIONS, loaded.main, MAX_EXPLANATIONS_FILE);
    text = replaceExplanation(composeExplanations(mainCopy.text, draftCopy && draftCopy.text, drafted), input.id, input.entry).text;
    path = EXPLANATIONS;
    record = { ...previous, explanations: [...new Set([...previous.explanations, input.id])].sort() };
  }
  // The rebuilt file must stay readable by this endpoint; refuse before any
  // Git object or ref is written.
  if (encoder.encode(text).length > (input.kind === 'note' ? MAX_NOTE_FILE : MAX_EXPLANATIONS_FILE)) fail(413, 'too_large');
  record = { version: 1, baseMain: previous.baseMain, updated: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    notes: record.notes, explanations: record.explanations };
  const parentSha = loaded.head || loaded.main;
  const parent = await api('GET', 'git/commits/' + parentSha);
  if (!parent || !SHA.test(parent.tree?.sha || '')) fail(502, 'invalid_repository_content');
  const blob = await api('POST', 'git/blobs', { content: encode(text), encoding: 'base64' });
  const blobSha = validSha(blob && blob.sha);
  const nextTree = await api('POST', 'git/trees', { base_tree: parent.tree.sha, tree: [
    { path, mode: '100644', type: 'blob', sha: blobSha },
    { path: MANIFEST, mode: '100644', type: 'blob', content: manifestText(record) },
  ] });
  const label = input.kind === 'note' ? 'note fitz-' + chapter(input.ch) : 'explanation ' + input.id;
  const commit = await api('POST', 'git/commits', { message: 'CMS exam draft: ' + label,
    tree: validSha(nextTree && nextTree.sha), parents: [parentSha] });
  const next = validSha(commit && commit.sha);
  // Non-force update is the compare-and-swap; a concurrent save makes it
  // non-fast-forward (409). A new branch is created only from a full commit.
  const result = loaded.head
    ? await api('PATCH', 'git/refs/heads/' + encodeURIComponent(BRANCH), { sha: next, force: false })
    : await api('POST', 'git/refs', { ref: 'refs/heads/' + BRANCH, sha: next });
  if (!result || !result.object || result.object.sha !== next) fail(502, 'save_not_verified');
  try {
    const accepted = await file(api, path, next, input.kind === 'note' ? MAX_NOTE_FILE : MAX_EXPLANATIONS_FILE);
    const acceptedRecord = await file(api, MANIFEST, next, MAX_SMALL_FILE);
    if (accepted.sha !== blobSha || accepted.text !== text || acceptedRecord.text !== manifestText(record)) fail(502, 'save_not_verified');
  } catch (_) { fail(502, 'save_not_verified'); }
  return { ok: true, head: next, blobSha, branch: BRANCH, draft: view(record), published: false };
}

export default async function handler(req) {
  if (!['GET', 'POST'].includes(req.method)) return new Response(null, { status: 405, headers: { Allow: 'GET, POST', 'Cache-Control': 'no-store' } });
  try {
    if (req.method === 'POST' && (req.headers.get('origin') !== new URL(req.url).origin ||
        req.headers.get('sec-fetch-site') !== 'same-origin')) fail(403, 'same_origin_required');
    const session = await getSession(req);
    if (!session || !session.pat || session.login !== OWNER) fail(401, 'login_required');
    const api = github(session.pat);
    if (req.method === 'GET') {
      const query = new URL(req.url).searchParams;
      if (query.get('mode') === 'list') return json(200, await list(api));
      const loaded = await state(api);
      if (query.get('kind') === 'note') {
        const ch = chapter(query.get('ch'));
        const note = await readNote(api, loaded, ch);
        return json(200, { ok: true, ch, content: note.text.replace(/\r\n?/g, '\n'), source: note.source, blobSha: note.sha });
      }
      if (query.get('kind') === 'expl') {
        const id = query.get('id');
        if (typeof id !== 'string' || !QUESTION_ID.test(id)) fail(400, 'invalid_id');
        const stored = await readExplanations(api, loaded, id);
        return json(200, { ok: true, id, entry: readExplanation(stored.text, id), source: stored.source, blobSha: stored.sha });
      }
      fail(400, 'invalid_request');
    }
    return json(200, await save(api, await bodyOf(req)));
  } catch (error) {
    if (error instanceof ExamContentError) {
      const status = error.code === 'unknown_question' ? 404 : error.code === 'format_mismatch' ? 409 : error.code === 'too_large' ? 413 : 400;
      return json(status, { ok: false, error: error.code, reason: error.reason });
    }
    return json(error instanceof DraftError ? error.status : 503,
      { ok: false, error: error instanceof DraftError ? error.code : 'draft_unavailable' });
  }
}
