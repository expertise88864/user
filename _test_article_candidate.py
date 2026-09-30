"""Actual temporary Git histories; no user files, tokens or remote writes."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
import unittest

from _prepare_article_candidate import apply, plan


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run_git("init", "-b", "main")
        self.run_git("config", "user.name", "Fixture")
        self.run_git("config", "user.email", "fixture@example.invalid")
        self.original = getattr(self, "original_source", b"<html><h1>Original</h1></html>")
        self.write("blog/article.html", self.original)
        self.write("blog/blog-shared.js", b"var DN={}; DN.ARTICLES = [{slug:'article',title:'Original',title_en:'Original'}];\n")
        self.write("unchanged.txt", b"Keep source")
        self.commit("main baseline")
        self.base = self.run_git("rev-parse", "HEAD").strip()
        self.base_blob = self.run_git("rev-parse", "HEAD:blog/article.html").strip()
        self.run_git("switch", "-c", "drafts/article")
        self.slug = "article"
        self.image = b"GIF89a\x01\x00\x01\x00"
        self.image_path = "blog/images/article/" + hashlib.sha256(self.image).hexdigest() + ".gif"
        self.write(self.image_path, self.image)
        self.content = ('<html><h1>修改</h1><p>最新草稿</p><img src="/' + self.image_path + '"></html>').encode()
        self.write("blog/article.html", self.content)
        self.write("unchanged.txt", b"Unrelated dangerous branch change")
        self.write("api/unrelated.js", b"Unrelated API change")
        self.commit("draft source")
        self.blob = self.run_git("rev-parse", "HEAD:blog/article.html").strip()
        self.asset_sha = self.run_git("rev-parse", "HEAD:" + self.image_path).strip()
        self.record = {"version": 1, "file": "blog/article.html", "baseMain": self.base,
                       "baseSha": self.base_blob, "blobSha": self.blob, "status": "draft",
                       "assets": [{"path": self.image_path, "sha": self.asset_sha, "size": len(self.image)}], "metadata": None}
        self.save_manifest()
        self.head = self.run_git("rev-parse", "HEAD").strip()
        self.run_git("switch", "main")

    def run_git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.PIPE).decode().strip()

    def write(self, path, content):
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    def commit(self, message):
        self.run_git("add", "-A")
        self.run_git("commit", "-m", message)

    def save_manifest(self):
        self.write(".cms-drafts/" + self.slug + ".json", json.dumps(self.record).encode())
        self.commit("draft manifest")

    def amend_record(self, **changes):
        self.run_git("switch", "drafts/article")
        self.record.update(changes)
        self.save_manifest()
        self.head = self.run_git("rev-parse", "HEAD").strip()
        self.run_git("switch", "main")

    def prepare(self):
        return plan(self.root, self.head, self.record["file"], self.blob)

    def assert_rejected_clean(self):
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            self.prepare()
        self.assertEqual(self.run_git("status", "--porcelain"), "")
        self.assertEqual((self.root / "unchanged.txt").read_bytes(), b"Keep source")

    def test_extracts_only_article_and_manifest_media_without_merge_or_refs(self):
        old_refs = self.run_git("show-ref")
        files = self.prepare()
        self.assertEqual(set(files), {"blog/article.html", self.image_path})
        apply(self.root, files)
        self.assertEqual((self.root / "blog/article.html").read_bytes(), self.content)
        self.assertEqual((self.root / self.image_path).read_bytes(), self.image)
        self.assertFalse((self.root / "api/unrelated.js").exists())
        self.assertFalse((self.root / ".cms-drafts/article.json").exists())
        self.assertEqual((self.root / "unchanged.txt").read_bytes(), b"Keep source")
        self.assertEqual(self.run_git("show-ref"), old_refs)

    def test_newer_unrelated_main_change_is_preserved(self):
        self.write("unchanged.txt", b"New main")
        self.commit("new unrelated main")
        apply(self.root, self.prepare())
        self.assertEqual((self.root / "unchanged.txt").read_bytes(), b"New main")

    def test_main_article_conflict_stops_before_any_write(self):
        self.write("blog/article.html", b"<html><h1>New published edit</h1></html>")
        self.commit("changed main article")
        self.assert_rejected_clean()

    def test_stale_queued_blob_rejected(self):
        self.blob = "0" * 40
        self.assert_rejected_clean()

    def test_missing_blob_or_tree_base_cannot_be_treated_as_a_commit(self):
        tree = self.run_git("rev-parse", self.base + "^{tree}")
        for base_main in ("a" * 40, self.blob, tree):
            with self.subTest(base_main=base_main):
                self.amend_record(baseMain=base_main)
                with self.assertRaisesRegex(ValueError, "not an available commit"):
                    self.prepare()
                self.assertEqual(self.run_git("status", "--porcelain"), "")
                self.assertEqual((self.root / "blog/article.html").read_bytes(), self.original)

    def test_legacy_manifest_does_not_get_guessed_or_merged(self):
        self.run_git("switch", "drafts/article")
        self.run_git("rm", ".cms-drafts/article.json")
        self.commit("legacy draft")
        self.head = self.run_git("rev-parse", "HEAD")
        self.run_git("switch", "main")
        self.assert_rejected_clean()

    def test_bad_media_digest_size_and_duplicate_paths_preserve_destination(self):
        for assets in ([{**self.record["assets"][0], "size": 999}], self.record["assets"] * 2,
                       [{**self.record["assets"][0], "path": "../escape.gif"}]):
            with self.subTest(assets=assets):
                self.amend_record(assets=assets)
                self.assert_rejected_clean()

    def test_dirty_workspace_is_not_overwritten(self):
        self.write("blog/article.html", b"User local edit")
        with self.assertRaisesRegex(ValueError, "clean"):
            self.prepare()
        self.assertEqual((self.root / "blog/article.html").read_bytes(), b"User local edit")

    def test_new_input_between_validation_and_apply_is_preserved(self):
        files = self.prepare()
        self.write("blog/article.html", b"New user input")
        with self.assertRaisesRegex(ValueError, "changed after validation"):
            apply(self.root, files)
        self.assertEqual((self.root / "blog/article.html").read_bytes(), b"New user input")
        self.assertFalse((self.root / self.image_path).exists())

    def test_new_commit_between_validation_and_apply_requires_revalidation(self):
        files = self.prepare()
        self.write("unchanged.txt", b"New committed source")
        self.commit("another local change")
        with self.assertRaisesRegex(ValueError, "revision changed"):
            apply(self.root, files, expected_head=self.base)
        self.assertEqual((self.root / "blog/article.html").read_bytes(), self.original)

    def test_new_article_adds_only_safe_catalog_entry_and_source(self):
        self.run_git("switch", "drafts/article")
        self.slug = "new-patient-page"
        source = '<html><h1 data-zh="新的文章">新的文章<br>副標</h1><p>作者自己的草稿</p></html>'
        self.write("blog/" + self.slug + ".html", source.encode())
        self.commit("new article")
        self.blob = self.run_git("rev-parse", "HEAD:blog/" + self.slug + ".html")
        self.record.update(file="blog/" + self.slug + ".html", baseSha=None, blobSha=self.blob, assets=[],
                           metadata={"title_en": "Author's title", "tag": "標籤", "tag_en": "Topic", "cat": "note", "date": "2026-09-30"})
        self.save_manifest()
        self.head = self.run_git("rev-parse", "HEAD")
        self.run_git("switch", "main")
        files = self.prepare()
        self.assertEqual(set(files), {"blog/new-patient-page.html", "blog/blog-shared.js"})
        apply(self.root, files)
        from _sync_hub_catalog import load_catalog
        items = load_catalog(self.root)
        self.assertEqual(items[0]["title"], "新的文章")
        self.assertEqual(items[0]["title_en"], "Author's title")
        self.assertEqual(items[1]["slug"], "article")
        # The actual feed/catalog consumers must see the new entry, including
        # JS string semantics for apostrophes instead of truncating literals.
        import _gen_feeds
        from unittest.mock import patch
        with patch.object(_gen_feeds, "ROOT", self.root):
            parsed = _gen_feeds.parse_article_catalog()
        self.assertEqual(parsed[self.slug]["title"], "新的文章")
        self.assertEqual(parsed[self.slug]["cat"], "note")

    def test_catalog_strings_preserve_apostrophes_and_literal_escape_sequences(self):
        from _prepare_article_candidate import catalog_literal
        from _sync_hub_catalog import load_catalog
        import _gen_feeds
        from unittest.mock import patch
        value = {"slug": "article", "title": "病人的 '問題' \\n", "title_en": "Author's \\\\ title",
                 "tag": "Topic's tag", "tag_en": "Topic", "cat": "rx", "date": "2026-09-30"}
        self.write("blog/blog-shared.js", ("DN.ARTICLES = [" + catalog_literal(value) + "];\n").encode())
        self.assertEqual(load_catalog(self.root), [value])
        with patch.object(_gen_feeds, "ROOT", self.root):
            self.assertEqual(_gen_feeds.parse_article_catalog()["article"]["title"], value["title"])

    def test_wrong_file_revision_and_traversal_fail_before_reading(self):
        for file in ("../admin.html", "blog/index.html", "blog/article.html/other"):
            with self.subTest(file=file), self.assertRaises(ValueError):
                plan(self.root, self.head, file, self.blob)
        with self.assertRaises(ValueError):
            plan(self.root, "drafts/article", "blog/article.html", self.blob)


if __name__ == "__main__":
    unittest.main()
