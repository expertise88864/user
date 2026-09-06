"""Release failure paths, with no network or real Git mutations."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import io
from contextlib import redirect_stdout
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from _verify_remote_ci import REQUIRED, assess

ROOT = Path(__file__).resolve().parent


class RemoteEvidenceTests(unittest.TestCase):
    def runs(self):
        return [dict(id=i, path=p, event='push', status='completed', conclusion='success',
                     html_url=f'https://example.test/{i}') for i,p in enumerate(sorted(REQUIRED))]

    def test_no_evidence_is_not_success(self):
        pending, failed = assess([], [], [])
        self.assertTrue(pending)
        self.assertFalse(failed)

    def test_complete_success(self):
        self.assertEqual(assess(self.runs(), [], []), ([], []))

    def test_failure_cancellation_and_timeout_are_not_success(self):
        for conclusion in ('failure', 'cancelled', 'timed_out', 'skipped', None):
            runs = self.runs()
            runs[0]['conclusion'] = conclusion
            self.assertTrue(assess(runs, [], [])[1], conclusion)

    def test_pending_status_and_external_failure_are_not_success(self):
        status = dict(context='deploy', state='pending', target_url='https://example.test/deploy')
        self.assertTrue(assess(self.runs(), [], [status])[0])
        check = dict(name='external', status='completed', conclusion='failure', html_url='https://example.test/check')
        self.assertTrue(assess(self.runs(), [check], [])[1])

    def test_rerun_supersedes_failed_attempt(self):
        runs = self.runs()
        old = dict(runs[0], conclusion='failure', run_attempt=1)
        runs[0]['run_attempt'] = 2
        self.assertEqual(assess([old] + runs, [], []), ([], []))


class ScheduledPublicationTests(unittest.TestCase):
    def execute(self, fail_script=None):
        source = (ROOT / '.github/workflows/scheduled-publish.yml').read_text(encoding='utf-8')
        program = textwrap.dedent(source.split("python3 <<'PY'\n", 1)[1].rsplit('          PY', 1)[0])
        calls = []
        def check(command, **kwargs):
            calls.append(command)
            if fail_script and fail_script in command:
                raise subprocess.CalledProcessError(1, command)
            return 0
        def run(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=0 if 'ls-remote' in command else 1,
                                   stdout='abc refs/heads/drafts/example\n', stderr='')
        def output(command, **kwargs):
            calls.append(command)
            if 'ls-files' in command:
                return 'en/blog/example.html\n' if fail_script == 'untracked' else ''
            return 'a' * 40
        with tempfile.TemporaryDirectory(prefix='scheduled-fixture-') as directory:
            root = Path(directory)
            queue = root / '.github/scheduled-publish/queue.json'
            queue.parent.mkdir(parents=True)
            queue.write_text(json.dumps([dict(slug='example', branch='drafts/example',
                file='blog/example.html', at='2000-01-01T00:00:00Z')]), encoding='utf-8')
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch('subprocess.check_call', side_effect=check), patch('subprocess.run', side_effect=run), \
                        patch('subprocess.check_output', side_effect=output), \
                        patch.dict(os.environ, {'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1','RUNNER_TEMP':directory}), \
                        redirect_stdout(io.StringIO()):
                    if fail_script:
                        with self.assertRaises((subprocess.CalledProcessError, RuntimeError)):
                            exec(compile(program, 'scheduled-publish.yml', 'exec'), {})
                    else:
                        exec(compile(program, 'scheduled-publish.yml', 'exec'), {})
            finally:
                os.chdir(previous)
        return calls

    def test_failed_local_ci_cannot_publish_or_delete_drafts(self):
        calls = self.execute('_run_ci.py')
        self.assertFalse(any('push' in command for command in calls), calls)

    def test_success_prepares_review_bundle_without_publishing_or_claiming_review(self):
        calls = self.execute()
        self.assertTrue(any(command[:3] == ['git','bundle','create'] for command in calls), calls)
        self.assertFalse(any('push' in command or '--delete' in command for command in calls), calls)
        self.assertFalse(any('Claude-Opus-5-Review: pending' in str(command) for command in calls), calls)

    def test_untracked_generated_file_cannot_publish(self):
        calls = self.execute('untracked')
        self.assertFalse(any('push' in command for command in calls), calls)


@unittest.skipUnless(shutil.which('pwsh') or shutil.which('powershell'), 'PowerShell is required')
class DeploymentTests(unittest.TestCase):
    def execute(self, scenario):
        with tempfile.TemporaryDirectory(prefix='release-fixture-') as directory:
            root = Path(directory)
            shutil.copy2(ROOT / 'deploy.ps1', root / 'deploy.ps1')
            driver = r'''
$ErrorActionPreference = 'Stop'
$global:statusCalls = 0
function git {
    Add-Content -LiteralPath calls.txt -Value ('git ' + ($args -join ' '))
    $global:LASTEXITCODE = 0
    switch ($args[0]) {
        'branch' { 'main' }
        'status' {
            $global:statusCalls++
            if ($env:RELEASE_SCENARIO -eq 'dirty' -or ($env:RELEASE_SCENARIO -eq 'build-drift' -and $global:statusCalls -gt 1)) { ' M article.html' }
        }
        'rev-parse' { if ($args[1] -eq 'HEAD') { 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' } else { 'true' } }
        'push' { if ($env:RELEASE_SCENARIO -eq 'push-blocked') { $global:LASTEXITCODE = 1 } }
    }
}
function gh { $global:LASTEXITCODE = 0 }
function python {
    Add-Content -LiteralPath calls.txt -Value ('python ' + ($args -join ' '))
    $global:LASTEXITCODE = 0
    if (($env:RELEASE_SCENARIO -eq 'ci-failed' -and ($args -contains 'candidate')) -or
        ($env:RELEASE_SCENARIO -eq 'remote-failed' -and ($args -contains 'main')) -or
        ($env:RELEASE_SCENARIO -eq 'deploy-failed' -and ($args -contains 'production')) -or
        ($env:RELEASE_SCENARIO -eq 'smoke-failed' -and ($args -contains 'smoke'))) { $global:LASTEXITCODE = 1 }
}
& ./deploy.ps1
exit $LASTEXITCODE
'''
            (root / 'driver.ps1').write_text(driver, encoding='utf-8')
            result = subprocess.run([shutil.which('pwsh') or shutil.which('powershell'),
                                     '-NoProfile', '-File', str(root / 'driver.ps1')], cwd=root,
                                    env={**os.environ, 'RELEASE_SCENARIO':scenario},
                                    capture_output=True, text=True, encoding='utf-8', errors='replace')
            calls = (root / 'calls.txt').read_text(encoding='utf-8-sig')
            return result.returncode, calls, result.stdout + result.stderr

    def test_failures_before_push_preserve_work_and_do_not_publish(self):
        for scenario in ('dirty','ci-failed','build-drift'):
            code, calls, output = self.execute(scenario)
            self.assertNotEqual(code, 0, output)
            for forbidden in ('git push','git add','git stash','git rebase','git checkout','git commit'):
                self.assertNotIn(forbidden, calls, scenario)

    def test_remote_failure_is_not_delivery(self):
        code, calls, output = self.execute('remote-failed')
        self.assertNotEqual(code, 0, output)
        self.assertIn('git push origin aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:refs/heads/main', calls)
        self.assertNotIn('Delivered ', output)

    def test_complete_release_order(self):
        code, calls, output = self.execute('success')
        self.assertEqual(code, 0, output)
        self.assertLess(calls.index('--phase candidate'), calls.index('git push'))
        self.assertLess(calls.index('git push'), calls.index('--phase main'))
        self.assertLess(calls.index('--phase main'), calls.index('_delivery.py production'))
        self.assertLess(calls.index('_delivery.py production'), calls.index('_delivery.py smoke'))

    def test_production_failure_is_not_delivery(self):
        for scenario in ('deploy-failed', 'smoke-failed'):
            code, calls, output = self.execute(scenario)
            self.assertNotEqual(code, 0, output)
            self.assertNotIn('Delivered ', output)


if __name__ == '__main__':
    unittest.main()
