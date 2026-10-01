"""Prepare a review bundle for published CMS receipts; never commit or publish.

Only a separate retirement-only candidate may apply this bundle. It must then
pass independent review, exact-SHA remote CI, PR/Preview and formal delivery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from _cms_delivery import FILE, revision
from _cms_retirement import PREFIX, prepare


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.PIPE, timeout=20).decode("utf-8").strip()


def write_bundle(root: Path, destination: Path, expected: str, files: dict[str, bytes]):
    """Exclusive new directory outside the checkout; never overwrite sources."""
    root = root.resolve()
    expected = revision(expected)
    if git(root, "rev-parse", "HEAD") != expected:
        raise ValueError("Local revision changed after retirement preparation")
    if not files:
        return
    archive = PREFIX + expected + ".json"
    if set(files) != {FILE, archive} or any(not isinstance(raw, bytes) for raw in files.values()):
        raise ValueError("Unexpected retirement bundle paths")
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("Retirement bundle destination must not exist")
    for parent in destination.parents:
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise ValueError("Retirement bundle destination contains a link")
    destination = destination.resolve()
    if destination.is_relative_to(root) or root.is_relative_to(destination):
        raise ValueError("Retirement bundle must be outside the working checkout")
    if not destination.parent.is_dir():
        raise ValueError("Retirement bundle parent must be an existing directory")
    destination.mkdir()  # Exclusive creation; parent must already exist.
    for path, raw in files.items():
        target = destination / path
        target.parent.mkdir(exist_ok=True)
        with target.open("xb") as output:
            output.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-main", required=True, help="Exact observed published main SHA")
    parser.add_argument("--output", type=Path, help="New review bundle directory outside the checkout")
    parser.add_argument("--check", action="store_true", help="Validate only; write no files")
    args = parser.parse_args()
    if not args.check and args.output is None:
        parser.error("--output or --check is required")
    root = Path(__file__).resolve().parent
    expected = revision(args.expected_main)
    if git(root, "rev-parse", "HEAD") != expected:
        raise ValueError("Local HEAD must equal the expected published main revision")
    from _delivery import API
    files = prepare(API("expertise88864/user"), expected)
    if git(root, "rev-parse", "HEAD") != expected:
        raise ValueError("Local revision changed during retirement preparation")
    if not args.check:
        write_bundle(root, args.output, expected, files)
    print(json.dumps({"publishedMain": expected, "paths": sorted(files), "noOp": not files,
                      "sha256": {path: hashlib.sha256(raw).hexdigest() for path, raw in files.items()},
                      "bundleWritten": bool(files) and not args.check,
                      "reviewPassed": False, "candidateCIPassed": False, "published": False}))


if __name__ == "__main__":
    main()
