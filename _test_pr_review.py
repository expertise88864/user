"""tools/pr_review.py: whole-PR review bookkeeping (user decision 2026-10-15).

Offline; no GitHub or Codex calls. Run by the Delivery contract job."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("pr_review", ROOT / "tools" / "pr_review.py")
pr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pr)

SHA = "a" * 40
SESSION_ID = "0123abcd-0000-4000-8000-000000000000"


class FakeAPI:
    repo = "owner/repo"

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def call(self, method, path, body=None):
        self.calls.append(path)
        return self.routes(path)


class QuotaClassificationTests(unittest.TestCase):
    def test_reviewed_content_mentioning_quota_is_not_a_quota_error(self):
        raw = "\n".join([
            json.dumps({"type": "item.completed", "item": {"type": "command_execution",
                        "aggregated_output": "+QUOTA = re.compile('usage limit|rate limit')"}}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message",
                        "text": "checking quota-pending handling"}}),
            "[codex-review] ERROR: rate limit text in a wrapper line is not provider evidence",
        ])
        self.assertFalse(pr.provider_quota_error(raw))

    def test_provider_error_events_are_quota(self):
        for raw in (json.dumps({"type": "error", "message": "You've hit your usage limit. Try again at 5pm"}),
                    json.dumps({"type": "turn.failed", "error": {"message": "rate limit exceeded"}}),
                    "ERROR: You've hit your usage limit."):
            with self.subTest(raw=raw):
                self.assertTrue(pr.provider_quota_error(raw))

    def test_other_provider_errors_are_not_quota(self):
        self.assertFalse(pr.provider_quota_error(json.dumps({"type": "error", "message": "stream disconnected"})))


class StaleRoundTests(unittest.TestCase):
    def test_wrapper_refusing_early_cannot_reuse_previous_quota_log(self):
        import subprocess
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / ".codex-review"
            state.mkdir()
            (state / "last_raw.log").write_text(json.dumps({"type": "error", "message": "usage limit"}),
                                                encoding="utf-8")
            (state / "last_message.txt").write_text("", encoding="utf-8")
            with patch.object(pr, "ROOT", Path(tmp)), patch.object(pr, "bash", return_value="bash"), \
                 patch.object(pr, "wrapper", return_value="tools/codex_review.sh"), \
                 patch.object(pr.subprocess, "run", return_value=subprocess.CompletedProcess([], 64)):
                verdict, _, _ = pr.run_review("targeted", "b" * 40, SHA, None, None)
            self.assertEqual(verdict, "ERROR")
            self.assertFalse((state / "last_raw.log").exists())


class RunReviewEvidenceTests(unittest.TestCase):
    """Quota-pending only for a run the wrapper reports as untrusted (exit 4)
    whose own, fresh output ends on a quota error."""
    QUOTA = json.dumps({"type": "error", "message": "You've hit your usage limit."})

    def run_attempt(self, rc, fresh_raw=None):
        import subprocess
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".codex-review"
            state.mkdir()
            # Leftovers of an earlier attempt that really hit quota.
            (state / "last_message.txt").write_text("", encoding="utf-8")
            (state / "last_raw.log").write_text(self.QUOTA, encoding="utf-8")

            def wrapper_run(*args, **kwargs):
                if fresh_raw is not None:
                    (state / "last_raw.log").write_text(fresh_raw, encoding="utf-8")
                return subprocess.CompletedProcess(args, rc)
            with patch.object(pr, "ROOT", Path(directory)), \
                 patch.object(pr, "bash", return_value="bash"), \
                 patch.object(pr, "wrapper", return_value="tools/codex_review.sh"), \
                 patch.object(pr.subprocess, "run", side_effect=wrapper_run):
                return pr.run_review("targeted", "b" * 40, SHA, None, None)[0]

    def test_wrapper_stopping_early_never_reuses_stale_quota_log(self):
        self.assertEqual(self.run_attempt(64), "ERROR")

    def test_untrusted_run_without_fresh_quota_evidence_is_error(self):
        self.assertEqual(self.run_attempt(4), "ERROR")
        self.assertEqual(self.run_attempt(5, fresh_raw=self.QUOTA), "ERROR")
        self.assertEqual(self.run_attempt(64, fresh_raw=self.QUOTA), "ERROR")

    def test_current_quota_failure_is_pending(self):
        self.assertEqual(self.run_attempt(4, fresh_raw=self.QUOTA), "QUOTA_PENDING")


class PendingAndBackfillTests(unittest.TestCase):
    def test_pending_reads_every_page(self):
        pages = {1: [{"n": i} for i in range(100)], 2: [{"n": i} for i in range(100)], 3: [{"n": 0}]}

        def routes(path):
            page = int(path.rsplit("page=", 1)[1])
            return pages[page]
        api = FakeAPI(routes)
        self.assertEqual(len(pr.all_prs(api)), 201)
        self.assertEqual(len(api.calls), 3)

    def test_backfill_reuses_newest_owner_reviewed_base(self):
        statuses = [
            {"id": 1, "context": pr.CONTEXT, "creator": {"login": "owner"},
             "description": f"REQUEST_CHANGES base={'b' * 40}"},
            {"id": 3, "context": pr.CONTEXT, "creator": {"login": "intruder"},
             "description": f"APPROVE base={'d' * 40}"},
            {"id": 2, "context": pr.CONTEXT, "creator": {"login": "Owner"},
             "description": f"quota-pending base={'c' * 40}"},
        ]
        self.assertEqual(pr.reviewed_base(FakeAPI(lambda path: statuses), SHA), "c" * 40)
        self.assertEqual(pr.reviewed_base(FakeAPI(lambda path: []), SHA), "")


class TerminalQuotaTests(unittest.TestCase):
    """PR #17 review round 1 (P1): only the terminal provider error decides quota-pending."""

    def test_recovered_rate_limit_then_other_failure_is_not_quota(self):
        for raw in ("\n".join([json.dumps({"type": "error", "message": "rate limit exceeded, retrying"}),
                               json.dumps({"type": "turn.failed", "error": {"message": "401 Unauthorized"}})]),
                    "ERROR: rate limit exceeded; retrying\nERROR: 401 Unauthorized"):
            with self.subTest(raw=raw):
                self.assertFalse(pr.provider_quota_error(raw))

    def test_recovered_rate_limit_then_crash_or_silence_is_not_quota(self):
        """PR #17 review round 2 (P1): quota-pending needs the run to END on a quota error."""
        recovered = "ERROR: rate limit exceeded; retrying"
        for tail in ("exec git diff --stat\nsucceeded in 120ms", "panic: failed to write final output",
                     json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}})):
            with self.subTest(tail=tail):
                self.assertFalse(pr.provider_quota_error(f"{recovered}\n{tail}\n[codex-review] ERROR: x"))

    def test_terminal_quota_after_other_error_is_quota(self):
        self.assertTrue(pr.provider_quota_error("ERROR: stream disconnected\nERROR: You've hit your usage limit."))


class ResumeScopeTests(unittest.TestCase):
    """PR #17 review round 1 (P2): a resume reviews every commit since the last verdict."""

    def test_resume_plan_is_incremental_for_a_descendant_and_full_after_a_rebase(self):
        import io
        import subprocess
        from unittest.mock import patch
        prev, head = "b" * 40, SHA
        for saved in ({}, {"head": "short"}, {"head": head}):
            with self.subTest(saved=saved), self.assertRaises(pr.Blocked):
                pr.resume_plan(saved, head)
        # Rebase: the last verdict's head left the history, so the whole range again.
        with patch.object(pr.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)), \
             patch("sys.stdout", io.StringIO()):
            self.assertEqual(pr.resume_plan({"head": prev}, head), ("full", prev))
        with patch.object(pr.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(pr.resume_plan({"head": prev}, head), ("incremental", prev))
        self.assertEqual(run.call_args.args[0][-2:], [prev, head])

    def test_previous_head_reaches_the_wrapper_only_on_resume(self):
        import os
        import subprocess
        import tempfile
        from unittest.mock import patch
        envs = []

        def fake_run(args, **kwargs):
            envs.append(kwargs["env"])
            return subprocess.CompletedProcess(args, 64)
        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {"CODEX_REVIEW_PREV_TIP": "c" * 40}), \
             patch.object(pr, "ROOT", Path(tmp)), patch.object(pr, "bash", return_value="bash"), \
             patch.object(pr, "wrapper", return_value="tools/codex_review.sh"), \
             patch.object(pr.subprocess, "run", side_effect=fake_run):
            pr.run_review("targeted", "b" * 40, SHA, None, None, "d" * 40)
            pr.run_review("targeted", "b" * 40, SHA, None, "0" * 8 + "-0000-0000-0000-" + "0" * 12, "d" * 40)
        self.assertNotIn("CODEX_REVIEW_PREV_TIP", envs[0])
        self.assertEqual(envs[1]["CODEX_REVIEW_PREV_TIP"], "d" * 40)
        self.assertNotIn("CODEX_REVIEW_FULL_RESUME", envs[1])

    def test_rebase_fallback_asks_the_wrapper_for_the_whole_range(self):
        import os
        import subprocess
        import tempfile
        from unittest.mock import patch
        envs = []

        def fake_run(args, **kwargs):
            envs.append(kwargs["env"])
            return subprocess.CompletedProcess(args, 64)
        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {"CODEX_REVIEW_FULL_RESUME": "c" * 40, "CODEX_REVIEW_PREV_TIP": "c" * 40}), \
             patch.object(pr, "ROOT", Path(tmp)), patch.object(pr, "bash", return_value="bash"), \
             patch.object(pr, "wrapper", return_value="tools/codex_review.sh"), \
             patch.object(pr.subprocess, "run", side_effect=fake_run):
            pr.run_review("targeted", "b" * 40, SHA, None, None)
            pr.run_review("targeted", "b" * 40, SHA, None, SESSION_ID, "d" * 40, scope="full")
        for name in ("CODEX_REVIEW_FULL_RESUME", "CODEX_REVIEW_PREV_TIP"):
            self.assertNotIn(name, envs[0])
        self.assertEqual(envs[1]["CODEX_REVIEW_FULL_RESUME"], "d" * 40)
        self.assertNotIn("CODEX_REVIEW_PREV_TIP", envs[1])

    def test_wrapper_widens_the_resume_scope_to_every_new_commit(self):
        text = (ROOT / "tools" / "codex_review.sh").read_text(encoding="utf-8")
        assert 'PREV_TIP="${CODEX_REVIEW_PREV_TIP:-}"' in text
        assert 'merge-base --is-ancestor "$PREV_TIP" "$TIP"' in text
        assert "Review EVERY change in {{PREV}}..{{TIP}}" in text
        assert 'FULL_FROM="${CODEX_REVIEW_FULL_RESUME:-}"' in text
        assert "Re-review the COMPLETE pull request range" in text
        main_src = (ROOT / "tools" / "pr_review.py").read_text(encoding="utf-8")
        assert '"head": head,' in main_src and "scope, previous_head = resume_plan(saved, head, bool(rebuttal))" in main_src

    def test_wrapper_resume_prompt_carries_verification_scope_and_ends_with_the_verdict(self):
        text = (ROOT / "tools" / "codex_review.sh").read_text(encoding="utf-8")
        resume = text.split('if [ "$MODE" = "resume" ]; then', 1)[1].split("# ================= 第一輪", 1)[0]
        order = [resume.index(marker) for marker in (
            'scope_section "$SCOPE_FROM" "$SCOPE_TO"', "LOCAL VERIFICATION (this pass)",
            "Implementer rebuttal:", "End with exactly APPROVE or REQUEST_CHANGES.")]
        self.assertEqual(order, sorted(order))
        self.assertIn("{{SCOPE}}", text.split("# ================= 第一輪", 1)[1])


class RetryingQuotaTests(unittest.TestCase):
    """PR #1 round 4 (P1): an interrupted retry is not terminal quota exhaustion."""

    def test_retrying_or_transient_rate_limit_last_is_not_quota(self):
        for raw in (json.dumps({"type": "error", "message": "rate limit exceeded, retrying"}),
                    json.dumps({"type": "error", "message": "rate limit exceeded"}),
                    json.dumps({"type": "turn.failed", "error": {"message": "usage limit; retrying in 5s"}}),
                    "ERROR: rate limit exceeded"):
            with self.subTest(raw=raw):
                self.assertFalse(pr.provider_quota_error(raw))


class RecordRetryTests(unittest.TestCase):
    """PR #1 round 4 (P2): a failed GitHub recording keeps the verdict for --retry-record."""

    def test_failed_recording_keeps_verdict_and_old_binding_then_retry_records(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            binding = Path(tmp) / "pr_review.json"
            unrecorded = Path(tmp) / "pr_review_unrecorded.json"
            binding.write_text(json.dumps({"head": "b" * 40}), encoding="utf-8")
            entry = {"repo": "owner/repo", "pr": 7, "verdict": "APPROVE", "base": "c" * 40, "head": SHA,
                     "session": "s", "bound_session": "s", "message": "APPROVE", "resume": True}
            unrecorded.write_text(json.dumps(entry), encoding="utf-8")
            api, pull = FakeAPI(lambda path: None), {"number": 7}
            with patch.object(pr, "record", side_effect=pr.Blocked("HTTP 502")), \
                 self.assertRaises(pr.Blocked):
                pr.finish(api, pull, entry, binding, unrecorded)
            self.assertEqual(json.loads(binding.read_text(encoding="utf-8"))["head"], "b" * 40)
            self.assertTrue(unrecorded.is_file())
            with patch.object(pr, "record") as record:
                self.assertEqual(pr.retry_record(api, pull, SHA, binding, unrecorded), 0)
            record.assert_called_once()
            self.assertEqual(json.loads(binding.read_text(encoding="utf-8"))["head"], SHA)
            self.assertFalse(unrecorded.exists())

    def test_retry_refuses_another_head_or_pr(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            unrecorded = Path(tmp) / "u.json"
            unrecorded.write_text(json.dumps({"repo": "owner/repo", "pr": 7, "head": SHA}), encoding="utf-8")
            for pull, head in (({"number": 8}, SHA), ({"number": 7}, "b" * 40)):
                with self.subTest(pull=pull, head=head), self.assertRaises(pr.Blocked):
                    pr.retry_record(FakeAPI(lambda path: None), pull, head, Path(tmp) / "b.json", unrecorded)


class RebuttalTests(unittest.TestCase):
    """User decision 2026-10-15: one evidence-based rebuttal per unchanged head."""

    def test_same_head_needs_rebuttal_of_request_changes_once(self):
        saved = {"head": SHA, "verdict": "REQUEST_CHANGES"}
        with self.assertRaises(pr.Blocked):
            pr.resume_plan(saved, SHA)
        self.assertEqual(pr.resume_plan(saved, SHA, rebuttal=True), ("rebuttal", None))
        for bad in ({**saved, "verdict": "APPROVE"}, {**saved, "rebutted_head": SHA}, {"head": SHA}):
            with self.subTest(saved=bad), self.assertRaises(pr.Blocked):
                pr.resume_plan(bad, SHA, rebuttal=True)

    def test_changed_head_cannot_be_rebutted_before_its_own_verdict(self):
        """PR #2 round 1 (P2): a rebuttal on a new head would skip eligibility and the once-only limit."""
        for saved in ({"head": "b" * 40, "verdict": "APPROVE"},
                      {"head": "b" * 40, "verdict": "REQUEST_CHANGES"}):
            with self.subTest(saved=saved), self.assertRaises(pr.Blocked):
                pr.resume_plan(saved, SHA, rebuttal=True)

    def test_rebuttal_reaches_the_wrapper_only_on_resume(self):
        import os
        import subprocess
        import tempfile
        from unittest.mock import patch
        envs = []

        def fake_run(args, **kwargs):
            envs.append(kwargs["env"])
            return subprocess.CompletedProcess(args, 64)
        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {"CODEX_REVIEW_REBUTTAL_FILE": "stale"}), \
             patch.object(pr, "ROOT", Path(tmp)), patch.object(pr, "bash", return_value="bash"), \
             patch.object(pr, "wrapper", return_value="tools/codex_review.sh"), \
             patch.object(pr.subprocess, "run", side_effect=fake_run):
            pr.run_review("targeted", "b" * 40, SHA, None, None, None, "r.txt")
            pr.run_review("targeted", "b" * 40, SHA, None, "0" * 8 + "-0000-0000-0000-" + "0" * 12, None, "r.txt")
        self.assertNotIn("CODEX_REVIEW_REBUTTAL_FILE", envs[0])
        self.assertEqual(envs[1]["CODEX_REVIEW_REBUTTAL_FILE"], "r.txt")
        self.assertNotIn("CODEX_REVIEW_PREV_TIP", envs[1])

    def test_finish_marks_a_same_head_rebuttal_so_it_cannot_repeat(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            binding, unrecorded = Path(tmp) / "b.json", Path(tmp) / "u.json"
            entry = {"repo": "owner/repo", "pr": 7, "verdict": "REQUEST_CHANGES", "base": "c" * 40, "head": SHA,
                     "session": "s", "bound_session": "s", "message": "", "resume": True,
                     "rebuttal": True, "same_head_rebuttal": True}
            with patch.object(pr, "record") as record:
                pr.finish(FakeAPI(lambda path: None), {"number": 7}, entry, binding, unrecorded)
            self.assertTrue(record.call_args.args[-2])
            saved = json.loads(binding.read_text(encoding="utf-8"))
            self.assertEqual((saved["verdict"], saved["rebutted_head"]), ("REQUEST_CHANGES", SHA))
            with self.assertRaises(pr.Blocked):
                pr.resume_plan(saved, SHA, rebuttal=True)

    def test_wrapper_passes_the_rebuttal_and_rejects_diffs(self):
        text = (ROOT / "tools" / "codex_review.sh").read_text(encoding="utf-8")
        assert 'REBUTTAL_FILE="${CODEX_REVIEW_REBUTTAL_FILE:-}"' in text
        assert "Never withdraw a finding on assertion alone" in text
        assert "rebuttal 檔看起來含 diff" in text


DIFF_SAMPLES = ("diff --git a/x.py b/x.py", "    diff --git a/x.py b/x.py", "\t@@ -1,2 +1,2 @@",
                "  index 1234abc..5678def 100644", "    --- a/x.py", "    +++ b/x.py")
EVIDENCE_SAMPLES = ("Finding 1 is REJECTED: _delivery.py:40 already checks the owner.",
                    "---", "See the delivery suite, test_y (line 12) -- it covers this path.")


class RebuttalDiffMarkerTests(unittest.TestCase):
    """Backport of the morning-report PR #18 fix (P2): indented diffs must not pass as rebuttal evidence."""

    def test_python_check_rejects_indented_diffs_and_keeps_evidence(self):
        for line in DIFF_SAMPLES:
            with self.subTest(line=line):
                self.assertTrue(pr.DIFF_MARKER.search(f"evidence\n{line}\nmore"))
        for line in EVIDENCE_SAMPLES:
            with self.subTest(line=line):
                self.assertIsNone(pr.DIFF_MARKER.search(line))

    def test_wrapper_check_rejects_indented_diffs_and_keeps_evidence(self):
        import re
        import shutil
        import subprocess
        import tempfile
        grep = shutil.which("grep")
        if not grep:
            self.skipTest("grep not available")
        text = (ROOT / "tools" / "codex_review.sh").read_text(encoding="utf-8")
        block = text.split('REBUTTAL_FILE="${CODEX_REVIEW_REBUTTAL_FILE:-}"', 1)[1]
        pattern = re.search(r"grep -qE '([^']+)' \"\$REBUTTAL_FILE\"", block).group(1)
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "rebuttal.txt"
            for line, expected in [(x, 0) for x in DIFF_SAMPLES] + [(x, 1) for x in EVIDENCE_SAMPLES]:
                sample.write_text(f"evidence\n{line}\n", encoding="utf-8")
                with self.subTest(line=line):
                    rc = subprocess.run([grep, "-qE", pattern, str(sample)]).returncode
                    self.assertEqual(rc, expected)


_scope_spec = importlib.util.spec_from_file_location("review_scope", ROOT / "tools" / "review_scope.py")
scope = importlib.util.module_from_spec(_scope_spec)
_scope_spec.loader.exec_module(scope)


class FakeTree:
    files = {"blog/acne-myths.html", "about.html"}
    bundles = {"blog-shared"}


class ReviewScopeTests(unittest.TestCase):
    """User decision 2026-10-15 (D-19): generated output is reviewed through its generator
    plus a sample; the canonical-generated-files CI job enforces the rest."""

    def test_only_files_every_build_rewrites_or_prunes_are_generated(self):
        generated = ("exam/fitz-1.html", "exam/exam-data.json", "admin/exam-preview.css",
                     "en/blog/acne-myths.html", "sitemap.xml", "blog/feed.xml", "llms-full.txt",
                     "ai/faq.json", ".well-known/ai.txt", "robots.txt", "blog/blog-shared.min.js")
        # Hand-written files, and generated-looking files no build would rewrite or delete
        # (CI's git diff could not catch a hand edit there), are read in full.
        sources = ("exam/exam.js", "exam/sub/page.html", "data/exam/notes/ch1.frag", "_gen_exam.py",
                   "blog/blog-shared.js", "blog/acne-myths.html", "llms.txt", "tools/review_scope.py",
                   "en/blog/orphan.html", "en/about.html", "en/blog/acne-myths.json", "ai/extra.json",
                   "blog/other.min.js", "vendor/x.min.js", ".well-known/security.txt", "index.html")
        for path in generated:
            with self.subTest(path=path):
                self.assertIsNotNone(scope.group_of(path, FakeTree()))
        for path in sources:
            with self.subTest(path=path):
                self.assertIsNone(scope.group_of(path, FakeTree()))

    def test_sample_is_small_stable_per_head_and_varies_between_heads(self):
        pages = [f"exam/fitz-{n}.html" for n in range(50)]
        first = scope.sample(pages, "a" * 40)
        self.assertEqual(len(first), scope.SAMPLE)
        self.assertEqual(first, scope.sample(list(reversed(pages)), "a" * 40))
        self.assertTrue(set(first) <= set(pages))
        self.assertTrue(any(scope.sample(pages, c * 40) != first for c in "bcdef"))
        self.assertEqual(scope.sample(pages[:2], "a" * 40), pages[:2])

    def test_section_lists_samples_only_and_falls_back_to_full_reads(self):
        pages = [f"exam/fitz-{n}.html" for n in range(20)]
        text = scope.section(["_gen_exam.py", "data/exam/a.json", *pages], "a" * 40, FakeTree())
        self.assertIn("22 (2 source, 20 generated)", text)
        self.assertIn("_gen_exam.py from data/exam/**", text)
        self.assertIn("Canonical generated file consistency", text)
        self.assertEqual(text.count("    sample: "), scope.SAMPLE)
        only_sources = scope.section(["tools/pr_review.py", "en/blog/orphan.html"], "a" * 40, FakeTree())
        self.assertIn("read every changed file in full", only_sources)
        self.assertNotIn("sample:", only_sources)

    def test_changed_reads_the_committed_range_from_git(self):
        import shutil
        import subprocess
        import tempfile
        from unittest.mock import patch
        if not shutil.which("git"):
            self.skipTest("git not available")
        with tempfile.TemporaryDirectory() as tmp:
            def run(*args):
                return subprocess.check_output(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                                                *args], cwd=tmp, text=True).strip()
            run("init", "-q")
            Path(tmp, "a.txt").write_text("1", encoding="utf-8")
            run("add", "-A"); run("commit", "-qm", "base")
            base = run("rev-parse", "HEAD")
            Path(tmp, "exam").mkdir()
            Path(tmp, "exam", "p 1.html").write_text("x", encoding="utf-8")
            Path(tmp, "a.txt").unlink()
            run("add", "-A"); run("commit", "-qm", "head")
            head = run("rev-parse", "HEAD")
            with patch.object(scope, "ROOT", Path(tmp)):
                self.assertEqual(scope.changed(base, head), ["a.txt", "exam/p 1.html"])
                self.assertEqual(scope.Tree(head).bundles, set())
                Path(tmp, "_minify.py").write_text("JS_BUNDLES = ('blog-a', 'blog-b')\n", encoding="utf-8")
                run("add", "-A"); run("commit", "-qm", "minify")
                tree = scope.Tree(run("rev-parse", "HEAD"))
                self.assertEqual(tree.bundles, {"blog-a", "blog-b"})
                self.assertIn("exam/p 1.html", tree.files)
                self.assertIsNotNone(scope.group_of("blog/blog-a.min.js", tree))

    def test_wrapper_injects_the_scope_and_never_samples_without_it(self):
        text = (ROOT / "tools" / "codex_review.sh").read_text(encoding="utf-8")
        self.assertIn('"$SCRIPT_DIR/review_scope.py" "$1" "$2"', text)
        self.assertIn("Generated-output classification unavailable: read every changed file in full.", text)
        self.assertNotIn("(e.g. exam/** from", text)


class StatusChainTests(unittest.TestCase):
    """Incremental resumes record the link they continue from (prev=) and the session (s=)."""

    def test_status_description_names_base_prev_and_session(self):
        base, prev = "b" * 40, "c" * 40
        self.assertEqual(pr.status_description("APPROVE", base, "", SESSION_ID),
                         f"APPROVE base={base} s=0123abcd")
        text = pr.status_description("REQUEST_CHANGES", base, prev, SESSION_ID)
        self.assertEqual(text, f"REQUEST_CHANGES base={base} prev={prev} s=0123abcd")
        self.assertLessEqual(len(text), 140)
        self.assertEqual(pr.status_description("QUOTA_PENDING", base, "junk", "unavailable"),
                         f"quota-pending base={base}")

    def test_round_label_says_which_range_was_read(self):
        head, prev = SHA, "c" * 40
        self.assertIn("first", pr.round_label({"head": head, "resume": False}))
        self.assertIn(f"`{prev}..{head}`", pr.round_label({"head": head, "resume": True,
                                                          "scope": "incremental", "prev": prev}))
        full = pr.round_label({"head": head, "resume": True, "scope": "full", "replaced": prev})
        self.assertIn("WHOLE range", full)
        self.assertIn(prev, full)
        self.assertIn("rebuttal", pr.round_label({"head": head, "resume": True, "rebuttal": True}))


class IncrementalChainEndToEndTests(unittest.TestCase):
    """Simulated rounds through main(): first (whole range) -> incremental resume ->
    rebase -> whole-range fallback, and the pre-push gate walking each recorded chain."""

    BASE, H0, H1, H2, REBASED, MAIN = ("b" * 40, "1" * 40, "2" * 40, "3" * 40, "4" * 40, "9" * 40)
    PARENT = {"1" * 40: "b" * 40, "2" * 40: "1" * 40, "3" * 40: "2" * 40, "4" * 40: "9" * 40,
              "9" * 40: "b" * 40}

    def ancestor(self, older, newer):
        while newer:
            if newer == older:
                return True
            newer = self.PARENT.get(newer)
        return False

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".codex-review").mkdir()
        self.head = self.H0
        self.statuses = {}
        self.reviews = []
        self.next_id = 1

    def tearDown(self):
        self.tmp.cleanup()

    def fake_git(self, *args):
        if args == ("rev-parse", "HEAD"):
            return self.head
        if args[0] == "status":
            return ""
        if args == ("rev-parse", "FETCH_HEAD"):
            return self.MAIN
        if args[0] == "branch":
            return "codex/x"
        if args[0] == "merge-base":
            node = args[2]
            while not self.ancestor(node, args[1]):
                node = self.PARENT[node]
            return node
        raise AssertionError(args)

    def fake_run(self, args, **kwargs):
        import subprocess
        if "--is-ancestor" in args:
            return subprocess.CompletedProcess(args, 0 if self.ancestor(args[-2], args[-1]) else 1)
        if "ls-remote" in args:
            return subprocess.CompletedProcess(args, 0, stdout=f"{self.head}\trefs/heads/codex/x\n")
        return subprocess.CompletedProcess(args, 0)

    def fake_api(self):
        test = self

        class API:
            repo = "owner/repo"

            def __init__(self, *a):
                pass

            def call(self, method, path, body=None):
                if path.startswith("/pulls?"):
                    return [{"number": 7, "html_url": "https://github.com/owner/repo/pull/7",
                             "head": {"sha": test.head}}]
                if method == "POST" and path.startswith("/statuses/"):
                    test.statuses.setdefault(path.split("/")[-1], []).append(
                        {**body, "id": test.next_id, "creator": {"login": "owner"}})
                    test.next_id += 1
                return {}
        return API

    def round(self, verdict, *flags):
        import io
        import sys
        from unittest.mock import patch

        def review(mode, base, head, ctx, session, previous, rebuttal, scope_name):
            self.reviews.append((scope_name, base, previous))
            (self.root / ".codex-review" / "last_session_id").write_text(SESSION_ID, encoding="utf-8")
            return verdict, SESSION_ID, verdict
        with patch.object(pr, "ROOT", self.root), patch.object(pr, "API", self.fake_api()), \
             patch.object(pr, "repository", return_value="owner/repo"), \
             patch.object(pr, "git", side_effect=self.fake_git), \
             patch.object(pr.subprocess, "run", side_effect=self.fake_run), \
             patch.object(pr, "run_review", side_effect=review), \
             patch.object(sys, "argv", ["pr_review.py", *flags]), \
             patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
            return pr.main()

    def gate(self, sha):
        import io
        import sys
        from unittest.mock import patch
        import _delivery as d
        test = self

        class Pages:
            def pages(self, path):
                return list(test.statuses.get(path.split("/")[2], []))
        with patch.object(d.subprocess, "run", side_effect=self.fake_run), \
             patch.object(sys, "stderr", io.StringIO()):
            return d.pr_review(Pages(), {"repository": "owner/repo"}, sha, self.MAIN)

    def test_rounds_record_a_chain_the_gate_can_walk(self):
        import _delivery as d
        self.assertEqual(self.round("REQUEST_CHANGES"), 2)
        self.head = self.H1
        self.assertEqual(self.round("REQUEST_CHANGES", "--resume"), 2)
        self.head = self.H2
        self.assertEqual(self.round("APPROVE", "--resume"), 0)
        self.assertEqual(self.reviews, [("first", self.BASE, None), ("incremental", self.BASE, self.H0),
                                        ("incremental", self.BASE, self.H1)])
        self.assertEqual(self.statuses[self.H2][-1]["description"],
                         f"APPROVE base={self.BASE} prev={self.H1} s=0123abcd")
        self.assertEqual(self.gate(self.H2)["chain"], [self.H2, self.H1, self.H0])
        # A missing link, another session or another base breaks the chain: fail closed.
        saved = self.statuses.pop(self.H1)
        with self.assertRaises(d.Blocked):
            self.gate(self.H2)
        for broken in ("s=0123abcd", f"base={self.BASE}"):
            self.statuses[self.H1] = [{**saved[-1], "description": saved[-1]["description"].replace(
                broken, "s=ffffffff" if broken.startswith("s=") else "base=" + "e" * 40)}]
            with self.subTest(broken=broken), self.assertRaises(d.Blocked):
                self.gate(self.H2)
        # A later error status on a link does not erase the completed verdict before it.
        self.statuses[self.H1] = saved + [{**saved[-1], "state": "error", "id": 99,
                                           "description": f"ERROR base={self.BASE} prev={self.H0} s=0123abcd"}]
        self.assertEqual(self.gate(self.H2)["chain"], [self.H2, self.H1, self.H0])

    def test_rebase_falls_back_to_a_whole_range_review_that_roots_a_new_chain(self):
        self.assertEqual(self.round("REQUEST_CHANGES"), 2)
        self.head = self.REBASED
        self.assertEqual(self.round("APPROVE", "--resume"), 0)
        self.assertEqual(self.reviews[-1], ("full", self.MAIN, self.H0))
        self.assertEqual(self.statuses[self.REBASED][-1]["description"],
                         f"APPROVE base={self.MAIN} s=0123abcd")
        self.assertEqual(self.gate(self.REBASED)["chain"], [self.REBASED])

    def test_rebuttal_on_the_same_head_keeps_that_heads_link(self):
        import tempfile
        self.assertEqual(self.round("REQUEST_CHANGES"), 2)
        self.head = self.H1
        self.assertEqual(self.round("REQUEST_CHANGES", "--resume"), 2)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Finding 1 is REJECTED: the owner check is at _delivery.py:40.")
        try:
            self.assertEqual(self.round("APPROVE", "--resume", "--rebuttal", f.name), 0)
        finally:
            Path(f.name).unlink()
        self.assertEqual(self.reviews[-1], ("rebuttal", self.BASE, None))
        self.assertEqual(self.statuses[self.H1][-1]["description"],
                         f"APPROVE base={self.BASE} prev={self.H0} s=0123abcd")
        self.assertEqual(self.gate(self.H1)["chain"], [self.H1, self.H0])

    def test_link_must_be_an_ancestor_and_old_whole_range_statuses_still_pass(self):
        import _delivery as d
        self.statuses[self.H2] = [{"id": 2, "state": "success", "creator": {"login": "owner"},
                                   "context": d.REVIEW_CONTEXT,
                                   "description": f"APPROVE base={self.BASE} prev={self.REBASED} s=0123abcd"}]
        self.statuses[self.REBASED] = [{"id": 1, "state": "failure", "creator": {"login": "owner"},
                                        "context": d.REVIEW_CONTEXT,
                                        "description": f"REQUEST_CHANGES base={self.BASE} s=0123abcd"}]
        with self.assertRaises(d.Blocked):
            self.gate(self.H2)
        self.statuses[self.H2] = [{"id": 3, "state": "success", "creator": {"login": "owner"},
                                   "context": d.REVIEW_CONTEXT, "description": f"APPROVE base={self.BASE}"}]
        self.assertEqual(self.gate(self.H2)["chain"], [self.H2])

    def test_verification_summary_reaches_the_prompt_environment_and_rejects_diffs(self):
        import os
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CODEX_REVIEW_VERIFICATION", None)
            good, bad = Path(tmp, "v.txt"), Path(tmp, "d.txt")
            good.write_text("python -m unittest _test_pr_review: OK", encoding="utf-8")
            bad.write_text("diff --git a/x b/x\n", encoding="utf-8")
            self.assertEqual(self.round("REQUEST_CHANGES", "--verification", str(bad)), 1)
            self.assertEqual(self.reviews, [])
            self.assertEqual(self.round("REQUEST_CHANGES", "--verification", str(good)), 2)
            self.assertEqual(os.environ["CODEX_REVIEW_VERIFICATION"], "python -m unittest _test_pr_review: OK")

if __name__ == "__main__":
    unittest.main()
