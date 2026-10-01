/* Private admin settings UI. Data from the cookie API is rendered as text.
 * A saved draft or author request never implies verified production delivery. */
(function () {
  'use strict';
  const fields = [['bodyFont', 'axBodyFont'], ['headFont', 'axHeadFont'], ['bodySize', 'axBodySize']];
  const messages = {
    not_loaded: '請先載入設定。文章編輯與網站設定分別保存。',
    loading_cloud: '正在載入雲端設定…', saving_cloud: '正在核對並存入雲端；後續編輯會保留在畫面。',
    remote_loaded: '已載入設定；正式上線狀態尚未核對。', local_changes: '畫面有尚未儲存的設定。',
    local_saved: '已保留在這個瀏覽器，尚未存雲端或發布。',
    local_storage_failed: '本機空間不足或不可用，畫面編輯與既有草稿保留。可下載備份。',
    local_recovered: '已還原本機草稿，尚未存雲端或發布。', local_recovery_invalid: '本機草稿無法套用，原始備份保留。',
    local_recovery_conflict: '本機與雲端版本不同，尚未套用本機草稿；原始備份保留。',
    cloud_saved: '雲端草稿已核對並保存，尚未正式發布。',
    cloud_saved_newer_local_changes: '送出時的版本已保存；畫面後續修改仍需再存。',
    requested: '已申請發布，仍需完成網站檢查及預覽；尚未確認正式上線。',
    compare_required: '雲端結果已取得；請比較版本。畫面編輯保留，尚未覆寫。',
    settings_conflict: '來源或另一個分頁的版本已變更；請重新載入並比較。',
    write_unconfirmed: '存檔結果尚未確認。請重新載入並比較，避免重複送出。',
    login_changed: '登入狀態已變更；請重新載入並比較。畫面編輯保留。',
    login_required: '請先完成後台登入；畫面草稿保留。',
    request_failed: '暫時無法取得設定。畫面與既有草稿保留，請稍後再試。',
    checking_publication: '正在核對正式網站檢查與部署，畫面編輯仍保留。',
    publication_observed: '已取得上線核對結果；雲端草稿與畫面設定保持原樣。',
    publication_changed: '核對期間版本已變更，請重新載入並比較；畫面草稿保留。',
    publication_unavailable: '正式上線狀態尚未確認，請稍後再試；畫面草稿保留。',
    creating_new_version: '正在從已核對的正式設定建立新版；後續編輯會保留。',
    new_version_created: '新版雲端草稿已核對，可以開始編輯；舊雲端版本保留，這個動作不會發布。',
    new_version_newer_local_changes: '新版雲端草稿已建立；送出後的畫面修改仍需再存。',
    new_version_failed: '尚未建立新版。請重新核對上線狀態；舊草稿保留。',
    settings_receipt_not_retired: '發布證據尚未完成封存，暫時無法建立新版；舊草稿保留，請稍後再核對。',
    settings_publication_not_verified: '正式網站檢查或部署尚未確認，暫時無法建立新版；舊草稿保留。',
    reconciling_catalog: '正在核對並儲存您確認的文章目錄整合；舊版與備份保留。',
    catalog_reconciled: '文章目錄已整合為雲端草稿；仍需確認、檢查與預覽後才能發布。',
  };
  function element(tag, text, attributes = {}) {
    const node = document.createElement(tag);
    if (text !== null) node.textContent = text;
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    return node;
  }
  function button(id, text, action) {
    const node = element('button', text, {id, type: 'button', class: 'ax-btn'});
    node.addEventListener('click', action); return node;
  }
  function mount({panel, previewFont, toast}) {
    if (panel.dataset.settingsMounted || !window.CDSettingsDrafts || typeof window.cdAdminAuth?.getRevision !== 'function') return;
    panel.dataset.settingsMounted = '1';
    const find = id => panel.querySelector('#' + id);
    const fonts = Object.fromEntries(fields.map(([key, id]) => [key, [...find(id).options].map(option => option.value)]));
    let model, lastOrder = '', lastPicks = '', dialog = null;
    const box = element('section', null, {class: 'ax-settings-status', 'aria-label': '網站設定草稿'});
    const status = element('p', messages.not_loaded, {id: 'axSettingsStatus', role: 'status', 'aria-live': 'polite'});
    const hint = element('p', '字型、首頁排序與熱門推薦共用一份設定草稿。存雲端後，再確認並申請發布。');
    const local = button('axSettingsLocalSave', '存本機草稿', () => perform(() => model.saveLocal()));
    const restore = button('axSettingsRecover', '還原本機草稿', () => confirmRecovery());
    const download = button('axSettingsExport', '下載草稿備份', () => exportDraft());
    const compare = button('axSettingsCompare', '比較雲端與畫面', () => showCompare());
    const request = button('axSettingsRequest', '確認並申請發布', () => showRequest());
    const cancel = button('axSettingsCancel', '取消發布申請', () => perform(() => model.cancelRequest()));
    const observe = button('axSettingsPublication', '查詢正式上線狀態', () => perform(() => model.observe()));
    const nextVersion = button('axSettingsNewVersion', '從網站設定建立新版', () => showNewVersion());
    const reconcile = button('axSettingsReconcile', '比較並整合文章目錄', () => showCatalog());
    const publicationStatus = element('p', '正式上線狀態尚未查詢。', {id: 'axSettingsPublicationStatus', role: 'status', 'aria-live': 'polite'});
    box.append(status, hint, local, restore, download, compare, request, cancel, observe, nextVersion, reconcile, publicationStatus);
    panel.querySelector('.ax-body').prepend(box);
    const style = element('style', '.ax-settings-status{border-bottom:1px solid #dcd5c8;padding:0 0 10px;margin-bottom:12px;font-size:12px}' +
      '.ax-settings-status p{margin:6px 0}.ax-settings-dialog{box-sizing:border-box;max-width:720px;width:calc(100vw - 32px);max-height:calc(100vh - 32px);overflow:auto;padding:20px;border:1px solid #dcd5c8;border-radius:12px;color:#2a2620;background:#fff}' +
      '.ax-settings-dialog::backdrop{background:rgba(0,0,0,.45)}.ax-settings-dialog h2{font-size:20px;margin:0 0 12px}.ax-settings-dialog section{margin:14px 0;overflow-wrap:anywhere}' +
      '.ax-settings-dialog footer{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.ax-settings-dialog ol{padding-left:24px}.ax-setting-title{display:block;flex:1;min-width:0;overflow-wrap:anywhere}' +
      '.ax-reorder-list li.ax-setting-row{display:flex;flex-wrap:wrap;gap:4px;align-items:center;cursor:default}.ax-setting-row button{margin:0;font-size:12px;padding:4px 7px}' +
      '.ax-settings-status button:disabled,.ax-setting-row button:disabled{opacity:.55;cursor:default}');
    document.head.appendChild(style);
    async function perform(action) {
      try { return await action(); }
      catch (error) { toast(messages[error.code] || '目前無法套用這項操作；畫面草稿保留。'); return null; }
    }
    function currentOrder(state) { return state.working?.order.length ? state.working.order : state.loaded?.articles.map(item => item.slug) || []; }
    function move(kind, slug, delta) {
      const state = model.snapshot(), order = kind === 'order' ? currentOrder(state).slice() : state.working.picks.slice();
      const index = order.indexOf(slug), next = index + delta;
      if (index < 0 || next < 0 || next >= order.length) return;
      [order[index], order[next]] = [order[next], order[index]];
      perform(() => model.set(kind, order));
      const row = find(kind === 'order' ? 'axReorderList' : 'axPicksList').querySelector('[data-slug="' + slug + '"]');
      const requested = row?.querySelector('[data-move="' + delta + '"]');
      (requested && !requested.disabled ? requested : row?.querySelector('button:not(:disabled)'))?.focus();
    }
    function renderList(kind, values, articles) {
      const list = find(kind === 'order' ? 'axReorderList' : 'axPicksList'); list.replaceChildren();
      const titles = new Map(articles.map(item => [item.slug, item]));
      values.forEach((slug, index) => {
        const article = titles.get(slug), row = element('li', null, {class: 'ax-setting-row', 'data-slug': slug});
        const title = element('span', null, {class: 'ax-setting-title'});
        title.textContent = article.title;
        row.append(title);
        for (const [delta, label] of [[-1, '上移'], [1, '下移']]) {
          const control = button('', label, () => move(kind, slug, delta)); control.removeAttribute('id');
          control.dataset.move = String(delta); control.setAttribute('aria-label', article.title + '：' + label);
          control.disabled = delta < 0 ? index === 0 : index === values.length - 1; row.append(control);
        }
        if (kind === 'picks') {
          const remove = button('', '移除', () => {
            const state = model.snapshot(); if (state.working.picks.length <= 1) return toast('熱門推薦至少保留一篇。');
            perform(() => model.set('picks', state.working.picks.filter(value => value !== slug)));
            const next = find('axPicksList').children[Math.min(index, state.working.picks.length - 2)];
            (next?.querySelector('button:not(:disabled)') || find('axPicksAdd'))?.focus();
          });
          remove.removeAttribute('id'); remove.setAttribute('aria-label', article.title + '：移除'); remove.disabled = values.length <= 1; row.append(remove);
        }
        list.append(row);
      });
    }
    function paint(state) {
      const tab = panel.querySelector('.ax-tab.active')?.dataset.tab;
      box.hidden = !['font', 'reorder', 'picks'].includes(tab);
      status.textContent = state.loaded && !state.authorised ? messages.login_changed : state.uncertain ? messages.write_unconfirmed :
        state.remote ? messages.compare_required : state.needsRefresh ? messages.settings_conflict : messages[state.status] || messages.request_failed;
      const editing = !!state.working;
      const cloud = editing && state.authorised && !state.busy && !state.remote && !state.uncertain && !state.needsRefresh && !state.loaded.conflict;
      for (const [key, id] of fields) { find(id).disabled = !editing; if (editing) find(id).value = state.working.font[key]; }
      for (const id of ['axFontApply', 'axReorderSave', 'axPicksSave']) { find(id).disabled = !cloud; find(id).style.display = 'inline-flex'; }
      for (const id of ['axSettingsLoad', 'axReorderLoad', 'axPicksLoad']) find(id).disabled = state.busy;
      local.disabled = !editing; restore.disabled = !editing || state.busy; download.disabled = !state.loaded;
      compare.disabled = !state.remote || state.busy;
      request.disabled = !cloud || state.dirty || !state.loaded.head || !!state.loaded.request;
      cancel.disabled = !cloud || state.dirty || !state.loaded.request;
      observe.disabled = !state.loaded || !state.authorised || state.busy || state.dirty || !!state.remote || state.uncertain || state.needsRefresh;
      const proof = state.authorised ? state.publication : null;
      nextVersion.disabled = observe.disabled || !state.loaded?.head || proof?.state !== 'live' || !proof.ciVerified || !proof.deploymentVerified;
      reconcile.disabled = !state.loaded?.conflict || !state.authorised || state.busy || state.dirty || !!state.remote || state.uncertain || state.needsRefresh ||
        !(state.loaded.sourceRequiresReview || state.loaded.catalogSha !== state.loaded.mainCatalogSha);
      const publicationMessages = {
        ci_missing: '尚未取得這個版本的完整網站檢查。', ci_running: '網站檢查仍在進行，尚未確認上線。',
        ci_failed: '網站檢查未全部通過，尚未確認上線。', deployment_missing: '網站檢查已通過，尚未取得正式部署。',
        deployment_running: '正式網站正在更新，尚未確認完成。', deployment_failed: '正式部署尚未成功，請稍後再核對。',
        changed: '核對期間網站版本變更，請重新查詢。', not_published: '尚未取得正式網站的設定。',
        unverified: '目前無法確認完整上線證據，請稍後再試。',
      };
      publicationStatus.textContent = !proof ? '正式上線狀態尚未確認；存本機、存雲端及提交申請都不代表上線。' :
        proof.state === 'live' ? proof.published ? '這份已儲存設定的網站檢查與正式部署均已核對，確認已上線。' :
          '正式網站的目前設定已核對；這份雲端草稿與網站不同，尚未上線。' : publicationMessages[proof.state];
      if (proof) publicationStatus.textContent = '上次核對（'+new Date(proof.observedAt).toLocaleString('zh-TW',{hour12:false})+'）：'+publicationStatus.textContent;
      find('axFontPreview').disabled = !editing;
      find('axSettingsLegacyFont').disabled = !editing || state.busy;
      find('axSettingsLegacyOrder').disabled = !editing || state.busy;
      find('axOrderDefault').disabled = !editing;
      find('axPicksAdd').disabled = !editing || state.working.picks.length >= 12;
      find('axPicksAddBtn').disabled = !editing || state.working.picks.length >= 12;
      if (!editing) return;
      const order = currentOrder(state), orderKey = JSON.stringify([order, state.loaded.articles]);
      const picksKey = JSON.stringify([state.working.picks, state.loaded.articles]);
      if (orderKey !== lastOrder) { renderList('order', order, state.loaded.articles); lastOrder = orderKey; }
      if (picksKey !== lastPicks) {
        renderList('picks', state.working.picks, state.loaded.articles); lastPicks = picksKey;
        const select = find('axPicksAdd'), selected = select.value; select.replaceChildren();
        select.append(element('option', '選擇要推薦的文章', {value: ''}));
        for (const article of state.loaded.articles) if (!state.working.picks.includes(article.slug)) select.append(element('option', article.title, {value: article.slug}));
        if ([...select.options].some(option => option.value === selected)) select.value = selected;
      }
      find('axPicksStats').textContent = state.working.legacyPicks ?
        '目前沿用原先網站的熱門推薦。下列是新名單的起始選擇，儲存並申請發布後才會取代原名單。' :
        '畫面選擇 ' + state.working.picks.length + ' 篇；存雲端後仍需申請發布。';
    }
    function openDialog(title, trigger) {
      if (dialog) return null;
      const node = element('dialog', null, {class: 'ax-settings-dialog', 'aria-labelledby': 'axSettingsDialogTitle'});
      if (typeof node.showModal !== 'function') { toast('這個瀏覽器無法開啟確認視窗，請更新瀏覽器；草稿保留。'); return null; }
      node.append(element('h2', title, {id: 'axSettingsDialogTitle'})); document.body.append(node); dialog = node;
      node.addEventListener('close', () => { dialog = null; node.remove();
        if (trigger?.isConnected && !trigger.disabled) trigger.focus(); else find('axSettingsLoad').focus(); });
      node.addEventListener('keydown', event => {
        if (event.key !== 'Tab') return;
        const controls = [...node.querySelectorAll('button,input')].filter(control => !control.disabled && !control.hidden);
        const first = controls[0], last = controls.at(-1); if (!first) return;
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      });
      return node;
    }
    function summary(node, label, settings, articles) {
      const section = element('section', null); section.append(element('h3', label));
      if (!settings || !Array.isArray(settings.order) || !Array.isArray(settings.picks) || !settings.font) { section.append(element('p', '這個版本需另外整合，尚未套用。')); node.append(section); return; }
      for (const [key, id] of fields) {
        const option = [...find(id).options].find(item => item.value === settings.font[key]);
        section.append(element('p', find(id).labels[0]?.textContent + '：' + (option?.textContent || '無法套用')));
      }
      const titles = new Map(articles.map(item => [item.slug, item.title]));
      for (const [key, heading] of [['order', '首頁排序'], ['picks', '熱門推薦']]) {
        section.append(element('h4', heading));
        if (key === 'picks' && settings.legacyPicks) section.append(element('p', '沿用原先熱門推薦；這次未變更。'));
        else if (key === 'order' && !settings.order.length) section.append(element('p', '依文章日期排序（預設）'));
        else { const list = element('ol', null); settings[key].forEach(slug => list.append(element('li', titles.get(slug) || '已不在公開目錄的文章'))); section.append(list); }
      }
      node.append(section);
    }
    function showCompare() {
      const state = model.snapshot(); if (!state.remote) return;
      const node = openDialog('比較設定版本', compare); if (!node) return;
      summary(node, '畫面草稿（保留中）', state.working, state.loaded?.articles || state.remote.articles);
      summary(node, '剛取得的雲端版本', state.remote.conflict ? null : state.remote.settings, state.remote.articles);
      const footer = element('footer', null);
      footer.append(button('axSettingsKeepLocal', '繼續保留畫面草稿', () => node.close()));
      const adopt = button('axSettingsAdoptRemote', '備份畫面後採用雲端', () => {
        const now = model.snapshot();
        if (now.editRevision !== state.editRevision || now.remote?.head !== state.remote.head || now.busy) return toast('版本或畫面已變更，請重新比較。');
        if (now.dirty && !model.saveLocal()) { toast(messages.local_storage_failed); return; }
        perform(() => model.adoptRemote(state.editRevision)); node.close();
      }); adopt.disabled = state.remote.conflict; footer.append(adopt); node.append(footer); node.showModal();
    }
    function showRequest() {
      const state = model.snapshot(); if (!state.loaded || state.dirty || state.busy || !state.authorised) return;
      const node = openDialog('確認這組網站設定', request); if (!node) return;
      summary(node, '將申請發布的雲端草稿', state.loaded.settings, state.loaded.articles);
      const label = element('label', null), approved = element('input', null, {type: 'checkbox', id: 'axSettingsApproval'});
      label.append(approved, document.createTextNode(' 我已確認字型、首頁排序與推薦文章；檢查及預覽通過後才發布。')); node.append(label);
      const footer = element('footer', null), submit = button('axSettingsSubmitRequest', '提交發布申請', async () => {
        const now = model.snapshot();
        if (!approved.checked || now.editRevision !== state.editRevision || now.loaded?.head !== state.loaded.head ||
            now.loaded?.blobSha !== state.loaded.blobSha || now.busy) return toast('草稿已變更，請重新確認。');
        submit.disabled = true; approved.disabled = true;
        await perform(() => model.publication(true)); if (node.isConnected) node.close();
      }); submit.disabled = true;
      approved.addEventListener('change', () => submit.disabled = !approved.checked);
      footer.append(button('axSettingsRequestClose', '返回編輯', () => node.close()), submit); node.append(footer); node.showModal();
    }
    function showNewVersion() {
      const state = model.snapshot(), proof = state.publication;
      if (!state.loaded?.head || state.dirty || state.busy || !state.authorised || proof?.state !== 'live') return;
      const node = openDialog('比較並建立新版設定草稿', nextVersion); if (!node) return;
      summary(node, '目前雲端草稿（舊版會保留）', state.loaded.settings, state.loaded.articles);
      summary(node, '上次核對的正式網站設定', proof.sourceSettings, proof.articles);
      const label = element('label', null), approved = element('input', null, {type:'checkbox',id:'axSettingsNewVersionApproval'});
      label.append(approved,document.createTextNode(' 我已比較並確認，使用正式網站設定開始新一輪編輯；這個動作不會發布。')); node.append(label);
      const footer = element('footer',null), submit = button('axSettingsCreateNewVersion','確認建立新版',async()=>{
        const now = model.snapshot();
        if (!approved.checked || now.editRevision !== state.editRevision || now.loaded?.head !== state.loaded.head || now.busy ||
            now.publication?.mainSha !== proof.mainSha || now.publication?.mainBlobSha !== proof.mainBlobSha) return toast('版本或畫面已變更，請重新比較。');
        submit.disabled = true; approved.disabled = true;
        await perform(()=>model.newVersion(true,state.editRevision)); if(node.isConnected)node.close();
      }); submit.disabled = true;
      approved.addEventListener('change',()=>submit.disabled=!approved.checked);
      footer.append(button('axSettingsNewVersionClose','保留目前草稿',()=>node.close()),submit); node.append(footer); node.showModal();
    }
    function showCatalog() {
      if (reconcile.disabled) return;
      const state = model.snapshot(), node = openDialog('比較並整合文章目錄', reconcile); if (!node) return;
      node.append(element('p','請選擇要保留的設定來源，再核對清單。這個動作只存雲端草稿，不會發布；舊版資料與發布申請保留在歷史中。'));
      const controls = element('section',null), changes = element('section',null), picks = element('section',null), proposed = element('section',null);
      let selected;
      const label = element('label',null), approved = element('input',null,{type:'checkbox',id:'axSettingsCatalogApproval'});
      label.append(approved,document.createTextNode(' 我已比較並確認新的排序與推薦清單；原版本與本機備份保留。'));
      const footer = element('footer',null), submit = button('axSettingsSubmitCatalog','確認整合為草稿',async()=>{
        const now = model.snapshot();
        if (!approved.checked || now.editRevision !== state.editRevision || now.loaded?.head !== state.loaded.head || now.loaded?.main !== state.loaded.main || now.busy)
          return toast('版本或畫面已變更，請重新比較。');
        submit.disabled = true; approved.disabled = true;
        await perform(()=>model.reconcileCatalog(selected,true,state.editRevision)); if(node.isConnected)node.close();
      });
      function preview() {
        proposed.replaceChildren(); summary(proposed,'確認後的設定草稿',selected,state.loaded.articles);
        submit.disabled = !approved.checked || selected.picks.length < 1 || selected.picks.length > 12;
      }
      function choose(base) {
        const plan = model.catalogPlan(base); selected = plan.settings; approved.checked = false;
        changes.replaceChildren(); summary(changes,'原始設定（尚未變更）',plan.original,state.loaded.articles);
        changes.append(element('p','已移出目錄：'+(plan.removed.join('、') || '無')),
          element('p','新增至自訂排序末尾：'+(plan.added.map(slug=>state.loaded.articles.find(item=>item.slug===slug).title).join('、') || '無；預設排序依文章日期')));
        picks.replaceChildren(); picks.append(element('h3','核對熱門推薦（選擇 1 至 12 篇）'));
        for (const article of state.loaded.articles) {
          const row = element('label',null), input = element('input',null,{type:'checkbox','data-catalog-pick':article.slug});
          input.checked = selected.picks.includes(article.slug); row.style.display = 'block';
          row.append(input,document.createTextNode(' '+article.title)); picks.append(row);
          input.addEventListener('change',()=>{
            selected.picks = input.checked ? selected.picks.concat(article.slug) : selected.picks.filter(slug=>slug!==article.slug);
            selected.legacyPicks = false; approved.checked = false; preview();
          });
        }
        preview();
      }
      for (const [base,text] of [['draft','保留原雲端草稿設定'],['source','採用目前網站來源設定']]) {
        const row = element('label',null), input = element('input',null,{type:'radio',name:'axSettingsCatalogBase',value:base});
        input.checked = base === 'draft'; row.style.display = 'block'; row.append(input,document.createTextNode(' '+text)); controls.append(row);
        input.addEventListener('change',()=>{ if(input.checked) choose(base); });
      }
      approved.addEventListener('change',preview);
      footer.append(button('axSettingsCatalogClose','保留舊版，稍後處理',()=>node.close()),submit);
      node.append(controls,changes,picks,proposed,label,footer); choose('draft'); node.showModal();
    }
    function confirmRecovery() {
      const state = model.snapshot();
      if (state.dirty && !window.confirm('要以本機草稿取代畫面設定嗎？取消會保留畫面修改。')) return;
      perform(() => model.recoverLocal());
    }
    function exportDraft() {
      const state = model.snapshot(); if (!state.loaded) return;
      const blob = new Blob([JSON.stringify({version: 2, head: state.loaded?.head, baseSha: state.loaded?.baseSha,
        catalogSha: state.loaded?.catalogSha, settings: state.working || state.loaded.settings}, null, 2) + '\n'], {type: 'application/json'});
      const url = URL.createObjectURL(blob), link = element('a', '設定草稿備份', {download: 'site-settings-draft.json', href: url});
      document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    function importLegacy(kind) {
      let value;
      try { value = JSON.parse(localStorage.getItem('cd_admin_settings_draft_' + (kind === 'order' ? 'reorder' : 'font'))); }
      catch (_) { return toast('舊草稿無法讀取，原始備份保留。'); }
      if (value?.version !== 1 || value.kind !== (kind === 'order' ? 'reorder' : 'font')) return toast('沒有可套用的舊草稿。');
      const data = kind === 'order' ? value.order : Object.fromEntries(fields.map(([key]) => [key, value[key]]));
      if (!window.confirm('將舊草稿套用到畫面，稍後仍須存雲端並確認發布。要繼續嗎？')) return;
      perform(() => model.set(kind, data)); // Full current catalogue/closed-font validation; original legacy copy is retained.
    }
    const load = button('axSettingsLoad', '載入／重新核對雲端設定', () => perform(() => model.load()));
    box.insertBefore(load, local);
    find('axFontApply').addEventListener('click', () => perform(() => model.saveCloud('font')));
    find('axFontPreview').addEventListener('click', previewFont);
    find('axReorderSave').addEventListener('click', () => perform(() => model.saveCloud('order')));
    find('axPicksSave').addEventListener('click', () => perform(() => model.saveCloud('picks')));
    for (const id of ['axReorderLoad', 'axPicksLoad']) find(id).addEventListener('click', () => perform(() => model.load()));
    for (const [, id] of fields) find(id).addEventListener('change', () => perform(() => model.set('font', Object.fromEntries(fields.map(([key, control]) => [key, find(control).value])))));
    find('axPicksAddBtn').addEventListener('click', () => {
      const selected = find('axPicksAdd').value, state = model.snapshot(); if (!selected || !state.working) return;
      perform(() => model.set('picks', [...state.working.picks, selected]));
    });
    find('axSettingsLegacyFont').addEventListener('click', () => importLegacy('font'));
    find('axSettingsLegacyOrder').addEventListener('click', () => importLegacy('order'));
    find('axOrderDefault').addEventListener('click', () => perform(() => model.set('order', [])));
    panel.querySelector('.ax-tabs').addEventListener('click', () => paint(model.snapshot()));
    window.addEventListener('cd-admin-auth-changed', () => paint(model.snapshot()));
    model = window.CDSettingsDrafts.create({auth: window.cdAdminAuth, fonts,
      storage: {getItem: key => localStorage.getItem(key), setItem: (key, value) => localStorage.setItem(key, value)},
      fetch: window.fetch.bind(window), changed: paint});
    paint(model.snapshot());
  }
  window.CDSettingsPanel = {mount};
  document.dispatchEvent(new Event('cd-settings-ready'));
})();
