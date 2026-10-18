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

    def test_empty_or_trivial_rows_are_dropped(self):
        self.assertIsNone(nc.parse_citation(''))
        self.assertIsNone(nc.parse_citation('<em>見上</em>'))


if __name__ == '__main__':
    unittest.main()
