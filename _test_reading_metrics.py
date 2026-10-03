"""Reading metadata counts rendered text, never a second copy from attributes."""
import unittest
from _normalize_schema import compute_metrics
from _normalize_reading_shell import BLOCK, normalize
from _normalize_date_modified import prose_hash
from _gen_llms_full import extract_clean_body
from _gen_en_pages import apply_data_en, chinese_fragment_map
from _html_scan import attributes, iter_tags, tag_name
from _normalize_mentions import extract_body_text, build_term_index, derive_mentions


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


class ReadingNavigationTests(unittest.TestCase):
    """Root/translated articles need usable navigation without desktop JS."""

    def test_generated_source_ids_do_not_replace_legacy_english_fragments(self):
        source = ('<article class="prose"><h1>Guide</h1>'
                  '<h2 data-zh="第一章" data-en="First section">第一章</h2>'
                  '<h2 data-zh="第二章" data-en="Second section">第二章</h2>'
                  '<h2 id="authored" data-en="Third section">第三章</h2></article>')
        direct = normalize(apply_data_en(source), english=True)
        mirrored = normalize(apply_data_en(normalize(source)), english=True)
        ids = lambda text: [attributes(tag).get('id') for _,tag in iter_tags(text)
                            if tag_name(tag)=='h2' and not tag.startswith('</')]
        self.assertEqual(ids(mirrored), ids(direct))
        self.assertEqual(ids(mirrored), ['first-section', 'second-section', 'authored'])
        self.assertEqual(normalize(mirrored, english=True), mirrored)

    def test_generated_english_fragment_maps_back_to_exact_chinese_source(self):
        source = normalize('<article class="prose"><h1>Guide</h1>'
                           '<h2 data-en="First section">第一章</h2>'
                           '<h2 data-en="Second section">第二章</h2>'
                           '<h2 data-en="Third section">第三章</h2></article>')
        english = normalize(apply_data_en(source), english=True)
        self.assertEqual(chinese_fragment_map(source, english),
                         {'first-section':'第一章','second-section':'第二章','third-section':'第三章'})

    def test_generated_english_ids_reserve_authored_document_collisions(self):
        source = normalize('<aside id="first-section"></aside><article class="prose">'
                           '<h2 data-en="First section">第一章</h2>'
                           '<h2 data-en="Second section">第二章</h2>'
                           '<h2 id="second-section" data-en="Third section">第三章</h2></article>')
        english = normalize(apply_data_en(source), english=True)
        self.assertIn('href="#first-section-2"', english)
        self.assertIn('href="#second-section-2"', english)
        self.assertIn('<h2 id="second-section"', english)
        self.assertEqual(normalize(english, english=True), english)

    def test_generated_outline_does_not_reweight_glossary_mentions(self):
        source = ('<article class="prose"><h1>Fixture</h1><h2>Alpha</h2>'
                  '<p>Alpha Beta Beta</p><h2>Beta</h2><h2>Gamma</h2></article>')
        result = normalize(source)
        terms=[{'@id':'https://example.test/glossary#term-'+name.lower(),'name':name}
               for name in ('Alpha','Beta','Gamma')]
        index=build_term_index(terms)
        self.assertEqual(extract_body_text(result), extract_body_text(source))
        self.assertEqual(derive_mentions(extract_body_text(result),index,'fixture'),
                         derive_mentions(extract_body_text(source),index,'fixture'))

    def test_prose_article_root_preserves_authored_content_and_anchors(self):
        source = ('<article class="prose prose-lg"><h1>Guide</h1>'
                  '<h2 id="existing">First</h2><p>Keep this authored paragraph.</p>'
                  '<h2 id="second">Second</h2><h2 id="third">Third</h2></article>')
        result = normalize(source, english=True)
        self.assertIn('id="dn-inline-toc"', result)
        self.assertIn('href="#existing"', result)
        self.assertLess(result.index('</h1>'), result.index('id="dn-inline-toc"'))
        self.assertEqual(BLOCK.sub('', result), source)
        self.assertEqual(normalize(result, english=True), result)

    def test_translated_headings_keep_previous_desktop_fragments(self):
        source = ('<article><div id="proseEn" class="prose"><h2>What is psoriasis?</h2>'
                  '<h2>Six clinical subtypes</h2><h2>Severity assessment</h2>'
                  '<h2>Triggers</h2><h2>Diagnosis</h2><h2>Bottom line</h2></div></article>')
        result = normalize(source, english=True)
        for fragment in ('what-is-psoriasis', 'six-clinical-subtypes', 'severity-assessment',
                         'triggers', 'diagnosis', 'bottom-line'):
            self.assertIn('id="' + fragment + '"', result)
            self.assertIn('href="#' + fragment + '"', result)
        self.assertEqual(normalize(result, english=True), result)

    def test_new_heading_ids_do_not_collide_with_existing_document_ids(self):
        source = ('<aside id="overview"></aside><article><div id="proseEn">'
                  '<h2>Overview</h2><h2>Overview</h2><h2 id="overview-2">Author anchor</h2>'
                  '</div></article>')
        result = normalize(source, english=True)
        heading_ids = [attributes(tag).get('id') for _,tag in iter_tags(result)
                       if tag_name(tag)=='h2' and not tag.startswith('</')]
        self.assertEqual(heading_ids, ['overview-3', 'overview-4', 'overview-2'])
        self.assertIn('<h2 id="overview-2">Author anchor</h2>', result)

    def test_english_body_selected_without_changing_hidden_chinese_body(self):
        chinese = '<div id="proseZh"><h2>原文一</h2><h2>原文二</h2><h2>原文三</h2></div>'
        source = '<article>' + chinese + '<div id="proseEn"><h2>One</h2><h2>Two</h2><h2>Three</h2></div></article>'
        result = normalize(source, english=True)
        self.assertIn(chinese, result)
        self.assertIn('href="#one"', result)
        self.assertNotIn('href="#原文一"', result)

    def test_empty_english_placeholder_falls_back_to_rendered_body(self):
        source = ('<article><div id="proseEn"><!-- empty --></div><div id="proseZh">'
                  '<h2>First</h2><h2>Second</h2><h2>Third</h2></div></article>')
        result = normalize(source, english=True)
        self.assertIn('href="#first"', result)
        self.assertIn('In this article', result)

    def test_nested_class_prose_without_id_gets_navigation(self):
        source = '<article><section class="prose"><h2>First</h2><h2>Second</h2><h2>Third</h2></section></article>'
        self.assertIn('id="dn-inline-toc"', normalize(source, english=True))

    def test_root_prose_keeps_outline_when_an_inner_example_is_also_prose(self):
        source = ('<article class="prose"><h2>First</h2>'
                  '<section class="prose"><p>An inner formatted example.</p></section>'
                  '<h2>Second</h2><h2>Third</h2></article>')
        self.assertIn('href="#third"', normalize(source, english=True))

    def test_inert_headings_do_not_create_a_false_three_section_outline(self):
        source = ('<article class="prose"><h2>First</h2><h2>Second</h2>'
                  '<template><h2>Not rendered</h2></template>'
                  '<script>"<h2>Not rendered</h2>"</script>'
                  '<!-- <h2>Not rendered</h2> --></article>')
        self.assertNotIn('id="dn-inline-toc"', normalize(source, english=True))

    def test_markup_and_quoted_attribute_text_are_not_fake_headings(self):
        source = ('<article><div id="proseEn"><h2 id="" title="a > b" data-en="<h2>fake</h2>">'
                  'A &amp; B</h2><h2><em>Nested</em> title</h2><h2>第三章</h2></div></article>')
        result = normalize(source, english=True)
        self.assertIn('href="#a-b"', result)
        self.assertIn('href="#nested-title"', result)
        self.assertIn('href="#第三章"', result)
        self.assertIn('title="a > b" data-en="<h2>fake</h2>"', result)
        self.assertIn('A &amp; B', result)
        self.assertEqual(normalize(result, english=True), result)

    def test_non_prose_article_cards_are_untouched(self):
        source = '<article><h2>Card one</h2><h2>Card two</h2><h2>Card three</h2></article>'
        self.assertEqual(normalize(source, english=True), source)

    def test_generated_root_outline_does_not_restamp_authored_content_date(self):
        source = ('<article class="prose"><h1>Guide</h1><h2>First</h2><p>' +
                  '皮膚衛教' * 150 + '</p><h2>Second</h2><h2>Third</h2></article>')
        result = normalize(source)
        self.assertIsNotNone(prose_hash(source))
        self.assertEqual(prose_hash(result), prose_hash(source))
        self.assertNotEqual(prose_hash(result.replace('皮膚衛教', '作者更新', 1)), prose_hash(source))

    def test_generated_root_outline_does_not_duplicate_reading_word_count(self):
        source = ('<article class="prose"><h1>Guide</h1><h2>First</h2><p>' +
                  'word ' * 600 + '</p><h2>Second</h2><h2>Third</h2></article>')
        result = normalize(source, english=True)
        self.assertEqual(compute_metrics(result, 'en'), compute_metrics(source, 'en'))
        self.assertEqual(compute_metrics(result.replace('word ', 'new word ', 1), 'en')['wordCount'],
                         compute_metrics(source, 'en')['wordCount'] + 1)

    def test_root_outline_does_not_displace_the_length_limited_authored_corpus(self):
        source = ('<article class="prose"><h1>Fixture</h1><h2>First</h2><p>' +
                  'Nonmedical fixture text. ' * 400 + '</p><h2>Second</h2><h2>Third</h2></article>')
        result = normalize(source)
        before, after = extract_clean_body(source), extract_clean_body(result)
        self.assertGreater(len(before), 6000)
        self.assertEqual(after, before)
        self.assertEqual(after[:6000], before[:6000])
        self.assertIn('An authored addition', extract_clean_body(result.replace('</p>', 'An authored addition</p>', 1)))


if __name__ == '__main__':
    unittest.main()
