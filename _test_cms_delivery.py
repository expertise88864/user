"""Live author-intent / payload gates against disposable Git histories.

No credentials, hosted requests, hooks, remote writes or production deployments.
"""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from types import SimpleNamespace

import _cms_delivery as delivery
from _prepare_article_candidate import apply
import _test_article_request as fixtures


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


class LocalAPI:
    """The same response boundary as GitHub, using only isolated local blobs."""
    def __init__(self, fixture):
        self.fixture = fixture
        self.calls = []
        self.adjust = lambda path, data: data

    def get(self, path):
        self.calls.append(path)
        f = self.fixture
        if path.startswith("/contents/"):
            file, sha = path[len("/contents/"):].split("?ref=")
            raw = subprocess.check_output(["git", "show", sha + ":" + file], cwd=f.root, stderr=subprocess.PIPE)
            data = {"type": "file", "path": file, "sha": f.run_git("rev-parse", sha + ":" + file),
                    "size": len(raw), "encoding": "base64", "content": base64.b64encode(raw).decode()}
        elif path.startswith("/git/ref/heads/"):
            ref = "refs/heads/" + path[len("/git/ref/heads/"):]
            data = {"ref": ref, "object": {"type": "commit", "sha": f.run_git("rev-parse", ref)}}
        elif path.startswith("/git/commits/"):
            sha = path[len("/git/commits/"):]
            parents = f.run_git("rev-list", "--parents", "-n", "1", sha).split()[1:]
            data = {"sha": sha, "tree": {"sha": f.run_git("rev-parse", sha + "^{tree}")}, "parents": [{"sha": parent} for parent in parents]}
        elif path.startswith("/git/trees/"):
            tree_sha = path[len("/git/trees/"):].split("?")[0]
            raw = subprocess.check_output(["git", "ls-tree", "-r", "-z", tree_sha], cwd=f.root)
            entries = []
            for entry in raw.split(b"\0"):
                if not entry:
                    continue
                fields, name = entry.split(b"\t", 1)
                mode, kind, blob = fields.decode().split()
                entries.append({"path": name.decode(), "mode": mode, "type": kind, "sha": blob})
            data = {"sha": tree_sha, "truncated": False, "tree": entries}
        elif path.startswith("/git/blobs/"):
            blob = path[len("/git/blobs/"):]
            raw = subprocess.check_output(["git", "cat-file", "blob", blob], cwd=f.root)
            data = {"sha": blob, "size": len(raw), "encoding": "base64", "content": base64.b64encode(raw).decode()}
        elif path.startswith("/compare/"):
            base, head = path[len("/compare/"):].split("...")
            merge = f.run_git("merge-base", base, head)
            data = {"status": "identical" if base == head else "ahead" if merge == base else "diverged",
                    "merge_base_commit": {"sha": merge}, "total_commits": int(f.run_git("rev-list", "--count", base + ".." + head)),
                    "files": [{"filename": name, "status": "modified" if f.run_git("ls-tree", base, "--", name) else "added",
                               "sha": f.run_git("rev-parse", head + ":" + name), "changes": 1}
                              for name in f.run_git("diff", "--name-only", base, head).splitlines()]}
        else:
            raise AssertionError("Unexpected repository API path: " + path)
        return self.adjust(path, deepcopy(data))


class CMSDeliveryTests(unittest.TestCase):
    original_source = fixtures.RequestTests.original_source
    run_git = fixtures.RequestTests.run_git
    write = fixtures.RequestTests.write
    commit = fixtures.RequestTests.commit
    save_manifest = fixtures.RequestTests.save_manifest
    store = fixtures.RequestTests.store
    prepare = fixtures.RequestTests.prepare

    def setUp(self):
        fixtures.RequestTests.setUp(self)
        files, self.proof = self.prepare()
        files = delivery.with_receipt(self.root, files, self.proof, now=self.now)
        apply(self.root, files, expected_head=self.base)
        self.commit("isolated approved candidate")
        self.candidate = self.run_git("rev-parse", "HEAD")
        self.api = LocalAPI(self)

    def verify(self):
        return delivery.verify(self.candidate, self.api, now=self.now)

    def rewrite_receipt(self, mutate):
        record = json.loads((self.root / delivery.FILE).read_bytes())
        mutate(record)
        self.write(delivery.FILE, encoded(record))
        self.commit("isolated altered receipt")
        self.candidate = self.run_git("rev-parse", "HEAD")

    def test_live_request_binds_exact_approved_article_and_media_without_writes(self):
        before_refs = self.run_git("show-ref")
        result = self.verify()
        self.assertEqual(result, {"sha": self.candidate, "activeRequests": 1,
                                 "authorIntentVerified": True, "candidatePayloadVerified": True, "published": False})
        self.assertEqual(self.api.calls.count("/git/ref/heads/drafts/article"), 2)
        self.assertEqual(self.run_git("show-ref"), before_refs)
        self.assertEqual(self.run_git("status", "--porcelain"), "")

    def test_actual_api_request_bytes_and_git_proof_pass_both_delivery_engines(self):
        self.verify()
        self.node_verify_snapshot()

    def node_verify_snapshot(self):
        responses = {path: self.api.get(path) for path in list(dict.fromkeys(self.api.calls))}
        helper = Path(__file__).resolve().parent / "_cms_delivery.cjs"
        code = "const fs=require('node:fs'),v=require(process.argv[1]);const i=JSON.parse(fs.readFileSync(0,'utf8'));v.verifyLiveIntent(i.sha,async p=>i.responses[p],i.now).then(r=>console.log(JSON.stringify(r))).catch(()=>process.exitCode=1);"
        result = subprocess.run(["node", "-e", code, str(helper)], input=json.dumps({
            "sha": self.candidate, "responses": responses, "now": int(self.now.timestamp() * 1000)}),
            capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["activeRequests"], 1)

    def test_missing_inline_content_uses_exact_blob_for_both_delivery_engines(self):
        self.api.adjust = lambda path, data: {**data, "encoding": "none", "content": ""} if path.startswith("/contents/") else data
        self.assertEqual(self.verify()["activeRequests"], 1)
        self.node_verify_snapshot()
        self.assertTrue(any(path.startswith("/git/blobs/") for path in self.api.calls))

    def test_large_image_and_article_transport_are_bounded_and_hash_checked(self):
        for raw in (b"GIF89a" + b"x" * 1_100_000, b"<html><p>" + b"x" * 1_100_000 + b"</p></html>"):
            blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            path = "blog/article.html" if raw.startswith(b"<html>") else "blog/images/article/" + hashlib.sha256(raw).hexdigest() + ".gif"
            metadata = {"sha": blob, "size": len(raw), "type": "file", "path": path, "encoding": "none", "content": ""}
            payload = {"sha": blob, "size": len(raw), "encoding": "base64", "content": base64.b64encode(raw).decode()}
            calls = []
            def get(url):
                calls.append(url)
                self.assertIn(url, ["/contents/" + path + "?ref=" + self.candidate, "/git/blobs/" + blob])
                return metadata if url.startswith("/contents/") else payload
            api = SimpleNamespace(get=get)
            self.assertEqual(delivery.github_file(api, path, self.candidate, 1_500_000), (blob, raw))
            self.assertEqual(len(calls), 2)
            for changes in ({"sha": "b" * 40}, {"size": len(raw) - 1}, {"size": True}, {"encoding": "none"}, {"content": payload["content"][:-4]}):
                invalid = {**payload, **changes}
                api.get = lambda url: metadata if url.startswith("/contents/") else invalid
                with self.subTest(changes=tuple(changes)), self.assertRaises(ValueError):
                    delivery.github_file(api, path, self.candidate, 1_500_000)
            with self.assertRaises(ValueError):
                delivery.github_file(SimpleNamespace(get=get), path, self.candidate, 1_000_000)

    def test_empty_receipt_does_not_claim_a_deployment(self):
        self.rewrite_receipt(lambda value: value.update(requests=[]))
        result = self.verify()
        self.assertEqual(result["activeRequests"], 0)
        self.assertFalse(result["published"])
        self.assertEqual(len(self.api.calls), 3)

    def test_compact_api_json_and_duplicate_properties(self):
        record = {"version": 1, "label": "核可"}
        raw = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        self.assertEqual(delivery.parse(raw), record)
        with self.assertRaisesRegex(ValueError, "canonical"):
            delivery.parse(raw, canonical=True)
        for raw in (b'{"version":1,"version":1}', b'{"inner":{"a":1,"a":2}}', b'{"x":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                delivery.parse(raw)

    def test_schema_limits_and_future_timestamps(self):
        valid = encoded({"version": 1, "requests": [self.proof]})
        self.assertEqual(delivery.receipts(valid, now=self.now), [self.proof])
        for changes in ({"version": True}, {"file": "../admin.html"}, {"repository": "evil/repo"},
                        {"approvedBy": "another"}, {"action": "publish"}, {"requestHead": "0" * 40},
                        {"manifestSha": "short"}, {"requestedAt": "2026-09-30T14:00:00.000Z"},
                        {"scheduledAt": "2026-09-30T11:00:00.000Z"},
                        {"sourceSha256": {"blog/article.html": "a" * 64, "api/other.js": "b" * 64}},
                        {"sourceSha256": {"blog/article.html": "a" * 63}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                delivery.receipts(encoded({"version": 1, "requests": [{**self.proof, **changes}]}), now=self.now)
        for value in ({"version": True, "requests": []}, {"version": 1, "requests": [self.proof] * 2},
                      {"version": 1, "requests": [self.proof] * 21}, {"version": 1, "requests": [], "extra": True}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                delivery.receipts(encoded(value), now=self.now)
        with self.assertRaises(ValueError):
            delivery.receipts(valid, now=self.now.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            delivery.parse(b"x" * (delivery.MAX_BYTES + 1))

    def test_schedule_must_be_due_and_within_one_year(self):
        proof = {**self.proof, "action": "schedule", "scheduledAt": "2026-09-30T11:00:00.000Z"}
        self.assertEqual(delivery.receipts(encoded({"version": 1, "requests": [proof]}), now=self.now), [proof])
        for at in ("2026-09-30T13:00:00.000Z", proof["requestedAt"], "2028-09-30T11:00:00.000Z"):
            with self.subTest(at=at), self.assertRaises(ValueError):
                delivery.receipts(encoded({"version": 1, "requests": [{**proof, "scheduledAt": at}]}), now=self.now)

    def test_cancellation_or_newer_edit_invalidates_previously_green_candidate(self):
        self.verify()
        self.run_git("switch", "drafts/article")
        self.run_git("rm", ".cms-requests/article.json")
        self.commit("author withdraws request")
        self.run_git("switch", "main")
        with self.assertRaisesRegex(ValueError, "cancelled or superseded"):
            self.verify()

    def test_cancellation_during_validation_is_rechecked(self):
        counts = []
        def move(path, data):
            if path == "/git/ref/heads/drafts/article":
                counts.append(path)
                if len(counts) == 2:
                    data["object"]["sha"] = "b" * 40
            return data
        self.api.adjust = move
        with self.assertRaisesRegex(ValueError, "cancelled or superseded"):
            self.verify()
        self.assertEqual(len(counts), 2)

    def test_candidate_html_or_image_change_needs_new_preparation_evidence(self):
        for path in ("blog/article.html", self.image_path):
            with self.subTest(path=path):
                original = (self.root / path).read_bytes()
                self.write(path, original + b"changed")
                self.commit("candidate changed")
                self.candidate = self.run_git("rev-parse", "HEAD")
                with self.assertRaisesRegex(ValueError, "candidate payload"):
                    self.verify()
                self.write(path, original)
                self.commit("restore isolated payload")
                self.candidate = self.run_git("rev-parse", "HEAD")

    def test_rewriting_digest_cannot_approve_new_clinical_prose(self):
        changed = self.content + b"<p>unapproved</p>"
        self.write("blog/article.html", changed)
        self.rewrite_receipt(lambda value: value["requests"][0]["sourceSha256"].update({
            "blog/article.html": hashlib.sha256(changed).hexdigest()}))
        with self.assertRaisesRegex(ValueError, "different from the approved"):
            self.verify()

    def test_missing_or_added_approved_assets_are_rejected(self):
        for added in (False, True):
            with self.subTest(added=added):
                proof = deepcopy(self.proof)
                if added:
                    proof["sourceSha256"]["blog/images/article/" + "a" * 64 + ".png"] = "b" * 64
                else:
                    del proof["sourceSha256"][self.image_path]
                self.rewrite_receipt(lambda value: value.update(requests=[proof]))
                with self.assertRaisesRegex(ValueError, "lost or added"):
                    self.verify()

    def test_invalid_immutable_blob_evidence_never_passes(self):
        for updates in ({"encoding": "utf8"}, {"type": "symlink"}, {"size": True},
                        {"size": 3_000_000}, {"content": "%%%"}, {"sha": "b" * 40}):
            with self.subTest(updates=updates):
                self.api.adjust = lambda path, data: {**data, **updates} if path.startswith("/contents/") else data
                with self.assertRaises(ValueError):
                    self.verify()

    def test_contents_api_cannot_hide_symlink_executable_or_truncated_git_tree(self):
        for mode in ("120000", "100755", "040000"):
            def alter(path, data):
                if path.startswith("/git/trees/"):
                    for entry in data["tree"]:
                        if entry["path"] == ".cms-requests/article.json":
                            entry["mode"] = mode
                return data
            self.api.adjust = alter
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "ordinary"):
                self.verify()
        for truncated in (True, None, 0):
            self.api.adjust = lambda path, data: {**data, "truncated": truncated} if path.startswith("/git/trees/") else data
            with self.subTest(truncated=truncated), self.assertRaisesRegex(ValueError, "incomplete"):
                self.verify()

    def test_request_diff_cannot_claim_removed_renamed_or_different_blob(self):
        for changes in ({"status": "removed"}, {"status": "renamed"}, {"sha": "a" * 40},
                        {"changes": 0}, {"changes": True}, {"previous_filename": "unrelated.txt"}):
            def alter(path, data):
                if path == "/compare/" + self.saved + "..." + self.head:
                    data["files"][0].update(changes)
                return data
            self.api.adjust = alter
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "ordinary added/modified"):
                self.verify()

    def test_remote_identity_parent_compare_and_manifest_are_not_trusted_blindly(self):
        mutations = [
            ("/git/ref/heads/", lambda data: {**data, "ref": "refs/heads/main"}),
            ("/git/commits/", lambda data: {**data, "parents": []}),
            ("/compare/", lambda data: {**data, "status": "diverged"}),
            ("/compare/", lambda data: {**data, "files": [{"filename": "admin.html"}]} if data["total_commits"] == 1 and data["merge_base_commit"]["sha"] == self.saved else data),
        ]
        for prefix, mutate in mutations:
            with self.subTest(prefix=prefix):
                self.api.adjust = lambda path, data: mutate(data) if path.startswith(prefix) else data
                with self.assertRaises(ValueError):
                    self.verify()

    def test_wrong_request_or_manifest_blob_sha_is_rejected(self):
        for field in ("requestBlobSha", "manifestSha", "articleBlobSha", "baseSha", "draftHead", "preparedAgainst"):
            with self.subTest(field=field):
                self.rewrite_receipt(lambda value: value.update(requests=[{**self.proof, field: "b" * 40}]))
                with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                    self.verify()

    def test_existing_receipt_cannot_be_silently_replaced(self):
        before = (self.root / delivery.FILE).read_bytes()
        with self.assertRaisesRegex(ValueError, "retirement"):
            delivery.with_receipt(self.root, {"blog/article.html": self.content}, self.proof, now=self.now)
        self.assertEqual((self.root / delivery.FILE).read_bytes(), before)

    def test_unpublish_binds_indexing_patch_and_rejects_unfinished_clinical_prose(self):
        self.run_git("reset", "--hard", self.base)  # Disposable fixture only.
        self.request.update(action="unpublish", contentApproved=False)
        self.store(amend=True)
        files, self.proof = self.prepare()
        apply(self.root, delivery.with_receipt(self.root, files, self.proof, now=self.now), expected_head=self.base)
        self.commit("isolated visibility candidate")
        self.candidate = self.run_git("rev-parse", "HEAD")
        self.assertEqual(self.verify()["activeRequests"], 1)
        changed = files["blog/article.html"] + b"<p>unfinished new clinical text</p>"
        self.write("blog/article.html", changed)
        self.rewrite_receipt(lambda value: value["requests"][0]["sourceSha256"].update({
            "blog/article.html": hashlib.sha256(changed).hexdigest()}))
        with self.assertRaisesRegex(ValueError, "changed published prose"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
