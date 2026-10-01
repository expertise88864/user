"""Public rendering preserves maintained content and follows approved settings."""
import json
from pathlib import Path
import tempfile
import unittest
from _gen_site_settings import generate
from _site_settings_data import CONTRACT
from _site_settings_render import BEGIN, END, render_theme, theme_css
from _sync_hub_catalog import CardList, render_card, sync_source

EMPTY = {'bodyFont':'','headFont':'','bodySize':''}
FONT = {'bodyFont':"Georgia,'Noto Serif TC',serif",'headFont':"'Inter','Noto Sans TC',sans-serif",'bodySize':'18px'}


class SettingsRenderTests(unittest.TestCase):
    def test_fixed_font_options_compile_and_reset_without_touching_maintained_css(self):
        for newline in ('\n','\r\n'):
            source = '/* keep */' + newline + 'body{color:#222}' + newline
            self.assertEqual(render_theme(source, EMPTY), source)
            rendered = render_theme(source, FONT)
            self.assertTrue(rendered.startswith(source))
            self.assertIn("body{font-family:Georgia,'Noto Serif TC',serif!important}",rendered)
            self.assertIn('article p,article li,article td{font-size:18px!important}',rendered)
            self.assertEqual(render_theme(rendered, FONT), rendered)
            self.assertEqual(render_theme(rendered, EMPTY), source)
            changed = render_theme(rendered, {**FONT,'bodySize':'16px'})
            self.assertEqual(changed.count(BEGIN),1)
            self.assertNotIn('font-size:18px',changed)
        for key, choices in CONTRACT['fonts'].items():
            for choice in choices:
                self.assertIsInstance(theme_css({**EMPTY,key:choice}),str)

    def test_arbitrary_css_and_broken_markers_cannot_erase_maintained_rules(self):
        for font in ({**FONT,'bodyFont':'url(https://unsafe.test)'},{**FONT,'bodySize':'18px;}body{display:none'},
                     {**FONT,'extra':''},{'bodySize':''}):
            with self.subTest(font=font), self.assertRaises(ValueError): theme_css(font)
        for css in (BEGIN,END, '\n'+BEGIN+'\nbody{color:red}\n',
                    '\n'+END+'\n'+BEGIN+'\n', ('\n'+BEGIN+'\nx{}\n'+END+'\n')*2):
            with self.subTest(css=css), self.assertRaises(ValueError): render_theme(css,FONT)

    def test_generator_checks_real_outputs_without_rewriting_author_source(self):
        with tempfile.TemporaryDirectory(prefix='cd-settings-render-') as folder:
            root=Path(folder);(root/'blog').mkdir();(root/'assets').mkdir()
            rows=[{'slug':'alpha','title':'文章','title_en':'Article'}]
            (root/'blog/blog-shared.js').write_text('DN.ARTICLES='+json.dumps(rows)+';',encoding='utf8')
            (root/'blog/alpha.html').write_text('<html><head></head><body>Article</body></html>',encoding='utf8')
            source={'version':1,'legacyPicks':False,'font':FONT,'order':[],'picks':['alpha']}
            raw=(json.dumps(source,indent=2)+'\n').encode()
            (root/CONTRACT['source']).write_bytes(raw)
            css=root/'assets/dn-below-fold.css';css.write_bytes(b'/* maintained */\nbody{color:#222}\n')
            with self.assertRaises(ValueError): generate(root,check=True)
            self.assertEqual(generate(root),1)
            self.assertEqual(generate(root,check=True),1)
            self.assertEqual((root/CONTRACT['source']).read_bytes(),raw)
            self.assertIn('font-size:18px',css.read_text())
            css.write_text(css.read_text().replace('18px','14px'),encoding='utf8')
            with self.assertRaises(ValueError): generate(root,check=True)

    def test_custom_order_is_static_in_both_hubs_and_preserves_author_markup(self):
        rows=[dict(slug=slug,title=slug,title_en=slug,date=date) for slug,date in
              [('alpha','2026-01-01'),('beta','2026-02-01'),('gamma','2026-03-01')]]
        cards=[render_card(row).replace('<div class="al-body">','<div class="al-body"><svg><title>Artwork</title></svg>') for row in rows]
        for element in ('dn-article-list','articleList'):
            source='<head></head><div class="keep" id="'+element+'">'+''.join(cards)+'</div><footer>Keep</footer>'
            result=sync_source(source,element,rows,order=['beta','alpha','gamma'])
            self.assertEqual([c[0] for c in CardList(result,element).cards],['beta','alpha','gamma'])
            self.assertIn('data-dn-settings-order="custom"',result)
            self.assertTrue(result.endswith('<footer>Keep</footer>'))
            for card in cards: self.assertIn(card,result)
            self.assertEqual(sync_source(result,element,rows,order=['beta','alpha','gamma']),result)
            restored=sync_source(result,element,rows,order=[])
            self.assertNotIn('data-dn-settings-order',restored)
            if element=='dn-article-list':
                self.assertEqual([c[0] for c in CardList(restored,element).cards],['gamma','beta','alpha'])
            for invalid in (['alpha'],['alpha','alpha','beta'],['alpha','beta','hidden']):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError): sync_source(source,element,rows,order=invalid)


if __name__=='__main__': unittest.main()
