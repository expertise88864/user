"""Regression tests for raw-HTML article discovery and draft boundaries."""
import tempfile
from pathlib import Path
import unittest

from _sync_hub_catalog import CardList, load_catalog, public_catalog, render_card, sync_source


class HubCatalogTests(unittest.TestCase):
    def setUp(self):
        self.first = dict(slug="first", title="原有文章", title_en="Reader's guide", cat="rx", date="2026-05-01")
        self.second = dict(slug="second", title="新增文章", title_en='A & B "guide"', cat="myth", date="2026-05-02")

    def test_missing_card_is_static_and_existing_markup_is_preserved(self):
        card = render_card(self.first).replace('<div class="al-body">', '<div class="al-body"><span>Artwork</span>')
        source = '<header>Keep</header>\r\n<div id="list">\r\n' + card + '\r\n<!--keep-->\r\n</div><footer>Keep</footer>'
        result = sync_source(source, "list", [self.first, self.second])
        parsed = CardList(result, "list")
        self.assertEqual([c[0] for c in parsed.cards], ["first", "second"])
        self.assertIn(card, result)
        self.assertEqual(source.count("\r\n"), result.count("\r\n"))
        self.assertIn('<!--keep-->', result)
        self.assertEqual(result, sync_source(result, "list", [self.first, self.second]))

    def test_duplicates_and_drafts_are_removed_without_touching_other_links(self):
        first = render_card(self.first)
        draft = render_card(dict(self.second, slug="draft"))
        source = '<a href="/blog/draft">Outside</a><div id="list">' + first + first + draft + '</div>'
        result = sync_source(source, "list", [self.first])
        self.assertEqual([c[0] for c in CardList(result, "list").cards], ["first"])
        self.assertTrue(result.startswith('<a href="/blog/draft">Outside</a>'))

    def test_missing_or_duplicate_list_fails_closed(self):
        for source in ('<div></div>', '<div id="list">', '<div id="list"></div><div id="list"></div>'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                sync_source(source, "list", [self.first])

    def test_catalog_keeps_js_escaping_and_filters_late_noindex(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "blog").mkdir()
            (root / "blog/blog-shared.js").write_text(
                "DN.ARTICLES = [{slug:'first',title:'原有文章',title_en:'Reader\\'s guide'},"
                "{slug:'second',title:'新增文章',title_en:'New'},"
                "{slug:'draft',title:'草稿',title_en:'Draft',unpublished:true}];", encoding="utf-8")
            (root / "blog/first.html").write_text('<meta name="robots" content="index,follow">', encoding="utf-8")
            (root / "blog/second.html").write_text(' ' * 6000 + "<meta content='NOINDEX,follow' name='robots'>", encoding="utf-8")
            articles = load_catalog(root)
            self.assertEqual(articles[0]["title_en"], "Reader's guide")
            self.assertEqual([a["slug"] for a in public_catalog(articles, root)], ["first"])

    def test_text_is_escaped_and_decodes_without_losing_the_title(self):
        result = '<div id="list">' + render_card(self.second) + '</div>'
        self.assertIn('data-en="A &amp; B &quot;guide&quot;"', result)
        self.assertEqual(CardList(result, "list").cards[0][0], 'second')


if __name__ == "__main__":
    unittest.main()
