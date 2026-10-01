"""Settings retirement parity using immutable Git objects and synthetic CI.

No provider requests, author edits, ref writes, or production deployments.
"""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

import _site_settings_delivery as delivery
import _site_settings_retirement as retirement
from _test_site_settings_delivery import Fixture
from _retire_cms_receipts import write_bundle
import _test_cms_retirement as article_retirement_fixture


class PublishedSettings(Fixture):
    def __init__(self, settings_policy=True):
        super().__init__()
        self.policy = json.loads(Path('_delivery_policy.json').read_text(encoding='utf8'))
        self.policy['site_settings_author_intent'] = settings_policy
        self.main = self.commit({**self.files(self.main), '_delivery_policy.json': delivery.encoded(self.policy)}, [self.main], 'installed policy')
        self.refs['main'] = self.main
        self.approval()
        files, self.proof = delivery.plan(self, self.main, self.request)
        self.published = self.candidate(files)
        self.refs['main'] = self.published

    def get(self, path):
        if path.startswith('/actions/runs?'):
            head = parse_qs(urlsplit(path).query)['head_sha'][0]
            result = {'workflow_runs': [dict(id=101+i, path=e['path'], head_sha=head, head_branch='main', event='push',
                head_repository={'full_name': delivery.REPO}, status='completed', conclusion='success', run_attempt=1)
                for i, e in enumerate(self.policy['workflows'])] if head == self.published else []}
        elif path.startswith('/actions/runs/'):
            entry = self.policy['workflows'][int(path.split('/')[3])-101]
            result = {'jobs': [dict(id=301+i, head_sha=self.published, name=name, status='completed',
                conclusion='skipped' if name in entry.get('main_skips', []) else 'success',
                steps=[dict(name=n, status='completed', conclusion='success')
                    for n in [*entry['steps'][name]['required'], *entry['steps'][name].get('main_required', [])]])
                for i, name in enumerate(entry['jobs'])]}
        elif path.startswith('/deployments'):
            deployment = dict(id=201, sha=self.published, environment='Production', production_environment=False, creator={'login':'vercel[bot]'})
            if path.startswith('/deployments/201/statuses'):
                result = [dict(id=202, state='success', creator={'login':'vercel[bot]'}, environment_url='https://chendermatologist-fixture.vercel.app')]
            elif path == '/deployments/201': result = deployment
            elif path == '/deployments/999': result = {**deployment, 'id':999, 'sha':'a'*40}
            elif path.startswith('/deployments?'): result = [deployment]
            else: raise AssertionError('Unexpected settings deployment read '+path)
        else: return super().get(path)
        self.calls.append(path)
        result = copy.deepcopy(result)
        return self.tamper(path, result) if self.tamper else result


class SettingsRetirementTests(unittest.TestCase):
    def setUp(self):
        self.api = PublishedSettings()
        self.now = datetime(2026, 10, 1, tzinfo=timezone.utc)
        self.files = retirement.prepare(self.api, self.api.published, now=self.now)
        self.archive = retirement.PREFIX+self.api.published+'.json'
        self.candidate = self.api.candidate(self.files)

    def both(self, passed=True):
        responses = {}
        original = self.api.get
        def capture(path):
            value = original(path)
            responses.setdefault(path, []).append(copy.deepcopy(value))
            return value
        self.api.get = capture
        try: result = delivery.verify(self.candidate, self.api); py = True
        except Exception as error: result = {'error': str(error)}; py = False
        finally: self.api.get = original
        script = "const fs=require('node:fs'),v=require(process.argv[1]),i=JSON.parse(fs.readFileSync(0,'utf8'));v.verify(i.sha,async p=>{if(!i.responses[p]?.length)throw Error('Missing fixture response '+p);return i.responses[p].shift();}).then(r=>console.log(JSON.stringify({passed:true,result:r}))).catch(e=>console.log(JSON.stringify({passed:false,error:e.message})));"
        run = subprocess.run(['node', '-e', script, str(Path('_site_settings_delivery.cjs').resolve())],
            input=json.dumps({'sha': self.candidate, 'responses': responses}), capture_output=True, text=True, encoding='utf8', timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr)
        node = json.loads(run.stdout)
        self.assertNotIn('Missing fixture response', node.get('error', ''), node)
        self.assertEqual(py, passed, result)
        self.assertEqual(node['passed'], passed, node)
        return result

    def replace(self, path, raw):
        self.candidate = self.api.commit({**self.api.files(self.candidate), path: raw}, [self.api.published], 'changed candidate')

    def test_exact_two_file_retirement_preserves_settings_request_and_refs(self):
        refs = copy.deepcopy(self.api.refs)
        source = self.api.files(self.api.published)[delivery.SOURCE]
        self.assertEqual(set(self.files), {delivery.FILE, self.archive})
        self.assertEqual(json.loads(self.files[self.archive])['request'], self.api.proof)
        self.api.calls.clear()
        self.assertFalse(self.both()['activeRequest'])
        self.assertEqual(self.api.refs, refs)
        self.assertEqual(self.api.files(self.candidate)[delivery.SOURCE], source)
        self.assertFalse(any('/heads/'+delivery.BRANCH in p for p in self.api.calls))

    def test_inactive_receipt_is_noop_without_formal_or_deployment_claim(self):
        self.api.refs['main'] = self.candidate
        self.api.calls.clear()
        self.assertEqual(retirement.prepare(self.api, self.candidate, now=self.now), {})
        self.assertFalse(any(p.startswith(('/actions/', '/deployments')) for p in self.api.calls))

    def test_published_proof_replacement_and_removal_without_archive_block_both(self):
        self.candidate = self.api.candidate({delivery.FILE: delivery.encoded({'version':1, 'request':None})})
        self.both(False)
        changed = {**self.api.proof, 'preparedAgainst': self.api.published}
        self.candidate = self.api.candidate({delivery.FILE: delivery.encoded({'version':1, 'request':changed})})
        self.both(False)

    def test_receipt_cannot_retire_before_formal_ci_and_trusted_deployment(self):
        for target, field, value in [('/actions/runs?', 'conclusion', 'failure'),
            ('/actions/runs?', 'event', 'workflow_dispatch'), ('/actions/runs?', 'run_attempt', 0),
            ('/deployments?', 'sha', 'a'*40), ('/deployments/201/statuses', 'state', 'failure'),
            ('/deployments/201/statuses', 'creator', {'login':'maintainer'}),
            ('/deployments/201/statuses', 'environment_url', 'https://other.example/')]:
            def change(path, result):
                if path.startswith(target):
                    rows = result['workflow_runs'] if isinstance(result, dict) and 'workflow_runs' in result else result
                    rows[0][field] = value
                return result
            self.api.tamper = change
            with self.subTest(target=target, field=field):
                with self.assertRaises(Exception): retirement.prepare(self.api, self.api.published, now=self.now)
                self.both(False)

    def test_missing_duplicate_skipped_wrong_sha_or_failed_steps_block_both(self):
        for mutate in [lambda d: d.update(jobs=[]), lambda d: d['jobs'].append(copy.deepcopy(d['jobs'][0])),
            lambda d: d['jobs'][0].update(conclusion='skipped'), lambda d: d['jobs'][0].update(head_sha='a'*40),
            lambda d: d['jobs'][0]['steps'][0].update(conclusion='failure')]:
            def change(path, result):
                if path.startswith('/actions/runs/101/'): mutate(result)
                return result
            self.api.tamper = change
            with self.subTest(mutate=mutate): self.both(False)

    def test_retirement_cannot_mix_settings_catalog_or_code_changes(self):
        original = self.candidate
        for path in [delivery.SOURCE, delivery.CATALOG, 'app.js']:
            self.candidate = original
            self.replace(path, b'changed')
            with self.subTest(path=path): self.both(False)

    def test_archive_identity_request_timestamp_and_evidence_are_exact(self):
        for field, value in [('version', True), ('repository', 'other/repo'), ('publishedSha', 'a'*40),
            ('receiptBlobSha', 'a'*40), ('request', {}), ('preparedAt', '2999-01-01T00:00:00.000Z'), ('evidence', {})]:
            record = json.loads(self.files[self.archive]); record[field] = value
            self.replace(self.archive, delivery.encoded(record))
            with self.subTest(field=field): self.both(False)

    def test_archive_bytes_and_claimed_exact_run_deployment_status_cannot_be_forged(self):
        raw = self.files[self.archive]
        for changed in [raw.replace(b'"version": 1,', b'"version": 1, "version": 1,'),
            json.dumps(json.loads(raw), separators=(',', ':')).encode(), b'\xff']:
            self.replace(self.archive, changed)
            with self.subTest(raw=changed[:40]): self.both(False)
        for field in ['deploymentId', 'statusId', 'workflows']:
            record = json.loads(raw)
            record['evidence'][field] = [] if field == 'workflows' else 999
            self.replace(self.archive, delivery.encoded(record))
            with self.subTest(field=field): self.both(False)

    def test_history_is_immutable_for_later_engineering(self):
        self.api.refs['main'] = self.candidate
        self.api.runs[self.candidate] = [{'path':'.github/workflows/delivery.yml', 'head_sha':self.candidate, 'event':'push', 'head_branch':'main', 'head_repository':{'full_name':delivery.REPO}}]
        self.candidate = self.api.candidate({'app.js':b'/* later code */'})
        self.both()
        self.replace(self.archive, b'{}\n'); self.both(False)

    def test_new_draft_does_not_erase_published_retirement_evidence(self):
        self.api.refs[delivery.BRANCH] = self.api.draft
        self.both()

    def test_formal_phase_keeps_exact_prior_success_when_retirement_is_deployed(self):
        self.api.refs['main'] = self.candidate
        def change(path, result):
            if path.startswith('/deployments?'):
                result.append(dict(id=203, sha=self.candidate, environment='Production', production_environment=False, creator={'login':'vercel[bot]'}))
            if path.startswith('/deployments/201/statuses'):
                result.insert(0, dict(id=204, state='inactive', creator={'login':'vercel[bot]'}, environment_url='https://chendermatologist-fixture.vercel.app'))
            return result
        self.api.tamper = change
        self.both()

    def test_formal_phase_cannot_hide_prior_failure_with_new_retirement_deployment(self):
        self.api.refs['main'] = self.candidate
        def change(path, result):
            if path.startswith('/deployments?'):
                result.append(dict(id=203, sha=self.candidate, environment='Production', production_environment=False, creator={'login':'vercel[bot]'}))
            if path.startswith('/deployments/201/statuses'):
                result.insert(0, dict(id=204, state='failure', creator={'login':'vercel[bot]'}, environment_url='https://chendermatologist-fixture.vercel.app'))
            return result
        self.api.tamper = change
        self.both(False)

    def test_symlink_executable_nested_or_reserved_root_archive_rejected(self):
        for mode, path in [('120000', self.archive), ('100755', self.archive), ('100644', self.archive+'/hidden'), ('120000', retirement.PREFIX[:-1])]:
            def change(url, result):
                if url.startswith('/git/trees/'):
                    for row in result['tree']:
                        if row['path'] == self.archive: row.update(mode=mode, path=path)
                return result
            self.api.tamper = change
            with self.subTest(mode=mode, path=path): self.both(False)

    def test_main_ci_attempt_and_deployment_status_races_block_both(self):
        for target in ['/git/ref/heads/main', '/actions/runs?', '/deployments/201/statuses']:
            count = []
            def change(path, result):
                if path.startswith(target):
                    count.append(path)
                    if len(count)>1:
                        if target.startswith('/git/'): result['object']['sha'] = 'a'*40
                        elif target.startswith('/actions/'): result['workflow_runs'][0]['run_attempt'] = 2
                        else: result.insert(0, dict(id=205, state='failure', creator={'login':'vercel[bot]'}, environment_url='https://chendermatologist-fixture.vercel.app'))
                return result
            self.api.tamper = change
            with self.subTest(target=target): self.both(False)

    def test_naive_clock_rejected(self):
        with self.assertRaisesRegex(ValueError, 'timezone'):
            retirement.prepare(self.api, self.api.published, now=self.now.replace(tzinfo=None))

    def test_publication_without_settings_intent_gate_cannot_retire(self):
        for value in [False, 1, None]:
            api = PublishedSettings(settings_policy=value)
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'settings delivery policy'):
                retirement.prepare(api, api.published, now=self.now)


class SettingsRetirementBundleTests(unittest.TestCase):
    # Reuse the real disposable repository builder, not its article test cases.
    run_git = article_retirement_fixture.RetirementTests.run_git
    write = article_retirement_fixture.RetirementTests.write
    commit = article_retirement_fixture.RetirementTests.commit

    def test_bundle_is_exclusive_external_exact_and_leaves_checkout_refs_unchanged(self):
        with tempfile.TemporaryDirectory(prefix='settings-retirement-root-') as folder:
            self.root = Path(folder)
            self.run_git('init', '-q')
            self.run_git('config', 'user.email', 'fixture@example.invalid')
            self.run_git('config', 'user.name', 'Isolated fixture')
            self.write('fixture.txt', b'unchanged'); self.commit('fixture')
            head = self.run_git('rev-parse', 'HEAD')
            refs, status = self.run_git('show-ref'), self.run_git('status', '--porcelain')
            h = PublishedSettings()
            files = retirement.prepare(h, h.published, now=datetime(2026,10,1,tzinfo=timezone.utc))
            # Output identity is bound to this local revision independently of
            # synthetic publication contents; no bundle is applied or committed.
            archive = retirement.PREFIX+head+'.json'
            files = {delivery.FILE:files[delivery.FILE], archive:files[retirement.PREFIX+h.published+'.json']}
            with tempfile.TemporaryDirectory(prefix='settings-retirement-output-') as outside:
                target = Path(outside)/'bundle'
                write_bundle(self.root, target, head, files, settings=True)
                self.assertEqual((target/delivery.FILE).read_bytes(), files[delivery.FILE])
                self.assertEqual((target/archive).read_bytes(), files[archive])
                for destination, data, expected in [(target,files,head), (self.root/'inside',files,head),
                    (Path(outside)/'escape', {'../unsafe':b'x'},head), (Path(outside)/'missing'/'bundle',files,head),
                    (Path(outside)/'wrong',files,'a'*40)]:
                    with self.subTest(destination=destination),self.assertRaises(ValueError):
                        write_bundle(self.root,destination,expected,data,settings=True)
                with self.assertRaises(ValueError): write_bundle(self.root,Path(outside)/'cms-contract',head,files)
                with self.assertRaises(ValueError): write_bundle(self.root,Path(outside)/'bad-contract',head,files,settings='yes')
            self.assertEqual(self.run_git('show-ref'),refs)
            self.assertEqual(self.run_git('status','--porcelain'),status)


if __name__ == '__main__': unittest.main()
