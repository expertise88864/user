#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regression tests for _check_zh_english_prose.py.

The fixtures reproduce what the retired _fix_proseen_cjk.py did to the zh
source pages in 2026-05 (whole-file str.replace of Chinese with English), and
the legitimate English the check must keep allowing.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("zhprose", ROOT / "_check_zh_english_prose.py")
zhprose = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zhprose)


def page(body: str) -> str:
    return f'<!doctype html><html lang="zh-Hant-TW"><head><title>t</title></head><body>{body}</body></html>'


class TranslatorFootprintTests(unittest.TestCase):
    def test_replaced_lead_sentence_is_flagged(self):
        # blog/shingles-myths.html before the 2026-10-17 restore
        src = page('<p class="tldr">帶狀皰疹（俗稱<strong data-zh="皮蛇" data-en="Shingles">皮蛇</strong>）'
                   ' genuinely increases the risk of post-herpetic neuralgia (PHN). This article covers 6 of '
                   'the most common misconceptions and whether to get the vaccine.</p>')
        self.assertEqual(len(zhprose.scan(src)), 1)

    def test_half_replaced_sentence_is_flagged(self):
        # blog/rosacea-myths.html: "triggers 累積到一個閾值 before a flare occurs"
        src = page("<p>It's not &quot;one exposure equals immediate flare&quot; — rather, triggers "
                   '<strong>累積到一個閾值</strong> before a flare occurs. Everyone\'s threshold is different '
                   '— track your personal triggers.</p>')
        self.assertTrue(zhprose.scan(src))

    def test_qa_answer_in_div_is_flagged(self):
        src = page('<div class="qa-a"><div><strong>With 70+ years of clinical experience, properly '
                   'monitored use is very safe.</strong> Common side effects are monitorable and reversible.'
                   '</div></div>')
        self.assertTrue(zhprose.scan(src))


class AllowedEnglishTests(unittest.TestCase):
    def assertClean(self, body):
        self.assertEqual(zhprose.scan(page(body)), [])

    def test_restored_chinese_with_data_en_span(self):
        self.assertClean('<p><span data-en=" genuinely increases the risk of post-herpetic neuralgia (PHN). '
                         'This article covers 6 of the most common misconceptions" data-dn-text-only>'
                         '確實會大幅增加皰疹後神經痛（PHN）風險。本文整理 6 個最常見的錯誤觀念</span></p>')

    def test_terms_and_proper_names(self):
        self.assertClean('<p>2026 年《Journal of the American Academy of Dermatology》的編輯評論'
                         '（Letter from the Editor）；SALT（Severity of Alopecia Tool）。</p>')

    def test_inline_citation(self):
        self.assertClean('<p>研究顯示（Pinnell SR. Cutaneous photodamage, oxidative stress, and topical '
                         'antioxidant protection. J Am Acad Dermatol 2003）。</p>')

    def test_hidden_english_mirror_and_references(self):
        self.assertClean('<div id="proseEn" class="prose" style="display:none"><p>This is the English '
                         'mirror of the article and it is hidden on the Chinese page.</p></div>'
                         '<h2 id="refs">參考資料</h2><ol class="references"><li>Simpson EL, et al. '
                         'Baricitinib in adults with moderate to severe atopic dermatitis.</li></ol>')

    def test_reference_list_after_heading_without_class(self):
        self.assertClean('<h2>參考資料</h2><ol><li>Severe psoriasis is a disease that was treated with '
                         'a new retinoid in the trial.</li></ol>')

    def test_footer_and_explicit_english_quote(self):
        self.assertClean('<footer><p>This site is for general education only and is not medical advice.'
                         '</p></footer><blockquote lang="en">The patient is the one with the disease, '
                         'and we treat the person as a whole.</blockquote>')


class DiscoveryTests(unittest.TestCase):
    def test_real_site_pages_are_discovered(self):
        self.assertGreaterEqual(len(zhprose.zh_pages()), zhprose.MIN_FILES)


if __name__ == "__main__":
    unittest.main()
