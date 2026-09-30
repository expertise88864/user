"""Regression tests for raw-HTML article discovery and draft boundaries."""
import tempfile
from pathlib import Path
import unittest

from _sync_hub_catalog import CardList, load_catalog, load_overrides, public_catalog, render_card, sync_source


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

    def test_homepage_emits_newest_first_without_changing_card_markup(self):
        third = dict(self.second, slug='third')
        cards = [render_card(item) for item in (self.first, self.second, third)]
        source = '<div id="dn-article-list">' + '\r\n'.join(cards) + '</div>'
        articles = [self.first, self.second, third]
        result = sync_source(source, 'dn-article-list', articles)
        self.assertEqual([c[0] for c in CardList(result, 'dn-article-list').cards],
                         ['third', 'second', 'first'])
        for card in cards:
            self.assertIn(card, result)
        self.assertEqual(result.count('\r\n'), source.count('\r\n'))
        self.assertEqual(sync_source(result, 'dn-article-list', articles), result)

    def test_homepage_sorts_visible_dates_before_catalog_or_datetime(self):
        first = render_card(self.first).replace(">2026-05-01</time>", "> <span>2026-05-03</span> </time>")
        second = render_card(self.second)
        source = '<div id="dn-article-list">' + second + first + '</div>'
        result = sync_source(source, 'dn-article-list', [self.first, self.second])
        self.assertEqual([card[0] for card in CardList(result, 'dn-article-list').cards],
                         ['first', 'second'])
        self.assertIn(first, result)
        self.assertIn(second, result)
        self.assertEqual(result, sync_source(result, 'dn-article-list', [self.first, self.second]))

    def test_homepage_uses_catalog_when_visible_date_is_missing(self):
        first = render_card(self.first)
        second = render_card(self.second).replace(
            '<time datetime="2026-05-02">2026-05-02</time>', '')
        source = '<div id="dn-article-list">' + first + second + '</div>'
        result = sync_source(source, 'dn-article-list', [self.first, self.second])
        self.assertEqual([card[0] for card in CardList(result, 'dn-article-list').cards],
                         ['second', 'first'])
        self.assertIn(second, result)

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

    def test_metadata_drift_repairs_category_language_and_topic_preserving_artwork(self):
        item = {**self.first, 'tag': '處置 / 手術', 'tag_en': 'Biopsy'}
        card = render_card(item).replace('data-cat="rx"', 'data-cat="myth"')
        card = card.replace('<h2', '<svg id="artwork"><path d="M0 1"/></svg><span class="chip tag" data-en="Psoriasis">乾癬</span><h2')
        card = card.replace('>原有文章</h2>', '>English residue</h2>')
        source = '<div id="list">' + card + '</div>'
        result = sync_source(source, 'list', [item])
        self.assertIn('data-cat="rx"', result)
        self.assertIn('data-tag-en="Biopsy"', result)
        self.assertIn('>原有文章</h2>', result)
        self.assertIn('data-en="Biopsy">處置 / 手術</span>', result)
        self.assertIn('<svg id="artwork"><path d="M0 1"/></svg>', result)
        self.assertNotIn('乾癬', result)
        self.assertEqual(sync_source(result, 'list', [item]), result)

    def test_editorial_overrides_apply_to_existing_and_new_cards_idempotently(self):
        overrides = {'first': {'title': '醫師選擇的標題', 'title_en': 'Editorial title'},
                     'second': {'title': '另一個入口', 'title_en': 'Another entry'}}
        source = '<div id="list">' + render_card(self.first) + '</div>'
        result = sync_source(source, 'list', [self.first, self.second], overrides)
        self.assertIn('>醫師選擇的標題</h2>', result)
        self.assertIn('>另一個入口</h2>', result)
        self.assertEqual(sync_source(result, 'list', [self.first, self.second], overrides), result)

    def test_override_contract_rejects_unknown_slugs_and_category_changes(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / '_hub_card_overrides.json'
            for invalid in [{'index.html': {'missing': {'title': '錯誤'}}},
                            {'index.html': {'first': {'cat': 'myth'}}},
                            {'index.html': {'first': {'title': ''}}}]:
                path.write_text(json.dumps(invalid), encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_overrides([self.first], root)

    def test_public_dermatitis_cards_never_inherit_psoriasis_topic_labels(self):
        catalog = load_catalog()
        overrides = load_overrides(catalog)
        for hub, cards in overrides.items():
            for item in catalog:
                if item['slug'].startswith('atopic-dermatitis-'):
                    effective = {**item, **cards.get(item['slug'], {})}
                    self.assertEqual(effective['tag'], '異位性皮膚炎', (hub, item['slug']))
                    self.assertNotIn('psoriasis', effective['tag_en'].lower(), (hub, item['slug']))


if __name__ == "__main__":
    unittest.main()
