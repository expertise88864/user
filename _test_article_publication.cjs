// Real observer + real delivery contract; isolated GitHub evidence only.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const policy = JSON.parse(fs.readFileSync('_delivery_policy.json', 'utf8'));
const code = fs.readFileSync('api/admin/_article-publication.js', 'utf8').replace('export async function', 'async function');
const MAIN = 'a'.repeat(40), BLOB = 'b'.repeat(40), NEXT = 'c'.repeat(40);
function fixture() {
  const context = { URL, Date };
  vm.runInNewContext(code + '\nthis.observePublication=observePublication;', context);
  const runs = policy.workflows.map((entry, i) => ({ id: 100 + i, run_attempt: 1, path: entry.path,
    head_sha: MAIN, head_branch: 'main', event: 'push', head_repository: { full_name: policy.repository }, status: 'completed', conclusion: 'success' }));
  const jobs = new Map(runs.map((run, index) => [run.id, policy.workflows[index].jobs.map((name, i) => ({
    id: run.id * 10 + i, name, head_sha: MAIN, status: 'completed',
    conclusion: (policy.workflows[index].main_skips || []).includes(name) ? 'skipped' : 'success',
    steps: policy.workflows[index].steps[name].required.map(name => ({ name, status: 'completed', conclusion: 'success' })),
  }))]));
  const deployment = { id: 700, sha: MAIN, environment: 'Production', production_environment: true, creator: { login: 'vercel[bot]' } };
  const status = { id: 800, state: 'success', creator: { login: 'vercel[bot]' }, environment_url: 'https://chendermatologist-example-expertise88864s-projects.vercel.app' };
  const calls = [];
  const h = { runs, jobs, deployment, status, source: { main: MAIN, mainBlobSha: BLOB, blobSha: BLOB, mainIndexable: true }, cfg: structuredClone(policy), changedMain: false, fail: false, mutate: null };
  const clone = data => JSON.parse(JSON.stringify(data));
  async function api(method, path) {
    assert.equal(method, 'GET'); calls.push(path);
    if (h.fail) throw Error('private upstream token detail');
    let data;
    if (path.startsWith('actions/runs?')) data = { workflow_runs: clone(h.runs) };
    else if (path.includes('/jobs?')) data = { jobs: clone(h.jobs.get(Number(path.split('/')[2]))) };
    else if (path.startsWith('deployments?')) data = [clone(h.deployment)];
    else if (path.startsWith('deployments/') && path.includes('/statuses?')) data = [clone(h.status)];
    else if (path === 'git/ref/heads/main') data = { object: { sha: h.changedMain ? NEXT : MAIN } };
    else assert.fail('Unexpected evidence request: ' + path);
    return h.mutate ? h.mutate(path, data, calls) : data;
  }
  h.observe = () => context.observePublication(api, h.source, h.cfg);
  h.calls = calls;
  return h;
}

test('exact main workflows/jobs/steps, latest production and smoke confirm only the matching version', async () => {
  const h = fixture(), result = await h.observe();
  assert.equal(result.state, 'live'); assert.equal(result.published, true);
  assert.equal(result.ciVerified, true); assert.equal(result.deploymentVerified, true);
  assert.equal(result.mainSha, MAIN); assert.equal(result.mainBlobSha, BLOB);
  assert.equal(result.checks.length, policy.workflows.length); assert.ok(Number.isFinite(Date.parse(result.observedAt)));
  assert.ok(h.calls.some(path => path.includes('/attempts/1/jobs')));
  assert.equal(h.calls.at(-1), 'git/ref/heads/main');
});
test('a deployed main version never claims a different newer draft is published', async () => {
  const h = fixture(); h.source.blobSha = NEXT;
  const result = await h.observe();
  assert.equal(result.state, 'live'); assert.equal(result.deploymentVerified, true);
  assert.equal(result.matchesLoadedVersion, false); assert.equal(result.published, false);
});
test('a deployed noindex source is distinguished from public publication', async () => {
  const h = fixture(); h.source.mainIndexable = false;
  const result = await h.observe();
  assert.equal(result.state, 'live_noindex'); assert.equal(result.deploymentVerified, true);
  assert.equal(result.published, false); assert.equal(result.sourceIndexable, false);
});
test('verified Vercel Production environment with a false GitHub flag uses formal smoke rather than that flag alone', async () => {
  const h = fixture(); h.deployment.production_environment = false;
  assert.equal((await h.observe()).state, 'live');
});
test('a new draft with no main source stays unpublished without evidence requests', async () => {
  const h = fixture(); h.source.mainBlobSha = null;
  const result = await h.observe(); assert.equal(result.state, 'not_published'); assert.equal(result.published, false);
  assert.equal(h.calls.length, 0);
});
test('missing, running and failed formal workflows cannot borrow candidate success', async () => {
  for (const mode of ['missing', 'running', 'failure', 'cancelled', 'timed_out', 'skipped', 'neutral', 'dispatch', 'candidate', 'foreign']) {
    const h = fixture();
    if (mode === 'missing') h.runs.shift();
    else if (mode === 'running') { h.runs[0].status = 'in_progress'; h.runs[0].conclusion = null; }
    else if (mode === 'dispatch') h.runs[0].event = 'workflow_dispatch';
    else if (mode === 'candidate') h.runs[0].head_branch = 'codex/candidate';
    else if (mode === 'foreign') h.runs[0].head_repository.full_name = 'foreign/repo';
    else h.runs[0].conclusion = mode;
    const result = await h.observe();
    assert.ok(['ci_missing', 'ci_running', 'ci_failed'].includes(result.state), mode);
    assert.equal(result.ciVerified, false, mode); assert.equal(result.published, false, mode);
    assert.equal(h.calls.some(path => path.startsWith('deployments')), false);
  }
});
test('required job/step absence, duplicate, skip, hidden failure and wrong SHA all fail closed', async () => {
  for (const mode of ['missing-job', 'duplicate-job', 'unknown-job', 'missing-step', 'duplicate-step', 'skipped-step', 'hidden-failure', 'wrong-sha']) {
    const h = fixture(), jobs = h.jobs.get(100);
    if (mode === 'missing-job') jobs.shift();
    if (mode === 'duplicate-job') jobs.push(structuredClone(jobs[0]));
    if (mode === 'unknown-job') jobs.push({ name: 'Unknown', status: 'completed', conclusion: 'success', head_sha: MAIN, steps: [] });
    if (mode === 'missing-step') jobs[0].steps.shift();
    if (mode === 'duplicate-step') jobs[0].steps.push(structuredClone(jobs[0].steps[0]));
    if (mode === 'skipped-step') jobs[0].steps[0].conclusion = 'skipped';
    if (mode === 'hidden-failure') jobs[0].steps.push({ name: 'Optional step', status: 'completed', conclusion: 'failure' });
    if (mode === 'wrong-sha') jobs[0].head_sha = NEXT;
    const result = await h.observe(); assert.equal(result.state, 'ci_failed', mode); assert.equal(result.published, false, mode);
  }
});
test('latest run id and attempt take priority over old green evidence', async () => {
  const h = fixture(); h.runs.push({ ...h.runs[0], id: 900, status: 'in_progress', conclusion: null });
  const result = await h.observe(); assert.equal(result.state, 'ci_running'); assert.equal(result.published, false);
});
test('deployment must be exact SHA, production, trusted Vercel bot and latest status', async () => {
  for (const mode of ['preview', 'missing-production-flag', 'wrong-sha', 'foreign-bot', 'foreign-status-bot', 'failure', 'queued', 'inactive', 'unsafe-url']) {
    const h = fixture();
    if (mode === 'preview') h.deployment.environment = 'Preview';
    if (mode === 'missing-production-flag') delete h.deployment.production_environment;
    if (mode === 'wrong-sha') h.deployment.sha = NEXT;
    if (mode === 'foreign-bot') h.deployment.creator.login = 'untrusted-bot';
    if (mode === 'foreign-status-bot') h.status.creator.login = 'untrusted-bot';
    if (mode === 'unsafe-url') h.status.environment_url = 'https://attacker.test/private';
    if (['failure', 'queued', 'inactive'].includes(mode)) h.status.state = mode;
    const result = await h.observe(); assert.notEqual(result.state, 'live', mode); assert.equal(result.published, false, mode);
  }
});
test('a newer failed production deployment does not fall back to an old successful deployment', async () => {
  const h = fixture();
  h.mutate = (path, data) => path.startsWith('deployments?') ? [...data, { ...h.deployment, id: 701 }] : path.includes('/701/statuses?') ? [{ ...h.status, state: 'failure' }] : data;
  const result = await h.observe(); assert.equal(result.state, 'deployment_failed'); assert.equal(result.published, false);
});
test('a newer production rollback for another SHA cannot borrow old exact-main success', async () => {
  const h = fixture();
  h.mutate = (path, data) => path.startsWith('deployments?') && !new URLSearchParams(path.split('?')[1]).has('sha')
    ? [...data, { ...h.deployment, id: 701, sha: NEXT }] : data;
  const result = await h.observe();
  assert.equal(result.state, 'unverified'); assert.equal(result.published, false); assert.equal(result.deploymentVerified, false);
  assert.ok(h.calls.some(path => path.startsWith('deployments?') && !new URLSearchParams(path.split('?')[1]).has('sha')));
});
test('busy preview history cannot crowd production out of its bounded query', async () => {
  const h = fixture();
  h.mutate = (path, data) => {
    if (!path.startsWith('deployments?')) return data;
    const query = new URLSearchParams(path.split('?')[1]);
    assert.equal(query.has('sha'), false, 'rollback deployments must remain visible');
    if (query.get('environment') === 'Production') return data;
    return Array.from({ length: 100 }, (_, i) => ({ ...h.deployment, id: 1000 + i,
      environment: 'Preview', production_environment: false }));
  };
  const result = await h.observe();
  assert.equal(result.state, 'live'); assert.equal(result.published, true);
  assert.equal(h.calls.filter(path => path.startsWith('deployments?')).length, 2);
});
test('main, CI rerun, deployment or status changing during observation invalidates publication', async () => {
  for (const mode of ['main', 'runs', 'deployment', 'deployment-sha', 'status']) {
    const h = fixture(); h.changedMain = mode === 'main';
    h.mutate = (path, data, calls) => {
      const count = calls.filter(item => item === path).length;
      if (count > 1 && mode === 'runs' && path.startsWith('actions/runs?')) data.workflow_runs[0].run_attempt++;
      if (count > 1 && mode === 'deployment' && path.startsWith('deployments?')) data[0].id++;
      if (count > 1 && mode === 'deployment-sha' && path.startsWith('deployments?')) data.push({ ...data[0], id: 701, sha: NEXT });
      if (count > 1 && mode === 'status' && path.includes('/statuses?')) data[0].id++;
      return data;
    };
    const result = await h.observe(); assert.equal(result.state, 'changed', mode); assert.equal(result.published, false, mode);
  }
});
test('permission/network/malformed or incomplete pagination cannot produce green evidence', async () => {
  for (const mode of ['network', 'shape', 'pagination', 'bad-id']) {
    const h = fixture(); h.fail = mode === 'network';
    h.mutate = (path, data) => {
      if (path.startsWith('actions/runs?')) {
        if (mode === 'shape') return {};
        if (mode === 'pagination') return { workflow_runs: Array.from({ length: 100 }, () => ({ ...h.runs[0] })) };
        if (mode === 'bad-id') data.workflow_runs[0].id = '../secret';
      }
      return data;
    };
    const result = await h.observe(); assert.equal(result.state, 'unverified', mode); assert.equal(result.published, false, mode);
    assert.equal(JSON.stringify(result).includes('private'), false);
  }
});
test('broken delivery policy cannot silently reduce the completion gates', async () => {
  const h = fixture(); h.cfg.workflows.pop();
  const result = await h.observe(); assert.equal(result.state, 'unverified'); assert.equal(h.calls.length, 0);
});
