// Cookie-authenticated site-setting drafts only. No main ref, KV publication,
// repository selector, custom CSS, media upload or production deployment write.
import { getSession } from './_session.js';
import { contract, SHA, SettingsError, fail, exact, revision, parseJson, catalogOf, settingsOf, settingsRecord } from './_site-settings.js';
import { settingsGit } from './_settings-git.js';
import { observePublication } from './_article-publication.js';
import publicationPolicy from '../../_delivery_policy.json';
export const config = { runtime: 'edge' };
const encoder = new TextEncoder();
function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: {
    'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'private, no-store',
    'X-Content-Type-Options': 'nosniff', Vary: 'Cookie',
  } });
}
async function state(git) {
  const main = await git.ref('main');
  if (!main) fail(502, 'settings_main_unavailable');
  const [published, catalogBlob] = await Promise.all([git.file(contract.source, main), git.file(contract.catalog, main)]);
  const articles = catalogOf(parseJson(catalogBlob.content, 502, 'invalid_settings_catalog'));
  let sourceSettings, sourceRequiresReview = false;
  try { sourceSettings = settingsRecord(parseJson(published.content)); } catch (_) { fail(409, 'settings_base_requires_review'); }
  try { settingsOf(sourceSettings, articles); } catch (_) { sourceRequiresReview = true; }
  const head = await git.ref(contract.branch);
  let settings = sourceSettings, blobSha = published.sha, baseSha = published.sha, baseCatalogSha = catalogBlob.sha, conflict = false;
  let manifestRecord = null, request = null;
  if (head) {
    const [draft, manifest] = await Promise.all([git.file(contract.source, head), git.file(contract.manifest, head, true)]);
    if (!manifest) fail(409, 'settings_legacy_requires_review');
    const record = parseJson(manifest.content, 409, 'invalid_settings_manifest');
    exact(record, ['version', 'source', 'baseMain', 'baseSha', 'catalogSha', 'blobSha', 'status'], 409, 'invalid_settings_manifest');
    if (record.version !== 1 || record.source !== contract.source || record.status !== 'draft' ||
        !['baseMain', 'baseSha', 'catalogSha', 'blobSha'].every(field => SHA.test(record[field] || '')) || record.blobSha !== draft.sha) fail(409, 'invalid_settings_manifest');
    manifestRecord = record;
    settings = parseJson(draft.content, 409, 'invalid_settings_manifest');
    // A changed catalogue/config requires explicit integration. It must not
    // silently drop newly published articles or overwrite another author's work.
    baseSha = record.baseSha; baseCatalogSha = record.catalogSha; blobSha = draft.sha;
    conflict = baseSha !== published.sha || baseCatalogSha !== catalogBlob.sha;
    if (!conflict) settings = settingsOf(settings, articles);
    const [baseSource, baseCatalog] = record.baseMain === main ? [published, catalogBlob] :
      await Promise.all([git.file(contract.source, record.baseMain), git.file(contract.catalog, record.baseMain)]);
    if (baseSource.sha !== baseSha || baseCatalog.sha !== baseCatalogSha) fail(409, 'invalid_settings_manifest');
    // A conflicting draft is still validated against the catalogue that its
    // author used. Conflict must never turn malformed stored data into input.
    try { settings = settingsOf(settings, catalogOf(parseJson(baseCatalog.content))); }
    catch (_) { fail(409, 'invalid_settings_manifest'); }
    // A settings branch must stay a data-only descendant of its recorded
    // baseline. A clean request child cannot legitimise earlier code edits.
    const allowed = new Set([contract.source, contract.manifest, contract.request]);
    const [baseTree, draftTree] = await Promise.all([git.tree(record.baseMain), git.tree(head)]);
    const unchangedPayload = tree => [...tree.entries].filter(([path, entry]) => !allowed.has(path) && entry.type !== 'tree')
      .map(([path, entry]) => [path, entry.type, entry.mode, entry.sha]).sort((a, b) => a[0].localeCompare(b[0]));
    if (JSON.stringify(unchangedPayload(baseTree)) !== JSON.stringify(unchangedPayload(draftTree))) fail(409, 'invalid_settings_scope');
    const requestBlob = await git.file(contract.request, head, true);
    if (requestBlob) {
      const intent = parseJson(requestBlob.content, 409, 'invalid_settings_request');
      exact(intent, ['version', 'status', 'branch', 'draftHead', 'blobSha', 'baseMain', 'baseSha', 'catalogSha', 'settingsApproved'], 409, 'invalid_settings_request');
      if (intent.version !== 1 || intent.status !== 'requested' || intent.branch !== contract.branch || intent.settingsApproved !== true ||
          !['draftHead', 'blobSha', 'baseMain', 'baseSha', 'catalogSha'].every(field => SHA.test(intent[field] || '')) ||
          ['blobSha', 'baseMain', 'baseSha', 'catalogSha'].some(field => intent[field] !== record[field])) fail(409, 'invalid_settings_request');
      const commit = await git.commit(head);
      if (commit.parents.length !== 1 || commit.parents[0].sha !== intent.draftHead) fail(409, 'invalid_settings_request');
      const [parentSource, parentManifest, parentRequest] = await Promise.all([
        git.file(contract.source, intent.draftHead), git.file(contract.manifest, intent.draftHead), git.file(contract.request, intent.draftHead, true),
      ]);
      if (parentSource.sha !== draft.sha || parentManifest.content !== manifest.content || parentRequest !== null) fail(409, 'invalid_settings_request');
      const [parentTree, currentTree] = await Promise.all([git.tree(intent.draftHead), git.tree(head)]);
      const payload = tree => [...tree.entries].filter(([path, entry]) => path !== contract.request && entry.type !== 'tree')
        .map(([path, entry]) => [path, entry.type, entry.mode, entry.sha]).sort((a, b) => a[0].localeCompare(b[0]));
      if (JSON.stringify(payload(parentTree)) !== JSON.stringify(payload(currentTree))) fail(409, 'invalid_settings_request');
      request = { ...intent, requestHead: head, requestBlobSha: requestBlob.sha };
    }
  }
  if (!head) conflict = sourceRequiresReview;
  if (await git.ref('main') !== main || await git.ref(contract.branch) !== head) fail(409, 'settings_changed');
  return { main, head, baseSha, catalogSha: baseCatalogSha, mainBlobSha: published.sha, mainCatalogSha: catalogBlob.sha,
    blobSha, settings, sourceSettings, sourceRequiresReview, articles, conflict, manifestRecord, request,
    status: conflict ? 'conflict' : request ? 'requested' : head ? 'cloud_draft' : 'source_base',
    published: false, deploymentVerified: false };
}
async function bodyOf(req) {
  if (!/^application\/json(?:\s*;|$)/i.test(req.headers.get('content-type') || '') || !req.body) fail(400, 'invalid_settings_json');
  const reader = req.body.getReader(), chunks = [];
  let total = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > 32_000) fail(413, 'settings_too_large');
      chunks.push(value);
    }
  } finally { await reader.cancel(); }
  const bytes = new Uint8Array(total); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  let text;
  try { text = new TextDecoder('utf-8', { fatal: true }).decode(bytes); } catch (_) { fail(400, 'invalid_settings_json'); }
  return parseJson(text);
}
async function settingsObservation(git, loaded) {
  // The shared verifier checks formal push attempts/jobs/steps/smoke and the
  // global latest trusted production deployment. This is data, not an article.
  const proof = await observePublication(git.api, {
    main: loaded.main, mainBlobSha: loaded.mainBlobSha, blobSha: loaded.blobSha, mainIndexable: !loaded.sourceRequiresReview,
  }, publicationPolicy.site_settings_author_intent === true ? publicationPolicy : null);
  const { sourceIndexable, ...observation } = proof;
  const changed = await git.ref('main') !== loaded.main || await git.ref(contract.branch) !== loaded.head;
  return { ...observation, kind: 'site-settings', loadedHead: loaded.head, loadedBlobSha: loaded.blobSha,
    settingsValidated: sourceIndexable, ...(changed ? {state: 'changed', ciVerified: false, deploymentVerified: false, published: false} : {}) };
}
async function reconcileCatalog(git, input) {
  exact(input, ['action','expectedHead','blobSha','expectedMain','expectedMainBlob','expectedCatalog','settings','confirmed']);
  revision(input.expectedHead, true);
  for (const key of ['blobSha','expectedMain','expectedMainBlob','expectedCatalog']) revision(input[key]);
  if (input.confirmed !== true) fail(400, 'settings_confirmation_required');
  const loaded = await state(git);
  if (loaded.head !== input.expectedHead || loaded.blobSha !== input.blobSha || loaded.main !== input.expectedMain ||
      loaded.mainBlobSha !== input.expectedMainBlob || loaded.mainCatalogSha !== input.expectedCatalog ||
      !loaded.conflict || !(loaded.sourceRequiresReview || loaded.catalogSha !== loaded.mainCatalogSha)) fail(409, 'settings_conflict');
  const settings = settingsOf(input.settings, loaded.articles);
  if ((!loaded.settings.legacyPicks || !loaded.sourceSettings.legacyPicks) && settings.legacyPicks) fail(400, 'invalid_settings_selection');
  const receipt = await git.file('.site-settings-delivery.json', loaded.main, true);
  if (!receipt) fail(409, 'settings_receipt_not_retired');
  const proof = parseJson(receipt.content, 409, 'settings_receipt_not_retired');
  exact(proof, ['version','request'], 409, 'settings_receipt_not_retired');
  if (proof.version !== 1 || proof.request !== null || receipt.content !== JSON.stringify(proof,null,2)+'\n') fail(409, 'settings_receipt_not_retired');
  const content = JSON.stringify(settings,null,2)+'\n';
  async function unchanged() {
    if (await git.ref('main') !== loaded.main || await git.ref(contract.branch) !== loaded.head) fail(409,'settings_conflict');
  }
  await unchanged();
  const blob = await git.api('POST','git/blobs',{content,encoding:'utf-8'});
  if (!SHA.test(blob.sha || '')) fail(502,'settings_reconciliation_not_verified');
  const manifest = JSON.stringify({version:1,source:contract.source,baseMain:loaded.main,baseSha:loaded.mainBlobSha,
    catalogSha:loaded.mainCatalogSha,blobSha:blob.sha,status:'draft'})+'\n';
  const mainTree = await git.tree(loaded.main);
  const changes = [{path:contract.source,mode:'100644',type:'blob',content},
    {path:contract.manifest,mode:'100644',type:'blob',content:manifest}];
  if (mainTree.entries.has(contract.request)) changes.push({path:contract.request,mode:'100644',type:'blob',sha:null});
  await unchanged();
  const tree = await git.api('POST','git/trees',{base_tree:mainTree.sha,tree:changes});
  if (!SHA.test(tree.sha || '')) fail(502,'settings_reconciliation_not_verified');
  const commit = await git.api('POST','git/commits',{message:'[settings draft] reconcile article catalogue',tree:tree.sha,
    parents:[...new Set([loaded.head || loaded.main,loaded.main])]});
  if (!SHA.test(commit.sha || '')) fail(502,'settings_reconciliation_not_verified');
  await unchanged();
  const result = loaded.head ? await git.api('PATCH','git/refs/heads/'+encodeURIComponent(contract.branch),{sha:commit.sha,force:false}) :
    await git.api('POST','git/refs',{ref:'refs/heads/'+contract.branch,sha:commit.sha});
  if (result.ref !== 'refs/heads/'+contract.branch || result.object?.type !== 'commit' || result.object.sha !== commit.sha) fail(502,'settings_reconciliation_not_verified');
  try {
    const after = await state(git);
    if (after.head !== commit.sha || after.main !== loaded.main || after.blobSha !== blob.sha || after.conflict || after.request !== null ||
        after.baseSha !== loaded.mainBlobSha || after.catalogSha !== loaded.mainCatalogSha ||
        JSON.stringify(after.settings) !== JSON.stringify(settings) || (await git.file(contract.manifest,commit.sha)).content !== manifest)
      fail(502,'settings_reconciliation_not_verified');
    return {...after,verified:true};
  } catch (_) { fail(502,'settings_reconciliation_not_verified'); }
}
async function newVersion(git, input) {
  exact(input, ['action','expectedHead','blobSha','expectedMain','expectedMainBlob','expectedCatalog','confirmed']);
  for (const key of ['expectedHead','blobSha','expectedMain','expectedMainBlob','expectedCatalog']) revision(input[key]);
  if (input.action !== 'new-version' || input.confirmed !== true) fail(400, 'settings_confirmation_required');
  const loaded = await state(git);
  if (!loaded.head || !loaded.manifestRecord || loaded.head !== input.expectedHead || loaded.blobSha !== input.blobSha ||
      loaded.main !== input.expectedMain || loaded.mainBlobSha !== input.expectedMainBlob ||
      loaded.mainCatalogSha !== input.expectedCatalog) fail(409, 'settings_conflict');
  const proof = await settingsObservation(git, loaded);
  if (proof.state !== 'live' || !proof.ciVerified || !proof.deploymentVerified || !proof.settingsValidated) fail(409, 'settings_publication_not_verified');
  const receipt = await git.file('.site-settings-delivery.json', loaded.main, true);
  if (!receipt) fail(409, 'settings_receipt_not_retired');
  const value = parseJson(receipt.content, 409, 'settings_receipt_not_retired');
  exact(value, ['version','request'], 409, 'settings_receipt_not_retired');
  if (value.version !== 1 || value.request !== null || receipt.content !== JSON.stringify(value, null, 2)+'\n') fail(409, 'settings_receipt_not_retired');

  // Start with the complete trusted main tree, never merge draft code or
  // restore obsolete generated assets. Both old heads remain reachable.
  const mainTree = await git.tree(loaded.main);
  const manifest = JSON.stringify({version:1,source:contract.source,baseMain:loaded.main,
    baseSha:loaded.mainBlobSha,catalogSha:loaded.mainCatalogSha,blobSha:loaded.mainBlobSha,status:'draft'})+'\n';
  const changes = [{path:contract.source,mode:'100644',type:'blob',sha:loaded.mainBlobSha},
    {path:contract.manifest,mode:'100644',type:'blob',content:manifest}];
  if (mainTree.entries.has(contract.request)) changes.push({path:contract.request,mode:'100644',type:'blob',sha:null});
  async function unchanged() {
    if (await git.ref('main') !== loaded.main || await git.ref(contract.branch) !== loaded.head) fail(409, 'settings_conflict');
  }
  await unchanged();
  const tree = await git.api('POST', 'git/trees', {base_tree:mainTree.sha,tree:changes});
  if (!SHA.test(tree.sha || '')) fail(502, 'settings_new_version_not_verified');
  const commit = await git.api('POST', 'git/commits', {message:'[settings draft] new version from verified production',
    tree:tree.sha,parents:[...new Set([loaded.head,loaded.main])]});
  if (!SHA.test(commit.sha || '')) fail(502, 'settings_new_version_not_verified');
  await unchanged();
  const result = await git.api('PATCH', 'git/refs/heads/'+encodeURIComponent(contract.branch), {sha:commit.sha,force:false});
  if (result.ref !== 'refs/heads/'+contract.branch || result.object?.type !== 'commit' || result.object.sha !== commit.sha) fail(502, 'settings_new_version_not_verified');
  try {
    const after = await state(git);
    if (after.main !== loaded.main || after.head !== commit.sha || after.blobSha !== loaded.mainBlobSha ||
        after.baseSha !== loaded.mainBlobSha || after.catalogSha !== loaded.mainCatalogSha || after.conflict || after.request !== null ||
        JSON.stringify(after.settings) !== JSON.stringify(loaded.sourceSettings) ||
        (await git.file(contract.manifest, commit.sha)).content !== manifest) fail(502, 'settings_new_version_not_verified');
    return {...after,verified:true};
  } catch (_) { fail(502, 'settings_new_version_not_verified'); }
}
async function save(git, input) {
  exact(input, ['expectedHead', 'baseSha', 'catalogSha', 'kind', 'values']);
  revision(input.expectedHead, true); revision(input.baseSha); revision(input.catalogSha);
  if (!['font', 'order', 'picks'].includes(input.kind)) fail(400, 'invalid_settings_kind');
  const loaded = await state(git);
  if (loaded.conflict || input.expectedHead !== loaded.head || input.baseSha !== loaded.baseSha || input.catalogSha !== loaded.catalogSha) fail(409, 'settings_conflict');
  // Choosing recommendations is an explicit migration. Other settings retain
  // the legacy read source until the author saves picks and requests delivery.
  const settings = settingsOf({ ...loaded.settings, [input.kind]: input.values,
    ...(input.kind === 'picks' ? {legacyPicks: false} : {}) }, loaded.articles);
  const content = JSON.stringify(settings, null, 2) + '\n';
  if (encoder.encode(content).length > 32_000) fail(413, 'settings_too_large');
  const parent = loaded.head || loaded.main;
  const sourceBlob = await git.api('POST', 'git/blobs', { content, encoding: 'utf-8' });
  if (!SHA.test(sourceBlob.sha || '')) fail(502, 'settings_save_not_verified');
  const manifest = JSON.stringify({ version: 1, source: contract.source, baseMain: loaded.manifestRecord?.baseMain || loaded.main,
    baseSha: loaded.baseSha, catalogSha: loaded.catalogSha, blobSha: sourceBlob.sha, status: 'draft' }) + '\n';
  const changes = [{ path: contract.source, mode: '100644', type: 'blob', sha: sourceBlob.sha },
    { path: contract.manifest, mode: '100644', type: 'blob', content: manifest }];
  // Saving a changed draft invalidates any previous version-bound request.
  if (loaded.head && await git.file(contract.request, loaded.head, true)) changes.push({ path: contract.request, mode: '100644', type: 'blob', sha: null });
  async function unchanged() {
    if (await git.ref('main') !== loaded.main || await git.ref(contract.branch) !== loaded.head) fail(409, 'settings_conflict');
  }
  await unchanged();
  const nextTree = await git.api('POST', 'git/trees', { base_tree: (await git.tree(parent)).sha, tree: changes });
  if (!SHA.test(nextTree.sha || '')) fail(502, 'settings_save_not_verified');
  const nextCommit = await git.api('POST', 'git/commits', { message: '[settings draft] ' + input.kind, tree: nextTree.sha, parents: [parent] });
  if (!SHA.test(nextCommit.sha || '')) fail(502, 'settings_save_not_verified');
  await unchanged();
  const result = loaded.head ? await git.api('PATCH', 'git/refs/heads/' + encodeURIComponent(contract.branch), { sha: nextCommit.sha, force: false }) :
    await git.api('POST', 'git/refs', { ref: 'refs/heads/' + contract.branch, sha: nextCommit.sha });
  if (result.ref !== 'refs/heads/' + contract.branch || result.object?.type !== 'commit' || result.object.sha !== nextCommit.sha) fail(502, 'settings_save_not_verified');
  try {
    const [afterSource, afterManifest] = await Promise.all([git.file(contract.source, nextCommit.sha), git.file(contract.manifest, nextCommit.sha)]);
    if (await git.ref(contract.branch) !== nextCommit.sha || await git.ref('main') !== loaded.main || afterSource.content !== content ||
        afterSource.sha !== sourceBlob.sha || afterManifest.content !== manifest || await git.file(contract.request, nextCommit.sha, true) !== null) fail(502, 'settings_save_not_verified');
  } catch (_) { fail(502, 'settings_save_not_verified'); }
  return { ...loaded, head: nextCommit.sha, blobSha: sourceBlob.sha,
    manifestRecord: parseJson(manifest), request: null, conflict: false,
    settings, branch: contract.branch, status: 'cloud_draft', verified: true, published: false, deploymentVerified: false };
}
async function requestPublication(git, input) {
  const cancel = input.action === 'cancel-request';
  exact(input, ['action', 'expectedHead', 'blobSha', 'baseSha', 'catalogSha', ...(cancel ? [] : ['settingsApproved'])]);
  for (const field of ['expectedHead', 'blobSha', 'baseSha', 'catalogSha']) revision(input[field]);
  if (!cancel && (input.action !== 'request-publication' || input.settingsApproved !== true)) fail(400, 'settings_approval_required');
  const loaded = await state(git);
  if (loaded.conflict || loaded.head !== input.expectedHead || loaded.blobSha !== input.blobSha ||
      loaded.baseSha !== input.baseSha || loaded.catalogSha !== input.catalogSha || !loaded.manifestRecord) fail(409, 'settings_conflict');
  if (cancel ? !loaded.request : loaded.request !== null) fail(409, 'settings_request_changed');
  const content = cancel ? null : JSON.stringify({ version: 1, status: 'requested', branch: contract.branch,
    draftHead: loaded.head, blobSha: loaded.blobSha, baseMain: loaded.manifestRecord.baseMain,
    baseSha: loaded.baseSha, catalogSha: loaded.catalogSha, settingsApproved: true }) + '\n';
  const changes = [{ path: contract.request, mode: '100644', type: 'blob', ...(cancel ? {sha: null} : {content}) }];
  async function unchanged() {
    if (await git.ref('main') !== loaded.main || await git.ref(contract.branch) !== loaded.head) fail(409, 'settings_conflict');
  }
  await unchanged();
  const tree = await git.api('POST', 'git/trees', { base_tree: (await git.tree(loaded.head)).sha, tree: changes });
  if (!SHA.test(tree.sha || '')) fail(502, 'settings_request_not_verified');
  const commit = await git.api('POST', 'git/commits', { message: cancel ? '[settings draft] cancel publication request' : '[settings draft] request publication',
    tree: tree.sha, parents: [loaded.head] });
  if (!SHA.test(commit.sha || '')) fail(502, 'settings_request_not_verified');
  await unchanged();
  const result = await git.api('PATCH', 'git/refs/heads/' + encodeURIComponent(contract.branch), {sha: commit.sha, force: false});
  if (result.ref !== 'refs/heads/' + contract.branch || result.object?.type !== 'commit' || result.object.sha !== commit.sha) fail(502, 'settings_request_not_verified');
  try {
    const current = await state(git);
    if (current.head !== commit.sha || current.main !== loaded.main || current.blobSha !== loaded.blobSha || current.conflict ||
        (cancel ? current.request !== null : current.request?.draftHead !== loaded.head)) fail(502, 'settings_request_not_verified');
    return { ...current, verified: true };
  } catch (_) { fail(502, 'settings_request_not_verified'); }
}
export default async function handler(req) {
  if (!['GET', 'POST'].includes(req.method)) return new Response(null, { status: 405, headers: { Allow: 'GET, POST', 'Cache-Control': 'no-store' } });
  try {
    const selector = new URL(req.url).search;
    const observing = req.method === 'GET' && selector === '?publication=1';
    if (selector && !observing) fail(400, 'invalid_settings_selector');
    if (req.method === 'POST' && (req.headers.get('origin') !== new URL(req.url).origin ||
        (req.headers.has('sec-fetch-site') && req.headers.get('sec-fetch-site') !== 'same-origin'))) fail(403, 'same_origin_required');
    const session = await getSession(req);
    if (!session?.pat || session.login !== 'expertise88864') fail(401, 'login_required');
    const git = settingsGit(session.pat);
    if (req.method === 'GET') {
      const loaded = await state(git);
      if (!observing) return json(200, loaded);
      return json(200, {...loaded,publication:await settingsObservation(git,loaded)});
    }
    const input = await bodyOf(req);
    if (input?.action === 'reconcile-catalog') return json(200, await reconcileCatalog(git, input));
    if (input?.action === 'new-version') return json(200, await newVersion(git, input));
    return json(200, input && Object.hasOwn(input, 'action') ? await requestPublication(git, input) : await save(git, input));
  } catch (error) {
    return json(error instanceof SettingsError ? error.status : 503,
      { ok: false, error: error instanceof SettingsError ? error.code : 'settings_unavailable' });
  }
}
