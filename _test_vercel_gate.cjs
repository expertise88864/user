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
    'assets/settings-catalog.json':Buffer.from(JSON.stringify({version:1,articles:settingsDefault.picks.map(slug=>({slug,title:slug,title_en:slug}))},null,2)+'\n'),
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
      name, status: 'completed', conclusion: bad === 'skip' || (isPR && ['Preview browser','Production smoke'].includes(name)) ? 'skipped' : 'success',
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
  assert.deepEqual(delivery.pull_request.skips, ['Preview browser','Production smoke']);
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
  assert.equal(config.buildCommand, 'node _vercel_gate.cjs --build && npm run build && node _vercel_gate.cjs --build --post-build');
});
