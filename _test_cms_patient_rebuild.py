"""Actual isolated subprocess replay on disposable, nonclinical Git histories."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import _cms_delivery as delivery
import _cms_generated_package as package
import _cms_patient_package as patient
import _cms_patient_rebuild as rebuild
from _prepare_article_candidate import apply
import _test_article_request as request_fixtures


class RebuildTests(unittest.TestCase):
    original_source = request_fixtures.RequestTests.original_source
    run_git = request_fixtures.RequestTests.run_git
    write = request_fixtures.RequestTests.write
    commit = request_fixtures.RequestTests.commit
    save_manifest = request_fixtures.RequestTests.save_manifest
    store = request_fixtures.RequestTests.store
    prepare = request_fixtures.RequestTests.prepare

    def setUp(self):
        request_fixtures.RequestTests.setUp(self)
        here = Path(__file__).resolve().parent
        # A tiny trusted fixture pipeline executes in the child; no production
        # prose, packages, credentials, network or actual site generator runs.
        for name in ('_prepare_article_candidate.py', '_cms_delivery.py'):
            self.write(name, (here / name).read_bytes())
        self.write('.gitignore', b'pagefind/\nnode_modules/\n__pycache__/\nignored/\n')
        self.write('package.json', b'{"private":true}\n')
        self.write('package-lock.json', b'{"name":"fixture","lockfileVersion":3}\n')
        self.generator = (
            'from pathlib import Path\n'
            'p=Path("blog/article.html");p.write_bytes(p.read_bytes()+b"<!-- fixture generated -->")\n'
            'outputs={"en/blog/article.html":b"<html><p>Fixture translation</p></html>",'
            '"assets/search-index.json":b"{\\"fixture\\":true}\\n",'
            '"ai/fixture.json":b"{\\"summary\\":\\"Fixture only\\"}\\n",'
            '"feed.xml":b"<feed>Fixture only</feed>",'
            '"pagefind/pagefind.js":b"export const fixture=true;\\n",'
            '"pagefind/fragment/example.pf_fragment":b"Fixture search text\\0"}\n'
            'for name,raw in outputs.items():\n'
            ' p=Path(name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)\n'
        ).encode('ascii')
        self.write('_fixture_generate.py', self.generator)
        self.write('_run_quality.py', (
            'import subprocess,sys\n'
            'BUILD_GENERATED_STEPS=[]\n'
            'def regeneration_steps(value):\n'
            ' assert value=="2026-09-30"\n'
            ' return [[sys.executable,"-B","_fixture_generate.py"]]\n'
            'def run_steps(name,commands):\n'
            ' for command in commands:subprocess.run(command,check=True)\n'
        ).encode('ascii'))
        self.commit('trusted nonclinical fixture pipeline')
        self.record_source_and_outputs()

    def record_source_and_outputs(self):
        self.base = self.run_git('rev-parse', 'HEAD')
        self.run_git('update-ref', 'refs/heads/main', self.base)
        files, proof = self.prepare()
        self.proof = proof
        files = delivery.with_receipt(self.root, files, proof, now=self.now)
        apply(self.root, files, expected_head=self.base)
        self.commit('isolated approved source')
        self.source = self.run_git('rev-parse', 'HEAD')
        subprocess.run([sys.executable, '-B', '_fixture_generate.py'], cwd=self.root, check=True)
        self.commit('isolated fixture outputs')
        self.generated = self.run_git('rev-parse', 'HEAD')
        self.archive = self.capture()
        self.run_git('switch', '--detach', self.base)

    def test_trusted_generation_can_remove_a_tracked_stale_output(self):
        self.write('en/blog/retired.html', b'Obsolete generated fixture')
        self.write('_fixture_generate.py', self.generator +
                   b'Path("en/blog/retired.html").unlink()\n')
        self.commit('trusted pipeline removes a retired generated page')
        self.record_source_and_outputs()
        result = self.verify()
        self.assertTrue(result['generationVerified'])
        self.assertFalse(result['published'])
        # The user's original checkout remains at its trusted pipeline. Only
        # the disposable reconstruction removes this previously tracked file.
        self.assertEqual((self.root / 'en/blog/retired.html').read_bytes(),
                         b'Obsolete generated fixture')

    def capture(self):
        manifest = package.encode(package.create(self.root, self.source, self.generated,
                                                 'blog/article.html', now=self.now))
        return patient.record(self.root, manifest, now=self.now)

    def verify(self, raw=None):
        # Only dependency installation is replaced, because this fixture has no
        # dependencies. Reconstruction and generation use real isolated children.
        with patch.object(rebuild, 'install_dependencies', return_value={'fixtureOnly': True}):
            return rebuild.verify(self.root, self.archive if raw is None else raw, self.base,
                                  '2026-09-30', now=self.now)

    def altered_outputs(self, changes):
        self.run_git('switch', '--detach', self.source)
        subprocess.run([sys.executable, '-B', '_fixture_generate.py'], cwd=self.root, check=True)
        for name, raw in changes.items():
            if raw is None:
                (self.root / name).unlink()
            else:
                self.write(name, raw)
        self.commit('self-consistent but unreproducible fixture outputs')
        self.generated = self.run_git('rev-parse', 'HEAD')
        raw = self.capture()
        self.run_git('switch', '--detach', self.base)
        return raw

    def test_rebuild_compares_complete_raw_outputs_and_preserves_original_checkout(self):
        self.write('user-note.txt', b'Keep this unsaved user file')
        before = (self.run_git('show-ref'), self.run_git('status', '--porcelain'))
        result = self.verify()
        self.assertTrue(result['generationVerified'])
        self.assertEqual(result['archiveSha256'], hashlib.sha256(self.archive).hexdigest())
        self.assertEqual(result['pagefindFiles'], 2)
        for field in ('liveAuthorIntentVerified', 'contentApproved', 'ciVerified', 'published'):
            self.assertIs(result[field], False)
        self.assertEqual((self.run_git('show-ref'), self.run_git('status', '--porcelain')), before)
        self.assertEqual((self.root / 'user-note.txt').read_bytes(), b'Keep this unsaved user file')

    def test_rewriting_generated_identity_does_not_approve_different_patient_outputs(self):
        for name in ('blog/article.html', 'en/blog/article.html', 'ai/fixture.json',
                     'assets/search-index.json', 'feed.xml', self.image_path):
            with self.subTest(name=name):
                raw = self.altered_outputs({name: b'Altered fixture bytes'})
                self.assertTrue(patient.verify(self.root, raw, now=self.now)['immutableIdentityVerified'])
                with self.assertRaisesRegex(ValueError, 'different size|bytes differ'):
                    self.verify(raw)

    def test_missing_added_renamed_and_changed_pipeline_outputs_fail(self):
        for changes in ({'feed.xml': None}, {'extra.html': b'Unrecorded fixture'},
                        {'feed.xml': None, 'renamed.xml': b'<feed>Fixture only</feed>'},
                        {'_fixture_generate.py': self.generator + b'\n# different generator\n'}):
            with self.subTest(changes=list(changes)):
                raw = self.altered_outputs(changes)
                with self.assertRaisesRegex(ValueError, 'omitted|renamed|different size|bytes differ'):
                    self.verify(raw)

    def test_mutable_pagefind_cannot_become_verified_generation(self):
        self.write('pagefind/pagefind.js', b'Unrelated new search bytes')
        raw = self.capture()
        self.assertTrue(patient.verify(self.root, raw, now=self.now)['immutableIdentityVerified'])
        with self.assertRaisesRegex(ValueError, 'Pagefind inventory'):
            self.verify(raw)

    def test_receipt_cannot_authorize_draft_controlled_catalog_code(self):
        self.run_git('switch', '--detach', self.source)
        bad = b'throw new Error("Draft controlled code must never execute");'
        self.write('blog/blog-shared.js', bad)
        proof = deepcopy(self.proof)
        proof['sourceSha256']['blog/blog-shared.js'] = hashlib.sha256(bad).hexdigest()
        self.write(delivery.FILE, package.encode({'version': 1, 'requests': [proof]}))
        self.run_git('add', '--all')
        self.run_git('commit', '--amend', '--no-edit')
        self.source = self.run_git('rev-parse', 'HEAD')
        subprocess.run([sys.executable, '-B', '_fixture_generate.py'], cwd=self.root, check=True)
        self.commit('outputs of altered source fixture')
        self.generated = self.run_git('rev-parse', 'HEAD')
        raw = self.capture()
        self.run_git('switch', '--detach', self.base)
        with self.assertRaisesRegex(ValueError, 'independent reconstruction'):
            self.verify(raw)

    def test_unrecorded_ignored_output_is_rejected(self):
        raw = self.altered_outputs({'_fixture_generate.py': self.generator})
        real_generate = rebuild.generate
        def add_ignored(checkout, *args):
            real_generate(checkout, *args)
            (checkout / 'ignored').mkdir()
            (checkout / 'ignored/patient.html').write_bytes(b'Unexpected patient fixture')
        with patch.object(rebuild, 'generate', add_ignored), self.assertRaisesRegex(ValueError, 'unrecorded ignored'):
            self.verify(raw)

    def test_failed_generation_never_returns_verified_receipt(self):
        def fail(*args, **kwargs):
            raise ValueError('Patient rebuild command failed (exit 9)')
        with patch.object(rebuild, 'generate', fail), self.assertRaisesRegex(ValueError, 'exit 9'):
            self.verify()

    def test_wrong_current_pipeline_invalid_date_and_tampered_archive_fail_before_execution(self):
        with patch.object(rebuild, 'install_dependencies') as install:
            for pipeline, frozen_date, raw in ((self.source, '2026-09-30', self.archive),
                                              (self.base, '2026-02-30', self.archive),
                                              (self.base, '2026-09-30', self.archive + b'extra')):
                with self.subTest(pipeline=pipeline, date=frozen_date), self.assertRaises(ValueError):
                    rebuild.verify(self.root, raw, pipeline, frozen_date, now=self.now)
            install.assert_not_called()

    def test_actual_public_rebuild_command_rejects_wrong_pipeline_instead_of_plain_verification(self):
        script = Path(__file__).resolve().with_name('_cms_patient_package.py')
        with tempfile.TemporaryDirectory(prefix='patient-rebuild-cli-') as directory:
            archive = Path(directory) / 'patient.zip'
            archive.write_bytes(self.archive)
            result = subprocess.run([sys.executable, str(script), '--root', str(self.root),
                                     'rebuild', str(archive), '--pipeline-head', self.source,
                                     '--content-date', '2026-09-30'], capture_output=True, timeout=60)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'explicitly trusted current HEAD', result.stderr)

    def test_public_command_dispatch_performs_actual_replay_with_fixture_dependencies_only(self):
        script = Path(__file__).resolve().with_name('_cms_patient_package.py')
        with tempfile.TemporaryDirectory(prefix='patient-rebuild-cli-') as directory:
            archive = Path(directory) / 'patient.zip'
            archive.write_bytes(self.archive)
            # Only dependency installation is mocked for this dependency-free
            # fixture. The real public argument parser, source reconstruction,
            # isolated subprocess generator and complete comparison all execute.
            code = ('import sys,runpy;from unittest.mock import patch;'
                    'sys.path.insert(0,sys.argv[1]);import _cms_patient_rebuild;'
                    'script=sys.argv[2];sys.argv=sys.argv[2:];'
                    'context=patch.object(_cms_patient_rebuild,"install_dependencies",return_value={"fixtureOnly":True});'
                    'context.start();runpy.run_path(script,run_name="__main__")')
            result = subprocess.run([sys.executable, '-c', code, str(script.parent), str(script),
                                     '--root', str(self.root), 'rebuild', str(archive),
                                     '--pipeline-head', self.base, '--content-date', '2026-09-30'],
                                    capture_output=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr.decode('utf8', errors='replace'))
            value = json.loads(result.stdout)
            self.assertTrue(value['generationVerified'])
            self.assertFalse(value['published'])

    def test_child_environment_omits_tokens_and_user_configuration(self):
        with tempfile.TemporaryDirectory(prefix='cms-env-test-') as folder:
            with patch.dict(os.environ, {'GH_TOKEN': 'fixture-secret', 'VERCEL_TOKEN': 'fixture-secret',
                                         'NODE_OPTIONS': '--require=untrusted', 'PYTHONPATH': 'untrusted',
                                         'GIT_CONFIG_COUNT': '1', 'NPM_CONFIG_USERCONFIG': 'untrusted'}):
                env = rebuild.environment(Path(folder))
            for key in ('GH_TOKEN', 'VERCEL_TOKEN', 'NODE_OPTIONS', 'PYTHONPATH', 'GIT_CONFIG_COUNT'):
                self.assertNotIn(key, env)
            self.assertEqual(env['NPM_CONFIG_IGNORE_SCRIPTS'], 'true')
            self.assertEqual(env['GIT_CONFIG_GLOBAL'], os.devnull)
            self.assertTrue(Path(env['NPM_CONFIG_USERCONFIG']).is_relative_to(Path(folder)))


if __name__ == '__main__':
    unittest.main()
