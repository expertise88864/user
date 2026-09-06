/* Vercel ignored-build command: exit 0 = do NOT deploy, exit 1 = build.
 * Production must already have exact-SHA candidate CI evidence.
 * No credential or response body is logged. Preview builds never become production.
 */
const fs = require('node:fs');
const assert = require('node:assert/strict');

async function allowed(env = process.env, request = fetch) {
  if (env.VERCEL_ENV === 'preview') return true;
  if (env.VERCEL_ENV !== 'production' || !/^[a-f0-9]{40}$/.test(env.VERCEL_GIT_COMMIT_SHA || '')) return false;
  const cfg = JSON.parse(fs.readFileSync(__dirname + '/_delivery_policy.json', 'utf8'));
  assert.match(cfg.repository, /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/);
  assert.ok(Array.isArray(cfg.workflows) && cfg.workflows.length > 0, 'Missing workflow contract');
  for (const entry of cfg.workflows) {
    assert.match(entry.path, /^\.github\/workflows\/[A-Za-z0-9_-]+\.yml$/);
    assert.ok(Array.isArray(entry.jobs) && entry.jobs.length > 0, 'Missing job contract');
    for (const job of entry.jobs) assert.ok(entry.steps?.[job]?.required?.length > 0, 'Missing step contract');
  }
  const sha = env.VERCEL_GIT_COMMIT_SHA;
  const headers = { Accept: 'application/vnd.github+json', 'User-Agent': 'verified-production-only' };
  const credential = env.GH_TOKEN || env.GITHUB_TOKEN;
  if (credential) headers.Authorization = 'Bearer ' + credential;
  async function pages(path, key) {
    const rows = [];
    for (let page = 1; page <= 20; page++) {
      const response = await request('https://api.github.com/repos/' + cfg.repository + path +
        (path.includes('?') ? '&' : '?') + 'per_page=100&page=' + page,
        { headers, redirect: 'error', signal: AbortSignal.timeout(15000) });
      assert.ok(response.ok, 'GitHub evidence unavailable');
      const data = await response.json();
      const list = key ? data[key] : data;
      assert.ok(Array.isArray(list), 'Malformed GitHub evidence');
      rows.push(...list);
      if (list.length < 100) return rows;
    }
    throw Error('Incomplete GitHub evidence');
  }
  const runs = await pages('/actions/runs?head_sha=' + sha, 'workflow_runs');
  for (const entry of cfg.workflows) {
    const matching = runs.filter(r => r.head_sha === sha && r.path === entry.path &&
      String(r.head_branch).startsWith('codex/'));
    const pushed = matching.filter(r => r.event === 'push');
    const candidates = (pushed.length ? pushed : matching.filter(r => cfg.allow_dispatch === true &&
      r.event === 'workflow_dispatch' && r.actor?.login === 'github-actions[bot]' &&
      r.head_branch.startsWith('codex/scheduled-'))).sort((a, b) => b.id - a.id);
    const run = candidates[0];
    assert.ok(run && run.status === 'completed' && run.conclusion === 'success', 'Candidate CI is not green');
    const jobs = await pages('/actions/runs/' + run.id + '/attempts/' + (run.run_attempt || 1) + '/jobs', 'jobs');
    for (const required of entry.jobs) assert.ok(jobs.some(j => j.name === required), 'Required job missing');
    assert.ok(jobs.length > 0, 'No jobs');
    for (const job of jobs) {
      assert.equal(job.status, 'completed');
      if (job.conclusion === 'skipped' && (entry.candidate_skips || []).includes(job.name)) continue;
      assert.equal(job.conclusion, 'success', 'Job not green');
      const contract = entry.steps?.[job.name];
      assert.ok(contract?.required?.length > 0, 'Missing step contract');
      assert.ok(Array.isArray(job.steps) && job.steps.length > 0, 'Missing step evidence');
      for (const name of [...contract.required, ...(contract.candidate_required || [])]) {
        const matches = job.steps.filter(s => s.name === name);
        assert.equal(matches.length, 1, 'Required step missing/duplicated');
        assert.equal(matches[0].status, 'completed', 'Required step incomplete');
        assert.equal(matches[0].conclusion, 'success', 'Required step not successful');
      }
      assert.ok(!(job.steps || []).some(s =>
        ['failure', 'cancelled', 'timed_out', 'action_required'].includes(s.conclusion)), 'Hidden step failure');
    }
  }
  if (cfg.require_pr) {
    const prs = await pages('/commits/' + sha + '/pulls');
    assert.ok(prs.some(p => p.head?.sha === sha && p.base?.ref === 'main' &&
      p.head?.repo?.full_name === cfg.repository && (p.state === 'open' || p.merged_at)), 'No reviewed candidate PR');
  }
  return true;
}
module.exports = { allowed };
if (require.main === module) {
  // Build mode uses normal failure semantics, so a missing/broken gate cannot deploy.
  const buildMode = process.argv.includes('--build');
  allowed().then(ok => {
    console.log(ok ? 'Verified candidate or Preview: build allowed.' : 'Production blocked: candidate evidence unavailable.');
    process.exitCode = buildMode ? (ok ? 0 : 1) : (ok ? 1 : 0);
  }).catch(() => {
    console.error('Production blocked: exact-SHA candidate CI verification failed.');
    process.exitCode = buildMode ? 1 : 0;
  });
}
