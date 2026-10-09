import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn,spawnSync,execFileSync} from 'node:child_process';
import {request} from 'node:https';
import {request as plainRequest} from 'node:http';
import {readFileSync,writeFileSync,mkdirSync,copyFileSync,mkdtempSync,realpathSync,rmSync,symlinkSync,unlinkSync} from 'node:fs';
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

for (const aliasedRoot of [false, true]) {
test(`local preview serves public routes while private files and aliases stay unavailable (aliased root: ${aliasedRoot})`, {timeout:30000}, async () => {
  const temporary=mkdtempSync(path.join(os.tmpdir(),'chenderm-serve-private-'));
  const site=path.join(temporary,'site'),outside=path.join(temporary,'outside');
  const links=[];
  let child, rootAlias;
  try {
  mkdirSync(site);mkdirSync(outside);
  copyFileSync('_serve.mjs',path.join(site,'_serve.mjs'));
  const fixture=(name,body)=>{const target=path.join(site,name);mkdirSync(path.dirname(target),{recursive:true});writeFileSync(target,body);};
  const privateFiles=['.git/config','.codex-review/report.txt','.env','.env.local',
    '_delivery_policy.json','api/admin/example.js','tools/codex_review.sh',
    'node_modules/example/index.js','delivery-preview/report.html',
    'local.pem','local.key','google-credentials.json','x-service-account-key.json',
    'PIPELINE.md','package.json','package-lock.json','vercel.json','middleware.js',
    'astro-rewrite/source.js','data/private.json','styles/config.ini','unpublished.html',
    'plausible-verification-key.txt'];
  for(const name of privateFiles)fixture(name,'ISOLATED_PRIVATE_MARKER');
  const publicFiles=new Map([['index.html','PUBLIC_HOME'],['tools.html','PUBLIC_TOOLS'],
    ['blog/index.html','PUBLIC_BLOG'],['assets/public.svg','PUBLIC_SVG'],
    ['admin/word-editor.js','PUBLIC_EDITOR'],['.well-known/ai.txt','PUBLIC_AI_POLICY'],
    ['en/index.html','PUBLIC_EN'],['ai/faq.json','PUBLIC_AI'],['pagefind/wasm.en.pagefind','PUBLIC_SEARCH'],
    ['robots.txt','PUBLIC_ROBOTS'],['sitemap.xml','PUBLIC_SITEMAP'],['llms.txt','PUBLIC_LLM'],
    ['llms-full.txt','PUBLIC_LLM_FULL'],['manifest.json','PUBLIC_MANIFEST'],['sw.js','PUBLIC_SW'],
    ['icon-192.png','PUBLIC_ICON'],['public-fixture-indexnow-key.txt','public-fixture-indexnow-key\n']]);
  for(const [name,body] of publicFiles)fixture(name,body);
  writeFileSync(path.join(outside,'private.txt'),'ISOLATED_OUTSIDE_MARKER');
  // Junctions on Windows avoid requiring symlink privileges or OS changes.
  const linkKind=process.platform==='win32'?'junction':'dir';
  if(aliasedRoot){
    const link=path.join(temporary,'site-alias');
    symlinkSync(site,link,linkKind);rootAlias=link;
  }
  for(const [target,name] of [[outside,'outside-alias'],[path.join(site,'.git'),'private-alias'],
    [outside,'assets/outside-alias'],[path.join(site,'.git'),'assets/private-alias']]) {
    const link=path.join(site,name);symlinkSync(target,link,linkKind);links.push(link);
  }
    child=spawn(process.execPath,[...(aliasedRoot?['--preserve-symlinks-main']:[]),path.join(rootAlias||site,'_serve.mjs'),'--host','127.0.0.1','--port','0'],{cwd:site,stdio:['ignore','pipe','pipe']});
    const origin=await new Promise((resolve,reject)=>{
      let output='';const timer=setTimeout(()=>reject(Error('Private fixture startup timed out')),10000);
      child.stdout.on('data',data=>{output+=data;const match=output.match(/http:\/\/127\.0\.0\.1:\d+/);if(match){clearTimeout(timer);resolve(match[0]);}});
      child.once('error',error=>{clearTimeout(timer);reject(error);});
      child.once('exit',code=>{clearTimeout(timer);reject(Error('Private fixture exited '+code));});
    });
    // Direct loopback transport has no configured proxy or third-party collector.
    const get=(route,method='GET')=>new Promise((resolve,reject)=>{
      const req=plainRequest(origin+route,{method},res=>{const chunks=[];res.on('data',d=>chunks.push(d));res.on('end',()=>resolve({status:res.statusCode,body:Buffer.concat(chunks).toString()}));res.on('error',reject);});
      req.on('error',reject);req.setTimeout(5000,()=>req.destroy(Error('Private fixture request timeout')));req.end();
    });
    for(const name of privateFiles){for(const method of ['GET','HEAD']){const response=await get('/'+name,method);assert.equal(response.status,404,name);assert.doesNotMatch(response.body,/ISOLATED_PRIVATE_MARKER/);}}
    for(const route of ['/%2egit/config','/%5fgate.json','/API/admin/example.js','/TOOLS/codex_review.sh',
      '/outside-alias/private.txt','/private-alias/config','/assets/outside-alias/private.txt',
      '/assets/private-alias/config']){const response=await get(route);assert.equal(response.status,404,route);assert.doesNotMatch(response.body,/ISOLATED_(?:PRIVATE|OUTSIDE)_MARKER/);}
    for(const [route,body] of [['/','PUBLIC_HOME'],['/tools','PUBLIC_TOOLS'],['/blog','PUBLIC_BLOG'],
      ...[...publicFiles].filter(([name])=>!['index.html','tools.html','blog/index.html'].includes(name)).map(([name,body])=>['/'+name,body])]){
      const response=await get(route);assert.equal(response.status,200,route);assert.equal(response.body,body,route);
    }
    const picks=await get('/api/admin/popular-picks');assert.equal(picks.status,200);assert.deepEqual(JSON.parse(picks.body),{picks:[]});
  } finally {
    if(child?.pid&&child.exitCode===null&&child.signalCode===null){const exited=new Promise(resolve=>child.once('exit',resolve));child.kill();await exited;}
    for(const link of links){assert.ok([realpathSync(site),realpathSync(path.join(site,'assets'))].includes(realpathSync(path.dirname(link))));unlinkSync(link);}
    if(rootAlias){assert.equal(realpathSync(path.dirname(rootAlias)),realpathSync(temporary));unlinkSync(rootAlias);}
    assert.equal(realpathSync(path.dirname(temporary)),realpathSync(os.tmpdir()));
    assert.ok(path.basename(temporary).startsWith('chenderm-serve-private-'));
    rmSync(temporary,{recursive:true,force:true});
  }
});
}
