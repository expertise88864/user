"""Exercise the production Pagefind glob against public and private HTML fixtures."""
import importlib.util
from unittest.mock import patch
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import _setup_pagefind as legacy_builder

class SearchScopeTest(unittest.TestCase):
    def test_legacy_arguments_and_exit_status(self):
        for args in ([], ['--reindex']):
            with self.subTest(args=args):
                with patch.object(legacy_builder, 'build_index', return_value=7) as build:
                    self.assertEqual(legacy_builder.main(args), 7)
                    build.assert_called_once_with()
        for args in (['--version', '1.1.1'], ['--unknown']):
            with self.subTest(args=args):
                with patch.object(legacy_builder, 'build_index') as build:
                    with self.assertRaises(SystemExit) as error:
                        legacy_builder.main(args)
                    self.assertEqual(error.exception.code, 2)
                    build.assert_not_called()

    def test_only_public_route_roots_are_indexed(self):
        spec = importlib.util.spec_from_file_location('search_builder', '_run_pagefind.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        public = ['index.html', 'about.html', 'blog/article.html', 'en/index.html', 'en/blog/article.html']
        private = ['.git/retired-workspaces/blog/private.html', '.codex-review/evidence.html',
                   'node_modules/example/index.html', 'backup/blog/article.html']
        with tempfile.TemporaryDirectory(prefix='pagefind-scope-') as folder:
            root = Path(folder)
            for route in public + private:
                p = root / route
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('<html lang="en"><head><title>Fixture</title></head><body><main>'
                             '<h1>Search fixture</h1><p>Unique dermatology content.</p></main></body></html>', encoding='utf-8')
            npx = shutil.which('npx') or shutil.which('npx.cmd')
            self.assertIsNotNone(npx, 'Pagefind integration requires Node.js/npm')
            subprocess.run([npx, '--yes', 'pagefind@1.5.2', '--site', str(root),
                            '--output-path', str(root / 'pagefind'), '--root-selector', 'main',
                            '--glob', '**/*.html'], check=True, capture_output=True, timeout=180)
            before = list((root / 'pagefind/fragment').glob('*.pf_fragment'))
            self.assertGreater(len(before), len(public))
            with patch.object(builder, 'ROOT', root), patch.object(builder, 'PAGEFIND_DIR', root / 'pagefind'):
                # The legacy command must also clean contaminated old fragments.
                with patch.object(legacy_builder, 'build_index', builder.main):
                    self.assertEqual(legacy_builder.main(['--reindex']), 0)
            urls = set()
            for fragment in (root / 'pagefind/fragment').glob('*.pf_fragment'):
                data = gzip.decompress(fragment.read_bytes())
                urls.add(json.loads(data[data.index(b'{'):])['url'])
            self.assertEqual(urls, {'/', '/about.html', '/blog/article.html', '/en/', '/en/blog/article.html'})

    def test_output_boundary_preserves_unrelated_directory(self):
        spec = importlib.util.spec_from_file_location('search_builder', '_run_pagefind.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory(prefix='pagefind-boundary-') as folder:
            root = Path(folder)
            other = root / 'unrelated'
            other.mkdir()
            marker = other / 'keep.txt'
            marker.write_text('keep', encoding='utf-8')
            with patch.object(builder, 'ROOT', root), patch.object(builder, 'PAGEFIND_DIR', other):
                with self.assertRaises(ValueError):
                    builder.main()
            self.assertEqual(marker.read_text(encoding='utf-8'), 'keep')

    def test_missing_runner_or_failed_build_is_not_success(self):
        spec = importlib.util.spec_from_file_location('search_builder', '_run_pagefind.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory(prefix='pagefind-failure-') as folder:
            root = Path(folder)
            with patch.object(builder, 'ROOT', root), patch.object(builder, 'PAGEFIND_DIR', root / 'pagefind'):
                with patch.object(builder.shutil, 'which', return_value=None):
                    self.assertEqual(builder.main(), 1)
                with patch.object(builder.shutil, 'which', return_value='fake-npx'):
                    with patch.object(builder.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'failure')):
                        self.assertEqual(builder.main(), 1)
                    with patch.object(builder.subprocess, 'run', side_effect=subprocess.TimeoutExpired([], 180)):
                        self.assertEqual(builder.main(), 1)

if __name__ == '__main__':
    unittest.main()
