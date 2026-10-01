"""Guard API/delivery interpretation and exclusion of private article metadata."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from _site_settings_data import CONTRACT, ROOT, catalog_of, load_settings, parse_json, public_settings_catalog, public_settings_of, settings_of


def defaults():
    return {"version": 1, "legacyPicks": True, "font": {"bodyFont": "", "headFont": "", "bodySize": ""}, "order": [], "picks": ["alpha"]}


ARTICLES = [{"slug": slug, "title": "文章 " + slug, "title_en": "Article " + slug} for slug in ("alpha", "beta", "gamma")]


class SettingsDataTests(unittest.TestCase):
    def test_python_and_edge_projection_agree_without_relaxing_new_author_input(self):
        original = defaults()
        cases = [original, {**original, "order": ["gamma", "retired", "alpha"], "picks": ["retired", "beta"]},
                 {**original, "order": ["alpha"], "picks": ["retired"]},
                 {**original, "picks": []}, {**original, "picks": ["../private"]},
                 {**original, "order": ["alpha", "alpha"]}, {**original, "legacyPicks": 1},
                 {**original, "font": {**original["font"], "bodySize": "url(https://unsafe.test)"}}]
        script = """
const fs=require('node:fs'),vm=require('node:vm');
const context={contract:JSON.parse(fs.readFileSync('_site_settings_contract.json','utf8'))};
const source=fs.readFileSync('api/admin/_site-settings.js','utf8').replace(/^import[^\\n]+;\\s*$/gm,'').replace(/^export \\{[^\\n]+\\};\\s*$/gm,'').replace(/\\bexport (class|const|function)/g,'$1');
vm.runInNewContext(source+'\\nthis.validate=(value,articles)=>projectSettings(value,articles);',context);
const input=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(input.cases.map(value=>{try{return {ok:true,value:context.validate(value,input.articles)}}catch(_){return {ok:false}}})));
"""
        node = subprocess.run(["node", "-e", script], cwd=ROOT, input=json.dumps({"cases": cases, "articles": ARTICLES}),
                              text=True, encoding="utf-8", capture_output=True, timeout=15, check=True)
        for value, actual in zip(cases, json.loads(node.stdout), strict=True):
            with self.subTest(value=value):
                before = copy.deepcopy(value)
                try:
                    expected = {"ok": True, "value": public_settings_of(value, ARTICLES)}
                except ValueError:
                    expected = {"ok": False}
                self.assertEqual(actual, expected)
                self.assertEqual(value, before)

    def test_public_projection_survives_catalogue_evolution_without_rewriting_approved_source(self):
        for picks, expected in [(["alpha", "beta"], ["beta"]), (["alpha"], [])]:
            with self.subTest(picks=picks), tempfile.TemporaryDirectory(prefix="cd-settings-evolution-") as directory:
                root = Path(directory)
                (root / "blog").mkdir()
                rows = [{"slug": slug, "title": "Article " + slug, "title_en": "Article " + slug}
                        for slug in ("beta", "delta")]
                (root / "blog/blog-shared.js").write_text("DN.ARTICLES=" + json.dumps(rows) + ";", encoding="utf-8")
                for row in rows:
                    (root / ("blog/" + row["slug"] + ".html")).write_text("<html><head></head><body>Fixture</body></html>", encoding="utf-8")
                approved = {**defaults(), "legacyPicks": False, "order": ["alpha", "beta", "gamma"], "picks": picks}
                raw = (json.dumps(approved, indent=2) + "\n").encode()
                (root / CONTRACT["source"]).write_bytes(raw)
                projected, catalog = load_settings(root)
                self.assertEqual(projected["order"], ["beta", "delta"])
                self.assertEqual(projected["picks"], expected)
                self.assertIs(projected["legacyPicks"], False)
                self.assertEqual(projected["font"], approved["font"])
                self.assertEqual({item["slug"] for item in catalog["articles"]}, {"beta", "delta"})
                self.assertEqual((root / CONTRACT["source"]).read_bytes(), raw)
                with self.assertRaises(ValueError):
                    settings_of(approved, catalog["articles"])

    def test_python_and_edge_api_agree_on_author_input(self):
        valid = defaults()
        cases = [json.dumps(valid), json.dumps({**valid, "version": 1.0}), json.dumps({**valid, "order": ["gamma", "beta", "alpha"]}),
                 '{"version":1,"version":1}', '{"font":{"bodySize":"","body\\u0053ize":"18px"}}',
                 '{"version":NaN}', '[]', 'null', '{']
        cases.append(json.dumps({**valid, "legacyPicks": False}))
        for update in [{"legacyPicks": 0}, {"legacyPicks": "true"}, {"legacyPicks": None}, {"version": True}, {"version": "1"}, {"order": ["alpha"]}, {"order": ["alpha", "beta", "private"]},
                       {"order": ["alpha", "alpha", "beta"]}, {"picks": []}, {"picks": ["private"]}, {"picks": [None]},
                       {"picks": ["alpha", "alpha"]}, {"font": {**valid["font"], "bodySize": "url(https://unsafe.test)"}},
                       {"font": {**valid["font"], "css": "arbitrary"}}, {"source": "arbitrary.html"}]:
            cases.append(json.dumps({**valid, **update}))
        script = """
const fs=require('node:fs'),vm=require('node:vm');
const context={contract:JSON.parse(fs.readFileSync('_site_settings_contract.json','utf8'))};
const source=fs.readFileSync('api/admin/_site-settings.js','utf8').replace(/^import[^\\n]+;\\s*$/gm,'').replace(/^export \\{[^\\n]+\\};\\s*$/gm,'').replace(/\\bexport (class|const|function)/g,'$1');
vm.runInNewContext(source+'\\nthis.validate=(text,articles)=>settingsOf(parseJson(text),articles);',context);
const input=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(input.cases.map(text=>{try{return {ok:true,value:context.validate(text,input.articles)}}catch(_){return {ok:false}}})));
"""
        node = subprocess.run(["node", "-e", script], cwd=ROOT, input=json.dumps({"cases": cases, "articles": ARTICLES}),
                              text=True, encoding="utf-8", capture_output=True, timeout=15, check=True)
        actual = json.loads(node.stdout)
        for raw, result in zip(cases, actual, strict=True):
            with self.subTest(raw=raw):
                try:
                    expected = {"ok": True, "value": settings_of(parse_json(raw), ARTICLES)}
                except ValueError:
                    expected = {"ok": False}
                self.assertEqual(result, expected)

    def test_visibility_catalog_omits_unpublished_and_late_noindex(self):
        with tempfile.TemporaryDirectory(prefix="cd-settings-data-") as directory:
            root = Path(directory)
            (root / "blog").mkdir()
            rows = copy.deepcopy(ARTICLES)
            rows[2]["unpublished"] = True
            (root / "blog/blog-shared.js").write_text("DN.ARTICLES=" + json.dumps(rows, ensure_ascii=False) + ";", encoding="utf-8")
            (root / "blog/alpha.html").write_text('<html><head></head><body>公開</body></html>', encoding="utf-8")
            (root / "blog/beta.html").write_text('<html><head>' + (' ' * 6000) + '<meta content="noindex,follow" name="robots"></head></html>', encoding="utf-8")
            self.assertEqual(public_settings_catalog(root), {"version": 1, "articles": [ARTICLES[0]]})

    def test_real_generated_catalog_is_exact_and_default_source_has_no_author_override(self):
        settings, expected = load_settings()
        actual = parse_json((ROOT / CONTRACT["catalog"]).read_bytes(), limit=200_000)
        self.assertEqual(actual, expected)
        self.assertEqual(len(catalog_of(actual)), 52)
        self.assertEqual(settings["font"], {"bodyFont": "", "headFont": "", "bodySize": ""})
        self.assertEqual(settings["order"], [])
        self.assertIs(settings['legacyPicks'], True, 'bootstrap retains the existing public KV source')
        self.assertNotIn("severe-scabies-treatment", {row["slug"] for row in actual["articles"]})

    def test_default_order_matches_homepage_authored_dates_and_catalogue_ties(self):
        from _sync_hub_catalog import CardList
        expected = [slug for slug, _, _ in CardList((ROOT/'index.html').read_text(encoding='utf8'), 'dn-article-list').cards]
        actual = [item['slug'] for item in public_settings_catalog()['articles']]
        self.assertEqual(actual, expected)

    def test_read_bounds_utf8_duplicate_keys_and_catalog_rejections(self):
        for text in [b'\xff', b' ' * 32_001, '{"v":1,"v":2}', '{"v":Infinity}']:
            with self.subTest(text=str(text)[:40]), self.assertRaises(ValueError):
                parse_json(text)
        for rows in [[ARTICLES[0], ARTICLES[0]], [{**ARTICLES[0], "slug": "../private"}],
                     [{**ARTICLES[0], "title": "\ud800"}], [{**ARTICLES[0], "title_en": ""}],
                     [{**ARTICLES[0], "title": "😀" * 251}], [{**ARTICLES[0], "medicalDraft": "private"}]]:
            with self.subTest(rows=str(rows)[:70]), self.assertRaises(ValueError):
                catalog_of({"version": 1, "articles": rows})


if __name__ == "__main__":
    unittest.main()
