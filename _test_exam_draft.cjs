// Isolated in-memory GitHub: never contacts KV, GitHub, or production. Runs the
// real api/admin/exam-draft.js and api/admin/_exam-content.js against the real
// data/exam files. The fake follows GitHub's documented response shapes for the
// object media type (a directory is an object with `entries`, files above 1 MB
// come back with encoding "none" and no content).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const path = require('node:path');

let parse5;
test.before(async () => { parse5 = await import('parse5'); });

const BRANCH = 'cms-exam/drafts';
const EXPL = 'data/exam/explanations.json';
const MANIFEST = '.cms-exam/drafts.json';
const lf = text => text.replace(/\r\n/g, '\n');
const strip = text => text.replace(/^import[^\n]+;\s*$/gm, '').replace(/\bexport (class|const|function|async function)/g, '$1');
const transport = fs.readFileSync('api/admin/_github-fetch.js', 'utf8').replace(/\bexport (class|const|function|async function)/g, '$1');
const contentSource = strip(fs.readFileSync('api/admin/_exam-content.js', 'utf8')) +
  '\nthis.api={ExamContentError,QUESTION_ID,MAX_NOTE_BYTES,validateNote,validateEntry,serializeExplanations,replaceExplanation,composeExplanations,readExplanation};';
const handlerSource = transport + '\n' + strip(fs.readFileSync('api/admin/exam-draft.js', 'utf8'))
  .replace('export default async function handler', 'async function handler').replace('export const config', 'const config');
const sha1 = value => crypto.createHash('sha1').update(value).digest('hex');
const blobSha = bytes => sha1(Buffer.concat([Buffer.from('blob ' + bytes.length + '\0'), bytes]));
const sha = text => blobSha(Buffer.from(text));
const plain = value => JSON.parse(JSON.stringify(value));

const NOTES = Object.fromEntries(fs.readdirSync('data/exam/notes').filter(name => /^fitz-\d+\.frag$/.test(name))
  .map(name => [Number(name.match(/\d+/)[0]), lf(fs.readFileSync(path.join('data/exam/notes', name), 'utf8'))]));
const EXPL_TEXT = lf(fs.readFileSync(EXPL, 'utf8'));
const EXPL_DATA = JSON.parse(EXPL_TEXT);
const CHAPTERS_TEXT = lf(fs.readFileSync('data/exam/fitz_chapters.json', 'utf8'));
const CHAPTERS = Object.fromEntries(JSON.parse(CHAPTERS_TEXT).map(row => [row.chapter, row.title]));
const NOTE_CH = 17, OTHER_CH = 24;
const ID_A = '101-01', ID_B = '101-02', ID_C = '101-03';
const noteFile = ch => 'data/exam/notes/fitz-' + ch + '.frag';

function content() {
  const context = { parse: parse5.parse, parseFragment: parse5.parseFragment, TextEncoder, URL };
  vm.runInNewContext(contentSource, context);
  return context.api;
}
function fixture() {
  const calls = [], blobs = new Map(), trees = new Map(), commits = new Map(), refs = new Map(), logs = [];
  const store = value => { const bytes = Buffer.isBuffer(value) ? value : Buffer.from(value); const id = blobSha(bytes); blobs.set(id, bytes); return id; };
  const files = new Map([[EXPL, store(EXPL_TEXT)], ['data/exam/fitz_chapters.json', store(CHAPTERS_TEXT)], ['README.md', store('readme')]]);
  for (const [ch, text] of Object.entries(NOTES)) files.set(noteFile(ch), store(text));
  const mainTree = sha1('main-tree'), main = sha1('main');
  trees.set(mainTree, files); commits.set(main, { tree: { sha: mainTree }, parents: [], message: 'main' }); refs.set('main', main);
  const h = { calls, blobs, trees, commits, refs, logs, store, main, session: { pat: 'fixture-secret', login: 'expertise88864' } };
  const treeOf = commitSha => trees.get(commits.get(commitSha).tree.sha);
  h.fileAt = (commitSha, file) => { const id = treeOf(commitSha).get(file); return id ? blobs.get(id).toString('utf8') : null; };
  // A commit on top of `parent` with the given files (used for "main moved" and "foreign writer").
  h.addCommit = (parent, changes, message = 'x') => {
    const tree = new Map(treeOf(parent));
    for (const [file, text] of Object.entries(changes)) tree.set(file, store(text));
    const treeId = sha1(JSON.stringify([...tree])); trees.set(treeId, tree);
    const id = sha1(JSON.stringify([treeId, parent, message, commits.size])); commits.set(id, { tree: { sha: treeId }, parents: [parent], message });
    return id;
  };
  h.moveMain = changes => { h.main = h.addCommit(refs.get('main'), changes, 'main moves'); refs.set('main', h.main); return h.main; };
  async function fetch(url, options) {
    assert.equal(new URL(url).origin, 'https://api.github.com');
    assert.equal(options.redirect, 'manual');
    assert.ok(!('cache' in options), 'Vercel Edge fetch must not receive a cache option');
    assert.equal(options.headers['Cache-Control'], 'no-cache');
    assert.equal(options.headers.Authorization, 'Bearer fixture-secret');
    const u = new URL(url), route = decodeURIComponent(u.pathname.replace('/repos/expertise88864/user/', ''));
    if (route.startsWith('contents/')) assert.equal(options.headers.Accept, 'application/vnd.github.object+json');
    const body = options.body && JSON.parse(options.body);
    calls.push({ method: options.method, path: route, body });
    if (options.method !== 'GET') {
      // Writes are limited to objects and the one draft ref, never main.
      assert.ok(['git/blobs', 'git/trees', 'git/commits', 'git/refs', 'git/refs/heads/' + BRANCH].includes(route), 'unexpected write ' + route);
      if (route === 'git/refs') assert.equal(body.ref, 'refs/heads/' + BRANCH);
      if (route.startsWith('git/refs/heads/')) assert.equal(body.force, false, 'the ref update is a non-force compare-and-swap');
    }
    if (h.failRead && options.method === 'GET' && route.startsWith(h.failRead)) return Response.json({ message: 'private upstream detail' }, { status: 503 });
    let result;
    if (route.startsWith('git/ref/heads/')) {
      const value = refs.get(route.slice('git/ref/heads/'.length));
      if (!value) return Response.json({}, { status: 404 });
      result = { ref: 'refs/heads/' + route.slice('git/ref/heads/'.length), object: { type: 'commit', sha: value } };
    } else if (route.startsWith('contents/')) {
      const commit = commits.get(u.searchParams.get('ref'));
      assert.ok(commit, 'read must use a known immutable commit');
      const tree = trees.get(commit.tree.sha), file = route.slice('contents/'.length);
      if (tree.has(file)) {
        const bytes = blobs.get(tree.get(file));
        result = { type: 'file', sha: tree.get(file), size: bytes.length, encoding: 'base64', content: bytes.toString('base64') };
        if (h.corrupt && file === h.corrupt) result.content = Buffer.from('x'.repeat(bytes.length)).toString('base64');
        if (bytes.length > 1_000_000) { result.encoding = 'none'; result.content = ''; }
      } else {
        const prefix = file + '/', entries = [...tree].filter(([name]) => name.startsWith(prefix) && !name.slice(prefix.length).includes('/'))
          .map(([name, id]) => ({ type: 'file', name: name.slice(prefix.length), path: name, sha: id, size: blobs.get(id).length }));
        if (!entries.length) return Response.json({}, { status: 404 });
        // GitHub's object media type: a directory is an object with `entries`.
        result = { type: 'dir', name: file.split('/').pop(), path: file, sha: sha1(file), size: 0, entries };
      }
    } else if (route.startsWith('git/blobs/')) {
      const id = route.slice('git/blobs/'.length), bytes = blobs.get(id);
      assert.ok(bytes);
      result = { sha: id, size: bytes.length, encoding: 'base64', content: bytes.toString('base64') };
    } else if (route.startsWith('git/commits/')) {
      const id = route.slice('git/commits/'.length), value = commits.get(id);
      result = { sha: id, tree: value.tree, parents: value.parents.map(parent => ({ sha: parent })) };
    } else if (route === 'git/blobs') result = { sha: store(Buffer.from(body.content, 'base64')) };
    else if (route === 'git/trees') {
      const tree = new Map(trees.get(body.base_tree));
      for (const entry of body.tree) {
        assert.equal(entry.mode, '100644'); assert.equal(entry.type, 'blob');
        tree.set(entry.path, entry.sha || store(entry.content));
      }
      const id = sha1(JSON.stringify([...tree])); trees.set(id, tree); result = { sha: id };
    } else if (route === 'git/commits') {
      const id = sha1(JSON.stringify(body) + calls.length); commits.set(id, { tree: { sha: body.tree }, parents: body.parents, message: body.message });
      if (h.raceOnCommit) { const hook = h.raceOnCommit; h.raceOnCommit = null; hook(); }
      result = { sha: id };
    } else if (route === 'git/refs' || route.startsWith('git/refs/heads/')) {
      if (route === 'git/refs' ? refs.has(BRANCH) : commits.get(body.sha).parents[0] !== refs.get(BRANCH)) return Response.json({}, { status: 422 });
      refs.set(BRANCH, body.sha); result = { object: { sha: body.sha } };
    } else assert.fail('unexpected GitHub API path: ' + route);
    if (h.tamper) result = h.tamper(route, result);
    return Response.json(result);
  }
  const context = { console: { error: (...args) => logs.push(args.join(' ')) }, URL, Request, Response, TextEncoder, TextDecoder, Uint8Array,
    AbortController, setTimeout, clearTimeout, atob, btoa, crypto: crypto.webcrypto, fetch,
    getSession: async () => h.session, ...content() };
  vm.runInNewContext(handlerSource + '\nthis.handler=handler;', context);
  h.send = async (method, search, body, headers = {}) => {
    const init = { method, headers: { origin: 'https://editor.test', 'sec-fetch-site': 'same-origin', 'content-type': 'application/json', ...headers } };
    if (body !== undefined) init.body = typeof body === 'string' ? body : JSON.stringify(body);
    const response = await context.handler(new Request('https://editor.test/api/admin/exam-draft' + search, init));
    const text = await response.text();
    assert.ok(!text.includes('fixture-secret') && !text.includes('private upstream detail'), 'no credential or provider detail in the response');
    return { status: response.status, headers: response.headers, body: text ? JSON.parse(text) : null };
  };
  h.get = search => h.send('GET', search);
  h.post = (body, headers) => h.send('POST', '', body, headers);
  h.writes = () => calls.filter(call => call.method !== 'GET');
  h.head = () => refs.get(BRANCH);
  h.context = context;
  return h;
}
const NOTE_TOKEN = ch => sha(NOTES[ch]);
const EXPL_TOKEN = sha(EXPL_TEXT);
function editedNote(ch = NOTE_CH) { return NOTES[ch].replace(/<\/section>\s*$/, '<p>新增段落 <strong class="ex-n">1</strong></p>\n</section>\n'); }
function editedEntry(id = ID_A, tag = '修訂') {
  const entry = plain(EXPL_DATA[id]);
  entry.summary = entry.summary + ' （' + tag + '）';
  entry.items[0].text = entry.items[0].text + ' 補充 [i]Candida albicans[/i]。';
  return entry;
}
const noteBody = (extra = {}) => ({ kind: 'note', ch: NOTE_CH, content: editedNote(), baseBlobSha: NOTE_TOKEN(NOTE_CH), ...extra });
const explBody = (id = ID_A, extra = {}) => ({ kind: 'expl', id, entry: editedEntry(id), baseBlobSha: EXPL_TOKEN, ...extra });

test('access: session, owner login, same-origin (including sec-fetch-site) and methods', async () => {
  const h = fixture();
  h.session = null;
  for (const [method, search, body] of [['GET', '?mode=list'], ['GET', '?kind=note&ch=17'], ['GET', '?kind=expl&id=101-01'], ['POST', '', noteBody()]]) {
    const result = await h.send(method, search, body);
    assert.equal(result.status, 401); assert.deepEqual(plain(result.body), { ok: false, error: 'login_required' });
    assert.equal(result.headers.get('cache-control'), 'private, no-store');
  }
  h.session = { pat: 'fixture-secret', login: 'someone-else' };
  assert.equal((await h.get('?mode=list')).status, 401);
  assert.equal((await h.post(noteBody())).status, 401);
  h.session = { pat: '', login: 'expertise88864' };
  assert.equal((await h.get('?mode=list')).status, 401);
  h.session = { pat: 'fixture-secret', login: 'expertise88864' };
  const cross = await h.post(noteBody(), { origin: 'https://evil.test' });
  assert.equal(cross.status, 403); assert.equal(cross.body.error, 'same_origin_required');
  assert.equal((await h.post(noteBody(), { 'sec-fetch-site': 'cross-site' })).status, 403);
  assert.equal((await h.post(noteBody(), { 'sec-fetch-site': 'same-site' })).status, 403);
  assert.equal((await h.post(noteBody(), { origin: '' })).status, 403);
  // The header is required on writes, not only checked when present.
  const noHeader = await h.context.handler(new Request('https://editor.test/api/admin/exam-draft', { method: 'POST',
    headers: { origin: 'https://editor.test', 'content-type': 'application/json' }, body: JSON.stringify(noteBody()) }));
  assert.equal(noHeader.status, 403);
  assert.equal((await h.send('POST', '', noteBody(), { 'content-type': 'text/plain' })).status, 415);
  assert.equal((await h.context.handler(new Request('https://editor.test/api/admin/exam-draft', { method: 'PUT' }))).status, 405);
  assert.deepEqual(h.calls, [], 'rejected requests never reach GitHub');
});

test('reads: list, note and explanation from main', async () => {
  const h = fixture();
  const list = await h.get('?mode=list');
  assert.equal(list.status, 200, JSON.stringify(list.body)); assert.equal(list.body.ok, true);
  assert.deepEqual(plain(list.body.notes.map(row => row.ch)), Object.keys(NOTES).map(Number).sort((a, b) => a - b));
  assert.equal(list.body.notes.find(row => row.ch === NOTE_CH).title, CHAPTERS[NOTE_CH]);
  assert.deepEqual(plain(list.body.draft), { exists: false, notes: [], explanations: [], updated: null });
  const note = await h.get('?kind=note&ch=' + NOTE_CH);
  assert.deepEqual(plain(note.body), { ok: true, ch: NOTE_CH, content: NOTES[NOTE_CH], source: 'main', blobSha: NOTE_TOKEN(NOTE_CH) });
  const expl = await h.get('?kind=expl&id=' + ID_A);
  assert.deepEqual(plain(expl.body), { ok: true, id: ID_A, entry: EXPL_DATA[ID_A], source: 'main', blobSha: EXPL_TOKEN });
  assert.ok(h.calls.some(call => call.path.startsWith('git/blobs/')), 'the 1.2 MB file is read through its Git blob');
  for (const bad of ['?kind=note&ch=2', '?kind=note&ch=999']) { const r = await h.get(bad); assert.equal(r.status, 404); assert.equal(r.body.error, 'unknown_note'); }
  for (const bad of ['?kind=note&ch=0', '?kind=note&ch=abc', '?kind=note&ch=17x', '?kind=note&ch=-1', '?kind=note&ch=1000', '?kind=note']) {
    const r = await h.get(bad); assert.equal(r.status, 400, bad); assert.equal(r.body.error, 'invalid_chapter');
  }
  const unknown = await h.get('?kind=expl&id=999-99');
  assert.equal(unknown.status, 404); assert.equal(unknown.body.error, 'unknown_question');
  for (const bad of ['?kind=expl&id=101-1', '?kind=expl&id=../x', '?kind=expl']) { const r = await h.get(bad); assert.equal(r.status, 400); assert.equal(r.body.error, 'invalid_id'); }
  assert.equal((await h.get('?kind=other')).status, 400);
  assert.equal((await h.get('')).body.error, 'invalid_request');
  assert.deepEqual(h.writes(), []);
});

test('note save: branch created from main, manifest format, verification, then reads come from the draft', async () => {
  const h = fixture();
  const saved = await h.post(noteBody());
  assert.equal(saved.status, 200, JSON.stringify(saved.body));
  const body = editedNote();
  assert.equal(saved.body.ok, true); assert.equal(saved.body.blobSha, sha(body)); assert.equal(saved.body.head, h.head());
  assert.equal(saved.body.branch, BRANCH); assert.equal(saved.body.published, false);
  assert.deepEqual(plain(saved.body.draft), { exists: true, notes: [NOTE_CH], explanations: [], updated: JSON.parse(h.fileAt(h.head(), MANIFEST)).updated });
  assert.equal(h.commits.get(h.head()).parents[0], h.main, 'the branch starts from the main head');
  assert.equal(h.commits.get(h.head()).message, 'CMS exam draft: note fitz-' + NOTE_CH);
  assert.equal(h.fileAt(h.head(), noteFile(NOTE_CH)), body);
  const manifestText = h.fileAt(h.head(), MANIFEST), manifest = JSON.parse(manifestText);
  assert.deepEqual(Object.keys(manifest), ['version', 'baseMain', 'updated', 'notes', 'explanations']);
  assert.equal(manifestText, JSON.stringify(manifest, null, 1) + '\n', 'canonical manifest bytes');
  assert.equal(manifest.version, 1); assert.equal(manifest.baseMain, h.main); assert.deepEqual(manifest.notes, [NOTE_CH]); assert.deepEqual(manifest.explanations, []);
  assert.match(manifest.updated, /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/);
  assert.equal(h.refs.get('main'), h.main, 'main is untouched');
  assert.equal(h.fileAt(h.main, noteFile(NOTE_CH)), NOTES[NOTE_CH]);
  assert.deepEqual(h.writes().map(call => call.path), ['git/blobs', 'git/trees', 'git/commits', 'git/refs']);
  assert.ok(!h.calls.some(call => call.path.includes('heads/main') && call.method !== 'GET'));

  const read = await h.get('?kind=note&ch=' + NOTE_CH);
  assert.deepEqual(plain(read.body), { ok: true, ch: NOTE_CH, content: body, source: 'draft', blobSha: saved.body.blobSha });
  assert.equal((await h.get('?kind=note&ch=' + OTHER_CH)).body.source, 'main', 'an unedited chapter is still read from main');
  assert.deepEqual(plain((await h.get('?mode=list')).body.draft).notes, [NOTE_CH]);

  // A second save advances the same branch; another chapter keeps the list sorted and baseMain fixed.
  const first = h.head();
  const again = await h.post({ kind: 'note', ch: NOTE_CH, content: body + '\n', baseBlobSha: saved.body.blobSha });
  assert.equal(again.status, 200); assert.equal(h.commits.get(h.head()).parents[0], first);
  const second = await h.post({ kind: 'note', ch: OTHER_CH, content: editedNote(OTHER_CH), baseBlobSha: NOTE_TOKEN(OTHER_CH) });
  assert.equal(second.status, 200); assert.deepEqual(plain(second.body.draft).notes, [NOTE_CH, OTHER_CH]);
  assert.equal(JSON.parse(h.fileAt(h.head(), MANIFEST)).baseMain, h.main);
  assert.equal(h.fileAt(h.head(), noteFile(NOTE_CH)), body + '\n', 'the earlier chapter stays on the branch');
  // Saving the same chapter again with its previous (stale) token is a conflict.
  assert.equal((await h.post({ kind: 'note', ch: NOTE_CH, content: body, baseBlobSha: saved.body.blobSha })).status, 409);
});

test('note save normalizes CRLF to LF and stores nothing else differently', async () => {
  const h = fixture();
  const saved = await h.post(noteBody({ content: editedNote().replace(/\n/g, '\r\n') }));
  assert.equal(saved.status, 200);
  assert.equal(h.fileAt(h.head(), noteFile(NOTE_CH)), editedNote());
  assert.ok(!h.fileAt(h.head(), noteFile(NOTE_CH)).includes('\r'));
  // The unchanged fragment is accepted as it is.
  const same = fixture();
  assert.equal((await same.post(noteBody({ content: NOTES[NOTE_CH] }))).status, 200);
  assert.equal(same.fileAt(same.head(), noteFile(NOTE_CH)), NOTES[NOTE_CH]);
});

const GOOD = '<section class="ex-note" id="sec-1">\n<h2>標題</h2>\n<p class="ex-cite">c</p>\n<p>text <strong class="ex-n">1</strong> <span class="ex-ref">Ch.1</span> <span class="ex-ref ex-ref-mckee">M</span> <mark data-q="101-01">fact</mark> <mark data-q="101-01,102-02">two</mark><br></p>\n' +
  '<aside class="ex-trap"><strong>陷阱</strong> x</aside>\n<table class="ex-table"><thead><tr><th scope="col">a</th><th>b</th></tr></thead><tbody><tr><td>1</td><td>2</td></tr></tbody></table>\n<ul><li>a</li></ul><ol><li><em>b</em></li></ol><h3>h</h3>\n</section>\n';
test('note sanitizer: accepts the allowed grammar, rejects everything else with a readable reason', async () => {
  const h = fixture();
  assert.equal((await h.post(noteBody({ content: GOOD }))).status, 200);
  const check = async (body, pattern, status = 400, error = 'invalid_note') => {
    const result = await h.post(noteBody({ content: body, baseBlobSha: (await h.get('?kind=note&ch=' + NOTE_CH)).body.blobSha }));
    assert.equal(result.status, status, body.slice(0, 120) + ' => ' + JSON.stringify(result.body)); assert.equal(result.body.error, error);
    assert.match(result.body.reason, pattern, body.slice(0, 120));
  };
  const wrap = inner => '<section class="ex-note" id="s">\n<h2>T</h2>\n' + inner + '\n</section>\n';
  const writes = h.writes().length;
  await check(wrap('<script>alert(1)</script>'), /<script>/);
  await check(wrap('<style>p{}</style>'), /<style>/);
  await check(wrap('<p style="color:red">x</p>'), /style/);
  await check(wrap('<p onclick="x()">x</p>'), /onclick/);
  await check(wrap('<a href="https://x.test">x</a>'), /<a>/);
  await check(wrap('<img src="x.png">'), /<img>/);
  await check(wrap('<span class="ex-ref" href="x">x</span>'), /href/);
  await check(wrap('<p class="evil">x</p>'), /evil/);
  await check(wrap('<span class="ex-ref evil">x</span>'), /evil/);
  await check(wrap('<span>x</span>'), /class/);
  await check(wrap('<li class="ex-ref">x</li>'), /class/);
  await check(wrap('<mark data-q="1-1">x</mark>'), /data-q/);
  await check(wrap('<mark>x</mark>'), /data-q/);
  await check(wrap('<span class="ex-ref" data-q="101-01">x</span>'), /data-q/);
  await check(wrap('<table class="ex-table"><thead><tr><th scope="rowgroup">a</th></tr></thead></table>'), /scope/);
  await check(wrap('<p id="x">x</p>'), /id/);
  await check(wrap('<!-- note -->'), /註解/);
  await check(wrap('<![CDATA[x]]>'), /註解/);
  await check(wrap('<p>{{hit:101-01}}</p>'), /\{\{/);
  await check(wrap('<iframe></iframe>'), /<iframe>/);
  await check(wrap('<svg></svg>'), /<svg>/);
  await check(wrap('<div>x</div>'), /<div>/);
  await check(wrap('<template>x</template>'), /<template>/);
  await check(wrap('<section class="ex-note" id="inner"><h2>x</h2></section>'), /最外層/);
  await check(wrap('<table class="ex-table"><tbody><tr><td><table class="ex-table"><tbody><tr><td>x</td></tr></tbody></table></td></tr></tbody></table>'), /巢狀/);
  await check('<p>top level</p>\n', /最外層/);
  await check('stray text\n' + GOOD, /最外層/);
  await check(GOOD + '<!-- trailing -->', /註解/);
  await check('<section class="ex-note" id="Bad_Id">\n<h2>T</h2>\n</section>', /id/);
  await check('<section id="sec-1" class="ex-note">\n<h2>T</h2>\n</section>', /section/);
  await check("<section class='ex-note' id=\"sec-1\">\n<h2>T</h2>\n</section>", /開始標籤/);
  await check('<section class="ex-note" id="sec-1" data-x="1">\n<h2>T</h2>\n</section>', /data-x/);
  await check('<section class="ex-note">\n<h2>T</h2>\n</section>', /section/);
  await check('<section class="ex-note" id="a">\n<p>no heading</p>\n</section>', /<h2>/);
  await check(GOOD + GOOD, /重複/);
  await check('', /空/);
  await check('  \n', /空/);
  await check(wrap('<p>a</div> b</p>'), /結束標籤/);
  await check(wrap('<p>one<p>two</p>'), /結束標籤/);
  await check(wrap('<ul><li>one<li>two</ul>'), /結束標籤/);
  await check(wrap('<table class="ex-table"><tr><td>x</td></tr></table>'), /缺少開始標籤|tbody|結束標籤|錯亂|位置|移到/);
  // Markup the browser would move (foster parenting) is rejected, not stored as written.
  await check(wrap('<table class="ex-table"><p class="ex-cite">moved</p><tbody><tr><td>x</td></tr></tbody></table>'), /位置|移到/);
  await check(wrap('<table class="ex-table">loose text<tbody><tr><td>x</td></tr></tbody></table>'), /位置|移到/);
  await check(wrap('<table class="ex-table"><tbody><tr>loose<td>x</td></tr></tbody></table>'), /位置|移到/);
  await check(wrap('<p>a</b> b</p>'), /結束標籤/);
  await check(wrap('<p>a</br></p>'), /缺少開始標籤|結束標籤|<br>|錯亂|位置|移到/);
  await check(wrap('<p>a\u0001b</p>'), /控制字元/);
  await check('<section class="ex-note" id="a">\n<h2>T</h2>\n<p>' + 'x'.repeat(410_000) + '</p>\n</section>', /400 KB/, 413, 'too_large');
  assert.equal((await h.post(noteBody({ content: 5, baseBlobSha: (await h.get('?kind=note&ch=' + NOTE_CH)).body.blobSha }))).body.error, 'invalid_note');
  assert.equal(h.writes().length, writes, 'nothing was written by any rejected note');
  // Request shape errors are plain invalid_request, bad values have their own codes.
  for (const body of [{ kind: 'note', ch: NOTE_CH, content: GOOD }, { ...noteBody(), extra: 1 }, { kind: 'discard' }, { kind: 'other' }, [], 'x', 5, null]) {
    const bad = await h.post(body); assert.equal(bad.status, 400, JSON.stringify(body)); assert.equal(bad.body.error, 'invalid_request');
  }
  assert.equal((await h.post(noteBody({ ch: 2.5 }))).body.error, 'invalid_chapter');
  assert.equal((await h.post(noteBody({ ch: 2 }))).body.error, 'unknown_note');
  assert.equal((await h.post(noteBody({ baseBlobSha: 'abc' }))).body.error, 'invalid_revision');
});

test('note sanitizer: accepts every committed fragment unchanged and rejects each with a forbidden element added', () => {
  const api = content();
  assert.equal(Object.keys(NOTES).length, 50);
  for (const [ch, text] of Object.entries(NOTES)) {
    assert.equal(api.validateNote(text), text, 'fitz-' + ch);
    assert.equal(api.validateNote(text.replace(/\n/g, '\r\n')), text, 'CRLF input is normalized, fitz-' + ch);
    for (const broken of [text.replace(/<\/section>\s*$/, '<script>1</script></section>'), text.replace('<h2>', '<h2 onclick="1">'), text.replace(/<\/section>\s*$/, '</section></section>')]) {
      assert.throws(() => api.validateNote(broken), error => error.code === 'invalid_note', 'fitz-' + ch);
    }
  }
});

test('explanation save changes only that entry and keeps the file format byte for byte', async () => {
  const h = fixture();
  const saved = await h.post(explBody());
  assert.equal(saved.status, 200, JSON.stringify(saved.body));
  const updated = h.fileAt(h.head(), EXPL);
  assert.equal(saved.body.blobSha, sha(updated));
  const expected = JSON.parse(EXPL_TEXT); expected[ID_A] = editedEntry();
  assert.equal(updated, JSON.stringify(expected, null, 1));
  const marker = line => /^ "\d{3}-\d{2}": /.test(line);
  const before = EXPL_TEXT.split('\n'), after = updated.split('\n');
  const start = before.findIndex(line => line.startsWith(' "' + ID_A + '": ')), end = start + 1 + before.slice(start + 1).findIndex(marker);
  const tail = before.length - end;
  assert.deepEqual(after.slice(0, start), before.slice(0, start));
  assert.deepEqual(after.slice(after.length - tail), before.slice(end));
  assert.notDeepEqual(after.slice(start, after.length - tail), before.slice(start, end));
  assert.deepEqual(Object.keys(JSON.parse(updated)), Object.keys(EXPL_DATA), 'key order is kept');
  assert.ok(!updated.endsWith('\n'));
  assert.equal(h.commits.get(h.head()).message, 'CMS exam draft: explanation ' + ID_A);
  const manifest = JSON.parse(h.fileAt(h.head(), MANIFEST));
  assert.deepEqual(manifest.explanations, [ID_A]); assert.deepEqual(manifest.notes, []); assert.equal(saved.body.published, false);
  const read = await h.get('?kind=expl&id=' + ID_A);
  assert.deepEqual(plain(read.body), { ok: true, id: ID_A, entry: editedEntry(), source: 'draft', blobSha: saved.body.blobSha });
});

test('explanation drafts accumulate: a second id keeps the first, and newer main text is never reverted', async () => {
  const h = fixture();
  const first = await h.post(explBody(ID_A));
  assert.equal(first.status, 200);
  // main changes a third question after the branch was created
  const mainEdited = JSON.parse(EXPL_TEXT); mainEdited[ID_C] = { ...mainEdited[ID_C], summary: mainEdited[ID_C].summary + ' main-edit' };
  h.moveMain({ [EXPL]: JSON.stringify(mainEdited, null, 1) });
  // an id that is not drafted is read from current main, with main's file as its token
  const other = await h.get('?kind=expl&id=' + ID_B);
  assert.equal(other.body.source, 'main'); assert.equal(other.body.blobSha, sha(h.fileAt(h.main, EXPL)));
  const second = await h.post({ kind: 'expl', id: ID_B, entry: editedEntry(ID_B, '第二題'), baseBlobSha: other.body.blobSha });
  assert.equal(second.status, 200, JSON.stringify(second.body));
  const merged = JSON.parse(h.fileAt(h.head(), EXPL));
  assert.deepEqual(merged[ID_A], editedEntry(ID_A), 'the first draft entry is kept');
  assert.deepEqual(merged[ID_B], editedEntry(ID_B, '第二題'));
  assert.equal(merged[ID_C].summary, mainEdited[ID_C].summary, 'an entry changed on main after the branch was created is not reverted');
  assert.deepEqual(Object.keys(merged), Object.keys(EXPL_DATA));
  assert.deepEqual(plain(second.body.draft).explanations, [ID_A, ID_B]);
  assert.equal(JSON.parse(h.fileAt(h.head(), MANIFEST)).baseMain, JSON.parse(h.fileAt(h.commits.get(h.head()).parents[0], MANIFEST)).baseMain, 'baseMain stays the original main');
  // The first id's token is now stale; the current draft file's token works.
  assert.equal((await h.post({ kind: 'expl', id: ID_A, entry: editedEntry(ID_A, '三'), baseBlobSha: first.body.blobSha })).status, 409);
  const reread = await h.get('?kind=expl&id=' + ID_A);
  assert.equal(reread.body.source, 'draft'); assert.equal(reread.body.blobSha, second.body.blobSha);
  const third = await h.post({ kind: 'expl', id: ID_A, entry: editedEntry(ID_A, '三'), baseBlobSha: reread.body.blobSha });
  assert.equal(third.status, 200);
  const final = JSON.parse(h.fileAt(h.head(), EXPL));
  assert.equal(final[ID_A].summary.endsWith('（三）'), true); assert.deepEqual(final[ID_B], editedEntry(ID_B, '第二題'));
  assert.equal(final[ID_C].summary, mainEdited[ID_C].summary);
});

test('every committed explanation re-saved unchanged reproduces the file exactly', async () => {
  const api = content();
  const ids = Object.keys(EXPL_DATA);
  assert.ok(ids.length >= 747, 'all real entries are covered: ' + ids.length);
  assert.equal(JSON.stringify(EXPL_DATA, null, 1), EXPL_TEXT, 'JS serialization equals the committed bytes');
  assert.ok(!EXPL_TEXT.endsWith('\n'), 'no trailing newline, like json.dumps');
  for (const id of ids) {
    const result = api.replaceExplanation(EXPL_TEXT, id, plain(EXPL_DATA[id]));
    assert.equal(result.text === EXPL_TEXT, true, id + ' unchanged entry must reproduce the file');
  }
  // The same through the endpoint for entries with flags, a dispute with sources and a pmid.
  const flagged = ids.find(id => EXPL_DATA[id].flags), sourced = ids.find(id => EXPL_DATA[id].dispute && EXPL_DATA[id].dispute.sources);
  for (const id of [ID_A, flagged, sourced]) {
    const h = fixture();
    const saved = await h.post({ kind: 'expl', id, entry: plain(EXPL_DATA[id]), baseBlobSha: EXPL_TOKEN });
    assert.equal(saved.status, 200, id);
    assert.equal(h.fileAt(h.head(), EXPL), EXPL_TEXT, id);
    assert.equal(saved.body.blobSha, EXPL_TOKEN);
  }
  // Key order in the request does not change the bytes.
  const entry = plain(EXPL_DATA[sourced]);
  const shuffled = { dispute: { sources: entry.dispute.sources.map(s => ({ url: s.url, year: s.year, title: s.title, ...(s.pmid ? { pmid: s.pmid } : {}) })), current: entry.dispute.current, exam: entry.dispute.exam, kind: entry.dispute.kind },
    items: entry.items.map(it => ({ refs: it.refs, text: it.text, ok: it.ok, label: it.label, key: it.key })), summary: entry.summary };
  assert.equal(api.replaceExplanation(EXPL_TEXT, sourced, shuffled).text, EXPL_TEXT);
  // Python's json.dumps output is the same bytes (checked by _test_pull_exam_drafts.py).
});

test('explanation schema: unknown keys, bad values and unknown ids are rejected before anything is written', async () => {
  const h = fixture();
  const attempt = async (mutate, pattern, id = ID_A) => {
    const entry = editedEntry(id); mutate(entry);
    const result = await h.post({ kind: 'expl', id, entry, baseBlobSha: EXPL_TOKEN });
    assert.equal(result.status, 400, JSON.stringify(result.body)); assert.equal(result.body.error, 'invalid_entry');
    assert.match(result.body.reason, pattern);
    assert.deepEqual(h.writes(), []);
  };
  await attempt(e => { e.extra = 1; }, /extra/);
  await attempt(e => { delete e.summary; }, /summary/);
  await attempt(e => { e.summary = '   '; }, /summary/);
  await attempt(e => { e.summary = 5; }, /summary/);
  await attempt(e => { e.summary = 'a\u0000b'; }, /summary/);
  await attempt(e => { e.summary = 'a\nb'; }, /換行/);
  await attempt(e => { e.summary = 'a\tb'; }, /summary/);
  await attempt(e => { e.summary = 'a'.repeat(2001); }, /2000/);
  await attempt(e => { e.items.pop(); }, /items/);
  await attempt(e => { e.items.push({ ...e.items[0] }); }, /items/);
  await attempt(e => { e.items = 'x'; }, /items/);
  await attempt(e => { e.items[0].extra = 1; }, /items\[0\]/);
  await attempt(e => { delete e.items[0].ok; }, /ok/);
  await attempt(e => { e.items[0].ok = 'yes'; }, /ok/);
  await attempt(e => { e.items[0].key = 'Z'; }, /key/);
  await attempt(e => { [e.items[0].key, e.items[1].key] = [e.items[1].key, e.items[0].key]; }, /key/);
  await attempt(e => { e.items[0].label = 'x\ny'; }, /label/);
  await attempt(e => { e.items[0].text = ''; }, /text/);
  await attempt(e => { e.items[0].text = 'a'.repeat(4001); }, /4000/);
  await attempt(e => { e.items[0].refs = [[1]]; }, /refs/);
  await attempt(e => { e.items[0].refs = [['X', '1']]; }, /refs\[0\]/);
  await attempt(e => { e.items[0].refs = [[0, '1']]; }, /refs\[0\]/);
  await attempt(e => { e.items[0].refs = [[301, '1']]; }, /refs\[0\]/);
  await attempt(e => { e.items[0].refs = [[1.5, '1']]; }, /refs\[0\]/);
  await attempt(e => { e.items[0].refs = [[1, 'p.266']]; }, /頁碼/);
  await attempt(e => { e.items[0].refs = [[1, '']]; }, /頁碼/);
  await attempt(e => { e.items[0].refs = Array.from({ length: 21 }, () => [1, '2']); }, /refs/);
  await attempt(e => { e.flags = Array.from({ length: 11 }, () => 'x'); }, /flags/);
  await attempt(e => { e.flags = [3]; }, /flags\[0\]/);
  await attempt(e => { e.dispute = { kind: 'weird', exam: 'x' }; }, /kind/);
  await attempt(e => { e.dispute = { kind: 'old' }; }, /exam/);
  await attempt(e => { e.dispute = { kind: 'old', exam: 'x', extra: 1 }; }, /extra/);
  const src = over => ({ kind: 'old', exam: 'x', current: 'y', sources: [{ title: 't', url: 'https://example.org/a', year: 2020, ...over }] });
  await attempt(e => { e.dispute = src({ url: 'http://example.org/a' }); }, /url/);
  await attempt(e => { e.dispute = src({ url: 'javascript:alert(1)' }); }, /url/);
  await attempt(e => { e.dispute = src({ url: 'https://u:p@example.org/a' }); }, /url/);
  await attempt(e => { e.dispute = src({ url: 'https://Example.org/a' }); }, /url/);
  await attempt(e => { e.dispute = src({ url: 'not a url' }); }, /url/);
  await attempt(e => { e.dispute = src({ year: '2020' }); }, /year/);
  await attempt(e => { e.dispute = src({ pmid: 'abc' }); }, /pmid/);
  await attempt(e => { e.dispute = src({ pmid: 12345 }); }, /pmid/);
  await attempt(e => { e.dispute = src({ extra: 1 }); }, /extra/);
  await attempt(e => { e.dispute = { kind: 'old', exam: 'x', sources: [] }; }, /sources/);
  assert.equal((await h.post({ kind: 'expl', id: ID_A, entry: 'x', baseBlobSha: EXPL_TOKEN })).body.error, 'invalid_entry');
  assert.equal((await h.post({ kind: 'expl', id: '101-1', entry: editedEntry(), baseBlobSha: EXPL_TOKEN })).body.error, 'invalid_id');
  assert.equal((await h.post({ kind: 'expl', id: ID_A, entry: editedEntry(), baseBlobSha: 'nope' })).body.error, 'invalid_revision');
  assert.equal((await h.post({ kind: 'expl', id: ID_A, entry: editedEntry() })).body.error, 'invalid_request');
  const unknown = await h.post({ kind: 'expl', id: '999-99', entry: editedEntry(), baseBlobSha: EXPL_TOKEN });
  assert.equal(unknown.status, 404); assert.equal(unknown.body.error, 'unknown_question');
  assert.deepEqual(h.writes(), []);
  // Accepted: pmid digit string, dispute null (dropped), all-false ok, flags omitted when empty.
  const entry = editedEntry(); entry.dispute = src({ pmid: '12345' }); entry.flags = ['附註'];
  assert.equal((await h.post({ kind: 'expl', id: ID_A, entry, baseBlobSha: EXPL_TOKEN })).status, 200);
  const clear = fixture(), cleared = editedEntry(); cleared.dispute = null; cleared.flags = []; cleared.items.forEach(item => { item.ok = false; });
  assert.equal((await clear.post({ kind: 'expl', id: ID_A, entry: cleared, baseBlobSha: EXPL_TOKEN })).status, 200);
  const stored = JSON.parse(clear.fileAt(clear.head(), EXPL))[ID_A];
  assert.equal('dispute' in stored, false); assert.equal('flags' in stored, false);
});

test('explanation save fails closed when the stored file is not in the exact json.dumps format', async () => {
  const h = fixture();
  h.trees.get(h.commits.get(h.main).tree.sha).set(EXPL, h.store(EXPL_TEXT + '\n'));
  const result = await h.post({ kind: 'expl', id: ID_A, entry: editedEntry(), baseBlobSha: sha(EXPL_TEXT + '\n') });
  assert.equal(result.status, 409); assert.equal(result.body.error, 'format_mismatch');
  assert.deepEqual(h.writes(), []); assert.equal(h.head(), undefined);
  const api = content();
  for (const broken of [EXPL_TEXT + '\n', EXPL_TEXT.replace('\n "101-01"', '\n  "101-01"'), EXPL_TEXT.replace(/\n/g, '\r\n'), '[]', 'null', '{']) {
    assert.throws(() => api.replaceExplanation(broken, ID_A, editedEntry()), error => error.code === 'format_mismatch');
  }
});

test('stale baseBlobSha is a conflict and nothing is written', async () => {
  const h = fixture();
  const first = await h.post(noteBody());
  assert.equal(first.status, 200);
  const head = h.head(), writes = h.writes().length;
  assert.equal((await h.post(noteBody({ content: editedNote() + '\n' }))).status, 409, 'the main token is stale once the chapter is drafted');
  assert.equal((await h.post(noteBody({ baseBlobSha: 'b'.repeat(40) }))).body.error, 'conflict');
  assert.equal((await h.post(explBody(ID_A, { baseBlobSha: 'c'.repeat(40) }))).status, 409);
  assert.equal(h.head(), head); assert.equal(h.writes().length, writes);
  // A token from before main changed that file is stale too.
  const h2 = fixture();
  h2.moveMain({ [noteFile(NOTE_CH)]: NOTES[NOTE_CH] + '\n' });
  assert.equal((await h2.post(noteBody())).status, 409);
  assert.deepEqual(h2.writes(), []);
});

test('a concurrent writer makes the ref update fail as a conflict', async () => {
  const h = fixture();
  const first = await h.post(noteBody());
  assert.equal(first.status, 200);
  h.raceOnCommit = () => h.refs.set(BRANCH, h.addCommit(h.head(), { [noteFile(OTHER_CH)]: 'other' }));
  const raced = await h.post({ kind: 'note', ch: NOTE_CH, content: editedNote() + '\n', baseBlobSha: first.body.blobSha });
  assert.equal(raced.status, 409); assert.equal(raced.body.error, 'conflict');
  const h2 = fixture();
  h2.raceOnCommit = () => h2.refs.set(BRANCH, h2.addCommit(h2.main, { 'x.txt': 'y' }));
  const created = await h2.post(noteBody());
  assert.equal(created.status, 409); assert.equal(created.body.error, 'conflict');
});

test('body cap, malformed JSON and bad draft records', async () => {
  const h = fixture();
  const big = JSON.stringify(noteBody({ content: '<p>' + 'x'.repeat(650_000) + '</p>' }));
  const streamed = await h.send('POST', '', big);
  assert.equal(streamed.status, 413); assert.equal(streamed.body.error, 'too_large');
  assert.equal((await h.send('POST', '', '{}', { 'content-length': '700000' })).status, 413);
  assert.equal((await h.send('POST', '', '{not json')).status, 400);
  assert.equal((await h.send('POST', '', Buffer.from([0xff, 0xfe]).toString('latin1'))).status, 400);
  const mid = await h.post(noteBody({ content: '<section class="ex-note" id="a">\n<h2>T</h2>\n<p>' + 'x'.repeat(500_000) + '</p>\n</section>' }));
  assert.equal(mid.status, 413); assert.equal(mid.body.error, 'too_large');
  assert.deepEqual(h.writes(), []);
  const withoutManifest = fixture();
  withoutManifest.refs.set(BRANCH, withoutManifest.addCommit(withoutManifest.main, { 'x.txt': 'y' }));
  const noManifest = await withoutManifest.post(noteBody());
  assert.equal(noManifest.status, 502); assert.equal(noManifest.body.error, 'invalid_draft_record');
  assert.equal((await withoutManifest.get('?mode=list')).body.error, 'invalid_draft_record');
  const good = { version: 1, baseMain: 'a'.repeat(40), updated: '2026-01-01T00:00:00Z', notes: [], explanations: [] };
  for (const record of ['{"version":2}\n', '[]\n', JSON.stringify(good) + '\n', JSON.stringify({ ...good, notes: [0] }, null, 1) + '\n',
    JSON.stringify({ ...good, explanations: ['bad'] }, null, 1) + '\n', JSON.stringify({ ...good, extra: 1 }, null, 1) + '\n',
    JSON.stringify({ ...good, baseMain: 'zz' }, null, 1) + '\n', JSON.stringify(good, null, 1)]) {
    const broken = fixture();
    broken.refs.set(BRANCH, broken.addCommit(broken.main, { [MANIFEST]: record }));
    const result = await broken.post(noteBody());
    assert.equal(result.status, 502, record); assert.equal(result.body.error, 'invalid_draft_record');
    assert.deepEqual(broken.writes(), []);
  }
  const fine = fixture();
  fine.refs.set(BRANCH, fine.addCommit(fine.main, { [MANIFEST]: JSON.stringify(good, null, 1) + '\n' }));
  assert.equal((await fine.get('?mode=list')).status, 200, 'a well-formed empty manifest is accepted');
});

test('upstream failures and tampered repository data fail closed without leaking details', async () => {
  const h = fixture();
  h.failRead = 'contents/data/exam/notes';
  const failed = await h.get('?mode=list');
  assert.equal(failed.status, 502); assert.match(failed.body.error, /^github_/);
  const tampered = fixture();
  tampered.corrupt = noteFile(NOTE_CH);
  const bad = await tampered.get('?kind=note&ch=' + NOTE_CH);
  assert.equal(bad.status, 502); assert.equal(bad.body.error, 'invalid_repository_content');
  const mismatch = fixture();
  mismatch.tamper = (route, result) => route === 'git/blobs/' + EXPL_TOKEN ? { ...result, content: Buffer.from('x'.repeat(result.size)).toString('base64') } : result;
  assert.equal((await mismatch.get('?kind=expl&id=' + ID_A)).status, 502);
  const unverified = fixture();
  unverified.tamper = (route, result) => route === 'git/refs' ? { object: { sha: 'f'.repeat(40) } } : result;
  const notVerified = await unverified.post(noteBody());
  assert.equal(notVerified.status, 502); assert.equal(notVerified.body.error, 'save_not_verified');
  assert.ok(h.logs.every(line => !line.includes('fixture-secret')));
});
