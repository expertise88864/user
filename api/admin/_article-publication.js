// Read-only observation, never a release permit. Evidence belongs to exact main
// at the observation time, not to an unsaved edit or another draft revision.
// API contracts: https://docs.github.com/en/rest/actions/workflow-runs
// and https://docs.github.com/en/rest/deployments/statuses
const REPO = 'expertise88864/user';
const SHA = /^(?!0{40}$)[a-f0-9]{40}$/;
const terminalFailures = new Set(['failure', 'cancelled', 'timed_out', 'action_required']);
const id = value => Number.isSafeInteger(value) && value > 0;

function policyValid(policy) {
  return policy && policy.repository === REPO && policy.require_pr === true &&
    policy.allow_dispatch === false && policy.cms_author_intent === true &&
    Array.isArray(policy.workflows) && policy.workflows.length >= 6 &&
    new Set(policy.workflows.map(entry => entry.path)).size === policy.workflows.length &&
    policy.workflows.every(entry => /^\.github\/workflows\/[a-z0-9_-]+\.yml$/i.test(entry.path) &&
      Array.isArray(entry.jobs) && entry.jobs.length > 0 && new Set(entry.jobs).size === entry.jobs.length &&
      entry.jobs.every(name => typeof name === 'string' && name &&
        Array.isArray(entry.steps?.[name]?.required) && entry.steps[name].required.length > 0)) &&
    policy.workflows.some(entry => entry.path === '.github/workflows/delivery.yml' &&
      entry.jobs.includes('Production smoke') && entry.steps['Production smoke'].required.includes('Verify exact-SHA production pages and assets'));
}

function runsFor(runs, policy, sha) {
  return policy.workflows.map(entry => {
    const candidates = runs.filter(run => run.head_sha === sha && run.path === entry.path &&
      run.head_branch === 'main' && run.event === 'push' && run.head_repository?.full_name === REPO);
    if (candidates.some(run => !id(run.id) || !id(run.run_attempt))) throw Error('Invalid run identity');
    const run = candidates.sort((a, b) => b.id - a.id || b.run_attempt - a.run_attempt)[0];
    return { entry, run };
  });
}

function signatures(selected) {
  return JSON.stringify(selected.map(({ run }) => run && [run.id, run.run_attempt, run.status, run.conclusion]));
}

function jobsPassed(jobs, entry, sha) {
  if (!jobs.length || entry.jobs.some(name => jobs.filter(job => job.name === name).length !== 1)) return false;
  return jobs.every(job => {
    if (job.status !== 'completed' || job.head_sha !== sha) return false;
    if (job.conclusion === 'skipped' && (entry.main_skips || []).includes(job.name)) return true;
    const contract = entry.steps?.[job.name];
    if (job.conclusion !== 'success' || !contract?.required?.length || !Array.isArray(job.steps) || !job.steps.length) return false;
    const required = [...contract.required, ...(contract.main_required || [])];
    if (required.some(name => {
      const matching = job.steps.filter(step => step.name === name);
      return matching.length !== 1 || matching[0].status !== 'completed' || matching[0].conclusion !== 'success';
    })) return false;
    return !job.steps.some(step => terminalFailures.has(step.conclusion));
  });
}

function productionFor(deployments) {
  // The verified Vercel integration uses environment=Production while its
  // GitHub production_environment flag can be false. That flag alone cannot
  // classify Preview vs production; require exact SHA/bot/environment + smoke.
  const matching = deployments.filter(item => String(item.environment).toLowerCase() === 'production' &&
    typeof item.production_environment === 'boolean' && ['vercel[bot]', 'vercel'].includes(item.creator?.login));
  if (matching.some(item => !id(item.id) || !SHA.test(item.sha || ''))) throw Error('Invalid deployment identity');
  return matching.sort((a, b) => b.id - a.id)[0] || null;
}

function statusFor(statuses) {
  if (statuses.some(item => !id(item.id))) throw Error('Invalid deployment status identity');
  return statuses.sort((a, b) => b.id - a.id)[0] || null;
}

function validDeploymentUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && url.hostname.startsWith('chendermatologist-') &&
      url.hostname.endsWith('.vercel.app') && !url.username && !url.password && !url.port &&
      ['/', ''].includes(url.pathname) && !url.search && !url.hash;
  } catch (_) { return false; }
}

export async function observePublication(api, source, policy) {
  const base = { mainSha: source.main, mainBlobSha: source.mainBlobSha,
    matchesLoadedVersion: source.mainBlobSha !== null && source.mainBlobSha === source.blobSha,
    sourceIndexable: source.mainIndexable === true,
    ciVerified: false, deploymentVerified: false, published: false, checks: [], observedAt: new Date().toISOString() };
  if (!SHA.test(source.main || '') || (source.mainBlobSha !== null && (!SHA.test(source.mainBlobSha || '') || typeof source.mainIndexable !== 'boolean')) || !policyValid(policy)) {
    return { ...base, state: 'unverified' };
  }
  if (source.mainBlobSha === null) return { ...base, state: 'not_published' };
  try {
    const deadline = Date.now() + 25_000;
    async function get(path) {
      if (Date.now() >= deadline) throw Error('Observation expired');
      return api('GET', path);
    }
    async function pages(path, key) {
      const rows = [];
      for (let page = 1; page <= 3; page++) {
        const data = await get(path + (path.includes('?') ? '&' : '?') + 'per_page=100&page=' + page);
        const items = key ? data?.[key] : data;
        if (!Array.isArray(items) || items.length > 100 || items.some(item => !item || typeof item !== 'object')) throw Error('Invalid evidence');
        rows.push(...items);
        if (items.length < 100) return rows;
      }
      throw Error('Incomplete evidence');
    }
    const runPath = 'actions/runs?head_sha=' + source.main;
    const selected = runsFor(await pages(runPath, 'workflow_runs'), policy, source.main);
    const checks = selected.map(({ entry, run }) => ({ workflow: entry.path,
      runId: run?.id || null, attempt: run?.run_attempt || null,
      status: run?.status || 'missing', conclusion: run?.conclusion || null }));
    let state = selected.some(({ run }) => !run) ? 'ci_missing' :
      selected.some(({ run }) => run.status !== 'completed') ? 'ci_running' :
      selected.some(({ run }) => run.conclusion !== 'success') ? 'ci_failed' : null;
    let deployment = null, deploymentStatus = null;
    if (!state) {
      const jobs = await Promise.all(selected.map(({ run }) => pages('actions/runs/' + run.id + '/attempts/' + run.run_attempt + '/jobs', 'jobs')));
      if (jobs.some((items, index) => !jobsPassed(items, selected[index].entry, source.main))) state = 'ci_failed';
    }
    const ciVerified = state === null;
    if (ciVerified) {
      // A rollback/manual redeploy may replace production without changing
      // main. A SHA-filtered list would hide that newer deployment entirely.
      deployment = productionFor(await pages('deployments?environment=Production'));
      if (!deployment) state = 'deployment_missing';
      else if (deployment.sha !== source.main) state = 'unverified';
      else {
        deploymentStatus = statusFor(await pages('deployments/' + deployment.id + '/statuses'));
        state = !deploymentStatus ? 'deployment_missing' :
          ['failure', 'error', 'inactive'].includes(deploymentStatus.state) ? 'deployment_failed' :
          deploymentStatus.state !== 'success' ? 'deployment_running' :
          !['vercel[bot]', 'vercel'].includes(deploymentStatus.creator?.login) ||
          !validDeploymentUrl(deploymentStatus.environment_url) ? 'unverified' : 'live';
      }
    }
    // A later rerun or deployment cannot borrow an older green result. Re-read
    // the latest observation rather than trusting a local receipt or old run.
    if (signatures(runsFor(await pages(runPath, 'workflow_runs'), policy, source.main)) !== signatures(selected)) {
      return { ...base, state: 'changed', checks };
    }
    if (state === 'live') {
      const freshDeployment = productionFor(await pages('deployments?environment=Production'));
      if (!freshDeployment || freshDeployment.id !== deployment.id || freshDeployment.sha !== source.main) return { ...base, state: 'changed', checks };
      const freshStatus = statusFor(await pages('deployments/' + deployment.id + '/statuses'));
      if (!freshStatus || freshStatus.id !== deploymentStatus.id || freshStatus.state !== 'success' ||
          !['vercel[bot]', 'vercel'].includes(freshStatus.creator?.login) ||
          freshStatus.environment_url !== deploymentStatus.environment_url) return { ...base, state: 'changed', checks };
    }
    const currentMain = await get('git/ref/heads/main');
    if (currentMain?.object?.sha !== source.main || Date.now() >= deadline) return { ...base, state: 'changed', checks };
    const deployed = state === 'live';
    return { ...base, state: deployed && !base.sourceIndexable ? 'live_noindex' : state, checks, ciVerified, deploymentVerified: deployed,
      published: deployed && base.matchesLoadedVersion && base.sourceIndexable,
      deploymentId: deployment?.id || null, observedAt: new Date().toISOString() };
  } catch (_) {
    // Permission/quota/network/malformed evidence is unknown, not a green light.
    return { ...base, state: 'unverified' };
  }
}
