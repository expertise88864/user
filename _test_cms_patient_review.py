"""Final generated-content approval with real disposable, nonclinical Git history.

Both actual publication engines consume the same immutable repository responses.
No hosted requests, credentials, production analytics or author content changes.
"""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import unittest
import zipfile

import _cms_delivery as delivery
import _cms_generated_package as tracked
import _cms_patient_review as review
import _test_cms_patient_package as fixtures
from _test_cms_delivery import LocalAPI


class WorkspaceWorkflowTests(unittest.TestCase):
    def test_quality_build_and_receipt_share_exact_pr_head_not_merge_sha(self):
        workflow = (Path(__file__).resolve().parent / '.github/workflows/quality.yml').read_text(encoding='utf8')
        job = workflow.split('  feeds-regen:', 1)[1].split('  html-validate:', 1)[0]
        identity = '${{ github.event.pull_request.head.sha || github.sha }}'
        self.assertIn('ref: ' + identity, job)
        self.assertIn('BUILD_SHA: ' + identity, job)
        self.assertIn('persist-credentials: false', job)
        self.assertIn('env -u GH_TOKEN python _run_quality.py build', job)
        self.assertEqual(job.count('--workspace "$BUILD_SHA"'), 2)
        self.assertNotIn('--workspace "$GITHUB_SHA"', job)


class PatientReviewTests(unittest.TestCase):
    original_source = fixtures.PatientPackageTests.original_source
    run_git = fixtures.PatientPackageTests.run_git
    write = fixtures.PatientPackageTests.write
    commit = fixtures.PatientPackageTests.commit
    save_manifest = fixtures.PatientPackageTests.save_manifest
    store = fixtures.PatientPackageTests.store
    prepare = fixtures.PatientPackageTests.prepare
    capture = fixtures.PatientPackageTests.capture

    def setUp(self):
        fixtures.PatientPackageTests.setUp(self)
        # Match the trusted preparation checkout and Linux deployment. These
        # assertions bind raw output bytes, not checkout newline conversion.
        self.run_git('config', 'core.autocrlf', 'false')
        self.archive = self.capture()
        with zipfile.ZipFile(io.BytesIO(self.archive)) as package:
            self.descriptor = package.read('manifest.json')
        self.review_raw = review.create(self.descriptor, hashlib.sha256(self.archive).hexdigest(),
                                        '2026-09-30', now=self.now)
        self.review_path = review.review_path('blog/article.html')
        self.write(self.review_path, self.review_raw)
        self.commit('complete synthetic patient output review')
        self.review_head = self.run_git('rev-parse', 'HEAD')
        self.entry = {**self.proof, 'version': 2, 'patientApproval': {
            'reviewHead': self.review_head,
            'manifestBlobSha': self.run_git('rev-parse', self.review_head + ':' + self.review_path),
            'manifestSha256': hashlib.sha256(self.review_raw).hexdigest(),
            'approvalHead': 'a' * 40, 'approvalBlobSha': 'b' * 40,
            'approvedAt': '2026-09-30T11:00:00.000Z'}}
        # The synthetic baseline predates its generated .gitignore. Switching
        # to the source request must not accidentally stage ignored build files
        # in the author-only control commit.
        (self.root / '.git/info/exclude').write_text('pagefind/\n', encoding='utf8')
        self.run_git('switch', 'drafts/article')
        final = review.expected_request(self.entry, review.manifest(self.review_raw, now=self.now))
        self.write('.cms-requests/article.json', (json.dumps(final, separators=(',', ':'), ensure_ascii=False) + '\n').encode())
        self.commit('owner explicitly approves final generated fixture')
        approval = self.entry['patientApproval']
        approval['approvalHead'] = self.run_git('rev-parse', 'HEAD')
        approval['approvalBlobSha'] = self.run_git('rev-parse', 'HEAD:.cms-requests/article.json')
        self.run_git('switch', 'codex/cms-gate')
        self.write(delivery.FILE, tracked.encode({'version': 1, 'requests': [self.entry]}))
        self.commit('synthetic candidate binds final approval')
        self.candidate = self.run_git('rev-parse', 'HEAD')
        self.api = LocalAPI(self)
        # Establish a complete valid response closure before mutation. A Node
        # rejection must name a real gate, never a missing test response.
        delivery.verify(self.candidate, self.api, now=self.now)
        self.responses = {path: self.api.get(path) for path in dict.fromkeys(self.api.calls)}

    def both(self, passed=True, pattern=None):
        captured = {}; original = self.api.get
        # Node checks retirement history before parsing each individual entry;
        # Python parses the entries first. Both get real evidence for the new
        # candidate even when Python rejects its schema before querying history.
        preloaded = {}
        tree = self.run_git('rev-parse', self.candidate + '^{tree}')
        for path in ('/git/commits/' + self.candidate, '/git/trees/' + tree + '?recursive=1',
                     '/contents/' + delivery.FILE + '?ref=' + self.candidate,
                     '/compare/' + self.base + '...' + self.candidate):
            preloaded[path] = original(path)
        def capture(path):
            result = original(path)
            captured.setdefault(path, []).append(deepcopy(result))
            return result
        self.api.get = capture
        try:
            try:
                result = delivery.verify(self.candidate, self.api, now=self.now)
                python = {'passed': True, 'result': result}
            except Exception as error:
                python = {'passed': False, 'error': str(error)}
        finally:
            self.api.get = original
        responses = {**self.responses, **preloaded, **{p: rows[-1] for p, rows in captured.items()}}
        refs = {p: rows for p, rows in captured.items() if p.startswith('/git/ref/')}
        code = """const fs=require('node:fs'),v=require(process.argv[1]),i=JSON.parse(fs.readFileSync(0,'utf8'));
        v.verifyLiveIntent(i.sha, async p=>{const sequence=i.refs[p];
          if(sequence?.length) return sequence.shift();
          if(!Object.hasOwn(i.responses,p)) throw Error('MISSING_TEST_RESPONSE:'+p);
          return i.responses[p];},i.now)
          .then(r=>console.log(JSON.stringify({passed:true,result:r})))
          .catch(e=>console.log(JSON.stringify({passed:false,error:e.message})));"""
        module = Path(__file__).resolve().parent / '_cms_delivery.cjs'
        run = subprocess.run(['node', '-e', code, str(module)], input=json.dumps({
            'sha': self.candidate, 'responses': responses, 'refs': refs,
            'now': int(self.now.timestamp() * 1000)}), capture_output=True, text=True, encoding='utf8', timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        node = json.loads(run.stdout)
        self.assertNotIn('MISSING_TEST_RESPONSE', node.get('error', ''), node)
        self.assertEqual(python['passed'], passed, python)
        self.assertEqual(node['passed'], passed, node)
        if pattern:
            self.assertRegex(python.get('error', ''), pattern)
            self.assertRegex(node.get('error', ''), pattern)
        return python

    def change_candidate(self, path, raw):
        self.write(path, raw); self.commit('synthetic candidate mutation')
        self.candidate = self.run_git('rev-parse', 'HEAD')

    def test_complete_final_approval_passes_actual_python_and_node_without_writes(self):
        before = (self.run_git('show-ref'), self.run_git('status', '--porcelain'))
        result = self.both()['result']
        self.assertEqual(result['activeRequests'], 1)
        self.assertFalse(result['published'])
        self.assertEqual(before, (self.run_git('show-ref'), self.run_git('status', '--porcelain')))
        self.assertIn('/contents/' + self.review_path + '?ref=' + self.review_head, self.api.calls)

    def test_generated_english_summary_catalog_and_runtime_mutations_block_both(self):
        for path in ('en/blog/article.html', 'ai/fixture.json', 'assets/search-index.json', 'blog/article.html'):
            with self.subTest(path=path):
                original = (self.root / path).read_bytes()
                self.change_candidate(path, original + b' unapproved fixture change')
                self.both(False, 'Candidate differs|Candidate.*approved')
                self.change_candidate(path, original)
                self.both()

    def test_extra_or_missing_patient_output_blocks_both(self):
        self.change_candidate('extra-patient.html', b'<p>Unapproved fixture</p>')
        self.both(False, 'Candidate.*approved')
        self.run_git('rm', 'extra-patient.html', 'en/blog/article.html')
        self.commit('synthetic missing output'); self.candidate = self.run_git('rev-parse', 'HEAD')
        self.both(False, 'Candidate.*approved')

    def test_receipt_cannot_rewrite_final_approval_or_manifest_identity(self):
        for field in review.APPROVAL_FIELDS:
            with self.subTest(field=field):
                entry = deepcopy(self.entry)
                entry['patientApproval'][field] = 'wrong'
                self.change_candidate(delivery.FILE, tracked.encode({'version': 1, 'requests': [entry]}))
                self.both(False)

    def test_final_approval_requires_owner_confirmation_and_exact_original_request(self):
        request_path = '/contents/.cms-requests/article.json?ref=' + self.entry['patientApproval']['approvalHead']
        for field, value in [('contentApproved', False), ('approvedBy', 'another'),
                             ('sourceRequestHead', 'a' * 40), ('archiveSha256', 'b' * 64),
                             ('contentDate', '2026-09-29'), ('sourceRequest', {})]:
            def alter(path, data):
                if path == request_path:
                    raw = json.loads(__import__('base64').b64decode(data['content']))
                    raw[field] = value
                    # Altered data keeps the old blob identity, so both engines
                    # must reject the actual hash rather than trusting metadata.
                    data['content'] = __import__('base64').b64encode((json.dumps(raw, separators=(',', ':')) + '\n').encode()).decode()
                return data
            self.api.adjust = alter
            with self.subTest(field=field): self.both(False)

    def test_cancelled_or_newer_draft_never_reuses_final_approval(self):
        self.run_git('switch', 'drafts/article')
        self.run_git('rm', '.cms-requests/article.json')
        self.commit('owner withdraws final approval')
        self.run_git('switch', 'codex/cms-gate')
        self.both(False, 'cancelled or superseded')

    def test_valid_git_hashes_cannot_authorize_an_incorrect_confirmation_record(self):
        original = review.expected_request(self.entry, review.manifest(self.review_raw, now=self.now))
        for field, value in [('contentApproved', False), ('approvedBy', 'another'),
                             ('sourceRequestHead', 'a' * 40), ('archiveSha256', 'b' * 64),
                             ('contentDate', '2026-09-29'), ('sourceRequest', {}),
                             ('sourceRequest', {**original['sourceRequest'], 'contentApproved': 1}),
                             ('sourceRequest', {**original['sourceRequest'], 'version': True})]:
            with self.subTest(field=field):
                # Keep genuine Git objects and both digests consistent. This
                # tests the confirmation contract beyond transport corruption.
                altered = deepcopy(original); altered[field] = value
                self.run_git('checkout', '--detach', self.proof['requestHead'])
                self.write('.cms-requests/article.json', (json.dumps(altered, separators=(',', ':'), ensure_ascii=False) + '\n').encode())
                self.commit('synthetic invalid confirmation: ' + field)
                head = self.run_git('rev-parse', 'HEAD')
                blob = self.run_git('rev-parse', 'HEAD:.cms-requests/article.json')
                self.run_git('update-ref', 'refs/heads/drafts/article', head)
                self.run_git('switch', 'codex/cms-gate')
                entry = deepcopy(self.entry)
                entry['patientApproval'].update(approvalHead=head, approvalBlobSha=blob)
                self.change_candidate(delivery.FILE, tracked.encode({'version': 1, 'requests': [entry]}))
                self.both(False, 'approval|Approval|confirm|request|Request')

    def test_cancellation_during_validation_is_rechecked_by_both_engines(self):
        seen = []
        def alter(path, data):
            if path == '/git/ref/heads/drafts/article':
                seen.append(path)
                if len(seen) == 2: data['object']['sha'] = 'a' * 40
            return data
        self.api.adjust = alter
        self.both(False, 'cancelled or superseded')
        self.assertEqual(len(seen), 2)

    def test_manifest_is_full_canonical_and_originally_unapproved(self):
        value = review.manifest(self.review_raw, now=self.now)
        mutations = [lambda v: v.update(version=True), lambda v: v.update(extra=True),
                     lambda v: v.update(contentDate='2026-02-30'),
                     lambda v: v['patientManifest'].update(contentApproved=True),
                     lambda v: v['patientManifest']['extraFiles'].pop('pagefind/pagefind.js'),
                     lambda v: v['patientManifest']['trackedPackage']['files'].pop('en/blog/article.html'),
                     lambda v: v['patientManifest']['trackedPackage']['files']['blog/article.html'].update(mode='120000')]
        for mutate in mutations:
            changed = deepcopy(value); mutate(changed)
            with self.assertRaises(ValueError): review.manifest(tracked.encode(changed), now=self.now)
        for raw in (self.review_raw[:-1], b'{"version":1,"version":1}', self.review_raw + b'x'):
            with self.assertRaises(ValueError): review.manifest(raw, now=self.now)

    def test_local_git_evidence_verifies_the_same_immutable_review_history(self):
        result, blob, raw = review.load_review(tracked.GitEvidence(self.root), self.review_head,
                                              'blog/article.html', expected_source=self.proof, now=self.now)
        self.assertEqual(raw, self.review_raw)
        self.assertEqual(blob, self.entry['patientApproval']['manifestBlobSha'])
        self.assertEqual(result['patientManifest']['trackedPackage']['generatedHead'], self.generated)

    def test_actual_ignored_search_and_uncommitted_tracked_generation_are_bound(self):
        result = review.verify_workspace(self.root, self.candidate, self.api, now=self.now)
        self.assertEqual(result['patientPackages'], 1)
        self.assertGreater(result['outputFilesVerified'], 3)
        self.node_workspace()
        self.write('pagefind/pagefind.js', b'unapproved generated search fixture')
        with self.assertRaisesRegex(ValueError, 'ignored search outputs'):
            review.verify_workspace(self.root, self.candidate, self.api, now=self.now)
        self.node_workspace(False, 'output')
        self.write('pagefind/pagefind.js', b'export const fixture = true;\n')
        self.write('en/blog/article.html', b'<p>Unapproved rebuild</p>')
        with self.assertRaisesRegex(ValueError, 'tracked build outputs'):
            review.verify_workspace(self.root, self.candidate, self.api, now=self.now)
        self.node_workspace(False, 'output|file')

    def test_build_cannot_introduce_unrecorded_patient_files(self):
        self.write('untracked-patient.html', b'<p>Unapproved build fixture</p>')
        with self.assertRaisesRegex(ValueError, 'unrecorded files'):
            review.verify_workspace(self.root, self.candidate, self.api, now=self.now)
        self.node_workspace(False, 'added or omitted')

    def test_build_cannot_hide_unrecorded_files_in_ignored_directories(self):
        self.run_git('config', 'core.excludesFile', str(self.root / '.git' / 'fixture-excludes'))
        (self.root / '.git' / 'fixture-excludes').write_text('hidden-output/\n', encoding='utf8')
        self.write('hidden-output/patient.html', b'<p>Unapproved ignored fixture</p>')
        with self.assertRaisesRegex(ValueError, 'unrecorded files'):
            review.verify_workspace(self.root, self.candidate, self.api, now=self.now)
        self.node_workspace(False, 'added or omitted')

    def test_build_control_files_cannot_change_after_immutable_validation(self):
        for name, expected in ((delivery.FILE, 'receipt'), (self.review_path, 'manifest')):
            with self.subTest(name=name):
                original = (self.root/name).read_bytes()
                self.write(name, original + b' ')
                with self.assertRaisesRegex(ValueError, expected + ' differs'):
                    review.verify_workspace(self.root,self.candidate,self.api,now=self.now)
                self.node_workspace(False,'output')
                self.write(name,original)

    def node_workspace(self, passed=True, pattern=None, *, preview=False):
        responses = {**self.responses}
        for path in ('/contents/' + self.review_path + '?ref=' + self.candidate,
                     '/contents/' + delivery.FILE + '?ref=' + self.candidate):
            responses[path] = self.api.get(path)
        module = Path(__file__).resolve().parent / '_cms_patient_review.cjs'
        code = """const fs=require('node:fs'),v=require(process.argv[1]),i=JSON.parse(fs.readFileSync(0,'utf8'));
          v.verifyWorkspace(i.root,i.sha,async p=>{
            if(!Object.hasOwn(i.responses,p)) throw Error('MISSING_TEST_RESPONSE:'+p);return i.responses[p];},i.now,{preview:i.preview})
          .then(r=>console.log(JSON.stringify({passed:true,result:r})))
          .catch(e=>console.log(JSON.stringify({passed:false,error:e.message})));"""
        run = subprocess.run(['node','-e',code,str(module)], input=json.dumps({'root':str(self.root),
            'sha':self.candidate,'responses':responses,'now':int(self.now.timestamp()*1000),'preview':preview}),
            capture_output=True,text=True,encoding='utf8',timeout=30)
        self.assertEqual(run.returncode,0,run.stderr)
        result=json.loads(run.stdout)
        self.assertNotIn('MISSING_TEST_RESPONSE',result.get('error',''),result)
        self.assertEqual(result['passed'],passed,result)
        if pattern:self.assertRegex(result.get('error',''),pattern)
        return result

    def test_only_the_approved_manifest_can_set_the_generation_clock(self):
        self.assertEqual(review.frozen_content_date(self.root,now=self.now),'2026-09-30')
        self.write(self.review_path,self.review_raw+b' ')
        with self.assertRaisesRegex(ValueError,'differs from final approval'):
            review.frozen_content_date(self.root,now=self.now)

    def test_windows_checkout_preserves_exact_approval_control_bytes(self):
        attributes = Path(__file__).resolve().parent / '.gitattributes'
        self.write('.gitattributes', attributes.read_bytes())
        for name in (self.review_path, delivery.FILE):
            self.assertEqual(self.run_git('-c','core.autocrlf=true','check-attr','eol','--',name), name + ': eol: lf')
            (self.root/name).unlink()
            self.run_git('-c','core.autocrlf=true','checkout',self.candidate,'--',name)
        self.assertEqual((self.root/self.review_path).read_bytes(),self.review_raw)
        self.assertEqual(review.frozen_content_date(self.root,now=self.now),'2026-09-30')

    def test_preapproval_preview_checks_real_outputs_but_cannot_be_promoted(self):
        self.run_git('update-ref','refs/heads/drafts/article',self.proof['requestHead'])
        self.run_git('checkout','--detach',self.review_head)
        self.candidate=self.review_head
        self.assertEqual(review.frozen_content_date(self.root,now=self.now),'2026-09-30')
        self.api.calls.clear()
        delivery.verify_preparation(self.source,self.api,now=self.now)
        review.load_review(self.api,self.review_head,'blog/article.html',expected_source=self.proof,now=self.now)
        self.responses.update({p:self.api.get(p) for p in dict.fromkeys(self.api.calls)})
        self.assertFalse(review.verify_workspace(self.root, self.candidate, self.api, now=self.now, preview=True)['published'])
        with self.assertRaisesRegex(ValueError, 'final patient approval'):
            review.verify_workspace(self.root, self.candidate, self.api, now=self.now)
        self.assertFalse(self.node_workspace(preview=True)['result']['published'])
        with self.assertRaisesRegex(ValueError,'Final generated patient content approval'):
            delivery.verify(self.candidate,self.api,now=self.now)
        self.write('en/blog/article.html',b'<p>Unexpected Preview build change</p>')
        with self.assertRaisesRegex(ValueError, 'tracked build outputs'):
            review.verify_workspace(self.root, self.candidate, self.api, now=self.now, preview=True)
        self.node_workspace(False,'output|file',preview=True)

    def test_source_preparation_without_a_review_does_not_invent_a_date(self):
        self.run_git('checkout','--detach',self.source)
        self.assertIsNone(review.frozen_content_date(self.root,now=self.now))

    def test_preapproval_clock_rejects_wrong_source_or_noncanonical_manifest(self):
        self.run_git('checkout','--detach',self.review_head)
        self.write(self.review_path,self.review_raw+b' ')
        with self.assertRaises(ValueError):review.frozen_content_date(self.root,now=self.now)
        self.write(self.review_path,self.review_raw)
        value=json.loads((self.root/delivery.FILE).read_bytes())
        value['requests'][0]['requestedAt']='2026-09-30T09:00:00.000Z'
        self.write(delivery.FILE,tracked.encode(value))
        with self.assertRaisesRegex(ValueError,'another source request'):
            review.frozen_content_date(self.root,now=self.now)


if __name__ == '__main__':
    unittest.main()
