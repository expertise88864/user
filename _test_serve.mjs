import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {request} from 'node:http';
import {readFileSync} from 'node:fs';
import {gunzipSync} from 'node:zlib';

test('actual static server negotiates production-like compression without changing content', async () => {
  const child=spawn(process.execPath,['_serve.mjs','--port','0'],{stdio:['ignore','pipe','pipe']});
  let errors='';child.stderr.on('data',data=>{errors+=data;});
  try {
    const origin=await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(Error('Server startup timed out: '+errors)),10000);
      let output='';
      child.stdout.on('data',data=>{output+=data;const match=output.match(/https?:\/\/127\.0\.0\.1:\d+/);if(match){clearTimeout(timer);resolve(match[0]);}});
      child.once('error',error=>{clearTimeout(timer);reject(error);});
      child.once('exit',code=>{clearTimeout(timer);reject(Error('Server exited '+code+': '+errors));});
    });
    const get=(route,encoding,method='GET')=>new Promise((resolve,reject)=>{
      const req=request(origin+route,{method,headers:encoding===null?{}:{'Accept-Encoding':encoding}},res=>{
        const chunks=[];res.on('data',data=>chunks.push(data));res.on('end',()=>resolve({status:res.statusCode,headers:res.headers,body:Buffer.concat(chunks)}));res.on('error',reject);
      });req.on('error',reject);req.end();
    });
    for (const [route,file] of [['/','index.html'],['/blog','blog/index.html'],['/blog/blog-shared.min.js?v=test','blog/blog-shared.min.js'],['/assets/tw-mini.css','assets/tw-mini.css']]) {
      const raw=readFileSync(file),compressed=await get(route,'gzip, deflate, br');
      assert.equal(compressed.status,200);assert.equal(compressed.headers['content-encoding'],'gzip');
      assert.equal(compressed.headers.vary,'Accept-Encoding');assert.deepEqual(gunzipSync(compressed.body),raw);
      assert.ok(compressed.body.length<raw.length);
      const head=await get(route,'gzip','HEAD');assert.equal(head.headers['content-encoding'],'gzip');assert.equal(head.body.length,0);
    }
    for (const encoding of [null,'identity','br','gzip;q=0','gzip;q=0, *;q=1','gzip;q=0.5, identity;q=1','gzip;q=invalid']) {
      const r=await get('/',encoding);assert.equal(r.status,200);assert.equal(r.headers['content-encoding'],undefined);assert.deepEqual(r.body,readFileSync('index.html'));
    }
    const wildcard=await get('/','*;q=1');assert.equal(wildcard.headers['content-encoding'],'gzip');
    const preferred=await get('/','gzip;q=0.5, identity;q=0');assert.equal(preferred.headers['content-encoding'],'gzip');
    const spaced=await get('/','gzip ; q=1, identity;q=0');assert.equal(spaced.status,200);assert.equal(spaced.headers['content-encoding'],'gzip');assert.deepEqual(gunzipSync(spaced.body),readFileSync('index.html'));
    assert.equal((await get('/','gzip;q=0, identity;q=0')).status,406);
    const image=await get('/icon-192.png','gzip');assert.equal(image.status,200);assert.equal(image.headers['content-encoding'],undefined);assert.deepEqual(image.body,readFileSync('icon-192.png'));
    assert.equal((await get('/missing-server-fixture','gzip')).status,404);
    assert.equal((await get('/','gzip','POST')).status,405);
  } finally {
    if(child.exitCode===null){const exited=new Promise(resolve=>child.once('exit',resolve));child.kill();await exited;}
  }
});
