"""Heading generation preserves private exports and rejects linked sources."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import _normalize_heading_structure as heading
import _site_html as sources


DOCUMENT = '<!doctype html><html><body><h1>Fixture</h1><h4 id="visual">Existing text</h4></body></html>\n'


class HeadingSourceScopeTests(unittest.TestCase):
    def write(self, root, name):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(DOCUMENT, encoding='utf8')
        return target

    def run_normalizer(self, root):
        with patch.object(heading, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
            heading.main()

    def test_build_normalizes_all_deployed_roots_and_preserves_private_html(self):
        with tempfile.TemporaryDirectory(prefix='heading-source-scope-') as directory:
            root = Path(directory)
            public = ['index.html', 'blog/fixture.html', 'admin/edit.html', 'en/index.html', 'en/blog/fixture.html']
            private = ['.codex-review/saved.html', '.claude-review/saved.html', '.lighthouseci/saved.html',
                       'delivery-preview/saved.html', 'backup/saved.html', 'drafts/saved.html',
                       'blog/backup/saved.html', 'admin/exports/saved.html', 'en/blog/backup/saved.html']
            for name in public + private:
                self.write(root, name)
            original = {name: (root / name).read_bytes() for name in public + private}
            with patch.object(heading, 'ROOT', root):
                self.assertEqual([p.relative_to(root).as_posix() for p in heading.iter_html_files()], sorted(public))
            self.run_normalizer(root)
            for name in public:
                result = (root / name).read_text(encoding='utf8')
                self.assertIn('<div class="visual-heading" id="visual">Existing text</div>', result, name)
            for name in private:
                self.assertEqual((root / name).read_bytes(), original[name], name)
            normalized = {name: (root / name).read_bytes() for name in public}
            self.run_normalizer(root)
            self.assertEqual({name: (root / name).read_bytes() for name in public}, normalized)

    def test_later_linked_source_is_rejected_before_any_public_write(self):
        with tempfile.TemporaryDirectory(prefix='heading-source-scope-') as directory:
            root = Path(directory)
            first = self.write(root, 'index.html')
            later = self.write(root, 'en/blog/linked.html')
            originals = [first.read_bytes(), later.read_bytes()]
            real_linked = sources._linked
            # Portable link-discovery fixture; this does not claim OS symlink validation.
            with patch.object(sources, '_linked', side_effect=lambda path: path == later or real_linked(path)):
                with self.assertRaisesRegex(ValueError, 'not an ordinary file'):
                    self.run_normalizer(root)
            self.assertEqual([first.read_bytes(), later.read_bytes()], originals)

    def test_linked_source_root_is_rejected_before_any_public_write(self):
        with tempfile.TemporaryDirectory(prefix='heading-source-scope-') as directory:
            root = Path(directory)
            first = self.write(root, 'index.html')
            self.write(root, 'blog/fixture.html')
            original = first.read_bytes()
            real_linked = sources._linked
            with patch.object(sources, '_linked', side_effect=lambda path: path == root / 'blog' or real_linked(path)):
                with self.assertRaisesRegex(ValueError, 'Linked site source directory'):
                    self.run_normalizer(root)
            self.assertEqual(first.read_bytes(), original)

    def test_non_directory_source_root_is_rejected_without_creating_output(self):
        with tempfile.TemporaryDirectory(prefix='heading-source-scope-') as directory:
            root = Path(directory) / 'missing'
            with self.assertRaisesRegex(ValueError, 'not a directory'):
                self.run_normalizer(root)
            self.assertFalse(root.exists())


if __name__ == '__main__':
    unittest.main()
