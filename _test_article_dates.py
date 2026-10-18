#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regression tests for the two-date article header (_normalize_article_dates).

Owner's decision 2026-10-17: "內容更新 <content date> · 醫師審閱 <review date>".
The live-corpus comparison with JSON-LD and both ledgers is
_check_seo_signals.check_visible_article_dates(); these tests pin the rewrite
rules for every header shape the corpus has had, idempotency, and that the
pill can never move the content hash that dates it.
"""
from __future__ import annotations

import re
import unittest

import _normalize_article_dates as dates
from _gen_en_pages import apply_data_en
from _normalize_date_modified import prose_hash

PILL = ('<span class="ml-3 inline-block px-2 py-0.5 rounded-full bg-mint-100 text-teal-700 '
        'text-[10.5px] font-semibold normal-case tracking-normal"')
ZH = "內容更新 2026-10-16 · 醫師審閱 2026-05-05"
EN = "Content updated 2026-10-16 · Physician reviewed 2026-05-05"
BODY = "<p>" + "皮膚衛教內容。" * 80 + "</p>"


def page(eyebrow: str, legacy: bool = False) -> str:
    head = f'<main><section><div class="max-w-3xl">{eyebrow}<h1 class="t">標題</h1></div></section>'
    if legacy:
        # Legacy single-<article> layout: the header sits inside the hashed region.
        return f'<main><article class="prose">{eyebrow}<h1>標題</h1>{BODY}</article></main>'
    return head + f'<article><div id="proseZh" class="prose">{BODY}</div></article></main>'


def rewrite(src: str) -> str:
    out, error = dates.rewrite_eyebrow(src, "2026-10-16", "2026-05-05")
    if error:
        raise AssertionError(error)
    return out


def eyebrow_of(src: str) -> str:
    return src[src.index('<div class="text-[11px]'):src.index("<h1")]


def pill_of(src: str) -> str:
    pills = [m.group(0).strip() for m in dates.DATES_PILL_RE.finditer(src)]
    if len(pills) != 1:
        raise AssertionError(f"expected one dates pill, found {len(pills)}")
    return pills[0]


def text_of(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


class HeaderShapes(unittest.TestCase):
    def assert_single_dates_pill(self, out: str) -> None:
        self.assertEqual(out.count("data-dn-article-dates"), 1)
        pill = pill_of(out)
        self.assertTrue(out.split(pill)[1].startswith("</div>"), "pill closes the header")
        self.assertEqual(text_of(pill), ZH)
        self.assertEqual(text_of(apply_data_en(pill)), EN)
        # Wraps only at " · ": each half is one non-breaking, translated span.
        self.assertEqual(pill.count('<span style="white-space:nowrap" data-zh="'), 2)
        self.assertNotRegex(pill.split(">", 1)[0], r"data-(?:zh|en)=")
        self.assertNotRegex(eyebrow_of(out).replace(pill, ""),
                            r"(?:更新|Updated)\s*(?:·\s*)?\d{4}-")

    def test_plain_updated_pill_is_replaced(self):
        src = page('<div class="text-[11px] uppercase mb-3">Patient guide · NHI rules '
                   f'{PILL} data-zh="更新 2026-05-05" data-en="Updated 2026-05-05">更新 2026-05-05</span></div>')
        out = rewrite(src)
        self.assert_single_dates_pill(out)
        self.assertIn('<div class="text-[11px] uppercase mb-3">Patient guide · NHI rules <span', out)

    def test_dated_pill_with_english_text_and_dot_is_replaced(self):
        src = page('<div class="text-[11px] uppercase mb-3">Patient guide · Myth busting '
                   f'{PILL} data-zh="更新日期 · 2026-05-03" data-en="Updated · 2026-05-03">Updated · 2026-05-03</span></div>')
        self.assert_single_dates_pill(rewrite(src))

    def test_pill_wrapped_by_the_zh_restore_is_replaced(self):
        # The 2026-10 zh restore wrapped the pill text in a text-only span.
        src = page('<div class="text-[11px] uppercase mb-3">Patient guide · Myth busting '
                   f'{PILL}><span data-en="Updated · 2026-05-13" data-dn-text-only>'
                   '更新日期 · 2026-05-13</span></span></div>')
        self.assert_single_dates_pill(rewrite(src))

    def test_untranslated_pill_is_replaced(self):
        src = page(f'<div class="text-[11px] uppercase mb-3">Patient guide {PILL}>Updated · 2026-05-13</span></div>')
        self.assert_single_dates_pill(rewrite(src))

    def test_guideline_attribution_keeps_its_text_and_loses_only_the_date(self):
        src = page('<div class="text-[11px] uppercase mb-3">Patient guide · Prescription '
                   f'{PILL} data-zh="依 TDA 2024 共識 · 更新 2026-05-04" '
                   'data-en="Per TDA 2024 consensus · Updated 2026-05-04">依 TDA 2024 共識 · 更新 2026-05-04</span></div>')
        out = rewrite(src)
        self.assert_single_dates_pill(out)
        self.assertIn('data-zh="依 TDA 2024 共識" data-en="Per TDA 2024 consensus">依 TDA 2024 共識</span>', out)

    def test_header_without_a_date_gains_the_pill(self):
        src = page('<div class="text-[11px] uppercase mb-3"><span data-zh="最新研究" data-en="Latest">最新研究</span></div>')
        out = rewrite(src)
        self.assert_single_dates_pill(out)
        self.assertIn('<span data-zh="最新研究" data-en="Latest">最新研究</span> <span', out)

    def test_translated_label_div_moves_its_translation_onto_a_span(self):
        # data-en on the <div> made _gen_en_pages replace the whole header,
        # pill included, with the label's English text.
        src = page('<div class="text-[11px] uppercase mb-3" data-zh="最新研究 · AI" data-en="Latest Research · AI">'
                   f'最新研究 · AI {PILL} data-zh="更新日期 · 2026-05-16" data-en="Updated · 2026-05-16">Updated · 2026-05-16</span></div>')
        out = rewrite(src)
        self.assert_single_dates_pill(out)
        self.assertIn('<div class="text-[11px] uppercase mb-3"><span data-zh="最新研究 · AI" '
                      'data-en="Latest Research · AI">最新研究 · AI</span> <span', out)
        english = apply_data_en(out)
        self.assertEqual(text_of(pill_of(english)), EN)
        self.assertIn(">Latest Research · AI</span>", english)

    def test_rewrite_is_idempotent_and_follows_new_dates(self):
        src = page('<div class="text-[11px] uppercase mb-3">Guide '
                   f'{PILL} data-zh="更新 2026-05-05" data-en="Updated 2026-05-05">更新 2026-05-05</span></div>')
        once = rewrite(src)
        self.assertEqual(rewrite(once), once)
        moved, error = dates.rewrite_eyebrow(once, "2026-11-01", "2026-10-20")
        self.assertIsNone(error)
        self.assertEqual(moved.count("data-dn-article-dates"), 1)
        self.assertEqual(text_of(pill_of(moved)), "內容更新 2026-11-01 · 醫師審閱 2026-10-20")

    def test_missing_header_is_reported_not_guessed(self):
        out, error = dates.rewrite_eyebrow('<main><h1>t</h1></main>', "2026-10-16", "2026-05-05")
        self.assertTrue(error)
        self.assertEqual(out, '<main><h1>t</h1></main>')


class ContentHashIsolation(unittest.TestCase):
    def test_pill_never_moves_the_content_hash(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                src = page('<div class="text-[11px] uppercase mb-3"><span data-zh="衛教" data-en="Guide">衛教</span></div>',
                           legacy=legacy)
                before = prose_hash(src)
                self.assertIsNotNone(before)
                once = rewrite(src)
                self.assertEqual(prose_hash(once), before)
                later, _ = dates.rewrite_eyebrow(once, "2027-01-01", "2026-12-31")
                self.assertEqual(prose_hash(later), before)

    def test_authored_text_still_moves_the_hash(self):
        src = rewrite(page('<div class="text-[11px] uppercase mb-3">Guide</div>', legacy=True))
        self.assertNotEqual(prose_hash(src.replace("皮膚衛教內容", "作者改寫內容", 1)), prose_hash(src))


if __name__ == "__main__":
    unittest.main()
