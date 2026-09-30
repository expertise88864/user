"""An audited generated sink must never become an unbounded file exemption."""
import tempfile
from pathlib import Path
import unittest
import _check_dangerous_sinks as audit


class GeneratedSinkAuditTests(unittest.TestCase):
    def test_current_complete_bundle_is_scanned_and_matches_audited_bytes(self):
        root = Path(__file__).resolve().parent
        path = root / 'admin/word-model.bundle.js'
        hits = len(audit.INNERHTML_RE.findall(audit.code_of(path)))
        self.assertEqual(hits, 1)
        self.assertEqual(audit.generated_sink_errors(path, 'admin/word-model.bundle.js', hits), [])
        paths, _ = audit.iter_files()
        self.assertIn(path, paths)
        self.assertNotIn('admin/word-model.bundle.js', audit.VENDORED)

    def test_even_same_sink_count_different_bytes_require_new_audit(self):
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bundle.js'
            path.write_bytes((root/'admin/word-model.bundle.js').read_bytes()+b'\nwindow.UNREVIEWED=true;\n')
            self.assertTrue(audit.generated_sink_errors(path, 'admin/word-model.bundle.js', 1))

    def test_new_sink_is_rejected_even_with_original_file_bytes(self):
        path = Path(__file__).resolve().parent/'admin/word-model.bundle.js'
        self.assertTrue(audit.generated_sink_errors(path, 'admin/word-model.bundle.js', 2))
        self.assertTrue(audit.generated_sink_errors(path, 'admin/word-model.bundle.js', 0))

    def test_git_checkout_line_endings_do_not_change_audit_identity(self):
        raw=(Path(__file__).resolve().parent/'admin/word-model.bundle.js').read_bytes().replace(b'\r\n',b'\n')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bundle.js';path.write_bytes(raw.replace(b'\n',b'\r\n'))
            self.assertEqual(audit.generated_sink_errors(path, 'admin/word-model.bundle.js', 1), [])

    def test_authored_sources_do_not_gain_an_html_sink_exemption(self):
        for name in ['admin/word-model.js','admin/draft-editor.js','admin/word-source.js','admin/word-media.js']:
            self.assertNotIn(name,audit.INNERHTML_ALLOWLIST)
            self.assertNotIn(name,audit.VENDORED)
            self.assertNotIn(name,audit.AUDITED_GENERATED_SINKS)


if __name__ == '__main__':
    unittest.main()
