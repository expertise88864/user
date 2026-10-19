// Real admin.html + admin/*.js with an isolated repository and a mocked
// /api/admin/exam-draft: the exam sidebar, the note editor with its sandboxed
// preview, the explanation form, save/409/rejection handling and the overlay's
// focus behaviour. No credentials, no external network, no writes to GitHub.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async function checkExamEditor(browser) {
  const SAVED = '已存入雲端草稿（cms-exam/drafts）。上線需由維護流程整合、重新生成、CI 與審查後才會發佈。';
  const sha = char => char.repeat(40);
  const notes = {
    17: '<section class="ex-note" id="alpha">\n<h2>Alpha 標題</h2>\n<p>原始 <strong class="ex-n">12</strong> <mark data-q="101-01">重點</mark></p>\n</section>\n',
    24: '<section class="ex-note" id="beta">\n<h2>Beta 草稿</h2>\n<p>draft body</p>\n</section>\n',
    40: '<section class="ex-note" id="gamma">\n<h2>Gamma</h2>\n</section>\n',
  };
  const blob = { 17: sha('a'), 24: sha('b'), 40: sha('c') };
  const source = { 17: 'main', 24: 'draft', 40: 'main' };
  const DISPUTE = { kind: 'old', exam: '考試答案：B', current: '現行：C', sources: [{ pmid: '123', title: 'T', year: 2020, url: 'https://pubmed.ncbi.nlm.nih.gov/123/' }] };
  const entries = {
    '101-01': { summary: '摘要一', items: [
      { key: 'A', label: '標籤A', ok: false, text: '說明 [i]Candida albicans[/i]。', refs: [[81, '1462-1463']] },
      { key: 'B', label: '標籤B', ok: true, text: '說明B', refs: [[52, '266-267'], ['M', '120']] }],
    flags: ['附註一', '附註二'], dispute: DISPUTE },
    '101-02': { summary: '摘要二', items: [{ key: 'A', label: 'x', ok: true, text: 'y', refs: [] }] },
  };
  let explBlob = sha('d');
  const titles = { 17: 'Alpha chapter', 24: 'Beta chapter', 40: '<img src=x onerror="window.__injected=1">' };
  let draft = { exists: true, notes: [24], explanations: ['101-02'], updated: '2026-10-19T00:00:00.000Z' };
  const posts = [], gitWrites = [], gets = [];
  // Serve admin pages with the production CSP so a policy violation (script,
  // style, frame or connect) in the editor or its preview fails this test.
  const vercel = JSON.parse(fs.readFileSync('vercel.json', 'utf8'));
  const cspFor = source => vercel.headers.find(entry => entry.source === source).headers.find(header => header.key === 'Content-Security-Policy').value;
  const csp = { page: cspFor('/admin.html'), asset: cspFor('/admin/(.*)') };
  const violations = [];
  const holds = [];
  const hold = test => {
    const entry = { test }; let release, arrive;
    entry.gate = new Promise(resolve => { release = resolve; });
    entry.arrived = new Promise(resolve => { arrive = resolve; });
    entry.arrive = arrive; holds.push(entry);
    return { release, arrived: entry.arrived };
  };
  let nextFailure = null, nextBlob = 0, listFails = false;
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block' });
  try {
    const page = await context.newPage();
    page.on('console', message => { if (/Content[- ]Security[- ]Policy|Refused to/i.test(message.text())) violations.push(message.text()); });
    const dialogs = [];
    let confirmAnswer = true;
    page.on('dialog', dialog => { dialogs.push(dialog.message()); (confirmAnswer ? dialog.accept() : dialog.dismiss()).catch(() => {}); });
    await page.addInitScript(() => {
      sessionStorage.setItem('cd_gh_pat', 'fixture-only-not-a-real-token');
      sessionStorage.setItem('cd_gh_pat_exp', String(Date.now() + 600000));
    });
    await page.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin === 'https://api.github.com') {
        if (request.method() !== 'GET') { gitWrites.push(request.url()); return route.abort(); }
        if (/\/contents\/?$/.test(url.pathname)) return route.fulfill({ status: 200, json: [{ type: 'file', name: 'index.html', path: 'index.html' }] });
        return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      }
      if (url.origin !== 'https://exam-editor.test') return route.abort();
      if (url.pathname === '/api/admin/login') return route.fulfill({ status: 200, json: { ok: true, login: 'expertise88864' } });
      if (url.pathname === '/api/admin/article-draft') return route.fulfill({ status: 200, json: { drafts: [], nextOffset: null, unsupportedRefs: 0 } });
      if (url.pathname === '/api/admin/exam-draft') {
        // A held request signals when it arrived and answers only when released.
        const held = holds.findIndex(entry => entry.test(url, request));
        if (held >= 0) { const [entry] = holds.splice(held, 1); entry.arrive(); await entry.gate; }
        assert.equal(request.headers().authorization, undefined, 'the browser PAT is never sent to the cookie-authenticated API');
        if (request.method() === 'GET') {
          gets.push(url.search);
          const q = url.searchParams;
          if (q.get('mode') === 'list') {
            if (listFails) return route.fulfill({ status: 502, json: { ok: false, error: 'github_timeout' } });
            return route.fulfill({ json: { ok: true, notes: [{ ch: 17, title: titles[17] }, { ch: 24, title: titles[24] }, { ch: 40, title: titles[40] }], draft } });
          }
          if (q.get('kind') === 'note') {
            const ch = Number(q.get('ch'));
            return route.fulfill({ json: { ok: true, ch, content: notes[ch], source: source[ch], blobSha: blob[ch] } });
          }
          if (q.get('kind') === 'expl') {
            const id = q.get('id');
            if (!entries[id]) return route.fulfill({ status: 404, json: { ok: false, error: 'unknown_question' } });
            return route.fulfill({ json: { ok: true, id, entry: entries[id], source: draft.explanations.includes(id) ? 'draft' : 'main', blobSha: explBlob } });
          }
          return route.fulfill({ status: 400, json: { ok: false, error: 'invalid_request' } });
        }
        assert.equal(request.method(), 'POST');
        assert.equal(request.headers()['content-type'], 'application/json');
        const body = JSON.parse(request.postData());
        posts.push(body);
        if (nextFailure) { const failure = nextFailure; nextFailure = null; return route.fulfill(failure); }
        const fresh = sha(String.fromCharCode(101 + ++nextBlob));
        if (body.kind === 'note') {
          assert.equal(body.baseBlobSha, blob[body.ch], 'the save carries the token it was loaded with');
          notes[body.ch] = body.content; blob[body.ch] = fresh; source[body.ch] = 'draft';
          draft = { ...draft, notes: [...new Set([...draft.notes, body.ch])].sort((a, b) => a - b) };
        } else {
          assert.equal(body.baseBlobSha, explBlob);
          entries[body.id] = body.entry; explBlob = fresh;
          draft = { ...draft, explanations: [...new Set([...draft.explanations, body.id])].sort() };
        }
        return route.fulfill({ json: { ok: true, head: sha('9'), blobSha: fresh, draft } });
      }
      if (request.method() !== 'GET') return route.abort();
      const root = process.cwd(), target = path.resolve(root, '.' + url.pathname);
      if (!target.startsWith(root + path.sep) || !fs.existsSync(target) || !fs.statSync(target).isFile()) return route.fulfill({ status: 404, body: '' });
      const contentType = target.endsWith('.js') ? 'application/javascript' : target.endsWith('.css') ? 'text/css' : target.endsWith('.html') ? 'text/html' : 'application/octet-stream';
      const policy = url.pathname === '/admin.html' ? csp.page : url.pathname.startsWith('/admin/') ? csp.asset : null;
      return route.fulfill({ status: 200, contentType, body: fs.readFileSync(target), headers: policy ? { 'Content-Security-Policy': policy } : {} });
    });
    const status = () => page.locator('#examStatus').textContent();
    const poll = async (check, message) => {
      for (let i = 0; i < 100; i++) { if (await check()) return; await page.waitForTimeout(50); }
      assert.fail(message);
    };
    const previewFrame = async () => (await page.locator('#examPreview').elementHandle()).contentFrame();

    await page.goto('https://exam-editor.test/admin.html');
    await page.waitForSelector('#examList .exam-item[data-exam-note="17"]');

    // --- sidebar: own container after #fileList, headings, draft marks, text-only rendering
    assert.deepEqual(await page.evaluate(() => {
      const list = document.getElementById('fileList');
      return { next: list.nextElementSibling && list.nextElementSibling.id, inside: list.querySelectorAll('.exam-item').length, hidden: document.getElementById('examList').hidden };
    }), { next: 'examList', inside: 0, hidden: false });
    assert.deepEqual(await page.locator('#examList .exam-group-title').allTextContents(), ['考試重點（3）', '題目詳解']);
    assert.equal(await page.locator('#examList .exam-group-title').first().getAttribute('role'), 'heading');
    assert.deepEqual(await page.locator('#examList [data-exam-note]').evaluateAll(nodes => nodes.map(node => [node.dataset.examNote, node.textContent])),
      [['17', 'Ch.17 Alpha chapter'], ['24', 'Ch.24 Beta chapter · 雲端草稿'], ['40', 'Ch.40 <img src=x onerror="window.__injected=1">']]);
    assert.equal(await page.locator('#examList img').count(), 0, 'chapter titles are text, never markup');
    assert.equal(await page.evaluate(() => window.__injected), undefined);
    assert.equal(await page.locator('#examExplOpen').textContent(), '編輯題目詳解…');
    assert.equal(await page.locator('#examList [data-exam-expl="101-02"]').textContent(), '101-02 · 雲端草稿');
    // The file-list regrouping (and another refresh) neither removes nor duplicates the exam rows.
    await page.evaluate(() => refreshFileList());
    await page.waitForTimeout(200);
    assert.equal(await page.locator('#examList .exam-item').count(), 3 + 1 + 1);
    assert.equal(await page.locator('#fileList .exam-item').count(), 0);
    assert.equal(await page.locator('#examList').isVisible(), true);

    // --- note editor: dialog semantics, source, sandboxed styled preview
    const row17 = page.locator('#examList [data-exam-note="17"]');
    await row17.click();
    await page.waitForFunction(() => document.getElementById('examNoteSource') && !document.getElementById('examNoteSource').disabled && document.getElementById('examNoteSource').value);
    assert.equal(await page.locator('#examOverlay').isVisible(), true);
    const dialog = page.locator('#examOverlay [role="dialog"]');
    assert.equal(await dialog.getAttribute('aria-modal'), 'true');
    assert.equal(await dialog.getAttribute('aria-labelledby'), 'examDialogTitle');
    assert.equal(await page.locator('#examDialogTitle').textContent(), '考試重點 · Ch.17');
    assert.equal(await page.locator('#examNoteSource').inputValue(), notes[17]);
    assert.match(await status(), /已載入（來源：正式版 main）/);
    assert.notEqual(await page.locator('#examSave').evaluate(node => getComputedStyle(node).backgroundImage), 'none', 'the primary button keeps its fill over the shared button reset');
    assert.equal(await page.locator('#examPreview').getAttribute('sandbox'), '', 'preview has no sandbox permissions at all');
    const srcdoc = await page.locator('#examPreview').getAttribute('srcdoc');
    assert.ok(srcdoc.includes('href="/admin/exam-preview.css"') && !/<script/i.test(srcdoc));
    assert.equal(await page.evaluate(() => document.getElementById('main-content').inert && document.querySelector('header.top').inert), true, 'background is inert while the dialog is open');
    await poll(async () => (await (await previewFrame()).locator('h2').textContent()) === 'Alpha 標題', 'preview shows the heading');
    const frame = await previewFrame();
    await poll(() => frame.evaluate(() => getComputedStyle(document.querySelector('.ex-note')).borderTopStyle === 'solid'), 'exam CSS applies in the preview');
    assert.equal(await frame.evaluate(() => getComputedStyle(document.querySelector('strong.ex-n')).fontWeight), '700');
    // Typing updates the preview after the debounce.
    await page.locator('#examNoteSource').fill(notes[17].replace('</section>', '<p>新增行</p>\n</section>'));
    await poll(async () => (await (await previewFrame()).locator('p').last().textContent()) === '新增行', 'preview follows the textarea');

    // --- save: exact body, success message, sidebar mark, next save uses the new token
    await page.locator('#examSave').click();
    await poll(async () => (await status()) === SAVED, 'saved message');
    assert.deepEqual(posts.at(-1), { kind: 'note', ch: 17, content: notes[17], baseBlobSha: sha('a') });
    assert.equal(await page.locator('#examStatus').getAttribute('class'), 'exam-status exam-ok');
    assert.equal(await page.locator('#examList [data-exam-note="17"]').textContent(), 'Ch.17 Alpha chapter · 雲端草稿');
    await page.locator('#examNoteSource').fill(notes[17] + '<!-- second -->');
    await page.locator('#examSave').click();
    await poll(() => posts.length === 2, 'second save posted');
    assert.notEqual(posts[1].baseBlobSha, sha('a'), 'the token advances after a save');

    // --- server rejection is shown verbatim and the text stays
    nextFailure = { status: 400, json: { ok: false, error: 'invalid_note', reason: '不允許的標籤 <script>（第 3 行）' } };
    await page.locator('#examNoteSource').fill('<section class="ex-note" id="x">\n<h2>T</h2>\n<script>1</script></section>');
    await page.locator('#examSave').click();
    await poll(async () => (await status()).startsWith('重點內容被拒絕'), 'rejection shown');
    assert.equal(await status(), '重點內容被拒絕：不允許的標籤 <script>（第 3 行）');
    assert.equal(await page.locator('#examStatus').getAttribute('class'), 'exam-status exam-err');
    assert.equal(await page.locator('#examNoteSource').inputValue(), '<section class="ex-note" id="x">\n<h2>T</h2>\n<script>1</script></section>');

    // --- 409 keeps the text, backs it up locally, reload + restore brings it back
    const mine = '<section class="ex-note" id="mine">\n<h2>我的修改</h2>\n</section>\n';
    nextFailure = { status: 409, json: { ok: false, error: 'conflict' } };
    await page.locator('#examNoteSource').fill(mine);
    await page.locator('#examSave').click();
    await poll(async () => (await status()).startsWith('版本衝突'), 'conflict message');
    assert.equal(await page.locator('#examNoteSource').inputValue(), mine, 'the text is kept');
    assert.deepEqual(JSON.parse(await page.evaluate(() => localStorage.getItem('dn-exam-draft-backup:note:17'))).value, mine, 'and backed up under a namespaced key');
    confirmAnswer = true;
    const dialogsBefore = dialogs.length;
    await page.locator('#examReload').click();
    await poll(async () => (await page.locator('#examNoteSource').inputValue()) === notes[17], 'reload shows the server version');
    assert.equal(dialogs.length, dialogsBefore + 1, 'reloading over unsaved text asks first');
    assert.equal(await page.locator('#examRestore').isVisible(), true);
    await page.locator('#examRestore').click();
    assert.equal(await page.locator('#examNoteSource').inputValue(), mine);
    assert.equal(await page.locator('#examRestore').isVisible(), false);

    // --- focus trap, Esc and close with unsaved changes
    await page.locator('#examSave').focus();
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => document.activeElement.closest('#examOverlay') !== null), true, 'Tab stays inside the dialog');
    await page.locator('#examClose').focus();
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => document.activeElement.closest('#examOverlay') !== null), true);
    confirmAnswer = false;
    await page.keyboard.press('Escape');
    await poll(() => dialogs.some(message => message.includes('尚未存成雲端草稿')), 'unsaved warning on Esc');
    assert.equal(await page.locator('#examOverlay').isVisible(), true, 'declining keeps the dialog open');
    await page.locator('#examClose').click();
    assert.equal(await page.locator('#examOverlay').isVisible(), true);
    confirmAnswer = true;
    await page.keyboard.press('Escape');
    await poll(async () => !(await page.locator('#examOverlay').isVisible()), 'closed after confirming');
    assert.equal(await page.evaluate(() => document.activeElement && document.activeElement.dataset.examNote), '17', 'focus returns to the row that opened it');
    assert.equal(await page.evaluate(() => document.getElementById('main-content').inert), false);
    // A clean dialog closes without asking.
    const asked = dialogs.length;
    await page.locator('#examList [data-exam-note="24"]').click();
    await page.waitForFunction(() => document.getElementById('examNoteSource').value.includes('Beta'));
    assert.match(await status(), /來源：雲端草稿/);
    await page.locator('#examClose').click();
    await poll(async () => !(await page.locator('#examOverlay').isVisible()), 'closed');
    assert.equal(dialogs.length, asked);

    // --- explanation form
    await page.locator('#examExplOpen').click();
    assert.equal(await page.locator('#examExplPanel').isVisible(), true);
    assert.equal(await page.locator('#examNotePanel').isVisible(), false);
    assert.equal(await page.locator('#examExplId').evaluate(node => document.activeElement === node), true);
    await page.locator('#examExplId').fill('101-1');
    await page.locator('#examExplLoad').click();
    assert.equal(await status(), '題號格式需為 YYY-NN，例如 101-01。');
    await page.locator('#examExplId').fill('999-99');
    await page.locator('#examExplLoad').click();
    await poll(async () => (await status()).startsWith('找不到這個題號'), 'unknown question message');
    await page.locator('#examExplId').fill('101-01');
    await page.locator('#examExplLoad').click();
    await page.waitForSelector('#examExplForm fieldset');
    assert.equal(await page.locator('#examExplForm fieldset').count(), 2);
    assert.deepEqual(await page.locator('#examExplForm legend').allTextContents(), ['選項 A（代號固定）', '選項 B（代號固定）']);
    const fieldValues = await page.locator('#examExplForm textarea, #examExplForm input[type="text"]').evaluateAll(nodes => nodes.map(node => node.value));
    assert.deepEqual(fieldValues, ['摘要一', '標籤A', '說明 [i]Candida albicans[/i]。', '81:1462-1463', '標籤B', '說明B', '52:266-267; M:120', '附註一\n附註二', JSON.stringify(entries['101-01'].dispute, null, 2)]);
    // Client-side checks stop obviously bad input before any request.
    const before = posts.length;
    await page.locator('#examExplForm input[type="text"]').nth(1).fill('81 1462');
    await page.locator('#examSave').click();
    assert.match(await status(), /選項 A：參考頁碼格式/);
    await page.locator('#examExplForm input[type="text"]').nth(1).fill('81:1462-1463');
    await page.locator('#examExplForm textarea').last().fill('{ not json');
    await page.locator('#examSave').click();
    assert.equal(await status(), '疑義（dispute）不是有效的 JSON。');
    assert.equal(posts.length, before);
    await page.locator('#examExplForm textarea').last().fill(JSON.stringify(entries['101-01'].dispute));
    // The server stores one line per field, so line breaks are refused before any request.
    await page.locator('#examExplForm textarea').nth(1).fill('第一行\n第二行');
    await page.locator('#examSave').click();
    assert.match(await status(), /選項 A 的標籤與說明不可換行/);
    await page.locator('#examExplForm textarea').nth(1).fill('說明 [i]Candida albicans[/i]。');
    await page.locator('#examExplForm textarea').first().fill('摘要\n兩行');
    await page.locator('#examSave').click();
    assert.equal(await status(), '摘要不可換行，請寫成同一行。');
    assert.equal(posts.length, before);
    // A server rejection of the entry shows its reason; format_mismatch and too_large have their own messages.
    await page.locator('#examExplForm textarea').first().fill('摘要一');
    nextFailure = { status: 400, json: { ok: false, error: 'invalid_entry', reason: 'items[0].refs[0] 頁碼須為 266 或 266-267' } };
    await page.locator('#examSave').click();
    await poll(async () => (await status()).startsWith('詳解內容被拒絕'), 'entry rejection shown');
    assert.equal(await status(), '詳解內容被拒絕：items[0].refs[0] 頁碼須為 266 或 266-267');
    nextFailure = { status: 409, json: { ok: false, error: 'format_mismatch', reason: 'x' } };
    await page.locator('#examSave').click();
    await poll(async () => (await status()).includes('未存檔'), 'format mismatch message');
    nextFailure = { status: 413, json: { ok: false, error: 'too_large', reason: '內容超過 400 KB' } };
    await page.locator('#examSave').click();
    await poll(async () => (await status()).startsWith('內容太大：內容超過 400 KB'), 'too large reason shown');
    assert.equal(await page.locator('#examExplForm textarea').first().inputValue(), '摘要一', 'text kept after rejections');
    // Edit and save: the body carries the form as the entry schema.
    await page.locator('#examExplForm textarea').first().fill('摘要一（修訂）');
    await page.locator('#examExplForm input[type="checkbox"]').first().check();
    await page.locator('#examExplForm input[type="text"]').nth(3).fill('52:300-301; M:121');
    await page.locator('#examExplForm textarea').nth(3).fill('附註一');
    await page.locator('#examSave').click();
    await poll(async () => (await status()) === SAVED, 'explanation saved');
    const savedBody = posts.at(-1);
    assert.deepEqual(savedBody, { kind: 'expl', id: '101-01', baseBlobSha: sha('d'), entry: { summary: '摘要一（修訂）', items: [
      { key: 'A', label: '標籤A', ok: true, text: '說明 [i]Candida albicans[/i]。', refs: [[81, '1462-1463']] },
      { key: 'B', label: '標籤B', ok: true, text: '說明B', refs: [[52, '300-301'], ['M', '121']] }],
    flags: ['附註一'], dispute: DISPUTE } });
    assert.equal(await page.locator('#examList [data-exam-expl="101-01"]').textContent(), '101-01 · 雲端草稿');
    // Empty flags and dispute are omitted entirely; the next save uses the new token.
    await page.locator('#examExplForm textarea').nth(3).fill('');
    await page.locator('#examExplForm textarea').last().fill('');
    const count = posts.length;
    await page.locator('#examSave').click();
    await poll(() => posts.length === count + 1, 'second explanation save');
    await poll(async () => (await status()) === SAVED, 'second save finished');
    assert.equal('flags' in posts.at(-1).entry, false); assert.equal('dispute' in posts.at(-1).entry, false);
    assert.notEqual(posts.at(-1).baseBlobSha, sha('d'), 'the token advances after a save');
    // Loading another id while edited asks first; a draft id opens from the sidebar.
    await page.locator('#examExplForm textarea').first().fill('改了還沒存');
    confirmAnswer = false;
    const asks = dialogs.length;
    await page.locator('#examExplId').fill('101-02');
    await page.locator('#examExplLoad').click();
    assert.equal(dialogs.length, asks + 1);
    assert.equal(await page.locator('#examExplForm textarea').first().inputValue(), '改了還沒存');
    confirmAnswer = true;
    await page.locator('#examExplLoad').click();
    await poll(async () => (await page.locator('#examExplForm textarea').first().inputValue()) === '摘要二', 'other id loaded');
    assert.match(await status(), /來源：雲端草稿/);
    await page.locator('#examClose').click();
    await poll(async () => !(await page.locator('#examOverlay').isVisible()), 'closed');
    await page.locator('#examList [data-exam-expl="101-02"]').click();
    await poll(async () => (await page.locator('#examExplForm textarea').count()) > 0 && (await page.locator('#examExplId').inputValue()) === '101-02', 'sidebar draft row opens that id');
    await page.locator('#examClose').click();

    // --- a response from a closed or replaced editor session never touches the current one
    const dirtyAsks = () => dialogs.filter(message => message.includes('尚未存成雲端草稿')).length;
    const stayOpenIfDirty = async () => {
      confirmAnswer = false; const asked = dirtyAsks();
      await page.locator('#examClose').click();
      assert.equal(dirtyAsks(), asked + 1, 'the form is still dirty');
      assert.equal(await page.locator('#examOverlay').isVisible(), true);
      confirmAnswer = true;
    };
    const closeAndWait = async () => { await page.locator('#examClose').click(); await poll(async () => !(await page.locator('#examOverlay').isVisible()), 'closed'); };
    {
      // note load: A is held, the dialog is closed and reopened (B loads), B is edited, then A answers
      const mine = '<section class="ex-note" id="mine"><h2>Mine</h2></section>';
      const a = hold(url => url.searchParams.get('kind') === 'note' && url.searchParams.get('ch') === '40');
      await page.locator('#examList [data-exam-note="40"]').click();
      await a.arrived;
      await closeAndWait();
      await page.locator('#examList [data-exam-note="40"]').click();
      await page.waitForFunction(() => document.getElementById('examNoteSource').value.includes('Gamma'));
      await page.locator('#examNoteSource').fill(mine);
      a.release();
      await page.waitForTimeout(400);
      assert.equal(await page.locator('#examNoteSource').inputValue(), mine, 'a late note load does not overwrite the edited form');
      await stayOpenIfDirty();
      await closeAndWait();
      // explanation load, same shape
      const b = hold(url => url.searchParams.get('kind') === 'expl' && url.searchParams.get('id') === '101-02');
      await page.locator('#examExplOpen').click();
      await page.locator('#examExplId').fill('101-02');
      await page.locator('#examExplLoad').click();
      await b.arrived;
      await closeAndWait();
      await page.locator('#examExplOpen').click();
      await page.locator('#examExplId').fill('101-02');
      await page.locator('#examExplLoad').click();
      await page.waitForSelector('#examExplForm textarea');
      await page.locator('#examExplForm textarea').first().fill('第二個工作階段的修改');
      b.release();
      await page.waitForTimeout(400);
      assert.equal(await page.locator('#examExplForm textarea').first().inputValue(), '第二個工作階段的修改', 'a late explanation load does not overwrite the edited form');
      await stayOpenIfDirty();
      await closeAndWait();
      // note save: A's POST is held, the dialog is closed (confirmed) and reopened, B is edited, then A's save answers
      const c = hold((url, request) => request.method() === 'POST');
      await page.locator('#examList [data-exam-note="17"]').click();
      await page.waitForFunction(() => document.getElementById('examNoteSource').value.includes('Alpha'));
      await page.locator('#examNoteSource').fill('<section class="ex-note" id="first"><h2>First</h2></section>');
      const postsBefore = posts.length;
      await page.locator('#examSave').click();
      await c.arrived;
      await closeAndWait();
      await page.locator('#examList [data-exam-note="17"]').click();
      await page.waitForFunction(() => document.getElementById('examNoteSource').value.length > 0 && !document.getElementById('examNoteSource').disabled);
      await page.locator('#examNoteSource').fill(mine);
      c.release();
      await poll(() => posts.length === postsBefore + 1, 'the held save reached the server');
      await page.waitForTimeout(400);
      assert.equal(await page.locator('#examNoteSource').inputValue(), mine, 'a late save response does not overwrite the new form');
      assert.notEqual(await status(), SAVED, 'and does not report the new text as saved');
      await stayOpenIfDirty();
      await closeAndWait();
    }

    // --- Ctrl/Cmd+S belongs to the open exam dialog, not the article save behind it
    {
      await page.evaluate(() => { window.__articleSaves = 0; window.save = () => { window.__articleSaves += 1; }; });
      await page.locator('#examList [data-exam-note="17"]').click();
      await page.waitForFunction(() => document.getElementById('examNoteSource').value.length > 0 && !document.getElementById('examNoteSource').disabled);
      await page.locator('#examNoteSource').fill('<section class="ex-note" id="keys"><h2>Keys</h2></section>');
      const before = posts.length;
      await page.locator('#examNoteSource').press('Control+s');
      await poll(() => posts.length === before + 1, 'Ctrl+S posts the note');
      assert.equal(posts.at(-1).kind, 'note');
      await poll(async () => (await status()) === SAVED, 'saved by the shortcut');
      assert.equal(await page.evaluate(() => window.__articleSaves), 0, 'the article save was not triggered');
      // while a save is running the shortcut does nothing more
      const slow = hold((url, request) => request.method() === 'POST');
      await page.locator('#examNoteSource').fill('<section class="ex-note" id="keys"><h2>Keys 2</h2></section>');
      const count = posts.length;
      await page.locator('#examNoteSource').press('Meta+s');
      await slow.arrived;
      await page.locator('#examNoteSource').press('Control+s');
      await page.locator('#examNoteSource').press('Control+s');
      slow.release();
      await poll(() => posts.length === count + 1, 'one save');
      await page.waitForTimeout(300);
      assert.equal(posts.length, count + 1, 'no second request while busy');
      assert.equal(await page.evaluate(() => window.__articleSaves), 0);
      await closeAndWait();
      // the explanation form too
      await page.locator('#examExplOpen').click();
      await page.locator('#examExplId').fill('101-02');
      await page.locator('#examExplLoad').click();
      await page.waitForSelector('#examExplForm textarea');
      await page.locator('#examExplForm textarea').first().fill('快捷鍵存檔');
      const explBefore = posts.length;
      await page.locator('#examExplForm textarea').first().press('Control+s');
      await poll(() => posts.length === explBefore + 1, 'Ctrl+S posts the explanation');
      assert.equal(posts.at(-1).kind, 'expl'); assert.equal(posts.at(-1).entry.summary, '快捷鍵存檔');
      assert.equal(await page.evaluate(() => window.__articleSaves), 0);
      await closeAndWait();
      // with the dialog closed the shell's own shortcut works again (proves the spy sees it)
      await page.locator('body').press('Control+s');
      assert.equal(await page.evaluate(() => window.__articleSaves), 1);
    }

    // --- logging out hides the section; a failed list read is reported and can be retried
    const login = () => page.evaluate(() => { sessionStorage.setItem('cd_gh_pat', 'fixture-only-not-a-real-token'); sessionStorage.setItem('cd_gh_pat_exp', String(Date.now() + 600000)); window.dispatchEvent(new Event('cd-admin-auth-changed')); });
    const logout = () => page.evaluate(() => { sessionStorage.removeItem('cd_gh_pat'); sessionStorage.removeItem('cd_gh_pat_exp'); window.dispatchEvent(new Event('cd-admin-auth-changed')); });
    await logout();
    await poll(() => page.evaluate(() => document.getElementById('examList').hidden), 'section hidden after logout');
    assert.equal(await page.locator('#examList').isVisible(), false);
    assert.equal(await page.locator('#examList .exam-item').count(), 0, 'rows are dropped on logout');
    listFails = true;
    await login();
    await page.waitForSelector('#examRetry');
    assert.match(await page.locator('#examList [role="status"]').textContent(), /考試區清單暫時無法讀取（github_timeout）/);
    listFails = false;
    await page.locator('#examRetry').click();
    await page.waitForSelector('#examList [data-exam-note="17"]');
    assert.equal(await page.locator('#examRetry').count(), 0);
    assert.deepEqual(violations, [], 'no CSP violations under the production admin policy');
    assert.deepEqual(gitWrites, []);
    console.log('Exam editor: sidebar, sandboxed styled preview, note and explanation saves, 409/rejection handling, focus and logout verified');
  } finally { await context.close(); }
};

if (require.main === module) (async () => {
  const browser = await require('playwright').chromium.launch();
  try { await module.exports(browser); } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
