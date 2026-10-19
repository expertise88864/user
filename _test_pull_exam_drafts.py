"""Tests for _pull_exam_drafts.py (temp git repositories only) and for the
json.dumps format identity that the admin exam editor depends on."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import _pull_exam_drafts as pull

ROOT = Path(__file__).resolve().parent
BRANCH = pull.BRANCH
NOTE_17 = '<section class="ex-note" id="a">\n<h2>One</h2>\n<p>old</p>\n</section>\n'
NOTE_24 = '<section class="ex-note" id="b">\n<h2>Two</h2>\n<p>old</p>\n</section>\n'


def entry(summary: str) -> dict:
    return {"summary": summary, "items": [{"key": "A", "label": "x", "ok": True, "text": "t " + summary, "refs": [[1, "2-3"], ["M", "4"]]}]}


def base_explanations() -> dict:
    return {"101-01": entry("one"), "101-02": entry("two"), "101-03": entry("three")}


def run(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.test", "-c", "commit.gpgsign=false", *args],
                            cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise AssertionError(f"git {args} failed: {result.stderr}")
    return result.stdout


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


class Scenario:
    """origin (bare) + a maintainer checkout; the cloud writer is a second clone."""

    def __init__(self, tmp: Path, autocrlf: str = "false"):
        self.tmp = tmp
        self.origin = tmp / "origin.git"
        run(tmp, "init", "--bare", "-b", "main", str(self.origin))
        seed = tmp / "seed"
        run(tmp, "clone", str(self.origin), str(seed))
        run(seed, "checkout", "-b", "main")
        write(seed / "data/exam/notes/fitz-17.frag", NOTE_17)
        write(seed / "data/exam/notes/fitz-24.frag", NOTE_24)
        write(seed / pull.EXPLANATIONS, pull.dumps(base_explanations()))
        run(seed, "add", "-A"); run(seed, "commit", "-m", "base"); run(seed, "push", "origin", "main")
        self.base = run(seed, "rev-parse", "HEAD").strip()
        self.seed = seed
        self.work = tmp / "work"
        run(tmp, "-c", f"core.autocrlf={autocrlf}", "clone", "-b", "main", str(self.origin), str(self.work))
        run(self.work, "config", "core.autocrlf", autocrlf)

    def draft(self, notes: dict[int, str] | None = None, explanations: dict[str, dict] | None = None, base: str | None = None,
              manifest: dict | None = None, expl_text: str | None = None) -> None:
        cloud = self.tmp / "cloud"
        run(self.tmp, "clone", str(self.origin), str(cloud))
        run(cloud, "checkout", "-b", BRANCH, base or self.base)
        for ch, text in (notes or {}).items():
            write(cloud / pull.note_path(ch), text)
        if explanations or expl_text:
            data = json.loads((cloud / pull.EXPLANATIONS).read_text(encoding="utf-8"))
            data.update(explanations or {})
            write(cloud / pull.EXPLANATIONS, expl_text if expl_text is not None else pull.dumps(data))
        record = manifest or {"version": 1, "baseMain": base or self.base, "updated": "2026-10-19T00:00:00.000Z",
                              "notes": sorted(notes or {}), "explanations": sorted(explanations or {})}
        write(cloud / pull.MANIFEST, json.dumps(record) + "\n")
        run(cloud, "add", "-A"); run(cloud, "commit", "-m", "draft"); run(cloud, "push", "origin", BRANCH)

    def main_commit(self, changes: dict[str, str]) -> None:
        run(self.seed, "pull", "origin", "main")
        for path, text in changes.items():
            write(self.seed / path, text)
        run(self.seed, "add", "-A"); run(self.seed, "commit", "-m", "main moves"); run(self.seed, "push", "origin", "main")
        run(self.work, "pull", "--ff-only", "origin", "main")

    def pull(self, **kwargs) -> tuple[int, str]:
        lines: list[str] = []
        code = pull.pull(self.work, out=lines.append, **kwargs)
        return code, "\n".join(lines)

    def text(self, path: str) -> str:
        return (self.work / path).read_bytes().decode("utf-8")

    def status(self) -> list[str]:
        return sorted(line[3:] for line in run(self.work, "status", "--porcelain").splitlines())


class PullTests(unittest.TestCase):
    def scenario(self, **kwargs) -> Scenario:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Scenario(Path(directory.name), **kwargs)

    def cleanup_line(self, output: str) -> list[str]:
        lines = [line.strip() for line in output.splitlines() if line.strip().startswith("git push")]
        self.assertEqual(len(lines), 1, output)
        return lines[0].split()

    def remote_head(self, s: Scenario) -> str:
        listing = run(s.work, "ls-remote", "--heads", "origin", BRANCH).strip()
        return listing.split()[0] if listing else ""

    def test_cleanup_deletes_the_branch_only_while_it_is_still_the_imported_head(self):
        s = self.scenario()
        s.draft(notes={17: NOTE_17.replace("old", "new")})
        code, output = s.pull()
        self.assertEqual(code, 0, output)
        imported = self.remote_head(s)
        self.assertEqual(len(imported), 40)
        self.assertIn(imported, output, "the imported branch head is printed")
        command = self.cleanup_line(output)
        self.assertEqual(command, ["git", "push", f"--force-with-lease=refs/heads/{BRANCH}:{imported}", "origin", "--delete", BRANCH])
        self.assertEqual(pull.cleanup_command("origin", imported), " ".join(command))
        # A newer draft is saved after the import: the printed delete is refused and the branch stays.
        cloud = s.tmp / "cloud"
        write(cloud / pull.note_path(24), NOTE_24.replace("old", "newer draft"))
        run(cloud, "add", "-A"); run(cloud, "commit", "-m", "draft 2"); run(cloud, "push", "origin", BRANCH)
        newer = self.remote_head(s)
        self.assertNotEqual(newer, imported)
        refused = subprocess.run(command, cwd=s.work, capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(refused.returncode, 0, "the lease must make the delete fail")
        self.assertEqual(self.remote_head(s), newer, "the newer draft is still on the remote")

    def test_cleanup_command_succeeds_when_nothing_was_saved_after_the_import(self):
        s = self.scenario()
        s.draft(notes={17: NOTE_17.replace("old", "new")})
        code, output = s.pull()
        self.assertEqual(code, 0, output)
        done = subprocess.run(self.cleanup_line(output), cwd=s.work, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.remote_head(s), "")

    def test_no_draft_branch_is_not_an_error(self):
        s = self.scenario()
        code, output = s.pull()
        self.assertEqual(code, 0); self.assertIn(BRANCH, output)
        self.assertEqual(s.status(), [])

    def test_applies_notes_and_listed_explanations(self):
        s = self.scenario()
        s.draft(notes={17: NOTE_17.replace("old", "new")}, explanations={"101-01": entry("edited")})
        code, output = s.pull()
        self.assertEqual(code, 0, output)
        self.assertEqual(s.text("data/exam/notes/fitz-17.frag"), NOTE_17.replace("old", "new"))
        self.assertEqual(s.text("data/exam/notes/fitz-24.frag"), NOTE_24)
        expected = base_explanations(); expected["101-01"] = entry("edited")
        self.assertEqual(s.text(pull.EXPLANATIONS), pull.dumps(expected))
        self.assertEqual(s.status(), ["data/exam/explanations.json", "data/exam/notes/fitz-17.frag"])
        self.assertIn("_gen_exam.py", output)
        # Nothing is committed or pushed.
        self.assertEqual(run(s.work, "rev-parse", "HEAD").strip(), s.base)
        # While the result is uncommitted a second run refuses; once committed it finds everything applied.
        self.assertEqual(s.pull()[0], 2)
        run(s.work, "add", "-A"); run(s.work, "commit", "-m", "integrate")
        code, output = s.pull()
        self.assertEqual(code, 0); self.assertIn("已是草稿內容", output)
        self.assertEqual(s.status(), [])

    def test_explanations_are_applied_onto_the_current_file_not_replaced(self):
        s = self.scenario()
        s.draft(explanations={"101-01": entry("edited")})
        # main edits a different question after the draft branch was created
        moved = base_explanations(); moved["101-02"] = entry("changed on main")
        s.main_commit({pull.EXPLANATIONS: pull.dumps(moved)})
        code, output = s.pull()
        self.assertEqual(code, 0, output)
        expected = dict(moved); expected["101-01"] = entry("edited")
        self.assertEqual(s.text(pull.EXPLANATIONS), pull.dumps(expected))
        self.assertEqual(json.loads(s.text(pull.EXPLANATIONS))["101-02"], entry("changed on main"))

    def test_conflicting_explanation_writes_nothing(self):
        s = self.scenario()
        s.draft(notes={17: NOTE_17.replace("old", "new")}, explanations={"101-01": entry("edited")})
        moved = base_explanations(); moved["101-01"] = entry("main also edited it")
        s.main_commit({pull.EXPLANATIONS: pull.dumps(moved)})
        before = s.text(pull.EXPLANATIONS)
        code, output = s.pull()
        self.assertEqual(code, 1); self.assertIn("101-01", output)
        self.assertEqual(s.text(pull.EXPLANATIONS), before)
        self.assertEqual(s.text("data/exam/notes/fitz-17.frag"), NOTE_17, "the clean note is not applied either")
        self.assertEqual(s.status(), [])

    def test_conflicting_note_writes_nothing(self):
        s = self.scenario()
        s.draft(notes={17: NOTE_17.replace("old", "new")}, explanations={"101-01": entry("edited")})
        s.main_commit({"data/exam/notes/fitz-17.frag": NOTE_17.replace("old", "elsewhere")})
        code, output = s.pull()
        self.assertEqual(code, 1); self.assertIn("Ch.17", output)
        self.assertEqual(s.text(pull.EXPLANATIONS), pull.dumps(base_explanations()))
        self.assertEqual(s.status(), [])

    def test_dirty_target_is_refused_but_unrelated_changes_are_fine(self):
        s = self.scenario()
        s.draft(notes={17: NOTE_17.replace("old", "new")})
        write(s.work / "data/exam/notes/fitz-17.frag", NOTE_17 + "local edit\n")
        code, output = s.pull()
        self.assertEqual(code, 2); self.assertIn("fitz-17.frag", output)
        self.assertEqual(s.text("data/exam/notes/fitz-17.frag"), NOTE_17 + "local edit\n")
        write(s.work / "data/exam/notes/fitz-17.frag", NOTE_17)
        write(s.work / "scratch.txt", "unrelated")
        write(s.work / "data/exam/notes/fitz-24.frag", NOTE_24 + "edit\n")
        self.assertEqual(s.pull()[0], 0)

    def test_dry_run_writes_nothing(self):
        s = self.scenario()
        s.draft(notes={17: NOTE_17.replace("old", "new")}, explanations={"101-01": entry("edited")})
        code, output = s.pull(dry_run=True)
        self.assertEqual(code, 0); self.assertIn("dry-run", output)
        self.assertEqual(s.status(), [])

    def test_format_mismatch_fails_closed(self):
        s = self.scenario()
        # The draft file is not in the exact json.dumps format.
        text = pull.dumps({**base_explanations(), "101-01": entry("edited")}) + "\n"
        s.draft(explanations={"101-01": entry("edited")}, expl_text=text)
        code, output = s.pull()
        self.assertEqual(code, 1); self.assertIn("json.dumps", output)
        self.assertEqual(s.status(), [])
        # The current file is not in that format.
        s2 = self.scenario()
        s2.draft(explanations={"101-01": entry("edited")})
        s2.main_commit({pull.EXPLANATIONS: pull.dumps(base_explanations()) + "\n"})
        code, output = s2.pull()
        self.assertEqual(code, 1); self.assertIn("json.dumps", output)

    def test_invalid_manifest_is_refused(self):
        s = self.scenario()
        s.draft(notes={17: NOTE_17.replace("old", "new")}, manifest={"version": 2, "baseMain": s.base, "updated": "x", "notes": [17], "explanations": []})
        code, output = s.pull()
        self.assertEqual(code, 1); self.assertIn(pull.MANIFEST, output)
        self.assertEqual(s.status(), [])

    def test_crlf_working_tree_keeps_its_line_endings(self):
        s = self.scenario(autocrlf="true")
        self.assertIn(b"\r\n", (s.work / pull.EXPLANATIONS).read_bytes())
        s.draft(notes={17: NOTE_17.replace("old", "new")}, explanations={"101-01": entry("edited")})
        code, output = s.pull()
        self.assertEqual(code, 0, output)
        raw = (s.work / pull.EXPLANATIONS).read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))
        self.assertEqual(raw.decode("utf-8").replace("\r\n", "\n"), pull.dumps({**base_explanations(), "101-01": entry("edited")}))
        self.assertEqual(s.status(), ["data/exam/explanations.json", "data/exam/notes/fitz-17.frag"])
        self.assertEqual(run(s.work, "diff", "--stat", "--", "data/exam/notes").count("fitz-17"), 1)


class JsonFormatIdentityTests(unittest.TestCase):
    """The editor serializes with JSON.stringify(data, null, 1); the pipeline writes
    json.dumps(data, indent=1, ensure_ascii=False). _test_exam_draft.cjs proves the JS
    side reproduces the committed bytes; this proves the Python side does."""

    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / "data/exam/explanations.json").read_bytes().decode("utf-8").replace("\r\n", "\n")

    def test_committed_file_is_exactly_json_dumps_output(self):
        data = json.loads(self.text)
        self.assertEqual(len(data), 750)
        self.assertEqual(pull.dumps(data), self.text)
        self.assertFalse(self.text.endswith("\n"))
        self.assertEqual(pull.parse_exact(self.text.encode("utf-8"), "x"), data)

    def test_replacing_one_entry_changes_only_that_entry(self):
        data = json.loads(self.text)
        qid = "101-02"
        data[qid]["summary"] += " (edited)"
        updated = pull.dumps(data)
        before, after = self.text.split("\n"), updated.split("\n")
        start = next(i for i, line in enumerate(before) if line.startswith(f' "{qid}": '))
        end = next(i for i in range(start + 1, len(before)) if before[i].startswith(' "'))
        tail = len(before) - end
        self.assertEqual(after[:start], before[:start])
        self.assertEqual(after[len(after) - tail:], before[end:])
        self.assertEqual(list(json.loads(updated)), list(json.loads(self.text)))


if __name__ == "__main__":
    unittest.main()
