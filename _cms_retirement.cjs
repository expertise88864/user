/* Separately verified immutable retirement. No Git writes or release permit. */
'use strict';
const assert = require('node:assert/strict');
const { blob, tree, exactKeys, sha, time, validateReceiptEntry } = require('./_cms_delivery.cjs');
const FILE='.cms-delivery.json', PREFIX='.cms-retirements/', REPO='expertise88864/user';
const archive=/^\.cms-retirements\/([a-f0-9]{40})\.json$/;
const positive=value=>Number.isSafeInteger(value)&&value>0;
async function pages(api,path,key){
 const result=[];
 for(let page=1;page<=3;page++){
  const data=await api(path+(path.includes('?')?'&':'?')+'per_page=100&page='+page),rows=key?data?.[key]:data;
  assert.ok(Array.isArray(rows)&&rows.length<=100&&rows.every(r=>r&&typeof r==='object'&&!Array.isArray(r)), 'Incomplete retirement evidence');
  result.push(...rows);if(rows.length<100)return result;
 }
 throw Error('Retirement evidence exceeds its bound');
}
async function mainSha(api){const r=await api('/git/ref/heads/main');assert.ok(r?.ref==='refs/heads/main'&&r.object?.type==='commit'&&sha(r.object.sha),'Retirement main unavailable');return r.object.sha;}
async function mainRuns(api,head){return(await pages(api,'/actions/runs?head_sha='+head,'workflow_runs')).filter(r=>r.head_sha===head&&r.event==='push'&&r.head_branch==='main'&&r.head_repository?.full_name===REPO);}
async function baseline(api,candidate,current){
 if(current!==candidate){const c=await api('/compare/'+current+'...'+candidate);assert.ok(['ahead','identical'].includes(c?.status)&&c.merge_base_commit?.sha===current,'Retirement is not based on current main');return current;}
 let parent=candidate;
 for(let i=0;i<20;i++){
  const c=await api('/git/commits/'+parent);assert.ok(c?.sha===parent&&Array.isArray(c.parents)&&c.parents.length===1&&sha(c.parents[0].sha),'Retirement previous main is ambiguous');parent=c.parents[0].sha;
  if((await mainRuns(api,parent)).some(r=>r.path==='.github/workflows/delivery.yml'))return parent;
 }
 throw Error('Retirement previous main exceeds its bound');
}
function decode(raw){const value=JSON.parse(raw.toString('utf8'));assert.ok(Buffer.from(JSON.stringify(value,null,2)+'\n').equals(raw),'Retirement JSON is not canonical');return value;}
function archivePaths(entries){
 const paths=new Map();for(const [path,e]of entries){
  if(path===PREFIX.slice(0,-1))assert.ok(e.type==='tree'&&e.mode==='040000','Malformed retirement archive root');
  if(!path.startsWith(PREFIX)||e.type==='tree')continue;
  const m=archive.exec(path);assert.ok(m&&sha(m[1])&&e.type==='blob'&&e.mode==='100644'&&sha(e.sha),'Malformed retirement archive');paths.set(path,e.sha);
 }return paths;
}
async function selectedRuns(api,head,policy){
 const rows=await mainRuns(api,head),selected=[];
 for(const entry of policy.workflows){
  const matches=rows.filter(r=>r.path===entry.path);assert.ok(matches.length&&matches.every(r=>positive(r.id)&&positive(r.run_attempt)),'Retirement formal CI identity missing');
  const run=matches.sort((a,b)=>b.id-a.id||b.run_attempt-a.run_attempt)[0];assert.ok(run.status==='completed'&&run.conclusion==='success','Retirement formal CI failed');selected.push({workflow:entry.path,runId:run.id,attempt:run.run_attempt});
 }
 return selected;
}
async function production(api){
 const rows=(await pages(api,'/deployments')).filter(d=>String(d.environment).toLowerCase()==='production'&&typeof d.production_environment==='boolean'&&['vercel[bot]','vercel'].includes(d.creator?.login));
 assert.ok(rows.length&&rows.every(d=>positive(d.id)),'Retirement trusted deployment missing');const d=rows.sort((a,b)=>b.id-a.id)[0];assert.ok(sha(d.sha),'Retirement deployment SHA invalid');return d;
}
function validStatus(status){
 if(status.state!=='success'||!['vercel[bot]','vercel'].includes(status.creator?.login))return false;
 try{const u=new URL(status.environment_url);return u.protocol==='https:'&&u.hostname.startsWith('chendermatologist-')&&u.hostname.endsWith('.vercel.app')&&!u.username&&!u.password&&!u.port&&['/',''].includes(u.pathname)&&!u.search&&!u.hash;}catch(_){return false;}
}
function historicalStatusValid(latest,success,currentSha,published){
 try{assert.deepEqual(latest,success);return true;}catch(_){}
 return currentSha!==published&&latest.state==='inactive'&&latest.environment_url===success.environment_url&&validStatus({...latest,state:'success'});
}
async function publicationEvidence(api,published,candidate,claimed,trees){
 const p=await blob(api,'_delivery_policy.json',published,32000,trees),policy=JSON.parse(p.raw.toString('utf8'));
 assert.ok(policy?.repository===REPO&&policy.require_pr===true&&policy.allow_dispatch===false&&policy.cms_author_intent===true&&Array.isArray(policy.workflows)&&policy.workflows.length>=6&&policy.workflows.every(w=>w&&typeof w.path==='string'&&Array.isArray(w.jobs)&&w.jobs.length&&w.jobs.every(n=>typeof n==='string'))&&new Set(policy.workflows.map(w=>w.path)).size===policy.workflows.length,'Retirement formal policy missing');
 const selected=await selectedRuns(api,published,policy);
 for(let i=0;i<selected.length;i++){
  const record=selected[i],entry=policy.workflows[i],jobs=await pages(api,'/actions/runs/'+record.runId+'/attempts/'+record.attempt+'/jobs','jobs');
  assert.ok(jobs.length&&entry.jobs.every(n=>jobs.filter(j=>j.name===n).length===1)&&jobs.every(j=>j.head_sha===published),'Retirement formal job identity/SHA invalid');
  for(const job of jobs){
   assert.equal(job.status,'completed','Retirement formal job incomplete');
   if(job.conclusion==='skipped'&&(entry.main_skips||[]).includes(job.name))continue;
   const contract=entry.steps?.[job.name];assert.ok(job.conclusion==='success'&&contract?.required?.length&&Array.isArray(job.steps)&&job.steps.length,'Retirement formal job failed');
   for(const name of [...contract.required,...(contract.main_required||[])]){const steps=job.steps.filter(s=>s.name===name);assert.ok(steps.length===1&&steps[0].status==='completed'&&steps[0].conclusion==='success','Retirement formal step failed');}
   assert.ok(!job.steps.some(s=>['failure','cancelled','timed_out','action_required'].includes(s.conclusion)),'Retirement failed step hidden');
  }
 }
 assert.deepEqual(await selectedRuns(api,published,policy),selected,'Retirement formal CI changed');
 const d=await production(api);assert.ok([published,candidate].includes(d.sha),'Retirement production rolled back');
 const id=claimed.deploymentId;assert.ok(positive(id),'Retirement deployment identity invalid');
 const original=await api('/deployments/'+id);assert.ok(original?.id===id&&original.sha===published&&String(original.environment).toLowerCase()==='production'&&typeof original.production_environment==='boolean'&&['vercel[bot]','vercel'].includes(original.creator?.login),'Retirement deployment is not the published revision');
 const statuses=await pages(api,'/deployments/'+id+'/statuses');assert.ok(statuses.length&&statuses.every(s=>positive(s.id)),'Retirement status evidence incomplete');
 const status=statuses.find(s=>s.id===claimed.statusId);assert.ok(status&&validStatus(status),'Retirement trusted success missing');
 assert.ok((d.sha!==published||d.id===id)&&historicalStatusValid(statuses.reduce((a,b)=>a.id>b.id?a:b),status,d.sha,published),'Retirement publication changed since preparation');
 assert.deepEqual(claimed,{workflows:selected,deploymentId:id,statusId:status.id},'Retirement exact publication evidence mismatch');
 const fresh=await production(api);assert.ok(fresh.id===d.id&&fresh.sha===d.sha,'Retirement deployment changed during validation');
 const freshStatuses=await pages(api,'/deployments/'+id+'/statuses');
 assert.ok(freshStatuses.length&&freshStatuses.every(s=>positive(s.id))&&freshStatuses.some(s=>{try{assert.deepEqual(s,status);return true;}catch(_){return false;}}),'Retirement deployment status changed during validation');
 assert.ok(historicalStatusValid(freshStatuses.reduce((a,b)=>a.id>b.id?a:b),status,fresh.sha,published),'Retirement deployment status changed during validation');
}
async function verifyTransition(candidate,api,currentItems,now,trees){
 const current=await mainSha(api),base=await baseline(api,candidate,current),beforeTree=await tree(api,base,trees),afterTree=await tree(api,candidate,trees);
 const before=beforeTree.has(FILE)?await blob(api,FILE,base,128000,trees):null;
 const previous=before?decode(before.raw):{version:1,requests:[]};assert.ok(exactKeys(previous,['version','requests'])&&previous.version===1&&Array.isArray(previous.requests)&&previous.requests.length<=20,'Invalid previous CMS receipt');
 const oldPaths=archivePaths(beforeTree),newPaths=archivePaths(afterTree);
 for(const [path,id]of oldPaths)assert.equal(newPaths.get(path),id,'Immutable retirement history modified or removed');
 const added=[...newPaths.keys()].filter(p=>!oldPaths.has(p)),old=new Map(),fresh=new Map(currentItems.map(r=>[r.file,r]));
 for(const entry of previous.requests){validateReceiptEntry(entry,now);assert.ok(!old.has(entry.file),'Duplicate previous CMS request');old.set(entry.file,entry);}
 for(const [file,value]of fresh)if(old.has(file))assert.deepEqual(value,old.get(file),'Existing published receipt requires separate retirement before replacement');
 const removed=[...old.keys()].filter(p=>!fresh.has(p)).sort();
 if(added.length||removed.length){
  const path=PREFIX+base+'.json';assert.ok(removed.length&&added.length===1&&added[0]===path,'Receipt removal requires exact retirement');
  for(const [file,value]of fresh)assert.deepEqual(value,old.get(file),'Retirement changed another active request');
  const flatten=t=>new Map([...t].filter(([,e])=>e.type!=='tree').map(([p,e])=>[p,JSON.stringify([e.mode,e.type,e.sha])]));
  const a=flatten(beforeTree),b=flatten(afterTree),changed=[...new Set([...a.keys(),...b.keys()])].filter(p=>a.get(p)!==b.get(p)).sort();
  assert.deepEqual(changed,[FILE,path].sort(),'Retirement changed patient content or other source');
  const saved=await blob(api,path,candidate,256000,trees),record=decode(saved.raw);
  assert.ok(exactKeys(record,['version','repository','publishedSha','receiptBlobSha','requests','evidence','preparedAt'])&&record.version===1&&record.repository===REPO&&record.publishedSha===base&&record.receiptBlobSha===before.sha,'Retirement does not bind published receipt');
  assert.deepEqual(record.requests,removed.map(p=>old.get(p)),'Retirement lost exact published requests');assert.ok(time(record.preparedAt)<=now,'Retirement preparation is in future');
  assert.ok(exactKeys(record.evidence,['workflows','deploymentId','statusId']),'Retirement publication evidence incomplete');
  await publicationEvidence(api,base,candidate,record.evidence,trees);
 }
 assert.equal(await mainSha(api),current,'Retirement main changed during validation');
 return {retiredRequests:removed.length,baseline:base};
}
module.exports={verifyTransition};
