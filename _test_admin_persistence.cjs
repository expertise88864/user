const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('admin.html', 'utf8');
const OLD = 'a'.repeat(40), BLOB = 'b'.repeat(40), COMMIT = 'c'.repeat(40);
const deferred = () => { let resolve, reject; const promise = new Promise((a,b)=>{resolve=a;reject=b}); return {promise,resolve,reject}; };
function section(start,end){ const a=source.indexOf(start); assert.ok(a>=0,start); const b=source.indexOf(end,a); assert.ok(b>a,end); return source.slice(a,b); }
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
