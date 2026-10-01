"""Public description generation must not reintroduce excluded article data."""
from pathlib import Path
import json,tempfile,unittest
from unittest.mock import patch
import _normalize_articles_desc as generator

class DescriptionsTests(unittest.TestCase):
    def test_public_projection_and_repeat_generation_preserve_visible_descriptions(self):
        with tempfile.TemporaryDirectory(prefix='article-desc-fixture-') as folder:
            root=Path(folder).resolve()
            self.assertEqual(root.parent,Path(tempfile.gettempdir()).resolve())
            blog=root/'blog';blog.mkdir();en=root/'en'/'blog';en.mkdir(parents=True)
            rows=[{'slug':slug,'title':slug,'title_en':slug,**flags} for slug,flags in
              [('visible',{}),('draft',{'unpublished':True}),('noindex',{})]]
            shared=blog/'blog-shared.js';shared.write_text('DN.ARTICLES = '+json.dumps(rows)+';',encoding='utf8')
            hub=blog/'blog-hub.js';hub.write_text('(function(){\n})();',encoding='utf8')
            for slug in ('visible','draft','noindex'):
                robots='<meta name="robots" content="noindex,follow">' if slug=='noindex' else ''
                (blog/(slug+'.html')).write_text('<html><head>'+(' '*6000)+robots+'<meta name="description" content="'+slug+' description"></head><body></body></html>',encoding='utf8')
            (en/'visible.html').write_text('<meta name="description" content="English visible description">',encoding='utf8')
            with patch.multiple(generator,ROOT=root,SHARED=shared,HUB=hub,BLOG=blog,EN_BLOG=en):
                self.assertEqual(generator.parse_slugs_from_shared(),['visible'])
                self.assertEqual(generator.main(),0)
                first=hub.read_bytes()
                self.assertIn(b'visible description',first);self.assertIn(b'English visible description',first)
                self.assertNotIn(b'draft description',first);self.assertNotIn(b'noindex description',first)
                self.assertEqual(generator.main(),0);self.assertEqual(first,hub.read_bytes())

    def test_malformed_catalogue_cannot_silently_clear_previous_descriptions(self):
        with tempfile.TemporaryDirectory(prefix='article-desc-fixture-') as folder:
            root=Path(folder).resolve();self.assertEqual(root.parent,Path(tempfile.gettempdir()).resolve())
            blog=root/'blog';blog.mkdir()
            shared=blog/'blog-shared.js';shared.write_text('DN.ARTICLES = [];',encoding='utf8')
            hub=blog/'blog-hub.js';hub.write_text('(function(){/* previous description fixture */})();',encoding='utf8')
            before=hub.read_bytes()
            with patch.multiple(generator,ROOT=root,SHARED=shared,HUB=hub,BLOG=blog,EN_BLOG=root/'en'/'blog'):
                with self.assertRaises(ValueError):generator.main()
            self.assertEqual(before,hub.read_bytes())

if __name__=='__main__':unittest.main()
