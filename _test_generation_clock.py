"""A frozen content clock makes new-article metadata reproducible across days."""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import _normalize_date_modified as normalizer
import _run_quality as quality
from _check_deployment import check_content_date_order


def article(text: str = "這是純格式測試文字，沒有醫療建議。" * 40) -> str:
    return ('<html><head><script type="application/ld+json">'
            '{"@type":"Article","dateModified":"2026-01-01"}</script>'
            '<meta property="article:modified_time" content="2026-01-01T00:00:00+08:00">'
            '</head><body><h1>合成格式測試</h1><article><div id="proseZh"><p>'
            + text + '</p></div></article></body></html>')


class GenerationClockTests(unittest.TestCase):
    @contextlib.contextmanager
    def fixture(self, source: str | None = None, ledger: dict | None = None):
        with TemporaryDirectory(prefix="chendermatologist-clock-test-") as folder:
            root = Path(folder)
            blog = root / "blog"
            en_blog = root / "en" / "blog"
            blog.mkdir()
            en_blog.mkdir(parents=True)
            text = source if source is not None else article()
            (blog / "fixture.html").write_text(text, encoding="utf-8")
            (en_blog / "fixture.html").write_text(text, encoding="utf-8")
            content_dates = root / "_content_dates.json"
            content_dates.write_text(json.dumps(ledger or {}) + "\n", encoding="utf-8")
            with patch.multiple(normalizer, ROOT=root, BLOG=blog,
                                EN_BLOG=en_blog, CONTENT_DATES=content_dates):
                yield root

    def generate(self, root: Path, *, clock: str, frozen: str | None = None):
        class Clock(date):
            @classmethod
            def today(cls):
                return date.fromisoformat(clock)

        with patch.object(normalizer, "date", Clock), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(normalizer.main(content_date=frozen), 0)
        return {path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*") if path.is_file()}

    def test_frozen_clock_reproduces_complete_output_on_different_days(self):
        self.assertIsNotNone(normalizer.prose_hash(article()))
        with self.fixture() as root:
            first = self.generate(root, clock="2026-10-02", frozen="2026-09-30")
        with self.fixture() as root:
            second = self.generate(root, clock="2026-10-03", frozen="2026-09-30")
        self.assertEqual(first, second)
        for path in ("blog/fixture.html", "en/blog/fixture.html"):
            self.assertIn(b'"dateModified":"2026-09-30"', first[path])
            self.assertIn(b"2026-09-30T00:00:00+08:00", first[path])
        self.assertEqual(json.loads(first["_content_dates.json"])["fixture"]["date"], "2026-09-30")

    def test_default_clock_retains_existing_daily_behavior(self):
        with self.fixture() as root:
            first = self.generate(root, clock="2026-10-02")
        with self.fixture() as root:
            second = self.generate(root, clock="2026-10-03")
        self.assertNotEqual(first, second)
        self.assertEqual(json.loads(second["_content_dates.json"])["fixture"]["date"], "2026-10-03")

    def test_main_without_arguments_remains_supported(self):
        with self.fixture() as root, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(normalizer.main(), 0)
            ledger = json.loads((root / "_content_dates.json").read_bytes())
            self.assertEqual(ledger["fixture"]["date"], date.today().isoformat())

    def test_matching_prose_keeps_prior_ledger_date_and_raw_ledger(self):
        ledger = {"fixture": {"hash": normalizer.prose_hash(article()), "date": "2026-02-03"}}
        with self.fixture(ledger=ledger) as root:
            raw_before = (root / "_content_dates.json").read_bytes()
            result = self.generate(root, clock="2026-10-03", frozen="2026-09-30")
        self.assertEqual(result["_content_dates.json"], raw_before)
        self.assertIn(b'"dateModified":"2026-02-03"', result["blog/fixture.html"])

    def test_changed_prose_uses_selected_date_without_altering_text(self):
        ledger = {"fixture": {"hash": normalizer.prose_hash(article()), "date": "2026-02-03"}}
        updated = article("這是修改後的純格式測試文字，沒有醫療建議。" * 40)
        with self.fixture(source=updated, ledger=ledger) as root:
            result = self.generate(root, clock="2026-10-03", frozen="2026-09-30")
        self.assertEqual(normalizer.article_prose(result["blog/fixture.html"].decode("utf-8")),
                         normalizer.article_prose(updated))
        self.assertEqual(json.loads(result["_content_dates.json"])["fixture"],
                         {"hash": normalizer.prose_hash(updated), "date": "2026-09-30"})

    def test_short_prose_git_fallback_precedes_selected_clock(self):
        with self.fixture(source=article("格式測試")) as root, \
                patch.object(normalizer, "git_last_modified", return_value="2026-02-03"):
            result = self.generate(root, clock="2026-10-03", frozen="2026-09-30")
        self.assertIn(b'"dateModified":"2026-02-03"', result["blog/fixture.html"])
        self.assertEqual(json.loads(result["_content_dates.json"]), {})

    def test_short_prose_without_git_uses_selected_clock(self):
        with self.fixture(source=article("格式測試")) as root, \
                patch.object(normalizer, "git_last_modified", return_value=None):
            result = self.generate(root, clock="2026-10-03", frozen="2026-09-30")
        self.assertIn(b'"dateModified":"2026-09-30"', result["blog/fixture.html"])
        self.assertEqual(json.loads(result["_content_dates.json"]), {})

    def test_strict_calendar_date_validation(self):
        self.assertEqual(normalizer.content_date_argument("2024-02-29"), "2024-02-29")
        for invalid in ("20261002", "2026-W40-5", "2026-2-03", "2026-02-29", "0000-01-01",
                        "2026-13-01", "2026-10-02T12:00:00", " 2026-10-02", "2026-10-02\n",
                        "２０２６-１０-０２", "", True, 20261002):
            with self.subTest(value=invalid), self.assertRaises(argparse.ArgumentTypeError):
                normalizer.content_date_argument(invalid)

    def test_invalid_direct_argument_does_not_touch_files(self):
        with self.fixture() as root:
            before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            with self.assertRaises(argparse.ArgumentTypeError):
                normalizer.main(content_date="2026-02-29")
            self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_real_normalizer_cli_in_disposable_tree(self):
        source_root = Path(__file__).resolve().parent
        with self.fixture() as root:
            for name in ("_normalize_date_modified.py", "_normalize_reading_shell.py", "_html_scan.py"):
                (root / name).write_bytes((source_root / name).read_bytes())
            result = subprocess.run([sys.executable, str(root / "_normalize_date_modified.py"),
                                     "--content-date", "2026-09-30"], cwd=root,
                                    capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((root / "_content_dates.json").read_bytes())
                             ["fixture"]["date"], "2026-09-30")
            before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            invalid = subprocess.run([sys.executable, str(root / "_normalize_date_modified.py"),
                                      "--content-date", "2026-02-29"], cwd=root,
                                     capture_output=True, timeout=30)
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_quality_forwarding_preserves_command_order_and_shared_recipe(self):
        recipe = copy.deepcopy(quality.REGEN_STEPS)
        generated = quality.regeneration_steps("2026-09-30")
        self.assertEqual(quality.REGEN_STEPS, recipe)
        self.assertEqual(len(generated), len(recipe))
        changed = [(old, new) for old, new in zip(recipe, generated) if old != new]
        self.assertEqual(changed, [([quality.PY, "_normalize_date_modified.py"],
                                   [quality.PY, "_normalize_date_modified.py", "--content-date", "2026-09-30"])])
        self.assertEqual(quality.regeneration_steps(), recipe)

    def test_missing_or_ambiguous_clock_step_fails_closed(self):
        for recipe in ([], [[quality.PY, "_normalize_date_modified.py"]] * 2):
            with patch.object(quality, "REGEN_STEPS", recipe), self.assertRaises(ValueError):
                quality.regeneration_steps("2026-09-30")

    def test_quality_cli_runs_complete_selected_mode_with_date_forwarded(self):
        for args, expected in ((["regen", "--content-date", "2026-09-30"], 1),
                               (["build", "--content-date", "2026-09-30"], 4),
                               (["--content-date", "2026-09-30"], 4)):
            with self.subTest(args=args), patch.object(quality, "run_steps") as runner:
                self.assertEqual(quality.main(args), 0)
                self.assertEqual(runner.call_count, expected)
                self.assertEqual(runner.call_args_list[0].args[1], quality.regeneration_steps("2026-09-30"))
                if expected == 4:
                    self.assertEqual([call.args[1] for call in runner.call_args_list[1:]],
                                     [quality.BUILD_GENERATED_STEPS, quality.CHECK_STEPS, quality.POST_BUILD_STEPS])

    def test_quality_check_rejects_clock_invalid_dates_and_unknown_arguments(self):
        for args in (["check", "--content-date", "2026-09-30"], ["build", "--content-date", "2026-02-29"],
                     ["unknown"], ["build", "--unused"]):
            with self.subTest(args=args), patch.object(quality, "run_steps") as runner, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                quality.main(args)
            self.assertEqual(error.exception.code, 2)
            runner.assert_not_called()

    def test_quality_defaults_and_failure_exit_codes_unchanged(self):
        with patch.object(quality, "run_steps") as runner:
            self.assertEqual(quality.main([]), 0)
            self.assertEqual([call.args[1] for call in runner.call_args_list],
                             [quality.REGEN_STEPS, quality.BUILD_GENERATED_STEPS,
                              quality.CHECK_STEPS, quality.POST_BUILD_STEPS])
        with patch.object(quality, "run_steps", side_effect=subprocess.CalledProcessError(7, ["fixture"])), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(quality.main(["check"]), 7)

    def recipe_source(self, scripts):
        return 'REGEN_STEPS = ' + repr([["python", script] for script in scripts]).replace("'python'", "PY")

    def test_deployment_audit_reads_recipe_not_helper_strings(self):
        source = self.recipe_source(["_normalize_date_modified.py", "_gen_en_pages.py",
                                     "_gen_feeds.py", "_gen_llms_full.py"])
        source += '\ntarget = [PY, "_normalize_date_modified.py"]\n'
        self.assertEqual(check_content_date_order(source), [])
        self.assertEqual(check_content_date_order(Path(quality.__file__).read_text(encoding="utf-8")), [])

    def test_deployment_audit_still_rejects_missing_and_duplicate_actual_steps(self):
        dependencies = ["_gen_en_pages.py", "_gen_feeds.py", "_gen_llms_full.py"]
        for scripts in (dependencies, ["_normalize_date_modified.py"] * 2 + dependencies):
            source = self.recipe_source(scripts) + '\nfake = [PY, "_normalize_date_modified.py"]\n'
            self.assertTrue(check_content_date_order(source))

    def test_deployment_audit_still_rejects_each_reordered_or_missing_dependency(self):
        dependencies = ["_gen_en_pages.py", "_gen_feeds.py", "_gen_llms_full.py"]
        for dependent in dependencies:
            with self.subTest(dependent=dependent):
                others = [script for script in dependencies if script != dependent]
                reordered = self.recipe_source([dependent, "_normalize_date_modified.py"] + others)
                missing = self.recipe_source(["_normalize_date_modified.py"] + others)
                self.assertTrue(check_content_date_order(reordered))
                self.assertTrue(check_content_date_order(missing))

    def test_deployment_audit_rejects_ambiguous_or_computed_recipes_without_execution(self):
        for source in ('broken syntax!', 'REGEN_STEPS = make_recipe()', 'REGEN_STEPS = [[PY, script]]',
                       'REGEN_STEPS = []\nREGEN_STEPS = []', 'REGEN_STEPS += []', 'no_recipe = []'):
            with self.subTest(source=source):
                self.assertTrue(check_content_date_order(source))

    def test_deployment_audit_supports_the_annotated_literal_recipe(self):
        source = self.recipe_source(["_normalize_date_modified.py", "_gen_en_pages.py",
                                     "_gen_feeds.py", "_gen_llms_full.py"])
        source = source.replace('REGEN_STEPS =', 'REGEN_STEPS: list[list[str]] =')
        self.assertEqual(check_content_date_order(source), [])

    def test_deployment_audit_rejects_wrong_executable_or_unreviewed_arguments(self):
        source = self.recipe_source(["_normalize_date_modified.py", "_gen_en_pages.py",
                                     "_gen_feeds.py", "_gen_llms_full.py"])
        for bad in (source.replace("[PY, '_normalize_date_modified.py']", "['echo', '_normalize_date_modified.py']"),
                    source.replace("[PY, '_gen_en_pages.py']", "[OTHER, '_gen_en_pages.py']"),
                    source.replace("[PY, '_normalize_date_modified.py']", "[PY, '_normalize_date_modified.py', '--unknown']")):
            self.assertTrue(check_content_date_order(bad))


if __name__ == "__main__":
    unittest.main()
