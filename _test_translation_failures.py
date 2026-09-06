import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import _ai_translate as translate


class TranslationFailureTests(unittest.TestCase):
    def test_missing_key_fails(self):
        with patch.object(sys, 'argv', ['_ai_translate.py', '--all']), \
                patch.object(translate, 'API_KEY', ''), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(translate.main(), 1)

    def test_missing_source_fails_without_network(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(translate, 'DATA', directory), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(translate.translate_file('missing'), 1)

    def test_empty_translation_is_saved_but_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'example.json'
            data = {'strings':[{'zh':'範例','en':''}]}
            path.write_text(json.dumps(data), encoding='utf-8')
            with patch.object(translate, 'DATA', directory), \
                    patch.object(translate, 'translate_batch', return_value=['']), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(translate.translate_file('example'), 1)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), data)

    def test_pipeline_bad_usage_has_nonzero_exit(self):
        for args in ([], ['unknown','example']):
            result = subprocess.run([sys.executable, '_translate_pipeline.py', *args], capture_output=True)
            self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
