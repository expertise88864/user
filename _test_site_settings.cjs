// In-memory Git object graph only; no credentials, KV or network access.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const contract = JSON.parse(fs.readFileSync('_site_settings_contract.json', 'utf8'));
const publicationPolicy = JSON.parse(fs.readFileSync('_delivery_policy.json', 'utf8'));
const publicationContext = {URL, Date};
vm.runInNewContext(fs.readFileSync('api/admin/_article-publication.js','utf8').replace('export async function','async function')+
  '\nthis.observePublication=observePublication;',publicationContext);
const source = ['_site-settings.js', '_settings-git.js', 'site-settings.js'].map(file =>
  fs.readFileSync('api/admin/' + file, 'utf8').replace(/^import[^\n]+;\s*$/gm, '')
    .replace(/^export \{[^\n]+\};\s*$/gm, '').replace(/\bexport (class|const|function)/g, '$1')
    .replace('export default async function handler', 'async function handler')).join('\n');
const hash = value => crypto.createHash('sha1').update(value).digest('hex');
const gitBlob = bytes => hash(Buffer.concat([Buffer.from('blob ' + bytes.length + '\0'), bytes]));
const articles = ['alpha', 'beta', 'gamma'].map(slug => ({slug, title: '文章 ' + slug, title_en: 'Article ' + slug}));
const defaults = () => ({version: 1, legacyPicks: true, font: {bodyFont: '', headFont: '', bodySize: ''}, order: [], picks: ['alpha']});
function fixture(observationPolicy = publicationPolicy) {
  const blobs = new Map(), trees = new Map(), commits = new Map(), refs = new Map(), calls = [];
  const store = text => { const bytes = Buffer.isBuffer(text) ? text : Buffer.from(text); const sha = gitBlob(bytes); blobs.set(sha, bytes); return sha; };
  const treeId = tree => hash(JSON.stringify([...tree]));
  const initial = new Map([[contract.source, store(JSON.stringify(defaults()))], [contract.catalog, store(JSON.stringify({version: 1, articles}))]]);
  const tree = treeId(initial), main = hash('main');
  trees.set(tree, initial); commits.set(main, {tree: {sha: tree}, parents: []}); refs.set('main', main);
  const h = {blobs, trees, commits, refs, calls, store, main, session: true, timeouts: []};
  h.changeMain = (path, value, canonical = false) => {
    const nextTree = new Map(trees.get(commits.get(refs.get('main')).tree.sha));
    nextTree.set(path, store(JSON.stringify(value,null,canonical?2:undefined)+(canonical?'\n':'')));
    const id = treeId(nextTree), sha = hash('next-main-' + id);
    trees.set(id, nextTree); commits.set(sha, {tree: {sha: id}, parents: [refs.get('main')]}); refs.set('main', sha); return sha;
  };
  async function fetch(url, options) {
    const u = new URL(url);
    assert.equal(u.origin, 'https://api.github.com');
    assert.ok(u.pathname.startsWith('/repos/expertise88864/user/'));
    assert.equal(options.redirect, 'error');
    assert.equal(options.cache, 'no-store');
    assert.equal(options.headers.Authorization, 'Bearer fixture-only');
    const path = decodeURIComponent(u.pathname.slice('/repos/expertise88864/user/'.length));
    const body = options.body && JSON.parse(options.body), call = {path, method: options.method, body};
    calls.push(call);
    if (h.stall) return new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(Error('fixture timeout')), {once: true}));
    if (h.before) await h.before(call);
    if (h.fail === path) throw Error('private credential / fixture-only');
    let result;
    if (path.startsWith('actions/runs')) {
      if(path==='actions/runs') result={workflow_runs:h.workflowRuns||[]};
      else { const run=Number(path.split('/')[2]); result={jobs:h.workflowJobs?.get(run)||[]}; }
    } else if(path==='deployments') result=h.deployments||[];
    else if(/^deployments\/\d+\/statuses$/.test(path)) result=h.deploymentStatuses?.get(Number(path.split('/')[1]))||[];
    else if (path.startsWith('git/ref/heads/')) {
      const branch = path.slice(14), sha = refs.get(branch);
      if (!sha) return Response.json({}, {status: 404});
      result = {ref: 'refs/heads/' + branch, object: {sha, type: 'commit'}};
    } else if (path.startsWith('git/commits/')) {
      const sha = path.slice(12); assert.ok(commits.has(sha)); result = {sha, ...commits.get(sha), parents: commits.get(sha).parents.map(sha => ({sha}))};
    } else if (path.startsWith('git/trees/')) {
      const sha = path.slice(10); assert.ok(trees.has(sha)); result = {sha, truncated: false,
        tree: [...trees.get(sha)].map(([path, sha]) => ({path, sha, type: 'blob', mode: '100644'}))};
    } else if (path.startsWith('contents/')) {
      const head = u.searchParams.get('ref'); assert.ok(commits.has(head), 'all contents must use immutable SHA');
      const sha = trees.get(commits.get(head).tree.sha).get(path.slice(9)); assert.ok(sha);
      const bytes = blobs.get(sha); result = {sha, type: 'file', encoding: 'base64', size: bytes.length, content: bytes.toString('base64')};
    } else if (path === 'git/blobs') {
      assert.equal(body.encoding, 'utf-8'); result = {sha: store(body.content)};
    } else if (path === 'git/trees') {
      const next = new Map(trees.get(body.base_tree));
      for (const entry of body.tree) {
        assert.ok([contract.source, contract.manifest, contract.request].includes(entry.path));
        assert.equal(entry.mode, '100644'); assert.equal(entry.type, 'blob');
        if (entry.sha === null) next.delete(entry.path); else next.set(entry.path, entry.sha || store(entry.content));
      }
      const sha = treeId(next); trees.set(sha, next); result = {sha};
    } else if (path === 'git/commits') {
      if (body.message === '[settings draft] new version from verified production' || body.message === '[settings draft] reconcile article catalogue') {
        assert.ok(body.parents.length >= 1 && body.parents.length <= 2);
        assert.equal(body.parents[0], refs.get(contract.branch) || refs.get('main'));
        assert.ok(body.parents.includes(refs.get('main')));
      } else assert.equal(body.parents.length, 1);
      assert.ok(body.parents.every(sha => commits.has(sha)));
      const sha = hash(JSON.stringify(body)); commits.set(sha, {tree: {sha: body.tree}, parents: body.parents}); result = {sha};
    } else if (path === 'git/refs' || path.startsWith('git/refs/heads/')) {
      const branch = path === 'git/refs' ? body.ref.slice(11) : path.slice(15);
      assert.equal(branch, contract.branch, 'no main or caller-selected branch writes');
      assert.ok(body.force === undefined || body.force === false);
      if (h.race || (path === 'git/refs' && refs.has(branch)) ||
          (path !== 'git/refs' && commits.get(body.sha).parents[0] !== refs.get(branch))) return Response.json({}, {status: 422});
      refs.set(branch, body.sha); result = {ref: 'refs/heads/' + branch, object: {sha: body.sha, type: 'commit'}};
      if (h.uncertain) throw Error('fixture-only / upstream details');
    } else assert.fail('unexpected request: ' + path);
    if (h.after) await h.after(call);
    if (h.tamper) result = h.tamper(call, result);
    if (h.raw) { const raw = h.raw(call, result); if (raw) return raw; }
    return Response.json(result);
  }
  const context = {contract, URL, Request, Response, TextEncoder, TextDecoder, Uint8Array, AbortController,
    setTimeout: (callback, milliseconds) => { h.timeouts.push(milliseconds); return setTimeout(callback, h.fastTimers ? 10 : milliseconds); },
    clearTimeout, atob, crypto: crypto.webcrypto, fetch,
    getSession: async () => h.session ? {pat: 'fixture-only', login: h.login || 'expertise88864'} : null,
    observePublication:publicationContext.observePublication,publicationPolicy:observationPolicy};
  // Each source module has its own encoder binding.
  vm.runInNewContext(source.replace('const encoder = new TextEncoder();', 'const gitEncoder = new TextEncoder();')
    .replace("const header = encoder.encode('blob ", "const header = gitEncoder.encode('blob ") + '\nthis.api={handler,parseJson,settingsOf,catalogOf,settingsGit};', context);
  h.api = context.api;
  h.request = (input, options = {}) => h.api.handler(new Request('https://editor.test/api/admin/site-settings' + (options.query || ''), {
    method: input === undefined ? 'GET' : 'POST', headers: {origin: 'https://editor.test', 'content-type': 'application/json', ...options.headers},
    ...(input === undefined ? {} : {body: typeof input === 'string' ? input : JSON.stringify(input)}),
    ...Object.fromEntries(Object.entries(options).filter(([key]) => !['headers', 'query'].includes(key))),
  }));
  h.input = (loaded, extra = {}) => ({expectedHead: loaded.head, baseSha: loaded.baseSha, catalogSha: loaded.catalogSha,
    kind: 'font', values: {...defaults().font, bodySize: '18px'}, ...extra});
  h.read = async () => { const response = await h.request(); assert.equal(response.status, 200); return response.json(); };
  return h;
}
function noWrites(h) { assert.equal(h.calls.filter(call => call.method !== 'GET').length, 0); }
async function catalogConflict(withDraft = true) {
  const h=fixture();h.changeMain('.site-settings-delivery.json',{version:1,request:null},true);
  if(withDraft) {let v=await h.read();await h.request(h.input(v));v=await h.read();
    await h.request({action:'request-publication',expectedHead:v.head,blobSha:v.blobSha,baseSha:v.baseSha,catalogSha:v.catalogSha,settingsApproved:true});}
  h.changeMain('_site_settings.json',{...defaults(),legacyPicks:false,order:['gamma','alpha','beta']});
  h.changeMain(contract.catalog,{version:1,articles:['beta','gamma','delta'].map(slug=>({slug,title:'Article '+slug,title_en:'Article '+slug}))});
  const loaded=await h.read();h.calls.length=0;
  const input={action:'reconcile-catalog',expectedHead:loaded.head,blobSha:loaded.blobSha,expectedMain:loaded.main,
    expectedMainBlob:loaded.mainBlobSha,expectedCatalog:loaded.mainCatalogSha,confirmed:true,
    settings:{...loaded.settings,legacyPicks:false,order:['gamma','beta','delta'],picks:['beta']}};
  return {h,loaded,input};
}
for(const withDraft of [false,true]) test('catalogue reconciliation preserves old history and current main with existing draft='+withDraft,async()=>{
  const {h,loaded,input}=await catalogConflict(withDraft),old=loaded.head&&h.commits.get(loaded.head);
  assert.equal(loaded.conflict,true);assert.equal(loaded.sourceRequiresReview,true);
  const response=await h.request(input),after=await response.json();assert.equal(response.status,200,JSON.stringify(after));
  assert.equal(after.verified,true);assert.equal(after.conflict,false);assert.equal(after.request,null);assert.equal(after.published,false);
  assert.equal(after.main,loaded.main);assert.deepEqual(after.settings,input.settings);
  assert.deepEqual(Array.from(h.commits.get(after.head).parents),withDraft?[loaded.head,loaded.main]:[loaded.main]);
  if(withDraft)assert.equal(h.commits.get(loaded.head),old);
  assert.equal(after.sourceRequiresReview,true,'stored main is never silently rewritten');
  const request=await h.request({action:'request-publication',expectedHead:after.head,blobSha:after.blobSha,baseSha:after.baseSha,catalogSha:after.catalogSha,settingsApproved:true});
  assert.equal(request.status,200);
});
test('reconciliation rejects stale versions, empty/private/duplicate picks, incomplete order and legacy reactivation before writes',async()=>{
  for(const change of [{confirmed:'true'},{confirmed:false},{expectedMain:hash('wrong')},{expectedHead:hash('wrong')},
    {expectedCatalog:hash('wrong')},{extra:true},{settings:{...defaults(),legacyPicks:true,picks:['beta']}},
    ...[[],['private'],['beta','beta']].map(picks=>({settings:{...defaults(),legacyPicks:false,picks}})),
    {settings:{...defaults(),legacyPicks:false,picks:['beta'],order:['beta']}}]){
    const {h,input}=await catalogConflict();const response=await h.request({...input,...change});
    assert.ok([400,409].includes(response.status),JSON.stringify(change));noWrites(h);
  }
});
test('reconciliation cannot supersede an active receipt, a malformed draft or a main/branch race',async()=>{
  for(const variant of ['active','malformed','main-race','branch-race','uncertain']){
    const {h,input,loaded}=await catalogConflict();
    if(variant==='active')input.expectedMain=h.changeMain('.site-settings-delivery.json',{version:1,request:{fake:true}},true);
    if(variant==='malformed')h.tamper=(call,value)=>{if(call.path.startsWith('contents/')&&call.path.includes(contract.source))return {...value,sha:hash('fake')};return value;};
    if(variant.endsWith('race'))h.after=call=>{if(call.path==='git/blobs'){
      if(variant==='main-race')h.refs.set('main',h.main);else h.refs.set(contract.branch,loaded.manifestRecord.baseMain);}};
    if(variant==='uncertain')h.uncertain=true;
    const response=await h.request(input);assert.ok(response.status>=400);assert.equal((await response.json()).published,undefined);
    if(['active','malformed'].includes(variant))noWrites(h);
    if(variant!=='uncertain')assert.equal(h.calls.filter(c=>c.path.startsWith('git/refs')).length,0);
  }
});
function liveSettings(h){
  const main=h.refs.get('main');
  h.workflowRuns=publicationPolicy.workflows.map((entry,index)=>({id:101+index,run_attempt:1,path:entry.path,
    head_sha:main,head_branch:'main',event:'push',head_repository:{full_name:contract.repository},status:'completed',conclusion:'success'}));
  h.workflowJobs=new Map(h.workflowRuns.map((run,index)=>[run.id,publicationPolicy.workflows[index].jobs.map(name=>({
    head_sha:main,name,status:'completed',conclusion:publicationPolicy.workflows[index].main_skips?.includes(name)?'skipped':'success',
    steps:[...publicationPolicy.workflows[index].steps[name].required,...(publicationPolicy.workflows[index].steps[name].main_required||[])].map(name=>({name,status:'completed',conclusion:'success'}))
  }))]));
  h.deployments=[{id:201,sha:main,environment:'Production',production_environment:false,creator:{login:'vercel[bot]'}}];
  h.deploymentStatuses=new Map([[201,[{id:202,state:'success',creator:{login:'vercel[bot]'},environment_url:'https://chendermatologist-fixture.vercel.app'}]]]);
}
function cycleInput(loaded,extra={}) {
  return {action:'new-version',expectedHead:loaded.head,blobSha:loaded.blobSha,expectedMain:loaded.main,
    expectedMainBlob:loaded.mainBlobSha,expectedCatalog:loaded.mainCatalogSha,confirmed:true,...extra};
}
async function publishedSettingsFixture() {
  const h=fixture();h.changeMain('.site-settings-delivery.json',{version:1,request:null},true);
  const saved=await(await h.request(h.input(await h.read()))).json();
  const requested=await(await h.request({action:'request-publication',expectedHead:saved.head,blobSha:saved.blobSha,
    baseSha:saved.baseSha,catalogSha:saved.catalogSha,settingsApproved:true})).json();
  const before=h.refs.get('main'),tree=new Map(h.trees.get(h.commits.get(before).tree.sha));
  tree.set(contract.source,requested.blobSha);
  const id=hash(JSON.stringify([...tree])),main=hash('published-'+id);
  h.trees.set(id,tree);h.commits.set(main,{tree:{sha:id},parents:[before]});h.refs.set('main',main);
  liveSettings(h);h.oldRequest=requested.head;h.oldRequestTree=[...h.trees.get(h.commits.get(requested.head).tree.sha)].map(([path,sha])=>[path,sha]);
  h.calls.length=0;return h;
}
test('new settings cycle fixes the post-publication conflict without erasing old request or main/code/history',async()=>{
  const h=await publishedSettingsFixture(),before=await h.read(),main=h.refs.get('main');
  assert.equal(before.conflict,true);assert.equal(before.blobSha,before.mainBlobSha);
  h.changeMain('app.js','trusted current engineering');liveSettings(h);
  const loaded=await h.read(),response=await h.request(cycleInput(loaded)),after=await response.json();
  assert.equal(response.status,200,JSON.stringify(after));assert.equal(after.verified,true);assert.equal(after.conflict,false);
  assert.equal(after.status,'cloud_draft');assert.equal(after.request,null);assert.equal(after.published,false);
  assert.equal(after.blobSha,loaded.mainBlobSha);assert.equal(after.baseSha,loaded.mainBlobSha);
  assert.equal(after.manifestRecord.baseMain,loaded.main);assert.equal(h.refs.get('main'),loaded.main);
  const parents=h.commits.get(after.head).parents;assert.deepEqual(parents,[loaded.head,loaded.main]);
  assert.deepEqual([...h.trees.get(h.commits.get(h.oldRequest).tree.sha)],h.oldRequestTree);
  const actual=h.trees.get(h.commits.get(after.head).tree.sha),trusted=h.trees.get(h.commits.get(loaded.main).tree.sha);
  for(const [path,sha]of trusted) if(![contract.source,contract.manifest,contract.request].includes(path)) assert.equal(actual.get(path),sha);
  assert.equal(actual.has(contract.request),false);assert.ok(h.commits.has(main));
  const edited=await(await h.request(h.input(after,{values:{...after.settings.font,bodySize:'17px'}}))).json();
  assert.equal(edited.conflict,false);assert.equal(edited.settings.font.bodySize,'17px');
  const next=await h.request({action:'request-publication',expectedHead:edited.head,blobSha:edited.blobSha,
    baseSha:edited.baseSha,catalogSha:edited.catalogSha,settingsApproved:true});
  assert.equal(next.status,200);assert.equal((await next.json()).request.draftHead,edited.head);
});
test('new cycle requires literal confirmation and exact pinned draft/main/catalogue before any write',async()=>{
  for(const changes of [{confirmed:false},{confirmed:'true'},{expectedHead:'a'.repeat(40)},{blobSha:'a'.repeat(40)},
    {expectedMain:'a'.repeat(40)},{expectedMainBlob:'a'.repeat(40)},{expectedCatalog:'a'.repeat(40)},{repository:'other/repo'}]){
    const h=await publishedSettingsFixture(),loaded=await h.read();h.calls.length=0;
    const response=await h.request(cycleInput(loaded,changes));
    assert.ok([400,409].includes(response.status));noWrites(h);assert.equal(h.refs.get(contract.branch),loaded.head);
  }
});
test('new cycle cannot retire active/missing/forged receipt or rely on incomplete formal publication',async()=>{
  for(const change of [h=>h.changeMain('.site-settings-delivery.json',{version:1,request:{fake:true}}),
    h=>h.changeMain('.site-settings-delivery.json',{version:1,request:null,extra:true}),
    h=>h.workflowRuns[0].conclusion='failure',h=>h.workflowJobs.get(101)[0].steps[0].conclusion='skipped',
    h=>h.deploymentStatuses.get(201)[0].state='failure']){
    const h=await publishedSettingsFixture();change(h);
    if(h.refs.get('main')!==h.workflowRuns[0].head_sha) liveSettings(h);
    const loaded=await h.read();h.calls.length=0;
    assert.equal((await h.request(cycleInput(loaded))).status,409);noWrites(h);
  }
  const h=fixture(),saved=await(await h.request(h.input(await h.read()))).json();liveSettings(h);h.calls.length=0;
  const response=await h.request(cycleInput(saved));assert.equal(response.status,409);
  assert.equal((await response.json()).error,'settings_receipt_not_retired');noWrites(h);
});
test('new cycle respects cookie owner/origin, main/request races and ambiguous post-write outcomes',async()=>{
  for(const scenario of ['owner','origin','main','request','uncertain']){
    const h=await publishedSettingsFixture(),loaded=await h.read();h.calls.length=0;
    let options={};
    if(scenario==='owner')h.login='other';
    if(scenario==='origin')options={headers:{origin:'https://other.test'}};
    if(scenario==='main')h.before=call=>{if(call.path==='git/trees')h.changeMain('changed.js','new source');};
    if(scenario==='request')h.before=call=>{if(call.path==='git/commits')h.refs.set(contract.branch,loaded.main);};
    if(scenario==='uncertain')h.uncertain=true;
    const response=await h.request(cycleInput(loaded),options);assert.ok(response.status>=400);
    const data=await response.json();assert.notEqual(data.verified,true);assert.notEqual(data.published,true);
    assert.ok(!JSON.stringify(data).includes('fixture-only'));
    if(['owner','origin'].includes(scenario))noWrites(h);
    if(['main','request'].includes(scenario))assert.ok(!h.calls.some(call=>call.path.startsWith('git/refs/')));
  }
});
test('settings publication observation is authenticated read-only and cannot infer a deployment from main',async()=>{
  const h=fixture(); let response=await h.request(undefined,{query:'?publication=1'}),data=await response.json();
  assert.equal(response.status,200); assert.equal(data.publication.state,'ci_missing');
  assert.equal(data.publication.published,false); assert.equal(data.publication.deploymentVerified,false);
  assert.equal(data.publication.kind,'site-settings'); assert.equal(data.publication.sourceIndexable,undefined);
  assert.equal(data.published,false); noWrites(h);
  h.session=false; const count=h.calls.length;
  assert.equal((await h.request(undefined,{query:'?publication=1'})).status,401); assert.equal(h.calls.length,count);
  h.session=true;
  for(const query of ['?publication=0','?publication=1&branch=main','?publication=1&publication=1'])
    assert.equal((await h.request(undefined,{query})).status,400);
});
test('only exact all-green formal checks and latest trusted production verify a settings snapshot',async()=>{
  const h=fixture(); liveSettings(h);
  let data=await(await h.request(undefined,{query:'?publication=1'})).json();
  assert.equal(data.publication.state,'live'); assert.equal(data.publication.published,true);
  assert.equal(data.publication.settingsValidated,true); assert.equal(data.publication.loadedHead,null);
  const saved=await(await h.request(h.input(await h.read()))).json();
  data=await(await h.request(undefined,{query:'?publication=1'})).json();
  assert.equal(data.publication.state,'live'); assert.equal(data.publication.published,false);
  assert.equal(data.publication.matchesLoadedVersion,false); assert.equal(data.publication.loadedHead,saved.head);
  assert.equal(h.refs.get('main'),h.main);
});
test('missing, skipped, failed, duplicate or wrong-SHA jobs cannot claim settings publication',async()=>{
  for(const mutate of [h=>h.workflowJobs.set(101,[]),h=>h.workflowJobs.get(101)[0].conclusion='skipped',
    h=>h.workflowJobs.get(101)[0].head_sha='a'.repeat(40),h=>h.workflowJobs.get(101)[0].steps[0].conclusion='failure',
    h=>h.workflowJobs.get(101).push({...h.workflowJobs.get(101)[0]})]){
    const h=fixture(); liveSettings(h); mutate(h);
    const data=await(await h.request(undefined,{query:'?publication=1'})).json();
    assert.equal(data.publication.state,'ci_failed'); assert.equal(data.publication.published,false); noWrites(h);
  }
});
test('newer failed CI attempt or deployment rollback never borrows old green settings evidence',async()=>{
  const h=fixture(); liveSettings(h);
  h.workflowRuns.push({...h.workflowRuns[0],run_attempt:2,conclusion:'failure'});
  let data=await(await h.request(undefined,{query:'?publication=1'})).json();
  assert.equal(data.publication.state,'ci_failed'); assert.equal(data.publication.published,false);
  liveSettings(h); h.deployments.push({...h.deployments[0],id:203,sha:'a'.repeat(40)});
  data=await(await h.request(undefined,{query:'?publication=1'})).json();
  assert.equal(data.publication.state,'unverified'); assert.equal(data.publication.published,false); noWrites(h);
});
test('untrusted failed malformed and changing deployment statuses fail closed for settings',async()=>{
  for(const update of [{state:'failure'},{creator:{login:'maintainer'}},{environment_url:'https://other.example/'},{id:0}]){
    const h=fixture(); liveSettings(h); Object.assign(h.deploymentStatuses.get(201)[0],update);
    const data=await(await h.request(undefined,{query:'?publication=1'})).json();
    assert.equal(data.publication.published,false); assert.equal(data.publication.deploymentVerified,false); noWrites(h);
  }
  const h=fixture(); liveSettings(h); let statuses=0;
  h.before=call=>{if(call.path==='deployments/201/statuses'&&++statuses>1)
    h.deploymentStatuses.get(201).push({...h.deploymentStatuses.get(201)[0],id:204,state:'failure'});};
  const data=await(await h.request(undefined,{query:'?publication=1'})).json();
  assert.equal(data.publication.state,'changed'); assert.equal(data.publication.published,false);
});
test('settings branch changes during a main deployment observation invalidate the response',async()=>{
  const h=fixture(),saved=await(await h.request(h.input(await h.read()))).json(); liveSettings(h);
  h.after=call=>{if(call.path==='deployments/201/statuses') h.refs.set(contract.branch,h.main);};
  const data=await(await h.request(undefined,{query:'?publication=1'})).json();
  assert.equal(data.publication.loadedHead,saved.head); assert.equal(data.publication.state,'changed');
  assert.equal(data.publication.published,false); assert.equal(data.publication.ciVerified,false);
});
test('publication policy missing the literal settings intent gate or unreadable evidence remains unverified',async()=>{
  for(const flag of [false,1,null]){
    const h=fixture({...publicationPolicy,site_settings_author_intent:flag}); liveSettings(h);
    const data=await(await h.request(undefined,{query:'?publication=1'})).json();
    assert.equal(data.publication.state,'unverified'); assert.equal(data.publication.published,false);
    assert.ok(!h.calls.some(call=>call.path.startsWith('actions/'))); noWrites(h);
  }
  const h=fixture(); liveSettings(h); h.fail='actions/runs';
  const response=await h.request(undefined,{query:'?publication=1'}),text=await response.text();
  assert.equal(response.status,200); assert.equal(JSON.parse(text).publication.state,'unverified');
  assert.ok(!text.includes('fixture-only')); noWrites(h);
});
test('font/order drafts preserve legacy recommendations; saving picks explicitly opts into source ownership', async () => {
  const h = fixture(), initial = await h.read();
  assert.equal(initial.settings.legacyPicks, true);
  await h.request(h.input(initial)); let loaded = await h.read();
  assert.equal(loaded.settings.legacyPicks, true);
  await h.request(h.input(loaded, {kind: 'order', values: ['gamma', 'beta', 'alpha']})); loaded = await h.read();
  assert.equal(loaded.settings.legacyPicks, true);
  const response = await h.request(h.input(loaded, {kind: 'picks', values: ['alpha']}));
  assert.equal(response.status, 200); loaded = await response.json();
  assert.equal(loaded.settings.legacyPicks, false);
  assert.deepEqual(loaded.settings.picks, ['alpha']);
  await h.request(h.input(loaded)); loaded = await h.read();
  assert.equal(loaded.settings.legacyPicks, false);
  assert.equal(h.refs.get('main'), h.main, 'migration is a draft, never a live KV/main write');
});
test('a font draft preserves other settings and never claims publication; second edit is a single fast-forward', async () => {
  const h = fixture(), initial = await h.read();
  assert.equal(initial.head, null); assert.equal(initial.published, false); assert.equal(initial.deploymentVerified, false); noWrites(h);
  const firstResponse = await h.request(h.input(initial)), first = await firstResponse.json();
  assert.equal(firstResponse.status, 200); assert.equal(first.verified, true); assert.equal(first.published, false);
  assert.deepEqual(first.settings.picks, ['alpha']); assert.equal(first.settings.font.bodySize, '18px');
  const loaded = await h.read(); assert.equal(loaded.conflict, false); assert.equal(loaded.head, first.head);
  const secondResponse = await h.request(h.input(loaded, {kind: 'picks', values: ['beta', 'alpha']})), second = await secondResponse.json();
  assert.equal(secondResponse.status, 200); assert.equal(second.settings.font.bodySize, '18px');
  assert.deepEqual(second.settings.picks, ['beta', 'alpha']); assert.equal(h.commits.get(second.head).parents[0], first.head);
  assert.equal(h.refs.get('main'), h.main);
});
test('saving content atomically retires only the previous request and preserves its historic copy', async () => {
  const h = fixture(); let loaded = await h.read();
  await h.request(h.input(loaded)); loaded = await h.read();
  assert.equal((await h.request(intent(loaded))).status, 200); loaded = await h.read();
  const historic = h.trees.get(h.commits.get(loaded.head).tree.sha);
  const response = await h.request(h.input(loaded, {kind: 'order', values: ['gamma', 'alpha', 'beta']}));
  assert.equal(response.status, 200); const result = await response.json();
  assert.equal(h.trees.get(h.commits.get(result.head).tree.sha).has(contract.request), false);
  assert.equal(historic.has(contract.request), true);
});
function intent(loaded, extra = {}) {
  return {action: 'request-publication', expectedHead: loaded.head, blobSha: loaded.blobSha,
    baseSha: loaded.baseSha, catalogSha: loaded.catalogSha, settingsApproved: true, ...extra};
}
test('explicit author approval binds an immutable draft; cancellation leaves content and main intact', async () => {
  const h = fixture(); const base = await h.read(); await h.request(h.input(base)); const draft = await h.read();
  const response = await h.request(intent(draft)), requested = await response.json();
  assert.equal(response.status, 200); assert.equal(requested.status, 'requested'); assert.equal(requested.verified, true);
  assert.equal(requested.request.draftHead, draft.head); assert.equal(requested.request.requestHead, requested.head);
  assert.equal(requested.blobSha, draft.blobSha); assert.equal(requested.published, false); assert.equal(requested.deploymentVerified, false);
  assert.equal(h.commits.get(requested.head).parents[0], draft.head);
  const loaded = await h.read(); const cancel = intent(loaded, {action: 'cancel-request'}); delete cancel.settingsApproved;
  const cancelledResponse = await h.request(cancel), cancelled = await cancelledResponse.json();
  assert.equal(cancelledResponse.status, 200); assert.equal(cancelled.request, null); assert.equal(cancelled.blobSha, draft.blobSha);
  assert.equal(cancelled.status, 'cloud_draft'); assert.equal(h.refs.get('main'), h.main);
  assert.equal(h.trees.get(h.commits.get(requested.head).tree.sha).has(contract.request), true);
});
for (const extra of [{settingsApproved: false}, {settingsApproved: 'true'}, {action: 'publish-main'}, {css: 'arbitrary'}, {expectedHead: '0'.repeat(40)}]) {
  test('publication request requires literal approval and fixed operation: ' + JSON.stringify(extra), async () => {
    const h = fixture(); await h.request(h.input(await h.read())); const loaded = await h.read(), start = h.calls.length;
    const response = await h.request(intent(loaded, extra)); assert.equal(response.status, 400);
    assert.ok(h.calls.slice(start).every(call => call.method === 'GET'));
  });
}
test('stale publication approval cannot attach to another version; duplicate request cannot replace an intent', async () => {
  const h = fixture(); await h.request(h.input(await h.read())); const first = await h.read();
  await h.request(h.input(first, {kind: 'picks', values: ['beta']})); const next = await h.read();
  const start = h.calls.length; assert.equal((await h.request(intent(first))).status, 409);
  assert.ok(h.calls.slice(start).every(call => call.method === 'GET'));
  assert.equal((await h.request(intent(next))).status, 200); const requested = await h.read();
  const duplicateStart = h.calls.length; assert.equal((await h.request(intent(requested))).status, 409);
  assert.ok(h.calls.slice(duplicateStart).every(call => call.method === 'GET'));
});
test('unknown selector cannot influence reads or writes', async () => {
  const h = fixture(); assert.equal((await h.request(undefined, {query: '?ref=other'})).status, 400);
  assert.equal(h.calls.length, 0);
});
test('request carrying collateral source edits cannot masquerade as approval of a settings-only version', async () => {
  const h = fixture(); await h.request(h.input(await h.read())); const loaded = await h.read();
  assert.equal((await h.request(intent(loaded))).status, 200);
  const head = h.refs.get(contract.branch), tree = h.trees.get(h.commits.get(head).tree.sha);
  tree.set('api/admin/injected.js', h.store('arbitrary code'));
  const response = await h.request(); assert.equal(response.status, 409);
  assert.equal((await response.json()).error, 'invalid_settings_scope');
});
test('forged request binding cannot borrow a different draft SHA', async () => {
  const h = fixture(); await h.request(h.input(await h.read())); const loaded = await h.read();
  assert.equal((await h.request(intent(loaded))).status, 200);
  const head = h.refs.get(contract.branch), tree = h.trees.get(h.commits.get(head).tree.sha);
  const data = JSON.parse(h.blobs.get(tree.get(contract.request)).toString()); data.draftHead = h.main;
  tree.set(contract.request, h.store(JSON.stringify(data)));
  assert.equal((await h.request()).status, 409);
});
test('oversized and invalid UTF-8 upstream JSON are rejected without exposing details', async () => {
  for (const bytes of [Buffer.alloc(3_000_001, 32), Buffer.from([0xff])]) {
    const h = fixture(); h.raw = () => new Response(bytes);
    const response = await h.request(); assert.equal(response.status, 502); noWrites(h);
    assert.ok(!JSON.stringify(await response.json()).includes('fixture-only'));
  }
});
test('bad main after the ref write leaves an unverified outcome, never a production acknowledgement', async () => {
  const h = fixture(), loaded = await h.read();
  h.after = ({path}) => { if (path === 'git/refs') h.changeMain(contract.source, {...defaults(), picks: ['beta']}); };
  const response = await h.request(h.input(loaded)); assert.equal(response.status, 502);
  assert.equal((await response.json()).error, 'settings_save_not_verified'); assert.ok(h.refs.get(contract.branch));
});
test('a stalled upstream is aborted with the configured finite request deadline', async () => {
  const h = fixture(); h.stall = true; h.fastTimers = true;
  const response = await h.request(); assert.equal(response.status, 502); noWrites(h);
  assert.ok(h.timeouts.length > 0); assert.ok(h.timeouts.every(milliseconds => milliseconds > 0 && milliseconds <= 12_000));
  assert.equal((await response.json()).error, 'settings_repository_unavailable');
});
for (const action of ['read', 'save', 'request']) test('pre-existing collateral on the draft is rejected before ' + action, async () => {
  const h = fixture(); await h.request(h.input(await h.read())); const loaded = await h.read();
  const tree = h.trees.get(h.commits.get(loaded.head).tree.sha); tree.set('assets/injected.js', h.store('arbitrary code'));
  const start = h.calls.length;
  const response = await h.request(action === 'read' ? undefined : action === 'save' ? h.input(loaded) : intent(loaded));
  assert.equal(response.status, 409); assert.equal((await response.json()).error, 'invalid_settings_scope');
  assert.ok(h.calls.slice(start).every(call => call.method === 'GET'));
});
test('unrelated main advancement preserves the original draft base rather than inventing a mixed tree', async () => {
  const h = fixture(); await h.request(h.input(await h.read())); const first = await h.read();
  h.changeMain('assets/main-update.js', {value: 'new main source'}); const loaded = await h.read();
  assert.equal(loaded.conflict, false); const response = await h.request(h.input(loaded, {kind: 'picks', values: ['beta']}));
  assert.equal(response.status, 200); const next = await h.read();
  assert.equal(next.manifestRecord.baseMain, first.manifestRecord.baseMain);
  assert.equal(next.conflict, false); assert.equal(next.settings.font.bodySize, '18px');
  assert.equal((await h.request(intent(next))).status, 200);
  assert.equal(h.trees.get(h.commits.get(h.refs.get(contract.branch)).tree.sha).has('assets/main-update.js'), false);
});
for (const extra of [
  {repository: 'other/repo'}, {kind: 'css'}, {expectedHead: '0'.repeat(40)}, {baseSha: 'invalid'},
  {values: {...defaults().font, bodyFont: 'url(https://unsafe.test)'}},
  {kind: 'order', values: ['alpha']}, {kind: 'order', values: ['alpha', 'beta', 'private']},
  {kind: 'picks', values: ['alpha', 'alpha']}, {kind: 'picks', values: []}, {kind: 'picks', values: ['private']},
]) test('invalid or caller-selected setting input cannot write: ' + JSON.stringify(extra), async () => {
  const h = fixture(), loaded = await h.read();
  const response = await h.request(h.input(loaded, extra)); assert.equal(response.status, 400); noWrites(h);
});
test('stale tab cannot overwrite a newer draft', async () => {
  const h = fixture(), loaded = await h.read(); await h.request(h.input(loaded));
  const start = h.calls.length, response = await h.request(h.input(loaded)); assert.equal(response.status, 409);
  assert.ok(h.calls.slice(start).every(call => call.method === 'GET'));
});
for (const path of [contract.source, contract.catalog]) test('changed main ' + path + ' requires explicit integration without discarding old draft', async () => {
  const h = fixture(), loaded = await h.read(); await h.request(h.input(loaded));
  const oldHead = h.refs.get(contract.branch);
  h.changeMain(path, path === contract.source ? {...defaults(), picks: ['beta']} : {version: 1, articles: [...articles, {slug: 'delta', title: '新文章', title_en: 'New article'}]});
  const current = await h.read(); assert.equal(current.conflict, true); assert.equal(current.head, oldHead);
  const start = h.calls.length; assert.equal((await h.request(h.input(current))).status, 409);
  assert.ok(h.calls.slice(start).every(call => call.method === 'GET')); assert.equal(h.refs.get(contract.branch), oldHead);
});
test('non-fast-forward race is rejected without force or touching main', async () => {
  const h = fixture(), loaded = await h.read(); h.race = true;
  const response = await h.request(h.input(loaded)); assert.equal(response.status, 409); assert.equal(h.refs.get(contract.branch), undefined);
  assert.equal(h.refs.get('main'), h.main);
});
test('main moves during a read: no mixed snapshot', async () => {
  const h = fixture(); let moved = false;
  h.after = ({path}) => { if (!moved && path.startsWith('contents/')) { moved = true; h.changeMain(contract.source, {...defaults(), picks: ['beta']}); } };
  assert.equal((await h.request()).status, 409); noWrites(h);
});
test('main moves before CAS: no draft ref change', async () => {
  const h = fixture(), loaded = await h.read();
  h.after = ({path}) => { if (path === 'git/commits') h.changeMain(contract.source, {...defaults(), picks: ['beta']}); };
  assert.equal((await h.request(h.input(loaded))).status, 409); assert.equal(h.refs.get(contract.branch), undefined);
});
test('unknown write result is not acknowledged and can be resolved by read, not automatic retry', async () => {
  const h = fixture(), loaded = await h.read(); h.uncertain = true;
  const response = await h.request(h.input(loaded)), result = await response.json();
  assert.equal(response.status, 502); assert.equal(result.verified, undefined);
  assert.ok(!JSON.stringify(result).includes('fixture-only')); assert.ok(h.refs.get(contract.branch));
  const current = await h.read(); assert.equal(current.settings.font.bodySize, '18px');
  assert.equal(h.calls.filter(call => call.path === 'git/refs').length, 1);
});
for (const [name, tamper] of [
  ['symlink source', (call, result) => { if (call.path.startsWith('git/trees/')) result.tree.find(item => item.path === contract.source).mode = '120000'; return result; }],
  ['executable source', (call, result) => { if (call.path.startsWith('git/trees/')) result.tree.find(item => item.path === contract.source).mode = '100755'; return result; }],
  ['truncated tree', (call, result) => { if (call.path.startsWith('git/trees/')) result.truncated = true; return result; }],
  ['duplicate tree path', (call, result) => { if (call.path.startsWith('git/trees/')) result.tree.push(result.tree[0]); return result; }],
  ['content digest mismatch', (call, result) => { if (call.path.startsWith('contents/')) { result.content = Buffer.from('{}').toString('base64'); result.size = 2; } return result; }],
  ['wrong ref type', (call, result) => { if (call.path.startsWith('git/ref/heads/')) result.object.type = 'tag'; return result; }],
  ['wrong repository ref', (call, result) => { if (call.path.startsWith('git/ref/heads/')) result.ref = 'refs/heads/other'; return result; }],
]) test('untrusted upstream metadata rejected: ' + name, async () => {
  const h = fixture(); h.tamper = tamper; const response = await h.request(); assert.equal(response.status, 502); noWrites(h);
});
for (const raw of ['{"version":1,"version":1}', '{"font":{"bodySize":"","body\\u0053ize":"18px"}}']) test('ambiguous duplicate JSON keys rejected: ' + raw, async () => {
  const h = fixture(); assert.throws(() => h.api.parseJson(raw), /invalid_settings_json/);
  assert.equal((await h.request(raw)).status, 400); noWrites(h);
});
test('key-like text in arrays and strings is not mistaken for a duplicate key', () => {
  const h = fixture(); const value = {name: '"name": [ }', nested: [{name: 'a'}, {name: 'b'}], list: ['name', 'name']};
  assert.equal(JSON.stringify(h.api.parseJson(JSON.stringify(value))), JSON.stringify(value));
});
for (const headers of [{origin: 'https://external.test'}, {origin: ''}, {'sec-fetch-site': 'cross-site'}]) test('cross-origin write is denied before Git access', async () => {
  const h = fixture(); assert.equal((await h.request({}, {headers})).status, 403); assert.equal(h.calls.length, 0);
});
for (const login of [null, 'other-owner']) test('cookie session allowlist is mandatory', async () => {
  const h = fixture(); h.session = login !== null; h.login = login;
  assert.equal((await h.request()).status, 401); assert.equal(h.calls.length, 0);
});
test('bounded JSON streaming rejects an oversized request and malformed UTF-8 before any Git access', async () => {
  const h = fixture();
  assert.equal((await h.request(' '.repeat(32_001))).status, 413);
  assert.equal((await h.request(new Uint8Array([0xff]), {body: new Uint8Array([0xff])})).status, 400); assert.equal(h.calls.length, 0);
});
test('failed post-write verification never reports a verified save', async () => {
  const h = fixture(), loaded = await h.read(); let written = false;
  h.after = ({path}) => { if (path === 'git/refs') written = true; };
  h.tamper = (call, value) => { if (written && call.path.startsWith('contents/')) value.sha = hash('wrong blob'); return value; };
  const response = await h.request(h.input(loaded)); assert.equal(response.status, 502);
  assert.equal((await response.json()).error, 'settings_save_not_verified'); assert.equal(h.refs.get('main'), h.main);
});
