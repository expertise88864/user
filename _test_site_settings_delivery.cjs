// Shared Python-produced approval fixture: cross-language immutable proof,
// no real provider calls, cookies or writes. Node rechecks after successful CI.
const test=require('node:test'),assert=require('node:assert/strict');
const {spawnSync}=require('node:child_process');
const {verify,receipt}=require('./_site_settings_delivery.cjs');
const run=spawnSync('python',['_test_site_settings_delivery.py','--fixture'],{encoding:'utf8'});
assert.equal(run.status,0,run.stderr);const template=JSON.parse(run.stdout);
function fixture(input=template){
 const data=structuredClone(input),calls=[];
 const h={data,calls,tamper:null};
 h.api=async path=>{
  calls.push(path);let result;
  if(path.startsWith('/git/ref/heads/')){const branch=path.slice('/git/ref/heads/'.length);result={ref:'refs/heads/'+branch,object:{type:'commit',sha:data.refs[branch]}};}
  else if(path.startsWith('/git/commits/'))result=data.commits[path.split('/').at(-1)];
  else if(path.startsWith('/git/trees/'))result=data.trees[path.split('/').at(-1).split('?')[0]];
  else if(path.startsWith('/contents/')){
   const [file,query]=path.slice('/contents/'.length).split('?'),head=new URLSearchParams(query).get('ref');
   const row=data.trees[data.commits[head].tree.sha].tree.find(row=>row.path===file);assert.ok(row,'Missing fixture blob');
   const raw=Buffer.from(data.blobs[row.sha],'base64');result={path:file,sha:row.sha,type:'file',encoding:'base64',size:raw.length,content:raw.toString('base64')};
  }else if(path.startsWith('/compare/')){
   const [base,head]=path.slice('/compare/'.length).split('...'),seen=new Set(),pending=[head];
   while(pending.length){const value=pending.pop();if(seen.has(value))continue;seen.add(value);pending.push(...data.commits[value].parents.map(p=>p.sha));}
   result={status:base===head?'identical':seen.has(base)?'ahead':'diverged',merge_base_commit:{sha:seen.has(base)?base:head}};
  }else if(path.startsWith('/actions/runs?'))result={workflow_runs:data.runs[new URLSearchParams(path.split('?')[1]).get('head_sha')]||[]};
  else throw Error('Unexpected fixture read '+path);
  result=structuredClone(result);return h.tamper?h.tamper(path,result):result;
 };return h;
}
test('Python-prepared source/receipt passes complete Node production recheck; never claims publication',async()=>{
 const h=fixture(),result=await verify(h.data.candidate,h.api);
 assert.equal(result.authorIntentVerified,true);assert.equal(result.candidatePayloadVerified,true);assert.equal(result.published,false);
 assert.equal(h.calls.filter(path=>path==='/git/ref/heads/cms-settings/site').length,2);
});
test('valid baseline JSON formatting accepted by author API and Python also passes production recheck',async()=>{
 const alternate=spawnSync('python',['_test_site_settings_delivery.py','--fixture-noncanonical'],{encoding:'utf8'});
 assert.equal(alternate.status,0,alternate.stderr);const h=fixture(JSON.parse(alternate.stdout));
 assert.equal((await verify(h.data.candidate,h.api)).authorIntentVerified,true);
});
test('request cancellation after CI prevents production',async()=>{const h=fixture();h.data.refs['cms-settings/site']=h.data.proof.draftHead;await assert.rejects(verify(h.data.candidate,h.api),/cancelled/);});
test('actual formal main uses the previous main receipt baseline',async()=>{const h=fixture();h.data.refs.main=h.data.candidate;assert.equal((await verify(h.data.candidate,h.api)).authorIntentVerified,true);});
for(const change of ['symlink','truncated','duplicate','size','blob-sha','source','approval','parent','collateral','main-race','request-race'])test('production settings rejects '+change,async()=>{
 const h=fixture();h.tamper=(path,value)=>{
  if(change==='symlink'&&path.startsWith('/git/trees/')){const row=value.tree.find(r=>r.path==='_site_settings.json');if(row)row.mode='120000';}
  if(change==='truncated'&&path.startsWith('/git/trees/'))value.truncated=true;
  if(change==='duplicate'&&path.startsWith('/git/trees/'))value.tree.push(value.tree[0]);
  if(change==='size'&&path.startsWith('/contents/'))value.size=true;
  if(change==='blob-sha'&&path.startsWith('/contents/'))value.sha='a'.repeat(40);
  if(change==='source'&&path.startsWith('/contents/_site_settings.json?ref='+h.data.candidate))value.content=Buffer.from('arbitrary').toString('base64');
  if(change==='approval'&&path.startsWith('/contents/.site-settings-delivery.json')){
   const input=JSON.parse(Buffer.from(value.content,'base64'));input.request.settingsApproved=false;value.content=Buffer.from(JSON.stringify(input,null,2)+'\n').toString('base64');
  }
  if(change==='parent'&&path==='/git/commits/'+h.data.proof.requestHead)value.parents=[];
  if(change==='collateral'&&path.startsWith('/git/trees/')&&value.tree.some(r=>r.path==='.cms-settings-requests/site.json'))value.tree.push({path:'evil.py',mode:'100644',type:'blob',sha:'a'.repeat(40)});
  if(change==='main-race'&&path.startsWith('/contents/.cms-settings-requests/site.json'))h.data.refs.main=h.data.proof.draftHead;
  if(change==='request-race'&&path.startsWith('/contents/.cms-settings-requests/site.json'))h.data.refs['cms-settings/site']=h.data.proof.draftHead;
  return value;
 };await assert.rejects(verify(h.data.candidate,h.api));
});
for(const field of ['settingsApproved','requestHead','sourceSha256','source'])test('Node proof schema rejects forged '+field,()=>{
 const proof=structuredClone(template.proof);proof[field]=field==='settingsApproved'?1:field==='requestHead'?'0'.repeat(40):field==='sourceSha256'?'A'.repeat(64):'../outside';
 assert.throws(()=>receipt(Buffer.from(JSON.stringify({version:1,request:proof},null,2)+'\n')));
});
test('duplicate proof properties never pass last-key-wins parsing',()=>assert.throws(()=>receipt(Buffer.from('{"version":1,"version":1,"request":null}\n'))));
