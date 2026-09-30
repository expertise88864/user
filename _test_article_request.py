"""Version-bound author requests with real isolated Git refs; no hosted writes."""
from datetime import datetime, timezone
import json
import subprocess
import unittest
from unittest.mock import patch

import _test_article_candidate as fixtures
from _validate_article_request import request_plan


class RequestTests(unittest.TestCase):
    original_source = b'<html><head><meta name="robots" content="index,follow,max-image-preview:large" /></head><body><h1>Original</h1><svg id="keep"><path d="M0 0"/></svg></body></html>'
    run_git = fixtures.CandidateTests.run_git
    write = fixtures.CandidateTests.write
    commit = fixtures.CandidateTests.commit
    save_manifest = fixtures.CandidateTests.save_manifest

    def setUp(self):
        fixtures.CandidateTests.setUp(self)
        self.saved = self.head
        self.now = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
        # Query a disposable local origin: exercise actual ls-remote without
        # credentials/network and without modifying the user's repository.
        self.run_git("remote", "add", "origin", str(self.root))
        self.request = {"version": 1, "file": "blog/article.html", "action": "review",
                        "draftHead": self.saved, "manifestSha": self.run_git("rev-parse", self.saved + ":.cms-drafts/article.json"),
                        "blobSha": self.blob, "baseSha": self.base_blob, "approvedBy": "expertise88864",
                        "contentApproved": True, "requestedAt": "2026-09-30T10:00:00.000Z", "scheduledAt": None}
        self.store()

    def store(self, *, amend=False, extra=None):
        self.run_git("switch", "drafts/article")
        self.write(".cms-requests/article.json", (json.dumps(self.request, ensure_ascii=False, separators=(",", ":")) + "\n").encode())
        if extra:
            self.write(*extra)
        self.run_git("add", "-A")
        self.run_git("commit", *( ["--amend"] if amend else []), "-m", "author request")
        self.head = self.run_git("rev-parse", "HEAD")
        self.run_git("switch", "main")

    def prepare(self):
        return request_plan(self.root, self.head, "blog/article.html", self.blob, now=self.now)

    def reject(self, pattern=None):
        with self.assertRaisesRegex((ValueError, subprocess.CalledProcessError), pattern or "."):
            self.prepare()
        self.assertEqual(self.run_git("status", "--porcelain"), "")
        self.assertEqual((self.root / "blog/article.html").read_bytes(), self.original)

    def test_approved_source_and_facts_without_ref_or_file_writes(self):
        refs = self.run_git("show-ref")
        files, proof = self.prepare()
        self.assertEqual(set(files), {"blog/article.html", self.image_path})
        self.assertEqual(files["blog/article.html"], self.content)
        self.assertEqual(proof["requestHead"], self.head)
        self.assertEqual(proof["draftHead"], self.saved)
        self.assertEqual(proof["preparedAgainst"], self.base)
        self.assertEqual(set(proof["sourceSha256"]), set(files))
        self.assertEqual(self.run_git("show-ref"), refs)
        self.assertEqual(self.run_git("status", "--porcelain"), "")

    def test_scheduled_requests_must_be_due_and_within_author_interval(self):
        self.request.update(action="schedule", scheduledAt="2026-09-30T13:00:00.000Z")
        self.store(amend=True)
        self.reject("not due")
        self.request["scheduledAt"] = "2026-09-30T11:00:00.000Z"
        self.store(amend=True)
        self.assertEqual(self.prepare()[1]["action"], "schedule")
        self.request["scheduledAt"] = "2028-09-30T11:00:00.000Z"
        self.store(amend=True)
        self.reject("interval")

    def test_schema_identity_confirmation_and_timestamps_fail_closed(self):
        baseline = dict(self.request)
        for changes in ({"version": True}, {"approvedBy": "another-user"}, {"contentApproved": 1},
                        {"contentApproved": False}, {"action": "publish-main"}, {"file": "../admin.html"},
                        {"blobSha": "0" * 40}, {"manifestSha": "0" * 40}, {"baseSha": None},
                        {"requestedAt": "2026-09-30T13:00:00.000Z"}, {"requestedAt": "2026-09-30T10:00:00Z"},
                        {"scheduledAt": "2026-09-30T11:00:00.000Z"}, {"extra": "unknown"}):
            with self.subTest(changes=changes):
                self.request = {**baseline, **changes}
                self.store(amend=True)
                self.reject()

    def test_cancelled_or_newer_origin_head_invalidates_cached_request(self):
        old_head = self.head
        self.run_git("switch", "drafts/article")
        self.run_git("rm", ".cms-requests/article.json")
        self.commit("author cancelled")
        self.run_git("switch", "main")
        self.head = old_head
        self.reject("cancelled or changed")

    def test_unrelated_successor_and_extra_request_files_are_rejected(self):
        self.store(amend=True, extra=("unrelated.txt", b"not part of request"))
        self.reject("beyond")
        self.run_git("switch", "drafts/article")
        self.write("later.txt", b"later arbitrary change")
        self.commit("unrelated successor")
        self.head = self.run_git("rev-parse", "HEAD")
        self.run_git("switch", "main")
        self.reject("immediate successor")

    def test_main_conflict_preserves_request_and_source(self):
        self.write("blog/article.html", b"<html><h1>Another published edit</h1></html>")
        self.commit("main article changed")
        refs = self.run_git("show-ref")
        with self.assertRaisesRegex(ValueError, "Published article changed"):
            self.prepare()
        self.assertEqual(self.run_git("show-ref"), refs)
        self.assertEqual(self.run_git("status", "--porcelain"), "")

    def test_origin_missing_is_not_cached_approval(self):
        self.run_git("remote", "remove", "origin")
        self.reject()

    def test_deleted_request_branch_is_cancellation_not_transport_failure(self):
        self.run_git("branch", "-D", "drafts/article")
        self.reject("cancelled or changed")

    def test_cancellation_during_validation_is_checked_again_before_return(self):
        from _validate_article_request import verify_request_head
        calls = []

        def moving_origin(root, head, file):
            calls.append(head)
            if len(calls) == 2:
                raise ValueError("cancelled or changed")
            verify_request_head(root, head, file)

        with patch("_validate_article_request.verify_request_head", side_effect=moving_origin):
            self.reject("cancelled or changed")
        self.assertEqual(len(calls), 2)

    def test_unpublish_does_not_copy_unfinished_draft_to_public_source(self):
        self.request.update(action="unpublish", contentApproved=False)
        self.store(amend=True)
        refs = self.run_git("show-ref")
        files, proof = self.prepare()
        self.assertEqual(set(files), {"blog/article.html", "blog/blog-shared.js"})
        self.assertEqual(files["blog/article.html"], self.original.replace(b'content="index,follow,', b'content="noindex,follow,'))
        self.assertNotIn(self.content, files.values())
        self.assertEqual(proof["action"], "unpublish")
        self.assertEqual(self.run_git("show-ref"), refs)
        self.assertEqual(self.run_git("status", "--porcelain"), "")

    def test_hidden_article_does_not_get_implicit_permission_to_index(self):
        self.write("blog/blog-shared.js", b"DN.ARTICLES = [{slug:'article',title:'Original',title_en:'Original',unpublished:true}];")
        self.commit("intentionally unpublished")
        self.reject("visibility")


if __name__ == "__main__":
    unittest.main()
