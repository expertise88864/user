// Actual private admin HTML/scripts/buttons; all transport intercepted before
// egress. Fixture cookie/login and Git responses never contact real services.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const hash = value => crypto.createHash('sha1').update(value).digest('hex');
const clone = value => JSON.parse(JSON.stringify(value));
const settings = () => ({version: 1, legacyPicks: true, font: {bodyFont: '', headFont: '', bodySize: ''}, order: [], picks: ['alpha']});
const titles = ['第一篇文章', '第二篇 <img src="https://private.invalid/fixture">文章', '第三篇文章'];
const initial = () => ({main: hash('main'), head: null, blobSha: hash('source'), baseSha: hash('source'), catalogSha: hash('catalog'),
  mainBlobSha: hash('source'), mainCatalogSha: hash('catalog'), sourceSettings: settings(), settings: settings(),
  articles: ['alpha', 'beta', 'gamma'].map((slug, index) => ({slug, title: titles[index], title_en: 'Article ' + slug})),
  conflict: false, status: 'source_base', request: null, manifestRecord: null, published: false, deploymentVerified: false});
async function fixture(browser, width, scenario) {
  const context = await browser.newContext({viewport: {width, height: 1000}, locale: 'zh-TW', serviceWorkers: 'block'});
  const page = await context.newPage(), errors = [], calls = [], blocked = [];
  const h = {page, context, errors, calls, blocked, latest: initial(), mode: '', sequence: 0, pending: null};
  if (scenario === 'request') { h.latest.head = hash('saved draft'); h.latest.status = 'cloud_draft'; }
  if (scenario.startsWith('new-cycle')) {
    h.latest.head = hash('saved draft'); h.latest.blobSha = hash('draft source'); h.latest.settings.font.bodySize='18px';
    h.latest.conflict=scenario==='new-cycle-conflict'; h.latest.status=h.latest.conflict?'conflict':'cloud_draft';
  }
  if(scenario.startsWith('catalog')) {
    h.latest.head=hash('old catalogue draft');h.latest.catalogSha=hash('old catalogue');h.latest.mainCatalogSha=hash('new catalogue');
    h.latest.settings.order=['gamma','alpha','beta'];h.latest.sourceSettings.legacyPicks=false;h.latest.sourceRequiresReview=true;
    h.latest.conflict=true;h.latest.status='conflict';
    h.latest.articles=h.latest.articles.filter(a=>a.slug!=='alpha').concat({slug:'delta',title:'新增文章',title_en:'New article'});
  }
  await page.addInitScript(() => {
    sessionStorage.setItem('cd_gh_pat', 'fixture-only'); sessionStorage.setItem('cd_gh_pat_exp', String(Date.now() + 600000));
    localStorage.setItem('cd_admin_settings_draft_font', JSON.stringify({version: 1, kind: 'font', bodyFont: '', headFont: '', bodySize: '17px'}));
  });
  page.on('pageerror', error => errors.push(error.message));
  page.on('dialog', dialog => dialog.accept());
  function respond(input) {
    assert.equal(input.expectedHead, h.latest.head, 'fixture enforces the loaded immutable head');
    const cycling=input.action==='new-version',reconciling=input.action==='reconcile-catalog';
    if (cycling) {
      assert.equal(input.blobSha,h.latest.blobSha);assert.equal(input.expectedMain,h.latest.main);
      assert.equal(input.expectedMainBlob,h.latest.mainBlobSha);assert.equal(input.expectedCatalog,h.latest.mainCatalogSha);assert.equal(input.confirmed,true);
    } else if(reconciling){assert.equal(input.blobSha,h.latest.blobSha);assert.equal(input.expectedMain,h.latest.main);
      assert.equal(input.expectedMainBlob,h.latest.mainBlobSha);assert.equal(input.expectedCatalog,h.latest.mainCatalogSha);assert.equal(input.confirmed,true);}
    else {assert.equal(input.baseSha, h.latest.baseSha); assert.equal(input.catalogSha, h.latest.catalogSha);}
    const before = clone(h.latest); h.latest = {...before, head: hash('draft-' + (++h.sequence)), verified: true};
    if (cycling) {
      h.latest.settings=clone(h.latest.sourceSettings);h.latest.blobSha=h.latest.mainBlobSha;h.latest.baseSha=h.latest.mainBlobSha;
      h.latest.catalogSha=h.latest.mainCatalogSha;h.latest.status='cloud_draft';h.latest.conflict=false;h.latest.request=null;
      h.latest.manifestRecord={baseMain:h.latest.main};
    } else if(reconciling) {
      h.latest.settings=clone(input.settings);h.latest.blobSha=hash(JSON.stringify(input.settings));h.latest.baseSha=h.latest.mainBlobSha;
      h.latest.catalogSha=h.latest.mainCatalogSha;h.latest.status='cloud_draft';h.latest.conflict=false;h.latest.request=null;
      h.latest.manifestRecord={baseMain:h.latest.main};
    } else if (input.kind) {
      h.latest.settings[input.kind] = clone(input.values); h.latest.blobSha = hash(JSON.stringify(h.latest.settings));
      if (input.kind === 'picks') { h.latest.settings.legacyPicks = false; h.latest.blobSha = hash(JSON.stringify(h.latest.settings)); }
      h.latest.status = 'cloud_draft'; h.latest.request = null;
    } else if (input.action === 'request-publication') {
      assert.equal(input.settingsApproved, true); assert.equal(input.blobSha, before.blobSha);
      h.latest.request = {draftHead: before.head, requestHead: h.latest.head, blobSha: before.blobSha}; h.latest.status = 'requested';
    } else {
      assert.equal(input.action, 'cancel-request'); h.latest.request = null; h.latest.status = 'cloud_draft';
    }
    return clone(h.latest);
  }
  await page.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin === 'https://api.github.com') return route.fulfill({json: []});
    if (url.origin !== 'https://settings-editor.test') { blocked.push(url.hostname); return route.abort(); }
    if (url.pathname === '/api/admin/login' || url.pathname === '/api/admin/logout') return route.fulfill({json: {ok: true}});
    if (url.pathname === '/api/admin/site-settings') {
      assert.equal(request.headers().authorization, undefined, 'settings channel must not resend PAT');
      assert.ok(!request.postData()?.includes('fixture-only'), 'settings body contains data only');
      const input = request.method() === 'POST' ? request.postDataJSON() : null;
      const observing = url.search === '?publication=1';
      calls.push({method: request.method(), input, observing});
      if (observing) {
        assert.equal(request.method(), 'GET'); assert.equal(request.postData(), null);
        const state = h.publicationState || 'live', data = clone(h.latest);
        data.publication = {kind:'site-settings',state,loadedHead:data.head,loadedBlobSha:data.blobSha,
          mainSha:data.main,mainBlobSha:data.mainBlobSha,settingsValidated:true,ciVerified:state==='live',
          deploymentVerified:state==='live',published:state==='live'&&data.mainBlobSha===data.blobSha,
          matchesLoadedVersion:data.mainBlobSha===data.blobSha,checks:[],deploymentId:201,observedAt:new Date().toISOString()};
        if(h.mode==='hold') {await new Promise(resolve=>h.pending=resolve);h.pending=null;}
        return route.fulfill({json:data});
      }
      if (!input) return route.fulfill({json: clone(h.latest)});
      if(h.mode==='retirement-pending'&&input.action==='reconcile-catalog') return route.fulfill({status:409,json:{error:'settings_receipt_not_retired'}});
      if(h.mode==='retirement-pending'&&input.action==='new-version') return route.fulfill({status:409,json:{error:'settings_receipt_not_retired'}});
      if (h.mode === 'hold') {
        const body = await new Promise(resolve => h.pending = () => resolve(respond(input)));
        h.pending = null; return route.fulfill({json: body});
      }
      const result = respond(input);
      if (h.mode === 'uncertain') { h.mode = ''; return route.abort(); }
      return route.fulfill({json: result});
    }
    if (url.pathname.startsWith('/api/')) return route.fulfill({status: 404, json: {error: 'isolated fixture'}});
    if (request.method() !== 'GET') return route.abort();
    const root = process.cwd(), file = path.resolve(root, '.' + url.pathname);
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return route.fulfill({status: 404, body: ''});
    const contentType = file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.html') ? 'text/html' : 'application/octet-stream';
    return route.fulfill({status: 200, contentType, body: fs.readFileSync(file)});
  });
  await page.goto('https://settings-editor.test/admin.html');
  await page.waitForFunction(() => document.getElementById('axPanel')?.dataset.settingsMounted === '1');
  await page.evaluate(() => {
    document.getElementById('patModal').style.display = 'none';
    CURRENT_FILE = 'blog/fixture.html';
    CURRENT_CONTENT = '<html lang="zh-Hant"><head><title>設定測試</title></head><body><main><article><p>原始測試文章，必須保留。</p></article></main></body></html>';
    document.getElementById('filePath').textContent = CURRENT_FILE; mountIframe(CURRENT_CONTENT);
    document.getElementById('axPanel').classList.remove('collapsed');
  });
  await page.locator('.ax-tabs button[data-tab="font"]').click();
  assert.equal(await page.locator('#axBodySize').isDisabled(), true, 'no implicit legacy restore or unverified cloud baseline');
  await page.locator('#axSettingsLoad').click();
  if(scenario==='new-cycle-conflict'||scenario.startsWith('catalog')) await page.waitForFunction(()=>!document.getElementById('axSettingsLoad').disabled&&document.getElementById('axSettingsStatus').textContent.includes('來源'));
  else await page.waitForFunction(() => !document.getElementById('axBodySize').disabled);
  h.originalArticle = await page.frameLocator('iframe.editor').locator('article').evaluate(node => node.outerHTML);
  return h;
}
async function waitCloud(h) {
  await h.page.waitForFunction(() => !document.getElementById('axSettingsLoad').disabled);
}
module.exports = async function checkSettingsPanel(browser, options = {}) {
  let cases = 0;
  const scenarios = options.scenarios || ['keyboard', 'save-typing', 'compare', 'uncertain', 'request', 'recovery-auth', 'migration',
    'observation','observation-typing','observation-auth','new-cycle','new-cycle-typing','new-cycle-blocked','new-cycle-conflict',
    'catalog','catalog-source','catalog-blocked'];
  for (const width of options.widths || [390, 800, 1440]) for (const scenario of scenarios) {
    const h = await fixture(browser, width, scenario), page = h.page;
    try {
      if(scenario.startsWith('catalog')) {
        const before=clone(h.latest);assert.equal(await page.locator('#axSettingsReconcile').isDisabled(),false);
        assert.equal(await page.locator('#axSettingsExport').isDisabled(),false);
        await page.locator('#axSettingsReconcile').click();assert.match(await page.locator('dialog').textContent(),/alpha/);
        assert.match(await page.locator('dialog').textContent(),/新增文章/);assert.equal(await page.locator('#axSettingsSubmitCatalog').isDisabled(),true);
        await page.keyboard.press('Escape');await page.locator('dialog').waitFor({state:'detached'});
        assert.equal(await page.evaluate(()=>document.activeElement.id),'axSettingsReconcile');
        assert.equal(h.calls.filter(c=>c.method==='POST').length,0);assert.deepEqual(h.latest,before);
        await page.locator('#axSettingsReconcile').click();
        if(scenario==='catalog-source')await page.locator('input[name="axSettingsCatalogBase"][value="source"]').check();
        await page.locator('#axSettingsCatalogApproval').check();assert.equal(await page.locator('#axSettingsSubmitCatalog').isDisabled(),true,'no invented replacement recommendation');
        await page.locator('[data-catalog-pick="beta"]').check();assert.equal(await page.locator('#axSettingsCatalogApproval').isChecked(),false);
        await page.locator('#axSettingsCatalogApproval').check();
        assert.ok(await page.locator('dialog').evaluate(n=>n.getBoundingClientRect().width<=innerWidth-16));
        if(scenario==='catalog-blocked')h.mode='retirement-pending';
        await page.locator('#axSettingsSubmitCatalog').click();await page.locator('dialog').waitFor({state:'detached'});await waitCloud(h);
        if(scenario==='catalog-blocked'){assert.deepEqual(h.latest,before);assert.match(await page.locator('#axSettingsStatus').textContent(),/尚未完成封存/);}
        else{assert.equal(h.latest.conflict,false);assert.deepEqual(h.latest.settings.picks,['beta']);assert.equal(h.latest.settings.legacyPicks,false);
          assert.deepEqual(h.latest.settings.order,scenario==='catalog-source'?[]:['gamma','beta','delta']);
          assert.equal(await page.locator('#axFontApply').isDisabled(),false);assert.equal(await page.locator('#axSettingsRequest').isDisabled(),false);}
      }
      if(scenario.startsWith('new-cycle')) {
        const oldHead=h.latest.head;
        assert.equal(await page.locator('#axSettingsNewVersion').isDisabled(),true);
        await page.locator('#axSettingsPublication').click();await waitCloud(h);
        assert.equal(await page.locator('#axSettingsNewVersion').isDisabled(),false);
        await page.locator('#axSettingsNewVersion').click();
        assert.match(await page.locator('dialog').textContent(),/舊版會保留/);
        assert.match(await page.locator('dialog').textContent(),/上次核對的正式網站設定/);
        assert.equal(await page.locator('#axSettingsCreateNewVersion').isDisabled(),true);
        await page.keyboard.press('Escape');await page.locator('dialog').waitFor({state:'detached'});
        assert.equal(await page.evaluate(()=>document.activeElement.id),'axSettingsNewVersion');
        assert.equal(h.calls.filter(call=>call.method==='POST').length,0);
        await page.locator('#axSettingsNewVersion').click();await page.locator('#axSettingsNewVersionApproval').check();
        if(scenario==='new-cycle-typing')h.mode='hold';
        if(scenario==='new-cycle-blocked')h.mode='retirement-pending';
        await page.locator('#axSettingsCreateNewVersion').click();
        if(scenario==='new-cycle-typing') {
          for(let i=0;i<50&&!h.pending;i++)await page.waitForTimeout(10);assert.ok(h.pending);
          // The modal holds focus; legacy programmatic changes remain protected.
          await page.evaluate(()=>{const select=document.getElementById('axBodySize');select.value='17px';select.dispatchEvent(new Event('change',{bubbles:true}));});
          h.mode='';h.pending();
        }
        await waitCloud(h);await page.locator('dialog').waitFor({state:'detached'});
        if(scenario==='new-cycle-blocked') {
          assert.equal(h.latest.head,oldHead);assert.match(await page.locator('#axSettingsStatus').textContent(),/證據尚未完成封存/);
          assert.equal(await page.locator('#axBodySize').inputValue(),'18px');
        } else {
          assert.notEqual(h.latest.head,oldHead);assert.equal(h.latest.settings.font.bodySize,'');
          assert.equal(await page.locator('#axBodySize').inputValue(),scenario==='new-cycle-typing'?'17px':'');
          assert.match(await page.locator('#axSettingsStatus').textContent(),scenario==='new-cycle-typing'?/後的畫面修改/:/新版雲端草稿/);
          assert.equal(h.latest.published,false);
        }
        assert.equal(h.calls.filter(call=>call.method==='POST').length,1);
        assert.equal(h.calls.find(call=>call.method==='POST').input.action,'new-version');
      }
      if (scenario === 'observation') {
        await page.locator('#axSettingsPublication').focus(); await page.keyboard.press('Enter'); await waitCloud(h);
        assert.match(await page.locator('#axSettingsPublicationStatus').textContent(),/確認已上線/);
        h.publicationState='ci_failed'; await page.locator('#axSettingsPublication').click(); await waitCloud(h);
        assert.match(await page.locator('#axSettingsPublicationStatus').textContent(),/未全部通過/);
        await page.locator('#axBodySize').selectOption('18px');
        assert.equal(await page.locator('#axSettingsPublication').isDisabled(),true);
        assert.match(await page.locator('#axSettingsPublicationStatus').textContent(),/尚未確認/);
        assert.equal(h.calls.filter(call=>call.method==='POST').length,0);
        assert.equal(h.calls.filter(call=>call.observing).length,2);
      }
      if (['observation-typing','observation-auth'].includes(scenario)) {
        h.mode='hold'; await page.locator('#axSettingsPublication').click();
        for(let i=0;i<50&&!h.pending;i++) await page.waitForTimeout(10);
        assert.ok(h.pending);
        if(scenario==='observation-typing') await page.locator('#axBodySize').selectOption('18px');
        else await page.evaluate(()=>window.cdAdminAuth.clearPat());
        h.mode=''; h.pending(); await waitCloud(h);
        assert.match(await page.locator('#axSettingsPublicationStatus').textContent(),/尚未確認/);
        assert.match(await page.locator('#axSettingsStatus').textContent(),scenario==='observation-typing'?/期間版本已變更/:/登入狀態已變更/);
        if(scenario==='observation-typing') assert.equal(await page.locator('#axBodySize').inputValue(),'18px');
        assert.equal(h.calls.filter(call=>call.method==='POST').length,0);
      }
      if (scenario === 'keyboard') {
        await page.locator('.ax-tabs button[data-tab="reorder"]').click();
        assert.deepEqual(await page.locator('#axReorderList .ax-setting-title').allTextContents(), titles);
        assert.equal(await page.locator('#axReorderList img').count(), 0, 'HTML-like titles are text');
        await page.locator('#axReorderList [data-slug="alpha"] [data-move="1"]').click();
        assert.deepEqual(await page.locator('#axReorderList li').evaluateAll(nodes => nodes.map(node => node.dataset.slug)), ['beta', 'alpha', 'gamma']);
        await page.keyboard.press('Enter');
        assert.deepEqual(await page.locator('#axReorderList li').evaluateAll(nodes => nodes.map(node => node.dataset.slug)), ['beta', 'gamma', 'alpha']);
        assert.equal(await page.evaluate(() => document.activeElement.closest('[data-slug]')?.dataset.slug), 'alpha', 'focus remains on the moved article at list end');
        await page.locator('#axOrderDefault').click();
        assert.deepEqual(await page.locator('#axReorderList li').evaluateAll(nodes => nodes.map(node => node.dataset.slug)), ['alpha', 'beta', 'gamma']);
        assert.equal(h.calls.filter(call => call.method === 'POST').length, 0);
      }
      if (scenario === 'save-typing') {
        await page.locator('#axBodySize').selectOption('17px'); h.mode = 'hold';
        await page.locator('#axFontApply').click();
        for (let i = 0; i < 50 && !h.pending; i++) await page.waitForTimeout(10);
        assert.ok(h.pending); await page.locator('#axBodySize').selectOption('18px'); h.mode = ''; h.pending(); await waitCloud(h);
        assert.equal(h.latest.settings.font.bodySize, '17px'); assert.equal(await page.locator('#axBodySize').inputValue(), '18px');
        assert.match(await page.locator('#axSettingsStatus').textContent(), /後續修改/);
        await page.locator('.ax-tabs button[data-tab="picks"]').click(); await page.locator('#axPicksAdd').selectOption('beta'); await page.locator('#axPicksAddBtn').click();
        await page.locator('#axPicksSave').click(); await waitCloud(h);
        assert.deepEqual(h.latest.settings.picks, ['alpha', 'beta']); assert.equal(h.latest.settings.font.bodySize, '17px');
        await page.locator('.ax-tabs button[data-tab="font"]').click(); assert.equal(await page.locator('#axBodySize').inputValue(), '18px');
        assert.equal(await page.locator('#axSettingsRequest').isDisabled(), true, 'all unsaved kinds must be saved before author approval');
      }
      if (scenario === 'compare') {
        await page.locator('#axBodySize').selectOption('18px'); await page.locator('#axSettingsLoad').click(); await waitCloud(h);
        assert.equal(await page.locator('#axBodySize').inputValue(), '18px'); await page.locator('#axSettingsCompare').click();
        assert.equal(await page.locator('dialog').count(), 1);
        await page.evaluate(() => { const original = Storage.prototype.setItem; Storage.prototype.setItem = function(key, value) {
          if (key === 'cd_site_settings_local_v2') throw new DOMException('fixture quota', 'QuotaExceededError'); return original.call(this, key, value);
        }; });
        await page.locator('#axSettingsAdoptRemote').click(); assert.equal(await page.locator('dialog').count(), 1, 'no discarded typing if backup fails');
        assert.equal(await page.locator('#axBodySize').inputValue(), '18px');
        await page.keyboard.press('Escape'); await page.locator('dialog').waitFor({state: 'detached'});
        assert.equal(await page.evaluate(() => document.activeElement.id), 'axSettingsCompare');
      }
      if (scenario === 'uncertain') {
        await page.locator('#axBodySize').selectOption('18px'); h.mode = 'uncertain'; await page.locator('#axFontApply').click(); await waitCloud(h);
        assert.match(await page.locator('#axSettingsStatus').textContent(), /尚未確認/); assert.equal(await page.locator('#axFontApply').isDisabled(), true);
        await page.locator('#axSettingsLoad').click(); await waitCloud(h); await page.locator('#axSettingsCompare').click();
        await page.locator('#axSettingsAdoptRemote').click(); await page.locator('dialog').waitFor({state: 'detached'});
        assert.equal(await page.locator('#axBodySize').inputValue(), '18px'); assert.equal(h.calls.filter(call => call.method === 'POST').length, 1);
      }
      if (scenario === 'request') {
        await page.locator('#axSettingsRequest').click(); assert.equal(await page.locator('#axSettingsSubmitRequest').isDisabled(), true);
        assert.match(await page.locator('dialog').textContent(), /沿用原先熱門推薦；這次未變更/);
        await page.locator('#axSettingsApproval').check(); await page.locator('#axSettingsApproval').focus(); await page.keyboard.press('Shift+Tab');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'axSettingsSubmitRequest'); await page.keyboard.press('Tab');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'axSettingsApproval'); await page.keyboard.press('Escape');
        await page.locator('dialog').waitFor({state: 'detached'});
        assert.equal(await page.evaluate(() => document.activeElement.id), 'axSettingsRequest'); assert.equal(h.calls.filter(call => call.method === 'POST').length, 0);
        await page.locator('#axSettingsRequest').click(); await page.locator('#axSettingsApproval').check();
        // Programmatic edits are also protected while a native modal is open.
        await page.evaluate(() => { const select = document.getElementById('axBodySize'); select.value = '18px'; select.dispatchEvent(new Event('change', {bubbles: true})); });
        await page.locator('#axSettingsSubmitRequest').click(); assert.equal(h.calls.filter(call => call.method === 'POST').length, 0);
        await page.keyboard.press('Escape'); await page.locator('dialog').waitFor({state: 'detached'}); await page.locator('#axFontApply').click(); await waitCloud(h);
        await page.locator('#axSettingsRequest').click(); await page.locator('#axSettingsApproval').check(); await page.locator('#axSettingsSubmitRequest').click(); await waitCloud(h);
        assert.equal(h.latest.status, 'requested'); assert.match(await page.locator('#axSettingsStatus').textContent(), /尚未確認正式上線/);
        await page.locator('#axSettingsCancel').click(); await waitCloud(h); assert.equal(h.latest.request, null);
      }
      if (scenario === 'migration') {
        await page.locator('.ax-tabs button[data-tab="picks"]').click();
        assert.match(await page.locator('#axPicksStats').textContent(), /新名單的起始選擇/);
        await page.locator('#axPicksSave').click(); await waitCloud(h);
        assert.equal(h.latest.settings.legacyPicks, false); assert.deepEqual(h.latest.settings.picks, ['alpha']);
        assert.equal(await page.locator('#axSettingsRequest').isDisabled(), false, 'no artificial edit needed after saving the initial picks');
        await page.locator('#axSettingsRequest').click();
        assert.ok(!(await page.locator('dialog').textContent()).includes('這次未變更'));
        assert.ok((await page.locator('dialog li').allTextContents()).includes(titles[0]));
        await page.locator('#axSettingsApproval').check(); await page.locator('#axSettingsSubmitRequest').click(); await waitCloud(h);
        assert.equal(h.latest.status, 'requested'); assert.equal(h.latest.published, false);
      }
      if (scenario === 'recovery-auth') {
        const prior = await page.evaluate(() => localStorage.getItem('cd_admin_settings_draft_font'));
        assert.equal(await page.locator('#axBodySize').inputValue(), ''); await page.locator('#axSettingsLegacyFont').click();
        assert.equal(await page.locator('#axBodySize').inputValue(), '17px'); assert.equal(await page.evaluate(() => localStorage.getItem('cd_admin_settings_draft_font')), prior);
        await page.locator('#axSettingsLocalSave').click(); const saved = await page.evaluate(() => localStorage.getItem('cd_site_settings_local_v2'));
        await page.locator('#axBodySize').selectOption('18px'); await page.locator('#axSettingsRecover').click(); assert.equal(await page.locator('#axBodySize').inputValue(), '17px');
        await page.evaluate(() => { const original = Storage.prototype.setItem; Storage.prototype.setItem = function(key, value) {
          if (key === 'cd_site_settings_local_v2') throw new DOMException('fixture quota', 'QuotaExceededError'); return original.call(this, key, value);
        }; });
        await page.locator('#axBodySize').selectOption('18px'); await page.locator('#axSettingsLocalSave').click();
        assert.equal(await page.evaluate(() => localStorage.getItem('cd_site_settings_local_v2')), saved); assert.equal(await page.locator('#axBodySize').inputValue(), '18px');
        await page.evaluate(() => window.cdAdminAuth.clearPat()); assert.equal(await page.locator('#axFontApply').isDisabled(), true);
        assert.match(await page.locator('#axSettingsStatus').textContent(), /登入狀態已變更/); assert.equal(h.calls.filter(call => call.method === 'POST').length, 0);
      }
      assert.equal(await page.frameLocator('iframe.editor').locator('article').evaluate(node => node.outerHTML), h.originalArticle, 'settings must not rewrite the article');
      assert.equal(h.latest.published, false); assert.equal(h.latest.deploymentVerified, false);
      assert.ok(!h.blocked.includes('private.invalid')); assert.deepEqual(h.errors, []);
      assert.ok(await page.locator('#axPanel').evaluate(node => { const rect = node.getBoundingClientRect(); return rect.left >= 0 && rect.right <= innerWidth; }), 'panel fits the viewport');
      cases++;
    } finally { await h.context.close(); }
  }
  console.log('PASS actual admin settings panel: ' + cases + ' cases, fixed cookie drafts/title text/keyboard/snapshot/compare/recovery/request guards; no real services or publication.');
  return {cases, widths: options.widths || [390, 800, 1440]};
};
