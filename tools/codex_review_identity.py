#!/usr/bin/env python3
"""Check the actual Codex review session, rather than trusting requested flags."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", re.I)


def objects(path: Path, *, allow_diagnostics: bool = False) -> list[dict]:
    result = []
    raw = path.read_bytes()
    # Windows PowerShell 5.1 Tee-Object emits BOM-tagged UTF-16; the CLI
    # and PowerShell 7 emit UTF-8. Decode only explicit BOMs, without guessing
    # or suppressing malformed input before the machine identity checks.
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    for line in raw.decode(encoding).splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            if allow_diagnostics:
                continue
            raise ValueError("invalid session JSON") from None
        if isinstance(value, dict):
            result.append(value)
    return result


def verify(raw: Path, repo: Path, sessions: Path, started_at: float,
           expected_session: str | None = None) -> dict:
    from datetime import datetime

    if not math.isfinite(started_at) or started_at < 0:
        raise ValueError("invalid invocation timestamp")
    events = objects(raw, allow_diagnostics=True)
    ids = [x.get("thread_id") for x in events if x.get("type") == "thread.started"]
    if len(ids) != 1 or not isinstance(ids[0], str) or not UUID.fullmatch(ids[0]):
        raise ValueError("missing or ambiguous machine-readable session identity")
    sid = ids[0].lower()
    if expected_session and sid != expected_session.lower():
        raise ValueError("returned session differs from recorded session")
    turns = [x for x in events if x.get("type") == "turn.completed"]
    if len(turns) != 1 or any(x.get("type") in {"error", "turn.failed"} for x in events):
        raise ValueError("review turn did not complete normally")
    usage = turns[0].get("usage", {})
    numbers = [usage.get(k) for k in ("input_tokens", "output_tokens")]
    if any(type(n) is not int or n < 0 for n in numbers):
        raise ValueError("missing actual token usage")

    matches = list(sessions.rglob(f"*{sid}.jsonl"))
    if len(matches) != 1:
        raise ValueError("missing or ambiguous actual session log")
    log = matches[0]
    records = objects(log)
    metadata = [x.get("payload", {}) for x in records if x.get("type") == "session_meta"]
    if len(metadata) != 1 or str(metadata[0].get("id", "")).lower() != sid:
        raise ValueError("actual session metadata identity mismatch")
    if not metadata[0].get("cwd") or Path(metadata[0]["cwd"]).resolve() != repo.resolve():
        raise ValueError("actual session belongs to another repository")
    contexts = [x for x in records if x.get("type") == "turn_context"]
    if not contexts:
        raise ValueError("actual session has no review context")
    latest = contexts[-1]
    stamp = datetime.fromisoformat(latest.get("timestamp", "").replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.timestamp() < started_at - 1:
        raise ValueError("actual context is stale for this invocation")
    context = latest.get("payload", {})
    if not context.get("cwd") or Path(context["cwd"]).resolve() != repo.resolve():
        raise ValueError("actual turn belongs to another repository")
    if context.get("model") != "gpt-5.5" or context.get("effort") != "xhigh":
        raise ValueError("actual model/effort differs from gpt-5.5/xhigh")
    if context.get("sandbox_policy", {}).get("type") != "read-only":
        raise ValueError("actual review sandbox is not read-only")
    return {"sessionId": sid, "tokensUsed": sum(numbers), "actualModel": "gpt-5.5",
            "actualEffort": "xhigh", "readOnly": True,
            "turnId": context.get("turn_id"), "contextTimestamp": latest["timestamp"],
            "sessionLogSHA256": hashlib.sha256(log.read_bytes()).hexdigest(),
            "eventsSHA256": hashlib.sha256(raw.read_bytes()).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-log", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--started-at", type=float, required=True)
    parser.add_argument("--expected-session")
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--session-directory", type=Path,
                        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions")
    args = parser.parse_args()
    try:
        proof = verify(args.raw_log, args.repo, args.session_directory,
                       args.started_at, args.expected_session)
        args.proof.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"[codex-review] actual session verification failed: {exc}", file=sys.stderr)
        return 4
    print(f"{proof['sessionId']}\t{proof['tokensUsed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
