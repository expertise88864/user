import unittest
from unittest.mock import patch
from pathlib import Path
from _sync_article_navigation import canonical_header, migrate_article, update_editor
from _check_article_runtime import check_article, ROOT

HEADER='<header><nav class="dn-nav">shared links</nav></header>'
BODY='<main><article><h1>Physician headline</h1><p data-en="Original">醫師原文</p><code>class="dn-nav"</code></article></main>'

class NavigationGenerationTests(unittest.TestCase):
    def test_only_legacy_header_changes_and_second_pass_is_identical(self):
        original='<html><head></head><body><header>legacy</header>'+BODY+'</body></html>'
        result=migrate_article(original,HEADER)
        self.assertIn(BODY,result)
        self.assertIn(HEADER,result)
        self.assertNotIn('legacy',result)
        self.assertEqual(migrate_article(result,HEADER),result)
    def test_missing_header_receives_shared_navigation(self):
        source='<html><head></head><body>'+BODY+'</body></html>'
        self.assertIn(HEADER+BODY,migrate_article(source,HEADER))
    def test_existing_shared_header_is_not_overwritten(self):
        source='<html><head></head><body>'+HEADER+BODY+'</body></html>'
        result=migrate_article(source,HEADER.replace('shared','changed'))
        self.assertIn(HEADER,result)
        self.assertNotIn('changed links',result)
        self.assertIn('/assets/inline/nav-burger.js',result)
    def test_ambiguous_or_missing_structure_fails_before_writing(self):
        with self.assertRaises(ValueError): migrate_article(HEADER+HEADER+BODY,HEADER)
        with self.assertRaises(ValueError): migrate_article('<p>no main</p>',HEADER)
        with self.assertRaises(ValueError): canonical_header('<header>no shared nav</header>')
    def test_editor_slots_are_required_and_script_delimiters_are_escaped(self):
        source='const navigationHeader = ""; // generated navigation\nconst navigationStyles = ""; // generated navigation\n'
        result=update_editor(source,HEADER)
        self.assertIn(r'\u003cheader>',result)
        self.assertNotIn('<header>',result)
        self.assertEqual(update_editor(result,HEADER),result)
        with self.assertRaises(ValueError): update_editor('',HEADER)
    def test_noindex_articles_still_require_navigation(self):
        source='<html><head><meta name="robots" content="noindex,nofollow"></head><body>'+BODY+'</body></html>'
        with patch.object(Path,'read_text',return_value=source):
            errors=check_article(ROOT/'blog'/'temporary-test.html')
        self.assertTrue(any('navigation' in error for error in errors))
        self.assertFalse(any('blog-shared' in error for error in errors))

if __name__=='__main__': unittest.main()
