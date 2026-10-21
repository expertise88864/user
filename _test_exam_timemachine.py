"""「考試當年 vs 現行觀念」 (data/exam/timemachine.json) in the exam section.

Validation rules (_gen_exam.validate_timemachine) and where the block lands in
the generated pages: last inside .ex-expl, i.e. inside .ex-reveal, so quiz mode
hides it together with the official answer until the question is graded.
"""
from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path

import _gen_exam as gen

ROOT = Path(__file__).resolve().parent
TM = json.loads((ROOT / "data" / "exam" / "timemachine.json").read_text(encoding="utf-8"))
QIDS = {q["id"] for q in json.loads((ROOT / "data" / "exam" / "questions.json").read_text(encoding="utf-8"))}


def entry() -> dict:
    return {
        "then": "考試當年的說法", "now": "現行的說法", "changed": "2020 年起",
        "answer_impact": {"level": "不影響", "note": "官方答案不變。"},
        "sources": [{"title": "A guideline", "year": 2020, "url": "https://example.org/a"}],
    }


def card(html: str, qid: str) -> str:
    start = html.index(f'id="q-{qid}"')
    return html[start:html.index("</article>", start)]


class ValidationTests(unittest.TestCase):
    def test_committed_data_is_valid(self):
        self.assertEqual(gen.validate_timemachine(TM, QIDS), [])
        self.assertEqual(sorted(TM), ["101-04", "104-25", "104-42", "105-16", "106-23", "106-24", "106-44", "107-02", "107-19", "107-49", "109-15", "112-11"])
        self.assertNotIn("106-20", TM, "106-20 was moved out by the physician (2026-10-18)")

    def test_unknown_question_id(self):
        errors = gen.validate_timemachine({"099-01": entry()}, QIDS)
        self.assertTrue(any("099-01: unknown question id" in e for e in errors), errors)

    def test_every_entry_needs_sources_with_urls(self):
        for sources in ([], None):
            bad = entry()
            bad["sources"] = sources
            self.assertTrue(any("needs at least one source" in e for e in gen.validate_timemachine({"101-04": bad}, QIDS)))
        for url in (None, "", "pubmed 12345", "javascript:alert(1)"):
            bad = entry()
            bad["sources"].append({"title": "No link", "year": 2001, **({} if url is None else {"url": url})})
            errors = gen.validate_timemachine({"101-04": bad}, QIDS)
            self.assertTrue(any("source 2 has no url" in e for e in errors), (url, errors))

    def test_impact_level_is_one_of_two(self):
        for level in gen.TM_LEVELS:
            ok = entry()
            ok["answer_impact"]["level"] = level
            self.assertEqual(gen.validate_timemachine({"101-04": ok}, QIDS), [])
        for level in ("影響", "依現行觀念答案不同", "", None):
            bad = entry()
            bad["answer_impact"]["level"] = level
            errors = gen.validate_timemachine({"101-04": bad}, QIDS)
            self.assertTrue(any("answer_impact.level" in e for e in errors), (level, errors))

    def test_missing_text_fields(self):
        for field in ("then", "now", "changed"):
            bad = entry()
            del bad[field]
            self.assertTrue(any(f"missing text '{field}'" in e for e in gen.validate_timemachine({"101-04": bad}, QIDS)))
        bad = entry()
        bad["answer_impact"]["note"] = " "
        self.assertTrue(any("answer_impact.note" in e for e in gen.validate_timemachine({"101-04": bad}, QIDS)))

    def test_simplified_characters_are_rejected_anywhere(self):
        for path, text in ((("now",), "现行观念"), (("answer_impact", "note"), "答案不变"),
                           (("sources", 0, "title"), "皮肤病学")):
            bad = copy.deepcopy(entry())
            target = bad
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = text
            errors = gen.validate_timemachine({"101-04": bad}, QIDS)
            self.assertTrue(any("simplified characters" in e for e in errors), (path, errors))

    def test_simplified_list_has_no_traditional_characters(self):
        # Characters the site's Traditional text really uses must never be flagged.
        corpus = (ROOT / "data" / "exam" / "explanations.json").read_text(encoding="utf-8")
        self.assertEqual(sorted(set(corpus) & gen.HANS_ONLY), [])


class RenderTests(unittest.TestCase):
    def test_block_order_escaping_and_links(self):
        tm = entry()
        tm["now"] = "a < b & c"
        tm["sources"][0]["title"] = 'Title "quoted" <b>'
        html = gen.timemachine_html(tm)
        labels = [html.index(x) for x in ("考試當年 vs 現行觀念", "<dt>考試當年</dt>", "<dt>現行觀念</dt>",
                                          "<dt>何時改變</dt>", "<dt>對答案的影響</dt>", "參考文獻")]
        self.assertEqual(labels, sorted(labels))
        self.assertIn("a &lt; b &amp; c", html)
        self.assertIn("Title &quot;quoted&quot; &lt;b&gt;", html)
        self.assertIn('<a href="https://example.org/a" target="_blank" rel="noopener noreferrer">', html)
        self.assertIn('class="ex-tm-level ex-tm-same">不影響</span>', html)
        tm["answer_impact"]["level"] = gen.TM_LEVELS[1]
        self.assertIn("ex-tm-diff", gen.timemachine_html(tm))
        self.assertEqual(gen.timemachine_html(None), "")


class GeneratedPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = gen.build()

    def test_every_page_showing_the_explanation_has_the_block_inside_the_reveal(self):
        data = gen.load()
        for qid, tm in TM.items():
            q = next(q for q in data["questions"] if q["id"] == qid)
            tag = data["tags"][qid]
            pages = [f"year-{q['year']}.html"] + [f"fitz-{c}.html" for c in tag["fitz"]]
            pages += [f"{b}.html" for b in tag.get("other", [])]
            for name in pages:
                body = card(self.files[name], qid)
                reveal = body[body.index('<div class="ex-reveal">'):]
                self.assertEqual(reveal.count('<div class="ex-tm">'), 1, (qid, name))
                self.assertTrue(body.rstrip().endswith("</ul></div></div></div>"), (qid, name))
                for text in (tm["then"], tm["now"], tm["changed"], tm["answer_impact"]["note"]):
                    self.assertIn(gen.rich(text), reveal, (qid, name))
                for src in tm["sources"]:
                    self.assertIn(f'href="{gen.esc(src["url"])}" target="_blank" rel="noopener noreferrer"', reveal)

    def test_block_follows_the_dispute(self):
        body = card(self.files["fitz-117.html"], "101-04")
        self.assertLess(body.index('class="ex-dispute"'), body.index('class="ex-tm"'))

    def test_questions_without_an_entry_have_no_block(self):
        total = sum(html.count('<div class="ex-tm">') for name, html in self.files.items() if name.endswith(".html"))
        expected = sum(1 + len(gen.load()["tags"][qid]["fitz"]) + len(gen.load()["tags"][qid].get("other", []))
                       for qid in TM)
        self.assertEqual(total, expected)

    def test_client_data_carries_the_entries_verbatim(self):
        client = json.loads(self.files["exam-data.json"])
        got = {q["id"]: q["tm"] for q in client["questions"] if "tm" in q}
        self.assertEqual(got, TM)

    def test_quiz_mode_css_hides_the_reveal(self):
        self.assertIn("body.ex-quiz .ex-q:not(.ex-done) .ex-reveal{display:none}", gen.EXAM_STYLE)
        self.assertTrue(re.search(r":root\[data-theme=\"dark\"\] \.ex-tm\{", gen.EXAM_STYLE))


if __name__ == "__main__":
    unittest.main()
