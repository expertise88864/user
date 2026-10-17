const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const transport = fs.readFileSync('api/admin/_github-fetch.js', 'utf8').replace(/\bexport (class|const|function|async function)/g, '$1');
const session = transport + '\n' + fs.readFileSync('api/admin/_session.js', 'utf8').replace(/^import[^\n]+;\s*$/gm, '')
  .replace(/export\s*\{[\s\S]*?\};\s*$/, '');
const login = fs.readFileSync('api/admin/login.js', 'utf8').replace(/^import[^\n]+;\s*$/gm, '')
  .replace('export const config', 'const loginConfig').replace('export default async function handler', 'async function loginHandler');
const logout = fs.readFileSync('api/admin/logout.js', 'utf8').replace(/import[^;]+;/, '')
  .replace('export const config', 'const config').replace('export default async function handler', 'async function handler');
const request = () => new Request('https://site.invalid/api/admin/logout', {
  method: 'POST', headers: {cookie: 'dn_admin_session=test-session'},
});
function backend(fetch, env = {KV_REST_API_URL:'https://kv.invalid', KV_REST_API_TOKEN:'test-only'}, logs = []) {
  const ctx = {console:{error:(...args)=>logs.push(args.join(' '))}, Request, Response, TextDecoder, AbortController, setTimeout, clearTimeout, fetch, process:{env},
    crypto:require('node:crypto').webcrypto};
  vm.runInNewContext(session + '\n' + logout + '\n' + login + '\nthis.api={handler,loginHandler,getSession,createSession};', ctx);
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
  const api = backend(async url => url === 'https://api.github.com/repos/expertise88864/user' ? Response.json({full_name:'expertise88864/user'}) :
    url.includes('api.github.com') ? Response.json({login:'expertise88864'}) : Response.json(result));
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

// --- Login verifies repository access with the Edge-safe transport ---
const PAT = 'ghp_' + 'F'.repeat(36);
function loginBackend(repo, logs = []) {
  const calls = [];
  const api = backend(async (url, options) => {
    calls.push({url, options});
    if (url === 'https://api.github.com/user') return Response.json({login:'expertise88864'});
    if (url === 'https://api.github.com/repos/expertise88864/user') return repo(options);
    if (url.includes('/set/')) return Response.json({result:'OK'});
    return Response.json({result:0});
  }, undefined, logs);
  return {api, calls, logs};
}
const loginRequest = () => new Request('https://site.invalid/api/admin/login', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({pat:PAT})});
test('login reads the fixed repository with Edge-safe options before minting a session', async () => {
  const h = loginBackend(() => Response.json({full_name:'expertise88864/user', permissions:{push:false}}));
  const response = await h.api.loginHandler(loginRequest());
  assert.equal(response.status, 200);
  const repo = h.calls.find(call => call.url === 'https://api.github.com/repos/expertise88864/user');
  assert.ok(repo, 'repository read happens during login');
  assert.equal(repo.options.redirect, 'manual');
  assert.ok(!('cache' in repo.options), 'Edge fetch must not receive a cache option');
  assert.equal(repo.options.headers['Cache-Control'], 'no-cache');
  assert.ok(repo.options.signal);
  const set = h.calls.findIndex(call => call.url.includes('/set/'));
  assert.ok(set > h.calls.indexOf(repo), 'session is stored only after the repository read');
});
for (const [label, respond, status, code] of [
  ['401', () => Response.json({}, {status:401}), 401, 'github_token_invalid'],
  ['403', () => Response.json({}, {status:403}), 403, 'github_forbidden'],
  ['403 rate limit', () => Response.json({}, {status:403, headers:{'x-ratelimit-remaining':'0'}}), 429, 'github_rate_limited'],
  ['404', () => Response.json({}, {status:404}), 403, 'github_not_found'],
  ['301', () => new Response(null, {status:301, headers:{Location:'https://elsewhere.invalid/'}}), 502, 'github_redirect'],
  ['503', () => Response.json({}, {status:503}), 502, 'github_upstream_error'],
  ['AbortError', () => { throw new DOMException('aborted', 'AbortError'); }, 502, 'github_timeout'],
  ['TypeError', () => { throw new TypeError('fetch failed ' + PAT); }, 502, 'github_fetch_failed'],
  ['other repository', () => Response.json({full_name:'someone/else'}), 502, 'github_response_invalid'],
]) test('login repository check ' + label + ' returns ' + code + ' and creates no session', async () => {
  const h = loginBackend(respond);
  const response = await h.api.loginHandler(loginRequest());
  assert.equal(response.status, status);
  const body = await response.json();
  assert.equal(body.code, code);
  assert.equal(response.headers.get('set-cookie'), null);
  assert.equal(h.calls.filter(call => call.url.includes('/set/')).length, 0, 'no KV session on failure');
  assert.ok(!JSON.stringify(body).includes(PAT));
  for (const line of h.logs) assert.ok(!line.includes(PAT) && !line.includes('FFFFFFFF') && !/Bearer\s+\S/.test(line), 'PAT never logged');
  if (label !== 'other repository') {
    const entry = JSON.parse(h.logs[0].replace('[admin-github] ', ''));
    assert.equal(entry.endpoint, 'login'); assert.equal(entry.path, 'repos/expertise88864/user'); assert.equal(entry.code, code);
  }
});
test('the login page client exposes the server reason without provider text', async () => {
  const {auth, requests} = frontend();
  const login = auth.setPat('test-only');
  await flush();
  requests[0].resolve(Response.json({error:'GitHub repository access failed', code:'github_token_invalid'}, {status:401}));
  const failure = await login.then(() => null, error => error);
  assert.equal(failure.code, 'github_token_invalid');
  assert.match(auth.loginMessage(failure), /GitHub token 無效或已過期，請清除登入後重新登入/);
  const unknown = auth.setPat('test-only'); await flush();
  requests[1].resolve(new Response('<html>gateway</html>', {status:502}));
  const generic = await unknown.then(() => null, error => error);
  assert.equal(generic.code, 'login_failed');
  assert.equal(auth.loginMessage({code:'__proto__'}), auth.loginMessage({code:'login_failed'}));
});
