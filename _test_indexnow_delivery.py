"""IndexNow uses real delivery contracts and an isolated fake POST collector."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import unittest
from unittest import mock
import urllib.error

import _delivery as delivery
import _submit_indexnow as indexnow

SHA = 'a' * 40
OTHER = 'b' * 40
PUBLIC = 'https://chendermatologist.com/blog/acne-myths'


class EvidenceAPI:
    """Offline hosted response fixture; never obtains any credential."""
    def __init__(self):
        self.head = SHA
        self.runs = []
        self.jobs = {}
        for ordinal, entry in enumerate(delivery.policy()['workflows'], 1):
            self.runs.append(dict(id=ordinal, path=entry['path'], head_sha=SHA, head_branch='main',
                                  event='push', run_attempt=1, status='completed', conclusion='success',
                                  html_url=f'https://github.com/example/fixture/actions/runs/{ordinal}'))
            rows = []
            for job_number, name in enumerate(entry['jobs'], 1):
                skipped = name in entry.get('main_skips', [])
                required = entry['steps'][name]['required'] + entry['steps'][name].get('main_required', [])
                rows.append(dict(id=ordinal * 100 + job_number, name=name, status='completed',
                                 conclusion='skipped' if skipped else 'success',
                                 steps=[] if skipped else [dict(name=s, status='completed', conclusion='success')
                                                          for s in required]))
            self.jobs[ordinal] = rows
        self.deployment = dict(id=901, sha=SHA, environment='Production', production_environment=True,
                               creator={'login': 'vercel[bot]'})
        self.statuses = [dict(state='success', environment_url='https://fixture-production.vercel.app')]

    def get(self, path):
        if path == '/branches/main':
            return {'commit': {'sha': self.head}}
        raise AssertionError('Unexpected offline evidence GET')

    def pages(self, path, key=None):
        if path == '/actions/runs?head_sha=' + SHA:
            return deepcopy(self.runs)
        if path.startswith('/actions/runs/') and path.endswith('/attempts/1/jobs'):
            return deepcopy(self.jobs[int(path.split('/')[3])])
        if path == '/deployments?sha=' + SHA:
            return [deepcopy(self.deployment)]
        if path == '/deployments/901/statuses':
            return deepcopy(self.statuses)
        raise AssertionError('Unexpected offline evidence page')


class CollectorResponse:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'isolated collector response'


class IndexNowDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.output = StringIO()
        self.stack.enter_context(redirect_stdout(self.output))
        self.stack.enter_context(redirect_stderr(StringIO()))
        self.api = EvidenceAPI()
        self.api_constructor = self.stack.enter_context(mock.patch.object(delivery, 'API', return_value=self.api))
        self.clean = self.stack.enter_context(mock.patch.object(delivery, 'clean'))
        self.stack.enter_context(mock.patch('_cms_delivery.verify', return_value={'activeRequests': 0}))
        self.stack.enter_context(mock.patch('_site_settings_delivery.verify', return_value={'activeRequest': False}))
        self.stack.enter_context(mock.patch.object(indexnow, 'parse_sitemap_urls', return_value=[PUBLIC]))
        self.stack.enter_context(mock.patch.object(indexnow.time, 'sleep'))
        self.posts = []

        def collect(request, **options):
            self.assertEqual(request.full_url, indexnow.ENDPOINT)
            self.assertEqual(request.get_method(), 'POST')
            self.assertNotIn('Authorization', request.headers)
            self.posts.append(json.loads(request.data))
            return CollectorResponse(200)

        self.collect = collect
        self.transport = self.stack.enter_context(mock.patch.object(indexnow.urllib.request, 'urlopen', side_effect=collect))

    def test_verified_current_production_submits_only_public_deduplicated_urls(self):
        self.assertEqual(indexnow.submit([PUBLIC, PUBLIC], sha=SHA), 0)
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(self.posts[0]['urlList'], [PUBLIC])
        self.assertEqual(self.posts[0]['host'], 'chendermatologist.com')
        self.clean.assert_called_with(SHA)

    def test_invalid_or_zero_sha_never_obtains_credentials_or_posts(self):
        for sha in ['', 'main', SHA[:8], '0' * 40]:
            with self.subTest(sha=sha):
                self.assertEqual(indexnow.submit([PUBLIC], sha=sha), 2)
        self.api_constructor.assert_not_called()
        self.transport.assert_not_called()

    def test_dirty_or_changed_workspace_cannot_notify(self):
        self.clean.side_effect = delivery.Blocked('Dirty fixture')
        self.assertEqual(indexnow.submit([PUBLIC], sha=SHA), 2)
        self.api_constructor.assert_not_called()
        self.transport.assert_not_called()

    def test_query_fragment_foreign_private_or_noncanonical_url_cannot_notify(self):
        unsafe = [PUBLIC + '?q=patient-secret', PUBLIC + '#diagnosis', 'https://evil.example/health',
                  'http://chendermatologist.com/blog/acne-myths',
                  'https://chendermatologist.com/admin',
                  'https://name:secret@chendermatologist.com/blog/acne-myths',
                  'https://chendermatologist.com:443/blog/acne-myths',
                  'https://chendermatologist.com/blog/private-draft']
        for url in unsafe:
            with self.subTest(url=url):
                self.assertEqual(indexnow.submit([PUBLIC, url], sha=SHA), 2)
        self.api_constructor.assert_not_called()
        self.transport.assert_not_called()
        self.assertNotIn('patient-secret', self.output.getvalue())

    def test_candidate_or_stale_sha_cannot_notify(self):
        self.api.head = OTHER
        self.assertEqual(indexnow.submit([PUBLIC], sha=SHA), 2)
        self.transport.assert_not_called()

    def test_failed_pending_missing_cancelled_or_skipped_formal_workflow_cannot_notify(self):
        original = deepcopy(self.api.runs)
        for state in ['failure', 'cancelled', 'timed_out', 'skipped', 'in_progress', 'missing']:
            with self.subTest(state=state):
                self.api.runs = deepcopy(original)
                if state == 'missing':
                    self.api.runs.pop(0)
                elif state == 'in_progress':
                    self.api.runs[0].update(status=state, conclusion=None)
                else:
                    self.api.runs[0]['conclusion'] = state
                self.assertEqual(indexnow.submit([PUBLIC], sha=SHA), 2)
        self.transport.assert_not_called()

    def test_required_production_smoke_step_cannot_be_missing_skipped_or_failed(self):
        original = deepcopy(self.api.jobs)
        for state in ['missing', 'skipped', 'failure']:
            with self.subTest(state=state):
                self.api.jobs = deepcopy(original)
                smoke = next(j for rows in self.api.jobs.values() for j in rows if j['name'] == 'Production smoke')
                if state == 'missing':
                    smoke['steps'] = []
                else:
                    smoke['steps'][0]['conclusion'] = state
                self.assertEqual(indexnow.submit([PUBLIC], sha=SHA), 2)
        self.transport.assert_not_called()

    def test_wrong_sha_preview_or_foreign_deployment_cannot_notify(self):
        original = deepcopy(self.api.deployment)
        for change in [{'sha': OTHER}, {'environment': 'Preview'}, {'creator': {'login': 'untrusted-bot'}}]:
            with self.subTest(change=change):
                self.api.deployment = {**deepcopy(original), **change}
                self.assertEqual(indexnow.submit([PUBLIC], sha=SHA), 2)
        self.transport.assert_not_called()

    def test_failed_or_untrusted_production_status_cannot_notify(self):
        for status in [dict(state='failure', environment_url='https://fixture-production.vercel.app'),
                       dict(state='success', environment_url='https://evil.example'),
                       dict(state='success', environment_url='https://secret@fixture-production.vercel.app')]:
            with self.subTest(status=status):
                self.api.statuses = [status]
                self.assertEqual(indexnow.submit([PUBLIC], sha=SHA), 2)
        self.transport.assert_not_called()

    def test_main_advancement_during_evidence_verification_cannot_notify(self):
        original = self.api.pages

        def advance(path, key=None):
            result = original(path, key)
            if path.startswith('/deployments/'):
                self.api.head = OTHER
            return result

        self.api.pages = advance
        self.assertEqual(indexnow.submit([PUBLIC], sha=SHA), 2)
        self.transport.assert_not_called()

    def test_main_advancement_before_retry_blocks_second_post(self):
        def first(request, **options):
            response = self.collect(request, **options)
            self.api.head = OTHER
            response.status = 503
            return response

        self.transport.side_effect = first
        self.assertEqual(indexnow.submit([PUBLIC], sha=SHA), 2)
        self.assertEqual(len(self.posts), 1)

    def test_required_evidence_revocation_before_retry_blocks_second_post(self):
        def first(request, **options):
            response = self.collect(request, **options)
            self.api.runs[0]['conclusion'] = 'failure'
            response.status = 429
            return response

        self.transport.side_effect = first
        self.assertEqual(indexnow.submit([PUBLIC], sha=SHA), 2)
        self.assertEqual(len(self.posts), 1)

    def test_client_errors_still_fail_and_do_not_retry(self):
        for status in [400, 401, 403, 404, 413, 422]:
            with self.subTest(status=status):
                self.transport.reset_mock()
                self.transport.side_effect = lambda *a, **k: CollectorResponse(status)
                self.assertEqual(indexnow.submit([PUBLIC], sha=SHA), 1)
                self.assertEqual(self.transport.call_count, 1)

    def test_transient_indexnow_outage_remains_best_effort_after_verified_gate(self):
        for status in [429, 500, 502, 503, 504]:
            with self.subTest(status=status):
                self.transport.reset_mock()
                self.transport.side_effect = lambda *a, **k: CollectorResponse(status)
                self.assertEqual(indexnow.submit([PUBLIC], sha=SHA), 0)
                self.assertEqual(self.transport.call_count, 3)
        self.transport.reset_mock()
        self.transport.side_effect = TimeoutError('isolated network fixture')
        self.assertEqual(indexnow.submit([PUBLIC], sha=SHA), 0)
        self.assertEqual(self.transport.call_count, 3)

    def test_cli_requires_sha_and_rejects_ambiguous_scope(self):
        for argv in [[], ['--sha', SHA, '--since', '-1'], ['--sha', SHA, '--since', '7', PUBLIC]]:
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as error:
                indexnow.main(argv)
            self.assertEqual(error.exception.code, 2)
        self.transport.assert_not_called()

    def test_empty_scope_does_not_obtain_credentials_or_notify(self):
        self.assertEqual(indexnow.submit([], sha=SHA), 0)
        self.api_constructor.assert_not_called()
        self.transport.assert_not_called()

    def test_invalid_wait_is_rejected_before_evidence_or_post(self):
        for wait in [-1, 901, True, 1.5]:
            with self.subTest(wait=wait):
                self.assertEqual(indexnow.submit([PUBLIC], sha=SHA, wait=wait), 2)
        self.api_constructor.assert_not_called()
        self.transport.assert_not_called()


if __name__ == '__main__':
    unittest.main()
