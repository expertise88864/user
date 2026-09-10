const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('admin.html', 'utf8');
const OLD = 'a'.repeat(40), BLOB = 'b'.repeat(40), COMMIT = 'c'.repeat(40);
const deferred = () => { let resolve, reject; const promise = new Promise((a,b)=>{resolve=a;reject=b}); return {promise,resolve,reject}; };
function historySetup(){
  const requests=[],messages=[];let token='test-only',logout=false;
  const diff={textContent:'',html:'',button:null,set innerHTML(value){this.html=value;this.button=value.includes('id="restoreBtn"')?{addEventListener:(name,fn)=>{this.restore=fn}}:null;},get innerHTML(){return this.html},querySelector:()=>diff.button};
  const bg={isConnected:true,historyContext:{file:'blog/a.html',loadId:1,token:'test-only',requestId:0},querySelector:()=>diff,remove(){this.isConnected=false}};
  const c={CURRENT_FILE:'blog/a.html',EDITOR_LOAD_ID:1,EDITOR_LOADING:false,SAVE_PENDING:false,
    CURRENT_CONTENT:'current',SOURCE_MODE:true,BILINGUAL_MODE:false,sourceTextarea:{value:'current'},DIRTY:false,
    auth:{getPat:()=>token,isLogoutPending:()=>logout},BRANCH:'main',
    gh:async(method,path)=>{const gate=deferred();requests.push({method,path,gate});return gate.promise},
    decodeUtf8Base64:x=>x,renderDiff:(a,b)=>a+' => '+b,setStatus:m=>messages.push(m),alert:m=>messages.push(m),confirm:()=>true};
  vm.createContext(c);
  if(source.includes('function historyContextIsCurrent('))vm.runInContext(section('function historyContextIsCurrent(', 'async function loadHistoryList('),c);
  vm.runInContext(section('async function loadHistoryList(', 'function renderDiff('),c);
  return {c,bg,diff,requests,messages,setToken:v=>{token=v},logout:()=>{logout=true}};
}
test('history preview keeps the newest selection when older requests finish later',async()=>{
  const h=historySetup();const a=h.c.showCommitDiff(h.bg,OLD,false),b=h.c.showCommitDiff(h.bg,BLOB,false);
  h.requests[1].gate.resolve({content:'selected B'});await b;
  h.requests[0].gate.resolve({content:'stale A'});await a;
  assert.match(h.diff.innerHTML,/selected B/);assert.doesNotMatch(h.diff.innerHTML,/stale A/);
  h.diff.restore();assert.equal(h.c.CURRENT_CONTENT,'selected B');assert.equal(h.c.DIRTY,true);
});
test('history ignores stale request failures after a newer selection succeeds',async()=>{
  const h=historySetup();const a=h.c.showCommitDiff(h.bg,OLD,false),b=h.c.showCommitDiff(h.bg,BLOB,false);
  h.requests[1].gate.resolve({content:'selected B'});await b;const prior=h.diff.textContent;
  h.requests[0].gate.reject(Error('late failure'));await a;assert.equal(h.diff.textContent,prior);
});
test('history cannot replace editor content after file, load, login or busy state changes',async()=>{
  for(const invalidate of [h=>h.c.CURRENT_FILE='blog/b.html',h=>h.c.EDITOR_LOAD_ID++,h=>h.setToken('different'),h=>h.logout(),h=>h.c.SAVE_PENDING=true,h=>h.c.EDITOR_LOADING=true,h=>h.bg.remove()]){
    const h=historySetup();const pending=h.c.showCommitDiff(h.bg,OLD,false);h.requests[0].gate.resolve({content:'old'});await pending;
    invalidate(h);h.diff.restore();assert.equal(h.c.CURRENT_CONTENT,'current');assert.equal(h.c.DIRTY,false);
  }
});
test('history drops results for a closed dialog or changed editor identity',async()=>{
  for(const invalidate of [h=>h.bg.remove(),h=>h.c.EDITOR_LOAD_ID++,h=>h.c.CURRENT_FILE='blog/b.html',h=>h.logout()]){
    const h=historySetup();const pending=h.c.showCommitDiff(h.bg,OLD,false);invalidate(h);h.requests[0].gate.resolve({content:'stale'});await pending;
    assert.equal(h.diff.innerHTML,'');
  }
});
function section(start,end){ const a=source.indexOf(start); assert.ok(a>=0,start); const b=source.indexOf(end,a); assert.ok(b>a,end); return source.slice(a,b); }
function uploadSetup(){
  const calls=[];
  const c={window:{},BRANCH:'main',prompt:()=> 'image description',setStatus:()=>{},
    compressImage:async file=>({blob:file,ext:'.webp',newSize:1024,w:100,h:100}),
    _originalUploadImage:async()=>{calls.push('fallback');return '/original.png'},
    FileReader:class {readAsDataURL(){this.result='data:image/webp;base64,AA==';queueMicrotask(()=>this.onload())}},
    gh:async()=>{calls.push('PUT');throw Error('network outcome unknown')}};
  vm.createContext(c);vm.runInContext(section('uploadImage = async function(', '// Override insertImageAtSelection'),c);
  return {c,calls,file:{name:'photo.png',type:'image/png',size:4096}};
}
test('image upload never falls back to another write after an ambiguous API failure',async()=>{
  const h=uploadSetup();await assert.rejects(h.c.uploadImage(h.file),/network outcome unknown/);assert.deepEqual(h.calls,['PUT']);
});
test('cancelling image description does not upload a file',async()=>{
  const h=uploadSetup();h.c.prompt=()=>null;await assert.rejects(h.c.uploadImage(h.file),/取消/);assert.deepEqual(h.calls,[]);
});
test('only compression errors select the original-image fallback and preserve alt text',async()=>{
  const h=uploadSetup();h.c.compressImage=async()=>{throw Error('decode failed')};
  const result=await h.c.uploadImage(h.file);assert.equal(result.url,'/original.png');assert.equal(result.alt,'image description');assert.deepEqual(h.calls,['fallback']);
});
test('GIF skips compression but still supports description and cancellation',async()=>{
  const h=uploadSetup();h.c.compressImage=()=>{throw Error('should not compress')};h.file.type='image/gif';
  assert.equal((await h.c.uploadImage(h.file)).alt,'image description');assert.deepEqual(h.calls,['fallback']);
  h.c.prompt=()=>null;await assert.rejects(h.c.uploadImage(h.file),/取消/);assert.equal(h.calls.length,1);
});
test('compressed file read errors and aborts reject without uploading or retrying',async()=>{
  for(const event of ['onerror','onabort']){
    const h=uploadSetup();h.c.FileReader=class {readAsDataURL(){queueMicrotask(()=>this[event]())}};
    await assert.rejects(h.c.uploadImage(h.file),/讀取/);assert.deepEqual(h.calls,[]);
  }
});
test('original-image reads reject errors and aborts without leaving uploads pending',async()=>{
  for(const event of ['onerror','onabort']){
    const calls=[];const c={BRANCH:'main',setStatus:()=>{},gh:async()=>calls.push('PUT'),
      FileReader:class {readAsDataURL(){queueMicrotask(()=>this[event]())}}};
    vm.createContext(c);vm.runInContext(section('async function uploadImage(', '// =========== formatting buttons'),c);
    await assert.rejects(c.uploadImage({name:'a.gif',type:'image/gif'}),/讀取/);assert.deepEqual(calls,[]);
  }
});
function imageInsertionSetup(){
  const controls=[{disabled:false},{disabled:true}],inserted=[],messages=[],requests=[];
  let token='test-only',logout=false;
  const ancestor={isConnected:true,nodeType:1,closest:()=>({})};
  const range={commonAncestorContainer:ancestor};
  const doc={getSelection:()=>({rangeCount:1,getRangeAt:()=>({cloneRange:()=>range})})};
  const c={CURRENT_FILE:'blog/a.html',EDITOR_LOAD_ID:1,EDITOR_LOADING:false,SAVE_PENDING:false,SOURCE_MODE:false,BILINGUAL_MODE:false,
    auth:{getPat:()=>token,isLogoutPending:()=>logout},editFrame:{contentDocument:doc},
    document:{querySelectorAll:()=>controls},setStatus:m=>messages.push(m),
    gh:async(...args)=>requests.push(args),insertImageAtSelection:(...args)=>inserted.push(args),
    uploadImage:async(file,prefix,request)=>{await request('PUT',file.name);return {url:'/'+file.name,alt:file.name}}};
  vm.createContext(c);vm.runInContext(section('async function uploadAndInsertImages(', 'async function uploadImage('),c);
  return {c,controls,inserted,messages,requests,range,setToken:v=>{token=v},logout:()=>{logout=true}};
}
test('image batches preserve initial range and per-image descriptions and restore control states',async()=>{
  const h=imageInsertionSetup();await h.c.uploadAndInsertImages([{name:'a'},{name:'b'}]);
  assert.equal(h.inserted.length,2);assert.equal(h.inserted[0][1],h.range);assert.equal(h.inserted[1][1],h.range);
  assert.equal(h.inserted[0][2],'a');assert.equal(h.inserted[1][2],'b');
  assert.deepEqual(h.controls.map(c=>c.disabled),[false,true]);assert.equal(h.c.SAVE_PENDING,false);
});
test('pending image upload blocks duplicate operations without releasing the first lock',async()=>{
  const h=imageInsertionSetup(),gate=deferred();h.c.uploadImage=async()=>{await gate.promise;return {url:'/a',alt:'a'}};
  const first=h.c.uploadAndInsertImages([{name:'a'}]);assert.equal(h.c.SAVE_PENDING,true);
  await h.c.uploadAndInsertImages([{name:'b'}]);assert.equal(h.c.SAVE_PENDING,true);assert.equal(h.inserted.length,0);
  gate.resolve();await first;assert.equal(h.inserted.length,1);assert.equal(h.c.SAVE_PENDING,false);
});
test('image upload checks the original editor and session again before the remote write',async()=>{
  for(const invalidate of [h=>h.c.CURRENT_FILE='blog/b.html',h=>h.c.EDITOR_LOAD_ID++,h=>h.setToken('new'),h=>h.logout(),h=>h.c.SOURCE_MODE=true,h=>h.range.commonAncestorContainer.isConnected=false,h=>h.range.commonAncestorContainer.closest=()=>null]){
    const h=imageInsertionSetup(),gate=deferred();h.c.uploadImage=async(file,prefix,request)=>{await gate.promise;await request('PUT','a');return {url:'/a',alt:'a'}};
    const work=h.c.uploadAndInsertImages([{name:'a'}]);invalidate(h);gate.resolve();await work;
    assert.equal(h.requests.length,0);assert.equal(h.inserted.length,0);assert.equal(h.c.SAVE_PENDING,false);
  }
});
test('late image response cannot insert into a different editor document',async()=>{
  const h=imageInsertionSetup(),gate=deferred();h.c.uploadImage=async()=>{await gate.promise;return {url:'/a',alt:'a'}};
  const work=h.c.uploadAndInsertImages([{name:'a'}]);h.c.editFrame.contentDocument={};gate.resolve();await work;
  assert.equal(h.inserted.length,0);assert.equal(h.c.SAVE_PENDING,false);assert.match(h.messages.at(-1),/未插入/);
});
function setup(){
  const requests=[], storage=new Map(), cleared=[], messages=[];
  let put;
  const c={CURRENT_FILE:'blog/a.html',CURRENT_SHA:OLD,CURRENT_CONTENT:'original',DIRTY:true,
    SAVE_PENDING:false,EDITOR_LOADING:false,EDITOR_LOAD_ID:1,PAT:'test-only',BRANCH:'main',REPO:'test/repo',
    SOURCE_MODE:true,BILINGUAL_MODE:false,sourceTextarea:{value:'submitted'},editFrame:null,
    AUTOSAVE_KEY_PREFIX:'draft:',lastAutosaveAt:0,
    mergeBilingualBack:()=>c.bilingualContent,mergeIframeIntoOriginal:()=>c.visualContent,
    encodeUtf8Base64:x=>x,decodeUtf8Base64:x=>x,escapeHtml:x=>x,
    localStorage:{setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    clearAutosaveFor:f=>{cleared.push(f);storage.delete('draft:'+f)},updateAutosaveIndicator:()=>{},
    setStatus:m=>messages.push(m),toast:m=>messages.push(m),alert:m=>messages.push(m),confirm:()=>false,
    elShaInfo:{},elFilePath:{},document:{querySelectorAll:()=>[]},
    mountSource:x=>{c.sourceTextarea={value:x}},mountIframe:()=>{},
    console,window:{open:()=>{throw new Error('Unexpected external navigation')}},
    gh:async(method,path,body)=>{
      requests.push({method,path,body});
      if(method==='PUT'){put=body;return {content:{sha:BLOB},commit:{sha:COMMIT}};}
      if(path.includes('?ref='+COMMIT))return {sha:BLOB,content:put.content};
      return {sha:OLD};
    },
  };
  vm.createContext(c);
  vm.runInContext(section('function autosaveKey(', 'function updateAutosaveIndicator('),c);
  vm.runInContext(section('function showSaveModal(', '// Re-wire save button'),c);
  vm.runInContext(section('async function saveAsDraft(', '// ───'),c);
  vm.runInContext(section('async function loadFile(path){', '// =========== mount visual iframe'),c);
  vm.runInContext(section('function openScheduleModal(){', '// ───'),c);
  c.showSaveModal=async()=> 'test save';
  return {c,requests,storage,cleared,messages};
}
test('main save verifies immutable commit and only then clears its matching draft',async()=>{
  const {c,requests,cleared}=setup(); await c.saveWithModal();
  assert.equal(requests[0].method,'PUT');assert.equal(requests[0].body.sha,OLD);
  assert.equal(requests[1].path,'contents/blog/a.html?ref='+COMMIT);
  assert.equal(c.CURRENT_SHA,BLOB);assert.equal(c.CURRENT_CONTENT,'submitted');assert.equal(c.DIRTY,false);
  assert.deepEqual(cleared,['blog/a.html']);assert.equal(c.SAVE_PENDING,false);
});
test('typing during save stays dirty and autosaved, with new remote SHA for the next save',async()=>{
  const {c,storage,cleared}=setup(), gate=deferred(),started=deferred();const gh=c.gh;
  c.gh=async(...args)=>{if(args[0]==='PUT'){started.resolve();await gate.promise;}return gh(...args)};
  const pending=c.saveWithModal();await started.promise;
  c.sourceTextarea.value='newer edits';gate.resolve();await pending;
  assert.equal(c.CURRENT_SHA,BLOB);assert.equal(c.DIRTY,true);assert.equal(c.sourceTextarea.value,'newer edits');
  assert.equal(JSON.parse(storage.get('draft:blog/a.html')).content,'newer edits');assert.deepEqual(cleared,[]);
});
test('a stale completion cannot replace another article or clear its draft',async()=>{
  const {c,cleared}=setup(),gate=deferred(),started=deferred();const gh=c.gh;
  c.gh=async(...args)=>{if(args[0]==='PUT'){started.resolve();await gate.promise;}return gh(...args)};
  const pending=c.saveWithModal();await started.promise;
  c.CURRENT_FILE='blog/b.html';c.CURRENT_SHA='d'.repeat(40);c.CURRENT_CONTENT='B base';c.EDITOR_LOAD_ID++;
  c.sourceTextarea.value='B edits';gate.resolve();await pending;
  assert.equal(c.CURRENT_SHA,'d'.repeat(40));assert.equal(c.CURRENT_CONTENT,'B base');assert.equal(c.DIRTY,true);assert.deepEqual(cleared,[]);
});
test('one modal/write at a time; confirmation captures the latest editor content',async()=>{
  const {c,requests}=setup(),gate=deferred();let dialogs=0;
  c.showSaveModal=()=>{dialogs++;return gate.promise};
  const first=c.saveWithModal();await c.saveWithModal();await c.saveAsDraft(true);
  assert.equal(dialogs,1);assert.equal(requests.length,0);
  c.sourceTextarea.value='edited before confirmation';gate.resolve('save');await first;
  assert.equal(requests[0].body.content,'edited before confirmation');
});
test('cancelled modal releases lock without writing or clearing drafts',async()=>{
  const {c,requests,cleared}=setup();c.showSaveModal=async()=>null;await c.saveWithModal();
  assert.equal(c.SAVE_PENDING,false);assert.equal(requests.length,0);assert.deepEqual(cleared,[]);assert.equal(c.DIRTY,true);
});
for(const failure of ['network','mismatch'])test('verification '+failure+' preserves recovery copy and never reports clean',async()=>{
  const {c,storage,cleared}=setup(),gh=c.gh;
  c.gh=async(...args)=>{if(args[0]==='GET'){if(failure==='network')throw new Error('offline');return {sha:BLOB,content:'different'};}return gh(...args)};
  await c.saveWithModal();assert.equal(c.DIRTY,true);assert.equal(c.CURRENT_SHA,BLOB);assert.deepEqual(cleared,[]);
  assert.equal(JSON.parse(storage.get('draft:blog/a.html')).content,'submitted');assert.equal(c.SAVE_PENDING,false);
});
test('write conflict preserves source SHA, editor and autosave',async()=>{
  const {c,storage}=setup();c.gh=async()=>{throw new Error('conflict')};await c.saveWithModal();
  assert.equal(c.CURRENT_SHA,OLD);assert.equal(c.DIRTY,true);assert.equal(c.sourceTextarea.value,'submitted');assert.ok(storage.has('draft:blog/a.html'));
});
test('dual-language and metadata-only edits are included in autosave',()=>{
  const {c,storage}=setup();c.BILINGUAL_MODE=true;c.bilingualContent='both languages';c.autosave();
  assert.equal(JSON.parse(storage.get('draft:blog/a.html')).content,'both languages');
  c.BILINGUAL_MODE=false;c.CURRENT_CONTENT='metadata edit';c.sourceTextarea.value='metadata edit';c.autosave();
  assert.equal(JSON.parse(storage.get('draft:blog/a.html')).content,'metadata edit');
});
test('verified draft saves do not replace the main blob SHA',async()=>{
  const {c,requests}=setup();const result=await c.saveAsDraft(true);
  assert.equal(result.branch,'drafts/a');assert.equal(c.CURRENT_SHA,OLD);assert.equal(c.DIRTY,false);
  assert.ok(requests.some(r=>r.path==='contents/blog/a.html?ref='+COMMIT));
});
test('draft fetch permission failures never fall through to a create write',async()=>{
  const {c,requests}=setup();let calls=0;c.gh=async()=>{calls++;throw Object.assign(new Error('Forbidden'),{status:403})};
  assert.equal(await c.saveAsDraft(true),null);assert.equal(calls,1);assert.equal(requests.length,0);assert.equal(c.DIRTY,true);assert.equal(c.SAVE_PENDING,false);
});
test('only an actual 404 creates a missing draft branch/file, then verifies its commit',async()=>{
  const {c,requests}=setup(),gh=c.gh;const routes=[];
  c.gh=async(m,p,b)=>{
    routes.push({m,p,b});
    if(p.startsWith('branches/') || p.includes('?ref=drafts%2F'))throw Object.assign(new Error('Not Found'),{status:404});
    if(p==='git/refs/heads/main')return {object:{sha:COMMIT}};
    if(m==='POST')return {};
    return gh(m,p,b);
  };
  assert.ok(await c.saveAsDraft(true));
  assert.equal(routes.find(r=>r.m==='POST').b.ref,'refs/heads/drafts/a');
  assert.equal(requests.find(r=>r.method==='PUT').body.sha,undefined);
  assert.equal(c.CURRENT_SHA,OLD);
});
test('unverified draft returns no publishable result and preserves its recovery copy',async()=>{
  const {c,storage,cleared}=setup(),gh=c.gh;
  c.gh=async(...args)=>{if(args[1].includes('?ref='+COMMIT))throw new Error('verify offline');return gh(...args)};
  assert.equal(await c.saveAsDraft(true),null);assert.equal(c.DIRTY,true);assert.equal(c.CURRENT_SHA,OLD);
  assert.deepEqual(cleared,[]);assert.ok(storage.has('draft:blog/a.html'));
});
test('typing during a silent draft save prevents it from becoming a scheduling result',async()=>{
  const {c,storage}=setup(),gate=deferred(),started=deferred(),gh=c.gh;
  c.gh=async(...args)=>{if(args[0]==='PUT'){started.resolve();await gate.promise;}return gh(...args)};
  const pending=c.saveAsDraft(true);await started.promise;c.sourceTextarea.value='newer draft edits';gate.resolve();
  assert.equal(await pending,null);assert.equal(c.DIRTY,true);
  assert.equal(JSON.parse(storage.get('draft:blog/a.html')).content,'newer draft edits');
});
test('schedule handler refuses changed live content after queue fetch, without writing the queue',async()=>{
  const {c,storage}=setup(),gate=deferred(),started=deferred();const elements={};let writes=0;
  const bg={querySelector:id=>elements[id]||(elements[id]={addEventListener:(_event,fn)=>{elements[id].handler=fn}}),remove:()=>{}};
  c.document.createElement=()=>bg;c.document.body={appendChild:()=>{}};
  const snapshot=c.captureSaveSnapshot();c.saveAsDraft=async()=>({...snapshot,branch:'drafts/a',sha:BLOB});
  c.gh=async(method)=>{if(method==='PUT'){writes++;return {}}started.resolve();await gate.promise;return {sha:OLD,content:'[]'}};
  c.openScheduleModal();bg.querySelector('#schedAt').value=new Date(Date.now()+86400000).toISOString().slice(0,16);
  const pending=elements['#schedConfirm'].handler();await started.promise;
  c.sourceTextarea.value='changed while fetching queue';gate.resolve();await pending;
  assert.equal(writes,0);assert.equal(elements['#schedConfirm'].disabled,false);
  assert.equal(JSON.parse(storage.get('draft:blog/a.html')).content,'changed while fetching queue');
});
test('a stale schedule dialog cannot save a different article before validating its identity',async()=>{
  const {c}=setup();const elements={};let saves=0;
  const bg={querySelector:id=>elements[id]||(elements[id]={addEventListener:(_event,fn)=>{elements[id].handler=fn}}),remove:()=>{}};
  c.document.createElement=()=>bg;c.document.body={appendChild:()=>{}};c.saveAsDraft=async()=>{saves++;return null};
  c.openScheduleModal();bg.querySelector('#schedAt').value=new Date(Date.now()+86400000).toISOString().slice(0,16);
  c.CURRENT_FILE='blog/b.html';c.EDITOR_LOAD_ID++;await elements['#schedConfirm'].handler();
  assert.equal(saves,0);assert.equal(elements['#schedConfirm'].disabled,false);
});
test('loading is blocked while saving, and saving is blocked while loading',async()=>{
  const {c,requests}=setup();c.SAVE_PENDING=true;assert.equal(await c.loadFile('blog/b.html'),false);
  assert.equal(c.CURRENT_FILE,'blog/a.html');c.SAVE_PENDING=false;c.EDITOR_LOADING=true;await c.saveWithModal();assert.equal(requests.length,0);
});
test('out-of-order loads cannot restore an older selected article',async()=>{
  const {c}=setup(),a=deferred(),b=deferred();c.DIRTY=false;c.gh=(_m,p)=>p.endsWith('a.html')?a.promise:b.promise;
  const pa=c.loadFile('blog/a.html'),pb=c.loadFile('blog/b.html');b.resolve({sha:BLOB,content:'B'});await pb;
  a.resolve({sha:OLD,content:'A'});await pa;assert.equal(c.CURRENT_FILE,'blog/b.html');assert.equal(c.CURRENT_CONTENT,'B');assert.equal(c.EDITOR_LOADING,false);
});

function creationHarness({mirror=true,fail='',existing=false,catalog="  DN.ARTICLES = [\n    { slug:'old', title:'Original' },\n  ];",lostResponse=false,readFailure=false,unconfirmed=false}={}) {
  const requests=[];let published=OLD,prepared;
  const c={BRANCH:'main',decodeUtf8Base64:s=>s,gh:async(method,path,body)=>{
    requests.push({method,path,body});
    if(method==='PUT') throw new Error('Partial Contents write forbidden');
    if(method==='GET' && path==='git/ref/heads/main')return {object:{sha:published}};
    if(method==='GET' && path==='git/commits/'+OLD)return {tree:{sha:BLOB}};
    if(method==='GET' && path.startsWith('contents/blog/blog-shared.js?ref=')){
      assert.ok(path.endsWith(OLD));return {content:catalog};
    }
    if(method==='GET' && path.startsWith('contents/')){
      assert.ok(path.endsWith('?ref='+OLD));if(readFailure)throw Object.assign(new Error('forbidden'),{status:403});if(existing)return {sha:BLOB};
      throw Object.assign(new Error('not found'),{status:404});
    }
    if(path===fail)throw Object.assign(new Error('simulated failure'),{status:path.startsWith('git/refs/')?409:500});
    if(path==='git/trees'){prepared=body;return {sha:BLOB};}
    if(path==='git/commits'){assert.deepEqual(Array.from(body.parents),[OLD]);assert.equal(body.tree,BLOB);return {sha:COMMIT};}
    if(path==='git/refs/heads/main'){
      assert.equal(body.force,false);assert.equal(body.sha,COMMIT);published=COMMIT;
      if(unconfirmed){published='d'.repeat(40);throw new Error('connection lost');}
      if(lostResponse)throw new Error('connection lost');return {object:{sha:COMMIT}};
    }
    throw new Error('Unexpected request '+path);
  }};
  vm.createContext(c);vm.runInContext(section('async function createArticleAtomically(', 'function openNewArticleWizard(){'),c);
  return {requests,published:()=>published,prepared:()=>prepared,run:()=>c.createArticleAtomically({slug:'new-article',html:'<html lang="zh-Hant-TW">原文</html>',mirror,title:'Title',sub:'Subtitle',tag:'Tag',type:'note',date:'2026-09-10'})};
}
test('article creation publishes source, optional mirror and catalog with one ref update',async()=>{
  for(const mirror of [true,false]){
    const h=creationHarness({mirror});assert.equal(await h.run(),COMMIT);
    assert.equal(h.published(),COMMIT);assert.equal(h.prepared().base_tree,BLOB);
    const files=h.prepared().tree;assert.equal(files.length,mirror?3:2);
    assert.equal(files[0].path,'blog/new-article.html');assert.match(files[0].content,/原文/);
    if(mirror){assert.equal(files[1].path,'en/blog/new-article.html');assert.match(files[1].content,/lang="en"/);}
    assert.match(files.at(-1).content,/slug:'old'/);assert.match(files.at(-1).content,/slug:'new-article'/);
    assert.equal(h.requests.filter(r=>r.method==='PATCH').length,1);
  }
});
for(const fail of ['git/trees','git/commits','git/refs/heads/main'])test('creation failure preserves branch at '+fail,async()=>{
  const h=creationHarness({fail});await assert.rejects(h.run());assert.equal(h.published(),OLD);
  assert.ok(h.requests.every(r=>r.method!=='PUT'));
});
test('duplicate files and invalid or duplicate catalog fail before writing objects',async()=>{
  for(const options of [{existing:true},{catalog:'unrecognized catalog'},{catalog:"DN.ARTICLES = [\n {slug:'new-article'},\n  ];"}]){
    const h=creationHarness(options);await assert.rejects(h.run());assert.equal(h.published(),OLD);
    assert.ok(h.requests.every(r=>r.method==='GET'));
  }
});
test('lost successful ref response is verified without duplicate creation',async()=>{
  const h=creationHarness({lostResponse:true});assert.equal(await h.run(),COMMIT);
  assert.equal(h.requests.filter(r=>r.method==='PATCH').length,1);
  assert.equal(h.requests.filter(r=>r.path==='git/commits' && r.method==='POST').length,1);
});

test('unreadable paths do not masquerade as absent files',async()=>{
 const h=creationHarness({readFailure:true});await assert.rejects(h.run(),/forbidden/);
 assert.equal(h.published(),OLD);assert.ok(h.requests.every(r=>r.method==='GET'));
});
test('uncertain creation outcome never triggers another ref update',async()=>{
 const h=creationHarness({unconfirmed:true});await assert.rejects(h.run(),/尚無法確認/);
 assert.equal(h.requests.filter(r=>r.method==='PATCH').length,1);
});
test('wizard blocks duplicate creation and preserves input when creation fails',async()=>{
 const pending=deferred();let handler,calls=0,removed=0;
 const fields=Object.fromEntries(['Type','Title','Sub','Tag','Desc','Mirror'].map(k=>['#wiz'+k,{value:k==='Type'?'myth':k,checked:true,disabled:false}]));
 const controls=Object.values(fields);fields['#wizStatus']={textContent:''};fields['#wizCreate']={addEventListener:(name,fn)=>{handler=fn;}};
 const c={SAVE_PENDING:false,EDITOR_LOADING:false,auth:{getPat:()=> 'same-session',isLogoutPending:()=>false},
  bg:{querySelector:s=>fields[s],querySelectorAll:()=>controls,remove:()=>removed++},slug:'new-article',
  generateNewArticleSkeleton:()=>'<html>draft</html>',createArticleAtomically:()=>{calls++;return pending.promise;},
  setStatus:()=>{},toast:()=>{},alert:()=>{},gh:()=>{},
  document:{getElementById:()=>({value:'new-article'})},refreshFileList:async()=>{},loadFile:async()=>{throw new Error('Must not load a failed creation');}};
 vm.createContext(c);
 const wizardSource=source.replace(/\r\n/g,'\n');
 const start=wizardSource.indexOf("bg.querySelector('#wizCreate').addEventListener('click', async ()=>{");
 const end=wizardSource.indexOf('\n});\n}',start);
 assert.ok(start>=0 && end>start);
 vm.runInContext(wizardSource.slice(start,end+4),c);
 const first=handler();await handler();assert.equal(calls,1);assert.equal(c.SAVE_PENDING,true);
 assert.ok(controls.every(x=>x.disabled));pending.reject(new Error('simulated failure'));await first;
 assert.equal(c.SAVE_PENDING,false);assert.equal(fields['#wizStatus'].textContent,'simulated failure');assert.equal(removed,0);assert.equal(fields['#wizTitle'].value,'Title');
 assert.ok(controls.every(x=>!x.disabled));
});
