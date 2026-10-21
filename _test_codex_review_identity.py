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
                         "payload": {"cwd": str(self.root), "model": "gpt-6.1-sol", "effort": "xhigh",
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

    def test_bom_tagged_utf16_events_preserve_actual_identity(self):
        for bom, encoding in ((b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be")):
            with self.subTest(encoding=encoding):
                self.save()
                payload = "diagnostic \u4e2d\u6587\n" + "\n".join(map(json.dumps, self.events))
                self.raw.write_bytes(bom + payload.encode(encoding))
                result = identity.verify(self.raw, self.root, self.sessions, self.started, SID)
                self.assertEqual((result["sessionId"], result["tokensUsed"]), (SID, 7))
                self.assertEqual(result["actualModel"], "gpt-6.1-sol")
                self.assertEqual(result["actualEffort"], "xhigh")

    def test_malformed_encoding_is_not_silently_trusted(self):
        for raw in (b"\xff", b"\xff\xfe{", b"\xfe\xff\x00"):
            with self.subTest(raw=raw):
                self.save()
                self.raw.write_bytes(raw)
                with self.assertRaises(UnicodeDecodeError):
                    identity.verify(self.raw, self.root, self.sessions, self.started, SID)

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell encoding contract")
    def test_windows_powershell_tee_event_log_keeps_identity(self):
        self.save()
        shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.assertTrue(shell.is_file())
        # No real reviewer runs. Exercise the actual shell's Tee-Object encoding
        # with isolated machine-event fixtures and the real identity verifier.
        lines = ",".join("'" + json.dumps(e).replace("'", "''") + "'" for e in self.events)
        command = "@(" + lines + ") | Tee-Object -FilePath $env:CD_REVIEW_ENCODING_TEST_LOG"
        env = dict(os.environ, CD_REVIEW_ENCODING_TEST_LOG=str(self.raw))
        result = subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-Command", command],
                                cwd=self.root, env=env, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.raw.read_bytes().startswith(b"\xff\xfe"))
        proof = identity.verify(self.raw, self.root, self.sessions, self.started, SID)
        self.assertEqual((proof["sessionId"], proof["tokensUsed"]), (SID, 7))

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
        for key, bad in (("model", "gpt-5.5"), ("effort", "high"),
                         ("sandbox_policy", {"type": "workspace-write"})):
            original = context[key]
            context[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.verify()
            context[key] = original

    def test_previous_context_does_not_mask_wrong_current_context(self):
        self.records.append(json.loads(json.dumps(self.records[-1])))
        self.records[-1]["payload"]["model"] = "gpt-5.5"
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
    def run_wrapper(self, *, resume=False, returned=SID, rc=0, actual_model="gpt-6.1-sol",
                    actual_effort="xhigh", actual_sandbox="read-only", count=1, legacy=False,
                    retry_after_failure=False, crlf=False, python3_only=False, from_subdir=False,
                    reviewed_head=None, pr_range=None, prev_tip=None, rebuttal=None,
                    full_from=None, verification=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            commit = ["git", "-C", str(root), "-c", "user.name=Fixture", "-c",
                      "user.email=fixture@example.invalid", "commit", "-qm"]
            subprocess.run(commit[:-1] + ["--allow-empty", "-qm", "fixture base"], check=True)
            self.fixture_base = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                                               text=True, check=True).stdout.strip()
            # The PR adds one source file and generated exam pages (sampled, not read in full).
            (root / "exam").mkdir()
            for name in ("src.py", "exam/a.html", "exam/b.html", "exam/c.html", "exam/d.html"):
                (root / name).write_text(name + "\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            subprocess.run(commit + ["fixture"], check=True)
            tools = root / "tools"
            tools.mkdir()
            for name in ("codex_review.sh", "codex_review_identity.py", "review_scope.py"):
                shutil.copyfile(ROOT / "tools" / name, tools / name)
            state = root / ".codex-review"
            state.mkdir()
            (state / "last_pass").write_text(str(count))
            (state / "last_session_id").write_text(SID)
            head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                                  text=True, check=True).stdout.strip()
            if reviewed_head is not None:
                (state / "last_reviewed_head").write_text(
                    {"head": head, "base": self.fixture_base}.get(reviewed_head, reviewed_head) + "\n")
            model, effort = ("gpt-6.1-sol", "high") if legacy else ("gpt-6.1-sol", "xhigh")
            (state / "usage.tsv").write_text("timestamp\trepository\tmode\tmodel\teffort\tbase_ref\tsession_id\ttokens_used\tresult\tfindings\tpass\n"
                f"now\tfixture\tdeep\t{model}\t{effort}\tHEAD\t{SID}\t0\tREQUEST_CHANGES\t1\t{count}\n",
                newline="\r\n" if crlf else "\n")
            sessions = root / "sessions"
            sessions.mkdir()
            emitter = root / "emit.py"
            emitter.write_text('''import json,sys,pathlib,datetime,os
root=pathlib.Path.cwd(); args=sys.argv[1:]
(root/'called-args.json').write_text(json.dumps(args))
(root/'called-env.txt').write_text(os.environ.get('GIT_CONFIG_PARAMETERS',''))
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
            (bin_dir / ("python3" if python3_only else "python")).write_text(f'''#!/usr/bin/env bash
if [[ "$1" == *codex_review_identity.py ]]; then
  exec {python} "$@" --session-directory {shlex.quote(sessions.as_posix())}
else
  exec {python} "$@"
fi
''', encoding="utf-8")
            if python3_only:
                (bin_dir / "python").write_text("#!/usr/bin/env bash\nexit 91\n", encoding="utf-8")
            for entry in bin_dir.iterdir():
                entry.chmod(0o755)
            env = dict(os.environ, REVIEW_FIXTURE_SID=returned, REVIEW_FIXTURE_MODEL=actual_model,
                       REVIEW_FIXTURE_EFFORT=actual_effort, REVIEW_FIXTURE_SANDBOX=actual_sandbox,
                       REVIEW_FIXTURE_RC=str(rc),
                       # The fixture `codex` on PATH, not the highest-version CLI on this machine.
                       CODEX_REVIEW_CLI="codex")
            env.pop("CODEX_REVIEW_TIP", None)
            env.pop("CODEX_REVIEW_BASE", None)
            for name in ("CODEX_REVIEW_PREV_TIP", "CODEX_REVIEW_REBUTTAL_FILE", "CODEX_REVIEW_FULL_RESUME",
                         "CODEX_REVIEW_VERIFICATION"):
                env.pop(name, None)
            if verification is not None:
                env["CODEX_REVIEW_VERIFICATION"] = verification
            if full_from is not None:
                env["CODEX_REVIEW_FULL_RESUME"] = full_from
            if rebuttal is not None:
                evidence = root / "rebuttal.txt"
                if rebuttal != "missing":
                    evidence.write_text(rebuttal, encoding="utf-8")
                env["CODEX_REVIEW_REBUTTAL_FILE"] = evidence.as_posix()
            if prev_tip is not None:
                env["CODEX_REVIEW_PREV_TIP"] = {"head": head, "base": self.fixture_base}.get(prev_tip, prev_tip)
            if pr_range is not None:
                # tools/pr_review.py names the exact PR head and its merge base.
                env["CODEX_REVIEW_TIP"] = head if pr_range == "head" else pr_range
                env["CODEX_REVIEW_BASE"] = self.fixture_base
            # Bash itself receives native PATH. Its fixture PATH changes only in this child.
            fixture_path = bin_dir.as_posix()
            if os.name == "nt":
                fixture_path = "/" + fixture_path[0].lower() + fixture_path[2:]
            # Never fall back to the user's real Codex installation in a test.
            command = f"export PATH={shlex.quote(fixture_path)}:/usr/bin:/bin:/mingw64/bin; "
            if python3_only:
                # Hide python discovery even on CI hosts that provide both names.
                command += 'command() { if [[ "$1" == -v && "$2" == python ]]; then return 1; fi; builtin command "$@"; }; export -f command; '
            # A PR first pass gets the merge base from tools/pr_review.py.
            first = f"deep {self.fixture_base}" if pr_range else "deep HEAD"
            command += "exec bash " + ("../tools/" if from_subdir else "tools/") + "codex_review.sh " + (f"resume {SID.upper()}" if resume else first)
            env.pop("BASH_ENV", None)
            cwd = root / "nested" if from_subdir else root
            cwd.mkdir(exist_ok=True)
            result = subprocess.run([BASH, "--noprofile", "--norc", "-c", command], cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            if result.returncode == 4:
                self.assertEqual((state / "usage.tsv").read_text().splitlines()[-1].split("\t")[8], "UNKNOWN")
            if retry_after_failure:
                self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
                self.assertEqual((state / "last_session_id").read_text(), SID)
                self.assertEqual((state / "last_pass").read_text().strip(), str(count))
                env["REVIEW_FIXTURE_RC"] = "0"
                result = subprocess.run([BASH, "--noprofile", "--norc", "-c", command], cwd=cwd, env=env,
                                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            called = (root / "called-args.json").exists()
            if called:
                args = json.loads((root / "called-args.json").read_text())
                self.assertEqual(args[args.index("--model") + 1], "gpt-6.1-sol")
                self.assertIn("model_reasoning_effort=xhigh", args)
                if os.name == "nt":
                    self.assertIn("windows.sandbox=unelevated", args)
                # Only this repository is marked safe, only for the review child.
                self.assertEqual((root / "called-env.txt").read_text(),
                                 "'safe.directory'='" + subprocess.run(
                                     ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                                     capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip() + "'")
                self.assertIn("--json", args)
                self.assertIn("End with exactly", args[-1])
                self.last_prompt = args[-1]
            reviewed = state / "last_reviewed_head"
            self.last_reviewed = reviewed.read_text().strip() if reviewed.exists() else None
            self.fixture_head = head
            sid_file = state / "last_session_id"
            return result.returncode, called, (sid_file.read_text() if sid_file.exists() else None), (state / "last_pass").read_text().strip(), result.stdout + result.stderr

    def test_resume_reads_powershell_crlf_ledger(self):
        result = self.run_wrapper(resume=True, crlf=True, count=3)
        self.assertEqual(result[:4], (0, True, SID, "4"), result[-1])

    def test_python3_only_first_and_resumed_pass(self):
        for resume in (False, True):
            with self.subTest(resume=resume):
                result = self.run_wrapper(resume=resume, python3_only=True)
                self.assertEqual(result[:4], (0, True, SID, "2" if resume else "1"), result[-1])

    def test_resume_from_subdirectory_keeps_repository_context(self):
        result = self.run_wrapper(resume=True, from_subdir=True)
        self.assertEqual(result[:4], (0, True, SID, "2"), result[-1])

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
        for kwargs in ({"actual_model": "gpt-5.5"}, {"actual_effort": "high"}, {"actual_sandbox": "workspace-write"}):
            with self.subTest(kwargs=kwargs):
                result = self.run_wrapper(**kwargs)
                self.assertEqual(result[:4], (4, True, None, "0"), result[-1])

    def test_failed_cli_preserves_resume_state(self):
        result = self.run_wrapper(resume=True, rc=1)
        self.assertEqual(result[:4], (4, True, SID, "1"), result[-1])

    def test_first_pass_records_reviewed_head(self):
        result = self.run_wrapper()
        self.assertEqual(result[:4], (0, True, SID, "1"), result[-1])
        self.assertEqual(self.last_reviewed, self.fixture_head)

    def test_resume_after_reviewed_ancestor_is_incremental(self):
        result = self.run_wrapper(resume=True, reviewed_head="head")
        self.assertEqual(result[:4], (0, True, SID, "2"), result[-1])
        self.assertIn("INCREMENTAL", self.last_prompt)
        self.assertIn(f"git diff {self.fixture_head} HEAD", self.last_prompt)
        self.assertNotIn("{{PREV_HEAD}}", self.last_prompt)
        self.assertEqual(self.last_reviewed, self.fixture_head)

    def test_resume_without_valid_reviewed_ancestor_is_full(self):
        for recorded in (None, "0" * 40, "not-a-commit"):
            with self.subTest(recorded=recorded):
                result = self.run_wrapper(resume=True, reviewed_head=recorded)
                self.assertEqual(result[:4], (0, True, SID, "2"), result[-1])
                self.assertNotIn("INCREMENTAL", self.last_prompt)
                self.assertIn("Re-read the COMPLETE current delivery scope", self.last_prompt)
                self.assertIn("REVIEW SCOPE (committed range", self.last_prompt)

    def test_failed_resume_keeps_reviewed_head(self):
        result = self.run_wrapper(resume=True, rc=1, reviewed_head="0" * 40)
        self.assertEqual(result[:4], (4, True, SID, "1"), result[-1])
        self.assertEqual(self.last_reviewed, "0" * 40)

    def test_pr_review_names_whole_pr_range(self):
        result = self.run_wrapper(pr_range="head", verification="unit tests: OK")
        self.assertEqual(result[:4], (0, True, SID, "1"), result[-1])
        self.assertIn(f"Committed range {self.fixture_base}..{self.fixture_head} (one whole pull request",
                      self.last_prompt)
        for text in ("{{RANGE}}", "{{SCOPE}}", "{{VERIFICATION_RESULTS}}"):
            self.assertNotIn(text, self.last_prompt)
        self.assertIn("unit tests: OK", self.last_prompt)
        # Four generated pages changed; only three are sampled.
        self.assertIn("5 (1 source, 4 generated)", self.last_prompt)
        self.assertEqual(self.last_prompt.count("    sample: exam/"), 3)
        # A PR resume must say what to review: no silent whole-range or empty pass.
        result = self.run_wrapper(resume=True, reviewed_head="head", pr_range="head")
        self.assertEqual(result[:2], (64, False), result[-1])

    def test_pr_resume_reviews_every_change_since_last_verdict(self):
        result = self.run_wrapper(resume=True, reviewed_head="base", pr_range="head", prev_tip="base",
                                  verification="resume tests: OK")
        self.assertEqual(result[:4], (0, True, SID, "2"), result[-1])
        self.assertIn("(INCREMENTAL)", self.last_prompt)
        self.assertIn(f"Review EVERY change in {self.fixture_base}..{self.fixture_head}", self.last_prompt)
        self.assertIn("do not re-read the", self.last_prompt)
        self.assertIn(f"REVIEW SCOPE (committed range {self.fixture_base}..{self.fixture_head})", self.last_prompt)
        self.assertIn("LOCAL VERIFICATION (this pass):\nresume tests: OK", self.last_prompt)
        self.assertTrue(self.last_prompt.rstrip().endswith("End with exactly APPROVE or REQUEST_CHANGES."))
        self.assertEqual(self.last_reviewed, self.fixture_head)

    def test_pr_resume_after_rebase_reviews_the_whole_range(self):
        result = self.run_wrapper(resume=True, reviewed_head="0" * 40, pr_range="head", full_from="0" * 40)
        self.assertEqual(result[:4], (0, True, SID, "2"), result[-1])
        self.assertIn(f"Re-review the COMPLETE pull request range {self.fixture_base}..{self.fixture_head}",
                      self.last_prompt)
        self.assertIn("0" * 40 + ", is no longer an ancestor", self.last_prompt)
        self.assertNotIn("(INCREMENTAL)", self.last_prompt)
        for kwargs in ({"full_from": "short"}, {"full_from": "0" * 40, "prev_tip": "base"},
                       {"full_from": "0" * 40, "pr_range": None}):
            with self.subTest(kwargs=kwargs):
                args = {"resume": True, "pr_range": "head", **kwargs}
                self.assertEqual(self.run_wrapper(**args)[:2], (64, False))

    def test_pr_resume_rejects_invalid_previous_head(self):
        for prev_tip, pr_range in (("short", "head"), ("0" * 40, "head"), ("head", None), ("head", "head")):
            with self.subTest(prev_tip=prev_tip, pr_range=pr_range):
                result = self.run_wrapper(resume=True, pr_range=pr_range, prev_tip=prev_tip)
                self.assertEqual(result[:2], (64, False), result[-1])

    def test_pr_resume_rebuttal_reaches_reviewer(self):
        result = self.run_wrapper(resume=True, reviewed_head="head", pr_range="head",
                                  rebuttal="F1 REJECTED: guarded by _delivery.py:340\n")
        self.assertEqual(result[:4], (0, True, SID, "2"), result[-1])
        self.assertIn("Never withdraw a finding on assertion alone", self.last_prompt)
        self.assertIn("F1 REJECTED: guarded by _delivery.py:340", self.last_prompt)
        self.assertIn("do not re-review the range", self.last_prompt)
        # A same-head rebuttal must follow that head's own verdict.
        result = self.run_wrapper(resume=True, reviewed_head="base", pr_range="head", rebuttal="F1 REJECTED\n")
        self.assertEqual(result[:2], (64, False), result[-1])

    def test_pr_resume_rebuttal_rejects_diff_or_missing_file(self):
        for rebuttal in ("diff --git a/x b/x\n@@ -1 +1 @@\n", "missing"):
            with self.subTest(rebuttal=rebuttal):
                result = self.run_wrapper(resume=True, pr_range="head", rebuttal=rebuttal)
                self.assertEqual(result[:2], (64, False), result[-1])

    def test_pr_review_head_must_be_checked_out(self):
        for resume in (False, True):
            with self.subTest(resume=resume):
                result = self.run_wrapper(resume=resume, pr_range="0" * 40)
                self.assertEqual(result[:2], (64, False), result[-1])

    def test_legacy_profile_cannot_resume(self):
        result = self.run_wrapper(resume=True, legacy=True)
        self.assertEqual(result[:4], (64, False, SID, "1"), result[-1])


@unittest.skipUnless(BASH, "Bash operator requires Bash")
class BashCliUnicodePathTests(unittest.TestCase):
    """The real resolve_cli must return a non-ASCII CLI path intact (see the
    PowerShell counterpart in _test_review_fixes.py)."""
    CLI = "C:/Users/\u9673\u7fca\u5609/AppData/Local/OpenAI/Codex/bin/x/codex.exe"

    def test_resolve_cli_keeps_unicode_path(self):
        source = (ROOT / "tools/codex_review.sh").read_text(encoding="utf-8")
        start = source.index("review_git_scope() {")
        end = source.index("\nVERIFIED_SID=", start)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "codex_review_identity.py").write_text(
                "import sys\nassert sys.argv[1:] == ['which'], sys.argv\n"
                f"print({self.CLI!r})\nprint('codex-cli 0.0.0')\n", encoding="utf-8")
            out = root / "cli.txt"
            script = root / "probe.sh"
            script.write_text(
                'die() { echo "$*" >&2; exit 64; }\n'
                f"PYTHON={shlex.quote(sys.executable.replace(chr(92), '/'))}\n"
                f"SCRIPT_DIR={shlex.quote(root.as_posix())}\nREPO_ROOT=/fixture\n"
                + source[start:end]
                + f"\nresolve_cli >/dev/null\nprintf '%s' \"$CODEX_CLI\" > {shlex.quote(out.as_posix())}\n",
                encoding="utf-8", newline="\n")
            env = {k: v for k, v in os.environ.items()
                   if k not in ("PYTHONUTF8", "PYTHONIOENCODING", "CODEX_REVIEW_CLI", "BASH_ENV")}
            result = subprocess.run([BASH, "--noprofile", "--norc", str(script)], env=env,
                                    capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(out.read_bytes().decode("utf-8", "replace"), self.CLI)


if __name__ == "__main__":
    unittest.main()
