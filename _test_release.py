"""Release failure paths; Git writes stay in disposable fixtures, never hosted."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import shlex
import io
from contextlib import redirect_stdout
import unittest
from unittest.mock import patch

from types import SimpleNamespace

import _delivery as delivery

ROOT = Path(__file__).resolve().parent


class RemoteEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.sha = 'a' * 40
        # Exercise the actual six-workflow contract. PR and live author approval
        # are independently covered by _test_delivery.py; this collector is offline.
        self.cfg = {**delivery.policy(), 'require_pr': False}
        self.runs = []
        self.jobs = {}
        for index, entry in enumerate(self.cfg['workflows'], 1):
            self.runs.append(dict(id=index, path=entry['path'], event='push',
                                  head_sha=self.sha, head_branch='codex/release-fixture',
                                  run_attempt=1, status='completed', conclusion='success',
                                  html_url=f'https://example.test/{index}'))
            skips = entry.get('candidate_skips', [])
            self.jobs[index] = [dict(
                id=index * 100 + offset, name=name, status='completed',
                conclusion='skipped' if name in skips else 'success',
                steps=[dict(name=step, status='completed', conclusion='success')
                       for step in entry['steps'][name]['required']
                       + entry['steps'][name].get('candidate_required', [])],
            ) for offset, name in enumerate(entry['jobs'])]

    def verify(self):
        def pages(path, key):
            if key == 'workflow_runs':
                self.assertEqual(path, f'/actions/runs?head_sha={self.sha}')
                return self.runs
            self.assertEqual(key, 'jobs')
            run_id = int(path.split('/')[3])
            return self.jobs[run_id]
        with patch('_cms_delivery.verify', return_value={}), \
                patch('_site_settings_delivery.verify', return_value={}):
            evidence = delivery.verify(self.sha, 'candidate', self.cfg,
                                       SimpleNamespace(pages=pages))
        return [record for record in evidence if 'run_id' in record]

    def test_no_evidence_is_not_success(self):
        self.runs = []
        with self.assertRaises(delivery.Blocked):
            self.verify()

    def test_complete_success(self):
        evidence = self.verify()
        self.assertEqual(len(evidence), len(self.cfg['workflows']))
        self.assertEqual({record['run_id'] for record in evidence}, set(self.jobs))
        self.assertTrue(all(record['sha'] == self.sha for record in evidence))

    def test_failure_cancellation_and_timeout_are_not_success(self):
        for conclusion in ('failure', 'cancelled', 'timed_out', 'skipped', None):
            with self.subTest(conclusion=conclusion):
                self.runs[0]['conclusion'] = conclusion
                with self.assertRaises(delivery.Blocked):
                    self.verify()

    def test_pending_or_failed_job_and_step_are_not_success(self):
        job = self.jobs[1][0]
        for field, value in (('status', 'in_progress'), ('conclusion', 'failure')):
            with self.subTest(field=field):
                original = job[field]
                job[field] = value
                with self.assertRaises(delivery.Blocked):
                    self.verify()
                job[field] = original
        for conclusion in ('pending', 'failure', 'cancelled', 'timed_out', 'skipped', None):
            with self.subTest(step=conclusion):
                job['steps'][0]['conclusion'] = conclusion
                with self.assertRaises(delivery.Blocked):
                    self.verify()

    def test_rerun_supersedes_failed_attempt(self):
        old = dict(self.runs[0], conclusion='failure', run_attempt=1)
        self.runs[0]['run_attempt'] = 2
        self.runs.insert(0, old)
        self.assertEqual(len(self.verify()), len(self.cfg['workflows']))
        self.runs[1]['conclusion'] = 'failure'
        self.runs[0]['conclusion'] = 'success'
        with self.assertRaises(delivery.Blocked):
            self.verify()

    def test_missing_any_workflow_cannot_be_replaced_by_other_green_runs(self):
        complete = self.runs[:]
        for absent in complete:
            with self.subTest(path=absent['path']):
                self.runs = [run for run in complete if run is not absent]
                with self.assertRaises(delivery.Blocked):
                    self.verify()

    def test_wrong_sha_branch_or_event_cannot_supply_evidence(self):
        run = self.runs[0]
        for field, value in (('head_sha', 'b' * 40), ('head_branch', 'main'),
                             ('event', 'pull_request')):
            with self.subTest(field=field):
                original = run[field]
                run[field] = value
                with self.assertRaises(delivery.Blocked):
                    self.verify()
                run[field] = original


class ScheduledPublicationTests(unittest.TestCase):
    def setUp(self):
        from _test_scheduled_candidate import ScheduledCandidateTests
        self.fixture = ScheduledCandidateTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.output = Path(self.fixture.artifacts.name) / 'cms-source-artifacts'

    def execute(self, fail_preparation=False):
        import _process_article_requests as requests
        source = (ROOT / '.github/workflows/scheduled-publish.yml').read_text(encoding='utf-8')
        commands = [line.strip()[len('run: '):] for line in source.splitlines()
                    if line.strip().startswith('run: ')]
        self.assertEqual([shlex.split(command) for command in commands], [
            ['python', '_process_article_requests.py', '--output', '$RUNNER_TEMP/cms-source-artifacts'],
            ['python', '_process_site_settings_requests.py', '--output', '$RUNNER_TEMP/site-settings-source-artifacts'],
        ], 'Review every operational workflow command')
        command = shlex.split(commands[0])
        self.assertEqual(command, ['python', '_process_article_requests.py', '--output',
                                   '$RUNNER_TEMP/cms-source-artifacts'])
        fixture = self.fixture
        calls = []
        actual_run, actual_git = subprocess.run, requests.git

        def run(argv, **kwargs):
            calls.append(list(argv))
            self.assertFalse(argv[0] == 'git' and ('push' in argv or '--delete' in argv), argv)
            return actual_run(argv, **kwargs)

        def git(root, *args):
            # Only the runner's identity check is stubbed. Transport and bundle
            # content use real Git against the isolated local fixture origin.
            if args == ('remote', 'get-url', 'origin'):
                return ('https://github.com/' + requests.REPO).encode()
            return actual_git(root, *args)

        output = io.StringIO()
        argv = [command[1], command[2], str(fixture.output)]
        env = {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': requests.REPO,
               'GITHUB_REF': 'refs/heads/main', 'RUNNER_TEMP': fixture.artifacts.name}
        with patch.object(requests, '__file__', str(fixture.root / command[1])), \
                patch('sys.argv', argv), patch.dict(os.environ, env), \
                patch.object(requests, 'git', side_effect=git), \
                patch('subprocess.run', side_effect=run), redirect_stdout(output):
            if fail_preparation:
                with patch.object(requests, 'unchanged_main', side_effect=ValueError('Main advanced')):
                    with self.assertRaisesRegex(ValueError, 'Main advanced'):
                        requests.main()
            elif (fixture.root / 'en/blog/example.html').exists():
                with self.assertRaisesRegex(ValueError, 'Trusted checkout must be clean'):
                    requests.main()
            else:
                requests.main()
        return calls, output.getvalue()

    def test_failed_preparation_cannot_publish_or_delete_drafts(self):
        calls, output = self.execute(fail_preparation=True)
        self.assertFalse(any('push' in command for command in calls), calls)
        self.assertFalse(output)
        self.assertFalse(list(self.fixture.output.glob('*.bundle')))
        self.assertFalse((self.fixture.output / 'report.json').exists())
        self.fixture.assert_preserved()

    def test_success_prepares_review_bundle_without_publishing_or_claiming_review(self):
        calls, output = self.execute()
        self.assertTrue(any(command[:3] == ['git','bundle','create'] for command in calls), calls)
        self.assertFalse(any('push' in command or '--delete' in command for command in calls), calls)
        self.assertFalse(any('Claude-Opus-5-Review: pending' in str(command) for command in calls), calls)
        self.assertEqual(json.loads(output), {'prepared': 1, 'deferred': 0,
                         'reviewVerified': False, 'ciVerified': False, 'published': False})
        report = json.loads((self.fixture.output / 'report.json').read_text(encoding='utf-8'))
        destination = self.fixture.recipient(report['prepared'][0])
        self.assertEqual((destination / 'blog/article.html').read_bytes(), self.fixture.content)
        self.assertEqual((destination / self.fixture.image_path).read_bytes(), self.fixture.image)
        self.assertFalse((destination / 'api/unrelated.js').exists())
        self.fixture.assert_preserved()

    def test_untracked_generated_file_cannot_publish(self):
        self.fixture.write('en/blog/example.html', b'<h1>Untracked generated output</h1>')
        status = self.fixture.run_git('status', '--porcelain')
        calls, output = self.execute()
        self.assertFalse(any('push' in command for command in calls), calls)
        self.assertFalse(output)
        self.assertFalse(self.fixture.output.exists())
        self.assertEqual(self.fixture.run_git('status', '--porcelain'), status)
        self.assertEqual(self.fixture.run_git('show-ref'), self.fixture.refs)
        self.assertEqual((self.fixture.root / '.github/scheduled-publish/queue.json').read_bytes(), self.fixture.queue)


class ScheduledSettingsPublicationTests(unittest.TestCase):
    def execute(self, fail_preparation=False):
        import _process_site_settings_requests as requests
        from _test_site_settings_preparation import GitFixture
        source = (ROOT / '.github/workflows/scheduled-publish.yml').read_text(encoding='utf8')
        commands = [shlex.split(line.strip()[len('run: '):]) for line in source.splitlines()
                    if line.strip().startswith('run: ')]
        self.assertEqual(commands, [
            ['python', '_process_article_requests.py', '--output', '$RUNNER_TEMP/cms-source-artifacts'],
            ['python', '_process_site_settings_requests.py', '--output', '$RUNNER_TEMP/site-settings-source-artifacts'],
        ])
        with tempfile.TemporaryDirectory(prefix='release-settings-fixture-') as directory:
            parent=Path(directory);fixture=GitFixture(parent/'trusted');fixture.approval()
            fixture.command('remote','add','origin','https://github.com/'+requests.REPO)
            refs=fixture.command('show-ref');out=parent/'site-settings-source-artifacts';calls=[]
            actual_run=subprocess.run
            def run(argv, **kwargs):
                calls.append(list(argv))
                self.assertFalse(argv[0]=='git' and any(arg in argv for arg in ('push','--delete','merge')),argv)
                return actual_run(argv, **kwargs)
            def entry():
                if fail_preparation:
                    with patch.object(requests,'source_bundle',side_effect=ValueError('Invalid prepared bundle')):
                        with self.assertRaisesRegex(ValueError,'Invalid prepared bundle'):requests.main()
                else:requests.main()
            output=io.StringIO()
            env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':requests.REPO,'GITHUB_REF':'refs/heads/main','RUNNER_TEMP':directory}
            with patch.object(requests,'ROOT',fixture.root), patch.dict(os.environ,env), \
                    patch('sys.argv',[commands[1][1],'--output',str(out)]), \
                    patch('_delivery.API',return_value=fixture), patch('subprocess.run',side_effect=run), redirect_stdout(output):
                entry()
            self.assertEqual(fixture.command('show-ref'),refs)
            self.assertEqual(fixture.command('status','--porcelain').strip(),b'')
            self.assertFalse(any('Claude-Opus-5-Review: pending' in str(command) for command in calls))
            if fail_preparation:
                self.assertEqual(output.getvalue(),'');self.assertFalse((out/'report.json').exists())
            else:
                self.assertEqual(json.loads(output.getvalue()),{'prepared':1,'deferred':0,'reviewVerified':False,'ciVerified':False,'published':False})
                report=json.loads((out/'report.json').read_text(encoding='utf8'))
                self.assertEqual(len(report['prepared']),1)
                self.assertTrue((out/report['prepared'][0]['bundle']).is_file())

    def test_settings_workflow_command_prepares_source_only_with_fixed_runner_context(self):
        self.execute()

    def test_settings_workflow_failure_is_not_delivery_or_a_deferred_request(self):
        self.execute(fail_preparation=True)


@unittest.skipUnless(os.name == 'nt', 'Legacy domain entrypoints are Windows-only')
class DomainEntrypointSafetyTests(unittest.TestCase):
    def execute(self, entrypoint):
        with tempfile.TemporaryDirectory(prefix='retired-domain-fixture-') as directory:
            root = Path(directory)
            for script in ('set-domain.ps1', 'set-domain.bat'):
                shutil.copy2(ROOT / script, root / script)
            protected = {
                'index.html': '<link rel="canonical" href="https://old-domain.example/">',
                'AGENTS.md': 'User rules for old-domain.example',
                'CLAUDE.md': 'User rules for old-domain.example',
                'REMOTE_CI_DELIVERY.md': 'User rules for old-domain.example',
                '.codex-review/evidence.json': '{"original":"old-domain.example"}',
                '.git/config': '[remote "origin"]\nurl = https://old-domain.example/',
                'node_modules/fixture.json': '{"host":"old-domain.example"}',
                'en/index.html': '<a href="https://old-domain.example/">Generated</a>',
            }
            for name, value in protected.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(value.encode('utf8'))
            before = {str(path.relative_to(root)): path.read_bytes()
                      for path in root.rglob('*') if path.is_file()}
            if entrypoint == 'powershell':
                binary = shutil.which('pwsh') or shutil.which('powershell')
                self.assertIsNotNone(binary, 'Windows must execute the real PowerShell entrypoint')
                argv = [binary, '-NoProfile', '-File', str(root / 'set-domain.ps1'),
                        '-NewDomain', 'new-domain.example']
            else:
                argv = [os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c',
                        str(root / 'set-domain.bat'), 'new-domain.example']
            result = subprocess.run(argv, cwd=root, input=b'', stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=15)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(b'Retired bulk domain replacement', result.stderr)
            after = {str(path.relative_to(root)): path.read_bytes()
                     for path in root.rglob('*') if path.is_file()}
            self.assertEqual(after, before, 'Retired helpers must preserve every file and create no evidence')

    def test_powershell_preserves_rules_evidence_sources_and_generated_files(self):
        self.execute('powershell')

    def test_batch_preserves_failure_and_never_mutates_files(self):
        self.execute('batch')


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
        ($env:RELEASE_SCENARIO -eq 'smoke-failed' -and ($args -contains 'main'))) { $global:LASTEXITCODE = 1 }
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
        # Hosted smoke is a required main step, before the final deployment resolution.
        import _delivery
        workflow = next(w for w in _delivery.policy()['workflows'] if w['path'] == '.github/workflows/delivery.yml')
        self.assertIn('Production smoke', workflow['jobs'])
        self.assertNotIn('Production smoke', workflow['main_skips'])
        self.assertIn('Verify exact-SHA production pages and assets', workflow['steps']['Production smoke']['required'])
        self.assertIn('hosted smoke checks verified', output)

    def test_production_failure_is_not_delivery(self):
        for scenario in ('deploy-failed', 'smoke-failed'):
            code, calls, output = self.execute(scenario)
            self.assertNotEqual(code, 0, output)
            self.assertNotIn('Delivered ', output)


if __name__ == '__main__':
    unittest.main()
