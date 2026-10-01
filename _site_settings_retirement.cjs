'use strict';
const assert=require('node:assert/strict');
const {blob,tree,sha,exactKeys,time}=require('./_cms_delivery.cjs');
const {baseline,mainSha,publicationEvidence}=require('./_cms_retirement.cjs');
const FILE='.site-settings-delivery.json',PREFIX='.site-settings-retirements/',REPO='expertise88864/user';
const pattern=/^\.site-settings-retirements\/([a-f0-9]{40})\.json$/;
function archives(entries){
 const result=new Map();for(const[path,e]of entries){
  if(path===PREFIX.slice(0,-1))assert.ok(e.type==='tree'&&e.mode==='040000','Malformed settings retirement root');
  else if(path.startsWith(PREFIX)){
   const m=pattern.exec(path);assert.ok(m&&sha(m[1])&&e.type==='blob'&&e.mode==='100644'&&sha(e.sha),'Malformed settings retirement archive');result.set(path,e.sha);
  }
 }return result;
}
function decode(raw){const value=JSON.parse(raw.toString('utf8'));assert.ok(Buffer.from(JSON.stringify(value,null,2)+'\n').equals(raw),'Settings retirement JSON is not canonical');return value;}
async function verifyTransition(candidate,api,currentEntry,trees,now=Date.now()){
 const {receipt}=require('./_site_settings_delivery.cjs');
 const current=await mainSha(api),base=await baseline(api,candidate,current),oldTree=await tree(api,base,trees),newTree=await tree(api,candidate,trees);
 const before=oldTree.has(FILE)?await blob(api,FILE,base,16000,trees):null,old=before?receipt(before.raw):null;
 const previous=archives(oldTree),after=archives(newTree);
 for(const[path,id]of previous)assert.equal(after.get(path),id,'Immutable settings retirement history changed');
 const added=[...after.keys()].filter(path=>!previous.has(path));
 if(old!==null&&currentEntry!==null)assert.deepEqual(currentEntry,old,'Active settings proof requires separate retirement');
 const removed=old!==null&&currentEntry===null;
 if(removed||added.length){
  const path=PREFIX+base+'.json';assert.ok(removed&&added.length===1&&added[0]===path,'Settings removal requires exact retirement evidence');
  const rows=entries=>new Map([...entries].filter(([,e])=>e.type!=='tree').map(([p,e])=>[p,JSON.stringify([e.mode,e.type,e.sha])]));
  const a=rows(oldTree),b=rows(newTree),changed=[...new Set([...a.keys(),...b.keys()])].filter(p=>a.get(p)!==b.get(p)).sort();
  assert.deepEqual(changed,[FILE,path].sort(),'Settings retirement must be separate two-file candidate');
  const record=decode((await blob(api,path,candidate,64000,trees)).raw);
  assert.ok(exactKeys(record,['version','repository','publishedSha','receiptBlobSha','request','evidence','preparedAt'])&&
   record.version===1&&record.repository===REPO&&record.publishedSha===base&&record.receiptBlobSha===before.sha,'Settings retirement identity mismatch');
  assert.deepEqual(record.request,old,'Settings retirement request changed');
  assert.ok(time(record.preparedAt)<=now&&exactKeys(record.evidence,['workflows','deploymentId','statusId']),'Invalid settings retirement evidence');
  const policy=JSON.parse((await blob(api,'_delivery_policy.json',base,32000,trees)).raw.toString('utf8'));
  assert.equal(policy.site_settings_author_intent,true,'Published settings delivery policy missing');
  await publicationEvidence(api,base,candidate,record.evidence,trees);
 }
 assert.equal(await mainSha(api),current,'Settings main changed during retirement verification');
 return{retiredRequest:removed,baseline:base};
}
module.exports={verifyTransition};
