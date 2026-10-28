"""Exam section SEO (2026-10-28): page date ledger, sitemap lastmod, Chinese
chapter names, the split 考點 pages and per-page share cards.

Runs against the committed generator output and against in-memory rebuilds
(_gen_exam.build() writes nothing); temporary files only for --check.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _gen_exam as gen
import _gen_exam_og as og

ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"


def committed_ledger() -> dict:
    return json.loads((ROOT / "data" / "exam" / "page_dates.json").read_text(encoding="utf-8"))


class LedgerTests(unittest.TestCase):
    def dates(self, ledger: dict, path: str, body: str, today: str) -> tuple[str, str]:
        with patch.dict(gen.LEDGER, ledger, clear=True), patch.dict(gen.NEW_LEDGER, {}, clear=True), \
                patch.object(gen, "CONTENT_DATE", [today]):
            got = gen.page_dates(path, body)
            self.assertEqual(gen.NEW_LEDGER[path]["published"], got[0])
            return got

    def test_unchanged_content_keeps_dates_on_any_day(self):
        body = "<h1>Ch.1</h1><p>重點</p>"
        entry = {"hash": gen.content_hash(body), "published": "2026-10-15", "modified": "2026-10-21"}
        self.assertEqual(self.dates({"/exam/x": entry}, "/exam/x", body, "2099-01-01"),
                         ("2026-10-15", "2026-10-21"))

    def test_changed_content_takes_the_content_date_and_keeps_published(self):
        entry = {"hash": gen.content_hash("<p>舊</p>"), "published": "2026-10-15", "modified": "2026-10-21"}
        self.assertEqual(self.dates({"/exam/x": entry}, "/exam/x", "<h1>a</h1><p>新</p>", "2026-11-02"),
                         ("2026-10-15", "2026-11-02"))

    def test_new_page_is_published_and_modified_on_the_content_date(self):
        self.assertEqual(self.dates({}, "/exam/new", "<h1>a</h1>", "2026-11-02"), ("2026-11-02", "2026-11-02"))

    def test_hash_ignores_markup_outline_and_breadcrumbs_but_not_text(self):
        base = gen.content_hash('<h1>Ch.1</h1><p class="a">重點 一</p>')
        self.assertEqual(base, gen.content_hash('<h1 class="x">Ch.1</h1>\n<p><b>重點</b>一</p>'))
        self.assertEqual(base, gen.content_hash(
            '<nav class="crumbs"><a href="/">首頁</a></nav><h1>Ch.1</h1>'
            '<details class="ex-toc ex-toc-mobile"><summary>本章目錄</summary><nav><ol><li>x</li></ol></nav></details>'
            '<p>重點一</p>'))
        self.assertNotEqual(base, gen.content_hash("<h1>Ch.1</h1><p>重點二</p>"))

    def test_visible_date_joins_the_meta_line_or_gets_its_own(self):
        stamp = '<span class="ex-updated">最後更新：<time datetime="2026-10-28">2026-10-28</time></span>'
        self.assertEqual(gen.with_updated('<h1>a</h1><p class="ex-meta">原書 p.1</p><p>x</p>', "2026-10-28"),
                         f'<h1>a</h1><p class="ex-meta">原書 p.1 · {stamp}</p><p>x</p>')
        self.assertEqual(gen.with_updated('<h1>a</h1><p class="ex-lead">x</p>', "2026-10-28"),
                         f'<h1>a</h1><p class="ex-meta">{stamp}</p><p class="ex-lead">x</p>')

    def test_invalid_ledger_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "page_dates.json"
            for bad in ({"/exam": {"hash": "x", "published": "2026-10-28", "modified": "2026-10-01"}},
                        {"/exam": {"hash": "x", "published": "2026-1-1", "modified": "2026-10-01"}},
                        {"/exam": {"hash": "x", "published": "2026-10-01"}}):
                path.write_text(json.dumps(bad), encoding="utf-8")
                with patch.object(gen, "PAGE_DATES", path), self.assertRaises(SystemExit):
                    gen.load_ledger()


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = gen.build("2099-01-01")
        cls.ledger = dict(gen.NEW_LEDGER)
        cls.cards = dict(gen.OG_CARDS)
        cls.data = gen.load()

    def test_rebuild_on_another_day_reproduces_the_committed_dates(self):
        # No wall clock: an unchanged tree rebuilds byte-identical dates in 2099.
        self.assertEqual(self.ledger, committed_ledger())
        self.assertEqual(set(self.ledger), {"/exam" if n == "index.html" else "/exam/" + n[:-5]
                                            for n in self.files if n.endswith(".html")})

    def test_a_content_change_moves_only_that_pages_date(self):
        real_load = gen.load

        def edited():
            data = real_load()
            data["notes"][52] = data["notes"][52] + "<p>測試用新增段落</p>"
            return data

        with patch.object(gen, "load", edited):
            files = gen.build("2099-01-01")
            ledger = dict(gen.NEW_LEDGER)
        gen.build("2099-01-01")  # restore module state for other tests
        moved = {p: e for p, e in ledger.items() if e != self.ledger[p]}
        self.assertEqual(list(moved), ["/exam/fitz-52"])
        self.assertEqual(moved["/exam/fitz-52"]["modified"], "2099-01-01")
        self.assertEqual(moved["/exam/fitz-52"]["published"], self.ledger["/exam/fitz-52"]["published"])
        self.assertIn('"dateModified":"2099-01-01"', files["fitz-52.html"])
        self.assertIn('<time datetime="2099-01-01">2099-01-01</time>', files["fitz-52.html"])

    def test_check_mode_fails_when_the_ledger_is_stale(self):
        with tempfile.TemporaryDirectory() as folder:
            stale = committed_ledger()
            stale["/exam/fitz-52"]["hash"] = "0" * 16
            path = Path(folder) / "page_dates.json"
            path.write_text(gen.ledger_text(stale), encoding="utf-8")
            with patch.object(gen, "PAGE_DATES", path), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(gen.main(["--check"]), 1)
            self.assertIn("page_dates.json", out.getvalue())

    def test_jsonld_and_visible_dates_and_image(self):
        for name, html in self.files.items():
            if not name.endswith(".html"):
                continue
            route = "/exam" if name == "index.html" else "/exam/" + name[:-5]
            entry = self.ledger[route]
            node = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html).group(1))
            self.assertEqual((node["datePublished"], node["dateModified"]), (entry["published"], entry["modified"]), name)
            self.assertEqual(html.count('<span class="ex-updated">'), 1, name)
            og_image = re.search(r'<meta property="og:image" content="([^"]+)" />', html).group(1)
            self.assertEqual(node["image"]["url"], og_image, name)
            self.assertIn(f'<meta name="twitter:image" content="{og_image}" />', html)
            self.assertTrue(og_image.startswith(DOMAIN + "/assets/og/exam/"), name)
            self.assertIn(og_image.rsplit("/", 1)[1][:-4], self.cards, name)

    def test_chapter_pages_carry_the_chinese_name(self):
        html = self.files["fitz-52.html"]
        self.assertIn("<title>Fitzpatrick Ch.52 天疱瘡 Pemphigus 重點與考題 | 陳翊嘉醫師 · ChenDermatologist</title>", html)
        self.assertIn('<meta property="og:title" content="Fitzpatrick Ch.52 天疱瘡 Pemphigus 重點與考題" />', html)
        self.assertIn('<h1 class="ex-h1">Ch.52 Pemphigus <span class="ex-h1-zh">天疱瘡</span></h1>', html)
        self.assertIn("第 52 章 天疱瘡（Pemphigus）", html)
        self.assertIn('"name":"Ch.52 天疱瘡"', html)  # breadcrumb
        self.assertEqual(self.cards["fitz-52"], {"kicker": "Fitzpatrick 9e · 專科考試", "title": "Ch.52 天疱瘡",
                                                 "subtitle": "Pemphigus", "foot": "考題 17 題 · 重點整理"})
        from _check_meta_descriptions import cjk_width
        for name, html in self.files.items():
            m = re.fullmatch(r"fitz-(\d+)\.html", name)
            if m:
                zh = self.data["zh_titles"][int(m.group(1))][0]
                title = re.search(r"<title>([^<]*)</title>", html).group(1)
                self.assertIn(zh, title, name)
                if cjk_width(f"Ch.{m.group(1)} {zh} {self.data['chapters'][int(m.group(1))]['title']} 重點與考題") <= 100:
                    self.assertLessEqual(cjk_width(title), 100, name)

    def test_a_chapter_without_a_chinese_name_keeps_the_english_form(self):
        real_load = gen.load

        def no_zh():
            data = real_load()
            data["zh_titles"].pop(52)
            return data

        with patch.object(gen, "load", no_zh):
            html = gen.build("2099-01-01")["fitz-52.html"]
            card = gen.OG_CARDS["fitz-52"]
        gen.build("2099-01-01")
        self.assertIn("<title>Fitzpatrick Ch.52 Pemphigus 重點與考題 | 陳翊嘉醫師 · ChenDermatologist</title>", html)
        self.assertIn('<h1 class="ex-h1">Ch.52 Pemphigus</h1>', html)
        self.assertEqual(card["title"], "Ch.52")

    def test_fit_title_drops_the_prefix_before_the_site_name(self):
        from _check_meta_descriptions import cjk_width
        long = "Fitzpatrick Ch.1 " + "字" * 24 + " 重點與考題"
        got = gen.fit_title(long)
        self.assertLessEqual(cjk_width(got), 100)
        self.assertTrue(got.startswith("Ch.1 "))
        self.assertEqual(gen.fit_title("Fitzpatrick Ch.2 短 重點與考題"),
                         "Fitzpatrick Ch.2 短 重點與考題 | 陳翊嘉醫師 · ChenDermatologist")

    def test_every_concept_is_on_exactly_one_part_page(self):
        parts = {n: html for n, html in self.files.items() if re.fullmatch(r"concepts-p\d+\.html", n)}
        self.assertEqual(len(parts), 31)
        seen: dict[str, str] = {}
        for name, html in parts.items():
            for cid in re.findall(r'<li id="c-([^"]+)"', html):
                self.assertNotIn(cid, seen, f"{cid} on {name} and {seen.get(cid)}")
                seen[cid] = name
        concepts = self.data["concepts"]
        self.assertEqual(set(seen), {c["id"] for c in concepts})
        for c in concepts:
            self.assertEqual(seen[c["id"]], f"concepts-p{gen.part_of(self.data, c['ch'])}.html")
        self.assertNotIn('<li id="c-', self.files["concepts.html"])
        index = json.loads(self.files["concepts-index.json"])
        self.assertEqual([r[0] for r in index["concepts"]], [c["id"] for c in concepts])
        self.assertTrue(all(seen[r[0]] == f"concepts-p{r[6]}.html" for r in index["concepts"]))
        self.assertIn(f'data-cx-hub="/exam/concepts-index.json?v=', self.files["concepts.html"])

    def test_concept_pages_are_small(self):
        for name, html in self.files.items():
            if name.startswith("concepts") and name.endswith(".html"):
                self.assertLess(len(html.encode("utf-8")), 300_000, name)

    def test_every_concept_link_resolves_and_none_use_the_old_overview_anchor(self):
        ids = {n[:-5]: set(re.findall(r'\bid="([^"]+)"', h)) for n, h in self.files.items() if n.endswith(".html")}
        checked = 0
        for name, text in self.files.items():
            self.assertNotRegex(text, r"/exam/concepts(?:\.html)?[#?]", name)
            for page, frag in re.findall(r'href="/exam/(concepts-p\d+)(?:\?ch=\d+)?(?:#([^"]+))?"', text):
                self.assertIn(page, ids, name)
                if frag:
                    self.assertIn(frag, ids[page], f"{name} -> {page}#{frag}")
                    checked += 1
        self.assertGreater(checked, 2000)
        self.assertIn('href="/exam/concepts-p9?ch=52"', self.files["fitz-52.html"])

    def test_cards_cover_every_page(self):
        self.assertEqual(set(self.cards), {n[:-5] for n in self.files if re.fullmatch(r"(fitz|year)-\d+\.html", n)}
                         | {"hub", "concepts", "mckee", "kantor"})


class CommittedOutputTests(unittest.TestCase):
    def test_sitemap_lastmod_is_each_pages_date_modified(self):
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        lastmods = dict(re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", sitemap))
        ledger = committed_ledger()
        for route, entry in ledger.items():
            self.assertEqual(lastmods.get(DOMAIN + route), entry["modified"], route)
        self.assertGreater(len({e["modified"] for e in ledger.values()}), 3, "dates are per page, not one day")

    def test_committed_cards_match_their_text(self):
        specs = og.load_json(og.SPECS)
        self.assertEqual(og.check(specs, og.load_json(og.RECORD)), [])
        edited = dict(specs, **{"fitz-52": dict(specs["fitz-52"], foot="考題 18 題 · 重點整理")})
        self.assertEqual(og.stale_cards(edited, og.load_json(og.RECORD)), ["fitz-52"])

    def test_card_check_reports_missing_and_stray_files(self):
        specs = og.load_json(og.SPECS)
        record = og.load_json(og.RECORD)
        errors = og.check(dict(specs, **{"fitz-9999": dict(specs["fitz-52"], title="Ch.9999")}), record)
        self.assertTrue(any("fitz-9999.png is missing" in e for e in errors))
        errors = og.check({k: v for k, v in specs.items() if k != "fitz-52"}, record)
        self.assertTrue(any("fitz-52" in e and "no exam page uses" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
