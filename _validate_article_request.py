"""Validate a live author request before preparing source for independent review.

Read-only Git queries; never fetch, mutate refs, approve generated translations
or publish. The returned facts are preparation evidence, not a release permit.
Promotion / deployment must independently recheck cancellation and CI evidence.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

from _prepare_article_candidate import ARTICLE, git, plan, read_blob, revision

FIELDS = {"version", "file", "action", "draftHead", "manifestSha", "blobSha", "baseSha",
          "approvedBy", "contentApproved", "requestedAt", "scheduledAt"}


def article_slug(file: str) -> str:
    match = ARTICLE.fullmatch(file) if isinstance(file, str) else None
    if not match or len(match[1]) > 100 or match[1] in {"index", "topics", "charts"}:
        raise ValueError("Invalid article path")
    return match[1]


def timestamp(value: object) -> datetime:
    # The API stores Date.toISOString(): canonical UTC with exactly milliseconds.
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", value):
        raise ValueError("Request timestamp must be canonical UTC")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def verify_request_head(root: Path, head: str, file: str) -> None:
    head = revision(head)
    ref = "refs/heads/drafts/" + article_slug(file)
    # Query origin every time. A cached tracking ref cannot prove a request has
    # not been cancelled or superseded. Never fetch / write user refs here.
    result = subprocess.run(["git", "ls-remote", "--exit-code", "--heads", "origin", ref],
                            cwd=root, capture_output=True, text=True, timeout=20)
    if result.returncode == 2:
        raise ValueError("Author request was cancelled or changed on origin")
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
    lines = result.stdout.splitlines()
    if len(lines) != 1 or lines[0].split() != [head, ref]:
        raise ValueError("Author request was cancelled or changed on origin")


def request_record(raw: bytes, file: str, *, now: datetime | None = None,
                   require_due: bool = True) -> dict:
    """Validate the same API envelope for discovery and source preparation."""
    article_slug(file)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Validation clock must include a timezone")
    now = now.astimezone(timezone.utc)
    from _cms_delivery import parse
    record = parse(raw, canonical="compact", limit=8_000)
    if not isinstance(record, dict) or set(record) != FIELDS or type(record["version"]) is not int or record["version"] != 1:
        raise ValueError("Invalid author request schema")
    if record["file"] != file or not isinstance(record["action"], str) or record["action"] not in {"review", "schedule", "unpublish"} or record["approvedBy"] != "expertise88864":
        raise ValueError("Invalid author request identity/action")
    if type(record["contentApproved"]) is not bool or record["contentApproved"] != (record["action"] != "unpublish"):
        raise ValueError("Explicit author approval is required")
    for field in ("draftHead", "manifestSha", "blobSha"):
        revision(record[field])
    if record["baseSha"] is not None:
        revision(record["baseSha"])
    requested = timestamp(record["requestedAt"])
    if requested > now:
        raise ValueError("Request creation time is in the future")
    if record["action"] == "schedule":
        scheduled = timestamp(record["scheduledAt"])
        if not requested < scheduled <= requested + timedelta(days=365):
            raise ValueError("Invalid requested schedule interval")
        if require_due and scheduled > now:
            raise ValueError("Scheduled request is not due")
    elif record["scheduledAt"] is not None:
        raise ValueError("Unexpected schedule on this action")
    if record["action"] == "unpublish" and record["baseSha"] is None:
        raise ValueError("A never-published article cannot be unpublished")
    return record


def request_plan(root: Path, head: str, file: str, blob_sha: str,
                 *, now: datetime | None = None, live_root: Path | None = None) -> tuple[dict[str, bytes], dict]:
    """Prepare source in a clean checkout; query live refs via its trusted origin.

    The artifact preparer uses a disposable clone sharing only immutable Git
    objects. live_root keeps authentication/ref queries in the original trusted
    checkout, without copying its credentials or altering its working tree.
    """
    head, blob_sha = revision(head), revision(blob_sha)
    slug = article_slug(file)
    origin = live_root if live_root is not None else root
    verify_request_head(origin, head, file)
    request_path = ".cms-requests/" + slug + ".json"
    request_sha, request_bytes = read_blob(root, head, request_path)
    record = request_record(request_bytes, file, now=now)
    parent = revision(record["draftHead"])
    manifest_sha = revision(record["manifestSha"])
    if record["blobSha"] != blob_sha:
        raise ValueError("Author approved a different article revision")
    parents = git(root, "rev-list", "--parents", "-n", "1", head).decode().split()
    if parents != [head, parent]:
        raise ValueError("Request is no longer the immediate successor of its approved draft")
    changed = git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", parent, head).split(b"\0")
    if [path for path in changed if path] != [request_path.encode("utf-8")]:
        raise ValueError("Request commit changed files beyond the author request")
    manifest_path = ".cms-drafts/" + slug + ".json"
    manifest = read_blob(root, head, manifest_path)
    if manifest[0] != manifest_sha or read_blob(root, parent, manifest_path)[0] != manifest_sha:
        raise ValueError("Approved manifest changed")
    if read_blob(root, parent, file)[0] != blob_sha:
        raise ValueError("Approved draft article changed")
    manifest_record = json.loads(manifest[1].decode("utf-8"))
    if not isinstance(manifest_record, dict) or manifest_record.get("baseSha") != record["baseSha"]:
        raise ValueError("Approved article base changed")
    files = plan(root, head, file, blob_sha)
    # Publishing a formerly hidden catalog entry needs an explicit visibility
    # plan too. Do not silently index an intentionally unpublished article.
    if record["baseSha"] is not None:
        from _sync_hub_catalog import load_catalog
        entries = [entry for entry in load_catalog(root) if entry["slug"] == slug]
        if len(entries) != 1 or (entries[0].get("unpublished") and record["action"] != "unpublish"):
            raise ValueError("Article visibility requires a separate reviewed catalog plan")
    if record["action"] == "unpublish":
        if record["baseSha"] is None:
            raise ValueError("A never-published article cannot be unpublished")
        from _article_visibility import unpublish_plan
        # Validate the request bundle above, but prepare only the current main
        # article's indexing policy + catalog visibility. Never adopt draft text.
        main = git(root, "rev-parse", "HEAD").decode().strip()
        files = unpublish_plan(root, file, read_blob(root, main, file)[1], slug)
    verify_request_head(origin, head, file)
    proof = {"version": 1, "repository": "expertise88864/user", "file": file,
             "requestHead": head, "requestBlobSha": request_sha, "draftHead": parent,
             "manifestSha": manifest_sha, "articleBlobSha": blob_sha, "baseSha": record["baseSha"],
             "preparedAgainst": git(root, "rev-parse", "HEAD").decode().strip(),
             "action": record["action"], "approvedBy": record["approvedBy"],
             "requestedAt": record["requestedAt"], "scheduledAt": record["scheduledAt"],
             "sourceSha256": {path: hashlib.sha256(content).hexdigest() for path, content in files.items()}}
    return files, proof
