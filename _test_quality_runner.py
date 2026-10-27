"""The quality runner schedules checks concurrently without changing results.

Covers the 2026-10-16 build speed-up: read-only CHECK_STEPS run in a bounded
pool with output printed in list order, SERIAL_CHECK_STEPS act as barriers,
the first failure in list order decides the exit code, and the twice-run
normalizers skip only text the same build already proved unchanged.
"""
from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _normalize_css_links as css
import _normalize_heading_structure as heading
import _regen_fixed_points as fixed
import _run_quality as quality

PY = sys.executable


def step(code: str) -> list[str]:
    return [PY, "-c", code]


def wait_for(path: Path) -> str:
    return (f"import pathlib,sys,time\np=pathlib.Path({str(path)!r})\n"
            "end=time.time()+60\n"
            "while not p.exists():\n"
            "    if time.time()>end: sys.exit(3)\n"
            "    time.sleep(0.02)\n")


class ParallelChecksTests(unittest.TestCase):
    def run_checks(self, steps, jobs="4", serial=()):
        out = io.StringIO()
        with patch.dict(os.environ, {"DN_QUALITY_JOBS": jobs}), \
                patch.object(quality, "SERIAL_CHECK_STEPS", [list(command) for command in serial]), \
                contextlib.redirect_stdout(out):
            try:
                quality.run_steps("Run quality checks", steps, parallel=True)
            except subprocess.CalledProcessError as exc:
                return out.getvalue(), exc
        return out.getvalue(), None

    def test_checks_overlap_and_output_keeps_list_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "second-started"
            # The first check can only finish once the second one has run,
            # so this passes only when they really run at the same time.
            first = step(wait_for(marker) + "print('first done')")
            second = step(f"import pathlib;pathlib.Path({str(marker)!r}).write_text('x');print('second done')")
            output, error = self.run_checks([first, second])
        self.assertIsNone(error)
        self.assertTrue(output.replace("\r\n", "\n").endswith(
            f"+ {quality.label(first)}\nfirst done\n+ {quality.label(second)}\nsecond done\n"), output)

    def test_first_failure_in_list_order_decides_the_exit_code(self):
        slow_failure = step("import sys,time;time.sleep(0.5);print('slow');sys.exit(5)")
        fast_failure = step("import sys;print('fast');sys.exit(9)")
        output, error = self.run_checks([slow_failure, fast_failure, step("print('later')")])
        self.assertIsInstance(error, subprocess.CalledProcessError)
        self.assertEqual((error.returncode, error.cmd), (5, slow_failure))
        self.assertIn("slow", output)
        self.assertNotIn("fast", output)
        self.assertNotIn("later", output)

    def test_main_reports_the_same_fail_line_and_exit_code(self):
        failing = step("import sys;sys.exit(6)")
        out = io.StringIO()
        with patch.object(quality, "CHECK_STEPS", [step("pass"), failing, step("pass")]), \
                patch.dict(os.environ, {"DN_QUALITY_JOBS": "3"}), contextlib.redirect_stdout(out):
            self.assertEqual(quality.main(["check"]), 6)
        self.assertIn(f"[FAIL] {quality.label(failing)} exited with 6", out.getvalue())

    def test_serial_check_is_a_barrier_in_its_original_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = step(f"import pathlib,time;time.sleep(0.4);pathlib.Path({str(root / 'a')!r}).write_text('a')")
            serial = step(f"import pathlib,sys;r=pathlib.Path({str(root)!r})\n"
                          "sys.exit(0 if (r/'a').exists() and not (r/'b').exists() else 4)\n"
                          "")
            mark = step(f"import pathlib;pathlib.Path({str(root / 's')!r}).write_text('s')")
            after = step(f"import pathlib,sys;r=pathlib.Path({str(root)!r})\n"
                         "ok=(r/'s').exists();(r/'b').write_text('b');sys.exit(0 if ok else 4)")
            output, error = self.run_checks([before, serial, mark, after], serial=[serial, mark])
        self.assertIsNone(error, output)

    def test_no_check_starts_after_an_earlier_failure_at_a_barrier(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "ran"
            barrier = step(f"import pathlib;pathlib.Path({str(marker)!r}).write_text('x')")
            later = step(f"import pathlib;pathlib.Path({str(marker)!r}).write_text('y')")
            output, error = self.run_checks([step("import sys;sys.exit(2)"), barrier, later], serial=[barrier])
            self.assertEqual(error.returncode, 2)
            self.assertFalse(marker.exists())

    def test_single_job_keeps_the_original_serial_runner(self):
        with patch.dict(os.environ, {"DN_QUALITY_JOBS": "1"}), \
                patch.object(quality.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            quality.run_steps("Run quality checks", [["a"], ["b"]], parallel=True)
        self.assertEqual([call.args for call in run.call_args_list], [(["a"],), (["b"],)])
        self.assertEqual([call.kwargs for call in run.call_args_list], [{"check": True}] * 2)

    def test_job_count_is_bounded_and_validated(self):
        with patch.dict(os.environ, {"DN_QUALITY_JOBS": ""}):
            self.assertTrue(1 <= quality.check_jobs() <= 4)
        for raw in ("0", "-1", "two"):
            with self.subTest(raw=raw), patch.dict(os.environ, {"DN_QUALITY_JOBS": raw}), \
                    self.assertRaises(ValueError):
                quality.check_jobs()

    def test_only_quality_checks_run_concurrently(self):
        with patch.object(quality, "run_steps") as runner, \
                patch("_cms_patient_review.frozen_content_date", return_value=None):
            self.assertEqual(quality.main(["build"]), 0)
            self.assertEqual([call.kwargs.get("parallel", False) for call in runner.call_args_list],
                             [False, False, True, False])
            runner.reset_mock()
            self.assertEqual(quality.main(["check"]), 0)
            self.assertEqual(runner.call_args_list[0].kwargs, {"parallel": True})

    def test_deploy_builds_only_the_uncommitted_search_index(self):
        # Vercel serves the CI-verified checkout; only the gitignored Pagefind
        # index is produced there, with no regeneration and no repeated checks.
        self.assertEqual(quality.DEPLOY_STEPS, [[quality.PY, "_run_pagefind.py"]])
        with patch.object(quality, "run_steps") as runner:
            self.assertEqual(quality.main(["deploy"]), 0)
        self.assertEqual([call.args[1] for call in runner.call_args_list], [quality.DEPLOY_STEPS])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            quality.main(["deploy", "--content-date", "2026-10-27"])

    def test_serial_classification_names_real_checks(self):
        for command in quality.SERIAL_CHECK_STEPS:
            self.assertIn(command, quality.CHECK_STEPS)


class FixedPointTests(unittest.TestCase):
    PAGES = {
        "a.html": '<html><head><link rel="preload" as="style" href="/assets/tw-mini.css" '
                  'onload="this.onload=null;this.rel=\'stylesheet\'"></head><body><article><h1>T</h1>'
                  '<h4 id="x">H</h4></article></body></html>\n',
        "b.html": '<html><head></head><body><p>stable</p></body></html>\n',
    }

    def build_tree(self, root: Path) -> None:
        for name, text in self.PAGES.items():
            (root / name).write_text(text, encoding="utf-8")

    def run_normalizers(self, root: Path, state: str | None) -> dict[str, bytes]:
        env = {fixed.ENV: state} if state else {}
        files = lambda: sorted(root.glob("*.html"))
        with patch.dict(os.environ, env), patch.object(heading, "ROOT", root), \
                patch.object(heading, "iter_html_files", files), patch.object(css, "ROOT", str(root)), \
                patch.object(css, "html_files", lambda: [str(path) for path in files()]), \
                contextlib.redirect_stdout(io.StringIO()):
            if state is None:
                os.environ.pop(fixed.ENV, None)
            for _ in range(2):
                css.main()
                heading.main()
                # A generator between the passes rewrites one page.
                (root / "c.html").write_text(self.PAGES["a.html"], encoding="utf-8")
        return {path.name: path.read_bytes() for path in sorted(root.iterdir())}

    def test_skipping_proven_text_gives_byte_identical_results(self):
        with tempfile.TemporaryDirectory() as plain, tempfile.TemporaryDirectory() as skipped, \
                tempfile.TemporaryDirectory() as state:
            self.build_tree(Path(plain))
            self.build_tree(Path(skipped))
            self.assertEqual(self.run_normalizers(Path(plain), None),
                             self.run_normalizers(Path(skipped), state))

    def test_only_unchanged_text_is_recorded_and_changed_text_is_reprocessed(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as state:
            root = Path(tmp)
            self.build_tree(root)
            with patch.dict(os.environ, {fixed.ENV: state}):
                points = fixed.FixedPoints("_normalize_css_links", root)
                self.assertTrue(css.normalize_file(str(root / "a.html"), points))
                self.assertFalse(css.normalize_file(str(root / "b.html"), points))
                points.save()
                again = fixed.FixedPoints("_normalize_css_links", root)
            self.assertEqual(set(again.known), {"b.html"})
            text = (root / "b.html").read_text(encoding="utf-8")
            self.assertTrue(again.unchanged_since_proven(root / "b.html", text))
            self.assertFalse(again.unchanged_since_proven(root / "b.html", text + " "))
            self.assertFalse(again.unchanged_since_proven(root / "a.html",
                                                          (root / "a.html").read_text(encoding="utf-8")))

    def test_without_the_build_scope_every_file_is_processed(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(fixed.ENV, None)
            points = fixed.FixedPoints("_normalize_heading_structure", Path.cwd())
            points.record_unchanged(Path.cwd() / "x.html", "text")
            self.assertFalse(points.enabled)
            self.assertFalse(points.unchanged_since_proven(Path.cwd() / "x.html", "text"))
            points.save()

    def test_build_scope_is_private_and_removed_after_regeneration(self):
        os.environ.pop(fixed.ENV, None)
        with quality.fixed_point_scope():
            directory = Path(os.environ[fixed.ENV])
            self.assertTrue(directory.is_dir())
            self.assertFalse(directory.resolve().is_relative_to(Path(quality.__file__).resolve().parent))
        self.assertNotIn(fixed.ENV, os.environ)
        self.assertFalse(directory.exists())


if __name__ == "__main__":
    unittest.main()
