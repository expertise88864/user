const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const session = fs.readFileSync('api/admin/_session.js', 'utf8').replace(/export\s*\{[\s\S]*?\};\s*$/, '');
const logout = fs.readFileSync('api/admin/logout.js', 'utf8').replace(/import[^;]+;/, '')
  .replace('export const config', 'const config').replace('export default async function handler', 'async function handler');
const request = () => new Request('https://site.invalid/api/admin/logout', {
  method: 'POST', headers: {cookie: 'dn_admin_session=test-session'},
});
function backend(fetch, env = {KV_REST_API_URL:'https://kv.invalid', KV_REST_API_TOKEN:'test-only'}) {
  const ctx = {Request, Response, AbortController, setTimeout, clearTimeout, fetch, process:{env},
    crypto:require('node:crypto').webcrypto};
  vm.runInNewContext(session + '\n' + logout + '\nthis.api={handler,getSession,createSession};', ctx);
  return ctx.api;
}
for (const [name, response] of [
  ['HTTP failure', () => new Response('private provider details', {status:503})],
  ['network failure', () => {throw new Error('private provider details');}],
  ['malformed JSON', () => new Response('{')],
  ['Redis error', () => Response.json({error:'private provider details'})],
  ['missing result', () => Response.json({})],
  ['invalid result', () => Response.json({result:'1'})],
]) {
  test(`logout does not claim revocation after ${name}`, async () => {
    const api = backend(async url => url.includes('/del/') ? response() : Response.json({result:JSON.stringify({
      login:'expertise88864', pat:'test-only', exp:Date.now()/1000+60,
    })}));
    const result = await api.handler(request());
    assert.equal(result.status, 503);
    assert.equal(result.headers.get('set-cookie'), null);
    assert.equal((await result.json()).ok, false);
    assert.ok(await api.getSession(request()));
  });
}
test('missing KV configuration reports retryable failure without dropping cookie', async () => {
  const result = await backend(() => assert.fail('no request expected'), {}).handler(request());
  assert.equal(result.status,503);
  assert.equal(result.headers.get('set-cookie'),null);
});
for (const count of [0,1]) test(`confirmed DEL result ${count} clears cookie`, async () => {
  const result = await backend(async () => Response.json({result:count})).handler(request());
  assert.equal(result.status,200);
  assert.equal((await result.json()).ok,true);
  assert.match(result.headers.get('set-cookie'),/Max-Age=0/);
});
test('successful revocation makes the old session unusable', async () => {
  let stored = JSON.stringify({login:'expertise88864',pat:'test-only',exp:Date.now()/1000+60});
  const api = backend(async url => {
    if (url.includes('/del/')) { stored = null; return Response.json({result:1}); }
    return Response.json({result:stored});
  });
  assert.ok(await api.getSession(request()));
  assert.equal((await api.handler(request())).status,200);
  assert.equal(await api.getSession(request()),null);
});
test('stalled KV deletion returns a retryable response after its deadline', async () => {
  const api = backend((url,options) => new Promise((resolve,reject) => {
    options.signal.addEventListener('abort',()=>reject(new Error('aborted')),{once:true});
  }));
  const result = await api.handler(request());
  assert.equal(result.status,503);
  assert.equal(result.headers.get('set-cookie'),null);
});
test('logout without cookie is idempotent without KV', async () => {
  const result = await backend(() => assert.fail('no request expected'), {}).handler(new Request('https://site.invalid',{method:'POST'}));
  assert.equal(result.status,200);
});
test('logout rejects other methods without touching KV', async () => {
  const result = await backend(() => assert.fail('no request expected')).handler(new Request('https://site.invalid'));
  assert.equal(result.status,405);
  assert.equal(result.headers.get('allow'),'POST');
});
for (const data of [
  {login:'expertise88864',exp:1}, {login:'not-allowlisted',exp:Date.now()/1000+60},
]) test('invalid sessions stay denied even when cleanup fails', async () => {
  const api = backend(async url => url.includes('/del/') ? new Response('',{status:503}) : Response.json({result:JSON.stringify(data)}));
  assert.equal(await api.getSession(request()),null);
});
for (const result of [{error:'private details'},{result:null},{result:1}]) test('unconfirmed SET cannot create a session', async () => {
  const api = backend(async url => url.includes('api.github.com') ? Response.json({login:'expertise88864'}) : Response.json(result));
  await assert.rejects(api.createSession('test-only'),/KV set failed/);
});

function frontend(initial = {}) {
  const values = new Map(Object.entries(initial));
  const requests = [];
  const ctx = {window:{}, sessionStorage:{getItem:key=>values.get(key) ?? null,
    setItem:(key,value)=>values.set(key,value), removeItem:key=>values.delete(key)},
    localStorage:{removeItem(){}}, fetch:(url, options)=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}))};
  vm.runInNewContext(fs.readFileSync('admin/session-auth.js','utf8'),ctx);
  return {auth:ctx.window.cdAdminAuth,requests,values};
}
const flush = () => new Promise(resolve => setImmediate(resolve));
test('failed logout clears local PAT, persists retry state and blocks login', async () => {
  const fixture = frontend({cd_gh_pat:'test-only',cd_gh_pat_exp:String(Date.now()+60000)});
  const operation = fixture.auth.clearPat();
  assert.equal(fixture.auth.getPat(),'');
  assert.equal(fixture.values.has('cd_gh_pat'),false);
  await flush(); fixture.requests[0].resolve(Response.json({ok:false},{status:503}));
  await assert.rejects(operation);
  await assert.rejects(fixture.auth.setPat('test-only'));
  assert.equal(fixture.requests.length,1);
  assert.equal(frontend(Object.fromEntries(fixture.values)).auth.isLogoutPending(),true);
  const retry = fixture.auth.clearPat();
  await flush(); fixture.requests[1].resolve(Response.json({ok:true}));
  await retry;
  assert.equal(fixture.auth.isLogoutPending(),false);
});
test('logout waits for an in-flight login and prevents PAT resurrection', async () => {
  const {auth,requests,values} = frontend();
  const login = auth.setPat('test-only');
  const rejected = assert.rejects(login,/cancelled/);
  await flush();
  const logout = auth.clearPat();
  await flush(); assert.equal(requests.length,1);
  requests[0].resolve(Response.json({ok:true}));
  await rejected; await flush();
  assert.equal(requests[1].url,'/api/admin/logout');
  assert.equal(values.has('cd_gh_pat'),false);
  requests[1].resolve(Response.json({ok:true}));
  await logout;
  assert.equal(auth.getPat(),'');
});
test('queued login cancelled before start sends no credential', async () => {
  const {auth,requests} = frontend();
  const login = assert.rejects(auth.setPat('test-only'));
  const logout = auth.clearPat();
  await login; await flush();
  assert.deepEqual(requests.map(r=>r.url),['/api/admin/logout']);
  requests[0].resolve(Response.json({ok:true})); await logout;
});
test('cookie restore preserves the original browser expiration', async () => {
  const expiry = String(Date.now()+60000);
  const {auth,requests,values} = frontend({cd_gh_pat:'test-only',cd_gh_pat_exp:expiry});
  const restore = auth.restoreSession(); await flush();
  requests[0].resolve(Response.json({ok:true})); await restore;
  assert.equal(values.get('cd_gh_pat_exp'),expiry);
});
test('logout also waits for cookie restoration and never restores its PAT', async () => {
  const {auth,requests,values} = frontend({cd_gh_pat:'test-only',cd_gh_pat_exp:String(Date.now()+60000)});
  const restore = assert.rejects(auth.restoreSession(),/cancelled/);
  await flush();
  const logout = auth.clearPat();
  requests[0].resolve(Response.json({ok:true})); await restore; await flush();
  assert.equal(requests[1].url,'/api/admin/logout');
  requests[1].resolve(Response.json({ok:true})); await logout;
  assert.equal(values.has('cd_gh_pat'),false);
});
test('expired PAT requires server logout before another login', () => {
  const {auth,values} = frontend({cd_gh_pat:'test-only',cd_gh_pat_exp:'1'});
  assert.equal(auth.getPat(),'');
  assert.equal(auth.isLogoutPending(),true);
  assert.equal(values.has('cd_gh_pat'),false);
});
