"""Explicit final approval to a real isolated candidate; no hosted writes."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import _cms_generated_package as package
import _cms_patient_review as review
import _prepare_patient_review as preparation
import _test_patient_review_preparation as fixtures


class ReleaseTests(unittest.TestCase):
    original = fixtures.PreparationTests.original
    prepare_review = fixtures.PreparationTests.prepare

    def setUp(self):
        fixtures.PreparationTests.setUp(self)
        self.source_report = self.prepare_review()
        self.fixture.run_git('fetch','--no-write-fetch-head','--',str(self.output/'objects.bundle'),
                             preparation.REVIEW_REF)
        self.review_head = self.source_report['reviewHead']
        self.archive = self.output/'patient-package.zip'
        self.final_output = self.output.parent/'release'
        frozen = review.manifest((self.output/'review-manifest.json').read_bytes(),now=self.fixture.now)
        entry = {**self.source_report['sourceEvidence'],'version':2,'patientApproval':{
            'reviewHead':self.review_head,'manifestBlobSha':self.source_report['reviewBlobSha'],
            'manifestSha256':self.source_report['reviewManifestSha256'],
            'approvalHead':'a'*40,'approvalBlobSha':'b'*40,'approvedAt':'2026-09-30T11:00:00.000Z'}}
        self.request = review.expected_request(entry,frozen)
        (self.root/'.git/info/exclude').write_text('pagefind/\n__pycache__/\nnode_modules/\n',encoding='utf8')
        self.fixture.run_git('switch','drafts/article')
        self.store_request()
        self.fixture.run_git('checkout','--detach',self.fixture.base)

    def store_request(self):
        raw = (json.dumps(self.request,ensure_ascii=False,separators=(',',':'))+'\n').encode()
        self.fixture.write('.cms-requests/article.json',raw)
        self.fixture.commit('synthetic owner approves actual generated preview')
        self.approval = self.fixture.run_git('rev-parse','HEAD')

    def release(self, **changes):
        options = dict(root=self.root,output=self.final_output,approval_head=self.approval,
                       file='blog/article.html',expected_main=self.fixture.base,archive_path=self.archive,
                       now=self.fixture.now)
        options.update(changes)
        with patch.object(preparation,'EXECUTION_ROOT',self.root), \
             patch.object(preparation,'load_runtime',return_value=self.runtime), \
             patch.object(self.runtime.rebuild,'install_dependencies',return_value={'fixtureOnly':True}):
            return preparation.prepare_release(**options)

    def test_approved_bundle_rebuilds_complete_patient_outputs_and_preserves_original(self):
        before = self.original()
        result = self.release()
        self.assertEqual(before,self.original())
        self.assertEqual(result['state'],'approved_candidate_prepared')
        self.assertEqual(result['approvalHead'],self.approval)
        self.assertTrue(result['generationVerified'])
        self.assertTrue(result['finalAuthorIntentVerified'])
        self.assertTrue(result['contentApproved'])
        for field in ('independentReviewVerified','ciVerified','published'):
            self.assertIs(result[field],False)
        self.assertEqual(set(p.name for p in self.final_output.iterdir()),{'objects.bundle','report.json'})
        self.assertEqual(hashlib.sha256((self.final_output/'objects.bundle').read_bytes()).hexdigest(),result['objectsSha256'])
        self.assertEqual(json.loads((self.final_output/'report.json').read_bytes()),result)
        with self.runtime.rebuild.workspace(self.root) as temporary:
            imported = temporary/'imported'
            subprocess.run(['git','clone','--no-local','--single-branch','--branch','main','--no-checkout',
                            '--',str(self.root),str(imported)],check=True,capture_output=True)
            subprocess.run(['git','fetch','--no-write-fetch-head','--',str(self.final_output/'objects.bundle'),
                            preparation.RELEASE_REF],cwd=imported,check=True,capture_output=True)
            # The final author request is fetched separately, never included
            # as draft history in the generated candidate transport.
            self.assertNotEqual(subprocess.run(['git','cat-file','-e',self.approval],cwd=imported,capture_output=True).returncode,0)
            subprocess.run(['git','fetch','--no-write-fetch-head','--',str(self.root),self.approval],
                           cwd=imported,check=True,capture_output=True)
            api = package.GitEvidence(imported)
            _,receipt = self.runtime.candidate.read_blob(imported,result['candidateHead'],'.cms-delivery.json')
            entry = self.runtime.delivery.receipts(receipt,now=self.fixture.now)[0]
            self.assertEqual(entry['version'],2)
            review.verify_delivery(result['candidateHead'],api,entry,now=self.fixture.now)
            changed = subprocess.check_output(['git','diff','--name-only',self.review_head,result['candidateHead']],cwd=imported,text=True)
            self.assertEqual(changed.strip(),'.cms-delivery.json')

    def test_changed_archive_or_unapproved_request_cannot_create_candidate_artifacts(self):
        original = self.archive.read_bytes()
        self.archive.write_bytes(original+b'unapproved archive change')
        before = self.original()
        with self.assertRaisesRegex(ValueError,'archive differs'):
            self.release()
        self.assertEqual(before,self.original())
        self.assertFalse(self.final_output.exists())
        self.archive.write_bytes(original)
        self.fixture.run_git('switch','drafts/article')
        self.fixture.run_git('reset','--hard',self.source_report['requestHead'])
        self.request['contentApproved']=False
        self.store_request()
        self.fixture.run_git('checkout','--detach',self.fixture.base)
        with self.assertRaisesRegex(ValueError,'Final approval differs'):
            self.release()
        self.assertFalse(self.final_output.exists())

    def test_cancelled_request_and_wrong_pipeline_preserve_root(self):
        before=self.original()
        with self.assertRaisesRegex(ValueError,'Explicit pipeline'):
            self.release(expected_main=self.fixture.saved)
        self.assertEqual(before,self.original())
        self.fixture.run_git('update-ref','refs/heads/drafts/article',self.source_report['requestHead'])
        before=self.original()
        with self.assertRaisesRegex(ValueError,'cancelled or changed'):
            self.release()
        self.assertEqual(before,self.original())
        self.assertFalse(self.final_output.exists())

    def test_cancellation_during_regeneration_prevents_export(self):
        generate=self.runtime.rebuild.generate
        def cancel(*args,**kwargs):
            generate(*args,**kwargs)
            self.fixture.run_git('update-ref','refs/heads/drafts/article',self.source_report['requestHead'])
        with patch.object(self.runtime.rebuild,'generate',cancel),self.assertRaisesRegex(ValueError,'cancelled or changed'):
            self.release()
        self.assertFalse(self.final_output.exists())
        self.assertEqual(self.fixture.run_git('rev-parse','HEAD'),self.fixture.base)

    def test_linked_archive_and_dirty_original_never_execute_generation(self):
        linked=self.archive.parent/'linked.zip'
        os.link(self.archive,linked)
        with patch.object(self.runtime.rebuild,'generate') as generate, \
             self.assertRaisesRegex(ValueError,'ordinary bounded'):
            self.release(archive_path=linked)
        generate.assert_not_called()
        linked.unlink()
        self.fixture.write('user-notes.txt',b'Keep this unsaved file')
        before=self.original()
        with self.assertRaisesRegex(ValueError,'must be clean'):
            self.release()
        self.assertEqual(before,self.original())
        self.assertEqual((self.root/'user-notes.txt').read_bytes(),b'Keep this unsaved file')
        self.assertFalse(self.final_output.exists())

    def test_regeneration_drift_cannot_replace_approved_output(self):
        generate=self.runtime.rebuild.generate
        def mutate(checkout,*args,**kwargs):
            generate(checkout,*args,**kwargs)
            (checkout/'en/blog/article.html').write_bytes(b'Unapproved replacement fixture')
        before=self.original()
        with patch.object(self.runtime.rebuild,'generate',mutate),self.assertRaisesRegex(ValueError,'size|bytes differ'):
            self.release()
        self.assertEqual(before,self.original())
        self.assertFalse(self.final_output.exists())


if __name__ == '__main__':
    unittest.main()
