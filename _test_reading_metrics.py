"""Reading metadata counts rendered text, never a second copy from attributes."""
import unittest
from _normalize_schema import compute_metrics


class ReadingMetricsTests(unittest.TestCase):
    def test_rendered_english_translation_counted_once(self):
        text = ' '.join(['word'] * 800)
        source = f'<div id="proseZh"><p data-zh="原文" data-en="{text}">{text}</p></div>'
        self.assertEqual(compute_metrics(source, 'en'), {'wordCount':800, 'readingMinutes':4})

    def test_attribute_markup_does_not_become_visible_words(self):
        source = '<div id="proseEn"><p data-en="&lt;b&gt;Wrong hidden copy&lt;/b&gt;" title="Attribute words">Actual visible words</p></div>'
        self.assertEqual(compute_metrics(source, 'en'), {'wordCount':3, 'readingMinutes':2})

    def test_empty_english_placeholder_uses_rendered_fallback(self):
        source = '<div id="proseZh"><p data-en="One two three four">One two three four</p></div><div id="proseEn"></div>'
        self.assertEqual(compute_metrics(source, 'en'), {'wordCount':4, 'readingMinutes':2})

    def test_nested_prose_excludes_outside_reference_and_related_words(self):
        source = '<div id="proseEn"><div><p>First second</p></div><p>Third</p></div><footer>Excluded related reference text</footer>'
        self.assertEqual(compute_metrics(source, 'en'), {'wordCount':3, 'readingMinutes':2})

    def test_inert_text_and_comments_not_counted(self):
        source = '<div id="proseEn"><p>One &amp; two</p><!-- Excluded comment words --><script>Excluded script words</script><style>Excluded style words</style><template><p>Excluded template words</p></template></div>'
        self.assertEqual(compute_metrics(source, 'en'), {'wordCount':2, 'readingMinutes':2})

    def test_visible_symbols_and_authored_text_preserved(self):
        source = '<div id="proseEn"><p data-en="Old copy">Author changed words &gt; 2 and &lt; 4</p></div>'
        self.assertEqual(compute_metrics(source, 'en')['wordCount'], 6)

    def test_chinese_counting_contract_and_minimum_unchanged(self):
        source = '<div id="proseZh">' + '皮'*350 + ' ABC 123</div>'
        # The existing Chinese branch joins ASCII tokens after removing spaces.
        self.assertEqual(compute_metrics(source, 'zh-TW'), {'wordCount':351,'readingMinutes':2})
        self.assertEqual(compute_metrics('<div id="proseEn"></div>', 'en')['readingMinutes'],2)


if __name__ == '__main__':
    unittest.main()
