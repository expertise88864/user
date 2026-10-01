"""The navigation cleanup must preserve author text and accessibility styles."""
from pathlib import Path
import subprocess
import unittest

from _normalize_native_navigation import MARKER, META, RULES, normalize


class NativeNavigationTests(unittest.TestCase):
    def test_actual_legacy_article_preserves_everything_else(self):
        original = subprocess.check_output(['git', 'show', 'HEAD:blog/tinea-myths.html']).decode('utf-8')
        expected = original.replace(META, '')
        for rule in RULES:
            expected = expected.replace(rule, '')
        self.assertNotEqual(original, expected)
        actual = normalize(original)
        self.assertEqual(actual, expected)
        self.assertIn('*:focus-visible{', actual)
        self.assertIn('skip-to-main', actual)
        self.assertEqual(normalize(actual), actual)

    def test_examples_scripts_and_unmarked_styles_are_preserved(self):
        example = MARKER + META + '<style>' + RULES[0] + '</style>'
        source = '<html><head><script>const sample = ' + repr(example) + ';</script>'
        source += '<style>' + RULES[0] + '</style></head><body><textarea>' + example + '</textarea>'
        source += '<p>Explain @view-transition{navigation:auto}</p></body></html>'
        self.assertEqual(normalize(source), source)

    def test_newer_destination_has_no_legacy_changes(self):
        original = Path('blog/toenail-mechanical-disorders.html').read_text(encoding='utf-8')
        self.assertEqual(normalize(original), original)


if __name__ == '__main__':
    unittest.main()
