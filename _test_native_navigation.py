"""The navigation cleanup must preserve author text and accessibility styles."""
from pathlib import Path
import unittest

from _normalize_native_navigation import normalize

# Fixed historical fragment, independent of the normalizer's constants and
# repository history. Vercel/CI may use a shallow checkout of the fixed HEAD.
LEGACY = ('<!-- a11y-vt-applied --><meta name="view-transition" content="same-origin"><style>'
          '@view-transition{navigation:auto}'
          '::view-transition-old(root),::view-transition-new(root){animation-duration:.25s}'
          '@media(prefers-reduced-motion:reduce){::view-transition-old(root),::view-transition-new(root){animation:none}}')
NORMAL = '<!-- a11y-vt-applied --><style>'


class NativeNavigationTests(unittest.TestCase):
    def test_actual_legacy_article_preserves_everything_else(self):
        expected = Path('blog/tinea-myths.html').read_text(encoding='utf-8')
        self.assertEqual(expected.count(NORMAL), 1)
        original = expected.replace(NORMAL, LEGACY, 1)
        self.assertNotEqual(original, expected)
        actual = normalize(original)
        self.assertEqual(actual, expected)
        self.assertIn('*:focus-visible{', actual)
        self.assertIn('skip-to-main', actual)
        self.assertEqual(normalize(actual), actual)

    def test_examples_scripts_and_unmarked_styles_are_preserved(self):
        example = LEGACY + '</style>'
        source = '<html><head><script>const sample = ' + repr(example) + ';</script>'
        source += '<style>@view-transition{navigation:auto}</style></head><body><textarea>' + example + '</textarea>'
        source += '<p>Explain @view-transition{navigation:auto}</p></body></html>'
        self.assertEqual(normalize(source), source)

    def test_newer_destination_has_no_legacy_changes(self):
        original = Path('blog/toenail-mechanical-disorders.html').read_text(encoding='utf-8')
        self.assertEqual(normalize(original), original)


if __name__ == '__main__':
    unittest.main()
