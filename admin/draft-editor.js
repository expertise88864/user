// Bridge the existing visual/source/bilingual editor to immutable cloud drafts.
// Keep the original serializer and caret; saving must not remount the editor.
(function () {
  'use strict';
  const drafts = window.DNArticleDrafts;
  if (!drafts) return; // gh rejects writes even if this bridge cannot load.
  const originalLoad = loadFile, originalMount = mountIframe, originalSource = mountSource, originalContent = getCurrentEditorContent;
  let status = null;
  let viewObserver = null;
  let requestDialog = null;
  const requestLabels = { awaiting_review: '待審核', schedule_requested: '排程申請已保存',
    unpublish_requested: '下架申請已保存', invalidated: '舊申請已失效，需重新確認' };
  const publicationLabel = document.createElement('span');
  publicationLabel.id = 'publicationState'; publicationLabel.setAttribute('aria-live', 'polite');
  elStatusbar.appendChild(publicationLabel);
  let observationGeneration = 0;
  const websiteNotice = document.createElement('div');
  websiteNotice.id = 'websitePublicationNotice';
  websiteNotice.style.cssText = 'padding:8px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;flex-wrap:wrap;gap:8px;font-size:12px';
  const websiteLabel = document.createElement('span'), websiteButton = document.createElement('button');
  websiteLabel.id = 'websitePublicationState'; websiteLabel.setAttribute('aria-live', 'polite');
  websiteButton.id = 'checkPublicationBtn'; websiteButton.type = 'button'; websiteButton.textContent = '查看上線狀態';
  websiteButton.style.cssText = 'min-height:44px;padding:6px 10px;border:1px solid var(--border);border-radius:6px;background:#fff;color:var(--ink);cursor:pointer;flex-shrink:0';
  websiteNotice.append(websiteLabel, websiteButton);
  const newVersionButton = document.createElement('button'), versionBackupButton = document.createElement('button');
  newVersionButton.type = 'button'; versionBackupButton.type = 'button';
  for (const button of [newVersionButton, versionBackupButton]) button.style.cssText = websiteButton.style.cssText;
  newVersionButton.id = 'newDraftVersionBtn'; newVersionButton.textContent = '從上線版建立新版草稿';
  versionBackupButton.id = 'restoreDraftVersionBtn'; versionBackupButton.textContent = '還原新版前快照';
  websiteNotice.append(newVersionButton, versionBackupButton);
  document.getElementById('frameWrap').before(websiteNotice);
  function resetPublication() {
    observationGeneration++;
    websiteLabel.textContent = '網站上線狀態尚未核對。'; websiteLabel.removeAttribute('title');
    websiteButton.disabled = false;
  }
  resetPublication();
  websiteButton.addEventListener('click', async () => {
    const editorIdentity = identity();
    if (!isCurrent(editorIdentity) || !drafts.isArticle(CURRENT_FILE)) {
      websiteLabel.textContent = '請先登入並開啟文章，等待載入或保存完成後再核對。'; return;
    }
    const generation = ++observationGeneration;
    websiteButton.disabled = true; websiteLabel.textContent = '正在核對網站版本、正式驗證與部署…';
    try {
      const result = await drafts.observe(editorIdentity.file);
      if (generation !== observationGeneration || !isCurrent(editorIdentity)) return;
      websiteLabel.textContent = drafts.publicationMessage(result.publication) + (DIRTY ? ' 本機的新編輯尚未保存。' : '');
      websiteLabel.title = '核對時間：' + new Date(result.publication.observedAt).toLocaleString('zh-TW') + '；可重新查看最新狀態。';
    } catch (failure) {
      if (generation === observationGeneration && isCurrent(editorIdentity)) websiteLabel.textContent = drafts.message(failure);
    } finally {
      if (generation === observationGeneration) {
        websiteButton.disabled = false;
        if (!isCurrent(editorIdentity)) resetPublication();
      }
    }
  });
  function renderRequestState(request) {
    publicationLabel.textContent = request ? requestLabels[request.status] || '申請狀態需重讀確認' : '尚未送審';
    const cancel = document.getElementById('cancelRequestBtn');
    if (cancel) cancel.disabled = !request;
  }
  let listGeneration = 0;
  const originalRefresh = refreshFileList;
  refreshFileList = async function () {
    const generation = ++listGeneration, token = auth.getPat();
    await originalRefresh();
    if (!token || token !== auth.getPat()) return;
    try {
      const data = await drafts.list();
      if (generation !== listGeneration || token !== auth.getPat()) return;
      const existing = new Map(Array.from(elFileList.querySelectorAll('.file-item')).map(el => [el.dataset.path, el]));
      for (const draft of data.drafts) {
        let item = existing.get(draft.file);
        if (!item) {
          item = document.createElement('div'); item.className = 'file-item'; item.dataset.path = draft.file;
          item.textContent = draft.file; item.addEventListener('click', () => loadFile(draft.file)); elFileList.appendChild(item);
        }
        const label = document.createElement('span'); label.textContent = draft.legacy ? ' · 舊草稿（需比對）' : ' · 雲端草稿'; item.appendChild(label);
      }
      if (data.unsupportedRefs) setStatus('文章草稿已載入；另有 ' + data.unsupportedRefs + ' 個工程草稿需由專案流程處理。');
    } catch (failure) { setStatus('雲端草稿清單讀取未完成，可重試；目前編輯保留：' + drafts.message(failure), true); }
  };
  async function createArticle({ slug, html, title_en, tag, tag_en, type, date }) {
    const token = auth.getPat();
    if (!token || auth.isLogoutPending()) throw new Error('請先完成登入；輸入內容仍保留。');
    const cat = type === 'note' ? 'note' : type === 'research' ? 'research' : ['rx', 'overview'].includes(type) ? 'rx' : 'myth';
    const accepted = await drafts.create('blog/' + slug + '.html', html, { title_en, tag, tag_en, cat, date });
    if (auth.getPat() !== token || auth.isLogoutPending()) throw new Error('登入已變更，請重讀草稿清單確認建立結果；勿重複建立。');
    return accepted.head;
  }
  function current(file, loadId) { return CURRENT_FILE === file && EDITOR_LOAD_ID === loadId; }
  const versionBackupKey = file => 'cd-draft-version-backup:' + file;
  function preserveVersion(snapshot) {
    const raw = JSON.stringify({ file: snapshot.file, ts: Date.now(), sha: snapshot.sha,
      content: snapshot.content, draft: drafts.localState(snapshot.file) });
    localStorage.setItem(versionBackupKey(snapshot.file), raw);
    if (localStorage.getItem(versionBackupKey(snapshot.file)) !== raw) throw new Error('local_snapshot_failed');
  }
  async function startNewVersion() {
    const editorIdentity = identity();
    if (!isCurrent(editorIdentity) || !auth.getPat() || !drafts.isArticle(editorIdentity.file)) return;
    const snapshot = captureSaveSnapshot();
    let created = false;
    const active = () => current(snapshot.file, snapshot.loadId) && identityTokens.get(editorIdentity) === auth.getPat() && !auth.isLogoutPending();
    SAVE_PENDING = true; newVersionButton.disabled = true; versionBackupButton.disabled = true;
    setStatus('核對正式版本、CI 與部署；目前編輯保留…');
    try {
      const observed = await drafts.observe(snapshot.file);
      if (!active() || getCurrentEditorContent() !== snapshot.content) { setStatus('核對期間編輯已改變，請重新操作；尚未建立新版。', true); return; }
      const request = drafts.captureNewVersion(snapshot.file, observed);
      let previous;
      try { previous = localStorage.getItem(versionBackupKey(snapshot.file)); }
      catch (_) { setStatus('無法保存本機快照，尚未建立新版；請確認瀏覽器儲存空間。', true); return; }
      if (!confirm('將從已驗證的正式上線版建立新版草稿，舊雲端版本與申請保留在歷史。' +
          '目前內容及圖片會保存為本機「新版前快照」，不會自動上線。' +
          (previous ? '這會取代這篇先前的新版前快照；一般自動暫存仍保留。' : '') + '確定繼續？')) return;
      try { preserveVersion(snapshot); }
      catch (_) { setStatus('本機快照未能完整保存，尚未建立新版；目前內容保留。', true); return; }
      if (!active() || getCurrentEditorContent() !== snapshot.content) return;
      const accepted = await drafts.startNewVersion(request);
      created = true;
      if (!active()) return;
      if (getCurrentEditorContent() !== snapshot.content) { DIRTY = true; autosave(); setStatus('新版雲端草稿已建立；作業中的新編輯保留，請重讀比對，未覆寫編輯。', true); return; }
      const data = await drafts.load(snapshot.file, { activate: false });
      if (!active()) return;
      if (getCurrentEditorContent() !== snapshot.content) { DIRTY = true; autosave(); setStatus('新版草稿已建立；重讀期間的新編輯保留，請比對版本。', true); return; }
      if (data.head !== accepted.head || data.baseSha !== accepted.baseSha || data.blobSha !== accepted.blobSha ||
          data.legacy || data.conflict || data.request || typeof data.content !== 'string') throw new Error('new_version_reload_failed');
      drafts.activate(data); status = data;
      CURRENT_SHA = data.blobSha; CURRENT_CONTENT = data.content; DIRTY = false;
      elShaInfo.textContent = '草稿 SHA: ' + data.blobSha.slice(0, 7);
      if (SOURCE_MODE) mountSource(data.content); else mountIframe(data.content);
      if (sourceTextarea) sourceTextarea.readOnly = false;
      renderRequestState(null); resetPublication();
      document.getElementById('behindBanner').style.display = 'none';
      setStatus('新版雲端草稿已建立，尚未上線。可用「還原新版前快照」比對舊編輯；一般暫存仍保留。');
      checkAutosaveOnLoad(snapshot.file); scheduleWordCount();
    } catch (failure) { if (active()) setStatus((created ? '新版雲端草稿已建立，但重讀核對未完成，請比對版本，勿重複建立。' : '') + drafts.message(failure), true); }
    finally { SAVE_PENDING = false; newVersionButton.disabled = false; versionBackupButton.disabled = false; }
  }
  newVersionButton.addEventListener('click', startNewVersion);
  versionBackupButton.addEventListener('click', async () => {
    const editorIdentity = identity();
    if (!isCurrent(editorIdentity) || !auth.getPat() || !drafts.isArticle(editorIdentity.file)) return;
    const snapshot = captureSaveSnapshot();
    try {
      const saved = JSON.parse(localStorage.getItem(versionBackupKey(snapshot.file)) || 'null');
      if (!saved || saved.file !== snapshot.file || typeof saved.content !== 'string' || !saved.draft) { setStatus('這篇尚無新版前快照；目前編輯保留。'); return; }
      if (!confirm('還原新版前的內容與圖片，雲端草稿不變；目前編輯會先保存到一般本機暫存。版本不同時需比對整合。')) return;
      const raw = JSON.stringify({ ts: Date.now(), sha: snapshot.sha, content: snapshot.content, draft: drafts.localState(snapshot.file) });
      localStorage.setItem(autosaveKey(snapshot.file), raw);
      if (localStorage.getItem(autosaveKey(snapshot.file)) !== raw) throw new Error('local_snapshot_failed');
      const active = () => isCurrent(editorIdentity) && getCurrentEditorContent() === snapshot.content;
      versionBackupButton.disabled = true;
      const result = await drafts.restore(snapshot.file, saved.draft, { isCurrent: active });
      if (!active()) return;
      CURRENT_CONTENT = saved.content;
      if (SOURCE_MODE) mountSource(saved.content); else mountIframe(saved.content);
      DIRTY = true;
      setStatus(result.conflict ? '已還原新版前內容與圖片；版本不同，需比對整合，尚未保存雲端。' : '已還原新版前快照，尚未保存雲端。', result.conflict);
    } catch (_) { if (isCurrent(editorIdentity)) setStatus('快照還原未完成；目前編輯與原快照保留，請確認儲存空間及版本。', true); }
    finally { versionBackupButton.disabled = false; }
  });
  function displayState(data) {
    renderRequestState(data.request);
    if (data.legacy) setStatus('已載入舊雲端草稿；須先比對整合，目前僅供檢閱。', true);
    else if (data.conflict) setStatus('已載入雲端草稿；正式文章已有新版本，須先比對整合。', true);
    else setStatus(data.head ? '已載入雲端草稿；尚未正式發布。' : '已載入網站來源版本；編輯後會保存為雲端草稿。');
  }
  getCurrentEditorContent = function () { return drafts.canonical(CURRENT_FILE, originalContent()); };
  mountIframe = function (html) {
    if (viewObserver) { viewObserver.disconnect(); viewObserver = null; }
    originalMount(html);
    const frame = editFrame, file = CURRENT_FILE, loadId = EDITOR_LOAD_ID, loaded = drafts.localState(CURRENT_FILE);
    frame.addEventListener('load', () => {
      if (editFrame !== frame || !current(file, loadId)) return;
      drafts.preview(file, frame.contentDocument);
      if (loaded && !DIRTY && !SAVE_PENDING) drafts.bindView(file, getCurrentEditorContent(), loaded.head);
      if (status && (status.legacy || status.conflict)) {
        for (const region of frame.contentDocument.querySelectorAll('[contenteditable]')) region.contentEditable = 'false';
      } else {
        // A sandboxed editing engine can change text without delivering input
        // to the parent's listener. Compare real content with the mounted view;
        // decorative changes must not turn a clean source into a dirty draft.
        viewObserver = new MutationObserver(() => {
          if (frame !== editFrame || CURRENT_FILE !== file || (window.DNWordEditor && DNWordEditor.active())) return;
          if (drafts.hasUnsavedChanges(file, getCurrentEditorContent())) DIRTY = true;
        });
        for (const region of frame.contentDocument.querySelectorAll('[data-cd-editable]')) {
          viewObserver.observe(region, { subtree: true, childList: true, characterData: true, attributes: true,
            attributeFilter: ['href', 'src', 'alt', 'title', 'style', 'colspan', 'rowspan', 'start', 'type', 'width', 'height'] });
        }
      }
    }, { once: true });
  };
  mountSource = function (content) {
    if (viewObserver) { viewObserver.disconnect(); viewObserver = null; }
    originalSource(content);
    if (sourceTextarea) sourceTextarea.readOnly = !!(status && (status.legacy || status.conflict));
    const loaded = drafts.localState(CURRENT_FILE);
    if (loaded && !DIRTY && !SAVE_PENDING) drafts.bindView(CURRENT_FILE, getCurrentEditorContent(), loaded.head);
  };
  loadFile = async function (path) {
    if (!drafts.isArticle(path)) { status = null; renderRequestState(null); resetPublication(); return originalLoad(path); }
    if (SAVE_PENDING) { setStatus('存檔或圖片處理中，請稍候再切換文章。'); return false; }
    if (DIRTY && !confirm('目前有未儲存的改動，要捨棄嗎？本機暫存仍會保留。')) return false;
    autosave(); // Preserve the outgoing revision and its pending local images.
    const loadId = ++EDITOR_LOAD_ID;
    resetPublication();
    EDITOR_LOADING = true; setStatus('讀取正式版本與雲端草稿…');
    try {
      const data = await drafts.load(path, { activate: false });
      if (loadId !== EDITOR_LOAD_ID) return false;
      if (typeof data.content !== 'string') throw new Error('這篇尚無文章內容，請先建立草稿。');
      autosave(); // Also preserve any typing in the old editor while loading.
      drafts.activate(data);
      CURRENT_FILE = path; CURRENT_SHA = data.blobSha; CURRENT_CONTENT = data.content; DIRTY = false;
      status = data;
      elFilePath.textContent = path;
      elShaInfo.textContent = (data.head ? '草稿 SHA: ' : '正式來源 SHA: ') + data.blobSha.slice(0, 7);
      document.querySelectorAll('.file-item').forEach(el => el.classList.toggle('active', el.dataset.path === path));
      if (SOURCE_MODE) mountSource(CURRENT_CONTENT); else mountIframe(CURRENT_CONTENT);
      if (sourceTextarea) sourceTextarea.readOnly = !!(data.legacy || data.conflict);
      document.getElementById('behindBanner').style.display = 'none';
      displayState(data); checkAutosaveOnLoad(path); scheduleWordCount();
      return true;
    } catch (failure) {
      if (loadId === EDITOR_LOAD_ID) setStatus('讀取未完成，既有編輯仍保留：' + drafts.message(failure), true);
      return false;
    } finally { if (loadId === EDITOR_LOAD_ID) EDITOR_LOADING = false; }
  };
  async function saveDraft() {
    if (SAVE_PENDING || EDITOR_LOADING) { setStatus('載入或保存尚未結束，請稍候。'); return null; }
    if (!drafts.isArticle(CURRENT_FILE)) { setStatus('目前雲端草稿支援文章；工程檔案請走專案候選發布流程。', true); return null; }
    if (!auth || !auth.getPat() || auth.isLogoutPending()) { setStatus('請先登入，編輯與暫存仍保留。', true); return null; }
    SAVE_PENDING = true;
    resetPublication();
    try {
      const snapshot = captureSaveSnapshot(), draft = drafts.capture(snapshot.file, snapshot.content);
      DIRTY = true; autosave(); setStatus('保存雲端草稿與圖片…');
      const accepted = await drafts.save(draft);
      if (!snapshotIsActive(snapshot)) return null;
      CURRENT_SHA = accepted.blobSha; elShaInfo.textContent = '草稿 SHA: ' + accepted.blobSha.slice(0, 7);
      renderRequestState(null);
      const clean = getCurrentEditorContent() === snapshot.content;
      if (clean) { CURRENT_CONTENT = snapshot.content; DIRTY = false; clearAutosaveFor(snapshot.file); lastAutosaveAt = 0; updateAutosaveIndicator(); }
      else { DIRTY = true; autosave(); }
      setStatus('雲端草稿已保存並驗證；尚未正式發布。' + (clean ? '' : '後續編輯仍未保存，暫存已保留。'));
      return { ...snapshot, branch: accepted.branch, sha: accepted.blobSha, head: accepted.head, clean };
    } catch (failure) {
      DIRTY = true; autosave(); setStatus(drafts.message(failure), true); return null;
    } finally { SAVE_PENDING = false; }
  }
  saveWithModal = saveDraft; save = saveDraft; window.save = saveDraft;
  saveAsDraft = async function (silent) { const result = await saveDraft(); return silent && result && !result.clean ? null : result; };
  for (const id of ['saveBtn', 'draftBtn']) {
    const old = document.getElementById(id), button = old.cloneNode(true);
    old.replaceWith(button); button.textContent = id === 'saveBtn' ? '保存雲端草稿' : '存草稿';
    button.title = '保存經驗證的雲端草稿；不會直接更改正式網站'; button.addEventListener('click', saveDraft);
  }
  for (const [id, label, action] of [['reviewRequestBtn', '送審', 'review'], ['cancelRequestBtn', '取消申請', 'cancel']]) {
    const button = document.createElement('button'); button.type = 'button'; button.id = id; button.textContent = label;
    button.addEventListener('click', () => openRequest(action));
    document.getElementById('draftBtn').after(button);
  }
  renderRequestState(null);
  function openRequest(action) {
    if (requestDialog) { setStatus('請先完成或關閉目前的申請視窗。'); return; }
    const editorIdentity = identity();
    if (!isCurrent(editorIdentity) || !drafts.isArticle(CURRENT_FILE)) { setStatus('請先登入並開啟文章，等待保存完成後再申請。', true); return; }
    const file = CURRENT_FILE, content = getCurrentEditorContent();
    let observed;
    try { observed = drafts.captureRequest(file, content, { action }); }
    catch (failure) { setStatus(drafts.message(failure), true); return; }
    const labels = { review: '送出這個版本審核', schedule: '申請排程發布', unpublish: '申請文章下架', cancel: '取消這個版本的申請' };
    const bg = document.createElement('div'); bg.className = 'modal-bg'; requestDialog = bg;
    const modal = new DOMParser().parseFromString('<div class="modal" role="dialog" aria-modal="true" aria-labelledby="requestDialogTitle"><h2 id="requestDialogTitle"></h2><p id="requestArticleTitle"></p><p>確認只適用這個已保存版本；再編輯需重新確認。申請保存後，仍須完成審查、CI、預覽與正式發布，才會在網站生效。</p><label id="requestTimeLabel" for="requestAt">候選準備時間（本地時間）<input id="requestAt" type="datetime-local"></label><label style="display:flex;align-items:flex-start;gap:8px"><input id="requestApproval" type="checkbox" style="width:auto"><span id="requestApprovalText"></span></label><p id="requestError" role="alert"></p><div style="display:flex;gap:8px;justify-content:flex-end"><button type="button" id="requestClose">關閉</button><button type="button" id="requestConfirm">確認申請</button></div></div>', 'text/html');
    bg.appendChild(document.importNode(modal.body.firstElementChild, true));
    bg.querySelector('#requestDialogTitle').textContent = labels[action];
    const parsed = new DOMParser().parseFromString(content, 'text/html');
    bg.querySelector('#requestArticleTitle').textContent = parsed.querySelector('h1')?.textContent.trim() || file;
    bg.querySelector('#requestApprovalText').textContent = action === 'cancel' ? '確認撤回這個版本的申請，文章與草稿保留。' :
      action === 'unpublish' ? '確認申請文章下架，正文與草稿保留。' : '我已逐句確認這個已保存版本的醫療文字、圖片與出處。';
    const time = bg.querySelector('#requestAt');
    bg.querySelector('#requestTimeLabel').hidden = action !== 'schedule';
    const later = new Date(Date.now() + 3600_000);
    time.value = new Date(later.getTime() - later.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
    const opener = document.activeElement, close = bg.querySelector('#requestClose'), submit = bg.querySelector('#requestConfirm'), checkbox = bg.querySelector('#requestApproval');
    let pending = false;
    const finish = () => { if (pending) return; bg.remove(); requestDialog = null; if (opener && opener.isConnected) opener.focus(); };
    close.addEventListener('click', finish);
    bg.addEventListener('keydown', event => {
      if (event.key === 'Escape') { event.preventDefault(); finish(); }
      if (event.key === 'Tab') {
        const controls = [time, checkbox, close, submit].filter(element => !element.disabled && element.closest('[hidden]') === null);
        const first = controls[0], last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    });
    submit.addEventListener('click', async () => {
      if (pending) return;
      const error = bg.querySelector('#requestError');
      if (!checkbox.checked) { error.textContent = '請先勾選確認；尚未送出申請。'; return; }
      const local = drafts.localState(file);
      if (!isCurrent(editorIdentity) || getCurrentEditorContent() !== content ||
          !local || local.head !== observed.expectedHead || local.blobSha !== observed.expectedBlob) {
        error.textContent = '文章、登入或已保存版本已改變；請關閉後重新確認，未送出申請。'; autosave(); return;
      }
      let snapshot;
      try {
        if (action === 'schedule' && (!Number.isFinite(new Date(time.value).getTime()) || new Date(time.value).getTime() <= Date.now())) {
          error.textContent = '請選擇有效的未來時間；尚未送出申請。'; return;
        }
        const scheduledAt = action === 'schedule' ? new Date(time.value).toISOString() : undefined;
        snapshot = drafts.captureRequest(file, content, { action, contentApproved: checkbox.checked, confirmed: checkbox.checked, scheduledAt });
      } catch (failure) { error.textContent = drafts.message(failure); return; }
      pending = true; SAVE_PENDING = true; submit.disabled = true; close.disabled = true; checkbox.disabled = true; time.disabled = true;
      resetPublication();
      autosave(); setStatus('保存與驗證這個版本的申請…');
      try {
        const accepted = await drafts.submit(snapshot);
        if (current(file, editorIdentity.loadId) && identityTokens.get(editorIdentity) === auth.getPat() && !auth.isLogoutPending()) {
          renderRequestState(accepted.request);
          if (status) { status.head = accepted.head; status.request = accepted.request; }
          const unchanged = getCurrentEditorContent() === content;
          if (unchanged) { clearAutosaveFor(file); lastAutosaveAt = 0; updateAutosaveIndicator(); }
          else { DIRTY = true; autosave(); }
          setStatus((action === 'cancel' ? '申請已撤回並驗證；文章與草稿保留。' : '申請已保存並驗證；尚未正式發布。') + (unchanged ? '' : '等待期間的新編輯已暫存，尚未保存。'));
        }
        pending = false; finish();
      } catch (failure) {
        error.textContent = drafts.message(failure); autosave();
        pending = false; submit.disabled = false; close.disabled = false; checkbox.disabled = false; time.disabled = false;
      } finally { SAVE_PENDING = false; }
    });
    document.body.appendChild(bg); checkbox.focus();
  }
  uploadImage = async function (file) {
    const target = CURRENT_FILE, alt = prompt('輸入圖片替代文字（說明圖片內容）', '');
    if (alt === null) throw new Error('已取消圖片處理，原始檔保留。');
    let blob = file;
    if (!['image/gif', 'image/svg+xml'].includes(file.type)) {
      try { blob = (await compressImage(file)).blob; }
      catch (_) { setStatus('壓縮未完成，保留原圖加入本機草稿。'); }
    }
    const staged = await drafts.stage(target, blob);
    setStatus('圖片已加入本機草稿；保存文章時會一併存到雲端。');
    return { url: staged.url, alt };
  };
  async function poll() {
    if (!drafts.isArticle(CURRENT_FILE) || SAVE_PENDING || EDITOR_LOADING || !auth.getPat()) return;
    const file = CURRENT_FILE, loadId = EDITOR_LOAD_ID, token = auth.getPat(), loaded = drafts.localState(file);
    if (!loaded) return;
    try {
      const remote = await drafts.inspect(file), now = drafts.localState(file);
      if (!current(file, loadId) || SAVE_PENDING || EDITOR_LOADING || auth.getPat() !== token || !now || now.head !== loaded.head) return;
      if (remote.head !== now.head || remote.baseSha !== now.baseSha || remote.conflict) {
        publicationLabel.textContent = '雲端版本已變更，申請狀態需重讀確認';
        document.getElementById('behindBannerText').textContent = '雲端草稿或正式文章已更新；本機編輯保留，請先比對整合。';
        document.getElementById('behindBanner').style.display = 'flex';
      }
    } catch (_) { /* A failed observation does not change content or revision. */ }
  }
  const identityTokens = new WeakMap();
  function identity() {
    const value = { file: CURRENT_FILE, loadId: EDITOR_LOAD_ID };
    identityTokens.set(value, auth.getPat()); return value;
  }
  function isCurrent(value) { return !!(value && current(value.file, value.loadId) && identityTokens.get(value) === auth.getPat() && !auth.isLogoutPending() && !SAVE_PENDING && !EDITOR_LOADING); }
  async function compareVersion(sha, value) {
    if (!isCurrent(value) || !drafts.isArticle(value.file) || !/^[a-f0-9]{40}$/.test(sha || '')) {
      setStatus('目前無法比較此版本；文章與編輯保留，請重新載入歷史。', true); return false;
    }
    openVersionHistory();
    const dialogs = Array.from(document.querySelectorAll('.modal-bg'));
    const dialog = dialogs.reverse().find(el => el.historyContext && el.historyContext.file === value.file && el.historyContext.loadId === value.loadId);
    if (!dialog) return false;
    await showCommitDiff(dialog, sha, false);
    return historyContextIsCurrent(dialog);
  }
  window.DNEditorDraftBridge = { poll, save: saveDraft, createArticle, openRequest, identity, isCurrent, compareVersion, startNewVersion };
  if (auth.getPat()) refreshFileList();
})();
