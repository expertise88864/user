"""Regression tests for translation integrity and review/session trust."""
from __future__ import annotations

import contextlib
import http.client
import io
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import _check_runtime_smoke as smoke
from _gen_en_pages import DataEnRenderer
import _translate_ui as translate

ROOT = Path(__file__).resolve().parent


class TranslationTests(unittest.TestCase):
    def test_plain_fields_escape_markup_and_preserve_literal_entities(self):
        from html import escape
        from html.parser import HTMLParser
        class Text(HTMLParser):
            def __init__(self, source):
                super().__init__(); self.parts = []; self.images = 0; self.feed(source)
            def handle_data(self, data): self.parts.append(data)
            def handle_starttag(self, tag, attrs):
                if tag == 'img': self.images += 1
        for marker in ('data-dn-text-only', 'data-dn-text-only=""'):
            for value in ('<img src="x" onerror="window.__injected=1"> & "quoted"',
                          '&lt;literal&gt; &copy; < 2', '</span><script>alert(1)</script>'):
                with self.subTest(marker=marker, value=value):
                    source = f'<span {marker} data-en="{escape(value, quote=True)}"><span>原文</span></span>'
                    rendered = DataEnRenderer().render(source)
                    parsed = Text(rendered)
                    self.assertEqual(''.join(parsed.parts), value)
                    self.assertEqual(parsed.images, 0)
                    self.assertNotIn('<script>', rendered)

    def test_rich_translation_without_plain_marker_preserves_links(self):
        source = '<p data-en="See &lt;a href=&quot;/en/tools&quot;&gt;tools&lt;/a&gt; &amp; notes">原文</p>'
        self.assertIn('See <a href="/en/tools">tools</a> & notes', DataEnRenderer().render(source))

    def test_localized_jsonld_plain_metadata_cannot_close_script(self):
        from _gen_en_pages import localize_jsonld
        title = '</script><img src="x" onerror="window.__injected=1">'
        source = '<script type="application/ld+json" id="keep">{"@type":"Article","headline":"Original"}</script>'
        rendered = localize_jsonld(source, title, 'Notes & examples')
        self.assertEqual(rendered.count('</script>'), 1)
        self.assertNotIn('<img', rendered)
        self.assertEqual(json.loads(rendered.split('>', 1)[1].rsplit('</script>', 1)[0])['headline'], title)

    def test_late_article_jsonld_passes_keep_two_blocks_safe_and_idempotent(self):
        import _normalize_article_metadata as metadata
        import _normalize_mentions as mentions
        import _normalize_is_based_on as based_on
        from _normalize_citations import serialize_citations
        from _json_html import script_json
        from html.parser import HTMLParser
        payload = '</script><img src="x" onerror="window.__injected=1"> <!-- <script>'
        citations = serialize_citations([{'@type':'ScholarlyArticle','name':payload}])
        blocks = ''.join('<script type="application/ld+json" id="block-'+str(i)+'">'+script_json({
            '@type':'MedicalWebPage','name':payload,'description':'Preserve block '+str(i),
            'keywords':'Existing','audience':{'@type':'MedicalAudience','audienceType':'Patient'}})+'</script>' for i in range(2))
        class Scripts(HTMLParser):
            def __init__(self, source):
                super().__init__();self.images=0;self.scripts=[];self.current=None;self.feed(source)
            def handle_starttag(self, tag, attrs):
                if tag=='img':self.images+=1
                if tag=='script':self.current=''
            def handle_data(self, data):
                if self.current is not None:self.current+=data
            def handle_endtag(self, tag):
                if tag=='script' and self.current is not None:
                    self.scripts.append(json.loads(self.current));self.current=None
        with tempfile.TemporaryDirectory() as directory:
            page=Path(directory)/'fixture.html'
            source='<html><head>'+citations+blocks+'</head><body><p>Fixture prose</p></body></html>'
            page.write_text(source,encoding='utf8')
            def run():
                with patch.object(metadata,'git_last_modified',return_value=None):
                    metadata.process_article(page,{},is_en=False)
                mentions.update_article(page,[])
                based_on.update_article(page)
            run();first=page.read_text(encoding='utf8');run()
            self.assertEqual(page.read_text(encoding='utf8'),first)
            parsed=Scripts(first);self.assertEqual(parsed.images,0)
            self.assertEqual(len(parsed.scripts),3)
            self.assertEqual(parsed.scripts[0]['@graph'][0]['name'],payload)
            for i,obj in enumerate(parsed.scripts[1:]):
                self.assertEqual(obj['name'],payload)
                self.assertEqual(obj['description'],'Preserve block '+str(i))

    def test_tools_and_medical_about_preserve_literal_values_without_script_breakout(self):
        import _normalize_tools_schema as tools
        import _normalize_medical_codes as codes
        from _json_html import script_json
        payload='</script><img src="x" onerror="window.__injected=1">'
        template='<html><head><script type="application/ld+json">'+script_json({
            '@type':'MedicalWebPage','about':{'@type':'MedicalCondition','name':'Old'}})+'</script></head></html>'
        source,_=tools.inject(template,{'@context':'https://schema.org','@graph':[{'@type':'WebApplication','name':payload}]})
        source,_=codes.update_article_about(source,[{'@type':'MedicalCondition','name':payload}],[])
        self.assertNotIn('<img',source)
        bodies=re.findall(r'<script\b[^>]*>(.*?)</script>',source,re.S)
        objects=[json.loads(body) for body in bodies]
        self.assertEqual(objects[0]['about']['name'],payload)
        self.assertEqual(objects[1]['@graph'][0]['name'],payload)

    def test_generated_qa_jsonld_is_safe_and_repeated_build_preserves_prose(self):
        import _gen_faq_from_qa as faq
        from html import escape
        payload='</script><img src="x" onerror="window.__injected=1">'
        with tempfile.TemporaryDirectory() as directory:
            page=Path(directory)/'fixture.html'
            body='<body><h2 id="faq">FAQ</h2><div class="qa"><h3>'+escape(payload)+'</h3><p>Fixture answer long enough.</p></div></body>'
            page.write_text('<html><head></head>'+body+'</html>',encoding='utf8')
            self.assertEqual(faq.process(page),1)
            first=page.read_text(encoding='utf8');self.assertIn(body,first)
            self.assertNotIn('<img',first)
            raw=re.search(r'<script\b[^>]*>(.*?)</script>',first,re.S)[1]
            self.assertEqual(json.loads(raw)['mainEntity'][0]['name'],payload)
            self.assertEqual(faq.process(page),0)
            self.assertEqual(page.read_text(encoding='utf8'),first)

    def test_authoring_details_faq_uses_safe_json_without_changing_values(self):
        # This older authoring helper replaces stdout at import. Run its real
        # extractor/injector in a child so it cannot close the test runner's IO.
        code = '''import json
import _gen_faqpage_jsonld as faq
source='<html><head></head><body><article><details><summary>&lt;/script&gt;&lt;img src=x&gt;</summary><p>A literal answer long enough.</p></details></article></body></html>'
items=faq.extract_faqs(source)
first,_=faq.inject(source,items)
second,_=faq.inject(first,items)
print(json.dumps({'html':first,'stable':first==second,'question':items[0]['q']}))
'''
        result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,
                              text=True,encoding='utf8',timeout=15,check=True)
        fixture=json.loads(result.stdout)
        self.assertTrue(fixture['stable'])
        self.assertNotIn('<img',fixture['html'])
        body=re.search(r'<script\b[^>]*>(.*?)</script>',fixture['html'],re.S)[1]
        self.assertEqual(json.loads(body)['mainEntity'][0]['name'],fixture['question'])

    def test_python312_read_text_interface_and_crlf(self):
        # Exercise the production path with the read_text API available in CI.
        original = Path.read_text

        def read_text_312(path, encoding=None, errors=None):
            return original(path, encoding=encoding, errors=errors)

        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / 'probe.html'
            page.write_bytes('<p>中文</p>\r\n'.encode())
            with patch.object(Path, 'read_text', read_text_312):
                raw, units = translate.units(page)
            self.assertTrue(raw.endswith('\r\n'))
            self.assertEqual(len(units), 1)

    def test_functional_markup_survives(self):
        cases = [
            ('<a href="/tools">工具</a>', 'Tools', False),
            ('<a href="/tools">工具</a>', '<a href="/elsewhere">Tools</a>', False),
            ('<a href="/tools">工具</a>', '<a href="/en/tools">Tools</a>', True),
            ('<span id="dose">說明</span>', '<span>Notes</span>', False),
            ('<span id="dose">說明</span>', '<em id="dose">Notes</em>', False),
            ('<label for="score">分數</label>', '<label>Score</label>', False),
            ('<button type="button">按下</button>', 'Click', False),
            ('<a href="/tools">工具</a>', '<!-- <a href="/tools">Tools</a> -->', False),
            ('<a href="/tools">一</a><a href="/tools">二</a>',
             '<a href="/tools">One</a>', False),
            ('<a href="mailto:a@example.com?subject=回饋&amp;cc=b@example.com">回饋</a>',
             '<a href="mailto:a@example.com?cc=b@example.com&amp;subject=Feedback">Feedback</a>', True),
            ('<a href="mailto:a@example.com?subject=回饋">回饋</a>',
             '<a href="mailto:other@example.com?subject=Feedback">Feedback</a>', False),
        ]
        for zh, en, accepted in cases:
            with self.subTest(en=en):
                self.assertEqual(not translate.refuse_reason(zh, en), accepted)

    def test_cli_injection_and_mirror(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'data'
            data.mkdir()
            source = '<p >說明<a href="/tools">工具</a></p>\r\n<p>中文</p>'
            page = root / 'probe.html'
            page.write_bytes(source.encode())
            table = {'strings': [
                {'zh': '說明<a href="/tools">工具</a>', 'en': 'See tools'},
                {'zh': '中文', 'en': 'still 中文'},
            ]}
            dest = data / 'ui-probe.json'
            dest.write_text(json.dumps(table), encoding='utf-8')
            with patch.object(translate, 'ROOT', root), patch.object(translate, 'DATA', data):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(translate.cmd_inject(['probe.html']), 1)
                self.assertEqual(page.read_bytes(), source.encode())
                table['strings'][0]['en'] = 'See <a href="/tools">tools</a>'
                dest.write_text(json.dumps(table), encoding='utf-8')
                with contextlib.redirect_stdout(io.StringIO()):
                    # Valid entries can apply, but any refusal still fails.
                    self.assertEqual(translate.cmd_inject(['probe.html']), 1)
                mirror = DataEnRenderer().render(page.read_text(encoding='utf-8'))
                self.assertIn('See <a href="/tools">tools</a>', mirror)
                self.assertEqual(page.read_bytes().count(b'\r\n'), 1)
                # Intentionally empty work is not an invalid translation.
                table['strings'][1]['en'] = ''
                dest.write_text(json.dumps(table), encoding='utf-8')
                before = page.read_bytes()
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(translate.cmd_inject(['probe.html']), 0)
                self.assertEqual(page.read_bytes(), before)

    def test_existing_translations(self):
        # The glossary closing note intentionally contains nine cards and must
        # still be refused. All other filled production entries remain valid.
        for name in ('tools', 'glossary'):
            entries = json.loads((ROOT / f'data/translations/ui-{name}.json').read_text(encoding='utf-8'))['strings']
            for entry in entries:
                if not entry['en'].strip():
                    continue
                with self.subTest(page=name, zh=entry['zh'][:45]):
                    reason = translate.refuse_reason(entry['zh'], entry['en'])
                    if 'gloss-card' in entry['zh']:
                        self.assertTrue(reason)
                    else:
                        self.assertEqual(reason, '')


class SmokeTransportTests(unittest.TestCase):
    def response(self, content=b'page',status=200):
        response = io.BytesIO(content)
        response.status = status
        response.headers = {'content-type': 'text/html'}
        return response

    def connection(self,response=None,failure=None):
        connection=Mock()
        connection.getresponse.side_effect=failure
        connection.getresponse.return_value=response
        return connection

    def test_transient_failure_then_fresh_response(self):
        for failure in (ConnectionResetError(), TimeoutError(), http.client.IncompleteRead(b'half')):
            with self.subTest(failure=type(failure).__name__):
                connections=[self.connection(failure=failure),self.connection(self.response())]
                with patch.object(smoke.http.client, 'HTTPConnection', side_effect=connections) as request:
                    with patch.object(smoke.time, 'sleep'):
                        self.assertEqual(smoke.fetch('http://127.0.0.1:1', '/'), ('page', 'text/html'))
                    self.assertEqual(request.call_count, 2)
                    for connection in connections:
                        connection.close.assert_called_once()
                        connection.request.assert_called_once_with('GET','/',headers={'Connection':'keep-alive'})

    def test_persistent_failure_stops(self):
        connections=[self.connection(failure=ConnectionResetError()) for _ in range(3)]
        with patch.object(smoke.http.client, 'HTTPConnection', side_effect=connections) as request:
            with patch.object(smoke.time, 'sleep'), self.assertRaises(AssertionError):
                smoke.fetch('http://127.0.0.1:1', '/')
            self.assertEqual(request.call_count, 3)
        for connection in connections:connection.close.assert_called_once()

    def test_http_error_is_not_retried(self):
        for code in (301,404,500):
            connection=self.connection(self.response(status=code))
            with patch.object(smoke.http.client, 'HTTPConnection', return_value=connection) as request:
                with self.assertRaisesRegex(AssertionError, f'HTTP {code}'):
                    smoke.fetch('http://127.0.0.1:1', '/')
                self.assertEqual(request.call_count, 1)
                connection.close.assert_called_once()

    def test_external_target_is_rejected_before_connection(self):
        with patch.object(smoke.http.client,'HTTPConnection') as request:
            for base in ('https://127.0.0.1','http://example.invalid','http://user@127.0.0.1'):
                with self.assertRaises(AssertionError):smoke.fetch(base,'/')
            request.assert_not_called()

    def test_content_contract_still_rejects_missing_runtime(self):
        connection=self.connection(self.response(b'wrong page'))
        with patch.object(smoke.http.client,'HTTPConnection',return_value=connection) as request:
            body,_=smoke.fetch('http://127.0.0.1:1','/')
            self.assertEqual(smoke.assert_contains('probe',body,['required runtime']),['probe: missing required runtime'])
            self.assertEqual(request.call_count,1)


@unittest.skipUnless(os.name == 'nt', 'PowerShell wrapper runs on Windows')
class ReviewSessionTests(unittest.TestCase):
    sid = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
    other = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'

    def run_wrapper(self, recorded=None, returned=None, mode='resume', explicit=None, count=1, rc=0):
        shell = shutil.which('pwsh') or shutil.which('powershell')
        self.assertIsNotNone(shell)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture', '-c',
                            'user.email=fixture@example.invalid', 'commit', '--allow-empty', '-qm', 'fixture'], check=True)
            tools = root / 'tools'
            tools.mkdir()
            wrapper = tools / 'codex_review.ps1'
            wrapper.write_text((ROOT / 'tools/codex_review.ps1').read_text(encoding='utf-8-sig'), encoding='utf-8-sig')
            state = root / '.codex-review'
            state.mkdir()
            if recorded is not None:
                (state / 'last_session_id').write_text(recorded)
            (state / 'last_pass').write_text(str(count))
            (state / 'usage.tsv').write_text(
                'timestamp\trepository\tmode\tmodel\teffort\tbase_ref\tsession_id\ttokens_used\tresult\tfindings\tpass\n'
                f'now\tfixture\tdeep\tgpt-5.6-sol\thigh\tHEAD\t{recorded}\t0\tREQUEST_CHANGES\t1\t{count}\n')
            events = [{'type': 'turn.completed', 'usage': {'input_tokens': 3, 'output_tokens': 2}}]
            if returned is not None:
                events.insert(0, {'type': 'thread.started', 'thread_id': returned})
            (root / 'events.txt').write_text('\n'.join(json.dumps(e) for e in events))
            driver = root / 'driver.ps1'
            driver.write_text('''
function codex {
    'called' | Set-Content called.txt
    $index = [array]::IndexOf($args, '-o')
    'APPROVE' | Set-Content -LiteralPath $args[$index + 1]
    Get-Content events.txt
    $global:LASTEXITCODE = [int]$env:REVIEW_TEST_RC
}
& ./tools/codex_review.ps1 $env:REVIEW_TEST_MODE $env:REVIEW_TEST_ARG
exit $LASTEXITCODE
''', encoding='utf-8-sig')
            env = dict(os.environ, REVIEW_TEST_MODE=mode, REVIEW_TEST_ARG=explicit or ('HEAD' if mode != 'resume' else ''), REVIEW_TEST_RC=str(rc))
            result = subprocess.run([shell, '-NoProfile', '-File', str(driver)], cwd=root,
                                    env=env, capture_output=True, text=True, errors='replace')
            session_file = state / 'last_session_id'
            return (result.returncode, (root / 'called.txt').exists(),
                    session_file.read_text() if session_file.exists() else None,
                    (state / 'last_pass').read_text(), result.stdout + result.stderr)

    def test_invalid_record_never_launches_cli(self):
        result = self.run_wrapper(recorded='-' * 36, returned=self.sid)
        self.assertEqual(result[0], 64, result[-1])
        self.assertFalse(result[1])

    def test_wrong_or_missing_returned_identity_preserves_state(self):
        for returned in (self.other, None, '-' * 36, self.sid + 'x'):
            with self.subTest(returned=returned):
                result = self.run_wrapper(recorded=self.sid, returned=returned)
                self.assertEqual(result[0], 4, result[-1])
                self.assertEqual(result[2:4], (self.sid, '1'))

    def test_same_identity_case_insensitive_and_more_than_two_rounds(self):
        result = self.run_wrapper(recorded=self.sid, returned=self.sid, explicit=self.sid.upper(), count=2)
        self.assertEqual(result[0], 0, result[-1])
        self.assertEqual(result[2:4], (self.sid, '3'))

    def test_failed_cli_does_not_advance_or_overwrite(self):
        result = self.run_wrapper(recorded=self.sid, returned=self.other, rc=1)
        self.assertEqual(result[0], 4, result[-1])
        self.assertEqual(result[2:4], (self.sid, '1'))

    def test_first_pass_requires_valid_metadata(self):
        for returned in (None, '-' * 36):
            result = self.run_wrapper(mode='deep', returned=returned)
            self.assertEqual(result[0], 4, result[-1])
            self.assertEqual(result[2:4], (None, '0'))
        result = self.run_wrapper(mode='deep', returned=self.sid)
        self.assertEqual(result[0], 0, result[-1])
        self.assertEqual(result[2:4], (self.sid, '1'))


if __name__ == '__main__':
    unittest.main()
