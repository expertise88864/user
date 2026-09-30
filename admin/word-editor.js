// Opt-in authored-content editor. All persistence stays in the draft bridge.
(function () {
  'use strict';
  const drafts = window.DNArticleDrafts, bridge = window.DNEditorDraftBridge;
  if (!drafts || !bridge) return;
  const auth = window.cdAdminAuth;
  const originalContent = getCurrentEditorContent, originalMount = mountIframe, originalSource = mountSource, originalLoad = loadFile;
  let active = null, loading = null, fresh = null;
  const button = document.createElement('button');
  button.type = 'button'; button.id = 'wordEditBtn'; button.textContent = 'Word 編輯';
  button.title = '整理貼上的段落與圖片；特殊區塊保留原稿'; button.setAttribute('aria-pressed', 'false');
  document.getElementById('sourceBtn').before(button);
  const commands = {boldBtn:'bold',italicBtn:'italic',underlineBtn:'underline',strikeBtn:'strike',
    h2Btn:'h2',h3Btn:'h3',h4Btn:'h4',ulBtn:'bullet',olBtn:'ordered'};
  const unsupported = ['quoteBtn','codeBtn','alignLeftBtn','alignCenterBtn','alignRightBtn','colorPick','sizeSel','weightSel','clearFmtBtn',
    'linkBtn','tableBtn','imageLibBtn','citeBtn','metaBtn','bilingualEditBtn','bilingualBtn','spellBtn',
    'axFontPreview','axDictRun','axDictUndo','axFaqGen','axSpellRun'];

  function same(value) {
    return CURRENT_FILE === value.file && EDITOR_LOAD_ID === value.loadId && !EDITOR_LOADING &&
      auth.getPat() === value.token && !auth.isLogoutPending();
  }
  function key(value) {
    const state = drafts.localState(value.file);
    return same(value) && state ? JSON.stringify([value.file,value.loadId,state.head,state.baseSha,state.blobSha]) : null;
  }
  function content() {
    if (!active) return originalContent();
    if (!same(active)) throw Error('文章已切換，請保留暫存並重讀；未保存舊文章。');
    return active.region.assemble(active.editor.serialize());
  }
  getCurrentEditorContent = content;
  function detach() {
    if (!active) return;
    const prior = active; active = null;
    prior.observer.disconnect(); prior.editor.destroy(); prior.panel.remove();
    if (prior.host.isConnected) { prior.host.hidden = prior.hidden; prior.host.style.display = prior.display; }
    for (const {control,disabled,title} of prior.controls) { control.disabled = disabled; control.title = title; }
    button.textContent = 'Word 編輯'; button.setAttribute('aria-pressed', 'false');
  }
  mountIframe = function (html) {
    detach(); const result=originalMount(html);
    const value={html,file:CURRENT_FILE,loadId:EDITOR_LOAD_ID,frame:editFrame,preview:null};fresh=value;
    value.frame.addEventListener('load',()=>{if(fresh===value&&CURRENT_FILE===value.file&&EDITOR_LOAD_ID===value.loadId&&editFrame===value.frame)value.preview=originalContent();},{once:true});
    return result;
  };
  mountSource = function (html) { detach(); fresh=null; return originalSource(html); };
  loadFile = async function (file) {
    const previous = active;
    const result = await originalLoad(file);
    // A failed read advances the load generation but leaves the old editor.
    // Rebind only that surviving editor, never a concurrent/new mount.
    if (result === false && previous && active === previous && CURRENT_FILE === previous.file &&
        editFrame === previous.frame && !EDITOR_LOADING && auth.getPat() === previous.token && !auth.isLogoutPending()) {
      previous.loadId = EDITOR_LOAD_ID;
    }
    return result;
  };
  function loadModel() {
    if (window.DNWordModel) return Promise.resolve(window.DNWordModel);
    if (loading) return loading;
    loading = new Promise((resolve,reject) => {
      const script = document.createElement('script');
      script.src = '/admin/word-model.bundle.js';
      const timer = setTimeout(() => fail(), 20_000);
      function fail() { clearTimeout(timer); script.remove(); loading = null; reject(Error('編輯器暫時無法載入，原稿與目前編輯保留。')); }
      script.onerror = fail;
      script.onload = () => { clearTimeout(timer); if (!window.DNWordModel) return fail(); resolve(window.DNWordModel); };
      document.head.appendChild(script);
    });
    return loading;
  }
  function notify(value) {
    if (active !== value) return;
    const state = value.editor.status(), issueCount = value.editor.imageIssues().length;
    value.message.textContent = state.destroyed ? '編輯器已停止；原稿與可恢復暫存保留，請使用原始碼模式。' :
      state.pastePending ? '正在整理圖片，請稍候再存檔。' : value.mount.dataset.pasteError ||
      (issueCount ? issueCount + ' 張圖片尚缺說明，可開啟「圖片說明／排序」補上。' : '貼上圖文會保存在草稿；SVG 與互動區塊保留原稿。');
    value.panel.dataset.busy = String(state.pastePending);
  }
  function control(label, callback) {
    const element = document.createElement('button'); element.type = 'button'; element.textContent = label;
    element.addEventListener('click', () => {
      try { if (!active || !same(active)) throw Error('文章已切換，操作未套用。'); callback(active); }
      catch (error) { setStatus(error.message, true); }
    });
    return element;
  }
  function imagePanel(value) {
    if (value.editor.status().pastePending || value.editor.status().composing) throw Error('請完成圖片整理或中文選字後再調整圖片。');
    const existing = value.panel.querySelector('.word-image-list');
    if (existing) { existing.remove(); return; }
    const list = document.createElement('div'); list.className = 'word-image-list';
    const images = value.editor.images();
    if (!images.length) { list.textContent = '目前沒有可調整的圖片。'; value.panel.appendChild(list); return; }
    images.forEach((image,index) => {
      const row = document.createElement('div'); row.className = 'word-image-row';
      const label = document.createElement('label'); label.textContent = '圖片 ' + (index + 1) + ' 說明';
      const input = document.createElement('input'); input.type = 'text'; input.maxLength = 300; input.value = image.alt || '';
      label.appendChild(input); row.appendChild(label);
      const revision = value.editor.status().revision;
      function apply(callback) {
        if (active !== value || !same(value) || value.editor.status().revision !== revision || value.editor.status().pastePending || value.editor.status().composing) {
          throw Error('圖片內容或位置已變更，請重新開啟圖片說明；尚未套用。');
        }
        callback(); list.remove(); imagePanel(value);
      }
      row.appendChild(control('套用說明', () => apply(() => value.editor.setImageAlt(index, input.value))));
      if (index > 0) row.appendChild(control('往前', () => apply(() => value.editor.moveImage(index,index-1))));
      if (index < images.length - 1) row.appendChild(control('往後', () => apply(() => value.editor.moveImage(index,index+1))));
      list.appendChild(row);
    });
    value.panel.appendChild(list);
  }
  async function enter() {
    if (SAVE_PENDING || EDITOR_LOADING || BILINGUAL_MODE || !(SOURCE_MODE?sourceTextarea:editFrame) || !drafts.isArticle(CURRENT_FILE)) {
      throw Error('請先開啟文章，完成目前存檔後再使用 Word 編輯。');
    }
    const mode=SOURCE_MODE, textarea=sourceTextarea;
    const value = {file:CURRENT_FILE,loadId:EDITOR_LOAD_ID,token:auth.getPat(),frame:editFrame,host:mode?textarea:editFrame};
    // The iframe is a sanitized preview: its serializer can normalize SVG or
    // omit scripts. A clean mode transition must use the exact loaded source.
    const previewSnapshot=originalContent(), source=mode?previewSnapshot:drafts.canonical(value.file,CURRENT_CONTENT);
    const cleanPreview=!DIRTY||fresh&&fresh.file===value.file&&fresh.loadId===value.loadId&&fresh.frame===value.frame&&fresh.html===CURRENT_CONTENT&&fresh.preview===previewSnapshot;
    if(!mode&&!cleanPreview)throw Error('原有預覽模式已有修改，請先切到原始碼確認內容，再開啟 Word 編輯；目前編輯保留。');
    drafts.capture(value.file, source); // Assert writable draft context; no request.
    const model = await loadModel();
    if (!same(value) || active || editFrame !== value.frame || SOURCE_MODE!==mode || sourceTextarea!==textarea || BILINGUAL_MODE || SAVE_PENDING || originalContent() !== previewSnapshot || !mode&&drafts.canonical(value.file,CURRENT_CONTENT)!==source) {
      throw Error('載入期間文章或文字已變更，請再開啟 Word 編輯；目前內容保留。');
    }
    const region = model.articleRegion(source), panel = document.createElement('section');
    panel.className = 'word-editor-panel'; panel.setAttribute('aria-label','Word 文章編輯');
    const tools = document.createElement('div'); tools.className = 'word-editor-tools';
    tools.appendChild(control('復原', current => current.editor.command('undo')));
    tools.appendChild(control('重做', current => current.editor.command('redo')));
    tools.appendChild(control('段落', current => current.editor.command('paragraph')));
    tools.appendChild(control('圖片說明／排序', imagePanel));
    const message = document.createElement('p'); message.className = 'word-editor-message'; message.setAttribute('role','status');
    const mount = document.createElement('div'); mount.className = 'word-document';
    panel.append(tools,message,mount); elFrameWrap.appendChild(panel);
    Object.assign(value,{region,panel,message,mount,hidden:value.host.hidden,display:value.host.style.display,controls:[]});
    try {
      value.editor = model.createEditor(mount,region.inner,{file:value.file,contextKey:()=>key(value),editable:()=>same(value),
        prepareImages:blobs=>drafts.prepareImages(value.file,blobs),
        imagePreview:path=>{const doc=document.implementation.createHTMLDocument(''),img=doc.createElement('img');img.setAttribute('src',path);doc.body.appendChild(img);drafts.preview(value.file,doc);return img.getAttribute('src');},
        onChange:()=>{if(active===value&&same(value)){DIRTY=true;scheduleWordCount();document.dispatchEvent(new Event('cd-editor-content-changed'));notify(value);}}
      });
      for (const id of unsupported) {
        const element = document.getElementById(id); if (!element) continue;
        value.controls.push({control:element,disabled:element.disabled,title:element.title});
        element.disabled = true; element.title = '這項操作請先切回原有編輯或原始碼模式。';
      }
      value.host.hidden = true; value.host.style.display = 'none'; SOURCE_MODE=false;
      value.observer = new MutationObserver(()=>notify(value));
      value.observer.observe(mount,{attributes:true,attributeFilter:['data-paste-error','data-paste-state','data-recovery-required']});
      active = value; button.textContent = '回原有編輯'; button.setAttribute('aria-pressed','true');
      notify(value); value.editor.view.focus();
    } catch (error) { value.editor?.destroy(); panel.remove(); throw error; }
  }
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      if (active) { const source=content(); CURRENT_CONTENT=source; mountIframe(source); }
      else await enter();
    } catch (error) { setStatus(error.message,true); }
    finally { button.disabled=false; }
  });
  // Existing formatting listeners target the iframe. Intercept supported
  // commands before they can edit that hidden, out-of-date preview.
  document.getElementById('toolbarWrap').addEventListener('click', event => {
    if (!active) return;
    const target=event.target.closest('button'), name=target && commands[target.id];
    if (!name) return;
    event.preventDefault(); event.stopImmediatePropagation();
    try { active.editor.command(name); } catch (error) { setStatus(error.message,true); }
  },true);
  document.getElementById('imageInput').addEventListener('change', event => {
    if (!active) return;
    event.preventDefault(); event.stopImmediatePropagation();
    const value=active, files=[...event.target.files]; event.target.value='';
    if(!files.length)return;
    value.editor.pasteContent('',files).then(()=>{notify(value);autosave();}).catch(error=>{if(active===value)setStatus(error.message,true);});
  },true);
  window.DNWordEditor = {active:()=>!!active,status:()=>active?.editor.status(),source:content,
    text:()=>active ? active.editor.view.dom.textContent : ''};
})();
