const test = require('node:test');
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { allowed, failureSummary } = require('./_vercel_gate.cjs');
const cfg = require('./_delivery_policy.json');
const sha = 'a'.repeat(40);
const env = { VERCEL_ENV: 'production', VERCEL_GIT_COMMIT_SHA: sha };
test('Vercel installs the locked dependency graph without lifecycle scripts', () => {
  assert.equal(require('./vercel.json').installCommand, 'npm ci --ignore-scripts --no-audit --no-fund');
});
test('preview login sends the secret once without following redirects or exporting cookies', async () => {
  const { authenticatePreview } = require('./_delivery_preview.cjs');
  const base = new URL('https://candidate-team.vercel.app');
  const calls = [];
  const context = {
    request: { get: async (url, options) => {
      calls.push({url,options});
      return {status:()=>307,headers:()=>({location:'/'})};
    } },
    cookies: async () => [{domain:base.hostname,secure:true,httpOnly:true}],
  };
  await authenticatePreview(context, base, 'fixture-secret');
  assert.deepEqual(calls, [{url:base.origin+'/',options:{headers:{
    'x-vercel-protection-bypass':'fixture-secret','x-vercel-set-bypass-cookie':'true'
  },maxRedirects:0}}]);
  await authenticatePreview(context, base, '');
  assert.equal(calls.length, 1);
});
test('preview login rejects unsafe redirects, missing or unsafe cookies and sanitizes request failures', async () => {
  const { authenticatePreview } = require('./_delivery_preview.cjs');
  const base = new URL('https://candidate-team.vercel.app');
  const safe = {domain:base.hostname,secure:true,httpOnly:true};
  const context = (status, location, cookies) => ({
    request:{get:async()=>({status:()=>status,headers:()=>({location})})},
    cookies:async()=>cookies,
  });
  for (const location of ['https://other.vercel.app/','http://candidate-team.vercel.app/','http://[',undefined]) {
    await assert.rejects(authenticatePreview(context(307,location,[safe]),base,'fixture'), /redirect/);
  }
  for (const cookies of [[],[{...safe,domain:'.'+base.hostname}], [{...safe,domain:'other.vercel.app'}],
    [{...safe,secure:false}],[{...safe,httpOnly:false}]]) {
    await assert.rejects(authenticatePreview(context(307,'/',cookies),base,'fixture'), /cookies/);
  }
  await assert.rejects(authenticatePreview(context(500,undefined,[safe]),base,'fixture'), /authentication failed/);
  await assert.rejects(authenticatePreview({request:{get:async()=>{throw Error('header: fixture-secret');}}},base,'fixture-secret'),
    error=>error.message==='Preview authentication request failed');
});
test('preview credential stays on the exact deployment origin', () => {
  const { previewHeaders } = require('./_delivery_preview.cjs');
  const origin = 'https://candidate-team.vercel.app';
  assert.deepEqual(previewHeaders(origin + '/blog/example', origin, 'fixture'),
    { 'x-vercel-protection-bypass': 'fixture' });
  for (const url of ['https://analytics.example/x', 'https://other.vercel.app/',
    'http://candidate-team.vercel.app/', origin + '.evil.example/']) {
    assert.deepEqual(previewHeaders(url, origin, 'fixture'), {});
  }
  assert.deepEqual(previewHeaders(origin, origin, ''), {});
});
function fake(bad = '') {
  const pr = { number: 48, state: 'open', changed_files: 1,
    head: { sha, ref: 'codex/test', repo: { full_name: cfg.repository } },
    base: { sha: 'c'.repeat(40), ref: 'main', repo: { full_name: cfg.repository } } };
  const raw = Buffer.from(JSON.stringify({ version: 1, requests: [] }, null, 2) + '\n');
  const proofSha = createHash('sha1').update(Buffer.concat([Buffer.from('blob ' + raw.length + '\0'), raw])).digest('hex');
  const settingsDefault=require('./_site_settings_delivery.cjs').DEFAULT;
  const settingsFiles={
    '_site_settings.json':Buffer.from(JSON.stringify(settingsDefault,null,2)+'\n'),
    '.site-settings-delivery.json':Buffer.from(JSON.stringify({version:1,request:null},null,2)+'\n'),
    'assets/settings-catalog.json':Buffer.from(JSON.stringify({version:1,articles:['acne-myths','sunscreen-myths'].map(slug=>({slug,title:slug,title_en:slug}))},null,2)+'\n'),
  };
  const settingsBlob=bytes=>createHash('sha1').update(Buffer.concat([Buffer.from('blob '+bytes.length+'\0'),bytes])).digest('hex');
  return async (url) => {
    if (bad === 'http') return { ok: false };
    if (url.includes('/git/ref/heads/main')) return new Response(JSON.stringify({ ref: 'refs/heads/main', object: { type: 'commit', sha: '9'.repeat(40) } }));
    if (url.includes('/compare/' + '9'.repeat(40) + '...')) return new Response(JSON.stringify({ status: 'ahead', merge_base_commit: { sha: '9'.repeat(40) } }));
    if (url.includes('/git/commits/' + '9'.repeat(40))) return new Response(JSON.stringify({ sha: '9'.repeat(40), tree: { sha: '8'.repeat(40) }, parents: [] }));
    if (url.includes('/git/trees/' + '8'.repeat(40))) return new Response(JSON.stringify({ sha: '8'.repeat(40), truncated: false, tree: [] }));
    if (url.includes('/contents/.cms-delivery.json?ref=')) {
      if (bad === 'cms') return new Response('{}', { status: 404 });
      return new Response(JSON.stringify({ type: 'file', path: '.cms-delivery.json', encoding: 'base64', size: raw.length,
        content: raw.toString('base64'), sha: proofSha }));
    }
    if(url.includes('/contents/')){
      const path=url.split('/contents/')[1].split('?')[0],bytes=settingsFiles[path];
      assert.ok(bytes,'Unexpected fixture settings path');
      return Response.json({type:'file',path,sha:settingsBlob(bytes),size:bytes.length,encoding:'base64',content:bytes.toString('base64')});
    }
    if (url.includes('/git/commits/')) return new Response(JSON.stringify({ sha, tree: { sha: '1'.repeat(40) } }));
    if (url.includes('/git/trees/')) return new Response(JSON.stringify({ sha: '1'.repeat(40), truncated: false,
      tree: [{ path: '.cms-delivery.json', type: 'blob', mode: '100644', sha: proofSha },...Object.entries(settingsFiles).map(([path,bytes])=>({path,type:'blob',mode:'100644',sha:settingsBlob(bytes)}))] }));
    if (url.includes('/pulls?')) return { ok: true, json: async () => bad === 'pr' ? [] : [
      pr
    ] };
    if (url.includes('/pulls/48/files?')) return Response.json([{filename:'blog/example.html'}]);
    if (new URL(url).pathname.endsWith('/pulls/48')) return Response.json(pr);
    if (url.includes('/actions/runs?')) return { ok: true, json: async () => ({
      workflow_runs: cfg.workflows.flatMap((e, i) => [{
        id: i + 101, path: e.path, head_sha: bad === 'sha' ? 'b'.repeat(40) : sha,
        head_branch: bad === 'main' ? 'main' : 'codex/test', event: 'push',
        status: 'completed', conclusion: bad === 'run' ? 'failure' : 'success'
      }, ...(bad === 'pr-missing' ? [] : [{id:i+201,path:e.path,head_sha:sha,head_branch:'codex/test',
        event:'pull_request',status:'completed',conclusion:bad==='pr-run'?'failure':'success'}])])
    }) };
    const runId = Number(url.match(/runs\/(\d+)/)[1]);
    const isPR = runId >= 201;
    const id = runId - (isPR ? 200 : 100);
    return { ok: true, json: async () => ({ jobs: bad === 'missing' ? [] : cfg.workflows[id - 1].jobs.map(name => ({
      name, status: 'completed', conclusion: bad === 'skip' || (isPR && ['Browser fixtures','Preview browser','Production smoke'].includes(name)) ? 'skipped' : 'success',
      steps: bad === 'steps' ? [] : [
        ...cfg.workflows[id - 1].steps[name].required,
        ...(cfg.workflows[id - 1].steps[name].candidate_required || [])
      ].map(step => ({ name: step, status: 'completed',
        conclusion: bad === 'step' || (isPR && bad === 'pr-step') ? 'failure' : bad === 'step-skipped' ? 'skipped' : 'success' }))
    })) }) };
  };
}
test('preview does not need production approval', async () => {
  assert.equal(await allowed({ VERCEL_ENV: 'preview' }, () => { throw Error('no request'); }), true);
});
test('unknown environment and missing SHA deny deployment', async () => {
  assert.equal(await allowed({}), false);
  assert.equal(await allowed({ VERCEL_ENV: 'production' }), false);
});
test('exact complete candidate may deploy', async () => assert.equal(await allowed(env, fake()), true));
for (const bad of ['pr-run', 'pr-step', 'pr-missing']) {
  test('green push cannot waive ' + bad, async () => await assert.rejects(allowed(env, fake(bad)),
    bad === 'pr-step' ? /Required step not successful/ : /PR CI is not green/));
}
test('PR path-filter absence is allowed only for a complete nonmatching diff', async () => {
  for (const [files, changed, passes] of [
    [[{filename:'_delivery.py'}], 1, true],
    [[{filename:'blog/deep/example.html'}], 1, false],
    [[{filename:'notes.txt',previous_filename:'blog/old.html'}], 1, false],
    [[{filename:'_delivery.py'}], 2, false],
    [[{filename:'_delivery.py'},{filename:'_delivery.py'}], 2, false]
  ]) {
    const base = fake();
    const request = async (url, options) => {
      const response = await base(url, options);
      if (url.includes('/actions/runs?')) {
        const data = await response.json();
        return Response.json({workflow_runs:data.workflow_runs.filter(run => !(run.event === 'pull_request' && run.path.endsWith('/vale.yml')))});
      }
      if (url.includes('/pulls/48/files?')) return Response.json(files);
      if (new URL(url).pathname.endsWith('/pulls/48')) return Response.json({...await response.json(),changed_files:changed});
      return response;
    };
    if (passes) assert.equal(await allowed(env, request), true);
    else await assert.rejects(allowed(env, request));
  }
});
test('a failed observed PR run cannot disappear behind a nonmatching path filter', async () => {
  const base = fake();
  const request = async (url, options) => {
    const response = await base(url, options);
    if (url.includes('/pulls/48/files?')) return Response.json([{filename:'_delivery.py'}]);
    if (!url.includes('/actions/runs?')) return response;
    const data = await response.json();
    return Response.json({workflow_runs:data.workflow_runs.map(run => run.event === 'pull_request' && run.path.endsWith('/vale.yml') ? {...run,conclusion:'failure'} : run)});
  };
  await assert.rejects(allowed(env, request), /PR CI is not green/);
});
test('PR head branch and latest complete attempt are required separately from push', async () => {
  for (const change of [{head_sha:'b'.repeat(40)}, {head_branch:'main'}, {event:'workflow_dispatch'},
    {status:'in_progress',conclusion:null}, {conclusion:'cancelled'}, {conclusion:'timed_out'}]) {
    const base = fake();
    const request = async (url, options) => {
      const response = await base(url, options);
      if (!url.includes('/actions/runs?')) return response;
      const data = await response.json();
      return Response.json({workflow_runs:data.workflow_runs.flatMap(run => run.event === 'pull_request'
        ? [run,{...run,run_attempt:2,...change}] : [run])});
    };
    // Wrong identities do not overwrite the old exact successful run, so remove
    // that prior run for those missing-identity cases rather than invent a retry.
    const wrongIdentity = ['head_sha','head_branch','event'].some(key => key in change);
    const exactRequest = wrongIdentity ? async (url, options) => {
      const response = await request(url, options);
      if (!url.includes('/actions/runs?')) return response;
      const data = await response.json();
      return Response.json({workflow_runs:data.workflow_runs.filter(run => run.event !== 'pull_request' || run.run_attempt === 2)});
    } : request;
    await assert.rejects(allowed(env, exactRequest), /PR CI is not green/);
  }
});
test('PR identity moving during verification cannot authorize production', async () => {
  const base = fake(); let reads = 0;
  const request = async (url, options) => {
    const response = await base(url, options);
    if (!new URL(url).pathname.endsWith('/pulls/48')) return response;
    const pr = await response.json();
    return Response.json(++reads === 1 ? pr : {...pr,base:{...pr.base,sha:'d'.repeat(40)}});
  };
  await assert.rejects(allowed(env, request), /advanced during verification/);
});
test('PR job skips and Vale filters mirror the existing workflow event contract', () => {
  const fs = require('node:fs');
  const delivery = cfg.workflows.find(entry => entry.path.endsWith('/delivery.yml'));
  assert.deepEqual(delivery.pull_request.skips, ['Browser fixtures','Preview browser','Production smoke']);
  const vale = cfg.workflows.find(entry => entry.path.endsWith('/vale.yml'));
  const source = fs.readFileSync(vale.path, 'utf8');
  const section = source.split('  pull_request:')[1].split('  workflow_dispatch:')[0];
  const paths = [...section.matchAll(/^      - '([^']+)'$/gm)].map(match => match[1]);
  assert.deepEqual(vale.pull_request.paths, paths);
});
test('green candidate CI cannot authorize unapproved bootstrap settings',async()=>{
  const base=fake();let changed;
  const request=async(url,options)=>{
    const response=await base(url,options);
    if(url.includes('/contents/_site_settings.json')){
      const data=await response.json(),value=JSON.parse(Buffer.from(data.content,'base64'));value.font.bodySize='18px';
      const bytes=Buffer.from(JSON.stringify(value,null,2)+'\n');changed=createHash('sha1').update(Buffer.concat([Buffer.from('blob '+bytes.length+'\0'),bytes])).digest('hex');
      return Response.json({...data,sha:changed,size:bytes.length,content:bytes.toString('base64')});
    }
    if(url.includes('/git/trees/')&&changed){const data=await response.json();for(const row of data.tree)if(row.path==='_site_settings.json')row.sha=changed;return Response.json(data);}
    return response;
  };
  await assert.rejects(allowed(env,request),/Bootstrap/);
});
test('fresh failed candidate evidence cannot be masked by a cached green response', async () => {
  const base=fake();
  const request=async(url,options)=>{
    const response=await base(url,options);
    if(!url.includes('/actions/runs?'))return response;
    if(options.cache!=='no-store'||options.headers['Cache-Control']!=='no-cache')return response;
    const data=await response.json();
    data.workflow_runs=data.workflow_runs.map(run=>({...run,run_attempt:2,conclusion:'failure'}));
    return {ok:true,json:async()=>data};
  };
  await assert.rejects(allowed(env,request),/Candidate CI is not green/);
});
test('HTTP and network failures stay blocking and log only safe numeric metadata', async () => {
  const secret='example-upstream-secret';
  for(const status of [401,403,429,500]){
    let error;
    try{await allowed(env,async()=>new Response(secret,{status,headers:{'x-ratelimit-remaining':'0','x-secret':secret}}));}
    catch(value){error=value;}
    assert.ok(error,'Unavailable evidence must reject');
    assert.equal(failureSummary(error),'Production blocked: exact-SHA candidate CI verification failed. Evidence=candidate-ci; failure=http; HTTP='+status+'; GitHub rate-limit remaining=0');
  }
  for(const request of [async()=>{throw Error(secret);},async()=>new Response(secret),async()=>new Response(secret,{status:403,headers:{'x-ratelimit-remaining':secret}})]){
    let error;try{await allowed(env,request);}catch(value){error=value;}
    assert.ok(error);assert.ok(!failureSummary(error).includes(secret));
  }
  assert.equal(failureSummary(Error(secret)),'Production blocked: exact-SHA candidate CI verification failed.');
});
test('CMS metadata uses the large-file object media type and uncached bounded same-repository reads', async () => {
  const base = fake(); const calls = [];
  const request = async (url, options) => {
    if (url.includes('/contents/') || url.includes('/git/')) calls.push({ url, options });
    return base(url, options);
  };
  assert.equal(await allowed(env, request), true);
  // Article and settings intent checks each re-read main; the separate
  // settings retirement transition also checks its initial/final revision.
  assert.equal(calls.filter(call => call.url.includes('/git/ref/heads/main')).length, 6);
  assert.equal(calls.filter(call => call.url.includes('/contents/.cms-delivery.json')).length, 1);
  for (const { url, options } of calls) {
    assert.ok(url.startsWith('https://api.github.com/repos/' + cfg.repository + '/'));
    assert.equal(options.headers['Cache-Control'], 'no-cache');
    assert.equal(options.redirect, 'error');
    assert.equal(options.cache, 'no-store');
  }
  assert.equal(calls.find(call => call.url.includes('/contents/')).options.headers.Accept, 'application/vnd.github.object+json');
});
for (const bad of ['sha', 'main', 'run', 'missing', 'skip', 'step', 'http', 'pr', 'steps', 'step-skipped', 'cms']) {
  test(bad + ' never authorizes production', async () => {
    await assert.rejects(() => allowed(env, fake(bad)));
  });
}

function dispatchEvidence(overrides = {}, includeFailedPush = false) {
  const base = fake();
  return async (url, options) => {
    const response = await base(url, options);
    if (!url.includes('/actions/runs?')) return response;
    const data = await response.json();
    const dispatched = data.workflow_runs.map(run => ({
      ...run, event: 'workflow_dispatch', head_branch: 'codex/scheduled-123-1',
      actor: { login: 'github-actions[bot]' }, ...overrides
    }));
    // A newer green manual run must never replace failed push evidence.
    const failedPush = includeFailedPush ? data.workflow_runs.map(run => ({
      ...run, id: run.id - 100, conclusion: 'failure'
    })) : [];
    return { ok: true, json: async () => ({ workflow_runs: [...failedPush, ...dispatched] }) };
  };
}

test('this site requires push evidence even for bot scheduled dispatch', async () => {
  assert.equal(cfg.allow_dispatch, false);
  await assert.rejects(() => allowed(env, dispatchEvidence()));
});
test('successful dispatch cannot mask failed push evidence', async () => {
  await assert.rejects(() => allowed(env, dispatchEvidence({}, true)));
});
test('latest retry is selected; old green cannot mask failed or pending latest attempt', async () => {
  for (const status of ['success','failure','pending']) {
    const base = fake();
    const request = async (url, options) => {
      const response = await base(url, options);
      if (!url.includes('/actions/runs?')) return response;
      const data = await response.json();
      return { ok: true, json: async () => ({ workflow_runs: data.workflow_runs.flatMap(run => [
        { ...run, run_attempt: 1, conclusion: status === 'success' ? 'failure' : 'success' },
        { ...run, run_attempt: 2, status: status === 'pending' ? 'in_progress' : 'completed', conclusion: status === 'pending' ? null : status },
      ]) }) };
    };
    if (status === 'success') assert.equal(await allowed(env, request), true);
    else await assert.rejects(allowed(env, request));
  }
});
test('latest attempt missing a required matrix job cannot borrow it from an earlier attempt', async () => {
  const base = fake();
  const request = async (url, options) => {
    const response = await base(url, options);
    if (!url.includes('/jobs?')) return response;
    const data = await response.json();
    return { ok: true, json: async () => ({ jobs: data.jobs.slice(0, 1) }) };
  };
  await assert.rejects(allowed(env, request));
});
for (const overrides of [
  { actor: { login: 'maintainer' } }, { actor: undefined },
  { head_branch: 'codex/manual-test' }, { head_branch: 'main' }
]) {
  test('untrusted dispatch identity is not production evidence: ' + JSON.stringify(overrides), async () => {
    await assert.rejects(() => allowed(env, dispatchEvidence(overrides)));
  });
}

test('Vercel validates before and after generating production artifacts', () => {
  const config = require('./vercel.json');
  assert.equal(config.buildCommand, 'node _vercel_gate.cjs --build && npm run build && node _vercel_gate.cjs --build --post-build' +
    ' && python _site_publish.py --stage dist');
  assert.equal(config.outputDirectory, 'dist', 'Serve only the staged public site, never the repository root');
});
// Deployed file census: the exact-SHA deployment's own build reports what dist/
// holds (read back through the Vercel API); the CDN answers only a small sample.
const filesSha = 'b'.repeat(40);
const filesToken = 'fixture-files-token';
const filesBase = new URL('https://chendermatologist-abc123xyz-expertise88864s-projects.vercel.app');
const filesManifest = { published: ['index.html', 'blog/a b.html', 'assets/a b.css', 'admin.html'],
  private: ['_delivery.py', 'AGENTS.md', '.github/workflows/delivery.yml', 'api/og.js'] };
// Exactly what _site_publish.py census() prints for a dist/ holding `files`.
function censusLine(files = [...filesManifest.published, 'pagefind/pagefind.js', 'pagefind/fragment/a.pf_fragment']) {
  const tracked = files.filter(name => !name.startsWith('pagefind/')).sort();
  const digest = createHash('sha256').update(tracked.join('\n'), 'utf8').digest('hex');
  return '[site-census] files=' + tracked.length + ' sha256=' + digest + ' generated=' + (files.length - tracked.length) +
    ' search=' + (files.includes('pagefind/pagefind.js') ? 1 : 0);
}
function buildEvents(lines = [censusLine()]) {
  return [{ type: 'command', created: 1, payload: { text: 'Running "npm run build"', date: 1, id: 'e0', serial: '0', deploymentId: 'dpl_Fixture123' } },
    ...lines.map((text, index) => ({ type: 'stdout', created: 2 + index,
      payload: { text, date: 2 + index, id: 'e' + (index + 1), serial: String(index + 1), deploymentId: 'dpl_Fixture123' } }))];
}
function vercelRequest({ deployment = {}, events = buildEvents(), status = {}, calls = [] } = {}) {
  return async (url, options) => {
    calls.push({ url, options });
    const path = new URL(url).pathname;
    if (path.startsWith('/v13/deployments/')) {
      if (status.deployment) return new Response('upstream says ' + filesToken, { status: status.deployment });
      return Response.json({ id: 'dpl_Fixture123', url: filesBase.hostname, name: 'chendermatologist',
        readyState: 'READY', target: null, meta: { githubCommitSha: filesSha }, ...deployment });
    }
    if (path === '/v3/deployments/dpl_Fixture123/events') {
      if (status.events) return new Response('upstream says ' + filesToken, { status: status.events });
      return typeof events === 'string' ? new Response(events) : Response.json(events);
    }
    throw Error('Unexpected Vercel API request');
  };
}
function cdnContext({ served = new Set(), gate = new Map(), og = 'image/svg+xml; charset=utf-8', requested = [] } = {}) {
  return { request: {
    head: async url => {
      const path = new URL(url).pathname; requested.push(path);
      if (gate.has(path)) return { status: () => 401, headers: () => ({ 'www-authenticate': gate.get(path) }) };
      return { status: () => served.has(path) ? 200 : 404, headers: () => ({}) };
    },
    get: async (url, options) => {
      assert.equal(url, filesBase.origin + '/api/og?title=DermNotes'); assert.deepEqual(options, { maxRedirects: 0 });
      return { status: () => 200, headers: () => ({ 'content-type': og }) };
    },
  } };
}
const allServed = () => new Set(['/index.html', '/blog/a%20b.html', '/assets/a%20b.css', '/admin.html', '/pagefind/pagefind.js']);
test('deployed files come from the exact-SHA deployment build census and a small CDN sample', async () => {
  const { checkDeployedFiles } = require('./_delivery_preview.cjs');
  const calls = [], requested = [];
  const counts = await checkDeployedFiles(cdnContext({ served: allServed(), requested }), filesBase, filesManifest,
    { sha: filesSha, token: filesToken, request: vercelRequest({ calls }) });
  assert.deepEqual(counts, { deployment: 'dpl_Fixture123', published: 4, generated: 2, private: 3,
    adminBasicAuth: 0, cdnRequests: requested.length + 1, apiRequests: 2 });
  // Both API calls carry the token only in the Authorization header, never in a URL.
  assert.deepEqual(calls.map(call => call.url), [
    'https://api.vercel.com/v13/deployments/' + filesBase.hostname + '?slug=expertise88864s-projects',
    'https://api.vercel.com/v3/deployments/dpl_Fixture123/events?builds=1&limit=-1&direction=forward&slug=expertise88864s-projects']);
  for (const { url, options } of calls) {
    assert.ok(!url.includes(filesToken));
    assert.equal(options.headers.Authorization, 'Bearer ' + filesToken);
    assert.equal(options.redirect, 'error');
    assert.equal(options.cache, 'no-store');
  }
  // Sample: first and last file of each type, the generated bundle and internal paths.
  assert.ok(requested.length < 40, 'The CDN only answers a sample');
  for (const path of ['/pagefind/pagefind.js', '/_delivery.py', '/AGENTS.md', '/.github/workflows/delivery.yml',
    '/__pycache__/_run_quality.cpython-312.pyc', '/index.html', '/admin.html', '/assets/a%20b.css']) assert.ok(requested.includes(path), path);
  assert.ok(!requested.includes('/api/og.js'), 'Functions are not probed as static files');
  // Event text may also sit at the top level of an event.
  const flat = [{ type: 'stdout', created: 1, date: 1, id: 'x', serial: '1', deploymentId: 'dpl_Fixture123', info: { name: 'b', type: 'build' }, text: censusLine() }];
  assert.equal((await checkDeployedFiles(cdnContext({ served: allServed() }), filesBase, filesManifest,
    { sha: filesSha, token: filesToken, request: vercelRequest({ events: flat }) })).published, 4);
});
test('a missing public file or an extra internal or unexpected file fails the census', async () => {
  const { checkDeployedFiles } = require('./_delivery_preview.cjs');
  const files = [...filesManifest.published, 'pagefind/pagefind.js'];
  for (const [label, deployed, pattern] of [
    ['missing public', files.filter(name => name !== 'blog/a b.html'), /holds 3 public files, checkout selects 4/],
    ['renamed public', [...files.filter(name => name !== 'blog/a b.html'), 'blog/a-b.html'], /deployed file list differs/],
    ['missing generated', files.filter(name => name !== 'pagefind/pagefind.js'), /search bundle missing/],
    ['internal', [...files, '_delivery.py'], /holds 5 public files/],
    ['internal dotfile', [...files, '.github/workflows/delivery.yml'], /holds 5 public files/],
    ['bytecode', [...files, '__pycache__/_run_quality.cpython-312.pyc'], /holds 5 public files/],
    ['function source', [...files, 'api/og.js'], /holds 5 public files/],
  ]) {
    const requested = [];
    await assert.rejects(checkDeployedFiles(cdnContext({ served: allServed(), requested }), filesBase, filesManifest,
      { sha: filesSha, token: filesToken, request: vercelRequest({ events: buildEvents([censusLine(deployed)]) }) }),
    error => pattern.test(error.message) && /differs from the public site selection/.test(error.message), label);
    assert.deepEqual(requested, [], 'A failed census never falls back to probing the CDN: ' + label);
  }
  for (const [label, lines, pattern] of [
    ['no census', ['[OK] Staged 4 public files into dist/'], /exactly one output census \(found 0\)/],
    ['two censuses', [censusLine(), censusLine()], /exactly one output census \(found 2\)/],
    ['forged second census', [censusLine(), censusLine([...files, '_delivery.py'])], /found 2/],
    ['truncated census', ['[site-census] files=4 sha256=abc generated=1 search=1'], /found 0/],
  ]) {
    await assert.rejects(checkDeployedFiles(cdnContext({ served: allServed() }), filesBase, filesManifest,
      { sha: filesSha, token: filesToken, request: vercelRequest({ events: buildEvents(lines) }) }), pattern, label);
  }
  await assert.rejects(checkDeployedFiles(cdnContext(), filesBase, { published: [], private: [] },
    { sha: filesSha, token: filesToken, request: vercelRequest() }), /Incomplete/);
});
test('a missing token, API failure or unbound deployment fails closed without leaking the token', async () => {
  const { checkDeployedFiles } = require('./_delivery_preview.cjs');
  for (const token of [undefined, '', 'short', 'has space in it']) {
    const calls = [];
    await assert.rejects(checkDeployedFiles(cdnContext({ served: allServed() }), filesBase, filesManifest,
      { sha: filesSha, token, request: vercelRequest({ calls }) }), /VERCEL_FILES_TOKEN is missing or malformed/);
    assert.deepEqual(calls, [], 'No request without a token');
  }
  const failures = [
    [{ status: { deployment: 401 } }, /deployment request failed: HTTP 401/],
    [{ status: { deployment: 404 } }, /deployment request failed: HTTP 404/],
    [{ status: { events: 403 } }, /deployment build events request failed: HTTP 403/],
    [{ status: { events: 500 } }, /deployment build events request failed: HTTP 500/],
    [{ events: 'not json ' + filesToken }, /build events response is not JSON/],
    [{ events: { events: [] } }, /build events response is malformed/],
    [{ events: [] }, /found 0/],
    [{ deployment: { meta: { githubCommitSha: 'c'.repeat(40) } } }, /exact commit/],
    [{ deployment: { meta: {} } }, /exact commit/],
    [{ deployment: { target: 'production' } }, /production/],
    [{ deployment: { url: 'other-abc-expertise88864s-projects.vercel.app' } }, /different deployment/],
    [{ deployment: { readyState: 'BUILDING' } }, /not ready/],
    [{ deployment: { name: 'another-project' } }, /another project/],
    [{ deployment: { id: '../../v2/user' } }, /id is malformed/],
  ];
  for (const [options, pattern] of failures) {
    await assert.rejects(checkDeployedFiles(cdnContext({ served: allServed() }), filesBase, filesManifest,
      { sha: filesSha, token: filesToken, request: vercelRequest(options) }),
    error => pattern.test(error.message) && !error.message.includes(filesToken), JSON.stringify(options));
  }
  await assert.rejects(checkDeployedFiles(cdnContext({ served: allServed() }), filesBase, filesManifest,
    { sha: filesSha, token: filesToken, request: async () => { throw Error('socket ' + filesToken); } }),
  error => /deployment request failed \(network\)/.test(error.message) && !error.message.includes(filesToken));
  await assert.rejects(checkDeployedFiles(cdnContext({ served: allServed() }), filesBase, filesManifest,
    { sha: 'short', token: filesToken, request: vercelRequest() }), /full commit SHA/);
});
test('the CDN sample must really answer: status, Basic Auth gate and og function', async () => {
  const { checkDeployedFiles } = require('./_delivery_preview.cjs');
  const run = context => checkDeployedFiles(context, filesBase, filesManifest,
    { sha: filesSha, token: filesToken, request: vercelRequest() });
  // The optional admin Basic Auth gate (middleware.js) answers 401 for the admin shell only.
  const realm = 'Basic realm="ChenDermatologist Admin", charset="UTF-8"';
  const served = allServed(); served.delete('/admin.html');
  assert.equal((await run(cdnContext({ served, gate: new Map([['/admin.html', realm]]) }))).adminBasicAuth, 1);
  await assert.rejects(run(cdnContext({ served, gate: new Map([['/admin.html', 'Basic realm="Elsewhere"']]) })), /differs/);
  await assert.rejects(run(cdnContext({ served: allServed(), gate: new Map([['/index.html', realm]]) })), /differs/);
  const missing = allServed(); missing.delete('/assets/a%20b.css');
  await assert.rejects(run(cdnContext({ served: missing })), /assets\/a b\.css: HTTP 404, expected 200/);
  const exposed = allServed(); exposed.add('/_delivery.py');
  await assert.rejects(run(cdnContext({ served: exposed })), /_delivery\.py: HTTP 200, expected 404/);
  await assert.rejects(run(cdnContext({ served: allServed(), og: 'text/html' })), /api\/og/);
});
test('the census line the build prints is the one the Preview check expects', () => {
  const { expectedCensus, readCensus } = require('./_delivery_preview.cjs');
  const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
  const dist = fs.mkdtempSync(path.join(os.tmpdir(), 'census-'));
  try {
    for (const name of [...filesManifest.published, 'pagefind/pagefind.js', 'pagefind/fragment/a.pf_fragment']) {
      fs.mkdirSync(path.dirname(path.join(dist, name)), { recursive: true });
      fs.writeFileSync(path.join(dist, name), 'x');
    }
    const line = require('node:child_process').execFileSync('python', ['-c',
      'import sys, _site_publish as p; print(p.census(sys.argv[1]))', dist], { encoding: 'utf8' }).trim();
    const census = readCensus(buildEvents([line]));
    const expected = expectedCensus(filesManifest);
    assert.deepEqual([census.files, census.sha256, census.generated, census.search], [expected.files, expected.sha256, 2, true]);
  } finally { fs.rmSync(dist, { recursive: true, force: true }); }
});
test('the CDN sample stays small for the real manifest', () => {
  const { cdnSample } = require('./_delivery_preview.cjs');
  const manifest = JSON.parse(require('node:child_process').execFileSync('python', ['_site_publish.py', '--manifest'],
    { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 }));
  const jobs = cdnSample(manifest);
  assert.ok(jobs.length >= 10 && jobs.length <= 40, 'sample size ' + jobs.length);
  assert.equal(new Set(jobs.map(job => job[0])).size, jobs.length);
  const type = name => (name.match(/\.[A-Za-z0-9]+$/) || ['(none)'])[0].toLowerCase();
  for (const kind of new Set(manifest.published.filter(name => !name.startsWith('pagefind/')).map(type))) {
    assert.ok(jobs.some(([name, expected]) => expected === 200 && type(name) === kind), kind);
  }
  assert.ok(jobs.filter(job => job[1] === 404).length >= 3);
});
