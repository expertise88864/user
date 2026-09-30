// Authored-region document model. Article shell assembly lives in word-source.js.
import {parseFragment} from 'parse5';
import {Schema, DOMParser, DOMSerializer} from 'prosemirror-model';
import {EditorState, Plugin} from 'prosemirror-state';
import {EditorView} from 'prosemirror-view';
import {history, undo, redo,closeHistory} from 'prosemirror-history';
import {keymap} from 'prosemirror-keymap';
import {baseKeymap, toggleMark, setBlockType} from 'prosemirror-commands';
import {wrapInList} from 'prosemirror-schema-list';
import {articleRegion} from './word-source.js';
import {tableNodes, tableEditing} from 'prosemirror-tables';
import {prepareClipboardImages,verifyPreparedImages} from './word-media.js';

const supported = new Set(['p','h2','h3','h4','ul','ol','li','blockquote','div','section','span','strong','b','em','i','u','s','sup','sub','a','br','img','table','thead','tfoot','tbody','tr','td','th']);
function unsafeSourceAttributes(node) {
  return (node.attrs || []).some(({name,value}) => {
    // Keep active/ambiguous source opaque and byte-exact. It must not be
    // mounted in the authenticated editor just because its tag is supported.
    if (/^on|^data-pilot-/i.test(name) || ['background','srcdoc','srcset','ping','autofocus','contenteditable','is','action','formaction'].includes(name)) return true;
    if (name === 'style' && /\\|\/\*|(?:url|image(?:-set)?|cross-fade|paint|element|expression)\s*\(|@import|behavior\s*:|-moz-binding\s*:/i.test(value)) return true;
    if (!['href','src','xlink:href'].includes(name)) return false;
    if (/[\\\x00-\x20\x7f]/.test(value) || /^\/\//.test(value)) return true;
    const scheme = /^([a-z][a-z0-9+.-]*):/i.exec(value);
    if (!scheme) return false; // Relative article URLs and fragments.
    return !(name === 'src' ? /^https?$/i : /^(?:https?|mailto|tel)$/i).test(scheme[1]);
  });
}
const attributes = node => Object.fromEntries([...node.attributes].filter(a => !/^on/i.test(a.name)).map(a => [a.name,a.value]));
const shared = {attrs:{html:{default:{}}}};
const rule = tag => ({tag,getAttrs:dom=>({html:attributes(dom)})});
const output = tag => node => [tag,node.attrs.html,0];
const block = tag => ({...shared,group:'block',content:'inline*',parseDOM:[rule(tag)],toDOM:output(tag)});
const mark = tags => ({...shared,parseDOM:tags.map(rule),toDOM:output(tags[0])});
const nodes = {
  doc:{content:'block+'}, text:{group:'inline'},
  paragraph:block('p'), heading2:block('h2'), heading3:block('h3'), heading4:block('h4'),
  container:{attrs:{html:{default:{}},tag:{default:'div'}},group:'block',content:'block+',parseDOM:['div','section'].map(tag=>({tag,getAttrs:dom=>({html:attributes(dom),tag})})),toDOM:node=>[node.attrs.tag,node.attrs.html,0]},
  quote:{...shared,group:'block',content:'block+',parseDOM:[rule('blockquote')],toDOM:output('blockquote')},
  bullet_list:{...shared,group:'block',content:'list_item+',parseDOM:[rule('ul')],toDOM:output('ul')},
  ordered_list:{...shared,group:'block',content:'list_item+',parseDOM:[rule('ol')],toDOM:output('ol')},
  list_item:{...shared,content:'paragraph block*',parseDOM:[rule('li')],toDOM:output('li')},
  hard_break:{...shared,inline:true,group:'inline',selectable:false,parseDOM:[rule('br')],toDOM:node=>['br',node.attrs.html]},
  image:{...shared,inline:true,group:'inline',atom:true,draggable:true,parseDOM:[rule('img')],toDOM:node=>['img',node.attrs.html]},
  anchor:{attrs:{html:{default:{}},tag:{default:'span'}},inline:true,group:'inline',atom:true,selectable:false,
    parseDOM:['span[id]:empty','a[id]:not([href]):empty','a[name]:not([href]):empty'].map(tag=>({tag,priority:100,getAttrs:dom=>({html:attributes(dom),tag:dom.localName})})),
    toDOM:node=>[node.attrs.tag,node.attrs.html]},
  protected:{attrs:{key:{}},group:'block',atom:true,selectable:true,
    parseDOM:[{tag:'div[data-pilot-protected]',priority:100,getAttrs:dom=>({key:dom.dataset.pilotProtected})}],
    toDOM:node=>['div',{'data-pilot-protected':node.attrs.key,contenteditable:'false'},'受保護區塊']},
  protected_inline:{attrs:{key:{}},group:'inline',inline:true,atom:true,selectable:true,
    parseDOM:[{tag:'span[data-pilot-protected]',priority:100,getAttrs:dom=>({key:dom.dataset.pilotProtected})}],
    toDOM:node=>['span',{'data-pilot-protected':node.attrs.key,contenteditable:'false'},'受保護內容']},
  ...tableNodes({tableGroup:'block',cellContent:'block+'})
};
for (const name of ['table','table_row','table_cell','table_header']) {
  const spec=nodes[name], priorDOM=spec.toDOM;
  spec.attrs={...spec.attrs,html:{default:{}},...(name==='table_row'?{rowGroup:{default:'tbody'},rowGroupKey:{default:null},rowGroupHtml:{default:{}}}:{})};
  spec.parseDOM=spec.parseDOM.map(old=>({...old,getAttrs:dom=>{
    const parsed=old.getAttrs?old.getAttrs(dom):{};
    const parent=dom.parentElement,groupHtml=attributes(parent);delete groupHtml['data-pilot-row-group'];
    return {...parsed,html:attributes(dom),...(name==='table_row'?{rowGroup:['thead','tfoot'].includes(parent.localName)?parent.localName:'tbody',rowGroupKey:parent.dataset.pilotRowGroup||null,rowGroupHtml:['thead','tbody','tfoot'].includes(parent.localName)?groupHtml:{}}:{})};
  }}));
  spec.toDOM=node=>{const output=priorDOM(node);if(typeof output[1]==='object'&&!Array.isArray(output[1]))output[1]={...node.attrs.html,...output[1]};else output.splice(1,0,node.attrs.html);return output;};
}
const schema = new Schema({nodes,marks:{link:mark(['a']),strong:mark(['strong','b']),em:mark(['em','i']),underline:mark(['u']),strike:mark(['s']),sup:mark(['sup']),sub:mark(['sub']),span:mark(['span'])}});

function separateInlineAnchors(root) {
  // Inline marks may split at bold/italic boundaries. Keep the single target
  // in a dedicated empty anchor node rather than duplicating IDs on each mark.
  for(const element of [...root.querySelectorAll('a[id],a[name],span[id],strong[id],b[id],em[id],i[id],u[id],s[id],sup[id],sub[id]')]) {
    if(element.matches('[data-pilot-protected]'))continue;
    if(element.matches('span[id]:empty,a[id]:not([href]):empty,a[name]:not([href]):empty'))continue;
    for(const name of new Set([element.getAttribute('id'),element.localName==='a'?element.getAttribute('name'):null].filter(Boolean))) {
      const anchor=element.ownerDocument.createElement('span');anchor.id=name;element.before(anchor);
    }
    element.removeAttribute('id');element.removeAttribute('name');
  }
}

// Parse source locations, not DOM.outerHTML, so protected source bytes survive.
function protect(source) {
  const tree=parseFragment(source,{sourceCodeLocationInfo:true}), protectedSource=new Map(), ranges=[];
  function hasUnsupported(node) {return node.nodeName==='#comment'||!!(node.tagName&&(!supported.has(node.tagName)||unsafeSourceAttributes(node)||['thead','tbody','tfoot'].includes(node.tagName)&&!(node.childNodes||[]).some(child=>child.tagName==='tr')))||(node.childNodes||[]).some(hasUnsupported);}
  function visit(node, inline=false) {
    // Table/list children cannot be replaced by block divs without browser
    // foster-parenting or implicit list items. Protect the whole structure.
    if(node.tagName && ['table','ul','ol'].includes(node.tagName)&&hasUnsupported(node)) {
      const location=node.sourceCodeLocation,key='block-'+protectedSource.size;
      protectedSource.set(key,source.slice(location.startOffset,location.endOffset));
      ranges.push({start:location.startOffset,end:location.endOffset,key,tag:'div'});return;
    }
    if(node.nodeName==='#comment'||node.tagName&&(!supported.has(node.tagName)||unsafeSourceAttributes(node))) {
      const location=node.sourceCodeLocation;
      if(!location) throw Error('Unsupported block has no recoverable source location');
      const key='block-'+protectedSource.size;
      protectedSource.set(key,source.slice(location.startOffset,location.endOffset));
      ranges.push({start:location.startOffset,end:location.endOffset,key,tag:inline?'span':'div'});return;
    }
    // Interactive or translated blocks must remain opaque until supported.
    if(node.tagName && (node.attrs||[]).some(a=>a.name==='class'&&/dn-calc|calculator/.test(a.value))) {
      const location=node.sourceCodeLocation;
      if(!location) throw Error('Protected block lacks source location');
      const key='block-'+protectedSource.size;
      protectedSource.set(key,source.slice(location.startOffset,location.endOffset));
      ranges.push({start:location.startOffset,end:location.endOffset,key,tag:inline?'span':'div'});return;
    }
    const childInline=node.tagName&&['p','h2','h3','h4','span','strong','b','em','i','u','s','sup','sub','a','td','th'].includes(node.tagName);
    for(const child of node.childNodes||[]) visit(child,childInline);
  }
  visit(tree);
  let adapted=source;
  for(const range of ranges.sort((a,b)=>b.start-a.start)) adapted=adapted.slice(0,range.start)+'<'+range.tag+' data-pilot-protected="'+range.key+'"></'+range.tag+'>'+adapted.slice(range.end);
  return {adapted,protectedSource};
}
function keys(doc) { const found=[];doc.descendants(node=>{if(node.type.name.startsWith('protected'))found.push(node.attrs.key);});return found.sort(); }
function normalizePaste(html, doc, existingTargets=new Set(),imagePaths=new Set()) {
  const parsed=new globalThis.DOMParser().parseFromString(html,'text/html');
  if(parsed.querySelector('svg,iframe,object,embed,script,style,form,input,button')||[...parsed.querySelectorAll('img')].some(node=>!imagePaths.has(node.getAttribute('src')))) throw Error('貼上包含尚未支援區塊，原始剪貼簿保留；本次未插入。');
  if([...parsed.querySelectorAll('img[alt]')].some(node=>node.getAttribute('alt').length>300))throw Error('圖片替代文字超過上限，請保留說明後再整理；本次未插入。');
  const cells=[...parsed.body.querySelectorAll('td,th')];let occupied=0;
  for(const cell of cells){const dimensions=['rowspan','colspan'].map(name=>cell.getAttribute(name)||'1');if(dimensions.some(value=>!/^\d{1,3}$/.test(value)||Number(value)<1||Number(value)>100))throw Error('合併儲存格大小無法可靠整理，本次未插入。');occupied+=Number(dimensions[0])*Number(dimensions[1]);}
  if(occupied>10_000||parsed.body.querySelectorAll('tr').length>1024)throw Error('表格大小超過整理上限，本次未插入。');
  const prefix='word-paste-'+globalThis.crypto.getRandomValues(new Uint32Array(4)).join('-')+'-',targets=new Map(),owners=new Map();
  for(const element of parsed.body.querySelectorAll('[id],a[name]')) {
    const names=[element.getAttribute('id'),element.localName==='a'?element.getAttribute('name'):null].filter(value=>value!==null);
    for(const name of names) {
      if(!name||name.length>150||/[\s\x00-\x1f]/.test(name)||owners.has(name)&&owners.get(name)!==element)throw Error('文獻 anchor 重複或不明確，本次未插入；剪貼簿保留。');
      if(!targets.has(name)){targets.set(name,prefix+targets.size);owners.set(name,element);}
    }
    element.id=targets.get(names[0]);element.removeAttribute('name');
    if(names.length>1&&names[1]!==names[0]){const alias=parsed.createElement('span');alias.id=targets.get(names[1]);element.prepend(alias);}
  }
  for(const link of parsed.body.querySelectorAll('a[href^="#"]')) {
    const href=link.getAttribute('href');if(href==='#')continue;
    let target;try{target=decodeURIComponent(href.slice(1));}catch(_){throw Error('文獻連結格式不完整，本次未插入。');}
    if(targets.has(target))link.setAttribute('href','#'+targets.get(target));
    else if(!existingTargets.has(target))throw Error('請連同文獻／註脚一起貼上；本次未插入，剪貼簿保留。');
  }
  let lists=[];
  const safeHref=value=>!/[\\\x00-\x1f]/.test(value)&&(!/^mailto:/i.test(value)||!/%0[ad]/i.test(value))&&(/^(https?:\/\/|mailto:|#)/i.test(value)||/^\/(?!\/)/.test(value));
  for(const link of parsed.body.querySelectorAll('a[href]'))if(!safeHref(link.getAttribute('href')))throw Error('連結格式無法可靠整理，請保留來源後再修改；本次未插入。');
  for(const paragraph of [...parsed.body.children]) {
    const listStyle=paragraph.getAttribute('style')||'', match=/mso-list\s*:[^;]*\blevel(\d+)\b/i.exec(listStyle);
    if(paragraph.localName!=='p'||!match){lists=[];continue;}
    const level=Number(match[1]), label=[...paragraph.querySelectorAll('span')].find(span=>/mso-list\s*:\s*Ignore/i.test(span.getAttribute('style')||''));
    if(!label||level<1||level>8||level>lists.length+1)throw Error('Word 清單層級無法可靠辨識，本次未插入；剪貼簿保留。');
    const marker=label.textContent.trim(), ordered=/^(?:\d+|[a-zA-Z]+)[.)]$/.test(marker), kind=ordered?'ol':'ul';
    const numeral=/^(\d+)[.)]$/.exec(marker);
    if(level===1){if(!lists[0]||lists[0].kind!==kind){const list=parsed.createElement(kind);paragraph.before(list);lists=[{kind,list,last:null}];}}
    else if(!lists[level-1]||lists[level-1].kind!==kind){const parent=lists[level-2];if(!parent||!parent.last)throw Error('Word 清單缺少上一層項目，本次未插入。');const list=parsed.createElement(kind);parent.last.appendChild(list);lists.length=level-1;lists.push({kind,list,last:null});}
    lists.length=level;label.remove();
    const item=parsed.createElement('li');if(numeral)item.setAttribute('value',numeral[1]);
    lists[level-1].list.appendChild(item);item.appendChild(paragraph);lists[level-1].last=item;
  }
  for(const element of [...parsed.body.querySelectorAll('font,o\\:p')]){
    if(element.id){const anchor=parsed.createElement('span');anchor.id=element.id;element.before(anchor);}
    element.replaceWith(...element.childNodes);
  }
  for(const span of parsed.body.querySelectorAll('span[style]')) {
    const wrappers=[];
    if(span.style.fontWeight==='bold'||Number(span.style.fontWeight)>=600)wrappers.push('strong');
    if(span.style.fontStyle==='italic')wrappers.push('em');
    if(['super','sub'].includes(span.style.verticalAlign))wrappers.push(span.style.verticalAlign==='super'?'sup':'sub');
    if(span.style.textDecoration.includes('underline'))wrappers.push('u');
    for(const tag of wrappers){const node=parsed.createElement(tag);node.append(...span.childNodes);span.appendChild(node);}
  }
  separateInlineAnchors(parsed.body);
  for(const element of parsed.body.querySelectorAll('*')) {
    if(!supported.has(element.localName)) throw Error('貼上格式尚未支援：'+element.localName+'；本次未插入。');
    for(const attribute of [...element.attributes]) {
      if(element.localName==='a' && attribute.name==='href' && safeHref(attribute.value)) continue;
      if(attribute.name==='id'&&[...targets.values()].includes(attribute.value))continue;
      if(element.localName==='img'&&attribute.name==='src'&&imagePaths.has(attribute.value))continue;
      if(element.localName==='img'&&attribute.name==='alt'&&attribute.value.length<=300)continue;
      if(element.localName==='img'&&['width','height'].includes(attribute.name)&&/^\d+$/.test(attribute.value))continue;
      if(['td','th'].includes(element.localName)&&['colspan','rowspan'].includes(attribute.name)) continue;
      if(element.localName==='li'&&attribute.name==='value'&&/^\d+$/.test(attribute.value))continue;
      element.removeAttribute(attribute.name);
    }
  }
  for(const id of targets.values())if(![...parsed.body.querySelectorAll('[id]')].some(element=>element.id===id))throw Error('無法完整保留貼上的文獻 anchor，本次未插入；剪貼簿保留。');
  // Parse into a document without a browsing context; canonical draft image
  // paths must not cause a request before the asset is actually published.
  const host=parsed.createElement('div');host.append(...parsed.body.childNodes);return host;
}
export function createEditor(mount,source,options={}) {
  const doc=mount.ownerDocument, {adapted,protectedSource}=protect(source);
  const inert=new globalThis.DOMParser().parseFromString(adapted,'text/html'),host=inert.createElement('div');
  host.append(...inert.body.childNodes);
  separateInlineAnchors(host);
  // Compare annotations against the model's initial rendering, not differently
  // curated legacy data-zh strings. A private key survives model edits and is
  // always removed before serialization. Protected source is never traversed.
  [...host.querySelectorAll('[data-zh],[data-en]')].forEach((element,index)=>element.setAttribute('data-pilot-bilingual',String(index)));
  [...host.querySelectorAll('thead,tbody,tfoot')].forEach((element,index)=>element.setAttribute('data-pilot-row-group',String(index)));
  const initial=DOMParser.fromSchema(schema).parse(host,{preserveWhitespace:true}), originalKeys=keys(initial);
  const markerPrefix='pilot-source:'+globalThis.crypto.getRandomValues(new Uint32Array(4)).join('-')+':';
  function expand(html) {
    for(const [key,raw] of protectedSource)html=html.replace('<!--'+markerPrefix+key+'-->',()=>raw);
    return html;
  }
  function rendering(model) {
    const holder=inert.createElement('div');
    holder.appendChild(DOMSerializer.fromSchema(schema).serializeFragment(model.content,{document:inert}));
    // DOMSerializer assigns cssText, which normalizes author-provided styles.
    // Restore the raw style attribute without changing modeled cell spans.
    const styledTables=[];model.descendants(node=>{if(['table','table_row','table_cell','table_header'].includes(node.type.name))styledTables.push(node);});
    [...holder.querySelectorAll('table,tr,td,th')].forEach((element,index)=>{const html=styledTables[index]?.attrs.html;if(html&&Object.hasOwn(html,'style'))element.setAttribute('style',html.style);});
    const modeledTables=[];model.descendants(node=>{if(node.type.name==='table')modeledTables.push(node);});
    [...holder.querySelectorAll('table')].forEach((element,index)=>{
      const table=modeledTables[index],rows=[...element.querySelectorAll(':scope > tbody > tr')];
      let group=null,groupKey=null,groupHTML=null;
      table.forEach((row,offset,i)=>{
        const tag=row.attrs.rowGroup||'tbody',key=row.attrs.rowGroupKey,attrs=row.attrs.rowGroupHtml||{},signature=JSON.stringify(attrs);
        if(!group||group.localName!==tag||groupKey!==key||groupHTML!==signature){
          group=inert.createElement(tag);for(const[name,value]of Object.entries(attrs))group.setAttribute(name,value);
          element.appendChild(group);groupKey=key;groupHTML=signature;
        }
        group.appendChild(rows[i]);
      });
      for(const body of [...element.children])if(body.localName==='tbody'&&!body.children.length)body.remove();
    });
    const annotated=[...holder.querySelectorAll('[data-pilot-bilingual]')].map(element=>({element,key:element.getAttribute('data-pilot-bilingual')}));
    for(const {element} of annotated)element.removeAttribute('data-pilot-bilingual');
    for(const node of holder.querySelectorAll('[data-pilot-protected]')) {
      const key=node.dataset.pilotProtected;
      if(!protectedSource.has(key))throw Error('Protected block source missing');
      node.replaceWith(inert.createComment(markerPrefix+key));
    }
    return {holder,annotated};
  }
  const baseline=rendering(initial);
  const bilingualHTML=new Map(baseline.annotated.map(({element,key})=>[key,expand(element.innerHTML)]));
  const guard=new Plugin({filterTransaction(transaction,before){
    if(!transaction.docChanged)return true;
    if(options.editable?.()===false)return false;
    if(JSON.stringify(keys(transaction.doc))!==JSON.stringify(originalKeys))return false;
    let preserved=true;
    before.doc.descendants((node,pos)=>{if(node.type.name.startsWith('protected')){const mapped=transaction.mapping.mapResult(pos,1),after=transaction.doc.nodeAt(mapped.pos);if(mapped.deleted||!after||after.type!==node.type||after.attrs.key!==node.attrs.key)preserved=false;}});
    return preserved;
  }});
  let revision=0,pastePending=false,destroyed=false;
  const imageAssets=new Map();
  let state=EditorState.create({schema,doc:initial,plugins:[history(),guard,keymap({'Mod-z':undo,'Mod-y':redo,'Mod-Shift-z':redo}),keymap(baseKeymap),tableEditing()]});
  function blockDrop(view,event){event.preventDefault();mount.dataset.pasteError='請複製後貼上圖文，或使用圖片說明／排序；拖曳尚未套用，原稿保留。';return true;}
  const view=new EditorView(mount,{state,editable:()=>options.editable?.()!==false,attributes:{role:'textbox','aria-label':'中文文章編輯區','aria-multiline':'true'},dispatchTransaction(transaction){
    const before=state,applied=state.applyTransaction(transaction);
    if(!applied.transactions.length)return;
    try{view.updateState(applied.state);state=applied.state;if(!state.doc.eq(before.doc)||!state.selection.eq(before.selection))revision++;if(!state.doc.eq(before.doc)&&options.onChange){try{options.onChange();}catch(_){mount.dataset.notificationError='true';}}}
    catch(error){state=before;try{view.updateState(before);}catch(_){destroyed=true;mount.dataset.recoveryRequired='true';try{view.destroy();}catch(_){}for(const element of mount.querySelectorAll('[contenteditable]'))element.setAttribute('contenteditable','false');}throw error;}
  },
    handleDOMEvents:{drop:blockDrop,click(view,event){if(event.target.closest('a')){event.preventDefault();return true;}return false;},auxclick(view,event){if(event.target.closest('a')){event.preventDefault();return true;}return false;}},
    handleDrop:blockDrop,
    nodeViews:{...Object.fromEntries(['protected','protected_inline'].map(type=>[type,node=>{const el=doc.createElement(type==='protected'?'div':'span');el.dataset.pilotProtected=node.attrs.key;el.contentEditable='false';el.textContent='受保護區塊（SVG／互動內容／其他格式）';return {dom:el};}])),
      image:node=>{const el=doc.createElement('img');for(const[name,value]of Object.entries(node.attrs.html))if(name!=='src')el.setAttribute(name,value);el.src=imageAssets.get(node.attrs.html.src)?.url||options.imagePreview?.(node.attrs.html.src)||node.attrs.html.src;el.style.maxWidth='100%';el.style.height='auto';return {dom:el};}},
    handlePaste(view,event){try{if(view.composing)throw Error('中文輸入仍在選字，請完成或取消後貼上；剪貼簿保留。');const html=event.clipboardData.getData('text/html'),files=[...event.clipboardData.files];if(files.length||/<img\b/i.test(html)){pasteContent(html,files).catch(error=>mount.dataset.pasteError=error.message);return true;}if(!html)return false;const host=normalizePaste(html,doc,knownTargets());view.dispatch(view.state.tr.replaceSelection(DOMParser.fromSchema(schema).parseSlice(host)));return true;}catch(error){mount.dataset.pasteError=error.message;return true;}}
  });
  function knownTargets() {
    const result=new Set(),add=attrs=>{if(attrs&&attrs.id)result.add(attrs.id);if(attrs&&attrs.name)result.add(attrs.name);};
    view.state.doc.descendants(node=>{add(node.attrs.html);add(node.attrs.rowGroupHtml);for(const mark of node.marks)add(mark.attrs.html);});
    const visit=node=>{for(const attr of node.attrs||[])if(attr.name==='id'||node.tagName==='a'&&attr.name==='name')result.add(attr.value);for(const child of node.childNodes||[])visit(child);};
    for(const raw of protectedSource.values())visit(parseFragment(raw));
    return result;
  }
  async function pasteContent(html,files=[]) {
    if(pastePending||view.composing||destroyed||options.editable?.()===false)throw Error('圖片整理或中文選字尚未完成，請稍後再貼上；剪貼簿保留。');
    if(typeof options.prepareImages!=='function')throw Error('圖片準備介面尚未就緒，本次未插入；剪貼簿保留。');
    const snapshot={revision,selection:view.state.selection,context:options.contextKey?.()},existing=knownTargets();
    pastePending=true;mount.dataset.pasteState='preparing';
    try{
      const prepared=await prepareClipboardImages(html,files,options.file);
      const paths=new Set(prepared.images.map(item=>item.path)),host=normalizePaste(prepared.html,doc,existing,paths);
      const slice=DOMParser.fromSchema(schema).parseSlice(host);
      const result=await options.prepareImages(Object.freeze(prepared.images.map(item=>item.blob)));
      verifyPreparedImages(result,prepared.images);
      if(destroyed||view.composing||revision!==snapshot.revision||!view.state.selection.eq(snapshot.selection)||options.contextKey?.()!==snapshot.context)throw Error('整理期間文章、位置或版本已變更，本次未插入；剪貼簿保留。');
      const transaction=closeHistory(view.state.tr.replaceSelection(slice));
      if(JSON.stringify(keys(transaction.doc))!==JSON.stringify(originalKeys))throw Error('選取範圍包含受保護內容，本次未插入。');
      const oldImages=new Map(imageAssets),beforeState=state;
      try{result.commit();for(const item of prepared.images)imageAssets.set(item.path,item);view.dispatch(transaction);}
      catch(error){imageAssets.clear();for(const[path,item]of oldImages)imageAssets.set(path,item);state=beforeState;try{view.updateState(beforeState);}catch(_){destroyed=true;mount.dataset.recoveryRequired='true';try{view.destroy();}catch(_){}for(const element of mount.querySelectorAll('[contenteditable]'))element.setAttribute('contenteditable','false');}try{result.rollback();}catch(_){mount.dataset.recoveryRequired='true';throw Error('圖片操作未完成且暫存回復須再核對，文字與原剪貼簿保留。');}throw error;}
      mount.dataset.pasteError='';mount.dataset.pasteState='ready';
    }finally{pastePending=false;if(mount.dataset.pasteState==='preparing')mount.dataset.pasteState='failed';}
  }
  return {
    view, protectedSource,
    status(){return {pastePending,composing:view.composing,destroyed,revision};},
    command(name){
      if(destroyed||pastePending||view.composing||options.editable?.()===false)throw Error('編輯器尚未就緒，請完成目前操作。');
      const commands={bold:toggleMark(schema.marks.strong),italic:toggleMark(schema.marks.em),underline:toggleMark(schema.marks.underline),strike:toggleMark(schema.marks.strike),superscript:toggleMark(schema.marks.sup),subscript:toggleMark(schema.marks.sub),paragraph:setBlockType(schema.nodes.paragraph),h2:setBlockType(schema.nodes.heading2),h3:setBlockType(schema.nodes.heading3),h4:setBlockType(schema.nodes.heading4),bullet:wrapInList(schema.nodes.bullet_list),ordered:wrapInList(schema.nodes.ordered_list),undo,redo};
      const command=commands[name];if(!command)throw Error('這項格式目前尚未支援，請使用原始碼模式。');
      const result=command(view.state,view.dispatch.bind(view),view);view.focus();return result;
    },
    serialize(){
      if(view.composing)throw Error('中文輸入仍在選字，暫緩保存快照；請完成或取消輸入。');
      if(pastePending)throw Error('圖片仍在整理，暫緩保存快照；編輯內容保留。');
      if(state.doc.eq(initial)) return source;
      const {holder,annotated}=rendering(state.doc);
      // Process descendants first so ancestor Chinese HTML never embeds stale
      // translations of a child that changed in the same transaction.
      for(const {element,key} of annotated.reverse()) {
        const html=expand(element.innerHTML);
        if(html===bilingualHTML.get(key))continue;
        element.removeAttribute('data-en');
        element.setAttribute('data-zh',html);
        element.setAttribute('data-translation-pending','true');
      }
      return expand(holder.innerHTML);
    },
    insert(text){view.dispatch(view.state.tr.insertText(text));},
    undo(){return undo(view.state,view.dispatch.bind(view));}, redo(){return redo(view.state,view.dispatch.bind(view));},
    pasteHTML(html){if(view.composing)throw Error('中文輸入仍在選字，請完成或取消後貼上。');const holder=normalizePaste(html,doc,knownTargets());view.dispatch(view.state.tr.replaceSelection(DOMParser.fromSchema(schema).parseSlice(holder)));},
    pasteContent,
    images(){const found=[];view.state.doc.descendants(node=>{if(node.type.name==='image')found.push({...node.attrs.html});});return found;},
    imageIssues(){const issues=[];let index=0;view.state.doc.descendants(node=>{if(node.type.name==='image'){if(!(node.attrs.html.alt||'').trim())issues.push({index,code:'missing_alt'});index++;}});return issues;},
    setImageAlt(index,alt){if(typeof alt!=='string'||alt.length>300)throw Error('圖片替代文字太長或格式不符。');let count=0,found;view.state.doc.descendants((node,pos)=>{if(node.type.name==='image'&&count++===index)found={node,pos};});if(!found)throw Error('找不到圖片。');view.dispatch(view.state.tr.setNodeMarkup(found.pos,null,{html:{...found.node.attrs.html,alt}}));},
    moveImage(index,target){const images=[];view.state.doc.descendants((node,pos)=>{if(node.type.name==='image')images.push({node,pos});});if(!images[index]||!images[target])throw Error('圖片位置不明確。');if(index===target)return;const from=images[index],to=images[target],tr=view.state.tr.delete(from.pos,from.pos+from.node.nodeSize);tr.insert(tr.mapping.map(to.pos+(index<target?to.node.nodeSize:0)),from.node);view.dispatch(tr);},
    destroy(){destroyed=true;view.destroy();}
  };
}
window.DNWordModel={createEditor,articleRegion};
