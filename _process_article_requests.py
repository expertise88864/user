"""Discover author requests and preserve isolated source bundles for review.

No remote writes, queue edits, generators, draft code execution or release
permission. Each bundle is independently based on the same live main. CI and
model review must still run through the normal candidate delivery workflow.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from _cms_delivery import FILE as RECEIPT, REPO, with_receipt
from _prepare_article_candidate import apply, git, read_blob, revision
from _validate_article_request import article_slug, request_plan, request_record, timestamp, verify_request_head

MAX_BRANCHES = 200
MAX_BUNDLES = 20
QUEUE = ".github/scheduled-publish/queue.json"


def remote_heads(root: Path, pattern: str) -> dict[str, str]:
    # Command failure is not an empty queue. Do not print authenticated stderr.
    result = subprocess.run(["git", "ls-remote", "--heads", "origin", pattern], cwd=root,
                            capture_output=True, check=True, timeout=30)
    lines = result.stdout.decode("utf-8").splitlines()
    if len(lines) > MAX_BRANCHES:
        raise ValueError("Remote branch inventory exceeds the discovery limit")
    heads = {}
    for line in lines:
        parts = line.split()
        if len(parts) != 2 or parts[1] in heads:
            raise ValueError("Malformed remote branch inventory")
        heads[parts[1]] = revision(parts[0])
    return heads


def live_main(root: Path) -> str:
    heads = remote_heads(root, "refs/heads/main")
    if set(heads) != {"refs/heads/main"}:
        raise ValueError("Live main is unavailable")
    return heads["refs/heads/main"]


def unchanged_main(root: Path, main: str) -> None:
    if live_main(root) != main:
        raise ValueError("Main advanced during source preparation")


def immutable_source(root: Path, sha: str) -> None:
    # Fetch the full SHA into the object database, never a branch/tracking ref.
    subprocess.run(["git", "fetch", "--no-tags", "--no-write-fetch-head", "origin", revision(sha)],
                   cwd=root, capture_output=True, check=True, timeout=60)


def prepared_bundle(root: Path, output: Path, main: str, head: str, file: str,
                    record: dict, now: datetime) -> dict:
    # Disposable clone shares immutable objects only. Its origin points to root,
    # not GitHub; authentication queries stay in the trusted runner checkout.
    with tempfile.TemporaryDirectory(prefix="cms-source-", dir=output.parent) as directory:
        temporary = Path(directory).resolve()
        if not temporary.is_relative_to(output.parent.resolve()):
            raise ValueError("Temporary clone escaped the artifact parent")
        checkout = temporary / "checkout"
        subprocess.run(["git", "clone", "--shared", "--no-checkout", "--", str(root), str(checkout)],
                       capture_output=True, check=True, timeout=30)
        git(checkout, "config", "core.autocrlf", "false")
        git(checkout, "config", "user.name", "CMS Source Preparation")
        git(checkout, "config", "user.email", "cms-source@example.invalid")
        git(checkout, "checkout", "-b", "codex/cms-source-" + head, main)
        files, proof = request_plan(checkout, head, file, record["blobSha"], now=now, live_root=root)
        if proof["preparedAgainst"] != main:
            raise ValueError("Candidate base does not match discovery main")
        files = with_receipt(checkout, files, proof, now=now)
        apply(checkout, files, expected_head=main)
        git(checkout, "add", "--", *sorted(files))
        git(checkout, "commit", "-m", "cms source preparation: " + article_slug(file))
        candidate = revision(git(checkout, "rev-parse", "HEAD").decode().strip())
        changes = git(checkout, "diff", "--name-only", "-z", main, candidate).split(b"\0")
        changed = {path.decode("utf-8") for path in changes if path}
        if not changed <= set(files) or RECEIPT not in changed:
            raise ValueError("Candidate contains files outside the approved source plan")
        # Git clean filters / attributes must not silently change approved bytes.
        for path, raw in files.items():
            if read_blob(checkout, candidate, path)[1] != raw:
                raise ValueError("Committed source differs from the approved bytes")
        if git(checkout, "status", "--porcelain", "--untracked-files=all").strip():
            raise ValueError("Source preparation left unexpected working tree changes")
        unchanged_main(root, main)
        verify_request_head(root, head, file)
        name = head + "-" + main + ".bundle"
        bundle = output / name
        # The range contains only the isolated source commit, never draft history.
        git(checkout, "bundle", "create", str(bundle), main + "..HEAD")
        try:
            unchanged_main(root, main)
            verify_request_head(root, head, file)
        except (ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            bundle.unlink()
            raise
        return {"file": file, "action": record["action"], "requestHead": head,
                "mainSha": main, "candidateSha": candidate, "bundle": name,
                "bundleSha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
                "paths": sorted(files), "sourceSha256": proof["sourceSha256"],
                "state": "source_prepared", "reviewVerified": False,
                "ciVerified": False, "published": False}


def process(root: Path, output: Path, *, now: datetime | None = None) -> dict:
    root, output = root.resolve(), output.resolve()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Discovery clock must include a timezone")
    now = now.astimezone(timezone.utc)
    if output.is_relative_to(root) or not output.parent.is_dir() or output.exists():
        raise ValueError("Artifacts require a new directory outside the trusted checkout")
    if git(root, "status", "--porcelain", "--untracked-files=all").strip():
        raise ValueError("Trusted checkout must be clean")
    main = live_main(root)
    if git(root, "rev-parse", "HEAD").decode().strip() != main:
        raise ValueError("Trusted checkout must match live main")
    refs = git(root, "show-ref")
    queue = read_blob(root, main, QUEUE, optional=True)
    inventory = remote_heads(root, "refs/heads/drafts/*")
    output.mkdir()
    report = {"version": 1, "repository": REPO, "mainSha": main,
              "queuePreserved": True, "legacyQueueNeedsAuthorRequest": queue is not None,
              "prepared": [], "deferred": [], "published": False}
    for branch, head in sorted(inventory.items()):
        try:
            slug = branch.removeprefix("refs/heads/drafts/")
            file = "blog/" + slug + ".html"
            if branch != "refs/heads/drafts/" + article_slug(file):
                raise ValueError("Invalid draft branch")
        except ValueError:
            report["deferred"].append({"requestHead": head, "reason": "invalid_branch"})
            continue
        immutable_source(root, head)  # Transport failures must fail the job visibly.
        try:
            request = read_blob(root, head, ".cms-requests/" + slug + ".json", optional=True)
            if request is None:
                report["deferred"].append({"file": file, "requestHead": head, "reason": "author_request_required"})
                continue
            record = request_record(request[1], file, now=now, require_due=False)
            if record["action"] == "schedule" and timestamp(record["scheduledAt"]) > now:
                report["deferred"].append({"file": file, "requestHead": head, "reason": "not_due"})
                continue
            if len(report["prepared"]) >= MAX_BUNDLES:
                report["deferred"].append({"file": file, "requestHead": head, "reason": "preparation_limit"})
                continue
            report["prepared"].append(prepared_bundle(root, output, main, head, file, record, now))
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            # Preserve drafts/queue; do not expose user content via parser errors.
            report["deferred"].append({"file": file, "requestHead": head,
                                       "reason": "request_rejected", "errorType": type(error).__name__})
    unchanged_main(root, main)
    # No new refs, stage/working tree changes, or queue edits in the trusted root.
    if refs != git(root, "show-ref") or git(root, "status", "--porcelain", "--untracked-files=all").strip():
        raise ValueError("Trusted checkout changed during discovery")
    if read_blob(root, main, QUEUE, optional=True) != queue:
        raise ValueError("Legacy queue changed during discovery")
    # Requests can move while a later article is being prepared. Recheck the
    # whole artifact set before producing the report; failure uploads nothing.
    for item in report["prepared"]:
        verify_request_head(root, item["requestHead"], item["file"])
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REPOSITORY") != REPO:
        raise ValueError("Operational discovery requires the trusted repository runner")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("Operational discovery runs only from main")
    # Pinned actions/checkout uses the HTTPS repository URL without .git.
    # Accept only these two exact forms, never credentials/redirects/fork hosts.
    if git(root, "remote", "get-url", "origin").decode().strip() not in {
        "https://github.com/" + REPO, "https://github.com/" + REPO + ".git"
    }:
        raise ValueError("Operational discovery requires the fixed repository origin")
    runner = os.environ.get("RUNNER_TEMP")
    if not runner or args.output.resolve() != Path(runner).resolve() / "cms-source-artifacts":
        raise ValueError("Operational artifacts must use the fixed runner temporary directory")
    report = process(root, args.output)
    print(json.dumps({"prepared": len(report["prepared"]), "deferred": len(report["deferred"]),
                      "reviewVerified": False, "ciVerified": False, "published": False}))


if __name__ == "__main__":
    main()
