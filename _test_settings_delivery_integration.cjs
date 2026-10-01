// Real admin API save/request code -> Python extractor -> Node production gate.
// The existing in-memory API fixture intercepts all transport before egress.
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const {verify}=require('./_site_settings_delivery.cjs');
const source=fs.readFileSync('_test_site_settings.cjs','utf8').split('function noWrites(h)')[0];
assert.ok(source.includes('function fixture(')&&source.endsWith('\n'));
const context={require,Buffer,URL,Request,Response,TextEncoder,TextDecoder,Uint8Array,AbortController,setTimeout,clearTimeout,atob};
vm.runInNewContext(source+'\nthis.makeFixture=fixture;',context);
const hash=value=>crypto.createHash('sha1').update(value).digest('hex');
function graph(h){
 return {commits:Object.fromEntries([...h.commits].map(([sha,c])=>[sha,{sha,tree:c.tree,parents:c.parents.map(sha=>({sha}))}])),
  trees:Object.fromEntries([...h.trees].map(([sha,tree])=>[sha,{sha,truncated:false,tree:[...tree].map(([path,sha])=>({path,sha,mode:'100644',type:'blob'}))}])),
  blobs:Object.fromEntries([...h.blobs].map(([sha,raw])=>[sha,raw.toString('base64')])),refs:Object.fromEntries(h.refs)};
}
const prepare=`import base64,json,sys
from _test_site_settings_delivery import Fixture
from _site_settings_delivery import plan
data=json.load(sys.stdin);h=object.__new__(Fixture)
h.calls=[];h.tamper=None;h.runs={};h.refs=data['refs'];h.commits=data['commits'];h.trees=data['trees']
h.blobs={sha:base64.b64decode(raw) for sha,raw in data['blobs'].items()}
files,proof=plan(h,h.refs['main'],h.refs['cms-settings/site'])
print(json.dumps({'files':{path:base64.b64encode(raw).decode() for path,raw in files.items()},'proof':proof}))
`;
for (const cycle of [false,true,'catalog']) test(cycle === 'catalog' ? 'explicit catalogue reconciliation prepares strict approved current source through Python/Node gates' : cycle ? 'new admin editing cycle retains current main ancestry and prepares fresh approved source through Python/Node gates' :
 'actual admin-created manifest and intent prepare exact source-only candidate and pass production gate',async()=>{
 const h=context.makeFixture(),original=h.refs.get('main');
 const installed=new Map(h.trees.get(h.commits.get(original).tree.sha));
 installed.set('.site-settings-delivery.json',h.store(JSON.stringify({version:1,request:null},null,2)+'\n'));
 const installedTree=hash(JSON.stringify([...installed]));let main=hash('trusted-installed-proof:'+installedTree);
 h.trees.set(installedTree,installed);h.commits.set(main,{tree:{sha:installedTree},parents:[original]});h.refs.set('main',main);
 let loaded=await h.read();
 const saved=await h.request(h.input(loaded));assert.equal(saved.status,200);loaded=await h.read();
 const requested=await h.request({action:'request-publication',expectedHead:loaded.head,blobSha:loaded.blobSha,
  baseSha:loaded.baseSha,catalogSha:loaded.catalogSha,settingsApproved:true});assert.equal(requested.status,200);
 if(cycle === 'catalog') {
  const oldHead=h.refs.get('cms-settings/site');
  h.changeMain('_site_settings.json',{...loaded.sourceSettings,legacyPicks:false,order:['gamma','alpha','beta']});
  h.changeMain('assets/settings-catalog.json',{version:1,articles:['beta','gamma','delta'].map(slug=>({slug,title:'Article '+slug,title_en:'Article '+slug}))});
  main=h.refs.get('main');loaded=await h.read();assert.equal(loaded.sourceRequiresReview,true);assert.equal(loaded.conflict,true);
  const selected={...loaded.settings,legacyPicks:false,order:['gamma','beta','delta'],picks:['beta']};
  const response=await h.request({action:'reconcile-catalog',expectedHead:oldHead,blobSha:loaded.blobSha,expectedMain:main,
   expectedMainBlob:loaded.mainBlobSha,expectedCatalog:loaded.mainCatalogSha,settings:selected,confirmed:true});
  assert.equal(response.status,200,await response.clone().text());loaded=await response.json();
  assert.equal(loaded.conflict,false);assert.equal(loaded.request,null);assert.equal(loaded.sourceRequiresReview,true);
  assert.deepEqual(Array.from(h.commits.get(loaded.head).parents),[oldHead,main]);
  const request=await h.request({action:'request-publication',expectedHead:loaded.head,blobSha:loaded.blobSha,
   baseSha:loaded.baseSha,catalogSha:loaded.catalogSha,settingsApproved:true});assert.equal(request.status,200);
 } else if(cycle){
  const oldHead=h.refs.get('cms-settings/site'),oldCommit=h.commits.get(oldHead),beforeMain=main;
  const publishedFiles=new Map(h.trees.get(h.commits.get(main).tree.sha));
  publishedFiles.set('_site_settings.json',h.trees.get(oldCommit.tree.sha).get('_site_settings.json'));
  publishedFiles.set('app.js',h.store('/* current trusted engineering */'));
  const publishedTree=hash(JSON.stringify([...publishedFiles]));main=hash('verified-retired-source:'+publishedTree);
  h.trees.set(publishedTree,publishedFiles);h.commits.set(main,{tree:{sha:publishedTree},parents:[beforeMain]});h.refs.set('main',main);
  const policy=JSON.parse(fs.readFileSync('_delivery_policy.json','utf8'));
  h.workflowRuns=policy.workflows.map((entry,index)=>({id:101+index,run_attempt:1,path:entry.path,head_sha:main,
   head_branch:'main',event:'push',head_repository:{full_name:policy.repository},status:'completed',conclusion:'success'}));
  h.workflowJobs=new Map(h.workflowRuns.map((run,index)=>[run.id,policy.workflows[index].jobs.map(name=>({name,head_sha:main,
   status:'completed',conclusion:policy.workflows[index].main_skips?.includes(name)?'skipped':'success',
   steps:[...policy.workflows[index].steps[name].required,...(policy.workflows[index].steps[name].main_required||[])].map(name=>({name,status:'completed',conclusion:'success'}))}))]));
  h.deployments=[{id:201,sha:main,environment:'Production',production_environment:false,creator:{login:'vercel[bot]'}}];
  h.deploymentStatuses=new Map([[201,[{id:202,state:'success',creator:{login:'vercel[bot]'},environment_url:'https://chendermatologist-fixture.vercel.app'}]]]);
  loaded=await h.read();assert.equal(loaded.conflict,true);
  const created=await h.request({action:'new-version',expectedHead:loaded.head,blobSha:loaded.blobSha,expectedMain:main,
   expectedMainBlob:loaded.mainBlobSha,expectedCatalog:loaded.mainCatalogSha,confirmed:true});
  assert.equal(created.status,200,await created.clone().text());loaded=await created.json();
  assert.deepEqual(Array.from(h.commits.get(loaded.head).parents),[oldHead,main]);assert.equal(h.commits.get(oldHead),oldCommit);
  assert.equal(h.trees.get(h.commits.get(loaded.head).tree.sha).get('app.js'),publishedFiles.get('app.js'));
  const edited=await h.request(h.input(loaded,{values:{...loaded.settings.font,bodySize:'17px'}}));assert.equal(edited.status,200);loaded=await h.read();
  const nextRequest=await h.request({action:'request-publication',expectedHead:loaded.head,blobSha:loaded.blobSha,
   baseSha:loaded.baseSha,catalogSha:loaded.catalogSha,settingsApproved:true});assert.equal(nextRequest.status,200);
 }
 const requestHead=h.refs.get('cms-settings/site'),refs=Object.fromEntries(h.refs);
 const run=spawnSync('python',['-c',prepare],{input:JSON.stringify(graph(h)),encoding:'utf8'});
 assert.equal(run.status,0,run.stderr);const result=JSON.parse(run.stdout);
 assert.deepEqual(Object.keys(result.files).sort(),['.site-settings-delivery.json','_site_settings.json']);
 const files=new Map(h.trees.get(h.commits.get(main).tree.sha));
 for(const[path,raw]of Object.entries(result.files))files.set(path,h.store(Buffer.from(raw,'base64')));
 const tree=hash(JSON.stringify([...files])),candidate=hash('source-only-candidate:'+tree);
 h.trees.set(tree,files);h.commits.set(candidate,{tree:{sha:tree},parents:[main]});
 assert.ok(h.blobs.get(files.get('_site_settings.json')).equals(h.blobs.get(h.trees.get(h.commits.get(requestHead).tree.sha).get('_site_settings.json'))));
 const data=graph(h);
 const api=async path=>{
  if(path.startsWith('/git/ref/heads/')){const branch=path.slice(15);return{ref:'refs/heads/'+branch,object:{type:'commit',sha:data.refs[branch]}};}
  if(path.startsWith('/git/commits/'))return data.commits[path.split('/').at(-1)];
  if(path.startsWith('/git/trees/'))return data.trees[path.split('/').at(-1).split('?')[0]];
  if(path.startsWith('/contents/')){
   const[file,query]=path.slice(10).split('?'),head=new URLSearchParams(query).get('ref');
   const entry=data.trees[data.commits[head].tree.sha].tree.find(row=>row.path===file);assert.ok(entry);
   const raw=Buffer.from(data.blobs[entry.sha],'base64');return{path:file,type:'file',sha:entry.sha,encoding:'base64',size:raw.length,content:raw.toString('base64')};
  }
  if(path.startsWith('/compare/')){
   const[base,head]=path.slice(9).split('...'),seen=new Set(),pending=[head];
   while(pending.length){const sha=pending.pop();if(seen.has(sha))continue;seen.add(sha);pending.push(...data.commits[sha].parents.map(p=>p.sha));}
   return{status:base===head?'identical':seen.has(base)?'ahead':'diverged',merge_base_commit:{sha:seen.has(base)?base:head}};
  }
  assert.fail('Unexpected immutable delivery read '+path);
 };
 const checked=await verify(candidate,api);assert.equal(checked.authorIntentVerified,true);assert.equal(checked.published,false);
 assert.deepEqual(Object.fromEntries(h.refs),refs);assert.equal(h.refs.get('main'),main);
});
