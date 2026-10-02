// Article-draft client. Revision expectations belong to the content the author
// actually loaded, never to a branch SHA fetched immediately before a write.
(function () {
  'use strict';
  const contexts = new Map(), generations = new Map();
  const MAX_BODY = 3_500_000;
  const SHA = /^[a-f0-9]{40}$/;
  const labels = {
    login_required: '登入已失效，請重新登入；編輯與暫存仍保留。',
    draft_conflict: '雲端草稿或正式文章已有新版本，請先比對並整合；未覆寫任何版本。',
    legacy_draft_requires_review: '這篇有舊版雲端草稿，需先比對整合；目前僅供檢視。',
    draft_too_large: '草稿與圖片超過單次存檔大小，請先壓縮圖片；本機內容仍保留。',
    save_not_verified: '雲端可能已接受，但內容驗證未完成；請重讀確認，勿重複寫入。',
    unsupported_image: '此圖片格式尚未支援草稿上傳，原始檔保留；SVG 請先另存為 PNG 或 WebP。',
    article_exists: '這個文章網址已有正式文章或雲端草稿，請從清單開啟；未覆寫既有內容。',
    article_metadata_required: '新文章需要英文標題、分類與標籤；輸入仍保留。',
    invalid_article_metadata: '文章標題、標籤、分類或日期格式不完整；輸入仍保留。',
    draft_unavailable: '草稿服務暫時無法讀取，請確認登入或稍後重試；未寫入任何版本，既有編輯保留。',
    draft_list_unavailable: '草稿清單暫時無法完整讀取，請稍後重試；既有編輯與草稿保留。',
    cloud_draft_required: '請先保存目前文章為雲端草稿，再確認送審或排程。',
    unsaved_request: '目前內容與已保存版本不同，請先保存草稿；尚未送出申請。',
    author_confirmation_required: '請先逐句確認這個版本的醫療內容與圖片，或明確確認取消／下架申請。',
    invalid_schedule: '請選擇未來一年內的排程時間；尚未送出申請。',
    request_already_saved: '這個版本已有申請；請先取消，或編輯並保存新版本後重新確認。',
    request_missing: '目前沒有可取消的申請；請重讀確認，編輯保留。',
    publication_request_locked: '申請已進入發布流程，請先確認上線狀態，再開始新版草稿；目前編輯保留。',
    invalid_delivery_receipt: '發布資料暫時無法核對，請稍後重讀；目前編輯保留。',
    request_not_verified: '申請可能已保存，但驗證未完成；請重讀確認，勿重複送出。',
    article_not_published: '這篇尚未正式發布，無需申請下架。',
    invalid_local_draft: '暫存圖片不完整或版本不符，尚未還原；原暫存與編輯保留。',
    publication_unavailable: '網站上線狀態尚未確認，請稍後重試；編輯與草稿保留。',
    publication_changed: '確認期間版本已變更，請先重讀比對；本機編輯仍保留。',
    publication_not_verified: '正式 CI 與部署尚未全部確認，暫時無法從網站建立新版草稿。',
    publication_receipt_not_retired: '這篇的發布證據尚未完成封存，暫時不能開啟下一輪草稿；舊版本保留。',
    new_version_not_verified: '新版草稿可能已建立，但驗證未完成；請重讀比對，勿重複建立。本機快照保留。',
  };
  class DraftClientError extends Error {
    constructor(code) { super(labels[code] || '草稿作業未完成；編輯與暫存仍保留。'); this.code = code; }
  }
  function error(code) { return new DraftClientError(code); }
  function isArticle(file) { return /^blog\/(?!index\.html$|topics\.html$|charts\.html$)[a-z0-9]+(?:-[a-z0-9]+)*\.html$/.test(file || ''); }
  async function request(method, file, body, mode) {
    const unknownWrite = body && body.action === 'new-version' ? 'new_version_not_verified' : body && body.action ? 'request_not_verified' : 'save_not_verified';
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 45_000);
    try {
      const response = await fetch('/api/admin/article-draft' + (method === 'GET' ? mode === 'list' ? '?mode=list&offset=' + encodeURIComponent(file) : '?file=' + encodeURIComponent(file) + (['status', 'publication'].includes(mode) ? '&mode=' + mode : '') : ''), {
        method, credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal,
        headers: { 'Content-Type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}),
      });
      const data = await response.json();
      if (!response.ok) throw error(method === 'POST' && response.status >= 500 ? unknownWrite : data.error);
      return data;
    } catch (failure) {
      if (failure instanceof DraftClientError) throw failure;
      // An HTML gateway response or broken connection may follow an accepted
      // commit. Never expose raw parsing/provider details or retry the POST.
      throw error(method === 'POST' ? unknownWrite : mode === 'publication' ? 'publication_unavailable' : 'draft_unavailable');
    } finally { clearTimeout(timer); }
  }
  function mediaUrl(item) {
    const ext = item.path.split('.').pop(), type = { png: 'image/png', jpg: 'image/jpeg', webp: 'image/webp', gif: 'image/gif' }[ext];
    if (!type || typeof item.base64 !== 'string') throw error('invalid_draft_media');
    return 'data:' + type + ';base64,' + item.base64;
  }
  async function load(file, options) {
    if (!isArticle(file)) throw error('invalid_article');
    const generation = (generations.get(file) || 0) + 1;
    generations.set(file, generation);
    const data = await request('GET', file);
    if (generations.get(file) !== generation) throw error('editor_changed');
    if (data.file !== file || !(data.head === null || SHA.test(data.head)) ||
        !(data.baseSha === null || SHA.test(data.baseSha)) || !(data.blobSha === null || SHA.test(data.blobSha)) ||
        !(data.content === null || typeof data.content === 'string') ||
        !Array.isArray(data.media) || (data.requestLocked !== undefined && typeof data.requestLocked !== 'boolean')) throw error('invalid_draft_response');
    const context = { file, head: data.head, baseSha: data.baseSha, legacy: data.legacy,
      conflict: data.conflict, media: new Map(), generation, blobSha: data.blobSha,
      savedContent: data.content, request: data.request || null, requestLocked: data.requestLocked === true };
    for (const item of data.media) context.media.set(item.path, { ...item, url: mediaUrl(item), accepted: true });
    if (!options || options.activate !== false) contexts.set(file, context);
    return { ...data, context };
  }
  function activate(data) {
    if (!data || !data.context || data.file !== data.context.file || generations.get(data.file) !== data.context.generation) throw error('editor_changed');
    contexts.set(data.file, data.context);
  }
  function canonical(file, content) {
    const context = contexts.get(file);
    if (!context) return content;
    for (const item of context.media.values()) {
      // Replace only exact src attribute values, without reserializing the
      // original document or modifying live DOM, SVG, scripts or other text.
      const escaped = item.url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      content = content.replace(new RegExp('\\bsrc\\s*=\\s*(["\'])' + escaped + '\\1', 'g'), 'src="/' + item.path + '"');
    }
    return content;
  }
  function preview(file, doc) {
    const context = contexts.get(file);
    if (!context) return;
    for (const img of doc.querySelectorAll('img[src]')) {
      const path = img.getAttribute('src').replace(/^\//, ''), item = context.media.get(path);
      if (item) img.setAttribute('src', item.url);
    }
  }
  function capture(file, content, options) {
    const context = contexts.get(file);
    if (context && context.requestLocked) throw error('publication_request_locked');
    if (!context || context.legacy || context.conflict) throw error(context && context.legacy ? 'legacy_draft_requires_review' : 'draft_conflict');
    const html = canonical(file, content);
    const media = [...context.media.values()].filter(item => !item.accepted && html.includes('/' + item.path))
      .map(({ path, base64 }) => Object.freeze({ path, base64 }));
    const snapshot = Object.freeze({ file, expectedHead: context.head, baseSha: context.baseSha, content: html,
      media: Object.freeze(media), ...(options && options.metadata ? { metadata: Object.freeze({ ...options.metadata }) } : {}), context });
    if (new TextEncoder().encode(JSON.stringify({ ...snapshot, context: undefined })).length > MAX_BODY) throw error('draft_too_large');
    return snapshot;
  }
  async function save(snapshot) {
    if (contexts.get(snapshot.file) !== snapshot.context) throw error('editor_changed');
    const { file, expectedHead, baseSha, content, media, metadata } = snapshot;
    const accepted = await request('POST', file, { file, expectedHead, baseSha, content, media, ...(metadata ? { metadata } : {}) });
    if (accepted.file !== file || !SHA.test(accepted.head) || !SHA.test(accepted.blobSha) ||
        accepted.baseSha !== baseSha || accepted.verified !== true || accepted.published !== false || accepted.status !== 'cloud_draft') throw error('save_not_verified');
    // Edits made while awaiting I/O remain in the editor. Advance only this
    // loaded revision; the caller compares its live content with the snapshot.
    if (contexts.get(file) === snapshot.context) {
      snapshot.context.head = accepted.head;
      snapshot.context.blobSha = accepted.blobSha;
      snapshot.context.savedContent = snapshot.content;
      snapshot.context.viewContent = snapshot.content;
      snapshot.context.request = null;
      for (const item of media) {
        const live = snapshot.context.media.get(item.path);
        if (live && live.base64 === item.base64) live.accepted = true;
      }
    }
    return accepted;
  }
  function captureRequest(file, content, options) {
    const context = contexts.get(file), action = options && options.action;
    if (context && context.requestLocked) throw error('publication_request_locked');
    if (!context || context.legacy || (context.conflict && action !== 'cancel')) throw error('draft_conflict');
    if (!SHA.test(context.head || '') || !SHA.test(context.blobSha || '')) throw error('cloud_draft_required');
    const currentContent = canonical(file, content);
    if (currentContent !== (context.viewContent ?? context.savedContent)) throw error('unsaved_request');
    if (!['review', 'schedule', 'unpublish', 'cancel'].includes(action)) throw error('invalid_publication_request');
    return Object.freeze({ file, action, expectedHead: context.head, baseSha: context.baseSha,
      expectedBlob: context.blobSha, content: currentContent, context,
      ...(action === 'unpublish' || action === 'cancel' ? { confirmed: options.confirmed === true } : { contentApproved: options.contentApproved === true }),
      ...(action === 'schedule' ? { scheduledAt: options.scheduledAt } : {}) });
  }
  function bindView(file, content, head) {
    const context = contexts.get(file);
    if (!context || context.head !== head || typeof content !== 'string' || context.savedContent === null) return false;
    // The unchanged mounted view can normalize whitespace. Keep this comparison
    // projection separate; never replace immutable cloud bytes or the blob SHA.
    context.viewContent = canonical(file, content); return true;
  }
  function hasUnsavedChanges(file, content) {
    const context = contexts.get(file);
    return !context || canonical(file, content) !== (context.viewContent ?? context.savedContent);
  }
  async function submit(snapshot) {
    const context = contexts.get(snapshot.file);
    if (context !== snapshot.context || context.head !== snapshot.expectedHead || context.blobSha !== snapshot.expectedBlob) throw error('editor_changed');
    const { file, action, expectedHead, baseSha, expectedBlob, contentApproved, confirmed, scheduledAt } = snapshot;
    const accepted = await request('POST', file, { file, action, expectedHead, baseSha, expectedBlob,
      ...(contentApproved !== undefined ? { contentApproved } : {}),
      ...(confirmed !== undefined ? { confirmed } : {}), ...(scheduledAt !== undefined ? { scheduledAt } : {}) });
    const expectedStatus = { review: 'awaiting_review', schedule: 'schedule_requested', unpublish: 'unpublish_requested' }[action];
    if (accepted.file !== file || !SHA.test(accepted.head || '') || accepted.head === expectedHead ||
        accepted.baseSha !== baseSha || accepted.blobSha !== expectedBlob ||
        accepted.verified !== true || accepted.published !== false ||
        (action === 'cancel' ? accepted.request !== null :
          !accepted.request || accepted.request.action !== action || accepted.request.status !== expectedStatus ||
          accepted.request.blobSha !== expectedBlob || (action === 'schedule' && accepted.request.scheduledAt !== scheduledAt))) throw error('request_not_verified');
    if (contexts.get(file) === context) {
      context.head = accepted.head; context.request = accepted.request;
    }
    return accepted;
  }
  async function create(file, content, metadata) {
    const data = await load(file, { activate: false });
    if (data.head !== null || data.content !== null) throw error('article_exists');
    activate(data);
    return save(capture(file, content, { metadata }));
  }
  async function list() {
    const found = [], seen = new Set(); let offset = 0;
    for (let page = 0; page < 11; page++) {
      const data = await request('GET', String(offset), null, 'list');
      if (!Array.isArray(data.drafts) || data.drafts.length > 20) throw error('invalid_draft_response');
      for (const item of data.drafts) {
        if (!isArticle(item.file) || !SHA.test(item.head) || seen.has(item.file)) throw error('invalid_draft_response');
        seen.add(item.file); found.push(item);
      }
      if (data.nextOffset === null) return { drafts: found, unsupportedRefs: data.unsupportedRefs || 0 };
      if (!Number.isInteger(data.nextOffset) || data.nextOffset <= offset || data.nextOffset > 200) throw error('invalid_draft_response');
      offset = data.nextOffset;
    }
    throw error('draft_list_unavailable');
  }
  async function stage(file, blob) {
    const context = contexts.get(file);
    if (!context || context.legacy || context.conflict) throw error('draft_conflict');
    const ext = { 'image/webp': 'webp', 'image/png': 'png', 'image/jpeg': 'jpg', 'image/gif': 'gif' }[blob.type];
    if (!ext) throw error('unsupported_image');
    if (blob.size > 1_400_000) throw error('draft_too_large');
    const bytes = new Uint8Array(await blob.arrayBuffer());
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), b => b.toString(16).padStart(2, '0')).join('');
    if (contexts.get(file) !== context) throw error('editor_changed');
    let binary = '';
    for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
    const path = 'blog/images/' + file.slice(5, -5) + '/' + digest + '.' + ext;
    const previous = context.media.get(path);
    const item = { path, base64: btoa(binary), accepted: !!(previous && previous.accepted) };
    item.url = mediaUrl(item); context.media.set(path, item);
    return { url: item.url, path: '/' + path };
  }

  async function prepareImages(file, blobs) {
    const context = contexts.get(file);
    if (!context || context.legacy || context.conflict) throw error('draft_conflict');
    if (!Array.isArray(blobs) || blobs.length > 16) throw error('draft_too_large');
    if (blobs.length === 0) return Object.freeze({ images: Object.freeze([]), commit() {}, rollback() {} });
    const expected = { head: context.head, blobSha: context.blobSha, baseSha: context.baseSha };
    const prepared = new Map();
    for (const blob of blobs) {
      const ext = { 'image/webp': 'webp', 'image/png': 'png', 'image/jpeg': 'jpg', 'image/gif': 'gif' }[blob.type];
      if (!ext) throw error('unsupported_image');
      if (blob.size > 1_400_000 || blob.size < 8) throw error('draft_too_large');
      const bytes = new Uint8Array(await blob.arrayBuffer());
      const starts = values => values.every((value, index) => bytes[index] === value);
      const ascii = (offset, value) => [...value].every((char, index) => bytes[offset + index] === char.charCodeAt(0));
      if (!(ext === 'png' ? starts([137,80,78,71,13,10,26,10]) : ext === 'jpg' ? starts([255,216,255]) :
          ext === 'gif' ? ascii(0, 'GIF87a') || ascii(0, 'GIF89a') : ascii(0, 'RIFF') && ascii(8, 'WEBP'))) throw error('unsupported_image');
      let bitmap;
      try { bitmap = await createImageBitmap(blob); if (!bitmap.width || !bitmap.height || bitmap.width * bitmap.height > 30_000_000) throw error('unsupported_image'); }
      catch (_) { throw error('unsupported_image'); } finally { if (bitmap) bitmap.close(); }
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), value => value.toString(16).padStart(2, '0')).join('');
      let binary = '';
      for (let index = 0; index < bytes.length; index += 8192) binary += String.fromCharCode(...bytes.subarray(index, index + 8192));
      const path = 'blog/images/' + file.slice(5, -5) + '/' + digest + '.' + ext;
      const item = { path, base64: btoa(binary), accepted: false };
      item.url = mediaUrl(item); prepared.set(path, item);
    }
    let committed = false, consumed = false, beforeCommit, installed;
    function candidate() {
      if (contexts.get(file) !== context || context.legacy || context.conflict || context.head !== expected.head || context.baseSha !== expected.baseSha || context.blobSha !== expected.blobSha) throw error('editor_changed');
      const next = new Map(context.media);
      for (const [path, item] of prepared) next.set(path, { ...item, accepted: !!(next.get(path)?.accepted) });
      if (next.size > 16 || [...next.values()].reduce((sum, item) => sum + item.base64.length, 0) > 1_900_000) throw error('draft_too_large');
      return next;
    }
    candidate();
    return Object.freeze({ images: Object.freeze([...prepared.values()].map(item => Object.freeze({ path: '/' + item.path, url: item.url }))),
      commit() {
        if (consumed) throw error('editor_changed');
        const next = candidate();
        beforeCommit = context.media; installed = next; context.media = next; committed = true; consumed = true;
      },
      rollback() {
        if (!committed) return;
        if (context.head !== expected.head || context.baseSha !== expected.baseSha || context.blobSha !== expected.blobSha) throw error('editor_changed');
        const restored = new Map(context.media);
        for (const path of prepared.keys()) {
          // Revert only this token's entries, retaining later independent edits.
          if (restored.get(path) !== installed.get(path)) continue;
          if (beforeCommit.has(path)) restored.set(path, beforeCommit.get(path)); else restored.delete(path);
        }
        context.media = restored; committed = false;
      }
    });
  }
  function localState(file) {
    const context = contexts.get(file);
    return context ? { head: context.head, baseSha: context.baseSha, blobSha: context.blobSha, request: context.request,
      media: [...context.media.values()].map(({ path, base64, accepted }) => ({ path, base64, accepted })) } : null;
  }
  async function restore(file, saved, options) {
    const context = contexts.get(file);
    if (!context || !saved || !Array.isArray(saved.media) || saved.media.length > 16 ||
        !(saved.head === null || typeof saved.head === 'string' && SHA.test(saved.head)) ||
        !(saved.baseSha === null || typeof saved.baseSha === 'string' && SHA.test(saved.baseSha)) ||
        !(saved.blobSha === undefined || saved.blobSha === null || typeof saved.blobSha === 'string' && SHA.test(saved.blobSha))) throw error('invalid_local_draft');
    const expected = { head: context.head, baseSha: context.baseSha, blobSha: context.blobSha, media: context.media, entries: [...context.media] };
    const conflict = saved.head !== context.head || saved.baseSha !== context.baseSha ||
      (saved.blobSha !== undefined && saved.blobSha !== context.blobSha);
    const next = new Map(context.media), seen = new Set(); let encodedSize = 0;
    for (const item of saved.media) {
      const match = item && typeof item.path === 'string' && new RegExp('^blog/images/' + file.slice(5, -5) + '/([a-f0-9]{64})\\.(png|jpg|webp|gif)$').exec(item.path);
      if (!match || seen.has(item.path) || typeof item.base64 !== 'string' || item.base64.length > 1_900_000 ||
          !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(item.base64)) throw error('invalid_local_draft');
      seen.add(item.path); encodedSize += item.base64.length;
      if (encodedSize > 1_900_000) throw error('invalid_local_draft');
      let binary; try { binary = atob(item.base64); } catch (_) { throw error('invalid_local_draft'); }
      if (binary.length < 8 || binary.length > 1_400_000 || btoa(binary) !== item.base64) throw error('invalid_local_draft');
      const bytes = Uint8Array.from(binary, value => value.charCodeAt(0));
      const starts = values => values.every((value, index) => bytes[index] === value);
      const ascii = (offset, value) => [...value].every((char, index) => bytes[offset + index] === char.charCodeAt(0));
      const ext = match[2], valid = ext === 'png' ? starts([137,80,78,71,13,10,26,10]) : ext === 'jpg' ? starts([255,216,255]) :
        ext === 'gif' ? ascii(0, 'GIF87a') || ascii(0, 'GIF89a') : ascii(0, 'RIFF') && ascii(8, 'WEBP');
      if (!valid) throw error('invalid_local_draft');
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), value => value.toString(16).padStart(2, '0')).join('');
      if (digest !== match[1]) throw error('invalid_local_draft');
      const previous = context.media.get(item.path), accepted = !conflict && !!(previous && previous.accepted && previous.base64 === item.base64);
      next.set(item.path, { path: item.path, base64: item.base64, url: mediaUrl(item), accepted });
    }
    if (next.size > 16 || [...next.values()].reduce((sum, item) => sum + item.base64.length, 0) > 1_900_000) throw error('invalid_local_draft');
    if (contexts.get(file) !== context || context.head !== expected.head || context.baseSha !== expected.baseSha || context.blobSha !== expected.blobSha ||
        context.media !== expected.media || context.media.size !== expected.entries.length || expected.entries.some(([path, item]) => context.media.get(path) !== item) ||
        (options && options.isCurrent && options.isCurrent() !== true)) throw error('editor_changed');
    context.media = next;
    if (conflict) context.conflict = true;
    return { conflict };
  }
  async function inspect(file) { return request('GET', file, null, 'status'); }
  async function observe(file) {
    const context = contexts.get(file);
    if (!context || !isArticle(file)) throw error('publication_unavailable');
    const expected = { head: context.head, baseSha: context.baseSha, blobSha: context.blobSha };
    const data = await request('GET', file, null, 'publication'), proof = data && data.publication;
    const validSha = value => typeof value === 'string' && SHA.test(value) && value !== '0'.repeat(40);
    const nullableSha = value => value === null || validSha(value);
    const states = ['not_published', 'ci_missing', 'ci_running', 'ci_failed', 'deployment_missing', 'deployment_running', 'deployment_failed', 'live', 'live_noindex', 'unverified', 'changed'];
    if (!proof || data.file !== file || !nullableSha(data.head) || !nullableSha(data.blobSha) || !nullableSha(data.baseSha) ||
        !validSha(proof.mainSha) || !nullableSha(proof.mainBlobSha) || !states.includes(proof.state) ||
        ['matchesLoadedVersion', 'sourceIndexable', 'ciVerified', 'deploymentVerified', 'published'].some(key => typeof proof[key] !== 'boolean') ||
        !Array.isArray(proof.checks) || proof.checks.length > 30 ||
        typeof proof.observedAt !== 'string' || !Number.isFinite(Date.parse(proof.observedAt)) ||
        proof.matchesLoadedVersion !== (proof.mainBlobSha !== null && proof.mainBlobSha === data.blobSha)) throw error('publication_unavailable');
    const live = ['live', 'live_noindex'].includes(proof.state);
    if (proof.deploymentVerified !== live || (live && !proof.ciVerified) ||
        proof.published !== (proof.state === 'live' && proof.matchesLoadedVersion && proof.sourceIndexable) ||
        (proof.state === 'live' && !proof.sourceIndexable) || (proof.state === 'live_noindex' && proof.sourceIndexable) ||
        (['not_published', 'ci_missing', 'ci_running', 'ci_failed', 'changed'].includes(proof.state) && proof.ciVerified)) throw error('publication_unavailable');
    if (contexts.get(file) !== context || ['head', 'baseSha', 'blobSha'].some(key => context[key] !== expected[key] || data[key] !== expected[key])) throw error('publication_changed');
    return data;
  }
  function captureNewVersion(file, observation) {
    const context = contexts.get(file), proof = observation && observation.publication;
    const nonzero = value => typeof value === 'string' && SHA.test(value) && value !== '0'.repeat(40);
    if (!context || context.legacy || !nonzero(context.head) || !nonzero(context.blobSha)) throw error('cloud_draft_required');
    if (!proof || observation.file !== file || observation.head !== context.head || observation.blobSha !== context.blobSha ||
        observation.baseSha !== context.baseSha || proof.state !== 'live' || proof.ciVerified !== true ||
        proof.deploymentVerified !== true || proof.sourceIndexable !== true || !nonzero(proof.mainSha) || !nonzero(proof.mainBlobSha)) throw error('publication_not_verified');
    return { context, file, action: 'new-version', expectedHead: context.head, expectedBlob: context.blobSha,
      expectedMain: proof.mainSha, expectedMainBlob: proof.mainBlobSha, confirmed: true };
  }
  async function startNewVersion(snapshot) {
    const { context, ...payload } = snapshot;
    if (contexts.get(payload.file) !== context || context.head !== payload.expectedHead || context.blobSha !== payload.expectedBlob) throw error('publication_changed');
    const accepted = await request('POST', payload.file, payload);
    if (!accepted || accepted.file !== payload.file || !SHA.test(accepted.head || '') || accepted.head === '0'.repeat(40) ||
        accepted.head === payload.expectedHead || accepted.baseSha !== payload.expectedMainBlob || accepted.blobSha !== payload.expectedMainBlob ||
        accepted.status !== 'cloud_draft' || accepted.verified !== true || accepted.published !== false) throw error('new_version_not_verified');
    // The caller must re-read the immutable accepted revision and preserve any
    // typing during this request before activating a replacement editor.
    return accepted;
  }
  function publicationMessage(proof) {
    const messages = { not_published: '文章仍在草稿階段，尚未正式上線。',
      ci_missing: '網站來源已更新；正式驗證尚未完成。', ci_running: '網站版本正在驗證，尚未確認上線。',
      ci_failed: '網站版本驗證未通過，尚未完成發布。', deployment_missing: '正式驗證通過；部署尚未確認。',
      deployment_running: '正式驗證通過；網站正在部署。', deployment_failed: '正式驗證通過；部署未成功。',
      live_noindex: '網站版本已部署，目前不列入公開索引。',
      unverified: '網站上線狀態尚未確認，可稍後重試。', changed: '確認期間版本已變更，請重新核對。' };
    if (proof.state === 'live') return proof.published ? '這個已保存版本已正式上線。' : '網站來源版本已上線；目前草稿尚未上線。';
    return messages[proof.state] || messages.unverified;
  }
  function message(failure) { return failure instanceof DraftClientError ? failure.message : '草稿作業未完成；本機編輯與暫存仍保留。'; }
  window.DNArticleDrafts = { isArticle, load, activate, capture, save, captureRequest, bindView, hasUnsavedChanges, submit, create, list, stage, prepareImages, canonical, preview, localState, restore, inspect, observe, captureNewVersion, startNewVersion, publicationMessage, message };
})();
