const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('blog/blog-shared.js','utf8').replace("import('/pagefind/pagefind.js')",'Promise.resolve(window.testPagefind)');
const tick=()=>new Promise(r=>setImmediate(r));
function setup(en,search){
 const classes=new Set(),input={value:'',focus(){},addEventListener(){}},results={innerHTML:'',querySelectorAll(){return[]}};
 const overlay={classList:{add:c=>classes.add(c),remove:c=>classes.delete(c),contains:c=>classes.has(c)},querySelector:s=>s==='#dn-cmdk-input'?input:results,addEventListener(){}};
 const document={getElementById(){return null},createElement:t=>t==='style'?{}:overlay,head:{appendChild(){}},body:{appendChild(){}},addEventListener(){},querySelectorAll(){return[]},querySelector(){return null}};
 const window={testPagefind:{search}};
 vm.runInNewContext(source,{window,document,location:{pathname:en?'/en/blog/acne':'/blog/acne'},fetch:()=>Promise.resolve({ok:false})});
 const dn=window.DN;dn.detectLang=()=>en?'en':'zh';dn.ARTICLES=[{slug:'acne',title:'痘痘',title_en:'Acne guide',tag:'痘痘',tag_en:'Acne'},{slug:'eczema',title:'濕疹',title_en:'Eczema guide'}];dn.initCmdK();
 return {dn,input,results};
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
