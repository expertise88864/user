import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import _check_internal_links as links
import _normalize_tools_schema as tools_schema
import _check_en_internal_links as en_links
import _check_supply_chain as supply
import _normalize_mentions as mentions
from _normalize_css_links import normalize_font_loading, normalize_file as normalize_css_file
from _gen_search_index import extract as search_extract
from _normalize_heading_structure import normalize_content_headings
from _gen_en_pages import extract_faqs
from _normalize_reading_shell import normalize as reading_shell, BLOCK as reading_shell_block


class FragmentTests(unittest.TestCase):
    def test_reading_shell_preserves_content_and_is_idempotent(self):
        source = '<main><h1>Title</h1><article><div id="proseZh"><h2 id="one">First &amp; second</h2><p>Approved clinical text.</p><h2 id="two">Two</h2><h2 id="three">Three</h2></div></article></main>'
        result = reading_shell(source)
        self.assertEqual(reading_shell_block.sub('', result), source)
        self.assertEqual(reading_shell(result), result)
        self.assertEqual(result.count('id="dn-inline-toc"'), 1)
        self.assertIn('href="#one"', result)
        self.assertIn('First &amp; second</a>', result)
        self.assertEqual(extract_faqs(result), [])
        english = reading_shell(result, True)
        self.assertIn('Cover and reading information', english)
        self.assertIn('In this article', english)

    def test_reading_shell_keeps_existing_patient_metadata_and_article_h1(self):
        source = '<details id="dn-secondary-meta">Existing</details><article><h1>Title</h1><div id="proseZh">' + ''.join(f'<h2 id="h{i}">Heading {i}</h2>' for i in range(3)) + '</div></article>'
        result = reading_shell(source)
        self.assertEqual(result.count('id="dn-secondary-meta"'), 1)
        self.assertLess(result.index('</h1>'), result.index('id="dn-inline-toc"'))
        self.assertEqual(reading_shell_block.sub('', result), source)

    def test_reading_shell_uses_only_the_active_language_prose(self):
        zh = '<div id="proseZh">' + ''.join(f'<h2 id="zh{i}">中文 {i}</h2>' for i in range(3)) + '</div>'
        en = '<div id="proseEn">' + ''.join(f'<h2 id="en{i}">English {i}</h2>' for i in range(3)) + '</div>'
        source = '<article>' + zh + en + '</article>'
        result = reading_shell(source)
        self.assertIn('href="#zh0"', result)
        self.assertNotIn('href="#en0"', result)
        english = reading_shell('<article>' + en + '</article>', True)
        self.assertIn('href="#en0"', english)
        self.assertEqual(reading_shell(english, True), english)

    def test_english_faq_ignores_reading_disclosures_but_keeps_real_questions(self):
        source = '''<details class="dn-article-details"><summary>Article background</summary>
            <p>Background, cover and reading information.</p></details>
            <details id='dn-reading-settings'><summary>Reading settings</summary>
            <p>Choose a comfortable text size.</p></details>
            <details class="faq"><summary>Where can I find references?</summary>
            <p>References are listed at the end of this article.</p></details>'''
        faqs = extract_faqs(source)
        self.assertEqual(len(faqs), 1)
        self.assertEqual(faqs[0]['name'], 'Where can I find references?')
        self.assertEqual(faqs[0]['acceptedAnswer']['text'],
                         'References are listed at the end of this article.')

    def test_article_missing_shared_stylesheet_is_repaired_once(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'article.html'
            p.write_text('<head></head><body><h1>Title</h1><article>Body</article></body>', encoding='utf-8')
            self.assertTrue(normalize_css_file(str(p)))
            result = p.read_text(encoding='utf-8')
            self.assertEqual(result.count('id="dn-below-fold-css"'), 1)
            self.assertFalse(normalize_css_file(str(p)))

    def test_article_title_has_stable_shared_style(self):
        source = '<main><h1 class="text-[28px]">Title</h1><article><p>Body</p></article></main>'
        result = normalize_content_headings(source)
        self.assertIn('text-[28px] dn-article-title', result)
        self.assertEqual(normalize_content_headings(result), result)
        non_article = '<h1>Home</h1><script>const example = "<article>";</script>'
        self.assertEqual(normalize_content_headings(non_article), non_article)

    def test_search_extraction_recovers_after_hidden_void_elements(self):
        source = ('<head><noscript><link rel="stylesheet" href="/fonts.css"></noscript></head>'
                  '<body><h1>Visible title</h1><div hidden><img src="hidden.png"><p>Hidden text</p></div>'
                  '<p>This visible paragraph must still be available to the search index.</p></body>')
        result = search_extract(source)
        self.assertEqual(result['title'], 'Visible title')
        self.assertEqual(result['snippet'], 'This visible paragraph must still be available to the search index.')

    def test_font_loading_is_nonblocking_and_idempotent(self):
        source = '<head><link href="https://fonts.googleapis.com/css2?family=Inter&amp;display=optional" rel="stylesheet"></head><body>Text</body>'
        result = normalize_font_loading(source)
        self.assertEqual(normalize_font_loading(result), result)
        self.assertIn('media="print"', result)
        self.assertIn('<noscript><link rel="stylesheet"', result)
        self.assertEqual(result.count('font-loader.js?'), 1)
        self.assertNotIn('onload=', result)
        self.assertTrue(result.endswith('<body>Text</body>'))

    def test_optional_webfonts_do_not_download_cjk_shards(self):
        source = '<head><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&amp;family=Noto+Sans+TC:wght@400;500&amp;family=Noto+Serif+TC:wght@600;700&amp;display=optional"></head>'
        result = normalize_font_loading(source)
        self.assertIn('family=Inter', result)
        self.assertNotIn('Noto', result)
        self.assertEqual(normalize_font_loading(result), result)

    def test_font_loader_stays_stable_when_other_generators_append_head_entries(self):
        source = '<head><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter"></head>'
        result = normalize_font_loading(source)
        appended = result.replace('</head>', '<script defer src="/assets/web-vitals.iife.js"></script><style id="dn-nav-critical">nav{display:flex}</style></head>')
        self.assertEqual(normalize_font_loading(appended), appended)

    def test_cjk_only_stylesheet_does_not_leave_an_unused_font_loader(self):
        source = '<head><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC"></head>'
        self.assertEqual(normalize_font_loading(source), '<head></head>')

    def test_language_links_with_markup_in_attributes(self):
        parser = en_links.PageLinks()
        parser.feed('<a data-en="<strong>Open</strong>" href="/tools?a=1&amp;b=2">Open</a>')
        self.assertEqual(parser.hrefs, ['/tools?a=1&b=2'])

    def test_supply_chain_urls_survive_comment_stripping(self):
        floating = '@' + 'latest'
        for suffix, marker in (('.py', '#'), ('.mjs', '//'), ('.ps1', '#')):
            source = f'{marker} pkg{floating}\nurl = "https://esm.sh/pkg{floating}#fragment" {marker} note\n'
            scrubbed = supply.strip_line_comments(source, suffix)
            self.assertEqual(len(supply.LATEST_SPEC_RE.findall(scrubbed)), 1)
            self.assertEqual(len(source), len(scrubbed))
            self.assertEqual(source.count('\n'), scrubbed.count('\n'))

    def test_mention_ties_follow_first_body_occurrence(self):
        index = [{'@id': '#term-later', 'name': 'Later', 'tokens': [('後', 'literal')]},
                 {'@id': '#term-earlier', 'name': 'Earlier', 'tokens': [('先', 'literal')]}]
        result = mentions.derive_mentions('先，後', index, '', max_mentions=1)
        self.assertEqual(result[0]['@id'], '#term-earlier')

    def test_english_tool_schema_keeps_calculator_fragment_on_canonical_url(self):
        source = '<article class="tool-block" id="scorad"><h2>SCORAD</h2><a href="/en/blog/atopic-dermatitis-overview#dn-scorad">Open</a></article>'
        tool = tools_schema.parse_tools(source)[0]
        app = tools_schema.build_app(tool, 'en')
        self.assertEqual(app['url'], 'https://chendermatologist.com/blog/atopic-dermatitis-overview#dn-scorad')
        self.assertEqual(app['inLanguage'], 'en')

    def check(self, href):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text(f'<main id="real"><a href="{href}">link</a></main>', encoding='utf-8')
            (root / 'target.html').write_text('<h2 id="段落">Title</h2>', encoding='utf-8')
            with patch.object(links, 'ROOT', root), patch.object(links, 'MIN_LINKS_RESOLVED', 0), \
                    patch.object(links, 'calculator_anchors', return_value={}), contextlib.redirect_stdout(io.StringIO()):
                return links.main()

    def test_same_page_missing_fragment_is_rejected(self):
        self.assertEqual(self.check('#missing'), 1)
        self.assertEqual(self.check('#real'), 0)

    def test_cross_page_fragment_including_query_and_encoding(self):
        self.assertEqual(self.check('/target?mode=read#missing'), 1)
        self.assertEqual(self.check('/target?mode=read#%E6%AE%B5%E8%90%BD'), 0)

    def test_attribute_payload_is_not_a_real_anchor(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'target.html'
            target.write_text('<div data-en=\'<span id="phantom">text</span>\'></div><meta name="fake">', encoding='utf-8')
            self.assertNotIn('phantom', links.anchors_for(target, {}))
            self.assertNotIn('fake', links.anchors_for(target, {}))

    def test_courtesy_mirror_fallback_requires_real_source_section(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'en').mkdir()
            (root / 'target.html').write_text('<h2 id="detail">Detail</h2>', encoding='utf-8')
            (root / 'en/target.html').write_text('<h2 id="overview">Overview</h2>', encoding='utf-8')
            with patch.object(links, 'ROOT', root):
                self.assertTrue(links.needs_zh_fragment('/target#detail', {}, {}))
                self.assertFalse(links.needs_zh_fragment('/target#missing', {}, {}))
                (root / 'en/target.html').write_text('<h2 id="detail">Detail</h2>', encoding='utf-8')
                self.assertFalse(links.needs_zh_fragment('/target#detail', {}, {}))


if __name__ == '__main__':
    unittest.main()
