const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function fixture(lang='zh-Hant',legacyMedia=false) {
  const handlers={}, elements={}, doc={documentElement:{lang,getAttribute:()=>null,setAttribute(){}},activeElement:null};
  function element(id,parent=null,tag='button') {
    const classes=new Set(),attrs={},listeners={};
    const el={id,parent,tag,textContent:'',attrs,listeners,
      classList:{contains:key=>classes.has(key),remove:(...keys)=>keys.forEach(k=>classes.delete(k)),
        toggle:(key,on)=>{const next=on===undefined?!classes.has(key):on;next?classes.add(key):classes.delete(key);return next;}},
      setAttribute:(key,value)=>attrs[key]=value,getAttribute:key=>attrs[key]??null,
      addEventListener:(name,fn)=>listeners[name]=fn,
      contains:target=>{while(target){if(target===el)return true;target=target.parent;}return false;},
      focus:()=>{doc.activeElement=el;},closest:selector=>{let node=el;while(node){if(node.tag===selector)return node;node=node.parent;}return null;}};
    elements[id]=el; return el;
  }
  const header=element('header',null,'header'),nav=element('nav',header),burger=element('dn-nav-burger',header),link=element('link',nav,'a');
  const search=element('dn-nav-search',nav),theme=element('dn-nav-theme',nav),outside=element('outside');
  nav.querySelector=()=>link;
  doc.querySelector=()=>nav;doc.getElementById=id=>elements[id]||null;
  doc.addEventListener=(name,fn)=>handlers[name]=fn;
  const media={matches:true,addEventListener:(name,fn)=>media.change=fn};
  if(legacyMedia){delete media.addEventListener;media.addListener=fn=>media.change=fn;}
  let searches=0;
  vm.runInNewContext(fs.readFileSync('assets/inline/nav-burger.js','utf8'),{
    document:doc,window:{matchMedia:query=>query.includes('max-width')?media:{matches:false},DN:{openSearch:()=>searches++}},
    matchMedia:()=>({matches:false}),localStorage:{getItem:()=>null,setItem(){}},KeyboardEvent:function(){},
  });
  return {header,nav,burger,link,search,theme,outside,doc,media,handlers,
    open:()=>burger.listeners.click(),isOpen:()=>nav.classList.contains('open'),searches:()=>searches};
}
for(const [lang,open,close] of [['zh-Hant','開啟選單','關閉選單'],['en','Open menu','Close menu']]) {
  test(`mobile disclosure exposes state and Escape returns focus (${lang})`,()=>{
    const h=fixture(lang);assert.equal(h.burger.attrs['aria-label'],open);
    assert.equal(h.burger.attrs['aria-controls'],h.nav.id);
    h.open();assert.equal(h.isOpen(),true);assert.equal(h.burger.attrs['aria-expanded'],'true');
    assert.equal(h.header.classList.contains('dn-nav-expanded'),true);
    assert.equal(h.burger.attrs['aria-label'],close);assert.equal(h.doc.activeElement,h.link);
    let prevented=false;h.handlers.keydown({key:'Escape',preventDefault(){prevented=true;}});
    assert.equal(prevented,true);assert.equal(h.isOpen(),false);assert.equal(h.doc.activeElement,h.burger);
    assert.equal(h.header.classList.contains('dn-nav-expanded'),false);
    assert.equal(h.burger.attrs['aria-label'],open);
  });
}
test('outside pointer/focus and followed links close the disclosure',()=>{
  const h=fixture();h.open();h.handlers.click({target:h.link});assert.equal(h.isOpen(),true);
  h.handlers.click({target:h.outside});assert.equal(h.isOpen(),false);
  h.open();h.handlers.focusin({target:h.outside});assert.equal(h.isOpen(),false);
  h.open();h.nav.listeners.click({target:h.link});assert.equal(h.isOpen(),false);
});
test('breakpoint changes reset state and never leave desktop links focused while hidden',()=>{
  const h=fixture();h.open();h.media.matches=false;h.media.change();assert.equal(h.isOpen(),false);
  h.doc.activeElement=h.link;h.media.matches=true;h.media.change();assert.equal(h.doc.activeElement,h.burger);
  assert.equal(h.burger.attrs['aria-expanded'],'false');
});
test('search closes the menu before opening its own dialog',()=>{
  const h=fixture();h.open();h.search.listeners.click();assert.equal(h.isOpen(),false);assert.equal(h.searches(),1);
  h.open();h.handlers.keydown({key:'k',ctrlKey:true});assert.equal(h.isOpen(),false);
});
test('legacy media listeners keep resizing, search and theme controls wired',()=>{
  const h=fixture('en',true);h.open();h.media.matches=false;h.media.change();assert.equal(h.isOpen(),false);
  h.search.listeners.click();assert.equal(h.searches(),1);
  assert.equal(typeof h.theme.listeners.click,'function');
});
