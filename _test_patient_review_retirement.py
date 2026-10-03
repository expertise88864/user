"""Published v2 review retirement and later drafts in disposable Git only.

Formal CI/deployment responses are fixtures. No remote or patient-content writes.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import _cms_delivery as delivery
import _cms_generated_package as package
import _cms_retirement as retirement
import _retire_cms_receipts as bundle
import _test_cms_patient_review as reviews
import _test_cms_retirement as fixtures
import _test_patient_review_preparation as preparation_fixtures
import _prepare_patient_review as preparation
import _cms_patient_review as review
from _prepare_article_candidate import apply as apply_sources


class PatientRetirementTests(unittest.TestCase):
    def setUp(self):
        class PublishedReview(reviews.PatientReviewTests):
            def commit(case, message):
                if message == 'main baseline':
                    case.policy = json.loads(Path('_delivery_policy.json').read_text(encoding='utf8'))
                    case.write('_delivery_policy.json', package.encode(case.policy))
                    case.write('.cms-review/other.json', b'{"fixture":"unrelated retained control"}\n')
                    for name in ('_cms_delivery.py', '_cms_retirement.py', '_retire_cms_receipts.py',
                                 '_cms_patient_review.py', '_cms_patient_package.py', '_cms_generated_package.py',
                                 '_prepare_article_candidate.py', '_validate_article_request.py'):
                        case.write(name, Path(name).read_bytes())
                return super().commit(message)
        self.case = PublishedReview()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        case = self.case
        case.published = case.candidate
        case.run_git('update-ref', 'refs/heads/main', case.published)
        case.api = fixtures.PublicationAPI(case)
        case.verify = lambda: delivery.verify(case.candidate, case.api, now=case.now)
        self.files = retirement.prepare(case.api, case.published, now=case.now)
        self.archive = retirement.PREFIX + case.published + '.json'

    def test_retirement_records_exact_manifest_removal_and_keeps_immutable_history(self):
        case = self.case
        record = json.loads(self.files[self.archive])
        self.assertEqual(record['version'], 2)
        self.assertEqual(record['reviewManifests'], {
            case.review_path: {'blobSha': case.entry['patientApproval']['manifestBlobSha'],
                               'sha256': hashlib.sha256(case.review_raw).hexdigest()}})
        before = case.run_git('show-ref')
        bundle.apply(case.root, self.files, expected_head=case.published, now=case.now)
        self.assertEqual(case.run_git('show-ref'), before)
        case.commit('retire exact published review fixture')
        case.candidate = case.run_git('rev-parse', 'HEAD')
        result = fixtures.RetirementTests.both(case)
        self.assertEqual(result['activeRequests'], 0)
        self.assertFalse((case.root / case.review_path).exists())
        self.assertEqual(case.run_git('diff', '--name-only', case.published, case.candidate).splitlines(),
                         sorted([*self.files, case.review_path]))
        self.assertEqual(package.run(case.root, 'show', case.published + ':' + case.review_path), case.review_raw)
        self.assertEqual(package.run(case.root, 'show', case.review_head + ':' + case.review_path), case.review_raw)
        self.assertEqual((case.root / '.cms-review/other.json').read_bytes(), b'{"fixture":"unrelated retained control"}\n')

    def test_forged_archive_identities_and_schema_block_application_and_both_live_gates(self):
        case = self.case
        original = json.loads(self.files[self.archive])
        mutations = [
            lambda r: r.update(version=1),
            lambda r: r.update(version=True),
            lambda r: r.update(reviewManifests={}),
            lambda r: r['reviewManifests'][case.review_path].update(blobSha='a' * 40),
            lambda r: r['reviewManifests'][case.review_path].update(sha256='b' * 64),
            lambda r: r['reviewManifests'].update({'.cms-review/other.json': {'blobSha': 'a' * 40, 'sha256': 'b' * 64}}),
            lambda r: r.update(requests=[]),
            lambda r: r.update(receiptBlobSha='a' * 40),
            lambda r: r.update(preparedAt='2099-01-01T00:00:00.000Z'),
            lambda r: r.update(extra=True),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                case.run_git('switch', '--detach', case.published)
                value = deepcopy(original)
                mutate(value)
                files = {**self.files, self.archive: package.encode(value)}
                before = (case.run_git('show-ref'), case.run_git('status', '--porcelain'))
                with self.assertRaises(ValueError):
                    bundle.apply(case.root, files, expected_head=case.published, now=case.now)
                self.assertEqual(before, (case.run_git('show-ref'), case.run_git('status', '--porcelain')))
                self.assertFalse((case.root / self.archive).exists())
                apply_sources(case.root, files, expected_head=case.published)
                case.run_git('rm', case.review_path)
                case.commit('forged retirement fixture')
                case.candidate = case.run_git('rev-parse', 'HEAD')
                fixtures.RetirementTests.both(case, False)

    def test_retained_replaced_or_unrelated_removed_controls_block_both_live_gates(self):
        case = self.case
        for action in ('retain', 'replace', 'remove-other', 'change-patient'):
            with self.subTest(action=action):
                case.run_git('switch', '--detach', case.published)
                apply_sources(case.root, self.files, expected_head=case.published)
                if action == 'replace':
                    case.write(case.review_path, b'{"replacement":true}\n')
                elif action in ('remove-other', 'change-patient'):
                    case.run_git('rm', case.review_path)
                    if action == 'remove-other':
                        case.run_git('rm', '.cms-review/other.json')
                    else:
                        case.write('en/blog/article.html', b'<p>Unapproved fixture</p>')
                case.commit('wrong control retirement fixture')
                case.candidate = case.run_git('rev-parse', 'HEAD')
                fixtures.RetirementTests.both(case, False)

    def test_published_manifest_bytes_or_modes_cannot_be_forged_as_retirable(self):
        case = self.case
        original = case.published
        for action in ('changed', 'noncanonical', 'executable'):
            with self.subTest(action=action):
                case.run_git('switch', '--detach', original)
                if action == 'changed':
                    case.write(case.review_path, case.review_raw + b' ')
                elif action == 'noncanonical':
                    case.write(case.review_path, json.dumps(json.loads(case.review_raw)).encode())
                else:
                    case.run_git('update-index', '--chmod=+x', case.review_path)
                    # Do not run add -A, which could normalize the staged mode.
                    case.run_git('commit', '-m', 'invalid published mode fixture')
                if action != 'executable':
                    case.commit('invalid published manifest fixture')
                case.published = case.run_git('rev-parse', 'HEAD')
                case.run_git('update-ref', 'refs/heads/main', case.published)
                with self.assertRaises(ValueError):
                    retirement.prepare(case.api, case.published, now=case.now)

    def test_local_revision_dirty_workspace_and_linked_control_fail_before_writes(self):
        case = self.case
        with self.assertRaises(ValueError):
            bundle.apply(case.root, self.files, expected_head='a' * 40, now=case.now)
        case.write('user.txt', b'Keep user edits')
        with self.assertRaises(ValueError):
            bundle.apply(case.root, self.files, expected_head=case.published, now=case.now)
        (case.root / 'user.txt').unlink()
        with tempfile.TemporaryDirectory(prefix='review-control-hardlink-') as folder:
            outside = Path(folder) / 'same-control.json'
            os.link(case.root / case.review_path, outside)
            self.assertEqual(case.run_git('status', '--porcelain'), '')
            with self.assertRaisesRegex(ValueError, 'ordinary'):
                bundle.apply(case.root, self.files, expected_head=case.published, now=case.now)
            self.assertEqual(outside.read_bytes(), case.review_raw)
        self.assertFalse((case.root / self.archive).exists())
        self.assertEqual(case.run_git('status', '--porcelain'), '')
        with tempfile.TemporaryDirectory(prefix='receipt-control-hardlink-') as folder:
            outside = Path(folder) / 'same-receipt.json'
            receipt_before = (case.root / delivery.FILE).read_bytes()
            os.link(case.root / delivery.FILE, outside)
            with self.assertRaisesRegex(ValueError, 'ordinary'):
                bundle.apply(case.root, self.files, expected_head=case.published, now=case.now)
            self.assertEqual(outside.read_bytes(), receipt_before)
        for files in ({**self.files, '../unsafe': b'x'}, {**self.files, case.review_path: b'x'}):
            with self.assertRaises(ValueError):
                bundle.apply(case.root, files, expected_head=case.published, now=case.now)

    def test_ignored_existing_archive_is_never_overwritten(self):
        case = self.case
        with (case.root / '.git/info/exclude').open('a', encoding='utf8') as output:
            output.write('.cms-retirements/\n')
        case.write(self.archive, b'Keep private existing artifact')
        self.assertEqual(case.run_git('status', '--porcelain'), '')
        with self.assertRaisesRegex(ValueError, 'unarchived'):
            bundle.apply(case.root, self.files, expected_head=case.published, now=case.now)
        self.assertEqual((case.root / self.archive).read_bytes(), b'Keep private existing artifact')
        self.assertTrue((case.root / case.review_path).is_file())

    def test_actual_public_apply_cli_uses_external_bundle_without_staging_or_ref_writes(self):
        case = self.case
        before = case.run_git('show-ref')
        with tempfile.TemporaryDirectory(prefix='patient-retirement-bundle-') as folder:
            target = Path(folder) / 'bundle'
            bundle.write_bundle(case.root, target, case.published, self.files)
            self.assertEqual(bundle.load_bundle(case.root, target, case.published), self.files)
            run = subprocess.run([sys.executable, '-B', str(case.root / '_retire_cms_receipts.py'),
                                  '--expected-main', case.published, '--apply', str(target)],
                                 cwd=case.root, capture_output=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            self.assertEqual(result['removedPaths'], [case.review_path])
            self.assertTrue(result['sourceApplied'])
            for key in ('reviewPassed', 'candidateCIPassed', 'published', 'bundleWritten'):
                self.assertFalse(result[key])
        self.assertEqual(case.run_git('show-ref'), before)
        self.assertEqual(case.run_git('diff', '--cached', '--name-only'), '')
        self.assertFalse((case.root / case.review_path).exists())
        self.assertEqual((case.root / self.archive).read_bytes(), self.files[self.archive])


class NextPatientCycleTests(unittest.TestCase):
    def test_second_complete_preparation_after_retirement_gets_fresh_review_and_preserves_archive(self):
        trial = preparation_fixtures.PreparationTests()
        trial.setUp()
        self.addCleanup(trial.doCleanups)
        case = trial.fixture
        # Match the immutable transport, Linux build and ordinary control-file
        # contract. Windows checkout conversion is not a valid raw-byte proof.
        case.run_git('config', 'core.autocrlf', 'false')
        case.policy = json.loads(Path('_delivery_policy.json').read_text(encoding='utf8'))
        case.write('_delivery_policy.json', package.encode(case.policy))
        case.commit('trusted second-cycle formal policy fixture')
        case.base = case.run_git('rev-parse', 'HEAD')
        case.run_git('update-ref', 'refs/heads/main', case.base)
        (case.root / '.git/info/exclude').write_text('pagefind/\nnode_modules/\n__pycache__/\n', encoding='utf8')
        first = trial.prepare()
        case.run_git('fetch', '--no-write-fetch-head', '--', str(trial.output / 'objects.bundle'),
                     preparation.GENERATED_REF, preparation.REVIEW_REF)
        first_raw = (trial.output / 'review-manifest.json').read_bytes()
        entry = {**first['sourceEvidence'], 'version': 2, 'patientApproval': {
            'reviewHead': first['reviewHead'], 'manifestBlobSha': first['reviewBlobSha'],
            'manifestSha256': first['reviewManifestSha256'], 'approvalHead': 'a' * 40,
            'approvalBlobSha': 'b' * 40, 'approvedAt': '2026-09-30T11:00:00.000Z'}}
        case.run_git('switch', 'drafts/article')
        case.write('.cms-requests/article.json',
                   (json.dumps(review.expected_request(entry, review.manifest(first_raw, now=case.now)),
                               separators=(',', ':'), ensure_ascii=False) + '\n').encode())
        case.commit('owner final confirmation fixture')
        entry['patientApproval']['approvalHead'] = case.run_git('rev-parse', 'HEAD')
        entry['patientApproval']['approvalBlobSha'] = case.run_git('rev-parse', 'HEAD:.cms-requests/article.json')
        case.run_git('switch', '--detach', first['reviewHead'])
        case.write(delivery.FILE, package.encode({'version': 1, 'requests': [entry]}))
        case.commit('synthetic first publication candidate')
        case.candidate = case.run_git('rev-parse', 'HEAD')
        self.assertEqual(delivery.verify(case.candidate, fixtures.fixture.LocalAPI(case), now=case.now)['activeRequests'], 1)
        case.published = case.candidate
        case.run_git('update-ref', 'refs/heads/main', case.published)
        case.api = fixtures.PublicationAPI(case)
        files = retirement.prepare(case.api, case.published, now=case.now)
        bundle.apply(case.root, files, expected_head=case.published, now=case.now)
        case.commit('synthetic first review retirement')
        case.candidate = case.run_git('rev-parse', 'HEAD')
        self.assertEqual(delivery.verify(case.candidate, case.api, now=case.now)['activeRequests'], 0)
        retired = case.candidate
        case.run_git('update-ref', 'refs/heads/main', retired)
        archive_path = retirement.PREFIX + case.published + '.json'
        archive_before = (case.root / archive_path).read_bytes()
        # Simulate the author's next save and explicit source request, preserving
        # the existing draft history while rebinding its current published base.
        case.run_git('switch', 'drafts/article')
        case.run_git('rm', '.cms-requests/article.json')
        case.write('blog/article.html', package.run(case.root, 'show', retired + ':blog/article.html') +
                   b'<!-- second nonclinical author edit -->')
        case.commit('next author edit fixture')
        case.blob = case.run_git('rev-parse', 'HEAD:blog/article.html')
        case.base_blob = case.run_git('rev-parse', retired + ':blog/article.html')
        case.record.update(baseMain=retired, baseSha=case.base_blob, blobSha=case.blob)
        case.save_manifest()
        case.saved = case.run_git('rev-parse', 'HEAD')
        case.base = retired
        case.request = {'version': 1, 'file': 'blog/article.html', 'action': 'review',
                        'draftHead': case.saved, 'manifestSha': case.run_git('rev-parse', 'HEAD:.cms-drafts/article.json'),
                        'blobSha': case.blob, 'baseSha': case.base_blob, 'approvedBy': 'expertise88864',
                        'contentApproved': True, 'requestedAt': '2026-09-30T11:30:00.000Z', 'scheduledAt': None}
        case.store()
        before = trial.original()
        second = trial.prepare(output=Path(trial.artifacts.name) / 'second-review')
        self.assertEqual(trial.original(), before)
        self.assertEqual(second['pipelineHead'], retired)
        self.assertEqual(second['sourceEvidence']['requestHead'], case.head)
        self.assertNotEqual(second['reviewHead'], first['reviewHead'])
        self.assertNotEqual(second['reviewManifestSha256'], first['reviewManifestSha256'])
        self.assertTrue(second['generationVerified'])
        for key in ('contentApproved', 'finalAuthorIntentVerified', 'ciVerified', 'published'):
            self.assertFalse(second[key])
        self.assertEqual((case.root / archive_path).read_bytes(), archive_before)
        self.assertEqual(package.run(case.root, 'show', case.published + ':' + first['reviewPath']), first_raw)



if __name__ == '__main__':
    unittest.main()
