"""Disposable published/retirement Git histories and shared Python/Node fixtures.

CI/deployment responses are synthetic. No hosted traffic, secrets or ref writes.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import parse_qs,urlsplit
import unittest

import _cms_delivery as delivery
import _cms_retirement as retirement
from _retire_cms_receipts import write_bundle
from _prepare_article_candidate import apply
import _test_cms_delivery as fixture
from _test_cms_delivery import encoded


class PublicationAPI(fixture.LocalAPI):
    def get(self, path):
        f=self.fixture
        if path.startswith('/actions/runs?'):
            self.calls.append(path)
            sha=parse_qs(urlsplit(path).query)['head_sha'][0]
            data={'workflow_runs': [dict(id=101+i,path=e['path'],head_sha=sha,head_branch='main',event='push',
                head_repository={'full_name':delivery.REPO},status='completed',conclusion='success',run_attempt=1)
                for i,e in enumerate(f.policy['workflows'])] if sha==f.published else []}
        elif path.startswith('/actions/runs/'):
            self.calls.append(path); run=int(path.split('/')[3]);e=f.policy['workflows'][run-101]
            data={'jobs':[dict(id=301+i,head_sha=f.published,name=name,status='completed',
                conclusion='skipped' if name in e.get('main_skips',[]) else 'success',
                steps=[dict(name=n,status='completed',conclusion='success') for n in [*e['steps'][name]['required'],*e['steps'][name].get('main_required',[])]])
                for i,name in enumerate(e['jobs'])]}
        elif path.startswith('/deployments'):
            self.calls.append(path)
            published=dict(id=201,sha=f.published,environment='Production',production_environment=False,creator={'login':'vercel[bot]'})
            if path.startswith('/deployments/201/statuses'):
                data=[dict(id=202,state='success',creator={'login':'vercel[bot]'},environment_url='https://chendermatologist-fixture.vercel.app')]
            elif path=='/deployments/201':data=published
            elif path.startswith('/deployments?'):data=[published]
            else:raise AssertionError('Unexpected retirement deployment path '+path)
        else:return super().get(path)
        return self.adjust(path,deepcopy(data))


class RetirementTests(unittest.TestCase):
    original_source = fixture.CMSDeliveryTests.original_source
    run_git = fixture.CMSDeliveryTests.run_git
    write = fixture.CMSDeliveryTests.write
    commit = fixture.CMSDeliveryTests.commit
    save_manifest = fixture.CMSDeliveryTests.save_manifest
    store = fixture.CMSDeliveryTests.store
    prepare = fixture.CMSDeliveryTests.prepare
    verify = fixture.CMSDeliveryTests.verify

    def setUp(self):
        fixture.CMSDeliveryTests.setUp(self)
        self.policy=json.loads(Path('_delivery_policy.json').read_text(encoding='utf-8'))
        self.write('_delivery_policy.json',encoded(self.policy));self.commit('isolated formal policy')
        self.published=self.run_git('rev-parse','HEAD');self.run_git('update-ref','refs/heads/main',self.published)
        self.api=PublicationAPI(self)
        self.files=retirement.prepare(self.api,self.published,now=self.now)
        self.archive=retirement.PREFIX+self.published+'.json'
        apply(self.root,self.files,expected_head=self.published);self.commit('separate retirement candidate')
        self.candidate=self.run_git('rev-parse','HEAD')

    def both(self,passed=True):
        self.api.calls.clear();responses={};original=self.api.get
        def capture(path):
            data=original(path);responses.setdefault(path,[]).append(deepcopy(data));return data
        self.api.get=capture
        try:result=self.verify();py=True
        except Exception as error:result={'error':str(error)};py=False
        finally:self.api.get=original
        module=Path(__file__).resolve().parent/'_cms_delivery.cjs'
        code="const fs=require('node:fs'),v=require(process.argv[1]),i=JSON.parse(fs.readFileSync(0,'utf8'));v.verifyLiveIntent(i.sha,async p=>{if(!i.responses[p]?.length)throw Error('Missing fixture response '+p);return i.responses[p].shift();},i.now).then(r=>console.log(JSON.stringify({passed:true,result:r}))).catch(e=>console.log(JSON.stringify({passed:false,error:e.message})));"
        r=subprocess.run(['node','-e',code,str(module)],input=json.dumps({'sha':self.candidate,'responses':responses,'now':int(self.now.timestamp()*1000)}),capture_output=True,text=True,encoding='utf-8',timeout=20)
        self.assertEqual(r.returncode,0,r.stderr);node=json.loads(r.stdout)
        self.assertEqual(py,passed,result);self.assertEqual(node['passed'],passed,node)
        return result

    def test_valid_retirement_preserves_history_content_drafts_and_refs(self):
        refs=self.run_git('show-ref');request=self.run_git('rev-parse','drafts/article')
        record=json.loads(self.files[self.archive]);self.assertEqual(record['requests'],[self.proof])
        self.assertEqual(record['publishedSha'],self.published)
        self.assertEqual(self.both()['activeRequests'],0)
        self.assertEqual(self.run_git('show-ref'),refs);self.assertEqual(self.run_git('rev-parse','drafts/article'),request)
        self.assertEqual(self.run_git('diff','--name-only',self.published,self.candidate).splitlines(),sorted(self.files))
        self.assertEqual((self.root/'blog/article.html').read_bytes(),self.content)

    def test_only_formal_all_green_can_prepare_retirement(self):
        for field in ['event','head_sha','head_repository','status','conclusion','run_attempt']:
            def alter(path,data):
                if path.startswith('/actions/runs?'):
                    data['workflow_runs'][0][field]={'full_name':'other/repo'} if field=='head_repository' else 0 if field=='run_attempt' else 'wrong'
                return data
            self.api.adjust=alter
            with self.subTest(field=field),self.assertRaises(Exception):retirement.prepare(self.api,self.published,now=self.now)

    def test_preview_history_does_not_exhaust_production_query_for_python_or_node(self):
        def alter(path,data):
            if path.startswith('/deployments?'):
                query=parse_qs(urlsplit(path).query)
                self.assertNotIn('sha',query, 'Production rollbacks must remain visible')
                if query.get('environment')!=['Production']:
                    return [dict(data[0],id=1000+i,environment='Preview',production_environment=False) for i in range(100)]
            return data
        self.api.adjust=alter
        self.assertEqual(retirement.prepare(self.api,self.published,now=self.now),self.files)
        self.assertEqual(self.both()['activeRequests'],0)

    def test_failed_missing_duplicate_skipped_or_wrong_sha_formal_jobs_block_both(self):
        cases=[lambda d:d.update(jobs=[]),lambda d:d['jobs'].append(deepcopy(d['jobs'][0])),
               lambda d:d['jobs'][0].update(conclusion='skipped'),lambda d:d['jobs'][0].update(head_sha='a'*40),
               lambda d:d['jobs'][0]['steps'][0].update(conclusion='failure'),
               lambda d:d['jobs'][0]['steps'].append(dict(name='hidden failure',status='completed',conclusion='timed_out'))]
        for change in cases:
            def alter(path,data):
                if path.startswith('/actions/runs/101/'):change(data)
                return data
            self.api.adjust=alter
            with self.subTest(change=change):self.both(False)

    def test_old_green_cannot_mask_new_attempt(self):
        count=[]
        def alter(path,data):
            if path.startswith('/actions/runs?'):
                count.append(path)
                if len(count)>1:data['workflow_runs'][0]['run_attempt']=2
            return data
        self.api.adjust=alter;self.both(False)

    def test_wrong_deployment_actor_status_url_sha_and_rollback_block_both(self):
        for target,update in [('/deployments?',dict(sha='a'*40)),('/deployments/201',dict(sha='a'*40)),
            ('/deployments/201',dict(creator={'login':'maintainer'})),
            ('/deployments/201/statuses',dict(state='failure')),('/deployments/201/statuses',dict(creator={'login':'maintainer'})),
            ('/deployments/201/statuses',dict(environment_url='https://other.example/'))]:
            def alter(path,data):
                if path.startswith(target):
                    if isinstance(data,list):data[0].update(update)
                    else:data.update(update)
                return data
            self.api.adjust=alter
            with self.subTest(target=target,update=update):self.both(False)

    def test_formal_phase_accepts_prior_success_after_new_deployment_marks_it_inactive(self):
        self.run_git('update-ref','refs/heads/main',self.candidate)
        def alter(path,data):
            if path.startswith('/deployments?'):
                data.append(dict(id=203,sha=self.candidate,environment='Production',production_environment=False,creator={'login':'vercel[bot]'}))
            if path.startswith('/deployments/201/statuses'):
                data.insert(0,dict(id=204,state='inactive',creator={'login':'vercel[bot]'},environment_url='https://chendermatologist-fixture.vercel.app'))
            return data
        self.api.adjust=alter;self.both()

    def test_new_candidate_deployment_cannot_hide_prior_publication_failure(self):
        self.run_git('update-ref','refs/heads/main',self.candidate)
        def alter(path,data):
            if path.startswith('/deployments?'):
                data.append(dict(id=203,sha=self.candidate,environment='Production',production_environment=False,creator={'login':'vercel[bot]'}))
            if path.startswith('/deployments/201/statuses'):
                data.insert(0,dict(id=204,state='failure',creator={'login':'vercel[bot]'},environment_url='https://chendermatologist-fixture.vercel.app'))
            return data
        self.api.adjust=alter;self.both(False)

    def test_retirement_cannot_mix_content_settings_or_generate_new_medical_text(self):
        for path in ['blog/article.html','admin.html','_delivery_policy.json']:
            original=(self.root/path).read_bytes() if (self.root/path).exists() else None
            self.write(path,b'changed');self.commit('unapproved extra source');self.candidate=self.run_git('rev-parse','HEAD')
            with self.subTest(path=path):self.both(False)
            if original is None:self.run_git('rm',path)
            else:self.write(path,original)
            self.commit('restore fixture');self.candidate=self.run_git('rev-parse','HEAD')

    def test_receipt_or_archive_deletion_and_wrong_archive_proofs_block_both(self):
        original=(self.root/self.archive).read_bytes()
        for field in ['publishedSha','receiptBlobSha','requests','preparedAt','evidence']:
            value=json.loads(original);value[field]=[] if field=='requests' else {} if field=='evidence' else 'wrong'
            self.write(self.archive,encoded(value));self.commit('alter archive');self.candidate=self.run_git('rev-parse','HEAD')
            with self.subTest(field=field):self.both(False)
        self.write(self.archive,original);self.commit('restore archive');self.candidate=self.run_git('rev-parse','HEAD')
        self.run_git('rm',self.archive);self.commit('drop archive');self.candidate=self.run_git('rev-parse','HEAD');self.both(False)

    def test_published_request_may_be_superseded_without_erasing_history_or_new_draft(self):
        self.run_git('switch','drafts/article');self.write('author-note.txt',b'new author edit');self.commit('new draft')
        new=self.run_git('rev-parse','HEAD');self.run_git('switch','codex/cms-gate')
        self.both();self.assertEqual(self.run_git('rev-parse','drafts/article'),new)

    def test_history_becomes_immutable_for_future_engineering_candidates(self):
        self.run_git('update-ref','refs/heads/main',self.candidate)
        self.write('new-code.txt',b'ordinary later engineering');self.commit('later source');self.candidate=self.run_git('rev-parse','HEAD')
        self.both()
        self.write(self.archive,b'{}\n');self.commit('rewrite published history');self.candidate=self.run_git('rev-parse','HEAD');self.both(False)

    def test_bundle_is_external_exclusive_and_never_changes_refs_or_checkout(self):
        self.run_git('checkout','--detach',self.published)
        refs=self.run_git('show-ref');status=self.run_git('status','--porcelain')
        with tempfile.TemporaryDirectory(prefix='cms-retirement-review-test-') as folder:
            destination=Path(folder)/'bundle'
            write_bundle(self.root,destination,self.published,self.files)
            self.assertEqual((destination/delivery.FILE).read_bytes(),self.files[delivery.FILE])
            with self.assertRaises(ValueError):write_bundle(self.root,destination,self.published,self.files)
            with self.assertRaises(ValueError):write_bundle(self.root,Path(folder)/'wrong',self.candidate,self.files)
            with self.assertRaises(ValueError):write_bundle(self.root,Path(folder)/'escape',self.published,{'../article.html':b'bad'})
            with self.assertRaisesRegex(ValueError,'parent'):write_bundle(self.root,Path(folder)/'missing'/'bundle',self.published,self.files)
            with self.assertRaises(ValueError):write_bundle(self.root,self.root/'inside',self.published,self.files)
        self.assertEqual(self.run_git('show-ref'),refs);self.assertEqual(self.run_git('status','--porcelain'),status)

    def test_empty_receipt_preparation_is_noop_with_no_formal_or_deployment_claim(self):
        self.run_git('update-ref','refs/heads/main',self.candidate)
        self.api.calls.clear()
        self.assertEqual(retirement.prepare(self.api,self.candidate,now=self.now),{})
        self.assertFalse(any(p.startswith(('/actions/','/deployments')) for p in self.api.calls))
        self.assertEqual(self.api.calls.count('/git/ref/heads/main'),2)

    def test_live_main_and_deployment_races_are_rejected(self):
        for target in ['/git/ref/heads/main','/deployments?']:
            count=[]
            def alter(path,data):
                if path.startswith(target):
                    count.append(path)
                    if len(count)>1:
                        if isinstance(data,list):data[0]['sha']='a'*40
                        else:data['object']['sha']='a'*40
                return data
            self.api.adjust=alter
            with self.subTest(target=target):self.both(False)

    def test_archive_mode_or_reserved_root_cannot_hide_history(self):
        for mode,path in [('120000',self.archive),('100755',self.archive),('120000','.cms-retirements')]:
            def alter(url,data):
                if url.startswith('/git/trees/'):
                    for e in data['tree']:
                        if e['path']==self.archive:
                            e.update(mode=mode,path=path)
                return data
            self.api.adjust=alter
            with self.subTest(mode=mode,path=path):self.both(False)

    def test_preparation_rejects_naive_clock(self):
        with self.assertRaisesRegex(ValueError,'timezone'):
            retirement.prepare(self.api,self.published,now=self.now.replace(tzinfo=None))

    def test_deployment_status_change_during_validation_blocks_both_ports(self):
        count=[]
        def alter(path,data):
            if path.startswith('/deployments/201/statuses'):
                count.append(path)
                if len(count)>1:data.insert(0,dict(id=205,state='failure',creator={'login':'vercel[bot]'},environment_url='https://chendermatologist-fixture.vercel.app'))
            return data
        self.api.adjust=alter;self.both(False)
        self.assertEqual(len(count),2)

    def test_existing_published_receipt_cannot_be_replaced_without_retirement(self):
        self.run_git('checkout','--detach',self.published)
        value=json.loads((self.root/delivery.FILE).read_bytes())
        value['requests'][0]['preparedAgainst']=self.published
        self.write(delivery.FILE,encoded(value));self.commit('replace published proof without retirement')
        self.candidate=self.run_git('rev-parse','HEAD');self.api.calls.clear()
        items=delivery.receipts(encoded(value),now=self.now)
        with self.assertRaisesRegex(ValueError,'published receipt'):
            retirement.verify_transition(self.candidate,delivery.ImmutableBlobs(self.api),items,now=self.now)
        self.both(False)
        self.assertEqual(self.api.calls.count('/git/ref/heads/drafts/article'),0)


if __name__=='__main__':unittest.main()
