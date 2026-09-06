const test = require('node:test');
const assert = require('node:assert/strict');
const { allowed } = require('./_vercel_gate.cjs');
const cfg = require('./_delivery_policy.json');
const sha = 'a'.repeat(40);
const env = { VERCEL_ENV: 'production', VERCEL_GIT_COMMIT_SHA: sha };
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
  return async (url) => {
    if (bad === 'http') return { ok: false };
    if (url.includes('/pulls?')) return { ok: true, json: async () => bad === 'pr' ? [] : [
      { state: 'open', head: { sha, repo: { full_name: cfg.repository } }, base: { ref: 'main' } }
    ] };
    if (url.includes('/actions/runs?')) return { ok: true, json: async () => ({
      workflow_runs: cfg.workflows.map((e, i) => ({
        id: i + 101, path: e.path, head_sha: bad === 'sha' ? 'b'.repeat(40) : sha,
        head_branch: bad === 'main' ? 'main' : 'codex/test', event: 'push',
        status: 'completed', conclusion: bad === 'run' ? 'failure' : 'success'
      }))
    }) };
    const id = Number(url.match(/runs\/(\d+)/)[1]) - 100;
    return { ok: true, json: async () => ({ jobs: bad === 'missing' ? [] : cfg.workflows[id - 1].jobs.map(name => ({
      name, status: 'completed', conclusion: bad === 'skip' ? 'skipped' : 'success',
      steps: bad === 'steps' ? [] : [
        ...cfg.workflows[id - 1].steps[name].required,
        ...(cfg.workflows[id - 1].steps[name].candidate_required || [])
      ].map(step => ({ name: step, status: 'completed',
        conclusion: bad === 'step' ? 'failure' : bad === 'step-skipped' ? 'skipped' : 'success' }))
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
for (const bad of ['sha', 'main', 'run', 'missing', 'skip', 'step', 'http', 'pr', 'steps', 'step-skipped']) {
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
for (const overrides of [
  { actor: { login: 'maintainer' } }, { actor: undefined },
  { head_branch: 'codex/manual-test' }, { head_branch: 'main' }
]) {
  test('untrusted dispatch identity is not production evidence: ' + JSON.stringify(overrides), async () => {
    await assert.rejects(() => allowed(env, dispatchEvidence(overrides)));
  });
}

test('Vercel validates before generating production artifacts', () => {
  const config = require('./vercel.json');
  assert.equal(config.buildCommand, 'node _vercel_gate.cjs --build && npm run build');
});
