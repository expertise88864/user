const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const fonts = JSON.parse(fs.readFileSync('_site_settings_contract.json', 'utf8')).fonts;
const clone = value => JSON.parse(JSON.stringify(value));
const sha = letter => letter.repeat(40);
const settings = () => ({version: 1, legacyPicks: true, font: {bodyFont: '', headFont: '', bodySize: ''}, order: [], picks: ['alpha']});
const base = () => ({main: sha('a'), head: null, blobSha: sha('b'), baseSha: sha('b'), catalogSha: sha('c'),
  mainBlobSha: sha('b'), mainCatalogSha: sha('c'), settings: settings(), sourceSettings: settings(),
  articles: ['alpha', 'beta', 'gamma'].map(slug => ({slug, title: '文章 ' + slug, title_en: 'Article ' + slug})),
  conflict: false, status: 'source_base', manifestRecord: null, request: null, published: false, deploymentVerified: false});
function fixture() {
  const context = {window: {}, AbortController, TextDecoder, Uint8Array, setTimeout, clearTimeout};
  vm.runInNewContext(fs.readFileSync('admin/settings-drafts.js', 'utf8'), context);
  const calls = [], updates = [], values = new Map(), auth = {pat: 'fixture-only', revision: 0};
  const storage = {getItem: key => values.get(key) || null, setItem: (key, value) => { if (storage.fail) throw Error('quota'); values.set(key, value); }};
  const model = context.window.CDSettingsDrafts.create({fonts, storage, auth: {getPat: () => auth.pat, getRevision: () => auth.revision},
    changed: state => updates.push(state), fetch: (url, options) => new Promise((resolve, reject) => calls.push({url, options, resolve, reject}))});
  const snapshot = model.snapshot;
  model.snapshot = () => clone(snapshot()); // Assertions compare data, not VM-realm prototypes.
  return {model, calls, auth, storage, values, updates};
}
async function load(h, data = base()) { const pending = h.model.load(); h.calls.at(-1).resolve(Response.json(data)); await pending; }
function observation(data = base(), changes = {}) {
  return {...clone(data), publication: {kind:'site-settings', state:'live', loadedHead:data.head, loadedBlobSha:data.blobSha,
    mainSha:data.main, mainBlobSha:data.mainBlobSha, settingsValidated:true, ciVerified:true, deploymentVerified:true,
    published:data.blobSha===data.mainBlobSha, matchesLoadedVersion:data.blobSha===data.mainBlobSha,
    checks:[], deploymentId:201, observedAt:new Date().toISOString(), ...changes}};
}
test('explicit publication observation is read-only, snapshot-bound and never writes or adopts server settings', async () => {
  const h=fixture(); await load(h); const before=h.model.snapshot();
  const pending=h.model.observe(),call=h.calls.at(-1);
  assert.equal(call.url,'/api/admin/site-settings?publication=1'); assert.equal(call.options.method,'GET');
  assert.equal(call.options.body,undefined); assert.equal(call.options.headers,undefined);
  call.resolve(Response.json(observation())); await pending;
  const after=h.model.snapshot(); assert.equal(after.publication.published,true);
  assert.deepEqual(after.working,before.working); assert.deepEqual(after.loaded,before.loaded);
  h.model.set('font',{...settings().font,bodySize:'18px'}); assert.equal(h.model.snapshot().publication,null);
});
test('typing or a newer cloud head during observation invalidates the result and retains working content', async () => {
  for(const change of ['typing','cloud']){
    const h=fixture(); await load(h); const pending=h.model.observe();
    if(change==='typing') h.model.set('font',{...settings().font,bodySize:'18px'});
    const data=change==='cloud'?{...base(),head:sha('d'),status:'cloud_draft'}:base();
    h.calls.at(-1).resolve(Response.json(observation(data)));
    await assert.rejects(pending,/publication_changed/);
    assert.equal(h.model.snapshot().publication,null);
    assert.equal(h.model.snapshot().working.font.bodySize,change==='typing'?'18px':'');
    assert.equal(h.model.snapshot().loaded.head,null);
  }
});
test('observation cannot reuse a login epoch or be displayed after logout', async () => {
  const h=fixture(); await load(h); let pending=h.model.observe();
  h.auth.revision++; h.calls.at(-1).resolve(Response.json(observation()));
  await assert.rejects(pending,/login_changed/); assert.equal(h.model.snapshot().publication,null);
  await load(h); pending=h.model.observe(); h.calls.at(-1).resolve(Response.json(observation())); await pending;
  h.auth.pat=null; assert.equal(h.model.snapshot().publication,null);
});
test('forged observation booleans, source identity and green claims are rejected without losing edits', async () => {
  for(const changes of [{published:1},{ciVerified:false},{deploymentVerified:false},{state:'ci_running'},
    {mainSha:sha('d')},{loadedBlobSha:sha('e')},{loadedHead:sha('f')},{settingsValidated:false},{matchesLoadedVersion:false},
    {deploymentId:0},{kind:'article'},{observedAt:'invalid'}]){
    const h=fixture(); await load(h); const pending=h.model.observe();
    h.calls.at(-1).resolve(Response.json(observation(base(),changes)));
    await assert.rejects(pending,/publication_unavailable/); assert.equal(h.model.snapshot().publication,null);
    assert.deepEqual(h.model.snapshot().working,settings());
  }
});
test('failed or different deployed version remains an observation without publication claim', async () => {
  for(const data of [observation(base(),{state:'ci_failed',ciVerified:false,deploymentVerified:false,published:false}),
    observation({...base(),head:sha('d'),blobSha:sha('e'),status:'cloud_draft'})]){
    const h=fixture(); const {publication,...loaded}=data; await load(h,loaded);
    const pending=h.model.observe(); h.calls.at(-1).resolve(Response.json(data)); await pending;
    assert.equal(h.model.snapshot().publication.published,false); assert.equal(h.model.snapshot().dirty,false);
  }
});
async function readyCycle(h, observed = null) {
  const loaded={...base(),head:sha('d'),blobSha:sha('e'),status:'cloud_draft'};
  loaded.settings.font.bodySize='18px'; await load(h,loaded);
  const pending=h.model.observe();h.calls.at(-1).resolve(Response.json(observed||observation(loaded)));await pending;
  return loaded;
}
function cycleResult(observed) {
  const result={...clone(observed),head:sha('f'),blobSha:observed.mainBlobSha,baseSha:observed.mainBlobSha,
    catalogSha:observed.mainCatalogSha,settings:clone(observed.sourceSettings),status:'cloud_draft',conflict:false,
    verified:true,request:null,manifestRecord:{baseMain:observed.main}};
  delete result.publication;return result;
}
function catalogBase(){const value=base();value.sourceRequiresReview=true;value.conflict=true;value.status='conflict';
 value.head=sha('d');value.catalogSha=sha('e');value.mainCatalogSha=sha('f');value.settings.order=['gamma','alpha','beta'];
 value.sourceSettings.legacyPicks=false;value.articles=value.articles.filter(a=>a.slug!=='alpha').concat({slug:'delta',title:'New article',title_en:'New article'});return value;}
function catalogResult(before,selected){return {...clone(before),head:sha('1'),blobSha:sha('2'),baseSha:before.mainBlobSha,
 catalogSha:before.mainCatalogSha,settings:clone(selected),conflict:false,status:'cloud_draft',request:null,verified:true,manifestRecord:{baseMain:before.main}};}
test('catalogue comparison is read-only, names removed/additional articles and never invents replacement picks',async()=>{
 const h=fixture();await load(h,catalogBase());const before=h.model.snapshot(),calls=h.calls.length;
 const plan=h.model.catalogPlan();assert.deepEqual(clone(plan.removed),['alpha']);assert.deepEqual(clone(plan.added),['delta']);
 assert.deepEqual(clone(plan.settings.order),['gamma','beta','delta']);assert.deepEqual(clone(plan.settings.picks),[]);
 assert.equal(plan.settings.legacyPicks,false);assert.deepEqual(h.model.snapshot(),before);assert.equal(h.calls.length,calls);
 await assert.rejects(h.model.reconcileCatalog(plan.settings,true,before.editRevision),/invalid_settings/);
 await assert.rejects(h.model.reconcileCatalog({...plan.settings,picks:['beta']},false,before.editRevision),/confirmation/);
 assert.equal(h.calls.length,calls);
});
test('explicit catalogue confirmation pins main/draft/blob/catalogue and creates a draft without deleting recovery',async()=>{
 const h=fixture(),before=catalogBase();await load(h,before);h.values.set('cd_site_settings_local_v2','retained original');
 const selected={...clone(h.model.catalogPlan().settings),picks:['beta']};const pending=h.model.reconcileCatalog(selected,true,h.model.snapshot().editRevision);
 const input=JSON.parse(h.calls.at(-1).options.body);assert.equal(input.action,'reconcile-catalog');assert.equal(input.expectedHead,before.head);
 assert.equal(input.expectedMain,before.main);assert.equal(input.expectedMainBlob,before.mainBlobSha);assert.equal(input.expectedCatalog,before.mainCatalogSha);
 h.calls.at(-1).resolve(Response.json(catalogResult(before,selected)));await pending;
 assert.deepEqual(h.model.snapshot().working,selected);assert.equal(h.model.snapshot().dirty,false);
 assert.equal(h.values.get('cd_site_settings_local_v2'),'retained original');assert.equal(h.model.snapshot().loaded.published,false);
});
test('catalogue conflicts and ambiguous acknowledgements retain the old source and block blind retry',async()=>{
 for(const variant of ['race','unknown','wrong','auth']){
  const h=fixture(),before=catalogBase();await load(h,before);const original=h.model.snapshot();
  const selected={...clone(h.model.catalogPlan().settings),picks:['beta']},pending=h.model.reconcileCatalog(selected,true,original.editRevision);
  if(variant==='auth')h.auth.revision++;
  if(variant==='race')h.calls.at(-1).resolve(Response.json({error:'private'},{status:409}));
  else if(variant==='unknown')h.calls.at(-1).reject(Error('network private'));
  else {const result=catalogResult(before,selected);if(variant==='wrong')result.baseSha=sha('3');h.calls.at(-1).resolve(Response.json(result));}
  await assert.rejects(pending);assert.deepEqual(h.model.snapshot().loaded,original.loaded);assert.equal(h.model.snapshot().working,null);
  const n=h.calls.length;await assert.rejects(h.model.reconcileCatalog(selected,true,original.editRevision));assert.equal(h.calls.length,n);
 }
});
test('new cycle requires explicit confirmation and pinned observation; reset saves a draft, never publishes',async()=>{
  const h=fixture(),before=await readyCycle(h),revision=h.model.snapshot().editRevision;
  await assert.rejects(h.model.newVersion(false,revision),/settings_confirmation_required/);
  await assert.rejects(h.model.newVersion(true,revision+1),/settings_not_ready/);
  const pending=h.model.newVersion(true,revision),call=h.calls.at(-1),input=JSON.parse(call.options.body);
  assert.deepEqual(input,{action:'new-version',expectedHead:before.head,blobSha:before.blobSha,
    expectedMain:before.main,expectedMainBlob:before.mainBlobSha,expectedCatalog:before.mainCatalogSha,confirmed:true});
  call.resolve(Response.json(cycleResult(before)));await pending;
  const after=h.model.snapshot();assert.equal(after.loaded.head,sha('f'));assert.equal(after.status,'new_version_created');
  assert.deepEqual(after.working,before.sourceSettings);assert.equal(after.dirty,false);assert.equal(after.loaded.published,false);
  assert.equal(after.publication,null);assert.equal(h.values.size,0,'no automatic overwrite of recovery backups');
});
test('new cycle adopts new baseline while retaining only changes typed after submission',async()=>{
  const h=fixture(),before=await readyCycle(h),revision=h.model.snapshot().editRevision;
  const pending=h.model.newVersion(true,revision);
  h.model.set('picks',['beta']);h.model.set('order',['gamma','beta','alpha']);
  h.calls.at(-1).resolve(Response.json(cycleResult(before)));await pending;
  const after=h.model.snapshot();assert.equal(after.working.font.bodySize,'','unmodified old font adopts selected website baseline');
  assert.deepEqual(after.working.picks,['beta']);assert.deepEqual(after.working.order,['gamma','beta','alpha']);
  assert.equal(after.working.legacyPicks,false);assert.equal(after.dirty,true);assert.equal(after.status,'new_version_newer_local_changes');
});
test('catalogue invalidates typing during a new cycle: retain old working/base and offer verified remote comparison',async()=>{
  const h=fixture(),initial={...base(),head:sha('d'),blobSha:sha('e'),status:'cloud_draft'};initial.settings.font.bodySize='18px';
  const current={...clone(initial),mainCatalogSha:sha('f'),articles:initial.articles.filter(a=>a.slug!=='beta'),conflict:true,status:'conflict'};
  await readyCycle(h,observation(current));const revision=h.model.snapshot().editRevision,pending=h.model.newVersion(true,revision);
  h.model.set('picks',['beta']);const afterServer=cycleResult(current);afterServer.head=sha('a');
  h.calls.at(-1).resolve(Response.json(afterServer));await pending;
  const state=h.model.snapshot();assert.equal(state.status,'compare_required');assert.deepEqual(state.working.picks,['beta']);
  assert.equal(state.loaded.head,initial.head);assert.equal(state.remote.head,afterServer.head);assert.equal(state.needsRefresh,true);
  assert.equal(h.model.saveLocal(),true);const saved=JSON.parse(h.values.get('cd_site_settings_local_v2'));
  assert.equal(saved.head,initial.head);assert.equal(saved.catalogSha,initial.catalogSha);
  h.model.adoptRemote(state.editRevision);assert.deepEqual(h.model.snapshot().working.picks,['alpha']);
});
test('late new cycle response after re-login cannot adopt or overwrite working/recovery',async()=>{
  const h=fixture(),before=await readyCycle(h),revision=h.model.snapshot().editRevision,pending=h.model.newVersion(true,revision);
  h.model.set('font',{...settings().font,bodySize:'17px'});h.auth.revision++;
  h.calls.at(-1).resolve(Response.json(cycleResult(before)));await assert.rejects(pending,/login_changed/);
  const after=h.model.snapshot();assert.equal(after.working.font.bodySize,'17px');assert.equal(after.loaded.head,before.head);
  assert.equal(after.authorised,false);assert.equal(after.publication,null);assert.equal(after.needsRefresh,true);
});
test('new cycle ambiguous write/conflict/wrong baseline forbids retry and preserves old draft',async()=>{
  for(const kind of ['network','conflict','wrong']){
    const h=fixture(),before=await readyCycle(h),revision=h.model.snapshot().editRevision,pending=h.model.newVersion(true,revision);
    if(kind==='network')h.calls.at(-1).reject(Error('fixture-only private details'));
    else if(kind==='conflict')h.calls.at(-1).resolve(Response.json({error:'settings_conflict'},{status:409}));
    else h.calls.at(-1).resolve(Response.json({...cycleResult(before),baseSha:sha('d')}));
    await assert.rejects(pending);assert.equal(h.model.snapshot().loaded.head,before.head);
    assert.equal(h.model.snapshot().working.font.bodySize,'18px');assert.equal(h.model.snapshot().publication,null);
    await assert.rejects(h.model.newVersion(true,revision),/settings_not_ready/);
  }
});
test('new cycle explains known publication/retirement gates without exposing arbitrary provider errors',async()=>{
  for(const code of ['settings_receipt_not_retired','settings_publication_not_verified','fixture-only secret']){
    const h=fixture(),before=await readyCycle(h),revision=h.model.snapshot().editRevision,pending=h.model.newVersion(true,revision);
    h.calls.at(-1).resolve(Response.json({error:code},{status:409}));await assert.rejects(pending);
    assert.equal(h.model.snapshot().status,code==='fixture-only secret'?'settings_conflict':code);
    assert.equal(h.model.snapshot().loaded.head,before.head);assert.equal(h.model.snapshot().working.font.bodySize,'18px');
    assert.ok(!JSON.stringify(h.updates).includes('fixture-only secret'));
  }
});
test('saving the displayed initial picks explicitly migrates them without requiring an artificial list edit', async () => {
  const h = fixture(); await load(h);
  const before = h.model.snapshot().loaded, pending = h.model.saveCloud('picks'), call = h.calls.at(-1);
  const input = JSON.parse(call.options.body); call.resolve(Response.json(saved(before, input))); await pending;
  assert.equal(h.model.snapshot().working.legacyPicks, false);
  assert.equal(h.model.snapshot().dirty, false);
});
test('local picks migration remains unsaved during a font save and is acknowledged only by a picks save', async () => {
  const h = fixture(); await load(h);
  assert.equal(h.model.snapshot().working.legacyPicks, true);
  h.model.set('picks', ['alpha']);
  assert.equal(h.model.snapshot().working.legacyPicks, false);
  assert.equal(h.model.snapshot().dirty, true, 'same displayed list still requires explicit migration approval');
  h.model.set('font', {...settings().font, bodySize: '18px'});
  let before = h.model.snapshot().loaded, pending = h.model.saveCloud('font'), input = JSON.parse(h.calls.at(-1).options.body);
  h.calls.at(-1).resolve(Response.json(saved(before, input))); await pending;
  assert.equal(h.model.snapshot().loaded.settings.legacyPicks, true);
  assert.equal(h.model.snapshot().working.legacyPicks, false);
  assert.throws(() => h.model.publication(true), /settings_approval_required/);
  before = h.model.snapshot().loaded; pending = h.model.saveCloud('picks'); input = JSON.parse(h.calls.at(-1).options.body);
  h.calls.at(-1).resolve(Response.json(saved(before, input, 'f'))); await pending;
  assert.equal(h.model.snapshot().loaded.settings.legacyPicks, false);
  assert.equal(h.model.snapshot().dirty, false);
});
function saved(before, input, next = 'd') {
  const result = {...clone(before), head: sha(next), verified: true};
  if (input.kind) {
    result.settings[input.kind] = clone(input.values); result.blobSha = sha('e'); result.request = null; result.status = 'cloud_draft';
    if (input.kind === 'picks') result.settings.legacyPicks = false;
  } else if (input.action === 'request-publication') {
    result.status = 'requested'; result.request = {draftHead: before.head, requestHead: result.head, blobSha: before.blobSha};
  } else { result.status = 'cloud_draft'; result.request = null; }
  return result;
}
test('loads only the fixed cookie endpoint; no credential or publication assertion is transmitted', async () => {
  const h = fixture(); await load(h);
  assert.equal(h.calls[0].url, '/api/admin/site-settings'); assert.equal(h.calls[0].options.credentials, 'same-origin');
  assert.equal(h.calls[0].options.redirect, 'error'); assert.equal(h.calls[0].options.headers, undefined);
  assert.equal(h.model.snapshot().dirty, false); assert.equal(h.model.snapshot().loaded.published, false);
  assert.ok(!JSON.stringify(h.updates).includes('fixture-only'));
});
test('font save uses a frozen snapshot; typing during the request remains unsaved', async () => {
  const h = fixture(); await load(h); h.model.set('font', {...settings().font, bodySize: '17px'});
  const before = h.model.snapshot().loaded, operation = h.model.saveCloud('font'), call = h.calls.at(-1), input = JSON.parse(call.options.body);
  h.model.set('font', {...settings().font, bodySize: '18px'});
  assert.equal(input.values.bodySize, '17px'); call.resolve(Response.json(saved(before, input))); await operation;
  const after = h.model.snapshot(); assert.equal(after.loaded.settings.font.bodySize, '17px'); assert.equal(after.working.font.bodySize, '18px');
  assert.equal(after.dirty, true); assert.equal(after.status, 'cloud_saved_newer_local_changes');
});
test('saving one kind preserves unsaved edits of both other kinds', async () => {
  const h = fixture(); await load(h); h.model.set('font', {...settings().font, bodySize: '18px'});
  h.model.set('picks', ['beta']); h.model.set('order', ['gamma', 'beta', 'alpha']);
  const before = h.model.snapshot().loaded, pending = h.model.saveCloud('font'), call = h.calls.at(-1);
  call.resolve(Response.json(saved(before, JSON.parse(call.options.body)))); await pending;
  const after = h.model.snapshot(); assert.deepEqual(after.working.picks, ['beta']); assert.deepEqual(after.loaded.settings.picks, ['alpha']);
  assert.deepEqual(after.working.order, ['gamma', 'beta', 'alpha']); assert.equal(after.uncertain, false); assert.equal(after.dirty, true);
});
test('late refresh never replaces edits; adopting a comparison requires the unchanged edit revision', async () => {
  const h = fixture(); await load(h); const pending = h.model.load();
  h.model.set('font', {...settings().font, bodySize: '18px'});
  const next = {...base(), head: sha('f'), status: 'cloud_draft'}; h.calls.at(-1).resolve(Response.json(next)); await pending;
  assert.equal(h.model.snapshot().loaded.head, null); assert.equal(h.model.snapshot().working.font.bodySize, '18px');
  assert.equal(h.model.snapshot().status, 'compare_required'); assert.throws(() => h.model.saveCloud('font'), /settings_not_ready/);
  const revision = h.model.snapshot().editRevision; h.model.set('picks', ['beta']);
  assert.throws(() => h.model.adoptRemote(revision), /settings_changed/);
  h.model.adoptRemote(h.model.snapshot().editRevision); assert.equal(h.model.snapshot().loaded.head, sha('f'));
});
test('logout and re-login with the same PAT invalidate an in-flight response', async () => {
  const h = fixture(); await load(h); h.model.set('picks', ['beta']); const before = h.model.snapshot().loaded;
  const pending = assert.rejects(h.model.saveCloud('picks'), /login_changed/), call = h.calls.at(-1);
  h.auth.revision++; call.resolve(Response.json(saved(before, JSON.parse(call.options.body)))); await pending;
  assert.equal(h.model.snapshot().loaded, null); assert.deepEqual(h.model.snapshot().working.picks, ['beta']);
  assert.equal(h.model.snapshot().busy, false);
});
test('uncertain write forbids another write and refresh offers comparison instead of silently acknowledging it', async () => {
  const h = fixture(); await load(h); h.model.set('picks', ['beta']); const before = h.model.snapshot().loaded;
  const pending = assert.rejects(h.model.saveCloud('picks'), /write_unconfirmed/), call = h.calls.at(-1), input = JSON.parse(call.options.body);
  call.reject(Error('private provider token')); await pending; assert.equal(h.model.snapshot().uncertain, true);
  assert.throws(() => h.model.saveCloud('picks'), /settings_not_ready/); assert.equal(h.calls.length, 2);
  await load(h, saved(before, input)); assert.equal(h.model.snapshot().status, 'compare_required');
  assert.equal(h.model.snapshot().loaded.head, null); assert.deepEqual(h.model.snapshot().working.picks, ['beta']);
  assert.ok(!JSON.stringify(h.updates).includes('private provider token'));
  h.model.adoptRemote(h.model.snapshot().editRevision); assert.equal(h.model.snapshot().uncertain, false);
});
test('conflict or quota failures preserve working content and previous recovery bytes', async () => {
  const h = fixture(); await load(h); h.model.set('picks', ['beta']); assert.equal(h.model.saveLocal(), true);
  const prior = [...h.values.values()][0]; h.model.set('picks', ['gamma']); h.storage.fail = true;
  assert.equal(h.model.saveLocal(), false); assert.equal([...h.values.values()][0], prior);
  const pending = assert.rejects(h.model.saveCloud('picks'), /settings_conflict/); h.calls.at(-1).resolve(Response.json({error: 'private conflict'}, {status: 409})); await pending;
  assert.deepEqual(h.model.snapshot().working.picks, ['gamma']); assert.equal(h.model.snapshot().uncertain, false);
  assert.equal([...h.values.values()][0], prior);
  h.model.set('picks', ['beta']); assert.throws(() => h.model.saveCloud('picks'), /settings_not_ready/);
  await load(h); assert.equal(h.model.snapshot().status, 'compare_required');
  h.model.adoptRemote(h.model.snapshot().editRevision); assert.equal(h.model.snapshot().needsRefresh, false);
});
test('a comparison or an earlier cloud base cannot be reused after logout and re-login', async () => {
  const h = fixture(); await load(h); h.auth.revision++;
  assert.throws(() => h.model.saveCloud('font'), /login_changed/); assert.equal(h.calls.length, 1);
  h.model.set('picks', ['beta']); await load(h); const edit = h.model.snapshot().editRevision; h.auth.revision++;
  assert.throws(() => h.model.adoptRemote(edit), /login_changed/); assert.deepEqual(h.model.snapshot().working.picks, ['beta']);
});
test('recovery requires exact head/base/catalog, never deletes mismatched copies or includes a PAT', async () => {
  const h = fixture(); await load(h); h.model.set('picks', ['beta']); h.model.saveLocal();
  const copy = [...h.values.values()][0]; assert.ok(!copy.includes('fixture-only'));
  const next = {...base(), head: sha('f'), status: 'cloud_draft'}; await load(h, next); h.model.adoptRemote(h.model.snapshot().editRevision);
  assert.equal(h.model.recoverLocal(), false); assert.equal(h.model.snapshot().status, 'local_recovery_conflict');
  assert.equal([...h.values.values()][0], copy);
});
test('publication requires saved exact content and explicit literal approval', async () => {
  const h = fixture(), cloud = {...base(), head: sha('f'), status: 'cloud_draft'};
  cloud.settings.legacyPicks = false; await load(h, cloud);
  assert.throws(() => h.model.publication('true'), /settings_approval_required/);
  h.model.set('picks', ['beta']); assert.throws(() => h.model.publication(true), /settings_approval_required/);
  h.model.set('picks', ['alpha']); const operation = h.model.publication(true), call = h.calls.at(-1), input = JSON.parse(call.options.body);
  assert.equal(input.expectedHead, sha('f')); assert.equal(input.settingsApproved, true); call.resolve(Response.json(saved(cloud, input))); await operation;
  assert.equal(h.model.snapshot().status, 'requested'); assert.equal(h.model.snapshot().loaded.published, false);
});
test('simultaneous cloud operations are prevented and public settings are not accepted as a live acknowledgement', async () => {
  const h = fixture(); const operation = assert.rejects(h.model.load(), /request_failed/);
  await assert.rejects(h.model.load(), /settings_busy/);
  h.calls[0].resolve(Response.json({...base(), published: true, deploymentVerified: true})); await operation;
  assert.equal(h.calls.length, 1); assert.equal(h.model.snapshot().loaded, null);
});
test('a wrong saved value cannot claim success even with a verified flag and a fresh SHA', async () => {
  const h = fixture(); await load(h); h.model.set('picks', ['beta']); const before = h.model.snapshot().loaded;
  const operation = assert.rejects(h.model.saveCloud('picks'), /write_unconfirmed/), call = h.calls.at(-1);
  const wrong = saved(before, JSON.parse(call.options.body)); wrong.settings.picks = ['gamma']; call.resolve(Response.json(wrong)); await operation;
  assert.equal(h.model.snapshot().loaded.head, null); assert.deepEqual(h.model.snapshot().working.picks, ['beta']); assert.equal(h.model.snapshot().uncertain, true);
});
test('request cancellation keeps subsequent typing and reports only the immutable cancelled version', async () => {
  const h = fixture(), cloud = {...base(), head: sha('f'), status: 'requested', request: {draftHead: sha('a'), requestHead: sha('f'), blobSha: sha('b')}};
  await load(h, cloud); const operation = h.model.cancelRequest(), call = h.calls.at(-1), input = JSON.parse(call.options.body);
  assert.equal(input.action, 'cancel-request'); assert.equal(input.expectedHead, sha('f'));
  h.model.set('picks', ['beta']); call.resolve(Response.json(saved(cloud, input))); await operation;
  assert.equal(h.model.snapshot().loaded.request, null); assert.deepEqual(h.model.snapshot().working.picks, ['beta']);
  assert.equal(h.model.snapshot().status, 'cloud_saved_newer_local_changes');
});
test('oversized response is cancelled without applying it or discarding working recovery', async () => {
  const h = fixture(); await load(h); h.model.set('picks', ['beta']); h.model.saveLocal(); const prior = [...h.values.values()][0];
  const operation = assert.rejects(h.model.load(), /request_failed/); h.calls.at(-1).resolve(new Response(' '.repeat(384_001))); await operation;
  assert.deepEqual(h.model.snapshot().working.picks, ['beta']); assert.equal([...h.values.values()][0], prior);
});
test('returned snapshots cannot mutate loaded metadata or the version being saved', async () => {
  const h = fixture(); await load(h); const snapshot = h.model.snapshot(); snapshot.loaded.baseSha = sha('f'); snapshot.working.picks = ['gamma'];
  assert.equal(h.model.snapshot().loaded.baseSha, sha('b')); assert.deepEqual(h.model.snapshot().working.picks, ['alpha']);
});
