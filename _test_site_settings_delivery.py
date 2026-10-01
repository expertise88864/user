"""Real blob hashes, immutable graph/read-only fake API; never contact providers."""
import base64
import copy
import hashlib
import json
import unittest
from urllib.parse import parse_qs
import _site_settings_delivery as s


def sha(value): return hashlib.sha1(value.encode()).hexdigest()
def blob(raw): return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def compact(value): return (json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n').encode()


class Fixture:
    def __init__(self, bootstrap=False, noncanonical=False):
        self.calls=[]; self.commits={}; self.trees={}; self.blobs={}; self.refs={}; self.runs={}; self.tamper=None
        self.articles=[{'slug':slug,'title':slug,'title_en':slug} for slug in s.DEFAULT['picks']]
        self.settings=copy.deepcopy(s.DEFAULT)
        files={s.CATALOG:s.encoded({'version':1,'articles':self.articles}),'app.js':b'/* trusted application */'}
        if not bootstrap: files.update({s.SOURCE:s.encoded(self.settings),s.FILE:s.encoded({'version':1,'request':None})})
        if noncanonical:
            for path in (s.SOURCE,s.CATALOG):
                if path in files:files[path]=json.dumps(json.loads(files[path]),ensure_ascii=True,separators=(',',':')).encode()
        self.main=self.commit(files,[],label='main');self.refs['main']=self.main
        self.runs[self.main]=[{'path':'.github/workflows/delivery.yml','head_sha':self.main,'event':'push','head_branch':'main','head_repository':{'full_name':s.REPO}}]
        self.draft=None;self.request=None

    def commit(self, files, parents, label):
        rows=[]
        for path,raw in files.items():
            raw=bytes(raw);bid=blob(raw);self.blobs[bid]=raw
            rows.append({'path':path,'mode':'100644','type':'blob','sha':bid})
        tree=sha(json.dumps(rows,sort_keys=True));head=sha(label+tree+str(parents))
        self.trees[tree]={'sha':tree,'truncated':False,'tree':rows}
        self.commits[head]={'sha':head,'tree':{'sha':tree},'parents':[{'sha':p,'url':'https://api.github.com/fixture'} for p in parents]}
        return head

    def files(self, head): return {r['path']:self.blobs[r['sha']] for r in self.trees[self.commits[head]['tree']['sha']]['tree']}

    def approval(self, updates=None, collateral=None):
        base=self.files(self.main);settings={**copy.deepcopy(self.settings),**(updates or {'font':{**self.settings['font'],'bodySize':'17px'}})}
        source=s.encoded(settings);base_sha=blob(base[s.SOURCE]);catalog_sha=blob(base[s.CATALOG])
        manifest={'version':1,'source':s.SOURCE,'baseMain':self.main,'baseSha':base_sha,'catalogSha':catalog_sha,'blobSha':blob(source),'status':'draft'}
        files={**base,s.SOURCE:source,s.MANIFEST:compact(manifest),**(collateral or {})}
        self.draft=self.commit(files,[self.main],label='draft')
        request={'version':1,'status':'requested','branch':s.BRANCH,'draftHead':self.draft,'blobSha':blob(source),
                 'baseMain':self.main,'baseSha':base_sha,'catalogSha':catalog_sha,'settingsApproved':True}
        self.request=self.commit({**files,s.REQUEST:compact(request)},[self.draft],label='request')
        self.refs[s.BRANCH]=self.request
        return self.request

    def candidate(self, files): return self.commit({**self.files(self.refs['main']),**files},[self.refs['main']],label='candidate')

    def get(self, path):
        self.calls.append(path)
        if path.startswith('/git/ref/heads/'):
            branch=path.split('/git/ref/heads/',1)[1];result={'ref':'refs/heads/'+branch,'object':{'type':'commit','sha':self.refs[branch]}}
        elif path.startswith('/git/commits/'):result=self.commits[path.split('/')[-1]]
        elif path.startswith('/git/trees/'):result=self.trees[path.split('/')[-1].split('?')[0]]
        elif path.startswith('/contents/'):
            filename,query=path[len('/contents/'):].split('?');head=parse_qs(query)['ref'][0]
            raw=self.files(head)[filename];result={'type':'file','path':filename,'sha':blob(raw),'encoding':'base64','size':len(raw),'content':base64.b64encode(raw).decode()}
        elif path.startswith('/compare/'):
            base,head=path[len('/compare/'):].split('...');seen=set();pending=[head]
            while pending:
                value=pending.pop()
                if value in seen:continue
                seen.add(value);pending.extend(p['sha'] for p in self.commits[value]['parents'])
            result={'status':'identical' if base==head else 'ahead' if base in seen else 'diverged','merge_base_commit':{'sha':base if base in seen else head}}
        elif path.startswith('/actions/runs?'):
            result={'workflow_runs':self.runs.get(parse_qs(path.split('?')[1])['head_sha'][0],[])}
        else:raise AssertionError('Unexpected read '+path)
        result=copy.deepcopy(result)
        return self.tamper(path,result) if self.tamper else result


class SettingsDeliveryTests(unittest.TestCase):
    def test_baseline_json_formatting_matches_existing_author_api_contract(self):
        h=Fixture(noncanonical=True);h.approval();files,_=s.plan(h,h.main,h.request)
        self.assertTrue(s.verify(h.candidate(files),h)['authorIntentVerified'])

    def test_extracts_only_exact_approved_data_and_receipt_no_code_or_refs_changed(self):
        h=Fixture();head=h.approval();refs=copy.deepcopy(h.refs)
        files,proof=s.plan(h,h.main,head)
        self.assertEqual(set(files),{s.SOURCE,s.FILE});self.assertEqual(files[s.SOURCE],h.files(head)[s.SOURCE])
        self.assertEqual(s.receipt(files[s.FILE]),proof);self.assertEqual(h.refs,refs)
        candidate=h.candidate(files);self.assertTrue(s.verify(candidate,h)['candidatePayloadVerified'])
        self.assertFalse(s.verify(candidate,h)['published'])

    def test_formal_main_and_later_engineering_use_same_immutable_approved_snapshot(self):
        h=Fixture();h.approval();files,_=s.plan(h,h.main,h.request);candidate=h.candidate(files)
        h.refs['main']=candidate;self.assertTrue(s.verify(candidate,h)['authorIntentVerified'])
        h.runs[candidate]=[{'path':'.github/workflows/delivery.yml','head_sha':candidate,'event':'push','head_branch':'main','head_repository':{'full_name':s.REPO}}]
        engineering=h.candidate({'app.js':b'/* independently reviewed engineering */'})
        self.assertTrue(s.verify(engineering,h)['authorIntentVerified'])

    def test_bootstrap_requires_exact_defaults_and_inactive_canonical_proof(self):
        h=Fixture(bootstrap=True)
        good={s.SOURCE:s.encoded(s.DEFAULT),s.FILE:s.encoded({'version':1,'request':None})}
        self.assertFalse(s.verify(h.candidate(good),h)['activeRequest'])
        for update in [{'version':True},{'legacyPicks':False},{'font':{**s.DEFAULT['font'],'bodySize':'18px'}},{'order':[h.articles[0]['slug']]}, {'picks':[h.articles[1]['slug']]}]:
            with self.subTest(update=update),self.assertRaises(ValueError):
                s.verify(h.candidate({**good,s.SOURCE:s.encoded({**s.DEFAULT,**update})}),h)

    def test_no_approval_cannot_change_settings_and_missing_receipt_is_not_exemption(self):
        h=Fixture();changed={**h.settings,'font':{**h.settings['font'],'bodySize':'18px'}}
        with self.assertRaises(ValueError):s.verify(h.candidate({s.SOURCE:s.encoded(changed)}),h)
        files=h.files(h.main);del files[s.FILE]
        with self.assertRaises(KeyError):s.verify(h.commit(files,[h.main],label='deleted proof'),h)

    def test_cancelled_request_and_candidate_drift_fail_even_after_green_ci(self):
        h=Fixture();h.approval();files,_=s.plan(h,h.main,h.request);candidate=h.candidate(files)
        h.refs[s.BRANCH]=h.draft
        with self.assertRaises(ValueError):s.verify(candidate,h)
        h.refs[s.BRANCH]=h.request
        with self.assertRaises(ValueError):s.verify(h.candidate({**files,s.SOURCE:s.encoded(h.settings)}),h)

    def test_active_proof_cannot_be_removed_replaced_or_prepared_over(self):
        h=Fixture();h.approval();files,_=s.plan(h,h.main,h.request);candidate=h.candidate(files)
        h.refs['main']=candidate
        with self.assertRaises(ValueError):s.verify(h.candidate({s.FILE:s.encoded({'version':1,'request':None})}),h)
        with self.assertRaises(ValueError):s.plan(h,candidate,h.request)

    def test_collateral_draft_file_is_rejected_before_extraction(self):
        for collateral in [{'app.js':b'unsafe replacement'},{'evil.py':b'raise RuntimeError("never execute")'}]:
            with self.subTest(collateral=collateral):
                h=Fixture();h.approval(collateral=collateral)
                with self.assertRaises(ValueError):s.plan(h,h.main,h.request)

    def test_source_ownership_cannot_reactivate_legacy_reads(self):
        h=Fixture();h.settings['legacyPicks']=False
        h.main=h.commit({**h.files(h.main),s.SOURCE:s.encoded(h.settings)},[h.main],label='source owned');h.refs['main']=h.main
        h.approval(updates={'legacyPicks':True})
        with self.assertRaises(ValueError):s.plan(h,h.main,h.request)

    def test_manifest_approval_parent_schema_blob_and_tree_tampering(self):
        def wrong_blob(path,result):
            if path.startswith('/contents/') and s.SOURCE in path:result['sha']='a'*40
            return result
        def symlink(path,result):
            if path.startswith('/git/trees/'):
                for row in result['tree']:
                    if row['path']==s.SOURCE:row['mode']='120000'
            return result
        def truncated(path,result):
            if path.startswith('/git/trees/'):result['truncated']=True
            return result
        def merge_parent(path,result):
            if path.startswith('/git/commits/'):result['parents']=[{'sha':'a'*40},{'sha':'b'*40}]
            return result
        for change in [wrong_blob,symlink,truncated,merge_parent]:
            with self.subTest(change=change.__name__):
                h=Fixture();h.approval();h.tamper=change
                with self.assertRaises(ValueError):s.plan(h,h.main,h.request)

    def test_live_main_or_request_changes_during_reads_block_the_result(self):
        for target in ['main',s.BRANCH]:
            with self.subTest(target=target):
                h=Fixture();h.approval();initial_refs=copy.deepcopy(h.refs)
                def race(path,result):
                    if path.startswith('/contents/'+s.REQUEST):h.refs[target]=h.draft
                    return result
                h.tamper=race
                with self.assertRaises(ValueError):s.plan(h,initial_refs['main'],initial_refs[s.BRANCH])

    def test_missing_or_stale_catalogue_baseline_requires_new_author_integration(self):
        h=Fixture();h.approval();source=h.files(h.main)
        changed=h.commit({**source,s.CATALOG:s.encoded({'version':1,'articles':h.articles[:-1]})},[h.main],label='changed catalogue')
        h.refs['main']=changed
        with self.assertRaises(ValueError):s.plan(h,changed,h.request)

    def test_receipt_closed_schema_types_digest_and_canonical_bytes(self):
        h=Fixture();h.approval();_,proof=s.plan(h,h.main,h.request)
        for update in [{'settingsApproved':1},{'source':'../outside'},{'version':True},{'repository':'other/repo'},
                       {'requestHead':'0'*40},{'sourceSha256':'A'*64},{'extra':'field'}]:
            with self.subTest(update=update),self.assertRaises(ValueError):s.receipt(s.encoded({'version':1,'request':{**proof,**update}}))
        for raw in [b'{"version":1,"version":1,"request":null}',b'\xff',b' '*16001]:
            with self.subTest(raw=raw[:40]),self.assertRaises(ValueError):s.receipt(raw)


if __name__=='__main__':
    import sys
    if sys.argv[1:] in (['--fixture'],['--fixture-noncanonical']):
        h=Fixture(noncanonical=sys.argv[1:] == ['--fixture-noncanonical']);h.approval();files,proof=s.plan(h,h.main,h.request);candidate=h.candidate(files)
        print(json.dumps({'commits':h.commits,'trees':h.trees,'blobs':{bid:base64.b64encode(raw).decode() for bid,raw in h.blobs.items()},
                          'refs':h.refs,'runs':h.runs,'candidate':candidate,'proof':proof}))
    else:unittest.main()
