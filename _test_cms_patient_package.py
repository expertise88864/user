"""Portable complete patient output snapshots on disposable nonclinical Git."""
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import warnings
import zipfile

import _cms_generated_package as tracked
import _cms_patient_package as patient
import _test_cms_generated_package as fixtures


class PatientPackageTests(unittest.TestCase):
    original_source = fixtures.PackageTests.original_source
    run_git = fixtures.PackageTests.run_git
    write = fixtures.PackageTests.write
    commit = fixtures.PackageTests.commit
    save_manifest = fixtures.PackageTests.save_manifest
    store = fixtures.PackageTests.store
    prepare = fixtures.PackageTests.prepare

    def setUp(self):
        fixtures.PackageTests.setUp(self)
        self.write('.gitignore', b'pagefind/\n')
        self.commit('isolated ignored search output boundary')
        # Regeneration must still be a direct child of approved source.
        self.run_git('reset', '--soft', self.generated)
        self.run_git('commit', '--amend', '--no-edit')
        self.generated = self.run_git('rev-parse', 'HEAD')
        self.write('pagefind/pagefind.js', b'export const fixture = true;\n')
        self.write('pagefind/fragment/fixture.pf_fragment', b'Fixture search text only\0')
        self.write('pagefind/pagefind.wasm', b'\0asm\x01\0\0\0')
        self.manifest = tracked.encode(tracked.create(self.root, self.source, self.generated,
                                                   'blog/article.html', now=self.now))

    def capture(self):
        return patient.record(self.root, self.manifest, now=self.now)

    def verify(self, raw):
        return patient.verify(self.root, raw, now=self.now)

    def rewrite(self, raw, *, change=None, drop=None, add=None, descriptor=None):
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(output, 'w') as target:
            for item in source.infolist():
                if item.filename == drop:
                    continue
                content = source.read(item)
                if item.filename == 'manifest.json' and descriptor:
                    value = json.loads(content)
                    descriptor(value)
                    content = tracked.encode(value)
                if change:
                    item, content = change(item, content)
                target.writestr(item, content)
            if add:
                info, content = patient.zip_entry(add, b'Unexpected bytes', 0o644)
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    target.writestr(info, content)
        return output.getvalue()

    def test_all_git_and_ignored_search_bytes_export_deterministically_without_writes(self):
        refs, status = self.run_git('show-ref'), self.run_git('status', '--porcelain')
        raw = self.capture()
        self.assertEqual(raw, self.capture())
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            descriptor = json.loads(archive.read('manifest.json'))
            expected = sorted([*descriptor['trackedPackage']['files'], *descriptor['extraFiles']])
            self.assertEqual(archive.namelist(), ['manifest.json'] + ['files/' + n for n in expected])
            for name, row in descriptor['trackedPackage']['files'].items():
                actual = subprocess.check_output(['git', 'show', self.generated + ':' + name], cwd=self.root)
                self.assertEqual(archive.read('files/' + name), actual)
            for name in descriptor['extraFiles']:
                self.assertEqual(archive.read('files/' + name), (self.root/name).read_bytes())
        result = self.verify(raw)
        self.assertEqual(result['ignoredPagefindFiles'], 3)
        self.assertEqual(result['archiveSha256'], hashlib.sha256(raw).hexdigest())
        self.assertTrue(result['immutableIdentityVerified'])
        self.assertEqual((self.run_git('show-ref'), self.run_git('status', '--porcelain')), (refs, status))

    def test_portable_verification_does_not_require_mutable_current_search_files(self):
        raw = self.capture()
        self.write('pagefind/pagefind.js', b'Changed after export')
        self.assertTrue(self.verify(raw)['immutableIdentityVerified'])
        self.assertNotEqual(raw, self.capture())

    def test_snapshot_never_becomes_a_receipt_or_live_generation_content_ci_approval(self):
        raw = self.capture()
        result = self.verify(raw)
        for field in patient.FALSE_FIELDS:
            self.assertIs(result[field], False)
            altered = self.rewrite(raw, descriptor=lambda value, field=field: value.update({field: True}))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'preparatory'):
                self.verify(altered)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            import _cms_delivery as delivery
            with self.assertRaises(ValueError):
                delivery.receipts(archive.read('manifest.json'), now=self.now)

    def test_changed_missing_added_renamed_patient_outputs_fail(self):
        raw = self.capture()
        for name in ('files/blog/article.html', 'files/en/blog/article.html',
                     'files/assets/search-index.json', 'files/pagefind/pagefind.js',
                     'files/pagefind/fragment/fixture.pf_fragment', 'files/pagefind/pagefind.wasm'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify(self.rewrite(raw, drop=name))
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify(self.rewrite(raw, change=lambda info, data: (info, data+b'x') if info.filename==name else (info,data)))
        with self.assertRaises(ValueError):
            self.verify(self.rewrite(raw, add='files/pagefind/unrecorded.js'))

    def test_duplicate_traversal_absolute_or_confusable_archive_paths_fail(self):
        raw = self.capture()
        for name in ('manifest.json', '../escape', '/absolute', 'files/pagefind/../escape',
                     'files/PAGEFIND/pagefind.js', 'files\\escape', 'files/drive:escape'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify(self.rewrite(raw, add=name))

    def test_compressed_directory_symlink_executable_or_changed_timestamp_entries_fail(self):
        raw = self.capture()
        def alter(attribute, value):
            def change(info, data):
                if info.filename=='files/pagefind/pagefind.js':
                    setattr(info, attribute, value)
                return info,data
            return change
        for attr, value in [('compress_type',zipfile.ZIP_DEFLATED),
                            ('external_attr',(stat.S_IFLNK|0o777)<<16),
                            ('external_attr',(stat.S_IFDIR|0o755)<<16),
                            ('external_attr',(stat.S_IFREG|0o755)<<16),
                            ('date_time',(2026,10,2,0,0,0))]:
            with self.subTest(attribute=attr,value=value), self.assertRaises(ValueError):
                self.verify(self.rewrite(raw, change=alter(attr,value)))
        with self.assertRaisesRegex(ValueError,'canonical'):
            self.verify(raw+b'unrecorded trailing bytes')

    def test_manifest_forged_types_missing_search_and_changed_git_identity_fail(self):
        raw=self.capture()
        changes=[lambda d:d.update(version=True),lambda d:d.update(unknown=True),
                 lambda d:d.update(extraFiles=[]),lambda d:d['extraFiles'].pop('pagefind/pagefind.js'),
                 lambda d:d['extraFiles']['pagefind/pagefind.js'].update(size=True),
                 lambda d:d['extraFiles']['pagefind/pagefind.js'].update(sha256='a'*63),
                 lambda d:d['trackedPackage'].update(generatedHead=self.source)]
        for change in changes:
            with self.assertRaises((ValueError,subprocess.CalledProcessError)):
                self.verify(self.rewrite(raw,descriptor=change))

    def test_missing_search_entrypoint_empty_directory_and_bounds_fail_closed(self):
        original=self.capture()
        for field,maximum in [('MAX_FILES',1),('MAX_BLOB',1),('MAX_TOTAL',1),('MAX_MANIFEST',1),('MAX_ARCHIVE',1)]:
            with self.subTest(field=field), patch.object(patient,field,maximum), self.assertRaises(ValueError):
                self.capture()
            with self.subTest(field=field), patch.object(patient,field,maximum), self.assertRaises(ValueError):
                self.verify(original)
        (self.root/'pagefind/pagefind.js').unlink()
        with self.assertRaisesRegex(ValueError,'entry point'):
            self.capture()

    def test_nested_empty_directory_count_is_bounded(self):
        (self.root/'pagefind/empty/a').mkdir(parents=True)
        with patch.object(patient,'MAX_FILES',3),self.assertRaisesRegex(ValueError,'directory inventory'):
            self.capture()

    def test_hardlinks_and_symlinks_do_not_export_outside_bytes(self):
        target=self.root/'outside.txt';target.write_bytes(b'Unrelated confidential fixture')
        link=self.root/'pagefind/hardlink'
        os.link(target,link)
        with self.assertRaisesRegex(ValueError,'link'):
            self.capture()
        link.unlink()
        try:
            link.symlink_to(target)
        except (OSError,NotImplementedError):
            return  # Actual Windows account may lack symlink privilege.
        with self.assertRaisesRegex(ValueError,'link'):
            self.capture()

    def test_changed_search_inventory_during_capture_is_rejected(self):
        real=patient.pagefind_files
        calls=0
        def mutate(root):
            nonlocal calls
            calls+=1
            if calls==2:self.write('pagefind/new-fragment',b'New concurrent bytes')
            return real(root)
        with patch.object(patient,'pagefind_files',mutate),self.assertRaisesRegex(ValueError,'changed during'):
            self.capture()

    def test_windows_stat_and_handle_creation_identity_agree_without_discarding_changes(self):
        values={'st_dev':1,'st_ino':2,'st_size':3,'st_mtime_ns':4,'st_birthtime_ns':5}
        path=SimpleNamespace(**values,st_ctime_ns=5)
        handle=SimpleNamespace(**values,st_ctime_ns=10)
        with patch.object(patient.os,'name','nt'):
            self.assertEqual(patient.identity(path),patient.identity(handle))
            for field in values:
                changed=SimpleNamespace(**{**values,field:100},st_ctime_ns=10)
                with self.subTest(field=field):
                    self.assertNotEqual(patient.identity(path),patient.identity(changed))
        with patch.object(patient.os,'name','posix'):
            self.assertNotEqual(patient.identity(path),patient.identity(handle))

    def test_dirty_user_sources_are_neither_adopted_nor_discarded(self):
        self.write('blog/article.html',b'Unsaved user source')
        self.write('user-note.txt',b'Preserve user note')
        before=self.run_git('status','--porcelain')
        raw=self.capture()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertNotIn('files/user-note.txt',archive.namelist())
            self.assertNotEqual(archive.read('files/blog/article.html'),b'Unsaved user source')
        self.assertEqual(self.run_git('status','--porcelain'),before)
        self.assertEqual((self.root/'user-note.txt').read_bytes(),b'Preserve user note')

    def test_real_cli_exports_outside_repository_preserves_existing_export_and_verifies(self):
        script=Path(__file__).resolve().with_name('_cms_patient_package.py')
        manifest=self.root/'tracked-manifest.json'
        manifest.write_bytes(self.manifest)
        with tempfile.TemporaryDirectory(prefix='patient-export-test-') as folder:
            output=Path(folder)/'patient.zip'
            command=[sys.executable,str(script),'--root',str(self.root),'record',str(manifest),'--output',str(output)]
            env={**os.environ,'PYTHONUTF8':'1'}
            first=subprocess.run(command,capture_output=True,text=True,encoding='utf8',timeout=60,env=env)
            self.assertEqual(first.returncode,0,first.stderr)
            result=json.loads(first.stdout)
            self.assertEqual(result['ignoredPagefindFiles'],3)
            saved=output.read_bytes()
            second=subprocess.run(command,capture_output=True,text=True,encoding='utf8',timeout=60,env=env)
            self.assertNotEqual(second.returncode,0)
            self.assertEqual(output.read_bytes(),saved)
            check=subprocess.run([sys.executable,str(script),'--root',str(self.root),'verify',str(output)],
                                 capture_output=True,text=True,encoding='utf8',timeout=60,env=env)
            self.assertEqual(check.returncode,0,check.stderr)
            self.assertEqual(json.loads(check.stdout)['archiveSha256'],result['archiveSha256'])
        invalid=subprocess.run([sys.executable,str(script),'--root',str(self.root),'record',str(manifest),
                                '--output',str(self.root/'patient.zip')],capture_output=True,timeout=60)
        self.assertNotEqual(invalid.returncode,0)
        self.assertFalse((self.root/'patient.zip').exists())


if __name__=='__main__':
    unittest.main()
