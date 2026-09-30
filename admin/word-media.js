// Prepare clipboard bytes locally. No uploads, HTTP fetches or file-system reads.
const formats={'image/png':'png','image/jpeg':'jpg','image/webp':'webp','image/gif':'gif'};
const sha=bytes=>crypto.subtle.digest('SHA-256',bytes).then(value=>[...new Uint8Array(value)].map(byte=>byte.toString(16).padStart(2,'0')).join(''));
function magic(bytes,type) {
 const starts=values=>values.every((value,index)=>bytes[index]===value),ascii=(offset,value)=>[...value].every((char,index)=>bytes[offset+index]===char.charCodeAt(0));
 return bytes.length>=8&&(type==='image/png'&&starts([137,80,78,71,13,10,26,10])||type==='image/jpeg'&&starts([255,216,255])||type==='image/gif'&&(ascii(0,'GIF87a')||ascii(0,'GIF89a'))||type==='image/webp'&&ascii(0,'RIFF')&&ascii(8,'WEBP'));
}
function dataBlob(url) {
 const match=/^data:(image\/(?:png|jpeg|webp|gif));base64,([A-Za-z0-9+/]*={0,2})$/.exec(url);
 if(!match||match[2].length>1_900_000)throw Error('圖片資料不完整或過大，本次未插入；剪貼簿保留。');
 const value=atob(match[2]),bytes=Uint8Array.from(value,char=>char.charCodeAt(0));
 return new Blob([bytes],{type:match[1]});
}
async function image(blob,file) {
 const ext=formats[blob.type];
 if(!ext||blob.size>1_400_000||blob.size<8)throw Error('圖片格式或大小不支援，本次未插入；剪貼簿保留。');
 const bytes=new Uint8Array(await blob.arrayBuffer());
 if(!magic(bytes,blob.type))throw Error('圖片格式與內容不符，本次未插入；剪貼簿保留。');
 let bitmap,width,height;try{bitmap=await createImageBitmap(blob);width=bitmap.width;height=bitmap.height;if(!width||!height||width*height>30_000_000)throw Error('dimensions');}
 catch(_){throw Error('圖片無法解碼，本次未插入；剪貼簿保留。');}finally{if(bitmap)bitmap.close();}
 const digest=await sha(bytes);let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
 return {blob,path:'/blog/images/'+file.slice(5,-5)+'/'+digest+'.'+ext,url:'data:'+blob.type+';base64,'+btoa(binary),encoded:Math.ceil(bytes.length/3)*4,width,height};
}
export async function prepareClipboardImages(html,files,file) {
 if(!/^blog\/(?!index\.html$|topics\.html$|charts\.html$)[a-z0-9]+(?:-[a-z0-9]+)*\.html$/.test(file||'')||file.slice(5,-5).length>100||new TextEncoder().encode(html).length>3_500_000||files.length>16)throw Error('圖片貼上範圍或大小不支援，本次未插入。');
 const parsed=new DOMParser().parseFromString(html,'text/html'),nodes=[...parsed.body.querySelectorAll('img')];
 if(nodes.length>16)throw Error('一次最多整理 16 張圖片，本次未插入。');
 const unique=new Map(),fileItems=await Promise.all(files.map(blob=>image(blob,file))),used=new Set();
 const keep=item=>{if(!unique.has(item.path))unique.set(item.path,item);return unique.get(item.path);};
 if(!nodes.length){
  for(const item of fileItems){keep(item);const paragraph=parsed.createElement('p'),img=parsed.createElement('img');img.src=item.path;img.alt='';img.width=item.width;img.height=item.height;paragraph.appendChild(img);parsed.body.appendChild(paragraph);}
 }else for(const node of nodes){
  const src=node.getAttribute('src')||'';let item;
  if(src.startsWith('data:'))item=await image(dataBlob(src),file);
  else{
   let name;try{name=decodeURIComponent(src.replace(/^cid:/,'').split(/[\\/]/).pop().split(/[?#]/)[0]);}catch(_){throw Error('圖片檔名無法可靠對照，本次未插入。');}
   const matches=files.map((blob,index)=>({blob,index})).filter(value=>value.blob.name===name);
   if(matches.length!==1)throw Error('剪貼簿缺少可對照的圖片資料，請一併複製圖片或單獨加入；本次未插入。');
   used.add(matches[0].index);item=fileItems[matches[0].index];
  }
  keep(item);node.setAttribute('src',item.path);node.setAttribute('width',String(item.width));node.setAttribute('height',String(item.height));
 }
 for(let index=0;index<fileItems.length;index++)if(nodes.length&&!used.has(index)&&!unique.has(fileItems[index].path))throw Error('圖片與圖文排版無法完整對照，本次未插入；剪貼簿保留。');
 if([...unique.values()].reduce((sum,item)=>sum+item.encoded,0)>1_900_000)throw Error('整批圖片超過草稿上限，本次未插入；剪貼簿保留。');
 return {html:parsed.body.innerHTML,images:[...unique.values()]};
}
export function verifyPreparedImages(result,expected) {
 if(!result||!Array.isArray(result.images)||result.images.length!==expected.length||typeof result.commit!=='function'||typeof result.rollback!=='function')throw Error('圖片準備結果無法核對，本次未插入。');
 for(let i=0;i<expected.length;i++)if(result.images[i].path!==expected[i].path||result.images[i].url!==expected[i].url)throw Error('圖片準備版本不一致，本次未插入。');
}
