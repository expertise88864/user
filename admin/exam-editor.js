/* Exam section editor (考試重點 study notes and 題目詳解 explanations).
 * Saves go to the cloud draft branch cms-exam/drafts through /api/admin/exam-draft
 * only; nothing here edits main or publishes. Everything from the API is rendered
 * as text, and the live preview is a script-less sandboxed iframe. The overlay is
 * self-contained so it never touches the article editor's file state. */
(function () {
  'use strict';
  const auth = window.cdAdminAuth;
  const host = document.getElementById('examList');
  if (!auth || !host) return;
  const API = '/api/admin/exam-draft';
  const SAVED = '已存入雲端草稿（cms-exam/drafts）。上線需由維護流程整合、重新生成、CI 與審查後才會發佈。';
  const QID = /^\d{3}-\d{2}$/;
  const MESSAGES = {
    login_required: '登入已失效或不是管理員帳號，請重新登入；畫面上的文字已保留。',
    conflict: '版本衝突：雲端草稿或正式版在你載入後已變更。請按「重新載入」取得最新版；你目前的文字仍保留在輸入框，並已備份在這個瀏覽器。',
    same_origin_required: '請求被拒絕（需同源），請重新整理後台頁面再試。',
    too_large: '內容太大，超過上限（單次 600 KB，重點內容 400 KB）。',
    invalid_request: '請求格式不正確，請重新整理後台頁面再試；畫面上的文字已保留。',
    json_required: '請求格式不正確，請重新整理後台頁面再試；畫面上的文字已保留。',
    unknown_note: '找不到這一章的重點檔。',
    unknown_question: '找不到這個題號的詳解。',
    invalid_id: '題號格式需為 YYY-NN，例如 101-01。',
    invalid_chapter: '章節編號不正確。',
    invalid_revision: '版本資訊不正確，請按「重新載入」。',
    invalid_draft_record: '雲端草稿紀錄異常，已停止寫入；請聯絡維護者檢查 cms-exam/drafts 分支。',
    format_mismatch: '詳解檔格式與產生器預期不符，為避免破壞資料已停止寫入（未存檔）；請聯絡維護者。',
    save_not_verified: '雲端未能核對剛才的存檔，請按「重新載入」確認結果後再決定是否重存。',
    github_token_invalid: 'GitHub token 無效或已過期，請清除登入後重新登入；畫面上的文字已保留。',
    github_rate_limited: 'GitHub API 使用量已達上限，請稍後再試；畫面上的文字已保留。',
    github_forbidden: 'GitHub 拒絕存取：token 可能沒有 expertise88864/user 的權限；畫面上的文字已保留。',
    github_timeout: '連線 GitHub 逾時，請稍後再試；畫面上的文字已保留。',
    draft_unavailable: '暫時無法連線，請稍後再試；畫面上的文字已保留。',
  };
  function describe(error) {
    const code = error && error.code;
    if (code === 'invalid_note') return '重點內容被拒絕：' + (error.reason || '格式不符');
    if (code === 'invalid_entry') return '詳解內容被拒絕：' + (error.path ? error.path + ' ' : '') + (error.reason || '格式不符');
    if (code === 'too_large' && error.reason) return '內容太大：' + error.reason;
    if (code && Object.prototype.hasOwnProperty.call(MESSAGES, code)) return MESSAGES[code];
    return '操作未完成（' + (code || 'request_failed') + '）；畫面上的文字已保留。';
  }

  function el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(attrs || {})) {
      if (name === 'text') node.textContent = value;
      else if (name === 'class') node.className = value;
      else if (value === true) node.setAttribute(name, '');
      else if (value !== false && value != null) node.setAttribute(name, String(value));
    }
    node.append(...children);
    return node;
  }
  async function api(query, options) {
    const response = await fetch(API + query, Object.assign({ credentials: 'same-origin', cache: 'no-store',
      headers: { Accept: 'application/json' } }, options || {}));
    let data = null;
    try { data = await response.json(); } catch (_) { data = null; }
    if (!response.ok || !data || data.ok !== true) {
      const failure = new Error('exam-draft request failed');
      failure.code = data && typeof data.error === 'string' ? data.error : 'request_failed';
      failure.reason = data && typeof data.reason === 'string' ? data.reason : '';
      failure.path = data && typeof data.path === 'string' ? data.path : '';
      throw failure;
    }
    return data;
  }
  function post(body) {
    return api('', { method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  }
  const loggedIn = () => !!auth.getPat() && !auth.isLogoutPending();

  // ------------------------------------------------------------ local backup
  const backupKey = (kind, key) => 'dn-exam-draft-backup:' + kind + ':' + key;
  function stash(kind, key, value) {
    try { localStorage.setItem(backupKey(kind, key), JSON.stringify({ value, at: Date.now() })); } catch (_) { /* Backup is best effort. */ }
  }
  function stashed(kind, key) {
    try { const item = JSON.parse(localStorage.getItem(backupKey(kind, key))); return item && item.value !== undefined ? item.value : null; }
    catch (_) { return null; }
  }
  function unstash(kind, key) { try { localStorage.removeItem(backupKey(kind, key)); } catch (_) { /* Ignore. */ } }

  // ------------------------------------------------------------ sidebar
  const model = { notes: [], draft: { exists: false, notes: [], explanations: [], updated: null }, error: '' };
  let loadedToken = null, generation = 0;
  function heading(text) {
    return el('div', { class: 'exam-group-title', role: 'heading', 'aria-level': '3', text });
  }
  function row(label, draftMark, attrs, action) {
    const node = el('button', Object.assign({ type: 'button', class: 'exam-item' }, attrs), el('span', { class: 'exam-item-name', text: label }));
    if (draftMark) node.append(el('span', { class: 'exam-draft-mark', text: ' · 雲端草稿' }));
    node.addEventListener('click', () => action(node));
    return node;
  }
  function render() {
    if (!loggedIn()) { host.hidden = true; host.replaceChildren(); return; }
    host.hidden = false;
    const kids = [heading('考試重點（' + model.notes.length + '）')];
    if (model.error) {
      const retry = el('button', { type: 'button', class: 'exam-item', id: 'examRetry', text: '重試讀取考試區清單' });
      retry.addEventListener('click', () => load(true));
      kids.push(el('p', { class: 'exam-note', role: 'status', text: model.error }), retry);
    }
    const notes = el('div', { class: 'exam-rows', id: 'examNoteRows' });
    const marked = new Set(model.draft.notes);
    for (const item of model.notes) {
      const label = 'Ch.' + item.ch + (item.title ? ' ' + item.title : '');
      notes.append(row(label, marked.has(item.ch), { 'data-exam-note': item.ch, title: item.title || '' }, node => openNote(item.ch, node)));
    }
    kids.push(notes, heading('題目詳解'));
    kids.push(row('編輯題目詳解…', false, { id: 'examExplOpen' }, node => openExplanation(null, node)));
    for (const id of model.draft.explanations) {
      kids.push(row(id, true, { 'data-exam-expl': id }, node => openExplanation(id, node)));
    }
    host.replaceChildren(...kids);
  }
  async function load(force) {
    if (!loggedIn()) { loadedToken = null; generation++; model.notes = []; render(); return; }
    const token = auth.getPat();
    if (!force && loadedToken === token) return;
    const mine = ++generation;
    try {
      const data = await api('?mode=list');
      if (mine !== generation || token !== auth.getPat()) return;
      model.notes = data.notes; model.draft = data.draft; model.error = ''; loadedToken = token;
    } catch (error) {
      if (mine !== generation) return;
      model.error = '考試區清單暫時無法讀取（' + (error.code || 'request_failed') + '）。';
      loadedToken = null;
    }
    render();
  }
  function updateDraft(draft) {
    if (draft && Array.isArray(draft.notes) && Array.isArray(draft.explanations)) { model.draft = draft; render(); }
  }

  // ------------------------------------------------------------ overlay
  let overlay = null, mode = null, returnFocus = null, returnSelector = '', busy = false;
  const note = { ch: null, base: '', blobSha: null, source: '', loaded: false };
  const expl = { id: null, blobSha: null, snapshot: '', source: '', fields: null, entry: null, loaded: false };

  function buildOverlay() {
    const title = el('h2', { id: 'examDialogTitle', text: '' });
    const close = el('button', { type: 'button', id: 'examClose', class: 'exam-btn', 'aria-label': '關閉', text: '關閉' });
    const status = el('p', { id: 'examStatus', class: 'exam-status', role: 'status', 'aria-live': 'polite' });
    const save = el('button', { type: 'button', id: 'examSave', class: 'exam-btn exam-primary', text: '存成雲端草稿' });
    const reload = el('button', { type: 'button', id: 'examReload', class: 'exam-btn', text: '重新載入' });
    const restore = el('button', { type: 'button', id: 'examRestore', class: 'exam-btn', hidden: true, text: '還原本機備份' });
    const source = el('textarea', { id: 'examNoteSource', class: 'exam-source', spellcheck: 'false', 'aria-label': '考試重點原始碼', wrap: 'off' });
    const preview = el('iframe', { id: 'examPreview', class: 'exam-preview', title: '考試重點預覽' });
    preview.setAttribute('sandbox', '');
    const notePanel = el('div', { class: 'exam-panel exam-note-panel', id: 'examNotePanel', hidden: true },
      el('div', { class: 'exam-pane' }, el('label', { class: 'exam-label', for: 'examNoteSource', text: '原始碼（僅限站內允許的標籤與 class）' }), source),
      el('div', { class: 'exam-pane' }, el('span', { class: 'exam-label', text: '預覽（套用考試區樣式，不執行任何腳本）' }), preview));
    const explId = el('input', { id: 'examExplId', class: 'exam-input', type: 'text', placeholder: '101-01', autocomplete: 'off', maxlength: '6', 'aria-label': '題號（YYY-NN）' });
    const explLoad = el('button', { type: 'button', id: 'examExplLoad', class: 'exam-btn', text: '載入' });
    const form = el('div', { id: 'examExplForm', class: 'exam-form' });
    const explPanel = el('div', { class: 'exam-panel exam-expl-panel', id: 'examExplPanel', hidden: true },
      el('div', { class: 'exam-idrow' }, el('label', { class: 'exam-label', for: 'examExplId', text: '題號' }), explId, explLoad),
      el('p', { class: 'exam-hint', text: '只能修改既有題目的詳解。文字中可用 [i]菌名[/i] 表示斜體（學名）。摘要、標籤與說明不可換行。參考頁碼格式：章節:頁碼（數字或 266-267），多筆以分號分隔，例如 81:1462-1463; M:120（M 代表 McKee）。' }),
      form);
    const dialog = el('div', { class: 'exam-dialog', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'examDialogTitle', tabindex: '-1' },
      el('header', { class: 'exam-dialog-head' }, title, close),
      el('div', { class: 'exam-dialog-body' }, notePanel, explPanel),
      el('footer', { class: 'exam-dialog-foot' }, status, el('div', { class: 'exam-actions' }, restore, reload, save)));
    const root = el('div', { class: 'exam-overlay', id: 'examOverlay', hidden: true }, dialog);
    document.body.append(root);
    close.addEventListener('click', requestClose);
    save.addEventListener('click', () => (mode === 'note' ? saveNote() : saveExplanation()));
    reload.addEventListener('click', () => (mode === 'note' ? reloadNote() : reloadExplanation()));
    restore.addEventListener('click', () => (mode === 'note' ? restoreNote() : restoreExplanation()));
    explLoad.addEventListener('click', () => loadExplanation(explId.value.trim(), true));
    explId.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); loadExplanation(explId.value.trim(), true); } });
    let timer = 0;
    source.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(renderPreview, 300); });
    root.addEventListener('keydown', trapTab);
    return { root, dialog, title, status, save, reload, restore, source, preview, notePanel, explPanel, explId, explLoad, form };
  }
  function renderPreview() {
    if (!overlay) return;
    overlay.preview.srcdoc = '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">' +
      '<link rel="stylesheet" href="/admin/exam-preview.css"></head><body><main class="ex-main">' + overlay.source.value + '</main></body></html>';
  }
  function setStatus(text, kind) {
    overlay.status.textContent = text || '';
    overlay.status.className = 'exam-status' + (kind ? ' exam-' + kind : '');
  }
  function setBusy(value) {
    busy = value;
    overlay.save.disabled = value || !isLoaded();
    overlay.reload.disabled = value;
    overlay.explLoad.disabled = value;
  }
  const isLoaded = () => (mode === 'note' ? note.loaded : expl.loaded);
  function dirty() {
    if (!overlay || overlay.root.hidden) return false;
    if (mode === 'note') return note.loaded && overlay.source.value !== note.base;
    return expl.loaded && rawState() !== expl.snapshot;
  }
  function openOverlay(kind, titleText, trigger) {
    overlay = overlay || buildOverlay();
    mode = kind;
    returnFocus = trigger || document.activeElement;
    // The sidebar is rebuilt after a save, so remember how to find the row again.
    const data = returnFocus && returnFocus.dataset ? returnFocus.dataset : {};
    returnSelector = data.examNote ? '[data-exam-note="' + data.examNote + '"]' : data.examExpl ? '[data-exam-expl="' + data.examExpl + '"]'
      : returnFocus && returnFocus.id === 'examExplOpen' ? '#examExplOpen' : '';
    overlay.title.textContent = titleText;
    overlay.notePanel.hidden = kind !== 'note';
    overlay.explPanel.hidden = kind !== 'expl';
    overlay.restore.hidden = true;
    overlay.root.hidden = false;
    for (const node of [document.querySelector('header.top'), document.getElementById('main-content')]) if (node) node.inert = true;
    document.addEventListener('keydown', onEscape, true);
    setStatus('');
    setBusy(false);
  }
  function closeOverlay() {
    overlay.root.hidden = true;
    for (const node of [document.querySelector('header.top'), document.getElementById('main-content')]) if (node) node.inert = false;
    document.removeEventListener('keydown', onEscape, true);
    note.loaded = false; expl.loaded = false;
    overlay.preview.srcdoc = '';
    const target = returnFocus && document.contains(returnFocus) ? returnFocus : returnSelector ? host.querySelector(returnSelector) : null;
    if (target && typeof target.focus === 'function') target.focus();
    returnFocus = null; returnSelector = '';
  }
  function requestClose() {
    if (dirty() && !window.confirm('有尚未存成雲端草稿的修改，確定要關閉嗎？（關閉後這些修改會遺失）')) return false;
    closeOverlay();
    return true;
  }
  function onEscape(event) {
    if (event.key !== 'Escape' || !overlay || overlay.root.hidden) return;
    event.preventDefault(); event.stopPropagation();
    requestClose();
  }
  function trapTab(event) {
    if (event.key !== 'Tab') return;
    const nodes = Array.from(overlay.dialog.querySelectorAll('button, textarea, input, [tabindex]:not([tabindex="-1"])'))
      .filter(node => !node.disabled && !node.closest('[hidden]'));
    if (!nodes.length) return;
    const first = nodes[0], last = nodes[nodes.length - 1];
    if (event.shiftKey && (document.activeElement === first || document.activeElement === overlay.dialog)) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
  const stillSignedIn = loggedIn;

  // ------------------------------------------------------------ note editor
  async function openNote(ch, trigger) {
    openOverlay('note', '考試重點 · Ch.' + ch, trigger);
    note.ch = ch; note.loaded = false;
    overlay.source.value = ''; overlay.source.disabled = true; renderPreview();
    await fetchNote();
    if (note.loaded) overlay.source.focus(); else overlay.dialog.focus();
  }
  async function fetchNote() {
    const ch = note.ch;
    setBusy(true); setStatus('載入中…');
    try {
      const data = await api('?kind=note&ch=' + encodeURIComponent(ch));
      if (!overlay || overlay.root.hidden || mode !== 'note' || note.ch !== ch) return;
      note.base = data.content; note.blobSha = data.blobSha; note.source = data.source; note.loaded = true;
      overlay.source.disabled = false; overlay.source.value = data.content; renderPreview();
      const backup = stashed('note', ch);
      overlay.restore.hidden = !(typeof backup === 'string' && backup !== data.content);
      setStatus('已載入（來源：' + (data.source === 'draft' ? '雲端草稿' : '正式版 main') + '）。' + (overlay.restore.hidden ? '' : '偵測到先前未存成功的本機備份，可按「還原本機備份」。'));
    } catch (error) { setStatus(describe(error), 'err'); }
    setBusy(false);
  }
  async function reloadNote() {
    if (dirty() && !window.confirm('重新載入會捨棄目前輸入框的修改（已備份在這個瀏覽器，可按「還原本機備份」取回）。確定嗎？')) return;
    if (dirty()) stash('note', note.ch, overlay.source.value);
    await fetchNote();
  }
  function restoreNote() {
    const backup = stashed('note', note.ch);
    if (typeof backup !== 'string') return;
    overlay.source.value = backup; renderPreview(); overlay.restore.hidden = true;
    setStatus('已還原本機備份；確認後按「存成雲端草稿」。');
  }
  async function saveNote() {
    if (busy || !note.loaded) return;
    if (!stillSignedIn()) { setStatus(MESSAGES.login_required, 'err'); return; }
    const content = overlay.source.value, ch = note.ch;
    setBusy(true); setStatus('正在存入雲端草稿並核對…');
    try {
      const result = await post({ kind: 'note', ch, content, baseBlobSha: note.blobSha });
      note.blobSha = result.blobSha; note.base = content; note.source = 'draft';
      unstash('note', ch); overlay.restore.hidden = true;
      updateDraft(result.draft);
      setStatus(SAVED, 'ok');
    } catch (error) {
      stash('note', ch, content);
      setStatus(describe(error), 'err');
    }
    setBusy(false);
  }

  // ------------------------------------------------------------ explanation editor
  function formatRefs(refs) { return refs.map(ref => ref[0] + ':' + ref[1]).join('; '); }
  function parseRefs(text) {
    const rows = text.split(';').map(part => part.trim()).filter(Boolean);
    return rows.map(part => {
      const at = part.indexOf(':');
      const chapter = at > 0 ? part.slice(0, at).trim() : '', page = at > 0 ? part.slice(at + 1).trim() : '';
      if (!(chapter === 'M' || /^\d{1,4}$/.test(chapter)) || !page) throw new Error('參考頁碼格式應為「章節:頁碼」，多筆以分號分隔，例如 81:1462-1463; M:120');
      return [chapter === 'M' ? 'M' : Number(chapter), page];
    });
  }
  let fieldCount = 0;
  function field(labelText, control, hint) {
    const id = control.id || ('examField' + (++fieldCount));
    control.id = id;
    return el('div', { class: 'exam-field' }, el('label', { class: 'exam-label', for: id, text: labelText }), control,
      hint ? el('span', { class: 'exam-hint', text: hint }) : '');
  }
  function buildExplForm(entry) {
    const form = overlay.form;
    const fields = { summary: el('textarea', { class: 'exam-input exam-area', rows: '3', 'aria-label': '摘要' }), items: [],
      flags: el('textarea', { class: 'exam-input exam-area', rows: '2' }), dispute: el('textarea', { class: 'exam-input exam-area exam-mono', rows: '6', spellcheck: 'false' }) };
    fields.summary.value = entry.summary;
    fields.flags.value = (entry.flags || []).join('\n');
    fields.dispute.value = entry.dispute ? JSON.stringify(entry.dispute, null, 2) : '';
    const kids = [field('摘要（summary）', fields.summary)];
    entry.items.forEach(item => {
      const parts = { key: item.key, label: el('input', { class: 'exam-input', type: 'text' }), ok: el('input', { type: 'checkbox' }),
        text: el('textarea', { class: 'exam-input exam-area', rows: '4' }), refs: el('input', { class: 'exam-input', type: 'text', placeholder: '81:1462-1463; M:120' }) };
      parts.label.value = item.label; parts.ok.checked = item.ok; parts.text.value = item.text; parts.refs.value = formatRefs(item.refs);
      fields.items.push(parts);
      const okId = 'examOk' + fields.items.length;
      parts.ok.id = okId;
      kids.push(el('fieldset', { class: 'exam-item-set' }, el('legend', { text: '選項 ' + item.key + '（代號固定）' }),
        field('標籤（label）', parts.label),
        el('div', { class: 'exam-field exam-check' }, parts.ok, el('label', { for: okId, text: '此選項為正確敘述（ok）' })),
        field('說明（text）', parts.text),
        field('參考頁碼（refs）', parts.refs)));
    });
    kids.push(field('附註（flags，每行一則，可留空）', fields.flags),
      field('疑義（dispute，JSON；留空表示沒有）', fields.dispute, '欄位：kind、exam，另可有 current、sources（title、url、year，可有 pmid）。'));
    form.replaceChildren(...kids);
    return fields;
  }
  function rawOf(fields) {
    return { summary: fields.summary.value, flags: fields.flags.value, dispute: fields.dispute.value,
      items: fields.items.map(item => ({ key: item.key, label: item.label.value, ok: item.ok.checked, text: item.text.value, refs: item.refs.value })) };
  }
  function rawState() { return expl.fields ? JSON.stringify(rawOf(expl.fields)) : ''; }
  function entryFromForm() {
    const raw = rawOf(expl.fields);
    if (!raw.summary.trim()) throw new Error('摘要不可空白。');
    if (/[\r\n]/.test(raw.summary)) throw new Error('摘要不可換行，請寫成同一行。');
    const entry = { summary: raw.summary, items: raw.items.map(item => {
      if (!item.label.trim() || !item.text.trim()) throw new Error('選項 ' + item.key + ' 的標籤與說明不可空白。');
      if (/[\r\n]/.test(item.label + item.text)) throw new Error('選項 ' + item.key + ' 的標籤與說明不可換行，請寫成同一行。');
      let refs;
      try { refs = parseRefs(item.refs); } catch (error) { throw new Error('選項 ' + item.key + '：' + error.message); }
      return { key: item.key, label: item.label, ok: item.ok, text: item.text, refs };
    }) };
    const flags = raw.flags.split('\n').map(line => line.trim()).filter(Boolean);
    if (flags.length) entry.flags = flags;
    if (raw.dispute.trim()) {
      try { entry.dispute = JSON.parse(raw.dispute); } catch (_) { throw new Error('疑義（dispute）不是有效的 JSON。'); }
    }
    return entry;
  }
  function openExplanation(id, trigger) {
    openOverlay('expl', '題目詳解', trigger);
    expl.loaded = false; expl.fields = null; expl.id = null;
    overlay.form.replaceChildren();
    overlay.explId.value = id || '';
    setStatus(id ? '' : '輸入題號後按「載入」。');
    if (id) loadExplanation(id, false); else overlay.explId.focus();
  }
  async function loadExplanation(id, confirmDiscard) {
    if (busy) return;
    if (!QID.test(id)) { setStatus(MESSAGES.invalid_id, 'err'); return; }
    if (confirmDiscard && dirty() && !window.confirm('載入其他題目會捨棄目前的修改（已備份在這個瀏覽器）。確定嗎？')) return;
    if (dirty()) stash('expl', expl.id, rawOf(expl.fields));
    setBusy(true); setStatus('載入中…');
    expl.loaded = false;
    try {
      const data = await api('?kind=expl&id=' + encodeURIComponent(id));
      if (!overlay || overlay.root.hidden || mode !== 'expl') return;
      expl.id = id; expl.blobSha = data.blobSha; expl.source = data.source; expl.entry = data.entry;
      expl.fields = buildExplForm(data.entry); expl.snapshot = rawState(); expl.loaded = true;
      overlay.explId.value = id;
      const backup = stashed('expl', id);
      overlay.restore.hidden = !(backup && typeof backup === 'object' && JSON.stringify(backup) !== expl.snapshot);
      setStatus('已載入 ' + id + '（來源：' + (data.source === 'draft' ? '雲端草稿' : '正式版 main') + '）。' + (overlay.restore.hidden ? '' : '偵測到先前未存成功的本機備份，可按「還原本機備份」。'));
    } catch (error) {
      overlay.form.replaceChildren(); expl.fields = null; overlay.restore.hidden = true;
      setStatus(describe(error), 'err');
    }
    setBusy(false);
  }
  async function reloadExplanation() {
    if (!expl.id) { setStatus('請先輸入題號並載入。'); return; }
    if (dirty() && !window.confirm('重新載入會捨棄目前表單的修改（已備份在這個瀏覽器，可按「還原本機備份」取回）。確定嗎？')) return;
    await loadExplanation(expl.id, false);
  }
  function restoreExplanation() {
    const backup = stashed('expl', expl.id);
    if (!backup || typeof backup !== 'object' || !expl.fields || !Array.isArray(backup.items)) return;
    const fields = expl.fields;
    fields.summary.value = String(backup.summary || ''); fields.flags.value = String(backup.flags || ''); fields.dispute.value = String(backup.dispute || '');
    fields.items.forEach(item => {
      const saved = backup.items.find(candidate => candidate && candidate.key === item.key);
      if (!saved) return;
      item.label.value = String(saved.label || ''); item.ok.checked = saved.ok === true; item.text.value = String(saved.text || ''); item.refs.value = String(saved.refs || '');
    });
    overlay.restore.hidden = true;
    setStatus('已還原本機備份；確認後按「存成雲端草稿」。');
  }
  async function saveExplanation() {
    if (busy || !expl.loaded) return;
    if (!stillSignedIn()) { setStatus(MESSAGES.login_required, 'err'); return; }
    let entry;
    try { entry = entryFromForm(); } catch (error) { setStatus(error.message, 'err'); return; }
    const id = expl.id, snapshot = rawState();
    setBusy(true); setStatus('正在存入雲端草稿並核對…');
    try {
      const result = await post({ kind: 'expl', id, entry, baseBlobSha: expl.blobSha });
      expl.blobSha = result.blobSha; expl.source = 'draft'; expl.snapshot = snapshot;
      unstash('expl', id); overlay.restore.hidden = true;
      updateDraft(result.draft);
      setStatus(SAVED, 'ok');
    } catch (error) {
      stash('expl', id, rawOf(expl.fields));
      setStatus(describe(error), 'err');
    }
    setBusy(false);
  }

  // ------------------------------------------------------------ wiring
  window.addEventListener('cd-admin-auth-changed', () => {
    load(false);
    if (overlay && !overlay.root.hidden) {
      if (stillSignedIn()) setBusy(busy);
      else { setStatus('登入狀態已變更；畫面上的文字已保留，請重新登入後再存。', 'err'); overlay.save.disabled = true; }
    }
  });
  if (typeof refreshFileList === 'function') {
    const originalRefresh = refreshFileList;
    refreshFileList = async function () {
      try { await originalRefresh(); } finally { load(false); }
    };
  }
  window.addEventListener('beforeunload', event => { if (dirty()) { event.preventDefault(); event.returnValue = ''; } });
  load(false);
})();
