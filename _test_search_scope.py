"""Exercise the production Pagefind glob against public and private HTML fixtures."""
import importlib.util
from unittest.mock import patch
import contextlib
import io
import os
import gzip
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import _setup_pagefind as legacy_builder

class SearchScopeTest(unittest.TestCase):
    def test_locked_tool_rejects_dependency_drift_and_ignores_executable_overrides(self):
        import _run_pagefind as builder
        with tempfile.TemporaryDirectory(prefix='pagefind-lock-') as folder:
            root = Path(folder).resolve()
            native_name = '@pagefind/windows-x64'
            entry = {'version': '1.5.2', 'integrity': 'sha512-' + 'A' * 86 + '=='}
            lock = {'packages': {'': {'dependencies': {'pagefind': '1.5.2'}},
                                 'node_modules/pagefind': entry,
                                 'node_modules/' + native_name: entry}}
            def write(name, value):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding='utf8')
            write('package.json', {'dependencies': {'pagefind': '1.5.2'}})
            write('package-lock.json', lock)
            write('node_modules/pagefind/package.json', {'name': 'pagefind', 'version': '1.5.2'})
            native_meta = 'node_modules/' + native_name + '/package.json'
            write(native_meta, {'name': native_name, 'version': '1.5.2'})
            binary = root / 'node_modules' / native_name / 'bin/pagefind_extended.exe'
            binary.parent.mkdir()
            binary.write_bytes(b'Non-executed locked fixture')
            fixture_pin = {native_name: {'integrity': entry['integrity'],
                                        'size': binary.stat().st_size,
                                        'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}}
            with patch.object(builder, 'PAGEFIND_NATIVE', fixture_pin), patch.object(builder.sys, 'platform', 'win32'), patch.object(builder.platform, 'machine', return_value='AMD64'):
                with patch.dict(os.environ, {'PAGEFIND_EXTENDED_BINARY_PATH': '/untrusted', 'PAGEFIND_BINARY_PATH': '/untrusted'}):
                    self.assertEqual(builder.locked_binary(root), binary)
                original = binary.read_bytes()
                binary.write_bytes(b'X' + original[1:])
                with self.assertRaisesRegex(ValueError, 'pinned bytes'):
                    builder.locked_binary(root)
                binary.write_bytes(original)
                changed = json.loads(json.dumps(lock))
                changed['packages']['node_modules/' + native_name]['integrity'] = 'sha512-' + 'B' * 86 + '=='
                write('package-lock.json', changed)
                with self.assertRaisesRegex(ValueError, 'pinned tarball'):
                    builder.locked_binary(root)
                write('package-lock.json', lock)
                write(native_meta, {'name': native_name, 'version': '1.4.0'})
                with self.assertRaisesRegex(ValueError, 'locked identity'):
                    builder.locked_binary(root)
                write(native_meta, {'name': native_name, 'version': '1.5.2'})
                write('package.json', {'dependencies': {'pagefind': '^1.5.2'}})
                with self.assertRaisesRegex(ValueError, 'exact root dependency'):
                    builder.locked_binary(root)
                write('package.json', {'dependencies': {'pagefind': '1.5.2'}})
                changed = json.loads(json.dumps(lock))
                changed['packages']['node_modules/' + native_name].pop('integrity')
                write('package-lock.json', changed)
                with self.assertRaisesRegex(ValueError, 'locked identity'):
                    builder.locked_binary(root)

    @staticmethod
    def write_catalog(root):
        (root / 'blog').mkdir(exist_ok=True)
        (root / 'blog/blog-shared.js').write_text(
            'DN.ARTICLES = [{slug:"article",title:"Public",title_en:"Public"},'
            '{slug:"draft",title:"Draft",title_en:"Draft",unpublished:true}];', encoding='utf-8')

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
            self.write_catalog(root)
            for route in public + private:
                p = root / route
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('<html lang="en"><head><title>Fixture</title></head><body><main>'
                             '<h1>Search fixture</h1><p>Unique dermatology content.</p></main></body></html>', encoding='utf-8')
            binary = builder.locked_binary()
            subprocess.run([str(binary), '--site', str(root),
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

    def test_author_visibility_and_robots_apply_to_both_languages(self):
        import _run_pagefind as builder
        with tempfile.TemporaryDirectory(prefix='pagefind-visibility-') as folder:
            root = Path(folder)
            self.write_catalog(root)
            public = ['index.html', 'blog/article.html', 'blog/clinical-companion.html',
                      'en/index.html', 'en/blog/article.html']
            hidden = ['blog/draft.html', 'en/blog/draft.html', 'blog/noindex.html',
                      'en/blog/noindex.html', 'blog/googlebot.html', 'admin.html', 'notes.html']
            for route in public + hidden:
                target = root / route
                target.parent.mkdir(parents=True, exist_ok=True)
                meta = ''
                if 'noindex' in route or route in {'admin.html', 'notes.html'}:
                    meta = '<!--' + 'x' * 6500 + '--><meta CONTENT="follow,NOINDEX" NAME="robots">'
                if 'googlebot' in route:
                    meta = '<meta name="googlebot" content="none">'
                target.write_text('<html lang="en"><head><title>Fixture</title>' + meta +
                                  '</head><body><main><h1>Dermatology visibility fixture</h1></main></body></html>', encoding='utf-8')
            with patch.object(builder, 'ROOT', root), patch.object(builder, 'PAGEFIND_DIR', root / 'pagefind'):
                self.assertEqual(builder.main(), 0)
            urls = set()
            for path in (root / 'pagefind/fragment').glob('*.pf_fragment'):
                raw = gzip.decompress(path.read_bytes())
                urls.add(json.loads(raw[raw.index(b'{'):])['url'])
            self.assertEqual(urls, {'/', '/blog/article.html', '/blog/clinical-companion.html',
                                   '/en/', '/en/blog/article.html'})

    def test_invalid_author_catalog_does_not_clear_the_previous_index(self):
        import _run_pagefind as builder
        with tempfile.TemporaryDirectory(prefix='pagefind-invalid-catalog-') as folder:
            root = Path(folder)
            (root / 'blog').mkdir()
            (root / 'index.html').write_text('<html><main><h1>Public home</h1></main></html>', encoding='utf-8')
            output = root / 'pagefind'
            output.mkdir()
            sentinel = output / 'previous.txt'
            sentinel.write_text('previous index', encoding='utf-8')
            for content in [None, 'DN.ARTICLES = [];', 'DN.ARTICLES = invalid;']:
                with self.subTest(catalog=content):
                    catalog = root / 'blog/blog-shared.js'
                    if content is None:
                        catalog.unlink(missing_ok=True)
                    else:
                        catalog.write_text(content, encoding='utf-8')
                    with patch.object(builder, 'ROOT', root), patch.object(builder, 'PAGEFIND_DIR', output):
                        with self.assertRaises((ValueError, OSError, subprocess.CalledProcessError)):
                            builder.main()
                    self.assertEqual(sentinel.read_text(encoding='utf-8'), 'previous index')

    def test_script_shell_setting_cannot_expand_direct_native_visibility(self):
        import _run_pagefind as builder
        # The hosted Vercel shell expands a brace-list CLI argument; Ubuntu's
        # dash and Windows cmd do not. Exercise the direct locked native binary
        # path, rather than a mock that cannot reveal this transport bug.
        bash = shutil.which('bash')
        if not bash and os.name == 'nt':
            candidate = Path('C:/Program Files/Git/bin/bash.exe')
            if candidate.is_file():
                bash = str(candidate)
        self.assertIsNotNone(bash, 'Pagefind shell integration requires Bash')
        with tempfile.TemporaryDirectory(prefix='pagefind-bash-') as folder:
            root = Path(folder)
            self.write_catalog(root)
            for route in ['index.html','blog/article.html','blog/draft.html','admin.html']:
                path = root / route
                meta = '<meta name="robots" content="noindex">' if route == 'admin.html' else ''
                path.write_text('<html lang="en"><head><title>Fixture</title>'+meta+
                                '</head><body><main><h1>Public search fixture</h1></main></body></html>', encoding='utf-8')
            original_glob = os.environ.get('PAGEFIND_GLOB')
            with patch.dict(os.environ, {'npm_config_script_shell':bash,'PAGEFIND_GLOB':'**/*.html'}):
                with patch.object(builder, 'ROOT', root), patch.object(builder, 'PAGEFIND_DIR', root / 'pagefind'):
                    self.assertEqual(builder.main(), 0)
                self.assertEqual(os.environ['PAGEFIND_GLOB'], '**/*.html')
            self.assertEqual(os.environ.get('PAGEFIND_GLOB'), original_glob)
            urls = set()
            for fragment in (root / 'pagefind/fragment').glob('*.pf_fragment'):
                raw = gzip.decompress(fragment.read_bytes())
                urls.add(json.loads(raw[raw.index(b'{'):])['url'])
            self.assertEqual(urls, {'/', '/blog/article.html'})

    def test_lowercase_failed_cli_diagnostics_are_visible(self):
        import _run_pagefind as builder
        with tempfile.TemporaryDirectory(prefix='pagefind-diagnostics-') as folder:
            root = Path(folder)
            self.write_catalog(root)
            (root / 'index.html').write_text('<html><main><h1>Public fixture</h1></main></html>', encoding='utf-8')
            real_run = subprocess.run
            calls = []
            def fail_pagefind(command, *args, **kwargs):
                if command[0] == 'fake-pagefind':
                    calls.append((command, kwargs))
                    return subprocess.CompletedProcess(command, 2, '', 'error: unexpected argument\nUsage: pagefind [OPTIONS]')
                return real_run(command, *args, **kwargs)
            stdout = io.StringIO()
            with patch.object(builder, 'ROOT', root), patch.object(builder, 'PAGEFIND_DIR', root / 'pagefind'):
                with patch.object(builder, 'locked_binary', return_value=Path('fake-pagefind')):
                    with patch.object(builder.subprocess, 'run', side_effect=fail_pagefind), contextlib.redirect_stdout(stdout):
                        self.assertEqual(builder.main(), 1)
            self.assertEqual(len(calls), 1)
            command, kwargs = calls[0]
            self.assertNotIn('--glob', command)
            self.assertEqual(kwargs['env']['PAGEFIND_GLOB'], 'index.html')
            self.assertEqual(kwargs['timeout'], 180)
            self.assertIn('error: unexpected argument', stdout.getvalue())
            self.assertIn('Usage: pagefind [OPTIONS]', stdout.getvalue())

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
            self.write_catalog(root)
            (root / 'index.html').write_text('<html><main><h1>Public fixture</h1></main></html>', encoding='utf-8')
            with patch.object(builder, 'ROOT', root), patch.object(builder, 'PAGEFIND_DIR', root / 'pagefind'):
                with patch.object(builder, 'locked_binary', side_effect=FileNotFoundError('missing locked dependency')):
                    self.assertEqual(builder.main(), 1)
                with patch.object(builder, 'locked_binary', return_value=Path('fake-pagefind')):
                    real_run = subprocess.run
                    def failed_build(command, *args, **kwargs):
                        if command[0] == 'fake-pagefind':
                            return subprocess.CompletedProcess(command, 1, '', 'failure')
                        return real_run(command, *args, **kwargs)
                    def timed_out_build(command, *args, **kwargs):
                        if command[0] == 'fake-pagefind':
                            raise subprocess.TimeoutExpired(command, 180)
                        return real_run(command, *args, **kwargs)
                    with patch.object(builder.subprocess, 'run', side_effect=failed_build):
                        self.assertEqual(builder.main(), 1)
                    with patch.object(builder.subprocess, 'run', side_effect=timed_out_build):
                        self.assertEqual(builder.main(), 1)

if __name__ == '__main__':
    unittest.main()
