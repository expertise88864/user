// Actual CMS bridge with isolated collectors/repository/API. No real PAT or writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
module.exports = async function checkEditorDraftBridge(browser) {
  const BASE = 'a'.repeat(40), HEAD = 'b'.repeat(40), BLOB = 'c'.repeat(40);
  const OLD = 'd'.repeat(40);
  const NEW_HEAD = 'e'.repeat(40), NEW_BLOB = 'f'.repeat(40);
  const html = '<!doctype html><html lang="zh-Hant"><head><title>Draft fixture</title></head><body><main><h1>Fixture &lt;img src=x onerror=&quot;window.REQUEST_INJECTED=1&quot;&gt;</h1><div id="proseZh"><p>Original text</p></div></main></body></html>';
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block' });
  const writes = [], externalWrites = []; let release, remoteHead = null, acceptedHtml = html;
  let conflict = false, pauseNextLoad = false, loadRelease, newDraft = null; const media = new Map();
  let publication = null, pauseNextRequest = false, requestRelease, requestSerial = 0;
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
        if (request.method() !== 'GET') { externalWrites.push(request.url()); return route.abort(); }
        if (url.pathname.endsWith('/commits')) return route.fulfill({ status: 200, json: [{ sha: OLD,
          commit: { message: 'Older fixture', author: { date: '2026-09-01T00:00:00Z' } } }] });
        if (url.pathname.endsWith('/contents/blog/example.html') && url.searchParams.get('ref') === OLD) return route.fulfill({ status: 200, json: {
          content: Buffer.from(html.replace('Original text', 'Historical text')).toString('base64'), sha: OLD } });
        return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      }
      if (url.origin !== 'https://editor-draft.test') return route.abort();
      if (url.pathname === '/api/admin/login') return route.fulfill({ status: 200, json: { ok: true, login: 'expertise88864' } });
      if (url.pathname === '/api/admin/article-draft') {
        if (request.method() === 'GET') {
          if (url.searchParams.get('mode') === 'list') return route.fulfill({ status: 200, json: { drafts: [
            ...(remoteHead ? [{ file: 'blog/example.html', head: remoteHead, legacy: false }] : []),
            ...(newDraft ? [{ file: 'blog/new-fixture.html', head: NEW_HEAD, legacy: false }] : []),
          ], nextOffset: null, unsupportedRefs: 0 } });
          if (url.searchParams.get('file') === 'blog/new-fixture.html') return route.fulfill({ status: 200, json: {
            file: 'blog/new-fixture.html', head: newDraft ? NEW_HEAD : null, baseSha: null, blobSha: newDraft ? NEW_BLOB : null,
            content: newDraft && newDraft.content, metadata: newDraft && newDraft.metadata, media: [], legacy: false, conflict: false,
          } });
          if (pauseNextLoad && url.searchParams.get('mode') !== 'status') {
            pauseNextLoad = false;
            await new Promise(resolve => { loadRelease = resolve; });
          }
          return route.fulfill({ status: 200, json: {
          file: 'blog/example.html', head: remoteHead, baseSha: BASE, blobSha: remoteHead ? BLOB : BASE,
          content: acceptedHtml, media: [...media.values()], assets: [], legacy: false, conflict: false, status: remoteHead ? 'cloud_draft' : 'published_base', request: publication,
          } });
        }
        const body = request.postDataJSON(); writes.push(body);
        if (body.file === 'blog/new-fixture.html') {
          assert.equal(body.expectedHead, null); assert.equal(body.baseSha, null); assert.ok(!newDraft);
          newDraft = body;
          return route.fulfill({ status: 200, json: { file: body.file, head: NEW_HEAD, blobSha: NEW_BLOB, baseSha: null,
            status: 'cloud_draft', verified: true, published: false, metadata: body.metadata, branch: 'drafts/new-fixture' } });
        }
        assert.equal(body.expectedHead, remoteHead);
        if (conflict) return route.fulfill({ status: 409, json: { error: 'draft_conflict' } });
        if (body.action) {
          assert.equal(body.expectedBlob, BLOB); assert.equal(body.content, undefined);
          assert.equal(body.action === 'unpublish' || body.action === 'cancel' ? body.confirmed : body.contentApproved, true);
          if (pauseNextRequest) { pauseNextRequest = false; await new Promise(resolve => { requestRelease = resolve; }); }
          remoteHead = (++requestSerial).toString(16).padStart(40, '0');
          publication = body.action === 'cancel' ? null : { action: body.action, blobSha: BLOB,
            status: { review: 'awaiting_review', schedule: 'schedule_requested', unpublish: 'unpublish_requested' }[body.action],
            scheduledAt: body.scheduledAt || null, requestedAt: new Date().toISOString() };
          return route.fulfill({ status: 200, json: { file: body.file, head: remoteHead, baseSha: BASE, blobSha: BLOB,
            request: publication, verified: true, published: false } });
        }
        await new Promise(resolve => { release = resolve; });
        remoteHead = HEAD; acceptedHtml = body.content; publication = null;
        for (const item of body.media) media.set(item.path, item);
        return route.fulfill({ status: 200, json: { file: body.file, head: HEAD, blobSha: BLOB, baseSha: BASE,
          status: 'cloud_draft', verified: true, published: false, branch: 'drafts/example' } });
      }
      if (request.method() !== 'GET') return route.abort();
      const root = process.cwd(), file = path.resolve(root, '.' + url.pathname);
      if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return route.fulfill({ status: 404, body: '' });
      const contentType = file.endsWith('.js') ? 'application/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.html') ? 'text/html' : 'application/octet-stream';
      return route.fulfill({ status: 200, contentType, body: fs.readFileSync(file) });
    });
    await page.goto('https://editor-draft.test/admin.html');
    await page.waitForFunction(() => !!window.DNEditorDraftBridge);
    assert.equal(await page.evaluate(() => loadFile('blog/example.html')), true);
    const editor = page.frameLocator('iframe.editor').locator('[data-cd-editable="1"]');
    await editor.waitFor(); await editor.click(); await editor.press('End'); await editor.pressSequentially(' edited');
    const gif = Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64');
    await page.locator('#imageInput').setInputFiles({ name: 'fixture.gif', mimeType: 'image/gif', buffer: gif });
    await editor.locator('img').waitFor();
    assert.match(await editor.locator('img').getAttribute('src'), /^data:image\/gif;base64,/);
    assert.equal(writes.length, 0, 'image staging must not write a branch');
    await page.evaluate(() => { DIRTY = true; autosave(); });
    const local = await page.evaluate(() => JSON.parse(localStorage.getItem('cd_admin_draft_blog/example.html')));
    assert.equal(local.draft.media.length, 1); assert.ok(local.content.includes('/blog/images/example/'));
    assert.ok(!local.content.includes('src="data:'), 'recovery content retains canonical image path');
    pauseNextLoad = true;
    const loading = page.evaluate(() => loadFile('blog/example.html'));
    await page.waitForFunction(() => EDITOR_LOADING);
    for (let i = 0; i < 50 && !loadRelease; i++) await page.waitForTimeout(10);
    assert.ok(loadRelease);
    await editor.click(); await editor.press('End'); await editor.pressSequentially(' while loading');
    loadRelease(); assert.equal(await loading, true);
    const outgoing = await page.evaluate(() => JSON.parse(localStorage.getItem('cd_admin_draft_blog/example.html')));
    assert.ok(outgoing.content.includes('while loading'), 'typing during a pending load must remain recoverable');
    assert.equal(outgoing.draft.media.length, 1, 'pending load must retain the outgoing image mapping');
    assert.ok(outgoing.content.includes('/blog/images/example/')); assert.ok(!outgoing.content.includes('src="data:'));
    await page.locator('#draftBanner').waitFor({ state: 'visible' });
    await page.evaluate(() => {
      const digest = crypto.subtle.digest.bind(crypto.subtle);
      crypto.subtle.digest = (...args) => new Promise((resolve, reject) => {
        window.releaseRecoveryDigest = () => { crypto.subtle.digest = digest; digest(...args).then(resolve, reject); };
      });
    });
    await page.locator('#draftRestoreBtn').click();
    await page.waitForFunction(() => restoringAutosave && typeof window.releaseRecoveryDigest === 'function');
    await editor.click(); await editor.press('End'); await editor.pressSequentially(' edited during recovery');
    await page.evaluate(() => window.releaseRecoveryDigest());
    await page.waitForFunction(() => !restoringAutosave);
    assert.ok((await editor.textContent()).includes('edited during recovery'), 'validation must not overwrite intervening typing');
    assert.equal((await page.evaluate(() => window.DNArticleDrafts.localState(CURRENT_FILE))).media.length, 0, 'rejected recovery must not install its first image');
    assert.ok(await page.locator('#draftBanner').isVisible(), 'original recovery remains available after a stale validation');
    assert.equal(writes.length, 0);
    await page.locator('#draftRestoreBtn').click();
    await page.waitForFunction(() => !restoringAutosave && document.getElementById('draftBanner').style.display === 'none').catch(async error => {
      console.error('Recovery fixture state', await page.evaluate(() => ({ status: document.getElementById('status')?.textContent,
        restoring: restoringAutosave, savePending: SAVE_PENDING, loading: EDITOR_LOADING,
        file: CURRENT_FILE, draft: window.DNArticleDrafts.localState(CURRENT_FILE) })));
      throw error;
    });
    await editor.waitFor();
    assert.ok((await editor.textContent()).includes('while loading'));
    await editor.locator('img').waitFor();
    assert.match(await editor.locator('img').getAttribute('src'), /^data:image\/gif;base64,/);
    await page.locator('#saveBtn').click();
    await page.waitForFunction(() => SAVE_PENDING);
    for (let i = 0; i < 50 && !release; i++) await page.waitForTimeout(10);
    assert.ok(release); assert.equal(writes[0].expectedHead, null); assert.equal(writes[0].media.length, 1);
    await editor.click(); await editor.press('End'); await editor.pressSequentially(' during save');
    release(); await page.waitForFunction(() => !SAVE_PENDING);
    assert.equal(await page.evaluate(() => DIRTY), true, 'later typing must remain dirty');
    const recovery = await page.evaluate(() => JSON.parse(localStorage.getItem('cd_admin_draft_blog/example.html')));
    assert.ok(recovery.content.includes('during save')); assert.equal(recovery.draft.head, HEAD);
    assert.ok((await editor.textContent()).includes('during save'), 'save must not remount/replace live editor');
    conflict = true;
    await page.locator('#draftBtn').click(); await page.waitForFunction(() => !SAVE_PENDING);
    assert.equal(writes.length, 2); assert.equal(writes[1].expectedHead, HEAD); assert.equal(writes[1].media.length, 0);
    assert.equal(await page.evaluate(() => DIRTY), true); assert.equal(await page.evaluate(() => CURRENT_SHA), BLOB);
    assert.ok(await page.evaluate(() => !!localStorage.getItem('cd_admin_draft_blog/example.html')));
    const blocked = await page.evaluate(async () => { try { await gh('PUT', 'contents/blog/example.html', {}); return false; } catch (_) { return true; } });
    assert.equal(blocked, true); assert.deepEqual(externalWrites, []);
    await page.reload(); await page.waitForFunction(() => !!window.DNEditorDraftBridge);
    assert.equal(await page.evaluate(() => loadFile('blog/example.html')), true);
    await page.locator('#draftBanner').waitFor({ state: 'visible' });
    await page.locator('#draftRestoreBtn').click();
    await page.waitForFunction(() => !restoringAutosave && document.getElementById('draftBanner').style.display === 'none');
    const restored = page.frameLocator('iframe.editor').locator('[data-cd-editable="1"]');
    await restored.waitFor();
    assert.ok((await restored.textContent()).includes('during save'), 'local edits must restore after a reload');
    await restored.locator('img').waitFor();
    assert.match(await restored.locator('img').getAttribute('src'), /^data:image\/gif;base64,/);
    assert.equal(await restored.locator('img').evaluate(img => img.naturalWidth), 1, 'unpublished cloud images must survive reload and local restoration');
    assert.ok(await page.evaluate(() => getCurrentEditorContent().includes('/blog/images/example/')));
    await page.locator('.ax-tabs button[data-tab="version"]').click();
    await page.locator('#axVersionLoad').click(); await page.locator('#axVersionList .ax-version').waitFor();
    await page.locator('#axVersionList .ax-version').click(); await page.locator('#restoreBtn').waitFor();
    assert.equal(writes.length, 2, 'version selection only opens a comparison');
    assert.ok((await restored.textContent()).includes('during save'));
    await page.locator('#restoreBtn').click();
    await page.waitForFunction(() => getCurrentEditorContent().includes('Historical text'));
    assert.equal(writes.length, 2, 'loading historical content must not write GitHub or draft API');
    assert.equal(await page.evaluate(() => CURRENT_SHA), BLOB, 'history must preserve the actual loaded CAS revision');
    assert.equal(await page.evaluate(() => DIRTY), true);
    conflict = false; release = null;
    await page.locator('#saveBtn').click(); await page.waitForFunction(() => SAVE_PENDING);
    for (let i = 0; i < 50 && !release; i++) await page.waitForTimeout(10);
    assert.ok(release); assert.equal(writes[2].expectedHead, HEAD); assert.ok(writes[2].content.includes('Historical text'));
    release(); await page.waitForFunction(() => !SAVE_PENDING);
    assert.deepEqual(externalWrites, []);
    await page.locator('#reviewRequestBtn').click();
    assert.ok((await page.locator('#requestArticleTitle').textContent()).includes('<img'));
    assert.equal(await page.locator('#requestArticleTitle img').count(), 0);
    assert.equal(await page.evaluate(() => window.REQUEST_INJECTED), undefined, 'author title markup remains inert text in the request dialog');
    await page.locator('#requestConfirm').click();
    assert.match(await page.locator('#requestError').textContent(), /請先勾選/);
    assert.equal(writes.length, 3, 'no request without explicit author confirmation');
    await page.evaluate(() => { editFrame.contentDocument.querySelector('[data-cd-editable] p').append(' changed during confirmation'); DIRTY = true; });
    await page.locator('#requestApproval').check(); await page.locator('#requestConfirm').click();
    assert.match(await page.locator('#requestError').textContent(), /已改變/);
    assert.equal(writes.length, 3, 'confirmation cannot switch to a newer unsaved version');
    await page.locator('#requestClose').click(); release = null;
    await page.locator('#saveBtn').click(); await page.waitForFunction(() => SAVE_PENDING);
    for (let i = 0; i < 50 && !release; i++) await page.waitForTimeout(10);
    assert.ok(release); release(); await page.waitForFunction(() => !SAVE_PENDING);
    pauseNextRequest = true; await page.locator('#reviewRequestBtn').click(); await page.locator('#requestApproval').check();
    await page.locator('#requestConfirm').click(); await page.waitForFunction(() => SAVE_PENDING);
    for (let i = 0; i < 50 && !requestRelease; i++) await page.waitForTimeout(10);
    assert.ok(requestRelease); assert.equal(await page.locator('#requestClose').isDisabled(), true);
    await page.evaluate(() => { editFrame.contentDocument.querySelector('[data-cd-editable] p').append(' typed while requesting'); DIRTY = true; });
    requestRelease(); await page.waitForFunction(() => !SAVE_PENDING);
    assert.equal(writes.length, 5); assert.equal(writes[4].action, 'review');
    assert.match(await page.locator('#publicationState').textContent(), /待審核/);
    assert.equal(await page.evaluate(() => DIRTY), true);
    const requestRecovery = await page.evaluate(() => JSON.parse(localStorage.getItem('cd_admin_draft_blog/example.html')));
    assert.ok(requestRecovery.content.includes('typed while requesting')); assert.equal(requestRecovery.draft.head, remoteHead);
    const requestedHead = remoteHead; release = null; await page.locator('#saveBtn').click();
    await page.waitForFunction(() => SAVE_PENDING);
    for (let i = 0; i < 50 && !release; i++) await page.waitForTimeout(10);
    assert.ok(release); assert.equal(writes[5].expectedHead, requestedHead); release(); await page.waitForFunction(() => !SAVE_PENDING);
    assert.match(await page.locator('#publicationState').textContent(), /尚未送審/);
    await page.locator('#scheduleBtn').click(); await page.locator('#requestApproval').check(); await page.locator('#requestConfirm').click();
    await page.locator('#requestDialogTitle').waitFor({ state: 'hidden' });
    assert.equal(writes[6].action, 'schedule'); assert.ok(Number.isFinite(Date.parse(writes[6].scheduledAt)));
    assert.match(await page.locator('#publicationState').textContent(), /排程申請已保存/);
    await page.locator('#cancelRequestBtn').click(); await page.locator('#requestApproval').check(); await page.locator('#requestConfirm').click();
    await page.locator('#requestDialogTitle').waitFor({ state: 'hidden' });
    assert.equal(writes[7].action, 'cancel'); assert.equal(await page.locator('#cancelRequestBtn').isDisabled(), true);
    await page.locator('#unpublishBtn').click(); await page.locator('#requestApproval').check(); await page.locator('#requestConfirm').click();
    await page.locator('#requestDialogTitle').waitFor({ state: 'hidden' }); assert.equal(writes[8].action, 'unpublish');
    assert.match(await page.locator('#publicationState').textContent(), /下架申請已保存/);
    assert.equal(await page.evaluate(() => loadFile('blog/example.html')), true);
    assert.match(await page.locator('#publicationState').textContent(), /下架申請已保存/);
    await page.locator('#reviewRequestBtn').click();
    assert.equal(await page.evaluate(() => loadFile('blog/example.html')), true);
    await page.locator('#requestApproval').check(); await page.locator('#requestConfirm').click();
    assert.match(await page.locator('#requestError').textContent(), /已改變/);
    assert.equal(writes.length, 9, 'reloaded editor identity invalidates the old request dialog');
    await page.locator('#requestClose').click();
    assert.deepEqual(externalWrites, []);
    const beforeNewArticle = writes.length;
    await page.locator('#newFileName').fill('new-fixture'); await page.locator('#newFileBtn').click();
    await page.locator('#wizType').selectOption('overview');
    await page.locator('#wizTitle').fill('新文章測試'); await page.locator('#wizTitleEn').fill('New article fixture');
    await page.locator('#wizTag').fill('測試'); await page.locator('#wizTagEn').fill('Fixture');
    await page.locator('#wizDesc').fill('隔離編輯器測試內容，不會上傳或發布。');
    await page.locator('#wizCreate').click();
    await page.waitForFunction(() => CURRENT_FILE === 'blog/new-fixture.html' && !EDITOR_LOADING && !SAVE_PENDING);
    assert.equal(writes.length, beforeNewArticle + 1); assert.equal(newDraft.metadata.title_en, 'New article fixture'); assert.equal(newDraft.metadata.cat, 'rx');
    assert.match(await page.locator('.file-item[data-path="blog/new-fixture.html"]').textContent(), /雲端草稿/);
    assert.equal(await page.evaluate(() => CURRENT_SHA), NEW_BLOB);
    await page.locator('#newFileName').fill('new-fixture'); await page.locator('#newFileBtn').click();
    await page.locator('#wizType').selectOption('overview');
    await page.locator('#wizTitle').fill('重複文章'); await page.locator('#wizTitleEn').fill('Duplicate');
    await page.locator('#wizTag').fill('測試'); await page.locator('#wizTagEn').fill('Fixture'); await page.locator('#wizDesc').fill('重複網址測試');
    await page.locator('#wizCreate').click(); await page.waitForFunction(() => !SAVE_PENDING);
    assert.match(await page.locator('#wizStatus').textContent(), /已有正式文章或雲端草稿/); assert.equal(writes.length, beforeNewArticle + 1);
    assert.equal(await page.locator('#wizTitle').inputValue(), '重複文章', 'failed creation retains wizard inputs');
    await page.locator('#wizCancel').click(); assert.deepEqual(externalWrites, []);
    console.log('CMS draft bridge: images/recovery/save typing/conflict/history/new article; version-bound confirmation, request typing/recovery, schedule/cancel/unpublish/status and stale dialogs; no direct writes passed');
  } finally { if (release) release(); if (loadRelease) loadRelease(); if (requestRelease) requestRelease(); await context.close(); }
};
