"""Discover author requests and preserve isolated candidates for review.

Legacy requests create source bundles. Exact final generated approvals rebuild
only the trusted current pipeline and must reproduce the full approved archive.
No remote writes, queue edits, draft code execution or release permission. CI
and model review still run through the normal candidate delivery workflow.
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

from _cms_delivery import FILE as RECEIPT, REPO, parse, with_receipt
from _prepare_article_candidate import apply, git, read_blob, revision
from _validate_article_request import article_slug, request_plan, request_record, timestamp, verify_request_head

MAX_BRANCHES = 200
MAX_BUNDLES = 20
QUEUE = ".github/scheduled-publish/queue.json"


class GeneratedReviewNeedsRefresh(ValueError):
    """An authentic immutable preview belongs to an older trusted pipeline."""


def final_request(root: Path, main: str, head: str, file: str, raw: bytes, now: datetime) -> dict:
    """Validate the complete final envelope before executing any generation."""
    import _cms_generated_package as package
    import _cms_patient_review as review
    record = parse(raw, canonical='compact', limit=8_000)
    if (not isinstance(record, dict) or set(record) != review.REQUEST_FIELDS or
            type(record.get('version')) is not int or record['version'] != 2 or
            record.get('file') != file or type(record.get('contentApproved')) is not bool or
            record['contentApproved'] is not True):
        raise ValueError('Invalid final patient request schema')
    original = request_record((json.dumps(record['sourceRequest'], ensure_ascii=False,
                                         separators=(',', ':')) + '\n').encode('utf8'),
                              file, now=now, require_due=False)
    if original['action'] == 'unpublish':
        raise ValueError('Unpublish cannot use final generated approval')
    review_head = revision(record['reviewHead'])
    try:
        immutable_source(root, review_head)
    except subprocess.CalledProcessError as error:
        # Only an explicit no-such-object Git protocol response rejects this
        # request. Authentication, rate-limit and other transport failures
        # remain visible job failures; never report them as an empty queue.
        messages = (error.stderr or b'').decode('utf8', errors='replace').splitlines()
        missing = ('not our ref ' + review_head, "couldn't find remote ref " + review_head)
        if error.returncode == 128 and any(line.strip().endswith(missing) for line in messages):
            raise ValueError('Final patient preview commit is unavailable') from None
        raise
    if git(root, 'cat-file', '-t', review_head).strip() != b'commit':
        raise ValueError('Final patient preview must identify a commit')
    if read_blob(root, review_head, review.review_path(file), optional=True) is None:
        raise ValueError('Final patient preview manifest is unavailable')
    evidence = package.GitEvidence(root)
    frozen, blob, manifest_raw = review.load_review(evidence, review_head, file, now=now)
    proof = frozen['patientManifest']['trackedPackage']['sourceEvidence']
    request_blob, _ = read_blob(root, head, '.cms-requests/' + article_slug(file) + '.json')
    entry = {**proof, 'version': 2, 'patientApproval': {
        'reviewHead': review_head, 'manifestBlobSha': blob,
        'manifestSha256': hashlib.sha256(manifest_raw).hexdigest(),
        'approvalHead': head, 'approvalBlobSha': request_blob, 'approvedAt': record['approvedAt']}}
    review.validate_approval(entry['patientApproval'], now=now)
    if timestamp(record['approvedAt']) < timestamp(original['requestedAt']) or record != review.expected_request(entry, frozen):
        raise ValueError('Final request differs from the complete approved patient preview')
    review.parent(evidence, head, proof['requestHead'])
    review.changed_one(evidence, proof['requestHead'], head,
                       '.cms-requests/' + article_slug(file) + '.json', request_blob)
    verify_request_head(root, head, file)
    if frozen['patientManifest']['trackedPackage']['pipelineHead'] != main:
        raise GeneratedReviewNeedsRefresh('Final preview belongs to an older trusted pipeline')
    return original


def prepared_patient_bundle(root: Path, output: Path, main: str, head: str,
                            file: str, record: dict, now: datetime) -> dict:
    from _prepare_patient_review import prepare_release
    name = head + '-' + main
    report = prepare_release(root, output / name, head, file, main, None, now=now)
    return {'file': file, 'action': record['action'], 'requestHead': head,
            'mainSha': main, 'candidateSha': report['candidateHead'], 'artifacts': name,
            'bundle': name + '/objects.bundle', 'bundleSha256': report['objectsSha256'],
            'archiveSha256': report['archiveSha256'], 'generationVerified': True,
            'state': report['state'], 'reviewVerified': False, 'ciVerified': False, 'published': False}


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
            envelope = parse(request[1], canonical='compact', limit=8_000)
            final = isinstance(envelope, dict) and envelope.get('version') == 2
            record = (final_request(root, main, head, file, request[1], now) if final else
                      request_record(request[1], file, now=now, require_due=False))
            if record["action"] == "schedule" and timestamp(record["scheduledAt"]) > now:
                report["deferred"].append({"file": file, "requestHead": head, "reason": "not_due"})
                continue
            if len(report["prepared"]) >= MAX_BUNDLES:
                report["deferred"].append({"file": file, "requestHead": head, "reason": "preparation_limit"})
                continue
            if not final:
                report["prepared"].append(prepared_bundle(root, output, main, head, file, record, now))
        except GeneratedReviewNeedsRefresh:
            report['deferred'].append({'file': file, 'requestHead': head,
                                       'reason': 'generated_review_requires_refresh'})
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            # Preserve drafts/queue; do not expose user content via parser errors.
            report["deferred"].append({"file": file, "requestHead": head,
                                       "reason": "request_rejected", "errorType": type(error).__name__})
        else:
            if final:
                # Generation/packaging failures are engineering failures, not
                # an invalid author request. Fail the job and upload no report.
                report['prepared'].append(prepared_patient_bundle(root, output, main, head, file, record, now))
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
