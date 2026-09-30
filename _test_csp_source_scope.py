"""Local audit reports must not add executable bodies to the deployed CSP."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import _gen_csp_hashes as generator
import _check_deployment as checker


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


if __name__ == "__main__":
    unittest.main()
