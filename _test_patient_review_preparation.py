"""Live local Git requests and complete disposable nonclinical package builds."""
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import _cms_patient_package as patient
import _cms_patient_rebuild as rebuild
import _prepare_patient_review as preparation
import _test_cms_patient_rebuild as fixtures


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RebuildTests('test_rebuild_compares_complete_raw_outputs_and_preserves_original_checkout')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        # The older replay fixture leaves main at its synthetic generated
        # commit. Operational preparation requires main at the trusted pipeline.
        for name,path in preparation.HELPER_PATHS.items():
            self.fixture.write(name,path.read_bytes())
        self.fixture.commit('trusted fixture preparation helpers')
        self.fixture.base=self.fixture.run_git('rev-parse','HEAD')
        self.fixture.run_git('update-ref','refs/heads/main',self.fixture.base)
        self.artifacts = tempfile.TemporaryDirectory(prefix='patient-review-test-')
        self.addCleanup(self.artifacts.cleanup)
        self.output = Path(self.artifacts.name) / 'review'
        with patch.object(preparation, 'EXECUTION_ROOT', self.root):
            self.runtime = preparation.load_runtime(
                self.root, preparation.trusted_runtime(self.root, self.fixture.base))

    def prepare(self, **changes):
        options = dict(root=self.root, output=self.output, request_head=self.fixture.head,
                       file='blog/article.html', expected_main=self.fixture.base,
                       content_date='2026-09-30', now=self.fixture.now)
        options.update(changes)
        # The tiny fixture has no dependencies. Source preparation, two actual
        # child generations, raw comparison and Git transport remain real.
        with patch.object(self.runtime.rebuild, 'install_dependencies', return_value={'fixtureOnly': True}), \
             patch.object(preparation,'EXECUTION_ROOT',self.root), \
             patch.object(preparation, 'load_runtime', return_value=self.runtime):
            return preparation.prepare(**options)

    def original(self):
        return (self.fixture.run_git('rev-parse', 'HEAD'), self.fixture.run_git('show-ref'),
                self.fixture.run_git('status', '--porcelain', '--untracked-files=all'))

    def test_complete_package_and_unreachable_objects_survive_transport_without_remote_writes(self):
        before = self.original()
        report = self.prepare()
        self.assertEqual(self.original(), before)
        self.assertEqual(set(p.name for p in self.output.iterdir()),
                         {'patient-package.zip', 'patient-manifest.json', 'objects.bundle', 'report.json'})
        self.assertEqual(report, json.loads((self.output/'report.json').read_text(encoding='utf8')))
        self.assertEqual(report['state'], 'awaiting_generated_content_approval')
        self.assertTrue(report['generationVerified'])
        for name in ('contentApproved','finalAuthorIntentVerified','ciVerified','published'):
            self.assertIs(report[name], False)
        archive = (self.output/'patient-package.zip').read_bytes()
        self.assertEqual(hashlib.sha256(archive).hexdigest(), report['archiveSha256'])
        with zipfile.ZipFile(io.BytesIO(archive)) as stored:
            self.assertEqual(stored.read('manifest.json'), (self.output/'patient-manifest.json').read_bytes())
            self.assertEqual(stored.read('files/unchanged.txt'), b'Keep source')
            self.assertNotIn('files/api/unrelated.js', stored.namelist())
            self.assertIn('files/en/blog/article.html', stored.namelist())
            self.assertIn('files/pagefind/fragment/example.pf_fragment', stored.namelist())
        # Generated commits exist only in the artifact, not the original repo.
        probe = subprocess.run(['git','cat-file','-e',report['generatedHead']],cwd=self.root,capture_output=True)
        self.assertNotEqual(probe.returncode,0)
        with rebuild.workspace(self.root) as temporary:
            imported = temporary/'imported'
            subprocess.run(['git','clone','--single-branch','--branch','main','--no-local',
                            '--no-checkout','--',str(self.root),str(imported)],
                           check=True,capture_output=True)
            unrelated=self.fixture.run_git('rev-parse',self.fixture.head+':api/unrelated.js')
            # A local optimized clone copies all objects even with single-branch;
            # force transport so this baseline starts with main objects only.
            self.assertNotEqual(subprocess.run(['git','cat-file','-e',unrelated],cwd=imported,
                                              capture_output=True).returncode,0)
            subprocess.run(['git','fetch','--no-write-fetch-head','--',str(self.output/'objects.bundle'),
                            preparation.GENERATED_REF],cwd=imported,
                           check=True,capture_output=True)
            self.assertNotEqual(subprocess.run(['git','cat-file','-e',unrelated],cwd=imported,
                                              capture_output=True).returncode,0)
            # Fetch the exact author request separately, as required by the
            # report. The draft code is present only as objects, never executed.
            subprocess.run(['git','fetch','--no-write-fetch-head','--',str(self.root),self.fixture.head],
                           cwd=imported,check=True,capture_output=True)
            result = patient.verify(imported, archive, now=self.fixture.now)
            self.assertEqual(result['files'],report['trackedFiles']+report['pagefindFiles'])
            self.assertFalse(result['contentApproved'])

    def test_same_frozen_inputs_keep_commit_and_complete_archive_identity(self):
        first = self.prepare()
        second = self.prepare(output=Path(self.artifacts.name)/'second')
        for field in ('pipelineHead','sourceHead','generatedHead','generatedTreeSha',
                      'archiveSha256','manifestSha256','contentDate'):
            self.assertEqual(first[field],second[field],field)

    def test_dirty_original_is_preserved_and_no_artifact_is_created(self):
        self.fixture.write('user-notes.txt',b'Keep my unsaved work')
        before=self.original()
        with self.assertRaisesRegex(ValueError,'must be clean'):
            self.prepare()
        self.assertEqual(self.original(),before)
        self.assertEqual((self.root/'user-notes.txt').read_bytes(),b'Keep my unsaved work')
        self.assertFalse(self.output.exists())

    def test_changed_main_or_cancelled_request_is_not_cached_approval(self):
        with self.assertRaisesRegex(ValueError,'Explicit pipeline'):
            self.prepare(expected_main=self.fixture.saved)
        self.fixture.run_git('update-ref','refs/heads/drafts/article',self.fixture.saved)
        with self.assertRaisesRegex(ValueError,'cancelled or changed'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_cancellation_during_generation_prevents_export(self):
        original=self.runtime.rebuild.generate
        calls=[]
        def cancel(checkout,*args):
            original(checkout,*args)
            calls.append(checkout)
            if len(calls)==1:
                self.fixture.run_git('update-ref','refs/heads/drafts/article',self.fixture.saved)
        with patch.object(self.runtime.rebuild,'generate',cancel),self.assertRaisesRegex(ValueError,'cancelled or changed'):
            self.prepare()
        self.assertFalse(self.output.exists())
        self.assertEqual((self.root/'blog/article.html').read_bytes(),self.fixture.original)

    def test_replay_mismatch_fails_before_artifact_writes(self):
        original=self.runtime.rebuild.generate
        calls=[]
        def different(checkout,*args):
            original(checkout,*args)
            calls.append(checkout)
            if len(calls)==2:
                (checkout/'feed.xml').write_bytes(b'Changed second-run fixture output')
        before=self.original()
        with patch.object(self.runtime.rebuild,'generate',different),self.assertRaisesRegex(ValueError,'different size|bytes differ'):
            self.prepare()
        self.assertEqual(self.original(),before)
        self.assertFalse(self.output.exists())

    def test_existing_inside_checkout_and_oversized_transport_are_rejected(self):
        self.output.mkdir();(self.output/'keep.txt').write_bytes(b'User output')
        with self.assertRaisesRegex(ValueError,'new directory'):
            self.prepare()
        self.assertEqual((self.output/'keep.txt').read_bytes(),b'User output')
        with self.assertRaisesRegex(ValueError,'new directory'):
            self.prepare(output=self.root/'review')
        with patch.object(preparation,'MAX_BUNDLE',1),self.assertRaisesRegex(ValueError,'transport exceeds'):
            self.prepare(output=Path(self.artifacts.name)/'too-large')
        self.assertFalse((Path(self.artifacts.name)/'too-large').exists())

    def test_invalid_clock_date_and_unpublish_do_not_turn_into_patient_approval(self):
        with self.assertRaisesRegex(ValueError,'timezone'):
            self.prepare(now=datetime(2026,9,30,12))
        with self.assertRaises(ValueError):
            self.prepare(content_date='2026-02-30')
        self.fixture.request.update(action='unpublish',contentApproved=False)
        self.fixture.store(amend=True)
        self.fixture.run_git('switch','--detach',self.fixture.base)
        with self.assertRaisesRegex(ValueError,'separate visibility-only'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_public_cli_rejects_dirty_input_before_dependency_installation(self):
        self.fixture.write('user.txt',b'Keep source')
        script=self.root/'_prepare_patient_review.py'
        result=subprocess.run([sys.executable,str(script),'--root',str(self.root),'--output',str(self.output),
                               '--request-head',self.fixture.head,'--file','blog/article.html',
                               '--expected-main',self.fixture.base,'--content-date','2026-09-30'],
                              capture_output=True,text=True,encoding='utf8',
                              env={**os.environ,'PYTHONUTF8':'1'})
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Trusted checkout must be clean',result.stderr)
        self.assertFalse(self.output.exists())

    def test_cross_checkout_cli_and_different_helper_version_are_rejected(self):
        script=Path(__file__).resolve().with_name('_prepare_patient_review.py')
        result=subprocess.run([sys.executable,str(script),'--root',str(self.root),'--output',str(self.output),
                               '--request-head',self.fixture.head,'--file','blog/article.html',
                               '--expected-main',self.fixture.base,'--content-date','2026-09-30'],
                              capture_output=True,text=True,encoding='utf8',env={**os.environ,'PYTHONUTF8':'1'})
        self.assertNotEqual(result.returncode,0)
        self.assertIn('execute from the trusted checkout itself',result.stderr)
        helper = self.root / '_cms_delivery.py'
        helper.write_bytes(helper.read_bytes()+b'\n# changed helper bytes\n')
        with self.assertRaisesRegex(ValueError,'must be clean'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_cancellation_after_writing_report_retires_success_marker(self):
        writer=preparation.write_artifacts
        def cancel_after_report(output,files,check,patient):
            calls=[]
            def current():
                calls.append(1)
                if len(calls)==5:
                    self.fixture.run_git('update-ref','refs/heads/drafts/article',self.fixture.saved)
                check()
            return writer(output,files,current,patient)
        with patch.object(preparation,'write_artifacts',cancel_after_report),self.assertRaisesRegex(ValueError,'cancelled or changed'):
            self.prepare()
        self.assertTrue((self.output/'patient-package.zip').is_file())
        self.assertFalse((self.output/'report.json').exists())

    def test_public_cli_does_not_execute_dirty_helper_import_code(self):
        marker = Path(self.artifacts.name) / 'import-executed.txt'
        helper = self.root / '_cms_delivery.py'
        helper.write_bytes(helper.read_bytes() +
                          ('\nfrom pathlib import Path\nPath(' + repr(str(marker)) +
                           ').write_text("Harmless fixture marker")\n').encode('utf8'))
        result = subprocess.run(
            [sys.executable, str(self.root / '_prepare_patient_review.py'),
             '--root', str(self.root), '--output', str(self.output),
             '--request-head', self.fixture.head, '--file', 'blog/article.html',
             '--expected-main', self.fixture.base, '--content-date', '2026-09-30'],
            capture_output=True, text=True, encoding='utf8', env={**os.environ, 'PYTHONUTF8': '1'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Trusted checkout must be clean', result.stderr)
        self.assertFalse(marker.exists())
        self.assertFalse(self.output.exists())

    def test_runtime_uses_verified_source_not_global_cached_helpers_or_pyc(self):
        import py_compile
        import types
        helper = self.root / '_cms_delivery.py'
        original = helper.read_bytes()
        marker = Path(self.artifacts.name) / 'cached-code-executed.txt'
        helper.write_bytes(original + ('\nfrom pathlib import Path\nPath(' + repr(str(marker)) +
                                      ').write_text("Harmless cache marker")\n').encode('utf8'))
        py_compile.compile(str(helper), invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
        helper.write_bytes(original)
        foreign = types.ModuleType('_cms_delivery')
        foreign.REPO = 'wrong/cached-repository'
        existing = sys.modules['_cms_delivery']
        with patch.dict(sys.modules, {'_cms_delivery': foreign}), \
             patch.object(preparation, 'EXECUTION_ROOT', self.root):
            runtime = preparation.load_runtime(
                self.root, preparation.trusted_runtime(self.root, self.fixture.base))
        self.assertEqual(runtime.delivery.REPO, 'expertise88864/user')
        self.assertFalse(marker.exists())
        self.assertIs(sys.modules['_cms_delivery'], existing)

    def test_output_normalizes_safe_parent_and_rejects_link_alias(self):
        parent = Path(self.artifacts.name)
        (parent / 'child').mkdir()
        normalized = preparation.artifact_destination(parent / 'child' / '..' / 'review', self.root)
        self.assertEqual(normalized, parent.resolve() / 'review')
        # Junctions do not require Windows developer-mode/symlink privilege.
        alias = parent / 'alias'
        if os.name == 'nt':
            result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(alias), str(parent)],
                                    capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            alias.symlink_to(parent, target_is_directory=True)
        try:
            with self.assertRaisesRegex(ValueError, 'ordinary parent'):
                preparation.artifact_destination(alias / 'review', self.root)
        finally:
            # Remove only the verified link itself, never its target tree.
            self.assertEqual(alias.resolve(), parent.resolve())
            if os.name == 'nt':
                alias.rmdir()
            else:
                alias.unlink()

    def test_early_request_planning_does_not_execute_inherited_node_options(self):
        marker = Path(self.artifacts.name) / 'preload-executed.txt'
        preload = Path(self.artifacts.name) / 'preload.cjs'
        preload.write_text("require('node:fs').writeFileSync(" + json.dumps(str(marker)) +
                           ", 'Harmless local test marker');", encoding='utf8')
        options = '--require ' + json.dumps(str(preload))
        with patch.dict(os.environ, {'NODE_OPTIONS': options, 'NODE_PATH': str(preload.parent)}):
            files, proof = self.runtime.request.request_plan(
                self.root, self.fixture.head, 'blog/article.html',
                self.fixture.request['blobSha'], now=self.fixture.now)
            self.assertEqual(os.environ['NODE_OPTIONS'], options)
            self.assertEqual(proof['preparedAgainst'], self.fixture.base)
            self.assertIn('blog/article.html', files)
        self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
