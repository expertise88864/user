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

    def test_image_metadata_and_quoted_examples_are_not_intrinsic_dimensions(self):
        for attrs in ['data-width="640" data-height="480"', 'title="width=640 height=480"',
                      'width="640" data-height="480"']:
            with self.subTest(attrs=attrs):
                code,output=self.check('<img src="fixture.png" alt="Fixture" '+attrs+'>')
                self.assertEqual(code,1)
                self.assertIn('image missing width/height',output)

    def test_real_single_quoted_unquoted_and_uppercase_image_dimensions_pass(self):
        for attrs in ['width=640 height=480', "width='640' height='480'", 'WIDTH="640" HEIGHT="480"']:
            with self.subTest(attrs=attrs):
                code,output=self.check('<img src="fixture.png" alt="Fixture" '+attrs+'>')
                self.assertEqual(code,0,output)

    def test_single_unquoted_and_entity_decoded_duplicate_ids_also_fail(self):
        code,output=self.check('<h2 id=overview>Overview</h2><aside ID=\'overview\'></aside>'
                               '<div id="a&amp;b"></div><div id=\'a&b\'></div>')
        self.assertEqual(code,1)
        self.assertIn('duplicate id #overview',output)
        self.assertIn('duplicate id #a&b',output)


class AccessibilityPublishedScopeTests(unittest.TestCase):
    def test_exact_root_private_evidence_does_not_fail_public_accessibility(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'index.html').write_text('<html><body><h1>Fixture</h1><input aria-label="Public field"></body></html>',encoding='utf8')
            for name in ['.codex-review','.claude-review','.lighthouseci','delivery-preview']:
                p=root/name/'harness.html';p.parent.mkdir();p.write_text('<select id="unpublished-harness"></select>',encoding='utf8')
            with patch.object(audit,'ROOT',root),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(audit.main(),0)
                self.assertEqual([p.relative_to(root).as_posix() for p in audit.iter_html_files()],['index.html'])

    def test_missing_accessible_name_on_actual_public_control_still_fails(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'index.html').write_text('<h1>Fixture</h1><select id="public-choice"></select>',encoding='utf8')
            output=io.StringIO()
            with patch.object(audit,'ROOT',root),contextlib.redirect_stdout(output):
                self.assertEqual(audit.main(),1)
            self.assertIn('index.html: form control has no accessible name',output.getvalue())

    def test_similar_or_nested_evidence_directory_names_stay_audited(self):
        for name in ['.codex-review-public/guide.html','blog/.codex-review/guide.html','blog/delivery-preview/guide.html']:
            with self.subTest(name=name),TemporaryDirectory() as directory:
                root=Path(directory)
                p=root/name;p.parent.mkdir(parents=True);p.write_text('<h1>Fixture</h1><select id="public-choice"></select>',encoding='utf8')
                output=io.StringIO()
                with patch.object(audit,'ROOT',root),contextlib.redirect_stdout(output):
                    self.assertEqual(audit.main(),1)
                self.assertIn(name+': form control has no accessible name',output.getvalue())


if __name__=='__main__':
    unittest.main()
