const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('blog/blog-shared.js','utf8').replace("import('/pagefind/pagefind.js')",'Promise.resolve(window.testPagefind)');
const tick=()=>new Promise(r=>setImmediate(r));
function setup(en,search,fulltext=[]){
 const handlers={},classes=new Set(),input={value:'',focus(){},addEventListener:(name,fn)=>handlers[name]=fn},results={innerHTML:'',querySelectorAll(){return[]}};
 const overlay={classList:{add:c=>classes.add(c),remove:c=>classes.delete(c),contains:c=>classes.has(c)},querySelector:s=>s==='#dn-cmdk-input'?input:results,addEventListener(){}};
 const document={getElementById(){return null},createElement:t=>t==='style'?{}:overlay,head:{appendChild(){}},body:{appendChild(){}},addEventListener(){},querySelectorAll(){return[]},querySelector(){return null}};
 const window={testPagefind:{search}};
 vm.runInNewContext(source,{window,document,location:{pathname:en?'/en/blog/acne':'/blog/acne'},fetch:()=>Promise.resolve({ok:true,json:async()=>fulltext})});
 const dn=window.DN;dn.detectLang=()=>en?'en':'zh';dn.ARTICLES=[{slug:'acne',title:'痘痘',title_en:'Acne guide',tag:'痘痘',tag_en:'Acne'},{slug:'eczema',title:'濕疹',title_en:'Eczema guide'}];dn.initCmdK();
 return {dn,input,results,query(value){input.value=value;handlers.input();}};
}
test('English initial suggestions and failed query fallback preserve English routes',async()=>{
 const x=setup(true,()=>Promise.reject(Error('offline')));x.dn.openSearch();await tick();
 assert.match(x.results.innerHTML,/Acne guide/);assert.match(x.results.innerHTML,/\/en\/blog\/acne/);
 x.input.value='Acne';x.dn.closeSearch();x.dn.openSearch();x.input.value='Acne';await tick();await tick();
 assert.match(x.results.innerHTML,/Acne guide/);assert.doesNotMatch(x.results.innerHTML,/Eczema guide/);
});
test('failed result chunks fall back to searchable catalog',async()=>{
 const x=setup(false,()=>Promise.resolve({results:[{data:()=>Promise.reject(Error('chunk'))}]}));x.dn.openSearch();x.input.value='eczema';await tick();await tick();
 assert.match(x.results.innerHTML,/濕疹/);assert.doesNotMatch(x.results.innerHTML,/痘痘/);
});
test('synchronous search exceptions use the same fallback',async()=>{
 const x=setup(true,()=>{throw Error('sync')});x.dn.openSearch();x.input.value='glossary';await tick();await tick();
 assert.match(x.results.innerHTML,/Medical glossary/);assert.match(x.results.innerHTML,/\/en\/glossary/);
});
test('late response from closed search cannot replace reopened same query',async()=>{
 const pending=[];const x=setup(true,()=>new Promise(resolve=>pending.push(resolve)));
 x.dn.openSearch();x.input.value='acne';await tick();
 x.dn.closeSearch();x.dn.openSearch();x.input.value='acne';await tick();
 const latest=pending.at(-1);latest({results:[{data:async()=>({url:'/en/blog/acne',meta:{title:'Current'},excerpt:''})}]});await tick();
 for(const resolve of pending.slice(0,-1))resolve({results:[{data:async()=>({url:'/en/blog/acne',meta:{title:'Stale'},excerpt:''})}]});await tick();
 assert.match(x.results.innerHTML,/Current/);assert.doesNotMatch(x.results.innerHTML,/Stale/);
});


for(const en of [false,true]){
 test(`unavailable Pagefind handles fullwidth and reordered whole query words (${en?'en':'zh'})`,async()=>{
  const x=setup(en,()=>Promise.reject(Error('blocked')));x.dn.openSearch();await tick();
  for(const query of ['Ａｃｎｅ　guide','guide\tACNE',' Acne\u00a0guide ']){
   x.query(query);await tick();await tick();
   assert.match(x.results.innerHTML,new RegExp((en?'/en':'')+'/blog/acne'));
   assert.doesNotMatch(x.results.innerHTML,/\/blog\/eczema/);
  }
  x.query('Ａｃｎｅ　unfindabletoken');await tick();await tick();
  assert.doesNotMatch(x.results.innerHTML,/class="row/);
 });
 test(`fulltext fallback normalizes indexed Unicode as well as input (${en?'en':'zh'})`,async()=>{
  const x=setup(en,()=>Promise.reject(Error('blocked')),[{slug:'eczema',h:['Ｆｉｘｔｕｒｅ　ｈｅａｄｉｎｇ'],snippet:'Unicode index fixture'}]);
  x.dn.openSearch();await tick();await tick();x.query('fixture heading');await tick();await tick();
  assert.match(x.results.innerHTML,new RegExp((en?'/en':'')+'/blog/eczema'));
  assert.doesNotMatch(x.results.innerHTML,/\/blog\/acne/);
 });
}
test('normalized Pagefind query remains fresh through asynchronous search and data',async()=>{
 const queries=[];
 const x=setup(true,async query=>{queries.push(query);return {results:[{data:async()=>({url:'/en/blog/acne',meta:{title:'Current normalized result'},excerpt:''})}]};});
 x.dn.openSearch();await tick();x.query('Ａｃｎｅ　guide');await tick();await tick();
 assert.equal(queries.at(-1),'acne guide');
 assert.match(x.results.innerHTML,/Current normalized result/);
});
test('older result data cannot replace a newer normalized query',async()=>{
 let oldData;
 const x=setup(true,async query=>({results:[{data:query==='acne guide'?()=>new Promise(resolve=>oldData=resolve):async()=>({url:'/en/blog/eczema',meta:{title:'Newest result'},excerpt:''})}]}));
 x.dn.openSearch();await tick();x.query('Ａｃｎｅ　guide');await tick();await tick();
 x.query('Ｅｃｚｅｍａ');await tick();await tick();
 assert.match(x.results.innerHTML,/Newest result/);
 assert.equal(typeof oldData,'function');
 oldData({url:'/en/blog/acne',meta:{title:'Stale data'},excerpt:''});await tick();await tick();
 assert.match(x.results.innerHTML,/Newest result/);assert.doesNotMatch(x.results.innerHTML,/Stale data/);
});
