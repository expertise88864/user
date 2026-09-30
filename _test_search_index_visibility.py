"""Full-text search respects author visibility and inert article fragments."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import _gen_search_index as search
from _article_visibility import unpublish_plan


class SearchVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='search-visibility-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'blog').mkdir()
        (self.root / 'assets').mkdir()
        self.catalog = self.root / 'blog/blog-shared.js'
        self.output = self.root / 'assets/search-index.json'
        self.entries = [dict(slug=name, title=name, title_en=name,
                             cat='note', date='2026-01-01')
                        for name in ['visible', 'hidden']]
        self.write_catalog()
        for name in ['visible', 'hidden']:
            (self.root / 'blog' / (name + '.html')).write_text(
                '<!doctype html><html><head><meta name="robots" content="index,follow"></head>'
                '<body><main><h1>' + name + '</h1><p>' + name * 20 + '</p></main></body></html>',
                encoding='utf-8')

    def write_catalog(self, indent=None):
        self.catalog.write_text('DN.ARTICLES = ' + json.dumps(self.entries, indent=indent) + ';', encoding='utf-8')

    def generate(self):
        with patch.object(search, 'ROOT', str(self.root)), patch.object(search, 'BLOG', str(self.root / 'blog')), patch.object(search, 'OUT', str(self.output)):
            search.main()
        return json.loads(self.output.read_text(encoding='utf-8'))

    def test_double_quoted_unpublished_entry_does_not_leak_into_search(self):
        self.entries[1]['unpublished'] = True
        self.write_catalog()
        self.assertEqual([item['slug'] for item in self.generate()], ['visible'])

    def test_multiline_catalog_visibility_uses_the_same_parser_as_cms(self):
        self.entries[1]['unpublished'] = True
        self.write_catalog(indent=2)
        with patch.object(search, 'ROOT', str(self.root)):
            self.assertEqual(search.get_unpublished_slugs(), {'hidden'})
        self.assertEqual([item['slug'] for item in self.generate()], ['visible'])

    def test_actual_unpublish_plan_stays_out_of_search_without_removing_source(self):
        source = (self.root / 'blog/hidden.html').read_bytes()
        for name, content in unpublish_plan(self.root, 'blog/hidden.html', source, 'hidden').items():
            (self.root / name).write_bytes(content)
        self.assertEqual([item['slug'] for item in self.generate()], ['visible'])
        self.assertTrue((self.root / 'blog/hidden.html').exists())

    def test_late_noindex_with_reordered_case_insensitive_attributes_is_respected(self):
        p = self.root / 'blog/hidden.html'
        src = p.read_text(encoding='utf-8').replace('</head>', '<!--' + 'x' * 6500 + '--><meta CONTENT="follow,NOINDEX" NAME="robots"></head>')
        p.write_text(src, encoding='utf-8')
        self.assertEqual([item['slug'] for item in self.generate()], ['visible'])

    def test_googlebot_none_also_respects_nonindexable_editorial_intent(self):
        p = self.root / 'blog/hidden.html'
        p.write_text(p.read_text(encoding='utf-8').replace('</head>', '<meta name="googlebot" content="none"></head>'), encoding='utf-8')
        self.assertEqual([item['slug'] for item in self.generate()], ['visible'])

    def test_ambiguous_robots_attributes_fail_closed(self):
        for tag in [
            '<meta name="robots" content="noindex" content="index,follow">',
            '<meta name="robots" name="other" content="noindex">',
            '<meta name="other" name="googlebot" content="index,follow">',
            '<meta name="googlebot" content="none" content="index">',
        ]:
            with self.subTest(tag=tag):
                self.assertEqual(search.extract(tag + '<h1>Hidden title</h1>'), {})

    def test_inert_noindex_examples_do_not_hide_a_public_article(self):
        inert = '<!--<meta name="robots" content="noindex">--><template><meta name="robots" content="noindex"></template><textarea><meta name="googlebot" content="none"></textarea><script>const example="<meta name=robots content=noindex>";</script>'
        p = self.root / 'blog/visible.html'
        p.write_text(p.read_text(encoding='utf-8').replace('</head>', inert + '</head>'), encoding='utf-8')
        self.assertEqual([item['slug'] for item in self.generate()], ['hidden', 'visible'])

    def test_template_draft_text_is_not_a_title_heading_or_snippet(self):
        src = '<template><h1>Draft title</h1><h2>Draft topic</h2><p>' + 'draft ' * 20 + '</p></template><h1>Public title</h1><h2>Public topic</h2><p>' + 'visible ' * 20 + '</p>'
        data = search.extract(src)
        self.assertEqual(data['title'], 'Public title')
        self.assertEqual(data['h'], ['Public topic'])
        self.assertNotIn('draft', data['snippet'])

    def test_missing_or_invalid_catalog_preserves_the_last_index_instead_of_publishing_every_file(self):
        sentinel = b'[{"slug":"previous"}]'
        for value in [None, 'DN.ARTICLES = [];', 'DN.ARTICLES = notValid;']:
            with self.subTest(catalog=value):
                self.output.write_bytes(sentinel)
                if value is None:
                    self.catalog.unlink(missing_ok=True)
                else:
                    self.catalog.write_text(value, encoding='utf-8')
                with self.assertRaises((OSError, ValueError, subprocess.CalledProcessError)):
                    self.generate()
                self.assertEqual(self.output.read_bytes(), sentinel)

    def test_public_clinical_companion_outside_patient_catalog_remains_searchable(self):
        p = self.root / 'blog/companion.html'
        p.write_text('<html><head><meta name="robots" content="index,follow"></head><body><h1>Clinical companion</h1></body></html>', encoding='utf-8')
        self.assertEqual([item['slug'] for item in self.generate()], ['companion', 'hidden', 'visible'])


if __name__ == '__main__':
    unittest.main()
