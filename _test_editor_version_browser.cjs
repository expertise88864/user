// Actual admin UI with an isolated repository, collectors and cookie API.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
module.exports = async function checkEditorVersion(browser, options = {}) {
  const FILE = 'blog/example.html', HEAD = 'a'.repeat(40), BLOB = 'b'.repeat(40);
  const BASE = 'c'.repeat(40), MAIN = 'd'.repeat(40), LIVE = 'e'.repeat(40), NEXT = 'f'.repeat(40);
  const oldHtml = '<!doctype html><html lang="zh-Hant"><head><title>Fixture</title></head><body><main><h1>Fixture</h1><div id="proseZh"><p>Previous local text</p></div></main></body></html>';
  const liveHtml = oldHtml.replace('Previous local text', 'Verified production text');
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block' });
  let current = { head: HEAD, baseSha: BASE, blobSha: BLOB, content: oldHtml }, state = 'ci_failed';
  let receiptBlocked = false, pause = false, release; const writes = [], externalWrites = [];
  try {
    const page = await context.newPage();
    await page.addInitScript(() => {
      sessionStorage.setItem('cd_gh_pat', 'fixture-only-not-a-real-token');
      sessionStorage.setItem('cd_gh_pat_exp', String(Date.now() + 600000));
    });
    page.on('dialog', dialog => dialog.accept(dialog.type() === 'prompt' ? 'Fixture image' : undefined));
    await page.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin === 'https://api.github.com') {
        if (request.method() !== 'GET') { externalWrites.push(url.pathname); return route.abort(); }
        return route.fulfill({ status: 200, json: [] });
      }
      if (url.origin !== 'https://editor-version.test') return route.abort();
      if (url.pathname === '/api/admin/login') return route.fulfill({ status: 200, json: { ok: true, login: 'expertise88864' } });
      if (url.pathname === '/api/admin/article-draft') {
        if (request.method() === 'GET') {
          if (url.searchParams.get('mode') === 'list') return route.fulfill({ status: 200, json: { drafts: [{ file: FILE, head: current.head, legacy: false }], nextOffset: null, unsupportedRefs: 0 } });
          if (url.searchParams.get('mode') === 'publication') return route.fulfill({ status: 200, json: {
            file: FILE, head: current.head, baseSha: current.baseSha, blobSha: current.blobSha,
            publication: { mainSha: MAIN, mainBlobSha: LIVE, matchesLoadedVersion: current.blobSha === LIVE,
              sourceIndexable: true, ciVerified: state === 'live', deploymentVerified: state === 'live',
              published: state === 'live' && current.blobSha === LIVE, state, checks: [], observedAt: new Date().toISOString() },
          } });
          return route.fulfill({ status: 200, json: { file: FILE, ...current, media: [], legacy: false,
            conflict: current.baseSha !== LIVE, request: null, status: 'cloud_draft' } });
        }
        const body = request.postDataJSON(); writes.push(body);
        assert.equal(body.action, 'new-version'); assert.equal(body.file, FILE);
        assert.equal(body.expectedHead, current.head); assert.equal(body.expectedBlob, current.blobSha);
        assert.equal(body.expectedMain, MAIN); assert.equal(body.expectedMainBlob, LIVE); assert.equal(body.confirmed, true);
        assert.equal(body.content, undefined);
        if (receiptBlocked) return route.fulfill({ status: 409, json: { error: 'publication_receipt_not_retired' } });
        if (pause) { pause = false; await new Promise(resolve => { release = resolve; }); }
        current = { head: NEXT, baseSha: LIVE, blobSha: LIVE, content: liveHtml };
        return route.fulfill({ status: 200, json: { file: FILE, head: NEXT, baseSha: LIVE, blobSha: LIVE,
          status: 'cloud_draft', verified: true, published: false } });
      }
      if (request.method() !== 'GET') return route.abort();
      const root = process.cwd(), file = path.resolve(root, '.' + url.pathname);
      if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return route.fulfill({ status: 404, body: '' });
      const contentType = file.endsWith('.js') ? 'application/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.html') ? 'text/html' : 'application/octet-stream';
      return route.fulfill({ status: 200, contentType, body: fs.readFileSync(file) });
    });
    await page.goto('https://editor-version.test/admin.html');
    await page.waitForFunction(() => !!window.DNEditorDraftBridge);
    assert.equal(await page.evaluate(file => loadFile(file), FILE), true);
    await page.locator('#newDraftVersionBtn').click();
    await page.waitForFunction(() => !SAVE_PENDING);
    assert.equal(writes.length, 0); assert.match(await page.locator('#status').textContent(), /正式 CI/);
    state = 'live';
    await page.evaluate(() => {
      window.fixtureSetItem = Storage.prototype.setItem;
      Storage.prototype.setItem = function(key, value) {
        if (key.startsWith('cd-draft-version-backup:')) throw new DOMException('Fixture quota', 'QuotaExceededError');
        return window.fixtureSetItem.call(this, key, value);
      };
    });
    await page.locator('#newDraftVersionBtn').click(); await page.waitForFunction(() => !SAVE_PENDING);
    assert.equal(writes.length, 0); assert.match(await page.locator('#status').textContent(), /快照未能完整保存/);
    await page.evaluate(() => { Storage.prototype.setItem = window.fixtureSetItem; });
    // Use a writable source for the local pending image fixture; production
    // conflict protection itself is separately asserted by the API tests.
    current.baseSha = LIVE;
    assert.equal(await page.evaluate(file => loadFile(file), FILE), true);
    const editor = page.frameLocator('iframe.editor').locator('[data-cd-editable="1"]');
    await editor.waitFor();
    const gif = Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64');
    await editor.click(); await page.locator('#imageInput').setInputFiles({ name: 'fixture.gif', mimeType: 'image/gif', buffer: gif });
    await editor.locator('img').waitFor();
    await page.locator('#sourceBtn').click();
    const source = page.locator('#frameWrap textarea'); await source.waitFor();
    const outgoing = await page.evaluate(() => getCurrentEditorContent());
    receiptBlocked = true;
    await page.locator('#newDraftVersionBtn').click(); await page.waitForFunction(() => !SAVE_PENDING);
    assert.equal(writes.length, 1); assert.match(await page.locator('#status').textContent(), /發布證據/);
    const backup = await page.evaluate(file => JSON.parse(localStorage.getItem('cd-draft-version-backup:' + file)), FILE);
    assert.equal(backup.content, outgoing); assert.equal(backup.draft.media.length, 1);
    assert.ok(!backup.content.includes('src="data:')); assert.ok(backup.content.includes('/blog/images/example/'));
    receiptBlocked = false; pause = true;
    const resetting = page.evaluate(() => DNEditorDraftBridge.startNewVersion());
    for (let i = 0; i < 100 && !release; i++) await page.waitForTimeout(10);
    assert.ok(release);
    await source.fill(outgoing.replace('Previous local text', 'Typing during new version'));
    release(); release = null; await resetting;
    assert.equal(await page.evaluate(() => DNArticleDrafts.localState(CURRENT_FILE).head), HEAD);
    assert.match(await source.inputValue(), /Typing during new version/);
    assert.match(await page.locator('#status').textContent(), /新編輯保留/);
    const autosaved = await page.evaluate(file => JSON.parse(localStorage.getItem(autosaveKey(file))), FILE);
    assert.match(autosaved.content, /Typing during new version/); assert.equal(autosaved.draft.media.length, 1);
    // A later explicit operation is needed; never automatically retry a POST.
    current = { head: HEAD, baseSha: LIVE, blobSha: BLOB, content: oldHtml };
    await page.evaluate(() => { DIRTY = false; });
    assert.equal(await page.evaluate(file => loadFile(file), FILE), true);
    await page.evaluate(async file => {
      const saved = JSON.parse(localStorage.getItem('cd-draft-version-backup:' + file));
      await DNArticleDrafts.restore(file, saved.draft);
      sourceTextarea.value = saved.content; sourceTextarea.dispatchEvent(new Event('input', { bubbles: true }));
    }, FILE);
    await page.locator('#newDraftVersionBtn').click(); await page.waitForFunction(() => !SAVE_PENDING);
    assert.equal(await page.evaluate(() => DNArticleDrafts.localState(CURRENT_FILE).head), NEXT);
    assert.match(await source.inputValue(), /Verified production text/);
    assert.equal(await source.isEditable(), true);
    assert.equal(await page.evaluate(() => DIRTY), false);
    assert.match(await page.locator('#status').textContent(), /尚未上線/);
    await page.locator('#restoreDraftVersionBtn').click();
    await page.waitForFunction(() => DIRTY);
    assert.match(await source.inputValue(), /Previous local text/);
    assert.match(await source.inputValue(), /\/blog\/images\/example\//);
    assert.equal(await page.evaluate(() => DNArticleDrafts.localState(CURRENT_FILE).media.length), 1, 'new-version backup restores pending image bytes');
    assert.equal(await page.evaluate(() => DNArticleDrafts.localState(CURRENT_FILE).head), NEXT);
    assert.match(await page.locator('#status').textContent(), /版本不同/);
    for (const width of [390, 800, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const id of ['newDraftVersionBtn', 'restoreDraftVersionBtn']) {
        const box = await page.locator('#' + id).boundingBox();
        assert.ok(box && box.height >= 44 && box.x >= 0 && box.x + box.width <= width + 1, id + ' at ' + width);
      }
      if (options.screenshotDir) { fs.mkdirSync(options.screenshotDir, { recursive: true }); await page.screenshot({ path: path.join(options.screenshotDir, width + '.png'), fullPage: true }); }
    }
    assert.deepEqual(externalWrites, []); assert.equal(writes.length, 3);
    console.log('New-version UI passed: verified source, quota/receipt blocking, images/backup, typing preservation, explicit reload/restore, 390/800/1440, no main or collector writes');
  } finally { if (release) release(); await context.close(); }
};
