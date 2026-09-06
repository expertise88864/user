"""Wait for the exact pushed SHA's applicable GitHub workflows and checks."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

REQUIRED = {'.github/workflows/quality.yml', '.github/workflows/hyperlink.yml'}


def assess(runs, checks, statuses):
    # A rerun supersedes the earlier attempt, but only for the same workflow/event.
    latest = {}
    for run in sorted(runs, key=lambda item:(item['id'], item.get('run_attempt', 1))):
        latest[(run['path'], run['event'])] = run
    missing = REQUIRED - {item['path'] for item in latest.values()}
    pending = [f'missing workflow: {path}' for path in sorted(missing)]
    failures = []
    for run in latest.values():
        if run['status'] != 'completed':
            pending.append(run['html_url'])
        elif run['conclusion'] != 'success':
            failures.append(f"{run['conclusion']}: {run['html_url']}")
    for check in checks:
        if check['status'] != 'completed':
            pending.append(check['html_url'])
        elif check['conclusion'] != 'success':
            failures.append(f"{check['conclusion']}: {check['html_url']}")
    contexts = {}
    for status in reversed(statuses):
        contexts[status['context']] = status
    for status in contexts.values():
        if status['state'] == 'pending':
            pending.append(status['target_url'] or status['context'])
        elif status['state'] != 'success':
            failures.append(f"{status['state']}: {status['target_url'] or status['context']}")
    return pending, failures


def main():
    if len(sys.argv) != 2 or not re.fullmatch('[0-9a-f]{40}', sys.argv[1]):
        print('Usage: python _verify_remote_ci.py <full commit SHA>')
        return 2
    sha = sys.argv[1]
    def api(path):
        return json.loads(subprocess.check_output(['gh','api',path], text=True, encoding='utf-8'))
    repo = json.loads(subprocess.check_output(['gh','repo','view','--json','nameWithOwner'],
                                             text=True))['nameWithOwner']
    prefix = f'repos/{repo}'
    output = Path(tempfile.mkdtemp(prefix='dermnotes-remote-ci-')) / 'checks.json'
    print(f'Verifying {repo}@{sha}; evidence: {output}', flush=True)
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        runs = api(f'{prefix}/actions/runs?head_sha={sha}&per_page=100')['workflow_runs']
        checks = api(f'{prefix}/commits/{sha}/check-runs?filter=latest&per_page=100')['check_runs']
        statuses = api(f'{prefix}/commits/{sha}/statuses?per_page=100')
        if any(item.get('head_sha') != sha for item in runs + checks):
            raise RuntimeError('GitHub returned evidence for a different SHA')
        pending, failures = assess(runs, checks, statuses)
        # Refuse silent truncation rather than claim a partial page is complete.
        if len(runs) >= 100 or len(checks) >= 100 or len(statuses) >= 100:
            failures.append('CI response requires pagination; verify the complete result before delivery')
        output.write_text(json.dumps({'sha':sha,'runs':runs,'checks':checks,'statuses':statuses,
                                     'pending':pending,'failures':failures}, indent=2), encoding='utf-8')
        if failures:
            print('\n'.join(failures), flush=True)
            return 1
        if not pending:
            print(f'All applicable GitHub checks passed for {sha}', flush=True)
            return 0
        print(f'{len(pending)} check(s) pending for {sha}', flush=True)
        time.sleep(20)
    print('Timed out waiting for GitHub CI; delivery is not complete', flush=True)
    return 1


if __name__ == '__main__':
    sys.exit(main())
