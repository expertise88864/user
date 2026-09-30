// Actual admin observation UI; all collectors, GitHub and API traffic isolated.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async function checkPublicationUI(browser, options = {}) {
  for (const width of [390, 800, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 1100 }, serviceWorkers: 'block' });
    const HEAD = 'a'.repeat(40), BASE = 'b'.repeat(40), BLOB = 'c'.repeat(40), MAIN = 'd'.repeat(40), NEXT = 'e'.repeat(40);
    const html = '<!doctype html><html lang="zh-Hant"><head><title>Fixture</title></head><body><div id="proseZh"><h1>文章測試</h1><p id="intro">保留原始編輯</p></div></body></html>';
    let head = HEAD, content = html, proofState = 'ci_failed', sameVersion = false, fail = false, pause = false, release;
    const writes = [], externalWrites = [], observations = [];
    try {
      const page = await context.newPage();
      await page.addInitScript(() => {
        sessionStorage.setItem('cd_gh_pat', 'fixture-only-not-a-real-token');
        sessionStorage.setItem('cd_gh_pat_exp', String(Date.now() + 600000));
      });
      page.on('dialog', dialog => dialog.accept());
      await page.route('**/*', async route => {
        const request = route.request(), url = new URL(request.url());
        if (url.origin === 'https://api.github.com') {
          if (request.method() !== 'GET') { externalWrites.push(url.href); return route.abort(); }
          return route.fulfill({ json: [] });
        }
        if (url.origin !== 'https://publication-admin.test') return route.abort();
        if (url.pathname === '/api/admin/login') return route.fulfill({ json: { ok: true, login: 'expertise88864' } });
        if (url.pathname === '/api/admin/article-draft') {
          if (request.method() === 'GET') {
            if (url.searchParams.get('mode') === 'list') return route.fulfill({ json: { drafts: [], nextOffset: null, unsupportedRefs: 0 } });
            const file = url.searchParams.get('file');
            if (url.searchParams.get('mode') === 'publication') {
              observations.push(file);
              const deployed = ['live', 'live_noindex'].includes(proofState);
              const proof = { mainSha: MAIN, mainBlobSha: sameVersion ? BLOB : BASE, matchesLoadedVersion: sameVersion,
                sourceIndexable: proofState !== 'live_noindex', ciVerified: deployed || proofState.startsWith('deployment_'),
                deploymentVerified: deployed, published: proofState === 'live' && sameVersion,
                state: proofState, checks: [], observedAt: new Date().toISOString() };
              const data = { file, head, baseSha: BASE, blobSha: BLOB, publication: proof };
              if (pause) { pause = false; await new Promise(resolve => { release = resolve; }); }
              if (fail) return route.fulfill({ status: 503, json: { error: 'publication_unavailable' } });
              return route.fulfill({ json: data });
            }
            return route.fulfill({ json: { file, head, baseSha: BASE, blobSha: BLOB,
              content: file === 'blog/other.html' ? html.replace('保留原始編輯', '另一篇原稿') : content,
              media: [], legacy: false, conflict: false, request: null } });
          }
          const data = request.postDataJSON(); writes.push(data);
          assert.equal(data.action, undefined); assert.equal(data.expectedHead, HEAD);
          head = NEXT; content = data.content;
          return route.fulfill({ json: { file: data.file, head, baseSha: BASE, blobSha: BLOB,
            status: 'cloud_draft', verified: true, published: false } });
        }
        if (request.method() !== 'GET') { externalWrites.push(url.href); return route.abort(); }
        const root = process.cwd(), file = path.resolve(root, '.' + url.pathname);
        if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return route.fulfill({ status: 404, body: '' });
        return route.fulfill({ contentType: file.endsWith('.js') ? 'application/javascript' : file.endsWith('.css') ? 'text/css' : 'text/html', body: fs.readFileSync(file) });
      });
      await page.goto('https://publication-admin.test/admin.html');
      await page.waitForFunction(() => !!window.DNEditorDraftBridge);
      assert.equal(await page.evaluate(() => loadFile('blog/example.html')), true);
      const frame = page.frameLocator('iframe.editor');
      await frame.locator('#proseZh[data-cd-editable]').waitFor();
      const label = page.locator('#websitePublicationState'), button = page.locator('#checkPublicationBtn');
      const initial = await page.evaluate(() => ({ sha: CURRENT_SHA, html: getCurrentEditorContent(), head: DNArticleDrafts.localState(CURRENT_FILE).head }));
      async function check(state, expected) {
        proofState = state;
        await button.click();
        await page.waitForFunction(() => !document.getElementById('checkPublicationBtn').disabled);
        assert.ok((await label.innerText()).includes(expected), state + ': ' + await label.innerText());
      }
      await check('ci_failed', '驗證未通過');
      await check('deployment_failed', '部署未成功');
      await check('live', '目前草稿尚未上線');
      sameVersion = true;
      await check('live', '已正式上線');
      await check('live_noindex', '不列入公開索引');
      assert.deepEqual(await page.evaluate(() => ({ sha: CURRENT_SHA, html: getCurrentEditorContent(), head: DNArticleDrafts.localState(CURRENT_FILE).head })), initial);
      fail = true; await check('live', '尚未確認'); fail = false;
      assert.equal(await page.evaluate(() => DIRTY), false, 'readonly observations do not dirty a mounted view');
      await frame.locator('#intro').evaluate(node => { node.firstChild.data += ' 未觸發事件修改'; });
      await page.waitForFunction(() => DIRTY);
      const autosaved = await page.evaluate(() => { autosave(); return JSON.parse(localStorage.getItem(autosaveKey(CURRENT_FILE))).content; });
      assert.ok(autosaved.includes('未觸發事件修改'), 'DOM changes without input still receive local recovery protection');

      proofState = 'live'; pause = true; await button.click();
      await page.waitForFunction(() => document.getElementById('checkPublicationBtn').disabled);
      while (!release) await new Promise(resolve => setTimeout(resolve, 20));
      await frame.locator('#intro').click(); await page.keyboard.press('End'); await page.keyboard.type(' 核對中繼續編輯');
      release(); release = null;
      await page.waitForFunction(() => !document.getElementById('checkPublicationBtn').disabled);
      const observedText = await label.innerText();
      const editedState = await page.evaluate(() => ({ dirty: DIRTY, html: getCurrentEditorContent(), file: CURRENT_FILE, savePending: SAVE_PENDING, loadPending: EDITOR_LOADING }));
      assert.ok(observedText.includes('本機的新編輯尚未保存'), JSON.stringify({ observedText, editedState }));
      assert.ok((await page.evaluate(() => getCurrentEditorContent())).includes('核對中繼續編輯'));
      assert.equal(await page.evaluate(() => DNArticleDrafts.localState(CURRENT_FILE).head), HEAD);

      pause = true; await button.click();
      while (!release) await new Promise(resolve => setTimeout(resolve, 20));
      assert.equal(await page.evaluate(() => loadFile('blog/other.html')), true);
      release(); release = null;
      await frame.locator('#intro').waitFor();
      await page.waitForFunction(() => !document.getElementById('checkPublicationBtn').disabled);
      assert.ok((await label.innerText()).includes('尚未核對'));
      assert.ok((await page.evaluate(() => getCurrentEditorContent())).includes('另一篇原稿'));

      pause = true; await button.click();
      while (!release) await new Promise(resolve => setTimeout(resolve, 20));
      await page.evaluate(() => auth.setPat('changed-fixture-token'));
      release(); release = null;
      await page.waitForFunction(() => !document.getElementById('checkPublicationBtn').disabled);
      assert.ok((await label.innerText()).includes('尚未核對'));
      assert.deepEqual(writes, [], 'all publication observations are read-only');

      pause = true; await button.click();
      while (!release) await new Promise(resolve => setTimeout(resolve, 20));
      await page.evaluate(() => DNEditorDraftBridge.save());
      release(); release = null;
      await page.waitForFunction(() => !document.getElementById('checkPublicationBtn').disabled);
      assert.equal(await page.evaluate(() => DNArticleDrafts.localState(CURRENT_FILE).head), NEXT);
      assert.ok((await label.innerText()).includes('尚未核對'), 'old observation cannot overwrite a newer saved revision');
      assert.equal(writes.length, 1, 'only the explicit draft save writes, never observation');
      assert.deepEqual(externalWrites, [], 'no direct GitHub/main writes');
      const notice = await page.locator('#websitePublicationNotice').boundingBox();
      assert.ok(notice.width > 0 && notice.x + notice.width <= width + 1, 'publication notice stays within viewport');
      assert.ok((await button.boundingBox()).height >= 44, 'publication check remains a usable touch target');
      if (options.screenshotDir) {
        fs.mkdirSync(options.screenshotDir, { recursive: true });
        await page.screenshot({ path: path.join(options.screenshotDir, width + '.png') });
      }
      console.log('Actual publication UI passed at ' + width + 'px: state, DOM recovery, stale article/auth/save; observation/main writes=0, explicit draft save=1');
    } finally { if (release) release(); await context.close(); }
  }
};
