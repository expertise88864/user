"""The accessibility gate must count real DOM IDs, including quoted variants."""
import contextlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import _check_static_a11y as audit


class AccessibilityIDTests(unittest.TestCase):
    def check(self, fragment):
        with TemporaryDirectory() as directory:
            root=Path(directory);path=root/'fixture.html'
            path.write_text('<html><body><h1>Fixture</h1>'+fragment+'</body></html>',encoding='utf8')
            output=io.StringIO()
            with patch.object(audit,'ROOT',root), patch.object(audit,'iter_html_files',return_value=[path]), contextlib.redirect_stdout(output):
                code=audit.main()
            return code,output.getvalue()

    def test_provenance_and_quoted_attribute_payload_are_not_extra_dom_ids(self):
        code,output=self.check('<h2 id="overview" data-dn-heading-id="overview">Overview</h2>'
                               '<aside id="fake" title=\'example id="fake"\'>Example</aside>')
        self.assertEqual(code,0,output)

    def test_real_duplicate_ids_still_fail(self):
        code,output=self.check('<h2 id="overview">Overview</h2><aside id="overview"></aside>')
        self.assertEqual(code,1)
        self.assertIn('duplicate id #overview',output)

    def test_single_unquoted_and_entity_decoded_duplicate_ids_also_fail(self):
        code,output=self.check('<h2 id=overview>Overview</h2><aside ID=\'overview\'></aside>'
                               '<div id="a&amp;b"></div><div id=\'a&b\'></div>')
        self.assertEqual(code,1)
        self.assertIn('duplicate id #overview',output)
        self.assertIn('duplicate id #a&b',output)


if __name__=='__main__':
    unittest.main()
