"""Compatibility entrypoint for the policy-backed exact-SHA delivery verifier.

The default is formal-main verification; candidate evidence requires an explicit
--phase candidate. Workflow/job/step requirements live only in _delivery.py and
_delivery_policy.json, rather than an incomplete legacy workflow list.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sha", help="Exact full lowercase commit SHA")
    parser.add_argument("--phase", choices=("candidate", "main"), default="main")
    parser.add_argument("--wait", type=int, default=1800,
                        help="Bounded wait in seconds; the shared verifier limits it to 3600")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        parser.error("sha must be a full lowercase 40-character commit SHA")
    if args.wait < 0:
        parser.error("wait must be nonnegative")
    try:
        return subprocess.run(
            [sys.executable, str(ROOT / "_delivery.py"), "verify", args.sha,
             "--phase", args.phase, "--wait", str(args.wait)], cwd=ROOT,
        ).returncode
    except (OSError, ValueError) as exc:
        print(f"DELIVERY BLOCKED: cannot run the shared verifier: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
