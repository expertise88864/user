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
from _normalize_css_links import normalize_font_loading
from _gen_search_index import extract as search_extract


class FragmentTests(unittest.TestCase):
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
