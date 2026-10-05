"""Manual performance migrations preserve private HTML and author attributes."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import _apply_a11y_vt as a11y
import _apply_f10_image_priority as priority
import _extract_critical_css as critical
import _site_html as sources
from _html_scan import attributes, iter_tags, tag_name


DOCUMENT = '<html><head><link rel="stylesheet" href="/assets/tw-mini.css"></head><body><main><img src="fixture.png" width="640" height="480"></main></body></html>'


class PerformanceMigrationTests(unittest.TestCase):
    def test_priority_handles_real_attribute_quotes_and_preserves_quoted_examples(self):
        for attrs in ["loading='lazy' fetchpriority='low'", 'loading=lazy fetchpriority=low',
                      'LOADING="lazy" FETCHPRIORITY="low"', 'title="loading=lazy fetchpriority=low"']:
            with self.subTest(attrs=attrs):
                result = priority.patch_attrs('src="fixture.png" '+attrs, True)
                parsed = attributes('<img '+result+'>')
                self.assertEqual(parsed['loading'], 'eager')
                self.assertEqual(parsed['fetchpriority'], 'high')
                self.assertEqual(parsed['decoding'], 'async')
                if 'title=' in attrs:
                    self.assertEqual(parsed['title'], 'loading=lazy fetchpriority=low')
                self.assertEqual(priority.patch_attrs(result, True), result)

    def test_priority_ignores_inert_examples_and_preserves_urls_alt_and_later_loading(self):
        inert = '<!-- <img src="comment.png"> --><script>"<img src=script.png>"</script><textarea><img src="text.png"></textarea><template><img src="template.png"></template>'
        source = inert+'<img src=/image/ alt="Example > symbol"><img src="later.png" loading=lazy />'
        result, changed = priority.patch_html(source)
        self.assertTrue(changed)
        self.assertTrue(result.startswith(inert))
        real = [attributes(tag) for _,tag in iter_tags(result[len(inert):]) if tag_name(tag)=='img']
        self.assertEqual(real[0]['src'], '/image/')
        self.assertEqual(real[0]['alt'], 'Example > symbol')
        self.assertEqual(real[0]['loading'], 'eager')
        self.assertEqual(real[1]['loading'], 'lazy')
        self.assertEqual(priority.patch_html(result), (result, False))

    def test_all_manual_migrations_preserve_private_html_and_reject_later_links(self):
        for module in [a11y, priority, critical]:
            for linked in [False, True]:
                with self.subTest(module=module.__name__, linked=linked), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    public = ['index.html', 'blog/fixture.html', 'admin/edit.html', 'en/index.html', 'en/blog/later.html']
                    private = ['.codex-review/saved.html', '.claude-review/saved.html', 'backup/saved.html',
                               'drafts/saved.html', 'blog/backup/saved.html', 'pagefind/saved.html']
                    for name in public+private:
                        f=root/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(DOCUMENT,encoding='utf8')
                    css=root/'assets/tw-mini.css';css.parent.mkdir();css.write_text('body{margin:0}',encoding='utf8')
                    originals={name:(root/name).read_bytes() for name in public+private}
                    actual_linked=sources._linked
                    with contextlib.ExitStack() as stack:
                        stack.enter_context(patch.object(module,'ROOT',str(root)))
                        if module is critical:stack.enter_context(patch.object(module,'CSS_PATH',str(css)))
                        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                        if linked:
                            stack.enter_context(patch.object(sources,'_linked',side_effect=lambda f:f==root/'en/blog/later.html' or actual_linked(f)))
                            with self.assertRaisesRegex(ValueError,'not an ordinary file'):module.main()
                        else:module.main()
                    for name in public+private if linked else private:
                        self.assertEqual((root/name).read_bytes(),originals[name],name)
                    if not linked:
                        self.assertTrue(all((root/name).read_bytes()!=originals[name] for name in public))

    def test_importing_font_downloader_never_creates_assets_or_contacts_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);script=root/'_self_host_fonts.py'
            script.write_bytes(Path('_self_host_fonts.py').read_bytes())
            spec=importlib.util.spec_from_file_location('isolated_fonts',script)
            module=importlib.util.module_from_spec(spec)
            with patch('urllib.request.urlopen',side_effect=AssertionError('import must not download')),contextlib.redirect_stdout(io.StringIO()):
                spec.loader.exec_module(module)
            self.assertFalse((root/'assets').exists())
            self.assertTrue(callable(module.main))


if __name__=='__main__':
    unittest.main()
