"""Regression tests for translation integrity and review/session trust."""
from __future__ import annotations

import contextlib
import http.client
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import _check_runtime_smoke as smoke
from _gen_en_pages import DataEnRenderer
import _translate_ui as translate

ROOT = Path(__file__).resolve().parent


class TranslationTests(unittest.TestCase):
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
    def response(self, content=b'page'):
        response = io.BytesIO(content)
        response.headers = {'content-type': 'text/html'}
        return response

    def test_transient_failure_then_fresh_response(self):
        for failure in (ConnectionResetError(), TimeoutError(), http.client.IncompleteRead(b'half')):
            with self.subTest(failure=type(failure).__name__):
                with patch.object(smoke.urllib.request, 'urlopen', side_effect=[failure, self.response()]) as request:
                    with patch.object(smoke.time, 'sleep'):
                        self.assertEqual(smoke.fetch('http://127.0.0.1:1', '/'), ('page', 'text/html'))
                    self.assertEqual(request.call_count, 2)

    def test_persistent_failure_stops(self):
        with patch.object(smoke.urllib.request, 'urlopen', side_effect=ConnectionResetError()) as request:
            with patch.object(smoke.time, 'sleep'), self.assertRaises(AssertionError):
                smoke.fetch('http://127.0.0.1:1', '/')
            self.assertEqual(request.call_count, 3)

    def test_http_error_is_not_retried(self):
        for code in (404, 500):
            error = urllib.error.HTTPError('http://127.0.0.1:1', code, 'failed', {}, None)
            with patch.object(smoke.urllib.request, 'urlopen', side_effect=error) as request:
                with self.assertRaisesRegex(AssertionError, f'HTTP {code}'):
                    smoke.fetch('http://127.0.0.1:1', '/')
                self.assertEqual(request.call_count, 1)


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
