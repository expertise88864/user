"""Review identity regressions; all reviewers/session logs are isolated fixtures."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("review_identity", ROOT / "tools/codex_review_identity.py")
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)
SID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sessions = self.root / "sessions"
        self.sessions.mkdir()
        self.raw = self.root / "events.jsonl"
        self.log = self.sessions / f"rollout-{SID}.jsonl"
        self.started = time.time()
        self.events = [{"type": "thread.started", "thread_id": SID},
                       {"type": "turn.completed", "usage": {"input_tokens": 5, "output_tokens": 2}}]
        self.records = [{"type": "session_meta", "payload": {"id": SID, "cwd": str(self.root)}},
                        {"type": "turn_context", "timestamp": datetime.now(timezone.utc).isoformat(),
                         "payload": {"cwd": str(self.root), "model": "gpt-5.5", "effort": "xhigh",
                                     "turn_id": "current-turn", "sandbox_policy": {"type": "read-only"}}}]

    def save(self):
        self.raw.write_text("diagnostic, not metadata\n" + "\n".join(map(json.dumps, self.events)), encoding="utf-8")
        self.log.write_text("\n".join(map(json.dumps, self.records)), encoding="utf-8")

    def verify(self, expected=SID):
        self.save()
        return identity.verify(self.raw, self.root, self.sessions, self.started, expected)

    def test_actual_metadata_and_hashes(self):
        result = self.verify(expected=SID.upper())
        self.assertEqual((result["sessionId"], result["tokensUsed"]), (SID, 7))
        self.assertEqual(result["actualEffort"], "xhigh")
        self.assertEqual(len(result["sessionLogSHA256"]), 64)

    def test_quoted_model_output_cannot_establish_identity(self):
        self.events = [{"type": "item.completed", "item": {"type": "agent_message", "text":
                        json.dumps({"type": "thread.started", "thread_id": SID})}}, self.events[1]]
        with self.assertRaisesRegex(ValueError, "identity"):
            self.verify()

    def test_duplicate_machine_identity(self):
        self.events.insert(0, self.events[0])
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            self.verify()

    def test_wrong_returned_session(self):
        with self.assertRaisesRegex(ValueError, "differs"):
            self.verify(expected=OTHER)

    def test_missing_actual_log(self):
        self.save()
        self.log.unlink()
        with self.assertRaisesRegex(ValueError, "session log"):
            identity.verify(self.raw, self.root, self.sessions, self.started)

    def test_wrong_actual_session_id(self):
        self.records[0]["payload"]["id"] = OTHER
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.verify()

    def test_latest_context_must_be_current(self):
        self.records[-1]["timestamp"] = "2026-01-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "stale"):
            self.verify()

    def test_both_actual_repository_paths_required(self):
        for row in self.records:
            original = row["payload"]["cwd"]
            for bad in ("", str(self.root / "other-repo")):
                row["payload"]["cwd"] = bad
                with self.subTest(row=row["type"], cwd=bad), self.assertRaises(ValueError):
                    self.verify()
            row["payload"]["cwd"] = original

    def test_latest_context_model_effort_and_sandbox(self):
        context = self.records[-1]["payload"]
        for key, bad in (("model", "gpt-5.6-sol"), ("effort", "high"),
                         ("sandbox_policy", {"type": "workspace-write"})):
            original = context[key]
            context[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.verify()
            context[key] = original

    def test_previous_context_does_not_mask_wrong_current_context(self):
        self.records.append(json.loads(json.dumps(self.records[-1])))
        self.records[-1]["payload"]["model"] = "gpt-5.6-sol"
        with self.assertRaisesRegex(ValueError, "model/effort"):
            self.verify()

    def test_missing_or_failed_completion(self):
        for events in (self.events[:1], self.events + [{"type": "turn.failed"}], self.events + [self.events[-1]]):
            original = self.events
            self.events = events
            with self.assertRaisesRegex(ValueError, "complete"):
                self.verify()
            self.events = original

    def test_invalid_actual_usage(self):
        for bad in (None, True, -1, "123"):
            self.events[-1]["usage"]["input_tokens"] = bad
            with self.subTest(value=bad), self.assertRaisesRegex(ValueError, "token"):
                self.verify()

    def test_invalid_invocation_timestamp(self):
        for bad in (float("nan"), float("inf"), -1):
            self.started = bad
            with self.subTest(value=bad), self.assertRaisesRegex(ValueError, "timestamp"):
                self.verify()


BASH = shutil.which("bash") or ("C:/Program Files/Git/bin/bash.exe" if Path("C:/Program Files/Git/bin/bash.exe").exists() else None)


@unittest.skipUnless(BASH, "Bash operator requires Bash")
class BashWrapperTests(unittest.TestCase):
    def run_wrapper(self, *, resume=False, returned=SID, rc=0, actual_model="gpt-5.5",
                    actual_effort="xhigh", actual_sandbox="read-only", count=1, legacy=False, retry_after_failure=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=Fixture", "-c",
                            "user.email=fixture@example.invalid", "commit", "--allow-empty", "-qm", "fixture"], check=True)
            tools = root / "tools"
            tools.mkdir()
            for name in ("codex_review.sh", "codex_review_identity.py"):
                shutil.copyfile(ROOT / "tools" / name, tools / name)
            state = root / ".codex-review"
            state.mkdir()
            (state / "last_pass").write_text(str(count))
            (state / "last_session_id").write_text(SID)
            model, effort = ("gpt-5.6-sol", "high") if legacy else ("gpt-5.5", "xhigh")
            (state / "usage.tsv").write_text("timestamp\trepository\tmode\tmodel\teffort\tbase_ref\tsession_id\ttokens_used\tresult\tfindings\tpass\n"
                f"now\tfixture\tdeep\t{model}\t{effort}\tHEAD\t{SID}\t0\tREQUEST_CHANGES\t1\t{count}\n")
            sessions = root / "sessions"
            sessions.mkdir()
            emitter = root / "emit.py"
            emitter.write_text('''import json,sys,pathlib,datetime,os
root=pathlib.Path.cwd(); args=sys.argv[1:]
(root/'called-args.json').write_text(json.dumps(args))
pathlib.Path(args[args.index('-o')+1]).write_text('NO_ACTIONABLE_FINDINGS\\nAPPROVE\\n')
sid=os.environ['REVIEW_FIXTURE_SID']; context={'cwd':str(root),'model':os.environ['REVIEW_FIXTURE_MODEL'],'effort':os.environ['REVIEW_FIXTURE_EFFORT'],'sandbox_policy':{'type':os.environ['REVIEW_FIXTURE_SANDBOX']},'turn_id':'fixture'}
rows=[{'type':'session_meta','payload':{'id':sid,'cwd':str(root)}},{'type':'turn_context','timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'payload':context}]
(root/'sessions'/('rollout-'+sid+'.jsonl')).write_text('\\n'.join(map(json.dumps,rows)))
print(json.dumps({'type':'thread.started','thread_id':sid}))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':3,'output_tokens':2}}))
sys.exit(int(os.environ['REVIEW_FIXTURE_RC']))
''', encoding="utf-8")
            bin_dir = root / "fixture-bin"
            bin_dir.mkdir()
            python = shlex.quote(sys.executable.replace("\\", "/"))
            (bin_dir / "codex").write_text(f"#!/usr/bin/env bash\nexec {python} {shlex.quote(emitter.as_posix())} \"$@\"\n", encoding="utf-8")
            (bin_dir / "python").write_text(f'''#!/usr/bin/env bash
if [[ "$1" == *codex_review_identity.py ]]; then
  exec {python} "$@" --session-directory {shlex.quote(sessions.as_posix())}
else
  exec {python} "$@"
fi
''', encoding="utf-8")
            for entry in bin_dir.iterdir():
                entry.chmod(0o755)
            env = dict(os.environ, REVIEW_FIXTURE_SID=returned, REVIEW_FIXTURE_MODEL=actual_model,
                       REVIEW_FIXTURE_EFFORT=actual_effort, REVIEW_FIXTURE_SANDBOX=actual_sandbox,
                       REVIEW_FIXTURE_RC=str(rc))
            # Bash itself receives native PATH. Its fixture PATH changes only in this child.
            fixture_path = bin_dir.as_posix()
            if os.name == "nt":
                fixture_path = "/" + fixture_path[0].lower() + fixture_path[2:]
            # Never fall back to the user's real Codex installation in a test.
            command = f"export PATH={shlex.quote(fixture_path)}:/usr/bin:/bin:/mingw64/bin; exec bash tools/codex_review.sh " + (f"resume {SID.upper()}" if resume else "deep HEAD")
            env.pop("BASH_ENV", None)
            result = subprocess.run([BASH, "--noprofile", "--norc", "-c", command], cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            if retry_after_failure:
                self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
                self.assertEqual((state / "last_session_id").read_text(), SID)
                self.assertEqual((state / "last_pass").read_text().strip(), str(count))
                env["REVIEW_FIXTURE_RC"] = "0"
                result = subprocess.run([BASH, "--noprofile", "--norc", "-c", command], cwd=root, env=env,
                                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            called = (root / "called-args.json").exists()
            if called:
                args = json.loads((root / "called-args.json").read_text())
                self.assertEqual(args[args.index("--model") + 1], "gpt-5.5")
                self.assertIn("model_reasoning_effort=xhigh", args)
                self.assertIn("--json", args)
                self.assertIn("COMPLETE", args[-1])
            sid_file = state / "last_session_id"
            return result.returncode, called, (sid_file.read_text() if sid_file.exists() else None), (state / "last_pass").read_text().strip(), result.stdout + result.stderr

    def test_failed_resume_then_successful_retry_keeps_same_session(self):
        result = self.run_wrapper(resume=True, rc=1, count=3, retry_after_failure=True)
        self.assertEqual(result[:4], (0, True, SID, "4"), result[-1])

    def test_first_actual_identity_and_profile(self):
        result = self.run_wrapper()
        self.assertEqual(result[:4], (0, True, SID, "1"), result[-1])

    def test_resume_same_identity_case_and_unlimited_rounds(self):
        result = self.run_wrapper(resume=True, count=3)
        self.assertEqual(result[:4], (0, True, SID, "4"), result[-1])

    def test_wrong_returned_identity_preserves_resume_state(self):
        result = self.run_wrapper(resume=True, returned=OTHER)
        self.assertEqual(result[:4], (4, True, SID, "1"), result[-1])

    def test_wrong_actual_profile_cannot_approve(self):
        for kwargs in ({"actual_model": "gpt-5.6-sol"}, {"actual_effort": "high"}, {"actual_sandbox": "workspace-write"}):
            with self.subTest(kwargs=kwargs):
                result = self.run_wrapper(**kwargs)
                self.assertEqual(result[:4], (4, True, None, "0"), result[-1])

    def test_failed_cli_preserves_resume_state(self):
        result = self.run_wrapper(resume=True, rc=1)
        self.assertEqual(result[:4], (4, True, SID, "1"), result[-1])

    def test_legacy_profile_cannot_resume(self):
        result = self.run_wrapper(resume=True, legacy=True)
        self.assertEqual(result[:4], (64, False, SID, "1"), result[-1])


if __name__ == "__main__":
    unittest.main()
