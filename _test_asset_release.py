"""Returning-reader release regressions: stale immutable code must fail gates."""
import copy
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from _gen_asset_release import text_hash, validate_transition
from _normalize_css_links import ASSET_VERSION, normalize_file, normalize_text_color_utilities
from _normalize_analytics import KEEPER, normalize
import _check_third_party as third_party


class AssetReleaseTests(unittest.TestCase):
    def test_color_variables_generate_color_without_overwriting_font_sizes(self):
        source = ('.text-\\[var\\(--muted\\)\\]{font-size:var(--muted)}\n'
                  '.text-\\[var\\(--teal-deep\\)\\]{font-size:var(--teal-deep)}\n'
                  '.text-\\[var\\(--ink-2\\)\\]{font-size:var(--ink-2)}\n'
                  '.text-\\[14px\\]{font-size:14px}\n'
                  '.text-\\[var\\(--reading-size\\)\\]{font-size:var(--reading-size)}')
        result = normalize_text_color_utilities(source)
        for variable in ('muted', 'teal-deep', 'ink-2'):
            self.assertIn('color:var(--' + variable + ')', result)
            self.assertNotIn('font-size:var(--' + variable + ')', result)
        self.assertIn('.text-\\[14px\\]{font-size:14px}', result)
        self.assertIn('font-size:var(--reading-size)', result)
        self.assertEqual(normalize_text_color_utilities(result), result)

    def setUp(self):
        self.old = {'version': '202609121640', 'caches': {'CACHE': 'old', 'RUNTIME': 'old-runtime'},
                    'assets': {'blog/blog-shared.min.js': 'old-code'}, 'worker_sha256': 'old-worker'}

    def test_same_release_is_valid(self):
        validate_transition(self.old, copy.deepcopy(self.old))

    def test_changed_cached_code_cannot_reuse_version(self):
        for key in ('assets', 'worker_sha256'):
            new = copy.deepcopy(self.old)
            new[key] = {'blog/blog-shared.min.js': 'new-code'} if key == 'assets' else 'new-worker'
            with self.assertRaisesRegex(ValueError, 'ASSET_VERSION'):
                validate_transition(self.old, new)

    def test_both_sw_cache_generations_must_advance(self):
        for unchanged in ('CACHE', 'RUNTIME'):
            new = copy.deepcopy(self.old)
            new.update(version='202609300830', assets={'blog/blog-shared.min.js': 'new-code'})
            new['caches'] = {'CACHE': 'new', 'RUNTIME': 'new-runtime'}
            new['caches'][unchanged] = self.old['caches'][unchanged]
            with self.assertRaisesRegex(ValueError, unchanged):
                validate_transition(self.old, new)

    def test_complete_new_release_is_valid(self):
        new = copy.deepcopy(self.old)
        new.update(version='202609300830', assets={'blog/blog-shared.min.js': 'new-code'},
                   caches={'CACHE': 'new', 'RUNTIME': 'new-runtime'})
        validate_transition(self.old, new)

    def test_changed_code_cannot_roll_back_to_a_previously_cached_url(self):
        new = copy.deepcopy(self.old)
        new.update(version='202509300830', assets={'blog/blog-shared.min.js': 'new-code'},
                   caches={'CACHE': 'new', 'RUNTIME': 'new-runtime'})
        with self.assertRaisesRegex(ValueError, 'ASSET_VERSION'):
            validate_transition(self.old, new)

    def test_inline_loader_urls_are_versioned_without_duplicates_or_attribute_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / 'index.html'
            page.write_text('<html><head><script src="/assets/inline/analytics-loader.js" defer></script>'
                            '<script src="/assets/inline/nav-burger.js?v=202609121640" defer></script>'
                            '</head><body></body></html>', encoding='utf-8')
            self.assertTrue(normalize_file(str(page)))
            generated = page.read_text(encoding='utf-8')
            self.assertIn(f'analytics-loader.js?v={ASSET_VERSION}', generated)
            self.assertIn(f'nav-burger.js?v={ASSET_VERSION}', generated)
            self.assertEqual(generated.count('analytics-loader.js'), 1)
            self.assertFalse(normalize_file(str(page)))

    def test_shared_stylesheet_cannot_reuse_old_immutable_url(self):
        for href in ('/assets/tw-mini.css?v=23', '/assets/tw-mini.css'):
            with self.subTest(href=href), tempfile.TemporaryDirectory() as directory:
                page = Path(directory) / 'index.html'
                page.write_text('<html><head><link id="shared-style" rel="stylesheet" media="screen" href="'
                                + href + '"></head><body></body></html>', encoding='utf-8')
                self.assertTrue(normalize_file(str(page)))
                result = page.read_text(encoding='utf-8')
                self.assertIn(f'/assets/tw-mini.css?v={ASSET_VERSION}', result)
                self.assertIn('id="shared-style"', result)
                self.assertIn('media="screen"', result)
                self.assertEqual(result.count('/assets/tw-mini.css'), 1)
                self.assertFalse(normalize_file(str(page)))

    def test_windows_checkout_and_ubuntu_have_identical_release_digests(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.js'
            path.write_bytes('const title="異位性皮膚炎";\nrun();\n'.encode('utf-8'))
            linux = text_hash(path)
            path.write_bytes('const title="異位性皮膚炎";\r\nrun();\r\n'.encode('utf-8'))
            self.assertEqual(text_hash(path), linux)

    def test_legacy_analytics_tags_migrate_to_keeper_without_double_injection(self):
        for original in ('<script src="/assets/inline/analytics-loader.js" defer></script>',
                         '<script defer src="/assets/inline/analytics-loader.js?v=202609121640"></script>'):
            source = '<head>' + original + '</head>'
            result, _, _ = normalize(source)
            self.assertEqual(result.count(KEEPER), 1)
            self.assertEqual(result.count('analytics-loader.js'), 1)
            self.assertEqual(normalize(result)[0], result)

    def test_loading_audit_rejects_missing_or_stale_loader_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            loader = root / 'assets/inline/analytics-loader.js'
            loader.parent.mkdir(parents=True)
            loader.write_text((Path(__file__).parent / 'assets/inline/analytics-loader.js').read_text(encoding='utf-8'), encoding='utf-8')
            pages = [root / f'page-{i}.html' for i in range(100)]
            for query, expected in [(f'?v={ASSET_VERSION}', 0), ('', 1), ('?v=202609121640', 1)]:
                for page in pages:
                    page.write_text(f'<html><head><script src="/assets/inline/analytics-loader.js{query}" defer></script></head></html>', encoding='utf-8')
                with patch.object(third_party, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(third_party.main(), expected, query)


if __name__ == '__main__':
    unittest.main()
