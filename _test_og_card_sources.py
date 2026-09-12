"""Regression checks for share-card source drift, without fonts or rendering."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _gen_og_cards as cards


class CardSourcesTest(unittest.TestCase):
    def test_source_and_both_image_formats_must_match(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            page = root / 'sample.html'
            source = {'title': 'Original title', 'subtitle': '', 'date': '2026-05-15'}
            files = {}
            for ext in ('png', 'webp'):
                data = ('fixture-' + ext).encode()
                (root / ('sample.' + ext)).write_bytes(data)
                files[ext] = hashlib.sha256(data).hexdigest()
            record = {'source': dict(source), 'rendered_tag': 'Preserved label', 'files': files}
            with patch.object(cards, 'OG_DIR', root), patch.object(cards, 'card_targets', return_value=[page]), \
                    patch.object(cards, 'REQUIRED_CARD_SOURCES', frozenset({'sample'})), \
                    patch.object(cards, 'card_slug', return_value='sample'), \
                    patch.object(cards, 'article_fields', return_value=source):
                self.assertEqual(cards.check_card_sources({'sample': record}), [])
                self.assertTrue(cards.check_card_sources({}))
                for key in ('title', 'subtitle', 'date'):
                    original = source[key]
                    source[key] = 'Changed'
                    self.assertTrue(cards.check_card_sources({'sample': record}), key)
                    source[key] = original
                for ext in ('png', 'webp'):
                    path = root / ('sample.' + ext)
                    original = path.read_bytes()
                    path.write_bytes(b'changed')
                    self.assertTrue(cards.check_card_sources({'sample': record}), ext)
                    path.unlink()
                    self.assertTrue(cards.check_card_sources({'sample': record}), ext)
                    path.write_bytes(original)
                self.assertTrue(cards.check_card_sources({'sample': {'source': None}}))
                self.assertTrue(cards.check_card_sources({'unknown': record}))

    def test_all_adopted_cards_require_evidence(self):
        self.assertEqual(cards.REQUIRED_CARD_SOURCES, {
            'dupilumab-long-term-maintenance', 'topical-acids-patient', 'prurigo-nodularis',
        })
        records = cards.read_card_sources()
        self.assertEqual(cards.check_card_sources(records), [])
        for slug in cards.REQUIRED_CARD_SOURCES:
            incomplete = {key: value for key, value in records.items() if key != slug}
            self.assertIn(f'{slug}: required render source evidence missing',
                          cards.check_card_sources(incomplete))
            for tag in (None, '', 'Wrong label', 123):
                with self.subTest(slug=slug, tag=tag):
                    altered = {**records, slug: {**records[slug], 'rendered_tag': tag}}
                    self.assertTrue(cards.check_card_sources(altered))
            without_tag = dict(records[slug])
            del without_tag['rendered_tag']
            self.assertTrue(cards.check_card_sources({**records, slug: without_tag}))


if __name__ == '__main__':
    unittest.main()
