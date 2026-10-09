"""Heading generation preserves private exports and rejects linked sources."""
import contextlib
from html.parser import HTMLParser
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import _normalize_heading_structure as heading
import _site_html as sources


DOCUMENT = '<!doctype html><html><body><h1>Fixture</h1><h4 id="visual">Existing text</h4></body></html>\n'


class HeadingSourceScopeTests(unittest.TestCase):
    def test_article_title_preserves_classes_across_valid_attribute_syntax(self):
        class Headings(HTMLParser):
            def __init__(self):
                super().__init__()
                self.headings = []

            def handle_starttag(self, tag, attrs):
                if tag == 'h1':
                    self.headings.append(attrs)

        for attrs in ["class='authored'", 'class=authored', 'CLASS="authored"',
                      'class = "authored"', 'class="authored"',
                      'data-class="example" class=authored',
                      'class="authored&#32;second"']:
            with self.subTest(attrs=attrs):
                source = '<article><h1 '+attrs+' data-en="Keep > this">Title</h1></article>'
                result = heading.normalize_content_headings(source)
                parsed = Headings()
                parsed.feed(result)
                classes = [value for name, value in parsed.headings[0] if name == 'class']
                self.assertEqual(len(classes), 1)
                self.assertEqual(classes[0].split(),
                                 ['authored', 'second', 'dn-article-title'] if '&#32;' in attrs
                                 else ['authored', 'dn-article-title'])
                self.assertIn('data-en="Keep > this"', result)
                self.assertEqual(heading.normalize_content_headings(result), result)

    def test_class_lookalikes_and_existing_encoded_class_are_preserved(self):
        attrs = ' data-class="example" title="class=sample"'
        result = heading.with_added_class(attrs, 'dn-article-title')
        self.assertIn(' class="dn-article-title"', result)
        self.assertIn(attrs, result)
        encoded = ' class="authored dn&#45;article-title"'
        self.assertEqual(heading.with_added_class(encoded, 'dn-article-title'), encoded)

    def test_non_ascii_spaces_remain_part_of_authored_class_tokens(self):
        for raw, decoded in [('authored&#160;dn-article-title', 'authored\u00a0dn-article-title'),
                             ('authored\u00a0dn-article-title', 'authored\u00a0dn-article-title'),
                             ('&#160;authored', '\u00a0authored'),
                             ('authored&#8195;dn-article-title', 'authored\u2003dn-article-title')]:
            with self.subTest(raw=raw):
                source = '<article><h1 class="' + raw + '">Title</h1></article>'
                expected = '<article><h1 class="' + decoded + ' dn-article-title">Title</h1></article>'
                result = heading.normalize_content_headings(source)
                self.assertEqual(result, expected)
                self.assertEqual(heading.normalize_content_headings(result), result)

    def test_visual_headings_preserve_complete_quoted_attributes(self):
        for name in ('h4', 'h5'):
            with self.subTest(name=name):
                source = '<' + name + ' data-zh="<b>x</b>" class="y">Title</' + name + '>'
                expected = '<div data-zh="<b>x</b>" class="y visual-heading">Title</div>'
                result = heading.normalize_content_headings(source)
                self.assertEqual(result, expected)
                self.assertEqual(heading.normalize_content_headings(result), result)
        source = '<h4 id="lt-tip" data-zh="<b>x</b>">Tip</h4><h5>Other</h5>'
        self.assertEqual(heading.normalize_content_headings(source),
                         '<h3 id="lt-tip" data-zh="<b>x</b>">Tip</h3>'
                         '<div class="visual-heading">Other</div>')

    def test_inert_visual_heading_examples_are_preserved(self):
        example = '<h4 class="author">Example</h4><h5>Text</h5>'
        for source in ('<!--' + example + '-->', '<textarea>' + example + '</textarea>',
                       '<script>const text = ' + repr(example) + ';</script>',
                       '<div data-example="' + example.replace('"', "'") + '">Keep</div>'):
            with self.subTest(source=source):
                self.assertEqual(heading.normalize_content_headings(source), source)

    def test_unterminated_heading_tags_remain_untouched(self):
        for source in ('<article><h1 class="author', '<article><h1', '<h4 class="author',
                       '<h5 data-x=value', '<h4>Title</h4', '<h5>Title</h5'):
            with self.subTest(source=source):
                expected = source.replace('<h4>', '<div class="visual-heading">')
                expected = expected.replace('<h5>', '<div class="visual-heading">')
                self.assertEqual(heading.normalize_content_headings(source), expected)

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
