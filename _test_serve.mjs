import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn,spawnSync,execFileSync} from 'node:child_process';
import {request} from 'node:https';
import {readFileSync,mkdtempSync,realpathSync,rmSync} from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {gunzipSync} from 'node:zlib';

test('actual static server negotiates production-like compression without changing content', {timeout:30000}, async () => {
  // Production uses TLS. A dedicated local CA keeps byte-exact compression
  // assertions independent of HTTP filtering, without disabling TLS checks or
  // modifying the user's OS trust store, proxy or security configuration.
  const temporary=mkdtempSync(path.join(os.tmpdir(),'chenderm-serve-test-'));
  const cert=path.join(temporary,'localhost-cert.pem'),key=path.join(temporary,'localhost-key.pem');
  let child;
  try {
    const candidates=['openssl'];
    if(process.platform==='win32'){
      const gitExecPath=execFileSync('git',['--exec-path'],{encoding:'utf8'}).trim();
      candidates.push(path.resolve(gitExecPath,'../../../usr/bin/openssl.exe'));
    }
    const openssl=candidates.find(binary=>spawnSync(binary,['version'],{stdio:'pipe'}).status===0);
    assert.ok(openssl,'OpenSSL is required for the isolated loopback TLS fixture');
    const generated=spawnSync(openssl,['req','-x509','-newkey','rsa:2048','-nodes','-keyout',key,'-out',cert,'-days','1','-subj','/CN=localhost','-addext','subjectAltName=IP:127.0.0.1,DNS:localhost'],{stdio:'pipe'});
    assert.equal(generated.status,0,'The isolated test certificate must be created successfully');
    const ca=readFileSync(cert);
    child=spawn(process.execPath,['_serve.mjs','--host','127.0.0.1','--port','0','--tls-cert',cert,'--tls-key',key],{stdio:['ignore','pipe','pipe']});
  let errors='';child.stderr.on('data',data=>{errors+=data;});
    const origin=await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(Error('Server startup timed out: '+errors)),10000);
      let output='';
      child.stdout.on('data',data=>{output+=data;const match=output.match(/https?:\/\/127\.0\.0\.1:\d+/);if(match){clearTimeout(timer);resolve(match[0]);}});
      child.once('error',error=>{clearTimeout(timer);reject(error);});
      child.once('exit',code=>{clearTimeout(timer);reject(Error('Server exited '+code+': '+errors));});
    });
    const get=(route,encoding,method='GET')=>new Promise((resolve,reject)=>{
      const req=request(origin+route,{method,ca,headers:encoding===null?{}:{'Accept-Encoding':encoding}},res=>{
        const chunks=[];res.on('data',data=>chunks.push(data));res.on('end',()=>resolve({status:res.statusCode,headers:res.headers,body:Buffer.concat(chunks)}));res.on('error',reject);
      });req.on('error',reject);req.setTimeout(5000,()=>req.destroy(Error('Loopback TLS request timed out')));req.end();
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
    if(child?.pid&&child.exitCode===null&&child.signalCode===null){const exited=new Promise(resolve=>child.once('exit',resolve));child.kill();await exited;}
    assert.equal(realpathSync(path.dirname(temporary)),realpathSync(os.tmpdir()),'Only remove the exact owned system-temp fixture');
    assert.ok(path.basename(temporary).startsWith('chenderm-serve-test-'));
    rmSync(temporary,{recursive:true,force:true});
  }
});
