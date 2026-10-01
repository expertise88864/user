"""Actual disposable Git/bundle checks plus immutable fake API; no remote writes."""
import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import _process_site_settings_requests as p
import _site_settings_delivery as s
from _test_site_settings_delivery import Fixture,sha


class GitFixture(Fixture):
    def __init__(self,root):
        self.root=root
        subprocess.run(['git','init','--quiet',str(root)],check=True)
        super().__init__()
        subprocess.run(['git','checkout','--quiet','-b','main',self.main],cwd=root,check=True)
    def command(self,*args,input=None):return subprocess.check_output(['git',*args],cwd=self.root,input=input,stderr=subprocess.PIPE)
    def commit(self,files,parents,label):
        leaves=[]
        for path,raw in files.items():
            bid=self.command('hash-object','-w','--stdin',input=raw).decode().strip();self.blobs[bid]=raw
            leaves.append({'path':path,'mode':'100644','type':'blob','sha':bid})
        def tree(entries):
            rows=[];dirs={}
            for name,bid in entries:
                if '/' in name:
                    folder,rest=name.split('/',1);dirs.setdefault(folder,[]).append((rest,bid))
                else:rows.append(('100644 blob '+bid+'\t'+name).encode()+b'\0')
            for folder,entries in dirs.items():rows.append(('040000 tree '+tree(entries)+'\t'+folder).encode()+b'\0')
            return self.command('mktree','-z',input=b''.join(rows)).decode().strip()
        tid=tree([(row['path'],row['sha']) for row in leaves]);args=['-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit-tree',tid]
        for parent in parents:args+=['-p',parent]
        head=self.command(*args,input=label.encode()).decode().strip()
        self.trees[tid]={'sha':tid,'truncated':False,'tree':leaves}
        self.commits[head]={'sha':head,'tree':{'sha':tid},'parents':[{'sha':v} for v in parents]}
        return head


class SettingsPreparationTests(unittest.TestCase):
    def test_single_source_bundle_only_and_trusted_checkout_refs_untouched(self):
        with tempfile.TemporaryDirectory(prefix='cd-settings-prep-') as directory:
            parent=Path(directory).resolve();self.assertEqual(parent.parent,Path(tempfile.gettempdir()).resolve())
            h=GitFixture(parent/'trusted');h.approval();before=h.command('show-ref')
            result=p.process(h.root,parent/'output',h);self.assertEqual(len(result['prepared']),1)
            item=result['prepared'][0];self.assertFalse(item['reviewVerified']);self.assertFalse(item['ciVerified']);self.assertFalse(item['published'])
            self.assertEqual(item['paths'],sorted([s.SOURCE,s.FILE]));self.assertEqual(h.command('show-ref'),before)
            self.assertEqual(h.command('status','--porcelain').strip(),b'')
            self.assertEqual(sorted(path.name for path in (parent/'output').iterdir()),['report.json',item['bundle']])
            h.command('bundle','unbundle',str(parent/'output'/item['bundle']))
            self.assertEqual(h.command('show',item['sourceCommit']+':'+s.SOURCE),h.files(h.request)[s.SOURCE])
            self.assertEqual(h.command('rev-parse',item['sourceCommit']+'^').decode().strip(),h.main)
            self.assertEqual(h.command('rev-list',h.main+'..'+item['sourceCommit']).decode().splitlines(),[item['sourceCommit']])
            self.assertEqual(h.command('show-ref'),before,'bundle import adds objects, never request/ref history')

    def test_missing_branch_is_normal_absence_but_provider_failure_is_visible(self):
        for status in [404,503]:
            with self.subTest(status=status),tempfile.TemporaryDirectory(prefix='cd-settings-prep-') as directory:
                parent=Path(directory);h=GitFixture(parent/'trusted');original=h.get
                def reader(path):
                    if path=='/git/ref/heads/'+s.BRANCH:raise urllib.error.HTTPError('https://api.github.com/fixture',status,'fixture',None,None)
                    return original(path)
                h.get=reader
                if status==404:self.assertEqual(p.process(h.root,parent/'output',h)['prepared'],[])
                else:
                    with self.assertRaises(urllib.error.HTTPError):p.process(h.root,parent/'output',h)

    def test_unapproved_or_collateral_draft_is_deferred_without_bundle_or_code_execution(self):
        for kind in ['no-request','collateral']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory(prefix='cd-settings-prep-') as directory:
                parent=Path(directory);h=GitFixture(parent/'trusted');h.approval(collateral={'evil.py':b'raise RuntimeError("never run")'} if kind=='collateral' else None)
                if kind=='no-request':h.refs[s.BRANCH]=h.draft
                result=p.process(h.root,parent/'output',h);self.assertEqual(result['prepared'],[]);self.assertEqual(len(result['deferred']),1)
                self.assertEqual([v.name for v in (parent/'output').iterdir()],['report.json']);self.assertEqual(h.command('status','--porcelain').strip(),b'')

    def test_output_exists_or_dirty_root_never_gets_replaced(self):
        with tempfile.TemporaryDirectory(prefix='cd-settings-prep-') as directory:
            parent=Path(directory);h=GitFixture(parent/'trusted');out=parent/'existing';out.mkdir();(out/'keep').write_text('preserve')
            with self.assertRaises(ValueError):p.process(h.root,out,h)
            self.assertEqual((out/'keep').read_text(),'preserve')
            (h.root/'untracked').write_text('user work')
            with self.assertRaises(ValueError):p.process(h.root,parent/'new',h)
            self.assertFalse((parent/'new').exists())

    def test_main_movement_after_bundle_prevents_success_report(self):
        with tempfile.TemporaryDirectory(prefix='cd-settings-prep-') as directory:
            parent=Path(directory);h=GitFixture(parent/'trusted');h.approval();original=p.source_bundle
            def moved(*args):
                item=original(*args);h.refs['main']=h.draft;return item
            with patch.object(p,'source_bundle',side_effect=moved),self.assertRaises(ValueError):p.process(h.root,parent/'output',h)
            self.assertFalse((parent/'output/report.json').exists())

    def test_operational_entry_rejects_non_main_fork_local_and_outside_output_before_api(self):
        environments=[{}, {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'other/repo','GITHUB_REF':'refs/heads/main'},
                      {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':s.REPO,'GITHUB_REF':'refs/heads/codex/test'}]
        for env in environments:
            with self.subTest(env=env),patch.dict(os.environ,env,clear=True),patch('sys.argv',['_process_site_settings_requests.py','--output','outside']),patch.object(p,'process') as process:
                with self.assertRaises(ValueError):p.main()
                process.assert_not_called()
        with tempfile.TemporaryDirectory(prefix='cd-settings-prep-') as directory:
            parent=Path(directory);h=GitFixture(parent/'trusted');h.command('remote','add','origin','https://github.com/'+s.REPO)
            env={**os.environ,'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':s.REPO,'GITHUB_REF':'refs/heads/main','RUNNER_TEMP':str(parent)}
            with patch.dict(os.environ,env,clear=True),patch.object(p,'ROOT',h.root),patch('sys.argv',['_process_site_settings_requests.py','--output',str(parent/'outside')]),patch.object(p,'process') as process:
                with self.assertRaises(ValueError):p.main()
                process.assert_not_called()

    def test_malformed_discovered_ref_is_not_missing_or_a_deferred_request(self):
        for replacement in [None, [], {'ref':'refs/heads/other','object':{'type':'commit','sha':'1'*40}},
                            {'ref':'refs/heads/'+s.BRANCH,'object':[]},
                            {'ref':'refs/heads/'+s.BRANCH,'object':{'type':'blob','sha':'1'*40}},
                            {'ref':'refs/heads/'+s.BRANCH,'object':{'type':'commit','sha':None}}]:
            with self.subTest(ref=replacement),tempfile.TemporaryDirectory(prefix='cd-settings-prep-') as directory:
                parent=Path(directory);h=GitFixture(parent/'trusted');h.approval();original=h.get;reads=0
                def reader(path):
                    nonlocal reads
                    if path=='/git/ref/heads/'+s.BRANCH:
                        reads+=1
                        if reads==1:return replacement
                    return original(path)
                h.get=reader
                with self.assertRaises(ValueError):p.process(h.root,parent/'output',h)
                self.assertFalse((parent/'output/report.json').exists())

    def test_bundle_validation_failure_is_visible_and_never_a_deferred_author_request(self):
        with tempfile.TemporaryDirectory(prefix='cd-settings-prep-') as directory:
            parent=Path(directory);h=GitFixture(parent/'trusted');h.approval()
            with patch.object(p,'source_bundle',side_effect=ValueError('bundle integrity failure')),self.assertRaises(ValueError):
                p.process(h.root,parent/'output',h)
            self.assertFalse((parent/'output/report.json').exists())

    def test_author_withdrawal_after_bundle_prevents_success_report(self):
        with tempfile.TemporaryDirectory(prefix='cd-settings-prep-') as directory:
            parent=Path(directory);h=GitFixture(parent/'trusted');h.approval();original=p.source_bundle
            def withdrawn(*args):
                item=original(*args);h.refs[s.BRANCH]=h.draft;return item
            with patch.object(p,'source_bundle',side_effect=withdrawn),self.assertRaises(ValueError):
                p.process(h.root,parent/'output',h)
            self.assertFalse((parent/'output/report.json').exists())


if __name__=='__main__':unittest.main()
