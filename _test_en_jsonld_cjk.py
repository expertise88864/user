#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for _check_en_jsonld_cjk.py and _localize_en_jsonld.py (2026-10-18)."""
from __future__ import annotations

import json
import unittest

import _check_en_jsonld_cjk as check
import _localize_en_jsonld as loc


def ld(obj) -> str:
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False) + '</script>'


class CheckTests(unittest.TestCase):
    def test_flags_chinese_citation_in_is_based_on(self):
        # the 2026-10-18 CI failure on en/blog/prurigo-nodularis.html
        src = ld({"@type": "MedicalWebPage", "isBasedOn": [
            {"@type": "ScholarlyArticle", "name": "臺灣皮膚科醫學會。 結節性癢疹診斷與管理共識. 2024 年 9 月。"}]})
        self.assertEqual(len(check.scan(src)), 1)

    def test_flags_mixed_english_and_chinese(self):
        src = ld({"@type": "ScholarlyArticle", "name": "Taiwan Dermatological Association. 結節性癢疹診斷與管理共識"})
        self.assertTrue(check.scan(src))

    def test_alternate_name_is_exempt(self):
        src = ld({"@type": "Physician", "name": "Dr. Chen Yi-Jia", "alternateName": ["陳翊嘉醫師"]})
        self.assertEqual(check.scan(src), [])

    def test_physician_identity_and_iris_are_exempt(self):
        src = ld({"@type": "MedicalWebPage", "author": {"@type": "Physician", "@id": check.PHYSICIAN_ID,
                  "name": "陳翊嘉 醫師"}, "mentions": [{"@id": "https://chendermatologist.com/glossary#term-蕈狀肉芽腫"}]})
        self.assertEqual(check.scan(src), [])

    def test_other_person_name_is_not_exempt(self):
        self.assertTrue(check.scan(ld({"@type": "Person", "name": "王小明"})))

    def test_unparseable_block_fails(self):
        self.assertTrue(check.scan('<script type="application/ld+json">{oops</script>'))


class LocalizerTests(unittest.TestCase):
    def test_citation_name_from_li_data_en(self):
        zh = ('<ol class="references"><li data-zh="臺灣皮膚科醫學會(TDA)各疾病臨床診療共識：痤瘡(2024)。" '
              'data-en="Taiwanese Dermatological Association (TDA) consensus statements: acne (2024).">'
              '臺灣皮膚科醫學會(TDA)各疾病臨床診療共識：痤瘡(2024)。</li></ol>')
        cmap = loc.citation_map(zh)
        (zh_name, en_name), = cmap.items()
        self.assertNotRegex(en_name, loc.CJK)
        self.assertEqual(loc.translate_citation_name(zh_name, cmap), en_name)

    def test_chinese_date_tail_is_translated(self):
        self.assertEqual(loc.english_reference_tail("TDA Consensus. 2024 年 9 月。"), "TDA Consensus. September 2024.")

    def test_physician_identity_is_kept(self):
        node = {"@type": "Physician", "@id": loc.PHYSICIAN_ID, "name": "陳翊嘉 醫師", "givenName": "翊嘉"}
        self.assertEqual(loc.localize(node, {}, {}), node)

    def test_organization_name_keeps_chinese_in_alternate_name(self):
        out = loc.localize({"@type": "Organization", "name": "陳翊嘉醫師 · 皮膚科衛教筆記"}, {}, {})
        self.assertEqual(out["name"], "Dr. Chen Yi-Jia · Dermatology Notes")
        self.assertEqual(out["alternateName"], "陳翊嘉醫師 · 皮膚科衛教筆記")

    def test_item_list_uses_catalog_title_and_iri_is_kept(self):
        out = loc.localize({"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "url": "https://chendermatologist.com/blog/acne-myths", "name": "痘痘 8 大迷思"}],
            "@id": "https://chendermatologist.com/glossary#term-蕈狀肉芽腫"}, {}, {"acne-myths": "8 Acne Myths"})
        self.assertEqual(out["itemListElement"][0]["name"], "8 Acne Myths")
        self.assertEqual(out["@id"], "https://chendermatologist.com/glossary#term-蕈狀肉芽腫")

    def test_keywords_drop_chinese_synonyms(self):
        out = loc.localize({"keywords": "Acne, 尋常性痤瘡, 皮膚科, 衛教, dermatology"}, {}, {})
        self.assertEqual(out["keywords"], "Acne, dermatology, patient education")


if __name__ == "__main__":
    unittest.main()
