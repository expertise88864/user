"""Patient next-question selection and raw-HTML catalog integrity."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import _inject_related as related


def browser_fixture():
    from _gen_en_pages import DataEnRenderer, localize_jsonld
    payload = '<img src="x" onerror="window.__relatedInjected=1"> & "quoted"'
    article = dict(slug='fixture', title='Fixture title', title_en=payload,
                   tag='Fixture topic', tag_en=payload, date='2026-01-01')
    block = related.build_related_html('current', [article])
    script_payload = '</script><img src="x" onerror="window.__jsonldInjected=1">'
    script_block = related.build_related_html('current', [{**article, 'title': script_payload}])
    return {'payload': payload, 'blocks': [block, DataEnRenderer().render(block)],
            'scriptPayload': script_payload,
            'jsonldBlocks': [script_block, localize_jsonld(DataEnRenderer().render(script_block), 'Fixture', 'Fixture')]}


class RelatedArticlesTests(unittest.TestCase):
    def test_real_catalog_does_not_truncate_english_apostrophes(self):
        article = next(a for a in related.parse_articles() if a['slug'] == 'tinea-myths')
        self.assertEqual(article['title_en'], "7 Athlete's Foot / Nail Fungus Myths")

    def test_pilot_questions_use_the_explicit_sequence_without_category_padding(self):
        catalog = related.parse_articles()
        overrides = related.load_overrides(catalog)
        public = related.public_catalog(catalog, related.ROOT)
        groups = related.build_tag_groups(catalog)
        for source, sequence in overrides.items():
            current = next(a for a in catalog if a['slug'] == source)
            with self.subTest(source=source):
                self.assertEqual([a['slug'] for a in related.select_related(current, public, groups, overrides)], sequence)
        self.assertEqual(overrides['tinea-myths'], ['toenail-mechanical-disorders'])

    def test_hidden_curated_targets_are_removed_without_unrelated_fillers(self):
        current = dict(slug='current', title='Current', tag='same', tag_en='same', cat='rx', date='2026-01-01', unpublished=False)
        other = dict(current, slug='other')
        selected = related.select_related(current, [current, other], {}, {'current':['hidden']})
        self.assertEqual(selected, [])
        self.assertIn('id="dn-related-static"', related.build_related_html('current', selected))
        self.assertNotIn('application/ld+json', related.build_related_html('current', selected))

    def test_override_typo_self_link_duplicate_or_oversized_list_fails(self):
        catalog = [dict(slug='first'), dict(slug='second')]
        for value in ({'unknown':['second']}, {'first':['unknown']}, {'first':['first']},
                      {'first':['second','second']}, {'first':[]}, {'first':'second'},
                      {'first':['second']*5}):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root/'_related_article_overrides.json').write_text(json.dumps(value), encoding='utf-8')
                with self.assertRaises(ValueError):
                    related.load_overrides(catalog, root)

    def test_actual_noindex_policy_filters_curated_and_scored_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'blog').mkdir()
            catalog = []
            for slug, robots in [('current','index,follow'), ('hidden','NOINDEX,follow'), ('visible','index,follow')]:
                (root/'blog'/(slug+'.html')).write_text('<meta name="robots" content="'+robots+'">',encoding='utf-8')
                catalog.append(dict(slug=slug,title=slug,tag='topic',tag_en='topic',cat='rx',date='2026-01-01',unpublished=False))
            public = related.public_catalog(catalog, root)
            current = catalog[0]
            for overrides in ({}, {'current':['hidden','visible']}):
                self.assertEqual([a['slug'] for a in related.select_related(current, public, {}, overrides)], ['visible'])

    def test_empty_selection_replaces_stale_generated_cards_and_preserves_prose(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'blog').mkdir()
            original = '<main><article><h2 id="keep">Author text</h2><p>Keep &amp; bytes.</p></article>\n<nav id="dn-related-static"><a href="/blog/hidden">Stale</a></nav>\n</main>'
            file = root/'blog/current.html'; file.write_text(original, encoding='utf-8')
            catalog=[dict(slug='current', title='Current', title_en='Current', cat='rx', tag='topic', tag_en='topic', date='2026-01-01', unpublished=False)]
            with patch.object(related, 'ROOT', root):
                related.inject(catalog, {}, public=catalog, overrides={'current':['hidden']})
                once = file.read_text(encoding='utf-8')
                related.inject(catalog, {}, public=catalog, overrides={'current':['hidden']})
            self.assertNotIn('/blog/hidden', once)
            self.assertIn('<article><h2 id="keep">Author text</h2><p>Keep &amp; bytes.</p></article>', once)
            self.assertEqual(once, file.read_text(encoding='utf-8'))

    def test_existing_bilingual_tags_are_rendered_in_the_selected_language(self):
        article = dict(slug='next', title='原有標題', title_en="Reader's guide", tag='原有標籤', tag_en='Existing topic', date='2026-01-01')
        block = related.build_related_html('current', [article])
        self.assertIn('data-zh="原有標籤" data-en="Existing topic" data-dn-text-only>原有標籤</span>', block)
        from _gen_en_pages import DataEnRenderer
        mirror = DataEnRenderer().render(block)
        self.assertIn('>Existing topic</span>', mirror)
        self.assertIn("Reader&#x27;s guide", block)
        self.assertNotIn('>原有標籤</span>', mirror)

    def test_related_metadata_remains_plain_in_both_generated_languages(self):
        from html.parser import HTMLParser
        class Fields(HTMLParser):
            def __init__(self, source):
                super().__init__(); self.fields = []; self.images = 0; self.feed(source)
            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if values.get('data-zh') in ('Fixture title', 'Fixture topic'):
                    self.fields.append(values)
                if tag == 'img': self.images += 1
        fixture = browser_fixture()
        for block in fixture['blocks']:
            parsed = Fields(block)
            self.assertEqual(len(parsed.fields), 3)
            self.assertEqual(parsed.images, 0)
            for values in parsed.fields:
                self.assertIn('data-dn-text-only', values)
                self.assertEqual(values['data-en'], fixture['payload'])

    def test_related_jsonld_cannot_break_out_of_script_in_either_language(self):
        import re
        fixture = browser_fixture()
        for block in fixture['jsonldBlocks']:
            scripts = re.findall(r'<script type="application/ld\+json">(.*?)</script>', block, re.S)
            self.assertEqual(len(scripts), 1)
            self.assertEqual(json.loads(scripts[0])['itemListElement'][0]['name'], fixture['scriptPayload'])
            self.assertNotIn('<img', block)

    def test_schema_normalization_keeps_related_script_safe_and_idempotent(self):
        import _normalize_schema as schema
        fixture = browser_fixture()
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / 'fixture.html'
            for block in fixture['jsonldBlocks']:
                page.write_text('<html><head></head><body>'+block+'</body></html>', encoding='utf8')
                schema.normalize_file(page)
                normalized = page.read_text(encoding='utf8')
                self.assertNotIn('<img', normalized)
                self.assertEqual(normalized.count('</script>'), 1)
                self.assertEqual(list(schema.iter_jsonld(normalized))[0]['itemListElement'][0]['name'], fixture['scriptPayload'])
                schema.normalize_file(page)
                self.assertEqual(page.read_text(encoding='utf8'), normalized)


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--browser-fixture']:
        sys.stdout.reconfigure(encoding='utf-8')
        print(json.dumps(browser_fixture(), ensure_ascii=False))
    else:
        unittest.main()
