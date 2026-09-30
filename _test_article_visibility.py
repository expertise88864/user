"""Visibility candidates preserve public bytes, metadata and indexing policy."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from _article_visibility import unpublish_plan
from _sync_hub_catalog import load_catalog
import _gen_feeds


class VisibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'blog').mkdir()
        self.catalog = self.root / 'blog/blog-shared.js'
        self.original_catalog = ("/* Keep header */ DN.ARTICLES = [\n"
            "  // Preserve artwork and editorial metadata\n"
            "  {slug:'other',title:'別篇 {標題}',title_en:'Other',emoji:'keep'},\n"
            "  {slug:'article',title:'作者的 \\'問題\\'',title_en:'Author\\'s title',cat:'note',date:'2026-09-30',desc:'保留原摘要'}\n"
            "];\n// Keep footer\n").encode()
        self.catalog.write_bytes(self.original_catalog)
        self.source = ('<!doctype html><html><head><title>文章</title>\n'
            '<meta content="index,follow,max-image-preview:large,max-snippet:-1" name="robots">'
            '<meta name="description" content="原摘要"></head><body><h1 id="title">作者文章</h1>'
            '<p>原段落 <a href="#keep">連結</a></p><svg id="keep"><path d="M0 0"/></svg>'
            '<script>window.KEEP="untouched"</script></body></html>').encode()

    def prepare(self, source=None):
        return unpublish_plan(self.root, 'blog/article.html', source or self.source, 'article')

    def test_only_visibility_changes_prose_markup_anchors_and_other_entries_preserved(self):
        before = load_catalog(self.root)
        files = self.prepare()
        self.assertEqual(set(files), {'blog/article.html', 'blog/blog-shared.js'})
        text = files['blog/article.html'].decode()
        old_meta = '<meta content="index,follow,max-image-preview:large,max-snippet:-1" name="robots">'
        new_meta = '<meta content="noindex,follow,max-image-preview:large,max-snippet:-1" name="robots">'
        self.assertEqual(text, self.source.decode().replace(old_meta, new_meta))
        # Preparation does not write; only applying the returned catalog changes it.
        self.assertEqual(self.catalog.read_bytes(), self.original_catalog)
        self.catalog.write_bytes(files['blog/blog-shared.js'])
        after = load_catalog(self.root)
        self.assertEqual(after[0], before[0])
        self.assertEqual({k:v for k,v in after[1].items() if k not in {'unpublished', 'cms_robots_before'}}, before[1])
        self.assertTrue(after[1]['unpublished'])
        self.assertEqual(after[1]['cms_robots_before'], 'index,follow,max-image-preview:large,max-snippet:-1')
        self.assertIn(b"// Preserve artwork and editorial metadata", files['blog/blog-shared.js'])
        self.assertIn(b"{slug:'other',title:", files['blog/blog-shared.js'])
        with patch.object(_gen_feeds, 'ROOT', self.root):
            self.assertEqual(_gen_feeds.get_unpublished_slugs(), {'article'})
            self.assertNotIn('article', _gen_feeds.parse_article_catalog())

    def test_original_noindex_and_nofollow_policy_is_remembered_not_unlocked(self):
        source = self.source.replace(b'index,follow,', b'noindex,nofollow,')
        files = self.prepare(source)
        self.catalog.write_bytes(files['blog/blog-shared.js'])
        item = load_catalog(self.root)[1]
        self.assertEqual(item['cms_robots_before'], 'noindex,nofollow,max-image-preview:large,max-snippet:-1')
        self.assertIn(b'content="noindex,nofollow,', files['blog/article.html'])
        self.assertNotIn(b'content="index,', files['blog/article.html'])

    def test_missing_duplicate_outside_head_or_ambiguous_robots_are_rejected(self):
        tag = b'<meta content="index,follow,max-image-preview:large,max-snippet:-1" name="robots">'
        for altered in (self.source.replace(tag, b''), self.source.replace(tag, tag*2),
                        self.source.replace(tag, b'').replace(b'</body>', tag+b'</body>'),
                        self.source.replace(tag, b'').replace(b'</head>', b'').replace(b'</body>', tag+b'</body>'),
                        self.source.replace(tag, b'<template>'+tag+b'</template>'),
                        self.source.replace(tag, b'<noscript>'+tag+b'</noscript>'),
                        self.source.replace(tag, b'<meta name="robots" name="other" content="index">'),
                        self.source.replace(tag, b'<meta name="robots" content="index" content="noindex">')):
            with self.subTest(source=altered), self.assertRaises(ValueError):
                self.prepare(altered)
            self.assertEqual(self.catalog.read_bytes(), self.original_catalog)

    def test_already_hidden_missing_entry_or_old_recovery_policy_is_rejected(self):
        for insertion in ("unpublished:true", "cms_robots_before:'index,follow'"):
            self.catalog.write_bytes(self.original_catalog.replace(b"desc:'", insertion.encode()+b",desc:'"))
            with self.subTest(insertion=insertion), self.assertRaises(ValueError):
                self.prepare()
        self.catalog.write_bytes(self.original_catalog.replace(b"slug:'article'", b"slug:'missing'"))
        with self.assertRaises(ValueError):
            self.prepare()

    def test_catalog_quoted_braces_comments_and_nested_data_keep_locations(self):
        self.catalog.write_bytes(self.original_catalog.replace(b"emoji:'keep'", b"emoji:'keep',details:{text:'}['},values:['{','}'] /* } ] */"))
        before = load_catalog(self.root)
        files = self.prepare()
        self.catalog.write_bytes(files['blog/blog-shared.js'])
        self.assertEqual(load_catalog(self.root)[0], before[0])

    def test_robots_attribute_order_quotes_other_attributes_and_byte_layout_survive(self):
        from _article_visibility import robots_content
        cases = [
            ('<meta name="robots" content="index,follow" id="keep" />', '<meta name="robots" content="noindex,follow" id="keep" />'),
            ("<META data-note='content=other' CONTENT='index,follow' name='ROBOTS'>", "<META data-note='content=other' CONTENT='noindex,follow' name='ROBOTS'>"),
            ('<meta name=robots content=index,follow >', '<meta name=robots content="noindex,follow" >'),
        ]
        for old, new in cases:
            with self.subTest(old=old):
                self.assertEqual(robots_content(old, 'noindex,follow'), new)

    def test_real_catalog_and_article_preserve_every_unrelated_entry_and_public_markup(self):
        from _article_visibility import Robots, robots_content
        root = Path(__file__).resolve().parent
        self.catalog.write_bytes((root / 'blog/blog-shared.js').read_bytes())
        source = (root / 'blog/dupilumab-long-term-maintenance.html').read_bytes()
        before = load_catalog(self.root)
        files = unpublish_plan(self.root, 'blog/dupilumab-long-term-maintenance.html', source, 'dupilumab-long-term-maintenance')
        self.catalog.write_bytes(files['blog/blog-shared.js'])
        after = load_catalog(self.root)
        self.assertEqual(len(after), len(before))
        for old, new in zip(before, after):
            if old['slug'] != 'dupilumab-long-term-maintenance':
                self.assertEqual(old, new)
            else:
                self.assertEqual({k:v for k,v in new.items() if k not in {'unpublished', 'cms_robots_before'}}, old)
                self.assertTrue(new['unpublished'])
        text = source.decode()
        left, right, old_policy = Robots(text).one()
        expected_policy = 'noindex,' + ','.join(part for part in old_policy.split(',') if part != 'index')
        self.assertEqual(files['blog/dupilumab-long-term-maintenance.html'].decode(),
                         text[:left] + robots_content(text[left:right], expected_policy) + text[right:])


if __name__ == '__main__':
    unittest.main()
