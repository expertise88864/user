"""Local audit reports must not add executable bodies to the deployed CSP."""
from pathlib import Path
import base64
import contextlib
import hashlib
import io
import tempfile
import unittest
from unittest.mock import patch

import _gen_csp_hashes as generator
import _check_deployment as checker
import _check_inline_events as events
import _html_scan as scanner


class CspSourceScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Retain the real checker floors; build a sufficient public fixture set.
        self.public = ["index.html", "blog/article.html", "admin.html", "en/blog/article.html"]
        self.public += [f"fixture-{i}.html" for i in range(96)]
        for i, name in enumerate(self.public):
            self.write(name, f"<script>window.fixture = {i};</script>")
        self.gen_root = patch.object(generator, "ROOT", self.root)
        self.check_root = patch.object(checker, "ROOT", self.root)
        self.gen_root.start()
        self.check_root.start()
        self.addCleanup(self.gen_root.stop)
        self.addCleanup(self.check_root.stop)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def add_reports(self):
        for directory in [".codex-review", ".claude-review", ".lighthouseci", "delivery-preview"]:
            self.write(f"{directory}/nested/report.html", "<script>window.auditOnly = true;</script>")

    def config(self):
        per_file, _, _, refusals = generator.collect_hashes()
        self.assertEqual(refusals, [])
        hashes = sorted(set().union(*per_file.values()))
        return {"headers": [{"source": "/(.*)", "headers": [{
            "key": "Content-Security-Policy", "value": "script-src 'self' " + " ".join(hashes),
        }]}]}

    def test_reports_do_not_change_generated_hashes(self):
        before = generator.collect_hashes()
        self.add_reports()
        self.assertEqual(generator.collect_hashes(), before)
        self.assertEqual(set(before[0]), set(self.public))
        self.assertEqual(before[1:3], (100, 100))

    def test_only_exact_top_level_audit_directories_are_excluded(self):
        self.add_reports()
        included = ["blog/.lighthouseci/report.html", ".codex-review-other/report.html"]
        for i, name in enumerate(included):
            self.write(name, f"<script>window.other = {i};</script>")
        self.assertEqual(set(generator.collect_hashes()[0]), set(self.public + included))

    def test_checker_still_rejects_a_missing_public_script_hash(self):
        config = self.config()
        self.add_reports()
        errors = []
        checker.check_inline_script_hashes(errors, config)
        self.assertEqual(errors, [])
        self.write("blog/article.html", "<script>window.newPublicBody = true;</script>")
        checker.check_inline_script_hashes(errors, config)
        self.assertTrue(any("missing" in error and "blog/article.html" in error for error in errors), errors)

    def test_attribute_examples_never_authorize_inline_script_bodies(self):
        self.write('index.html', '<div data-en="<script>example()</script>"></div>'
                   '<script>window.real = true;</script>')
        hashes, _, _, refusals = generator.collect_hashes()
        digest = base64.b64encode(hashlib.sha256(b'window.real = true;').digest()).decode()
        self.assertEqual(hashes['index.html'], {"'sha256-" + digest + "'"})
        self.assertEqual(refusals, [])

    def test_event_audit_cannot_hide_handlers_after_attribute_examples(self):
        # Keep the actual coverage floors instead of making an undersized fixture pass.
        for name in self.public:
            self.write(name, '<main>' + '<p>Fixture</p>' * 30 + '</main>')
        self.write('index.html', '<div data-en="<script>"></div>\n'
                   '<button onclick="unsafe()">Test</button><script>real()</script>')
        output = io.StringIO()
        with patch.object(events, 'ROOT', self.root), contextlib.redirect_stdout(output):
            result = events.main()
        self.assertEqual(result, 1)
        self.assertIn('index.html:2: inline event handler onclick', output.getvalue())
        self.assertNotIn('discovery or tag parsing is broken', output.getvalue())

    def test_raw_text_and_unicode_keep_exact_body_and_source_offsets(self):
        cases = [
            ('<p>\u0130</p><script>real()</script>', 'real()'),
            ('<script data-label="before > </script>">real()</script>', 'real()'),
            ('<style>.example::after{content:"<script>fake()</script>"}</style>'
             '<script>real()</script>', 'real()'),
            ('<textarea data-label="> </textarea>"><script>example()</script></textarea>'
             '<script>real()</script>', 'real()'),
            ('<div data-en="<textarea>"></div><script>real()</script>', 'real()'),
            ('<script>var text="<!-- <textarea>example</textarea> -->"; real()</script>',
             'var text="<!-- <textarea>example</textarea> -->"; real()'),
        ]
        for markup, expected in cases:
            with self.subTest(markup=markup):
                self.assertEqual([body for _, body in scanner.iter_inline_scripts(markup)], [expected])
        markup = '<p>\u0130</p>\n<script data-label="before > </script>">body()</script>\n<button onclick="test()">Keep</button>'
        blanked = scanner.blank_script_style(markup)
        self.assertEqual(len(blanked), len(markup))
        self.assertEqual([i for i, c in enumerate(blanked) if c == '\n'],
                         [i for i, c in enumerate(markup) if c == '\n'])
        self.assertNotIn('body()', blanked)
        self.assertIn('<button onclick="test()">Keep</button>', blanked)

    def test_raw_text_names_require_html_tag_delimiters(self):
        for name in ('script', 'style', 'textarea', 'title'):
            for suffix in ('!', '?', '=', '@'):
                with self.subTest(name=name, suffix=suffix):
                    markup = (f'<{name}{suffix}>Example</{name}{suffix}>'
                              '<button onclick="test()">Keep</button>'
                              '<script>real()</script>')
                    self.assertEqual(list(scanner.iter_inline_scripts(markup)), [({}, 'real()')])
                    self.assertIn('<button onclick="test()">Keep</button>',
                                  scanner.blank_script_style(markup))
                    self.assertEqual(scanner.mask_inert_regions(markup), markup)

    def test_stray_quotes_do_not_hide_later_scripts_or_rcdata(self):
        prefixes = ["<img alt=Patient's src=/a.png>", "<p data-x=a='b>",
                    "x <y it's</p>", "<!example '", "<?example '", "</?example '"]
        for prefix in prefixes:
            if not prefix.endswith('>'):
                prefix += '>'
            with self.subTest(prefix=prefix):
                markup = prefix + '<textarea><button onclick="example()">Text</textarea>'
                markup += '<script>run()</script><button onclick="real()">Keep</button>'
                self.assertEqual(list(scanner.iter_inline_scripts(markup)), [({}, 'run()')])
                self.assertNotIn('run()', scanner.blank_script_style(markup))
                self.assertNotIn('example()', scanner.mask_inert_regions(markup))
                self.assertIn('real()', scanner.blank_script_style(markup))
                self.write('index.html', markup)
                hashes, _, _, refusals = generator.collect_hashes()
                digest = base64.b64encode(hashlib.sha256(b'run()').digest()).decode()
                self.assertEqual(hashes['index.html'], {"'sha256-" + digest + "'"})
                self.assertEqual(refusals, [])

    def test_tag_boundary_matches_browser_attribute_states(self):
        cases = [
            '<img alt=Patient\'s src=/a.png>',
            '<p data-x=a=\'b>',
            '<p data-x /=\'b>',
            '<p data-x="a > b" data-y=\'c > d\'>',
            '<p data-x = "a > b" data-y =\'c > d\'>',
            '<p data-x="a"data-y=\'c > d\'>',
        ]
        for tag in cases:
            with self.subTest(tag=tag):
                self.assertEqual(list(scanner.iter_tags(tag + '<button>Keep</button>')),
                                 [(0, tag), (len(tag), '<button>'),
                                  (len(tag) + len('<button>Keep'), '</button>')])

    def test_browser_comment_closures_do_not_hide_live_scripts(self):
        for comment in ('<!-- x -->', '<!-- x --!>', '<!-->', '<!--->'):
            with self.subTest(comment=comment):
                markup = comment + '<script>run()</script><!-- remaining -->'
                self.assertEqual(list(scanner.iter_inline_scripts(markup)), [({}, 'run()')])
                masked = scanner.mask_comments(markup)
                self.assertIn('<script>run()</script>', masked)
                self.assertEqual(len(masked), len(markup))
                self.assertEqual(masked[:len(comment)], ' ' * len(comment))


if __name__ == "__main__":
    unittest.main()
