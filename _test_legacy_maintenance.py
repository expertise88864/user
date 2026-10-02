"""Regression tests for manual maintenance tools; no image decoder or real writes."""
from contextlib import redirect_stdout
import ast
import html
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MaintenanceImportTests(unittest.TestCase):
    def test_import_does_not_touch_navigation_stdout_or_load_codecs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            originals = {}
            for name in ('_clean_dead_slugs', '_convert_images', '_dump_aria', '_wrap_citations', '_html_scan'):
                (root / f'{name}.py').write_bytes((ROOT / f'{name}.py').read_bytes())
            for name in ('blog/index.html', 'blog/topics.html', 'en/blog/index.html', 'en/blog/topics.html'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                originals[name] = b'<li><a href="/blog/eczema-myths">Keep on import</a></li>'
                path.write_bytes(originals[name])
            # A fresh interpreter verifies imports even when codecs are unavailable.
            command = """
import importlib.abc, sys
class NoCodecs(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'PIL', 'pillow_avif'}:
            raise AssertionError('Codec imported during helper import')
sys.meta_path.insert(0, NoCodecs())
original = sys.stdout
import _clean_dead_slugs, _convert_images, _dump_aria, _wrap_citations
assert sys.stdout is original
print('import-safe')
"""
            run = subprocess.run([sys.executable, '-c', command], cwd=root,
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout.strip(), 'import-safe')
            self.assertEqual({n: (root / n).read_bytes() for n in originals}, originals)


class SVGLabelExtractionTests(unittest.TestCase):
    def setUp(self):
        self.script = load_script('_dump_aria')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.page = self.root / 'fixture.html'

    def labels(self, source):
        self.page.write_text(source, encoding='utf8')
        with patch.object(self.script, 'ROOT', self.root):
            return self.script.extract_zh_arias('fixture.html')

    def test_quoted_greater_than_single_quotes_and_entities_do_not_lose_labels(self):
        source = '<SVG data-note="1 > 0" aria-label=\'甲 &amp; 乙\'></SVG><svg aria-label="丙"></svg>'
        self.assertEqual(self.labels(source), ['甲 & 乙', '丙'])

    def test_non_svg_and_inert_examples_do_not_shift_translation_order(self):
        source = '<button aria-label="導航"></button><!-- <svg aria-label="註解"></svg> -->'
        for tag in ('script', 'style', 'template', 'noscript', 'textarea', 'title'):
            source += f'<{tag}><svg aria-label="範例"></svg></{tag}>'
        source += '<svg aria-label="實際圖"></svg><svg aria-label="English only"/>'
        self.assertEqual(self.labels(source), ['實際圖'])

    def test_translation_count_mismatch_fails_before_appending_output(self):
        self.labels('<svg aria-label="甲"></svg><svg aria-label="乙"></svg>')
        for translations in ([], ['One'], ['One', 'Two', 'Three']):
            with self.subTest(translations=translations), patch.object(self.script, 'ROOT', self.root):
                lines = ['Previous output']
                with self.assertRaisesRegex(ValueError, 'fixture.html'):
                    self.script.dump('fixture.html', translations, lines)
                self.assertEqual(lines, ['Previous output'])

    def test_matching_labels_preserve_exact_order_and_escape_quotes(self):
        self.labels('<svg aria-label="甲 &quot;引文&quot;"></svg><svg aria-label="乙"></svg>')
        lines = []
        with patch.object(self.script, 'ROOT', self.root):
            self.script.dump('fixture.html', ['First "quote"', 'Second'], lines)
        self.assertEqual(len(lines), 5)
        self.assertIn('甲 ' + chr(92) + '"引文' + chr(92) + '"', lines[1])
        self.assertIn('First ' + chr(92) + '"quote' + chr(92) + '"', lines[2])
        self.assertIn('Second', lines[4])


class CitationWrappingTests(unittest.TestCase):
    def setUp(self):
        self.script = load_script('_wrap_citations')

    def test_only_visible_text_changes_preserving_attributes_and_surrounding_bytes(self):
        source = '<p title="(Hill 2014)" data-zh="(Hill 2014)" data-en="(Hill 2014)">\n原文 (Hill 2014) 結尾 &amp;\n</p>'
        expected = source.replace('原文 (Hill 2014)', '原文 (<span class="cite">Hill 2014</span>)')
        result, count = self.script.wrap(source)
        self.assertEqual((result, count), (expected, 1))
        self.assertEqual(self.script.wrap(result), (result, 0))

    def test_inert_foreign_preformatted_and_existing_citations_are_preserved(self):
        for tag in ('script', 'style', 'template', 'noscript', 'textarea', 'title', 'pre', 'code', 'kbd', 'svg', 'math'):
            source = f'<{tag}>(Hill 2014)</{tag}>'
            with self.subTest(tag=tag):
                self.assertEqual(self.script.wrap(source), (source, 0))
        for source in ('<!-- (Hill 2014) -->', '<span class="cite other">(Hill 2014)</span>'):
            with self.subTest(source=source):
                self.assertEqual(self.script.wrap(source), (source, 0))

    def test_visible_citation_after_skipped_block_is_wrapped_and_rate_like_numbers_ignored(self):
        source = '<template><p>(Hill 2014)</p></template><p>(Hill 2014) (Fraxel 1550) (Hill 2044)</p>'
        expected = '<template><p>(Hill 2014)</p></template><p>(<span class="cite">Hill 2014</span>) (Fraxel 1550) (Hill 2044)</p>'
        self.assertEqual(self.script.wrap(source), (expected, 1))

    def test_raw_text_fake_tags_cannot_corrupt_following_real_text(self):
        for tag in ('textarea', 'title'):
            source = f'<div><{tag}><script></div>(Hill 2014)</{tag}><p>(Hill 2014)</p></div>'
            expected = source.replace('<p>(Hill 2014)</p>', '<p>(<span class="cite">Hill 2014</span>)</p>')
            with self.subTest(tag=tag):
                self.assertEqual(self.script.wrap(source), (expected, 1))

    def test_manual_main_targets_script_root_and_rerun_does_not_write_again(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / 'blog/fixture.html'
            page.parent.mkdir()
            page.write_text('<p>(Hill 2014)</p>', encoding='utf8')
            with patch.object(self.script, 'ROOT', root), redirect_stdout(io.StringIO()):
                self.script.main()
                once = page.read_bytes()
                self.script.main()
            self.assertEqual(page.read_bytes(), once)
            self.assertEqual(once, b'<p>(<span class="cite">Hill 2014</span>)</p>')


class SVGTranslationConsumerTests(unittest.TestCase):
    def test_extracted_entity_label_works_with_real_generator_lookup_and_legacy_keys(self):
        # Execute the actual pure consumer function without importing the whole
        # generator or its stdout configuration. Use nonmedical UI fixture text.
        tree = ast.parse((ROOT / '_gen_en_pages.py').read_text(encoding='utf8'))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == 'translate_aria_labels']
        self.assertEqual(len(functions), 1)
        import re
        context = {'re': re, 'html_lib': html, 'ARIA_LABEL_TRANSLATIONS': {}}
        exec(compile(ast.Module(body=functions, type_ignores=[]), '_gen_en_pages.py', 'exec'), context)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = '<svg aria-label="卡片 &amp; 排版" data-note="原屬性"></svg>'
            (root / 'fixture.html').write_text(source, encoding='utf8')
            helper = load_script('_dump_aria')
            with patch.object(helper, 'ROOT', root):
                labels = helper.extract_zh_arias('fixture.html')
            context['ARIA_LABEL_TRANSLATIONS'][labels[0]] = 'Card & layout'
            expected = source.replace('卡片 &amp; 排版', 'Card &amp; layout')
            self.assertEqual(context['translate_aria_labels'](source), expected)
            # Existing raw-entity dictionary keys remain preferred and supported.
            context['ARIA_LABEL_TRANSLATIONS']['卡片 &amp; 排版'] = 'Legacy card'
            self.assertEqual(context['translate_aria_labels'](source), source.replace('卡片 &amp; 排版', 'Legacy card'))


class DeletedNavigationTests(unittest.TestCase):
    def setUp(self):
        self.script = load_script('_clean_dead_slugs')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_existing_chinese_or_english_source_preserves_links(self):
        slugs = ('atopic-dermatitis-topical', 'atopic-dermatitis-systemic')
        for prefix, slug in zip(('blog', 'en/blog'), slugs):
            source = self.root / prefix / f'{slug}.html'
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text('Article exists', encoding='utf8')
        for prefix in ('/blog/', '/en/blog/'):
            for slug in slugs:
                for markup in (f'<a href="{prefix}{slug}" class="article-list-item"><h2>保留</h2></a>',
                               f'<li><a href="{prefix}{slug}">保留</a></li>'):
                    with self.subTest(prefix=prefix, slug=slug, markup=markup):
                        navigation = self.root / 'fixture.html'
                        navigation.write_text(markup, encoding='utf8')
                        self.assertFalse(self.script.clean(navigation, self.root))
                        self.assertEqual(navigation.read_text(encoding='utf8'), markup)

    def test_missing_candidate_removed_idempotently_and_other_links_preserved(self):
        original = ('<main><a href="/blog/eczema-myths" class="article-list-item">Deleted</a>'
                    '<li><a href="/en/blog/atopic-dermatitis-comorbidity">Deleted</a></li>'
                    '<a href="/blog/other" class="article-list-item">保留</a></main>')
        navigation = self.root / 'fixture.html'
        navigation.write_text(original, encoding='utf8')
        self.assertTrue(self.script.clean(navigation, self.root))
        expected = '<main><a href="/blog/other" class="article-list-item">保留</a></main>'
        self.assertEqual(navigation.read_text(encoding='utf8'), expected)
        self.assertFalse(self.script.clean(navigation, self.root))

    def test_main_targets_script_root_independent_of_working_directory(self):
        live = self.root / 'blog/atopic-dermatitis-topical.html'
        live.parent.mkdir(parents=True)
        live.write_text('Existing source', encoding='utf8')
        keep = '<li><a href="/blog/atopic-dermatitis-topical">Keep</a></li>'
        for name in ('blog/index.html', 'blog/topics.html', 'en/blog/index.html', 'en/blog/topics.html'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('<li><a href="/blog/eczema-myths">Deleted</a></li>' + keep, encoding='utf8')
        with patch.object(self.script, 'ROOT', self.root), redirect_stdout(io.StringIO()):
            # main() uses ROOT for both paths and existence checks.
            self.script.main()
        self.assertTrue(all((self.root / name).read_text(encoding='utf8') == keep
                            for name in ('blog/index.html', 'blog/topics.html', 'en/blog/index.html', 'en/blog/topics.html')))


class PictureRewriteTests(unittest.TestCase):
    def setUp(self):
        self.script = load_script('_convert_images')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'assets/photo.jpg'
        self.source.parent.mkdir()
        self.source.write_bytes(b'file-existence fixture; not an image')
        self.source.with_suffix('.webp').write_bytes(b'file-existence fixture')
        self.page = self.root / 'blog/article.html'
        self.page.parent.mkdir()

    def rewrite(self, value, images=None):
        with patch.object(self.script, 'ROOT', str(self.root)):
            return self.script.rewrite_html_imgs(value, {self.source} if images is None else images, self.page)

    def test_original_tag_and_surrounding_text_preserved_on_first_and_second_pass(self):
        image = '<IMG alt="臨床圖 > 說明" src=\'/assets/photo.jpg\' width="20" loading="lazy" />'
        original = f'<main>原文\n{image}\n<img src="/assets/photo.jpg" alt="二">結尾</main>'
        once = self.rewrite(original)
        self.assertEqual(once.count('<picture>'), 2)
        self.assertEqual(once.count(image), 1)
        self.assertEqual(once.replace('<picture><source srcset="/assets/photo.webp" type="image/webp">', '').replace('</picture>', ''), original)
        self.assertEqual(self.rewrite(once), once)

    def test_existing_picture_and_inert_or_foreign_markup_unchanged(self):
        image = '<img src="/assets/photo.jpg">'
        fixtures = [f'<{tag}>{image}</{tag}>' for tag in
                    ('picture', 'script', 'style', 'template', 'noscript', 'textarea', 'title', 'svg', 'math')]
        fixtures += [f'<!-- {image} -->', f'<picture><source srcset="custom.webp">{image}</picture>']
        for original in fixtures:
            with self.subTest(original=original):
                self.assertEqual(self.rewrite(original), original)
                # A separate eligible image following the excluded block still wraps.
                after = self.rewrite(original + image)
                self.assertTrue(after.startswith(original))
                self.assertEqual(after[len(original):].count('<picture>'), 1)

    def test_opt_out_and_responsive_choices_preserved(self):
        for attrs in ('data-no-picture', 'data-no-picture="false"', 'srcset="custom.webp 2x"', 'sizes="100vw"', 'src="/assets/other.jpg"'):
            original = f'<img src="/assets/photo.jpg" {attrs}>'
            with self.subTest(attrs=attrs):
                self.assertEqual(self.rewrite(original), original)

    def test_only_local_listed_images_with_existing_siblings_wrap(self):
        for src in ('https://example.com/assets/photo.jpg', '//example.com/assets/photo.jpg',
                    '../../photo.jpg', '/assets/photo.svg', '/assets/missing.jpg', '/assets\\photo.jpg',
                    '/assets/ph%00oto.jpg', '/assets/%5cphoto.jpg', '/assets/photo%2Ejpg'):
            original = f'<img src="{src}">'
            with self.subTest(src=src):
                self.assertEqual(self.rewrite(original), original)
        original = '<img src="/assets/photo.jpg">'
        self.assertEqual(self.rewrite(original, set()), original)
        self.source.with_suffix('.webp').unlink()
        self.assertEqual(self.rewrite(original), original)

    def test_relative_path_avif_precedence_and_escaped_query_preserved(self):
        self.source.with_suffix('.avif').write_bytes(b'file-existence fixture')
        original = '<img src="../assets/photo.jpg?v=1&amp;x=2#figure" alt="Original">'
        result = self.rewrite(original)
        self.assertEqual(result, '<picture><source srcset="../assets/photo.avif?v=1&amp;x=2#figure" type="image/avif"><source srcset="../assets/photo.webp?v=1&amp;x=2#figure" type="image/webp">' + original + '</picture>')

    def test_image_discovery_excludes_private_and_generated_directories(self):
        for name in ('.codex-review', 'node_modules', '.git', 'en', 'pagefind'):
            directory = self.root / name / 'nested'
            directory.mkdir(parents=True)
            (directory / 'private.jpg').write_bytes(b'not an image')
        self.assertEqual(self.script.find_images(self.root), [str(self.source)])


if __name__ == '__main__':
    unittest.main()
