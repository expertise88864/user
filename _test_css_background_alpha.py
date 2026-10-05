"""Footer tint preserves child opacity and each article's existing palette."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import _normalize_critical_css as css


class BackgroundAlphaTests(unittest.TestCase):
    def test_only_background_alpha_changes_and_warm_palette_stays_warm(self):
        for color, expected in [('#f5fbfa', '245,251,250'), ('#faf7f2', '250,247,242')]:
            original = '.bg-mint-50\\/60{background-color:'+color+';opacity:.6}'
            result = css.normalize_background_alpha(original)
            self.assertEqual(result, '.bg-mint-50\\/60{background-color:rgba('+expected+',.6)}')
            self.assertEqual(css.normalize_background_alpha(result), result)
            self.assertEqual(css.normalize_background_alpha('.chart{opacity:.6}'), '.chart{opacity:.6}')

    def test_main_updates_public_inline_and_external_rules_preserving_private_and_article_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rule = '.bg-mint-50\\/60{background-color:#f5fbfa;opacity:.6}'
            source = '<html><head><style>'+rule+'</style></head><body><p>Existing authored text</p></body></html>'
            public = root/'blog/fixture.html';public.parent.mkdir();public.write_text(source,encoding='utf8')
            recovery = []
            for name in ['404.html', 'offline.html', 'admin.html']:
                f=root/name
                f.write_text(source.replace('</style>', '@media print{body{color:black}}</style>'),encoding='utf8')
                recovery.append(f)
            private = root/'backup/fixture.html';private.parent.mkdir();private.write_text(source,encoding='utf8')
            external = root/'assets/tw-mini.css';external.parent.mkdir();external.write_text(rule,encoding='utf8')
            def normalize():
                with patch.object(css,'ROOT',root), patch.object(css,'PRINT_CSS_PATH',root/'assets/dn-print.css'), \
                     patch.object(css,'BELOW_FOLD_CSS_PATH',root/'assets/dn-below-fold.css'), contextlib.redirect_stdout(io.StringIO()):
                    css.main()
            normalize()
            after = public.read_text(encoding='utf8')
            self.assertIn('<p>Existing authored text</p>', after)
            self.assertNotIn('opacity:.6', after)
            self.assertEqual(private.read_text(encoding='utf8'), source)
            self.assertEqual(external.read_text(encoding='utf8'), css.normalize_background_alpha(rule))
            for f in recovery:
                self.assertNotIn('opacity:.6',f.read_text(encoding='utf8'))
                self.assertIn('@media print{body{color:black}}',f.read_text(encoding='utf8'))
                self.assertNotIn('dn-print-css',f.read_text(encoding='utf8'))
            normalize()
            self.assertEqual(public.read_text(encoding='utf8'), after)


if __name__=='__main__':
    unittest.main()
