"""Regression tests for _normalize_citations category-header detection.

Restored Chinese references can be complete in ~20 characters; they must stay
in the dn-citations graph. Headers are recognised structurally (list-style:none)
or by a trailing colon, never by length.
"""
import unittest

import _normalize_citations as nc


def refs(*items: str) -> str:
    return '<ol class="references">' + ''.join(items) + '</ol>'


class CitationMembership(unittest.TestCase):
    def test_short_chinese_reference_is_kept(self):
        li = ('<li><span data-en="Taiwan Dermatological Association." data-dn-text-only>'
              '臺灣皮膚科醫學會。</span><em>白斑臨床治療共識</em>. 2024.</li>')
        names = [c['name'] for c in nc.extract_citations(refs(li))]
        self.assertEqual(names, ['臺灣皮膚科醫學會。白斑臨床治療共識. 2024.'])

    def test_structural_header_is_dropped(self):
        header = '<li style="list-style:none"><strong>指引與共識</strong></li>'
        ref = '<li>Smith J. A long enough reference title. <em>J Dermatol</em>. 2024.</li>'
        names = [c['name'] for c in nc.extract_citations(refs(header, ref))]
        self.assertEqual(len(names), 1)
        self.assertTrue(names[0].startswith('Smith J.'))

    def test_colon_header_is_dropped(self):
        for text in ('Guidelines and consensus:', '指引與共識：'):
            self.assertIsNone(nc.parse_citation('<strong>' + text + '</strong>'))

    def test_journal_year_beats_study_years_in_title(self):
        c = nc.parse_citation('Wang TS, Hsieh CF, Tsai TF. Epidemiology of psoriatic disease and current '
                              'treatment patterns from 2003 to 2013: a nationwide study. '
                              '<em>J Dermatol Sci</em>. 2016;84:340-345.')
        self.assertEqual(c['datePublished'], '2016')

    def test_year_fallback_without_journal_segment(self):
        c = nc.parse_citation('Patient education: Eczema (The Basics). In: UpToDate (accessed November 18, 2026).')
        self.assertEqual(c['datePublished'], '2026')

    def test_pmid_with_or_without_colon(self):
        for ref in ('Shen WC. A long enough title. JAMA Dermatol. 2022;158(2):167-175. PMID 34964804',
                    'Shen WC. A long enough title. JAMA Dermatol. 2022;158(2):167-175. PMID: 34964804'):
            ids = nc.parse_citation(ref)['identifier']
            ids = ids if isinstance(ids, list) else [ids]
            self.assertIn({'@type': 'PropertyValue', 'propertyID': 'PMID', 'value': '34964804'}, ids)

    def test_empty_or_trivial_rows_are_dropped(self):
        self.assertIsNone(nc.parse_citation(''))
        self.assertIsNone(nc.parse_citation('<em>見上</em>'))


if __name__ == '__main__':
    unittest.main()
