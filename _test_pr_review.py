"""tools/pr_review.py: whole-PR review bookkeeping (user decision 2026-10-15).

Offline; no GitHub or Codex calls. Run by the Delivery contract job."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("pr_review", ROOT / "tools" / "pr_review.py")
pr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pr)

SHA = "a" * 40


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


class RunReviewEvidenceTests(unittest.TestCase):
    QUOTA = json.dumps({"type": "error", "message": "You've hit your usage limit."})

    def run_attempt(self, rc, fresh_raw=None):
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
            with patch.object(pr, "ROOT", Path(directory)), patch.object(pr, "bash", return_value="bash"),                  patch.object(pr, "wrapper", return_value="tools/codex_review.sh"),                  patch.object(pr.subprocess, "run", side_effect=wrapper_run):
                return pr.run_review("targeted", "b" * 40, SHA, None, None)[0]

    def test_wrapper_stopping_early_never_reuses_stale_quota_log(self):
        self.assertEqual(self.run_attempt(64), "ERROR")

    def test_untrusted_run_without_fresh_quota_evidence_is_error(self):
        self.assertEqual(self.run_attempt(4), "ERROR")
        self.assertEqual(self.run_attempt(5, fresh_raw=self.QUOTA), "ERROR")

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


if __name__ == "__main__":
    unittest.main()
