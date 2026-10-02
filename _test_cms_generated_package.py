"""Complete generated-package identity on disposable Git; no publication."""
from copy import deepcopy
import hashlib
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import _cms_generated_package as package
import _cms_delivery as delivery
import _normalize_schema as schema
from _test_cms_delivery import CMSDeliveryTests


class PackageTests(unittest.TestCase):
    original_source = CMSDeliveryTests.original_source
    run_git = CMSDeliveryTests.run_git
    write = CMSDeliveryTests.write
    commit = CMSDeliveryTests.commit
    save_manifest = CMSDeliveryTests.save_manifest
    store = CMSDeliveryTests.store
    prepare = CMSDeliveryTests.prepare

    def setUp(self):
        CMSDeliveryTests.setUp(self)
        self.source = self.candidate
        self.write('en/blog/article.html', b'<html lang="en"><head><title>Fixture</title></head><body><p>Fixture translation</p></body></html>')
        self.write('assets/search-index.json', b'{"fixture":"article"}\n')
        self.write('ai/fixture.json', b'{"summary":"Fixture only"}\n')
        self.write('feed.xml', b'<feed>Fixture only</feed>')
        self.commit('isolated generated artifacts')
        self.generated = self.run_git('rev-parse', 'HEAD')

    def create(self):
        return package.create(self.root, self.source, self.generated, 'blog/article.html', now=self.now)

    def verify(self, value):
        return package.verify(self.root, package.encode(value), now=self.now)

    def replace_generated(self, files):
        self.run_git('switch', '--detach', self.source)
        for name, content in files.items():
            self.write(name, content)
        self.commit('isolated alternative generated artifact')
        return self.run_git('rev-parse', 'HEAD')

    def test_complete_tree_and_bytes_are_recorded_without_refs_or_worktree_writes(self):
        status, refs = self.run_git('status', '--porcelain'), self.run_git('show-ref')
        value = self.create()
        expected = self.run_git('ls-tree', '-r', '--name-only', self.generated).splitlines()
        self.assertEqual(list(value['files']), sorted(expected))
        for name, row in value['files'].items():
            raw = subprocess.check_output(['git', 'show', self.generated+':'+name], cwd=self.root)
            self.assertEqual(row['blobSha'], self.run_git('rev-parse', self.generated+':'+name))
            self.assertEqual(row['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(row['size'], len(raw))
        result = self.verify(value)
        self.assertTrue(result['immutableIdentityVerified'])
        for field in ('liveAuthorIntentVerified','generationVerified','contentApproved','ciVerified','published'):
            self.assertIs(result[field], False)
        self.assertEqual(self.run_git('status', '--porcelain'), status)
        self.assertEqual(self.run_git('show-ref'), refs)

    def test_original_approval_does_not_approve_generated_english_or_metadata(self):
        value = self.create()
        for name in ('en/blog/article.html','assets/search-index.json','ai/fixture.json','feed.xml'):
            self.assertIn(name, value['files'])
            self.assertNotIn(name, value['sourceEvidence']['sourceSha256'])
        self.assertIs(value['contentApproved'], False)
        self.assertIs(value['generationVerified'], False)
        with self.assertRaisesRegex(ValueError, 'Invalid CMS delivery schema'):
            delivery.receipts(package.encode(value), now=self.now)

    def test_actual_schema_generation_is_recorded_but_never_rebinds_source_approval(self):
        # Use an actual generator with ROOT redirected only into the fixture.
        self.run_git('switch', '--detach', self.source)
        path = self.root/'blog/article.html'
        source = path.read_bytes()
        altered = source.replace(b'<html>', b'<html><head><title>Fixture</title><link rel="canonical" href="https://chendermatologist.com/blog/article"><script type="application/ld+json">{"@type":"Article"}</script></head>')
        self.write('blog/article.html', altered)
        with patch.object(schema, 'ROOT', self.root):
            self.assertTrue(schema.normalize_file(path))
        self.write('en/blog/article.html', b'<html>Fixture mirror</html>')
        self.commit('isolated actual normalization')
        self.generated = self.run_git('rev-parse','HEAD')
        value = self.create()
        self.assertNotEqual(value['files']['blog/article.html']['sha256'], value['sourceEvidence']['sourceSha256']['blog/article.html'])
        self.assertTrue(self.verify(value)['immutableIdentityVerified'])
        self.assertIs(value['contentApproved'],False)
        self.assertEqual(subprocess.check_output(['git','show',self.source+':blog/article.html'],cwd=self.root), source)

    def test_missing_added_renamed_or_changed_patient_surface_is_rejected(self):
        original = self.create()
        for name in ('blog/article.html', 'en/blog/article.html', self.image_path,
                     'assets/search-index.json', 'ai/fixture.json', 'feed.xml'):
            for change in ('missing', 'digest', 'blob', 'size', 'rename'):
                with self.subTest(name=name, change=change):
                    value = deepcopy(original)
                    if change == 'missing': del value['files'][name]
                    elif change == 'rename': value['files'][name+'.renamed'] = value['files'].pop(name)
                    else: value['files'][name][{'digest':'sha256','blob':'blobSha','size':'size'}[change]] = 1 if change=='size' else 'a'*64
                    with self.assertRaisesRegex(ValueError, 'complete immutable'):
                        self.verify(value)
        value=deepcopy(original);value['files']['unrecorded.html']=value['files']['blog/article.html']
        with self.assertRaisesRegex(ValueError,'complete immutable'):self.verify(value)

    def test_forged_version_types_approval_status_and_unknown_fields_are_rejected(self):
        original=self.create()
        for field,value in [('version',True),('repository','other/repo'),('state','approved'),
                            ('published',True),('generationVerified',True),('contentApproved',True),
                            ('ciVerified',True),('ciVerified',0),('unknown','value')]:
            changed=deepcopy(original);changed[field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'preparatory package'):
                self.verify(changed)
        changed=deepcopy(original);changed['sourceEvidence']['version']=True
        with self.assertRaisesRegex(ValueError,'complete immutable'):self.verify(changed)

    def test_pipeline_source_proof_tree_and_generated_identity_cannot_be_rewritten(self):
        original=self.create()
        for field in ('pipelineHead','sourceHead','generatedHead','generatedTreeSha'):
            changed=deepcopy(original);changed[field]=self.generated if field=='pipelineHead' else self.base
            with self.subTest(field=field),self.assertRaises((ValueError,subprocess.CalledProcessError)):
                self.verify(changed)
        changed=deepcopy(original);changed['sourceEvidence']['sourceSha256']['blog/article.html']='a'*64
        with self.assertRaisesRegex(ValueError,'complete immutable'):self.verify(changed)

    def test_generation_requires_the_frozen_source_parent_and_english_mirror(self):
        with self.assertRaisesRegex(ValueError,'direct child'):
            package.create(self.root,self.source,self.base,'blog/article.html',now=self.now)
        no_mirror=self.replace_generated({'generated.txt':b'Fixture'})
        with self.assertRaisesRegex(ValueError,'Chinese or English'):
            package.create(self.root,self.source,no_mirror,'blog/article.html',now=self.now)
        tree=self.run_git('rev-parse',self.generated+'^{tree}')
        with self.assertRaisesRegex(ValueError,'must be a commit'):
            package.create(self.root,self.source,tree,'blog/article.html',now=self.now)

    def test_generation_cannot_rewrite_the_old_source_receipt(self):
        raw=(self.root/delivery.FILE).read_bytes()+b' '
        other=self.replace_generated({delivery.FILE:raw,'en/blog/article.html':b'<html>Fixture</html>'})
        with self.assertRaisesRegex(ValueError,'source approval receipt'):
            package.create(self.root,self.source,other,'blog/article.html',now=self.now)

    def test_symlink_submodule_and_new_executable_are_not_regular_outputs(self):
        self.run_git('switch','--detach',self.source)
        self.write('en/blog/article.html',b'<html>Fixture</html>')
        blob=self.run_git('rev-parse',self.source+':blog/article.html')
        for mode,kind in [('120000','link'),('160000','submodule'),('100755','executable')]:
            self.run_git('reset','--hard',self.source)  # Verified disposable fixture.
            self.write('en/blog/article.html',b'<html>Fixture</html>')
            self.run_git('add','en/blog/article.html')
            self.run_git('update-index','--add','--cacheinfo',mode+','+(self.source if mode=='160000' else blob)+',generated-object')
            self.run_git('commit','-m','isolated '+kind)
            head=self.run_git('rev-parse','HEAD')
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'non-ordinary|executable'):
                package.create(self.root,self.source,head,'blog/article.html',now=self.now)

    def test_dirty_untracked_files_are_preserved_and_not_silently_archived(self):
        value=self.create()
        self.write('user-note.txt',b'Keep this user edit')
        self.write('blog/article.html',b'Unsaved working version')
        before=self.run_git('status','--porcelain')
        self.assertTrue(self.verify(value)['immutableIdentityVerified'])
        self.assertNotIn('user-note.txt',value['files'])
        self.assertEqual(self.run_git('status','--porcelain'),before)
        self.assertEqual((self.root/'user-note.txt').read_bytes(),b'Keep this user edit')

    def test_immutable_identity_does_not_claim_a_cancelled_request_is_still_live(self):
        value=self.create()
        self.run_git('update-ref','refs/heads/drafts/article',self.saved)
        result=self.verify(value)
        self.assertTrue(result['immutableIdentityVerified'])
        self.assertIs(result['liveAuthorIntentVerified'],False)
        self.assertIs(result['published'],False)

    def test_bounded_file_blob_total_and_manifest_limits_fail_closed(self):
        for field,maximum in [('MAX_FILES',1),('MAX_BLOB',1),('MAX_TOTAL',1),('MAX_MANIFEST',1)]:
            with self.subTest(field=field),patch.object(package,field,maximum),self.assertRaises(ValueError):
                self.create()

    def test_total_byte_bound_counts_repeated_output_paths(self):
        self.run_git('switch', '--detach', self.source)
        self.write('en/blog/article.html', b'<html>Fixture</html>')
        for index in range(3):
            self.write('copies/copy-' + str(index) + '.txt', b'x' * 1000)
        self.commit('isolated duplicate blob outputs')
        self.generated = self.run_git('rev-parse', 'HEAD')
        value = self.create()
        unique = {row['blobSha']: row['size'] for row in value['files'].values()}
        with patch.object(package, 'MAX_TOTAL', sum(unique.values())), self.assertRaisesRegex(ValueError, 'bytes exceed'):
            self.create()

    def test_duplicate_json_properties_noncanonical_bytes_and_nan_are_rejected(self):
        original=self.create();raw=package.encode(original)
        for altered in (raw.replace(b'"version": 1',b'"version": 1, "version": 1',1),
                        raw.rstrip(),raw.replace(b'"size": ',b'"size": NaN, "unused": ',1)):
            with self.subTest(),self.assertRaises(ValueError):
                package.verify(self.root,altered,now=self.now)


if __name__=='__main__':
    unittest.main()
