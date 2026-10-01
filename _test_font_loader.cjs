'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('assets/inline/font-loader.js','utf8');
function fixture({cached=false,painted=false,support=true,complete=false,broken=false,empty=false}={}){
 const frames=[],timers=new Map(),events={},loaders={},writes=[];let observed,disconnected=false,next=1;
 const link={sheet:cached?{}:null,addEventListener:(name,fn)=>{loaders[name]=fn;}};
 let media='print';Object.defineProperty(link,'media',{get:()=>media,set:value=>{media=value;writes.push(value);}});
 class Observer{static supportedEntryTypes=support?['paint']:[];constructor(fn){if(broken)throw Error('fixture unavailable observer');observed=fn;}observe(){}disconnect(){disconnected=true;}}
 const window={addEventListener:(name,fn)=>{(events[name] ||= []).push(fn);}};
 const context={window,document:{readyState:complete?'complete':'loading',querySelectorAll:()=>empty?[]:[link]},
  performance:{getEntriesByName:()=>painted?[{name:'first-contentful-paint'}]:[]},PerformanceObserver:Observer,
  requestAnimationFrame:fn=>frames.push(fn),setTimeout:(fn,delay)=>{const id=next++;timers.set(id,{fn,delay});return id;},clearTimeout:id=>timers.delete(id)};
 const run=()=>vm.runInNewContext(source,context);run();
 return {link,writes,run,loadCss:()=>loaders.load?.(),paint:(name='first-contentful-paint')=>observed?.({getEntries:()=>[{name}]}),
  frames:()=>{const pending=frames.splice(0);pending.forEach(fn=>fn());},loadPage:()=>events.load?.forEach(fn=>fn()),
  timers:()=>{const pending=[...timers.values()];timers.clear();pending.forEach(item=>item.fn());},disconnected:()=>disconnected};
}
test('cached CSS never activates merely because two animation frames elapsed',()=>{
 const f=fixture({cached:true});f.frames();f.frames();assert.equal(f.link.media,'print');
 f.paint('first-paint');assert.equal(f.link.media,'print');f.paint();assert.equal(f.link.media,'all');assert.ok(f.disconnected());
});
test('font CSS and first contentful paint may arrive in either order',()=>{
 for(const order of ['css-first','paint-first']){
  const f=fixture();if(order==='css-first')f.loadCss();else f.paint();assert.equal(f.link.media,'print',order);
  if(order==='css-first')f.paint();else f.loadCss();assert.equal(f.link.media,'all',order);
 }
});
test('a buffered first contentful paint permits cached or later CSS',()=>{
 const cached=fixture({cached:true,painted:true});assert.equal(cached.link.media,'all');
 const late=fixture({painted:true});assert.equal(late.link.media,'print');late.loadCss();assert.equal(late.link.media,'all');
});
test('missing/broken paint observation uses post-load fallback, retaining eventual fonts',()=>{
 for(const options of [{support:false},{broken:true},{complete:true,support:false},{support:true}]){
  const f=fixture({...options,cached:true});assert.equal(f.link.media,'print');
  f.loadPage();f.timers();f.frames();f.frames();f.timers();assert.equal(f.link.media,'all');
 }
});
test('duplicate script and CSS load do not activate the stylesheet twice',()=>{
 const f=fixture({cached:true});f.run();f.paint();f.loadCss();f.loadPage();f.timers();f.frames();f.frames();assert.deepEqual(f.writes,['all']);
});
test('failed optional CSS and absent font links remain harmless',()=>{
 const failed=fixture();failed.paint();failed.loadPage();failed.timers();failed.frames();failed.frames();assert.equal(failed.link.media,'print');
 const absent=fixture({empty:true});absent.paint();absent.loadPage();absent.timers();absent.frames();assert.deepEqual(absent.writes,[]);
});
