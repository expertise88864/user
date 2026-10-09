"""Discover genuine generated approvals in isolated nonclinical Git histories."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import _prepare_patient_review as preparation
import _process_article_requests as discovery
import _test_patient_release_preparation as fixtures


class PatientDiscoveryTests(unittest.TestCase):
    original = fixtures.ReleaseTests.original
    prepare_review = fixtures.ReleaseTests.prepare_review
    store_request = fixtures.ReleaseTests.store_request
    setUp = fixtures.ReleaseTests.setUp

    def process(self, output):
        with patch.object(preparation, 'EXECUTION_ROOT', self.root), \
             patch.object(preparation, 'load_runtime', return_value=self.runtime), \
             patch.object(self.runtime.rebuild, 'install_dependencies', return_value={'fixtureOnly': True}):
            return discovery.process(self.root, output, now=self.fixture.now)

    def replace_request(self, changes):
        # Only the fixture-owned temporary history is reset. The repository
        # under review and all real author/user files are untouched.
        self.assertTrue(self.root.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.fixture.run_git('switch', 'drafts/article')
        self.fixture.run_git('reset', '--hard', self.source_report['requestHead'])
        value = {**self.request, **changes}
        self.fixture.write('.cms-requests/article.json',
                           (json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf8'))
        self.fixture.commit('synthetic request variant')
        self.approval = self.fixture.run_git('rev-parse', 'HEAD')
        self.fixture.run_git('checkout', '--detach', self.fixture.base)

    def test_valid_final_approval_is_discovered_as_an_exact_candidate(self):
        before = self.original()
        output = self.output.parent / 'discovered'
        result = self.process(output)
        self.assertEqual(before, self.original())
        self.assertEqual(result['deferred'], [])
        self.assertEqual(len(result['prepared']), 1)
        row = result['prepared'][0]
        self.assertEqual(row['requestHead'], self.approval)
        self.assertEqual(row['state'], 'approved_candidate_prepared')
        for field in ('reviewVerified', 'ciVerified', 'published'):
            self.assertIs(row[field], False)
        package = output / row['artifacts']
        report = json.loads((package / 'report.json').read_bytes())
        self.assertEqual(report['approvalHead'], self.approval)
        self.assertEqual(report['archiveSha256'], self.source_report['archiveSha256'])
        self.assertEqual((package / 'patient-package.zip').read_bytes(), self.archive.read_bytes())
        with self.runtime.rebuild.workspace(self.root) as temporary:
            recipient = temporary / 'recipient'
            subprocess.run(['git', 'clone', '--no-hardlinks', '--no-checkout', str(self.root), str(recipient)],
                           check=True, capture_output=True)
            subprocess.run(['git', 'fetch', '--no-write-fetch-head', str(package / 'objects.bundle'),
                            preparation.RELEASE_REF], cwd=recipient, check=True, capture_output=True)
            changed = subprocess.check_output(['git', 'diff', '--name-only', self.review_head,
                                              report['candidateHead']], cwd=recipient).decode().splitlines()
            self.assertEqual(changed, ['.cms-delivery.json'])
        self.assertEqual(hashlib.sha256((package / 'objects.bundle').read_bytes()).hexdigest(), report['objectsSha256'])

    def test_original_download_is_not_needed_but_rebuilt_archive_is_byte_identical(self):
        expected = self.archive.read_bytes()
        self.archive.unlink()
        before = self.original()
        output = self.output.parent / 'without-original'
        result = self.process(output)
        row = result['prepared'][0]
        archive = output / row['artifacts'] / 'patient-package.zip'
        self.assertEqual(archive.read_bytes(), expected)
        self.assertEqual(before, self.original())

    def test_forged_final_requests_do_not_execute_generation(self):
        variants = [{'contentApproved': False}, {'manifestBlobSha': '0' * 40},
                    {'manifestSha256': '0' * 64}, {'archiveSha256': '0' * 64},
                    {'sourceRequestHead': '0' * 40}, {'approvedBy': 'not-the-author'},
                    {'approvedAt': '2030-01-01T00:00:00.000Z'}, {'unexpected': True},
                    {'contentDate': '2026-10-01'}, {'version': 2.0}, {'version': True}]
        for index, changes in enumerate(variants):
            with self.subTest(changes=changes):
                self.replace_request(changes)
                before = self.original()
                output = self.output.parent / ('forged-' + str(index))
                with patch.object(self.runtime.rebuild, 'generate') as generate:
                    result = self.process(output)
                self.assertFalse(result['prepared'])
                self.assertEqual(result['deferred'][0]['reason'], 'request_rejected')
                generate.assert_not_called()
                self.assertEqual(before, self.original())

    def test_older_pipeline_requires_new_preview_without_generation(self):
        self.fixture.write('unchanged.txt', b'New trusted pipeline revision')
        self.fixture.commit('trusted main advances after patient approval')
        current = self.fixture.run_git('rev-parse', 'HEAD')
        self.fixture.run_git('update-ref', 'refs/heads/main', current)
        before = self.original()
        with patch.object(self.runtime.rebuild, 'generate') as generate:
            result = self.process(self.output.parent / 'older-preview')
        self.assertFalse(result['prepared'])
        self.assertEqual(result['deferred'][0]['reason'], 'generated_review_requires_refresh')
        generate.assert_not_called()
        self.assertEqual(before, self.original())

    def test_generation_failure_is_not_misreported_as_rejected_author_intent(self):
        before = self.original()
        output = self.output.parent / 'generation-failed'
        with patch.object(self.runtime.rebuild, 'generate', side_effect=ValueError('controlled generation defect')):
            with self.assertRaisesRegex(ValueError, 'controlled generation defect'):
                self.process(output)
        self.assertFalse((output / 'report.json').exists())
        self.assertFalse(list(output.rglob('report.json')))
        self.assertEqual(before, self.original())

    def test_cancel_during_generation_prevents_success_report(self):
        generate = self.runtime.rebuild.generate
        def cancel(*args, **kwargs):
            generate(*args, **kwargs)
            self.fixture.run_git('update-ref', 'refs/heads/drafts/article', self.source_report['requestHead'])
        output = self.output.parent / 'cancelled'
        with patch.object(self.runtime.rebuild, 'generate', cancel):
            with self.assertRaisesRegex(ValueError, 'cancelled or changed'):
                self.process(output)
        self.assertFalse((output / 'report.json').exists())
        self.assertFalse(list(output.rglob('report.json')))
        self.assertEqual(self.fixture.run_git('rev-parse', 'HEAD'), self.fixture.base)

    def test_rebuilt_archive_drift_fails_without_a_candidate_report(self):
        before = self.original()
        record = self.runtime.patient.record
        def altered(*args, **kwargs):
            return record(*args, **kwargs) + b'Unapproved archive variant'
        output = self.output.parent / 'archive-drift'
        with patch.object(self.runtime.patient, 'record', altered):
            with self.assertRaisesRegex(ValueError, 'Rebuilt patient archive differs'):
                self.process(output)
        self.assertFalse((output / 'report.json').exists())
        self.assertFalse(list(output.rglob('report.json')))
        self.assertEqual(before, self.original())

    def test_missing_preview_is_rejected_while_another_valid_request_is_prepared(self):
        # A real missing SHA in a separate immutable author request must not
        # prevent the genuine article request from producing its exact bundle.
        self.fixture.run_git('switch', '-c', 'drafts/aaa-missing', self.source_report['requestHead'])
        invalid = {**self.request, 'file': 'blog/aaa-missing.html', 'reviewHead': 'd' * 40,
                   'sourceRequest': {**self.request['sourceRequest'], 'file': 'blog/aaa-missing.html'}}
        self.fixture.write('.cms-requests/aaa-missing.json',
                           (json.dumps(invalid, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf8'))
        self.fixture.commit('synthetic unavailable preview')
        missing = self.fixture.run_git('rev-parse', 'HEAD')
        self.fixture.run_git('checkout', '--detach', self.fixture.base)
        before = self.original()
        result = self.process(self.output.parent / 'missing-and-valid')
        self.assertEqual(before, self.original())
        self.assertEqual([row['requestHead'] for row in result['prepared']], [self.approval])
        self.assertEqual(result['deferred'], [{'file': 'blog/aaa-missing.html', 'requestHead': missing,
                                             'reason': 'request_rejected', 'errorType': 'ValueError'}])

    def test_preview_transport_failure_still_fails_the_job(self):
        fetch = discovery.immutable_source
        def unavailable(root, head):
            if head == self.review_head:
                raise subprocess.CalledProcessError(128, ['git', 'fetch'], stderr=b'controlled transport failure')
            return fetch(root, head)
        output = self.output.parent / 'transport-failed'
        before = self.original()
        with patch.object(discovery, 'immutable_source', unavailable):
            with self.assertRaises(subprocess.CalledProcessError):
                self.process(output)
        self.assertFalse((output / 'report.json').exists())
        self.assertEqual(before, self.original())

    def test_existing_commit_without_review_manifest_rejects_only_that_request(self):
        self.fixture.run_git('switch', '-c', 'drafts/aaa-missing', self.source_report['requestHead'])
        invalid = {**self.request, 'file': 'blog/aaa-missing.html', 'reviewHead': self.fixture.base,
                   'sourceRequest': {**self.request['sourceRequest'], 'file': 'blog/aaa-missing.html'}}
        self.fixture.write('.cms-requests/aaa-missing.json',
                           (json.dumps(invalid, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf8'))
        self.fixture.commit('synthetic existing preview without manifest')
        missing = self.fixture.run_git('rev-parse', 'HEAD')
        self.fixture.run_git('checkout', '--detach', self.fixture.base)
        before = self.original()
        result = self.process(self.output.parent / 'missing-manifest-and-valid')
        self.assertEqual(before, self.original())
        self.assertEqual([row['requestHead'] for row in result['prepared']], [self.approval])
        self.assertEqual(result['deferred'], [{'file': 'blog/aaa-missing.html', 'requestHead': missing,
                                             'reason': 'request_rejected', 'errorType': 'ValueError'}])


class ScheduledArtifactPathTests(unittest.TestCase):
    def test_workflow_artifacts_use_the_same_python_temporary_root(self):
        root = Path(__file__).resolve().parent
        workflow = (root / '.github/workflows/scheduled-publish.yml').read_text(encoding='utf8')
        step = workflow.split('      - name: Discover source requests and exact generated-content approvals\n')[1]
        step = step.split('      - name:', 1)[0]
        configured = bool(re.search(r'^          TMPDIR: \$\{\{ runner\.temp \}\}$', step, re.MULTILINE))
        with tempfile.TemporaryDirectory(prefix='patient-runner-path-') as directory:
            parent = Path(directory)
            runner, default = parent / 'runner-temp', parent / 'default-temp'
            runner.mkdir(); default.mkdir()
            artifacts = runner / 'cms-source-artifacts'
            artifacts.mkdir()
            environment = {**os.environ, 'RUNNER_TEMP': str(runner),
                           'TMPDIR': str(runner if configured else default), 'PYTHONDONTWRITEBYTECODE': '1'}
            # A fresh Python process follows its actual startup temp selection.
            # Runner temp and platform fallback are deliberately distinct.
            program = ('import sys; from pathlib import Path; '
                       'from _prepare_patient_review import artifact_destination; '
                       'print(artifact_destination(Path(sys.argv[1]), Path(sys.argv[2])))')
            valid = subprocess.run([sys.executable, '-c', program, str(artifacts / 'candidate'), str(root)],
                                   cwd=root, env=environment, capture_output=True, timeout=30)
            self.assertEqual(valid.returncode, 0, valid.stderr.decode('utf8', errors='replace'))
            outside = subprocess.run([sys.executable, '-c', program, str(default / 'candidate'), str(root)],
                                     cwd=root, env=environment, capture_output=True, timeout=30)
            self.assertNotEqual(outside.returncode, 0)
            self.assertIn(b'new directory in system temporary storage', outside.stderr)


if __name__ == '__main__':
    unittest.main()
