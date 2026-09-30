"""Real disposable Git histories and bundles; no hosted writes or project CI claim."""
from datetime import datetime, timezone
import contextlib
import io
import hashlib
import json
from pathlib import Path
import os
import subprocess
import tempfile
import sys
import unittest
from unittest.mock import patch

import _process_article_requests as requests
import _test_article_request as fixtures

ROOT = Path(__file__).resolve().parent


class ScheduledCandidateTests(unittest.TestCase):
    original_source = fixtures.RequestTests.original_source
    run_git = fixtures.RequestTests.run_git
    write = fixtures.RequestTests.write
    commit = fixtures.RequestTests.commit
    save_manifest = fixtures.RequestTests.save_manifest
    store = fixtures.RequestTests.store

    def setUp(self):
        fixtures.RequestTests.setUp(self)
        self.run_git("config", "core.autocrlf", "false")
        self.artifacts = tempfile.TemporaryDirectory()
        self.addCleanup(self.artifacts.cleanup)
        self.output = Path(self.artifacts.name) / "source-bundles"
        # Preserve a byte-exact legacy queue. It does not grant author permission.
        self.queue = b'[ {"slug":"legacy", "at":"2020-01-01T00:00:00Z"} ]\n'
        self.write(requests.QUEUE, self.queue)
        self.commit("legacy queue")
        self.main = self.run_git("rev-parse", "HEAD")
        self.refs = self.run_git("show-ref")

    def process(self):
        report = requests.process(self.root, self.output, now=self.now)
        self.assert_preserved()
        return report

    def assert_preserved(self):
        self.assertEqual(self.run_git("show-ref"), self.refs)
        self.assertEqual(self.run_git("rev-parse", "HEAD"), self.main)
        self.assertEqual(self.run_git("status", "--porcelain"), "")
        self.assertEqual((self.root / requests.QUEUE).read_bytes(), self.queue)
        self.assertEqual((self.root / "unchanged.txt").read_bytes(), b"Keep source")
        self.assertEqual(self.run_git("show", "drafts/article:blog/article.html").encode(), self.content.decode().strip().encode())

    def recipient(self, prepared):
        destination = Path(self.artifacts.name) / prepared["requestHead"]
        subprocess.run(["git", "clone", "--no-checkout", str(self.root), str(destination)], check=True, capture_output=True)
        subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=destination, check=True, capture_output=True)
        subprocess.run(["git", "fetch", str(self.output / prepared["bundle"]), "HEAD"], cwd=destination, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=destination, check=True, capture_output=True)
        return destination

    def test_new_request_discovered_without_queue_entry_and_without_mutations(self):
        report = self.process()
        self.assertEqual(len(report["prepared"]), 1)
        prepared = report["prepared"][0]
        self.assertFalse(prepared["ciVerified"])
        self.assertFalse(prepared["reviewVerified"])
        self.assertFalse(prepared["published"])
        self.assertEqual(prepared["mainSha"], self.main)
        bundle = self.output / prepared["bundle"]
        self.assertEqual(hashlib.sha256(bundle.read_bytes()).hexdigest(), prepared["bundleSha256"])
        destination = self.recipient(prepared)
        self.assertEqual((destination / "blog/article.html").read_bytes(), self.content)
        self.assertEqual((destination / self.image_path).read_bytes(), self.image)
        self.assertEqual((destination / "unchanged.txt").read_bytes(), b"Keep source")
        self.assertFalse((destination / "api/unrelated.js").exists())
        self.assertFalse((destination / ".cms-drafts/article.json").exists())
        self.assertFalse((destination / ".cms-requests/article.json").exists())
        proof = json.loads((destination / requests.RECEIPT).read_bytes())["requests"][0]
        self.assertEqual(proof["requestHead"], self.head)
        self.assertEqual(proof["preparedAgainst"], self.main)
        self.assertEqual(proof["sourceSha256"], prepared["sourceSha256"])
        parents = subprocess.check_output(["git", "rev-list", "--parents", "-n", "1", "HEAD"], cwd=destination).decode().split()
        self.assertEqual(parents, [prepared["candidateSha"], self.main])

    def test_empty_queue_does_not_hide_new_request(self):
        self.queue = b'[]\n'
        self.write(requests.QUEUE, self.queue)
        self.commit("empty legacy queue")
        self.main, self.refs = self.run_git("rev-parse", "HEAD"), self.run_git("show-ref")
        self.assertEqual(len(self.process()["prepared"]), 1)

    def test_missing_request_keeps_legacy_queue_and_creates_no_bundle(self):
        self.run_git("switch", "drafts/article")
        self.run_git("rm", ".cms-requests/article.json")
        self.commit("cancel author request")
        self.run_git("switch", "main")
        self.refs = self.run_git("show-ref")
        report = self.process()
        self.assertFalse(report["prepared"])
        self.assertEqual(report["deferred"][0]["reason"], "author_request_required")
        self.assertFalse(list(self.output.glob("*.bundle")))

    def test_future_schedule_waits_without_copying_or_removing_it(self):
        self.request.update(action="schedule", scheduledAt="2026-09-30T13:00:00.000Z")
        self.store(amend=True)
        self.refs = self.run_git("show-ref")
        report = self.process()
        self.assertFalse(report["prepared"])
        self.assertEqual(report["deferred"][0]["reason"], "not_due")

    def test_main_article_conflict_defers_request(self):
        self.write("blog/article.html", b"<html><h1>New published edit</h1></html>")
        self.commit("main content advanced")
        self.main, self.refs = self.run_git("rev-parse", "HEAD"), self.run_git("show-ref")
        report = self.process()
        self.assertFalse(report["prepared"])
        self.assertEqual(report["deferred"][0]["reason"], "request_rejected")
        self.assertFalse(list(self.output.glob("*.bundle")))

    def test_request_with_extra_commit_files_is_rejected(self):
        self.store(amend=True, extra=("malicious.py", b"raise Exception('must not execute')"))
        self.refs = self.run_git("show-ref")
        self.assertFalse(self.process()["prepared"])

    def test_cancel_during_bundle_creation_removes_artifact(self):
        actual = requests.git
        def moving(root, *args):
            result = actual(root, *args)
            if args[:2] == ("bundle", "create"):
                self.run_git("update-ref", "refs/heads/drafts/article", self.saved)
            return result
        with patch.object(requests, "git", side_effect=moving):
            # In this fixture origin is the trusted repository itself. Its ref
            # mutation also invalidates the whole discovery report.
            with self.assertRaisesRegex(ValueError, "Trusted checkout changed"):
                requests.process(self.root, self.output, now=self.now)
        self.assertFalse((self.output / "report.json").exists())
        self.assertFalse(list(self.output.glob("*.bundle")))
        self.assertEqual((self.root / requests.QUEUE).read_bytes(), self.queue)

    def test_main_advance_during_preparation_fails_without_success_report(self):
        with patch.object(requests, "unchanged_main", side_effect=ValueError("Main advanced")):
            with self.assertRaisesRegex(ValueError, "Main advanced"):
                requests.process(self.root, self.output, now=self.now)
        self.assertFalse((self.output / "report.json").exists())
        self.assertFalse(list(self.output.glob("*.bundle")))
        self.assert_preserved()

    def test_late_cancellation_prevents_success_report(self):
        actual = requests.verify_request_head
        calls = []
        def cancellation(root, head, file):
            calls.append(head)
            if len(calls) == 3:
                raise ValueError("Author cancelled after bundle preparation")
            return actual(root, head, file)
        with patch.object(requests, "verify_request_head", side_effect=cancellation):
            with self.assertRaisesRegex(ValueError, "Author cancelled"):
                requests.process(self.root, self.output, now=self.now)
        self.assertFalse((self.output / "report.json").exists())
        self.assert_preserved()

    def test_clean_filter_cannot_reseal_altered_article_bytes(self):
        actual = requests.git
        def altered(root, *args):
            if args[:2] == ("add", "--"):
                (root / "blog/article.html").write_bytes(b"<html><h1>Unapproved replacement</h1></html>")
            return actual(root, *args)
        with patch.object(requests, "git", side_effect=altered):
            report = self.process()
        self.assertFalse(report["prepared"])
        self.assertFalse(list(self.output.glob("*.bundle")))

    def test_operational_cli_rejects_wrong_context_origin_and_artifact_path(self):
        env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": requests.REPO,
               "GITHUB_REF": "refs/heads/main", "RUNNER_TEMP": self.artifacts.name}
        expected = Path(self.artifacts.name) / "cms-source-artifacts"
        for changes, origin, output in (
            ({"GITHUB_ACTIONS": "false"}, requests.REPO, expected),
            ({"GITHUB_REPOSITORY": "fork/user"}, requests.REPO, expected),
            ({"GITHUB_REF": "refs/heads/drafts/article"}, requests.REPO, expected),
            ({}, "fork/user", expected),
            ({}, requests.REPO, self.output),
        ):
            with self.subTest(changes=changes, origin=origin, output=output):
                with patch.dict(os.environ, {**env, **changes}), patch.object(sys, "argv", ["requests", "--output", str(output)]):
                    with patch.object(requests, "git", return_value=("https://github.com/" + origin + ".git\n").encode()):
                        with patch.object(requests, "process") as process:
                            with self.assertRaises(ValueError):
                                requests.main()
                            process.assert_not_called()

    def test_operational_cli_accepts_both_exact_checkout_https_forms(self):
        env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": requests.REPO,
               "GITHUB_REF": "refs/heads/main", "RUNNER_TEMP": self.artifacts.name}
        output = Path(self.artifacts.name) / "cms-source-artifacts"
        for suffix in ("", ".git"):
            with self.subTest(suffix=suffix), patch.dict(os.environ, env):
                with patch.object(sys, "argv", ["requests", "--output", str(output)]):
                    with patch.object(requests, "git", return_value=("https://github.com/" + requests.REPO + suffix + "\n").encode()):
                        with patch.object(requests, "process", return_value={"prepared": [], "deferred": []}) as process:
                            with contextlib.redirect_stdout(io.StringIO()):
                                requests.main()
                            process.assert_called_once()

    def test_non_ancestor_draft_is_deferred_without_blocking_valid_request(self):
        self.create_new_request("other")
        self.run_git("switch", "drafts/article")
        self.record["baseMain"] = self.saved  # Draft-only descendant of main.
        self.save_manifest()
        self.request["draftHead"] = self.run_git("rev-parse", "HEAD")
        self.request["manifestSha"] = self.run_git("rev-parse", "HEAD:.cms-drafts/article.json")
        self.store()
        self.refs = self.run_git("show-ref")
        report = self.process()
        self.assertEqual([item["file"] for item in report["prepared"]], ["blog/other.html"])
        self.assertEqual(report["deferred"][0]["file"], "blog/article.html")
        self.assertEqual(report["deferred"][0]["reason"], "request_rejected")

    def test_missing_or_non_commit_base_is_deferred_without_blocking_valid_request(self):
        self.create_new_request("other")
        self.run_git("switch", "drafts/article")
        self.record["baseMain"] = "a" * 40
        self.save_manifest()
        self.request["draftHead"] = self.run_git("rev-parse", "HEAD")
        self.request["manifestSha"] = self.run_git("rev-parse", "HEAD:.cms-drafts/article.json")
        self.store()
        self.refs = self.run_git("show-ref")
        report = self.process()
        self.assertEqual([item["file"] for item in report["prepared"]], ["blog/other.html"])
        self.assertEqual(report["deferred"][0]["file"], "blog/article.html")
        self.assertEqual(report["deferred"][0]["reason"], "request_rejected")

    def test_foreign_unicode_draft_branch_does_not_hide_valid_requests(self):
        self.run_git("branch", "drafts/foreign-草稿", self.base)
        self.refs = self.run_git("show-ref")
        report = self.process()
        self.assertEqual([item["file"] for item in report["prepared"]], ["blog/article.html"])
        self.assertEqual(report["deferred"][0]["reason"], "invalid_branch")

    def test_remote_lookup_failure_is_not_an_empty_queue(self):
        self.run_git("remote", "set-url", "origin", str(Path(self.artifacts.name) / "missing.git"))
        with self.assertRaises(subprocess.CalledProcessError):
            requests.process(self.root, self.output, now=self.now)
        self.assertFalse(self.output.exists())
        self.assert_preserved()

    def test_dirty_or_stale_main_or_unsafe_output_is_rejected(self):
        self.write("user.txt", b"keep local edit")
        with self.assertRaisesRegex(ValueError, "clean"):
            requests.process(self.root, self.output, now=self.now)
        (self.root / "user.txt").unlink()
        with self.assertRaisesRegex(ValueError, "outside"):
            requests.process(self.root, self.root / "artifacts", now=self.now)
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, "new directory"):
            requests.process(self.root, self.output, now=self.now)
        self.assert_preserved()

    def create_new_request(self, slug):
        self.run_git("switch", "-c", "drafts/" + slug, "main")
        file = "blog/" + slug + ".html"
        self.write(file, ('<html><h1>' + slug + '</h1></html>').encode())
        self.commit("new source")
        blob = self.run_git("rev-parse", "HEAD:" + file)
        manifest = {"version": 1, "file": file, "baseMain": self.main, "baseSha": None,
                    "blobSha": blob, "status": "draft", "assets": [],
                    "metadata": {"title_en": slug, "tag": "test", "tag_en": "test", "cat": "note", "date": "2026-09-30"}}
        manifest_file = ".cms-drafts/" + slug + ".json"
        self.write(manifest_file, json.dumps(manifest).encode())
        self.commit("new manifest")
        request = {**self.request, "file": file, "blobSha": blob, "baseSha": None,
                   "draftHead": self.run_git("rev-parse", "HEAD"),
                   "manifestSha": self.run_git("rev-parse", "HEAD:" + manifest_file)}
        self.write(".cms-requests/" + slug + ".json", (json.dumps(request, separators=(",", ":")) + "\n").encode())
        self.commit("new request")
        self.run_git("switch", "main")

    def test_multiple_new_articles_get_independent_catalogs(self):
        for slug in ("first", "second"):
            self.create_new_request(slug)
        self.refs = self.run_git("show-ref")
        report = self.process()
        self.assertEqual(len(report["prepared"]), 3)
        for prepared in report["prepared"]:
            self.assertEqual(prepared["mainSha"], self.main)
            if prepared["file"] == "blog/article.html":
                continue
            destination = self.recipient(prepared)
            slug = prepared["file"].split("/")[1].removesuffix(".html")
            catalog = (destination / "blog/blog-shared.js").read_bytes()
            other = "second" if slug == "first" else "first"
            self.assertIn(("slug:'" + slug + "'").encode(), catalog)
            self.assertNotIn(("slug:'" + other + "'").encode(), catalog)
            self.assertEqual(hashlib.sha256(catalog).hexdigest(), prepared["sourceSha256"]["blog/blog-shared.js"])

    def test_workflow_executes_trusted_helper_and_uploads_only_source_artifacts(self):
        workflow = (ROOT / ".github/workflows/scheduled-publish.yml").read_text(encoding="utf-8")
        self.assertIn("ref: main", workflow)
        self.assertIn("if: github.ref == 'refs/heads/main'", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn('python _process_article_requests.py --output "$RUNNER_TEMP/cms-source-artifacts"', workflow)
        self.assertIn("path: ${{ runner.temp }}/cms-source-artifacts/", workflow)
        self.assertNotIn("git push", workflow)
        self.assertNotIn("_run_ci.py", workflow)
        self.assertNotIn("Claude-Opus-5-Review: pending", workflow)


if __name__ == "__main__":
    unittest.main()
