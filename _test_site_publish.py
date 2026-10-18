"""Regression tests: Vercel serves only the staged public site."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import _check_deploy_exposure as exposure
import _site_publish as publish


def write(root: Path, relative: str, text: str = 'x') -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


class SelectionTests(unittest.TestCase):
    def test_repository_files_are_never_published(self):
        for name in ('_delivery.py', 'AGENTS.md', 'vercel.json', 'middleware.js', 'package.json',
                     '_vercel_gate.cjs', '_serve.mjs', '.gitignore', '.cms-delivery.json', 'deploy.ps1',
                     'deploy.bat', '_scratch.txt', '_site_settings.json', 'tools/pr_review.py',
                     'tools/codex_review.sh', '.github/workflows/delivery.yml', '.githooks/pre-push',
                     'data/exam/questions.json', '_pdf_extracts/AK JAAD.txt', 'api/og.js',
                     '__pycache__/_delivery.cpython-312.pyc', 'blog/__pycache__/x.cpython-312.pyc',
                     'assets/notes.md', 'blog/build.py', 'assets/.DS_Store', 'node_modules/a/index.js',
                     'blog/.well-known/x', 'dist/index.html', '../index.html', '/index.html', ''):
            self.assertFalse(publish.is_published(name), name)

    def test_site_files_stay_published(self):
        for name in ('index.html', '404.html', 'robots.txt', 'sitemap.xml', 'manifest.json', 'sw.js',
                     'favicon.ico', 'icon.svg', 'icon-192.png', 'llms.txt', 'opensearch.xml',
                     '.well-known/security.txt', 'blog/feed.xml', 'assets/fonts/a.woff2',
                     'pagefind/fragment/zh_1.pf_fragment', 'admin/word-editor.js', 'en/blog/a.html'):
            self.assertTrue(publish.is_published(name), name)

    def test_stage_copies_only_the_site_and_replaces_stale_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'repo'
            for name in ('index.html', 'sw.js', 'robots.txt', 'blog/a.html', 'pagefind/pagefind.js',
                         '_delivery.py', 'AGENTS.md', 'vercel.json', 'tools/x.sh', 'data/q.json',
                         '__pycache__/a.pyc', 'blog/__pycache__/b.pyc', 'blog/notes.md'):
                write(root, name)
            write(root, 'dist/stale.py')
            write(root, 'abcdef12.txt', 'abcdef12\n')  # IndexNow key file
            write(root, 'notes1234.txt', 'internal scratch')
            write(root, 'newpage.html')
            write(root, 'blog/_draft.html')
            files = publish.stage(root, root / 'dist')
            expected = ['abcdef12.txt', 'blog/a.html', 'index.html', 'pagefind/pagefind.js', 'robots.txt', 'sw.js']
            self.assertEqual(files, expected)
            copied = sorted(p.relative_to(root / 'dist').as_posix() for p in (root / 'dist').rglob('*') if p.is_file())
            self.assertEqual(copied, expected)
            # The staged output is never re-staged into itself.
            self.assertEqual(publish.published_files(root), expected)
            # The build-log census covers exactly the staged non-generated files.
            import hashlib
            tracked = '\n'.join(name for name in expected if not name.startswith('pagefind/'))
            self.assertEqual(publish.census(root / 'dist'),
                             '[site-census] files=5 sha256=' + hashlib.sha256(tracked.encode()).hexdigest() +
                             ' generated=1 search=1')
            write(root, 'dist/_delivery.py')
            self.assertIn('[site-census] files=6 ', publish.census(root / 'dist'))
            (root / 'dist/pagefind/pagefind.js').unlink()
            self.assertTrue(publish.census(root / 'dist').endswith(' generated=0 search=0'))

    def test_probe_manifest_covers_the_checkout_without_git(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('index.html', 'blog/a.html', '_delivery.py', 'tools/x.sh', '.github/w.yml',
                         '.git/HEAD', 'dist/index.html', 'delivery-preview/1.png', '__pycache__/a.pyc'):
                write(root, name)
            # A plain directory, not a repository: the Preview container cannot run git here.
            self.assertEqual(publish.checkout_manifest(root), {'published': ['blog/a.html', 'index.html'],
                                        'private': ['.github/w.yml', '_delivery.py', 'tools/x.sh']})

    def test_stage_refuses_outside_a_vercel_build_and_any_other_directory(self):
        with patch.dict(os.environ, {'VERCEL_ENV': ''}), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(publish.main(['--stage', 'dist']), 1)
            with self.assertRaises(SystemExit):
                publish.main(['--stage', '.'])

    def test_real_tree_stages_exactly_the_published_selection(self):
        expected = publish.published_files(publish.ROOT)
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(publish.stage(publish.ROOT, Path(temp) / 'dist'), expected)


class AuditTests(unittest.TestCase):
    def test_unclassified_paths_and_published_internals_fail(self):
        errors = exposure.classification_errors(['newdir/a.html', 'thing.webp', 'blog/x.md'])
        self.assertTrue(any('newdir/: unclassified top-level directory' in e for e in errors))
        self.assertTrue(any('thing.webp: unclassified root file' in e for e in errors))
        self.assertTrue(any('blog/x.md: tracked file in a public directory is not deployed' in e for e in errors))

    def test_local_server_and_deployment_share_one_public_site(self):
        self.assertEqual(exposure.config_errors(), [])
        with patch.object(exposure, 'PUBLIC_ROOT_FILES', publish.PUBLIC_ROOT_FILES | {'extra.html'}):
            self.assertTrue(any('PUBLIC_ROOT_FILES differs' in e for e in exposure.config_errors()))
        with patch.object(exposure, 'PUBLIC_DIRS', publish.PUBLIC_DIRS - {'pagefind'}):
            self.assertTrue(any('PUBLIC_DIRECTORIES differs' in e for e in exposure.config_errors()))

    def test_reference_to_an_unpublished_checkout_file_fails(self):
        refs = exposure.references('blog/a.html', '<link href="/data/q.json"><img srcset="x.png 1x, /icon-1.png 2x">'
                                   '<script>fetch(\'/ai/faq.json?v=1\')</script>'
                                   '<a href="https://chendermatologist.com/tools">t</a><a href="mailto:a@b.c">m</a>')
        self.assertEqual(refs, {'/data/q.json', '/blog/x.png', '/icon-1.png', '/ai/faq.json', '/tools'})
        files = {'data/q.json', 'blog/x.png', 'tools.html'}
        self.assertEqual(exposure.resolve('/tools', files), 'tools.html')
        self.assertEqual(exposure.resolve('/blog/', {'blog/index.html'}), 'blog/index.html')
        self.assertIsNone(exposure.resolve('/data/q.json', {'blog/x.png'}))


if __name__ == '__main__':
    unittest.main()
