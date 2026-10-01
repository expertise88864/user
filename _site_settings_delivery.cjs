/* Production recheck of the exact settings approval already validated by CI.
 * Fixed paths/repository, ordinary immutable blobs, no writes or release permit. */
'use strict';
const assert=require('node:assert/strict'),{createHash}=require('node:crypto');
const {blob,tree,exactKeys,sha}=require('./_cms_delivery.cjs');
const {baseline,mainSha}=require('./_cms_retirement.cjs');
const contract=require('./_site_settings_contract.json');
const FILE='.site-settings-delivery.json',REPO='expertise88864/user',SOURCE='_site_settings.json',CATALOG='assets/settings-catalog.json';
const BRANCH='cms-settings/site',MANIFEST='.cms-settings/site.json',REQUEST='.cms-settings-requests/site.json';
const FIELDS=['version','repository','source','requestHead','requestBlobSha','draftHead','manifestBlobSha','baseMain','baseSha','catalogSha','settingsBlobSha','preparedAgainst','sourceSha256','settingsApproved'];
const DEFAULT={version:1,legacyPicks:true,font:{bodyFont:'',headFont:'',bodySize:''},order:[],picks:['acne-myths','sunscreen-myths','atopic-dermatitis-overview','topical-steroids-guide','hairloss-myths']};
const encoded=value=>Buffer.from(JSON.stringify(value,null,2)+'\n');
function decode(raw,compact=false){const value=JSON.parse(raw.toString('utf8'));assert.ok(Buffer.from(JSON.stringify(value,null,compact?undefined:2)+'\n').equals(raw),'Settings JSON is not canonical');return value;}
function baselineData(raw){
 // Existing author APIs accept valid JSON formatting for immutable baseline
 // data. Match Python without relaxing canonical approved source/proof bytes.
 const text=new TextDecoder('utf-8',{fatal:true}).decode(raw),value=JSON.parse(text);
 const tokens=text.match(/"(?:\\.|[^"\\])*"|[{}\[\]:,]/g)||[],stack=[];
 for(let i=0;i<tokens.length;i++){
  const token=tokens[i];
  if(token==='{')stack.push(new Set());else if(token==='[')stack.push(null);
  else if(token==='}'||token===']')stack.pop();
  else if(token.charAt(0)==='"'&&tokens[i+1]===':'&&stack.at(-1)){
   const key=JSON.parse(token),keys=stack.at(-1);assert.ok(!keys.has(key),'Duplicate baseline settings JSON key');keys.add(key);
  }
 }return value;
}
function receipt(raw){
 const value=decode(raw);assert.ok(exactKeys(value,['version','request'])&&value.version===1,'Invalid settings proof');
 const e=value.request;if(e===null)return null;
 assert.ok(exactKeys(e,FIELDS)&&e.version===1&&e.repository===REPO&&e.source===SOURCE&&e.settingsApproved===true,'Invalid settings author proof');
 for(const field of ['requestHead','requestBlobSha','draftHead','manifestBlobSha','baseMain','baseSha','catalogSha','settingsBlobSha','preparedAgainst'])assert.ok(sha(e[field]),'Invalid settings revision');
 assert.ok(typeof e.sourceSha256==='string'&&/^[a-f0-9]{64}$/.test(e.sourceSha256),'Invalid settings digest');return e;
}
function catalog(value){
 assert.ok(exactKeys(value,['version','articles'])&&value.version===1&&Array.isArray(value.articles)&&value.articles.length>0&&value.articles.length<=contract.maxArticles,'Invalid settings catalogue');
 const seen=new Set();for(const item of value.articles){
  assert.ok(exactKeys(item,['slug','title','title_en'])&&typeof item.slug==='string'&&item.slug.length<=100&&/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(item.slug)&&!seen.has(item.slug),'Invalid settings catalogue slug');
  for(const key of ['title','title_en'])assert.ok(typeof item[key]==='string'&&item[key].trim()&&item[key].length<=500&&!/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?:^|[^\uD800-\uDBFF])[\uDC00-\uDFFF]/.test(item[key]),'Invalid settings title');seen.add(item.slug);
 }return value.articles;
}
function settings(value,articles,stored=false){
 assert.ok(exactKeys(value,['version','legacyPicks','font','order','picks'])&&value.version===1&&typeof value.legacyPicks==='boolean'&&exactKeys(value.font,Object.keys(contract.fonts)),'Invalid settings config');
 for(const [key,choices]of Object.entries(contract.fonts))assert.ok(typeof value.font[key]==='string'&&choices.includes(value.font[key]),'Invalid settings font');
 const known=new Set(articles.map(a=>a.slug));for(const [key,max]of [['order',contract.maxArticles],['picks',contract.maxPicks]]){
  const values=value[key];assert.ok(Array.isArray(values)&&values.length<=max&&new Set(values).size===values.length&&values.every(v=>typeof v==='string'&&v.length<=100&&/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(v)&&(stored||known.has(v))),'Invalid settings selection');
 }assert.ok(value.picks.length>0&&(stored||!value.order.length||value.order.length===articles.length),'Incomplete settings selection');return value;
}
async function ancestor(api,base,head){if(base===head)return;const compare=await api('/compare/'+base+'...'+head);assert.ok(['ahead','identical'].includes(compare?.status)&&compare.merge_base_commit?.sha===base,'Settings ancestry invalid');}
async function optional(api,path,head,limit,trees){return(await tree(api,head,trees)).has(path)?blob(api,path,head,limit,trees):null;}
async function live(api,head){const ref=await api('/git/ref/heads/'+BRANCH);assert.ok(ref?.ref==='refs/heads/'+BRANCH&&ref.object?.type==='commit'&&ref.object.sha===head,'Settings request cancelled or superseded');}
function payloadRows(entries,excluded){return[...entries].filter(([path,e])=>e.type!=='tree'&&!excluded.has(path)).map(([path,e])=>[path,e.type,e.mode,e.sha]).sort((a,b)=>a[0]<b[0]?-1:a[0]>b[0]?1:0);}
async function payload(api,head,prepared,trees){
 const source=await blob(api,SOURCE,head,32000,trees),manifestBlob=await blob(api,MANIFEST,head,8000,trees),requestBlob=await blob(api,REQUEST,head,8000,trees);
 const m=decode(manifestBlob.raw,true),r=decode(requestBlob.raw,true);
 assert.ok(exactKeys(m,['version','source','baseMain','baseSha','catalogSha','blobSha','status'])&&m.version===1&&m.source===SOURCE&&m.status==='draft','Invalid settings manifest');
 for(const key of ['baseMain','baseSha','catalogSha','blobSha'])assert.ok(sha(m[key]),'Invalid settings manifest revision');assert.equal(m.blobSha,source.sha,'Manifest source mismatch');
 assert.ok(exactKeys(r,['version','status','branch','draftHead','blobSha','baseMain','baseSha','catalogSha','settingsApproved'])&&r.version===1&&r.status==='requested'&&r.branch===BRANCH&&r.settingsApproved===true&&sha(r.draftHead),'Settings approval missing');
 for(const key of ['blobSha','baseMain','baseSha','catalogSha'])assert.equal(r[key],m[key],'Request manifest mismatch');
 const commit=await api('/git/commits/'+head);assert.ok(commit?.sha===head&&Array.isArray(commit.parents)&&commit.parents.length===1&&commit.parents[0]?.sha===r.draftHead,'Settings request is not the single child of draft');
 const parentSource=await blob(api,SOURCE,r.draftHead,32000,trees),parentManifest=await blob(api,MANIFEST,r.draftHead,8000,trees);
 assert.ok(parentSource.sha===source.sha&&parentManifest.sha===manifestBlob.sha&&await optional(api,REQUEST,r.draftHead,8000,trees)===null,'Settings request content changed or intent reused');
 assert.deepEqual(payloadRows(await tree(api,r.draftHead,trees),new Set([REQUEST])),payloadRows(await tree(api,head,trees),new Set([REQUEST])),'Settings request changed more than intent');
 await ancestor(api,m.baseMain,prepared);await ancestor(api,m.baseMain,r.draftHead);
 const baseSource=await blob(api,SOURCE,m.baseMain,32000,trees),baseCatalog=await blob(api,CATALOG,m.baseMain,200000,trees);
 assert.ok(baseSource.sha===m.baseSha&&baseCatalog.sha===m.catalogSha,'Settings baseline blobs changed');
 const articles=catalog(baselineData(baseCatalog.raw)),before=settings(baselineData(baseSource.raw),articles,true),after=settings(decode(source.raw),articles);
 assert.ok(before.legacyPicks!==false||after.legacyPicks!==true,'Settings cannot reactivate legacy reads');
 const excluded=new Set([SOURCE,MANIFEST,REQUEST]);assert.deepEqual(payloadRows(await tree(api,m.baseMain,trees),excluded),payloadRows(await tree(api,head,trees),excluded),'Collateral settings branch changes');
 return{source,proof:{version:1,repository:REPO,source:SOURCE,requestHead:head,requestBlobSha:requestBlob.sha,draftHead:r.draftHead,manifestBlobSha:manifestBlob.sha,
  baseMain:m.baseMain,baseSha:m.baseSha,catalogSha:m.catalogSha,settingsBlobSha:source.sha,preparedAgainst:prepared,sourceSha256:createHash('sha256').update(source.raw).digest('hex'),settingsApproved:true}};
}
async function verify(candidate,api){
 assert.ok(sha(candidate),'Invalid settings candidate');const trees=new Map(),current=await mainSha(api),previous=await baseline(api,candidate,current);
 const source=await blob(api,SOURCE,candidate,32000,trees),proofBlob=await blob(api,FILE,candidate,16000,trees),e=receipt(proofBlob.raw);
 const oldSource=await optional(api,SOURCE,previous,32000,trees),oldProof=await optional(api,FILE,previous,16000,trees),old=oldProof?receipt(oldProof.raw):null;
 await require('./_site_settings_retirement.cjs').verifyTransition(candidate,api,e,trees);
 if(e===null){
  if(oldSource===null){assert.equal(oldProof,null,'Invalid settings bootstrap');const articles=catalog(baselineData((await blob(api,CATALOG,candidate,200000,trees)).raw));assert.deepEqual(settings(decode(source.raw),articles),DEFAULT,'Bootstrap must keep original settings');assert.ok(source.raw.equals(encoded(DEFAULT)),'Bootstrap settings bytes differ');}
  else assert.ok(oldProof!==null&&oldSource.sha===source.sha,'Settings changed without author intent');
 }else{
  await live(api,e.requestHead);await ancestor(api,e.preparedAgainst,candidate);const approved=await payload(api,e.requestHead,e.preparedAgainst,trees);
  assert.deepEqual(e,approved.proof,'Settings approval proof differs');assert.ok(source.sha===e.settingsBlobSha&&source.raw.equals(approved.source.raw),'Settings payload differs from approval');
  if(old===null){assert.ok(e.preparedAgainst===previous&&oldSource?.sha===e.baseSha,'New settings preparation baseline stale');assert.equal((await blob(api,CATALOG,previous,200000,trees)).sha,e.catalogSha,'Settings catalogue changed');}
  await live(api,e.requestHead);
 }
 assert.equal(await mainSha(api),current,'Settings main changed during validation');return{sha:candidate,activeRequest:e!==null,authorIntentVerified:true,candidatePayloadVerified:true,published:false};
}
module.exports={verify,receipt,DEFAULT,FILE};
