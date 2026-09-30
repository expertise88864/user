"""Live, fail-closed author-intent checks; no Git writes or publication.

Preparation receipts remain active until a separate reviewed retirement step.
CI evidence does not replace checking the current request again before delivery.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.error

FILE = ".cms-delivery.json"
REPO = "expertise88864/user"
SHA = re.compile(r"[a-f0-9]{40}")
HASH = re.compile(r"[a-f0-9]{64}")
ARTICLE = re.compile(r"blog/([a-z0-9]+(?:-[a-z0-9]+)*)\.html")
MAX_BYTES = 128_000
FIELDS = {"version", "repository", "file", "requestHead", "requestBlobSha", "draftHead",
          "manifestSha", "articleBlobSha", "baseSha", "preparedAgainst", "action", "approvedBy",
          "requestedAt", "scheduledAt", "sourceSha256"}


class ImmutableBlobs:
    """Cache only immutable tree evidence, never the live author branch ref."""
    def __init__(self, api):
        self.api = api
        self.trees = {}

    def get(self, path):
        return self.api.get(path)

    def ordinary(self, path, commit, blob):
        if commit not in self.trees:
            record = self.get("/git/commits/" + commit)
            if not isinstance(record, dict) or record.get("sha") != commit:
                raise ValueError("CMS commit tree unavailable")
            tree_sha = revision(record.get("tree", {}).get("sha"))
            tree = self.get("/git/trees/" + tree_sha + "?recursive=1")
            if not isinstance(tree, dict) or tree.get("sha") != tree_sha or tree.get("truncated") is not False or not isinstance(tree.get("tree"), list) or len(tree["tree"]) > 10_000:
                raise ValueError("CMS Git tree evidence is incomplete")
            entries = {}
            for entry in tree["tree"]:
                name = entry.get("path") if isinstance(entry, dict) else None
                if not isinstance(name, str) or name in entries:
                    raise ValueError("CMS Git tree paths are ambiguous")
                entries[name] = entry
            self.trees[commit] = entries
        entry = self.trees[commit].get(path)
        if not entry or entry.get("mode") != "100644" or entry.get("type") != "blob" or entry.get("sha") != blob:
            raise ValueError("CMS inputs must be ordinary non-executable Git blobs")


def revision(value):
    if not isinstance(value, str) or not SHA.fullmatch(value) or value == "0" * 40:
        raise ValueError("CMS proof requires a full nonzero SHA")
    return value


def slug_for(file):
    match = ARTICLE.fullmatch(file) if isinstance(file, str) else None
    if not match or len(match[1]) > 100 or match[1] in {"index", "topics", "charts"}:
        raise ValueError("Invalid CMS article path")
    return match[1]


def utc(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", value):
        raise ValueError("CMS timestamp must be canonical UTC")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse(raw: bytes, *, canonical=False, limit=MAX_BYTES):
    if not isinstance(raw, bytes) or len(raw) > limit:
        raise ValueError("CMS proof exceeds its byte limit")
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate CMS JSON property")
            value[key] = item
        return value
    def invalid_constant(_):
        raise ValueError("Invalid CMS JSON number")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid_constant)
    expected = json.dumps(value, ensure_ascii=False, separators=(",", ":")) if canonical == "compact" else json.dumps(value, ensure_ascii=False, indent=2)
    if canonical and (expected + "\n").encode("utf-8") != raw:
        raise ValueError("CMS proof must use canonical JSON")
    return value


def receipts(raw: bytes, *, now=None):
    value = parse(raw, canonical=True)
    if not isinstance(value, dict) or set(value) != {"version", "requests"} or type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("Invalid CMS delivery schema")
    items = value["requests"]
    if not isinstance(items, list) or len(items) > 20:
        raise ValueError("Too many active CMS receipts")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("CMS validation clock requires a timezone")
    seen = set()
    for entry in items:
        if not isinstance(entry, dict) or set(entry) != FIELDS or type(entry["version"]) is not int or entry["version"] != 1:
            raise ValueError("Invalid CMS receipt schema")
        slug = slug_for(entry["file"])
        if slug in seen:
            raise ValueError("Duplicate CMS article receipt")
        seen.add(slug)
        if entry["repository"] != REPO or entry["approvedBy"] != "expertise88864" or not isinstance(entry["action"], str) or entry["action"] not in {"review", "schedule", "unpublish"}:
            raise ValueError("Untrusted CMS author/repository/action")
        for field in ["requestHead", "requestBlobSha", "draftHead", "manifestSha", "articleBlobSha", "preparedAgainst"]:
            revision(entry[field])
        if entry["baseSha"] is not None:
            revision(entry["baseSha"])
        if entry["action"] == "unpublish" and entry["baseSha"] is None:
            raise ValueError("A never-published article cannot be withdrawn")
        created = utc(entry["requestedAt"])
        if created > current:
            raise ValueError("CMS author request is in the future")
        if entry["action"] == "schedule":
            due = utc(entry["scheduledAt"])
            if not created < due <= created + timedelta(days=365) or due > current:
                raise ValueError("CMS schedule is invalid or not due")
        elif entry["scheduledAt"] is not None:
            raise ValueError("Unexpected CMS schedule")
        sources = entry["sourceSha256"]
        if not isinstance(sources, dict) or not 1 <= len(sources) <= 18 or entry["file"] not in sources:
            raise ValueError("Incomplete CMS source evidence")
        for path, digest in sources.items():
            if path not in {entry["file"], "blog/blog-shared.js"} and not re.fullmatch(r"blog/images/" + re.escape(slug) + r"/[a-f0-9]{64}\.(?:png|jpg|gif|webp)", path):
                raise ValueError("CMS source evidence escapes its article")
            if not isinstance(digest, str) or not HASH.fullmatch(digest):
                raise ValueError("Invalid CMS source digest")
    return items


def github_file(api, path, sha, limit=MAX_BYTES, *, optional=False):
    try:
        response = api.get("/contents/" + path + "?ref=" + revision(sha))
    except urllib.error.HTTPError as error:
        if optional and error.code == 404:
            return None
        raise
    if not isinstance(response, dict) or response.get("type") != "file" or response.get("encoding") not in {"base64", "none"} or response.get("path") != path:
        raise ValueError("CMS immutable blob is unavailable")
    encoded = response.get("content")
    size = response.get("size")
    blob = revision(response.get("sha"))
    if type(size) is not int or not 0 <= size <= limit:
        raise ValueError("Invalid CMS blob size")
    if response["encoding"] == "none":
        if encoded != "":
            raise ValueError("Invalid CMS object metadata")
        payload = api.get("/git/blobs/" + blob)
        if not isinstance(payload, dict) or payload.get("sha") != blob or payload.get("encoding") != "base64" or type(payload.get("size")) is not int or payload["size"] != size:
            raise ValueError("CMS exact-blob fallback does not match its metadata")
        encoded = payload.get("content")
    if not isinstance(encoded, str) or type(size) is not int or not 0 <= size <= limit or len(encoded) > limit * 2:
        raise ValueError("Invalid CMS blob size")
    raw = base64.b64decode(encoded.replace("\n", "").replace("\r", ""), validate=True)
    if len(raw) != size or base64.b64encode(raw).decode() != encoded.replace("\n", "").replace("\r", ""):
        raise ValueError("Invalid CMS blob encoding")
    if hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != blob:
        raise ValueError("CMS blob digest does not match its immutable SHA")
    if isinstance(api, ImmutableBlobs):
        api.ordinary(path, sha, blob)
    return blob, raw


def ancestor(api, base, head):
    if base == head:
        return
    compare = api.get("/compare/" + revision(base) + "..." + revision(head))
    if not isinstance(compare, dict) or compare.get("status") not in {"ahead", "identical"} or compare.get("merge_base_commit", {}).get("sha") != base:
        raise ValueError("CMS preparation is not based on the delivery history")


def approved_sources(api, entry):
    """Validate immutable approval inputs; never execute draft code."""
    slug = slug_for(entry["file"])
    _, manifest_raw = github_file(api, ".cms-drafts/" + slug + ".json", entry["draftHead"])
    if hashlib.sha1(b"blob " + str(len(manifest_raw)).encode() + b"\0" + manifest_raw).hexdigest() != entry["manifestSha"]:
        raise ValueError("Approved manifest changed")
    record = parse(manifest_raw)
    if not isinstance(record, dict) or type(record.get("version")) is not int or record.get("version") != 1 or record.get("file") != entry["file"] or record.get("blobSha") != entry["articleBlobSha"] or record.get("baseSha") != entry["baseSha"] or record.get("status") != "draft":
        raise ValueError("Approved manifest does not match the author request")
    ancestor(api, revision(record.get("baseMain")), entry["preparedAgainst"])
    blob, article = github_file(api, entry["file"], entry["draftHead"], 1_500_000)
    if blob != entry["articleBlobSha"]:
        raise ValueError("Author approved a different article blob")
    article.decode("utf-8")
    assets = record.get("assets")
    if not isinstance(assets, list) or len(assets) > 16:
        raise ValueError("Invalid approved media manifest")
    files = {entry["file"]: article}
    total = 0
    for asset in assets:
        path = asset.get("path") if isinstance(asset, dict) else None
        match = re.fullmatch(r"blog/images/" + re.escape(slug) + r"/([a-f0-9]{64})\.(png|jpg|gif|webp)", path or "")
        if not match or path in files or type(asset.get("size")) is not int:
            raise ValueError("Invalid approved media identity")
        sha, content = github_file(api, path, entry["draftHead"], 1_500_000)
        magic = {"png": content.startswith(b"\x89PNG\r\n\x1a\n"), "jpg": content.startswith(b"\xff\xd8\xff"),
                 "gif": content.startswith((b"GIF87a", b"GIF89a")), "webp": content[:4] == b"RIFF" and content[8:12] == b"WEBP"}
        if sha != asset.get("sha") or len(content) != asset["size"] or len(content) < 8 or hashlib.sha256(content).hexdigest() != match[1] or not magic[match[2]]:
            raise ValueError("Approved media content changed")
        total += ((len(content) + 2) // 3) * 4
        if total > 1_900_000:
            raise ValueError("Approved media exceeds its reloadable limit")
        files[path] = content
    sources = entry["sourceSha256"]
    if entry["action"] != "unpublish":
        # New article/catalog metadata remains subject to the normal independent
        # diff review. This gate binds patient text and each approved media blob.
        if set(sources) - {"blog/blog-shared.js"} != set(files):
            raise ValueError("CMS receipt lost or added approved source files")
        for path, content in files.items():
            if hashlib.sha256(content).hexdigest() != sources[path]:
                raise ValueError("CMS source is different from the approved draft")
    elif set(sources) != {entry["file"], "blog/blog-shared.js"}:
        raise ValueError("Unpublish receipt must change only article visibility and catalog")
    # Do not use a newer draft's prose for an unpublish request. Its visibility
    # patch is independently reviewed and bound below to the candidate bytes.
    baseline = github_file(api, entry["file"], entry["preparedAgainst"], 1_500_000, optional=True)
    if (baseline[0] if baseline else None) != entry["baseSha"]:
        raise ValueError("CMS preparation used a different published article")
    if entry["action"] == "unpublish":
        from _article_visibility import unpublish_article
        article, _ = unpublish_article(baseline[1])
        if hashlib.sha256(article).hexdigest() != sources[entry["file"]]:
            raise ValueError("Unpublish candidate changed published prose")


def verify(sha, api, *, now=None):
    sha = revision(sha)
    api = ImmutableBlobs(api)
    _, raw = github_file(api, FILE, sha)
    items = receipts(raw, now=now)
    def live(entry):
        ref = api.get("/git/ref/heads/drafts/" + slug_for(entry["file"]))
        if not isinstance(ref, dict) or ref.get("ref") != "refs/heads/drafts/" + slug_for(entry["file"]) or ref.get("object", {}).get("type") != "commit" or ref["object"].get("sha") != entry["requestHead"]:
            raise ValueError("CMS author request was cancelled or superseded")
    for entry in items:
        live(entry)
        request_path = ".cms-requests/" + slug_for(entry["file"]) + ".json"
        blob, raw_request = github_file(api, request_path, entry["requestHead"], 8_000)
        expected = {"version": 1, "file": entry["file"], "action": entry["action"], "draftHead": entry["draftHead"],
                    "manifestSha": entry["manifestSha"], "blobSha": entry["articleBlobSha"], "baseSha": entry["baseSha"],
                    "approvedBy": entry["approvedBy"], "contentApproved": entry["action"] != "unpublish",
                    "requestedAt": entry["requestedAt"], "scheduledAt": entry["scheduledAt"]}
        request = parse(raw_request, canonical="compact", limit=8_000)
        if blob != entry["requestBlobSha"] or not isinstance(request, dict) or set(request) != set(expected) or type(request.get("version")) is not int or type(request.get("contentApproved")) is not bool or request != expected:
            raise ValueError("CMS receipt does not bind the approved request")
        commit = api.get("/git/commits/" + entry["requestHead"])
        if not isinstance(commit, dict) or commit.get("sha") != entry["requestHead"] or [parent.get("sha") for parent in commit.get("parents", [])] != [entry["draftHead"]]:
            raise ValueError("CMS request is not the direct child of its draft")
        compare = api.get("/compare/" + entry["draftHead"] + "..." + entry["requestHead"])
        if not isinstance(compare, dict) or compare.get("status") != "ahead" or compare.get("total_commits") != 1 or compare.get("merge_base_commit", {}).get("sha") != entry["draftHead"] or [item.get("filename") for item in compare.get("files", [])] != [request_path]:
            raise ValueError("CMS request commit changed more than its intent")
        changed = compare["files"][0]
        if changed.get("status") not in {"added", "modified"} or changed.get("sha") != entry["requestBlobSha"] or type(changed.get("changes")) is not int or changed["changes"] < 1 or "previous_filename" in changed:
            raise ValueError("CMS request diff is not an ordinary added/modified intent file")
        ancestor(api, entry["preparedAgainst"], sha)
        approved_sources(api, entry)
        for path, digest in entry["sourceSha256"].items():
            _, candidate = github_file(api, path, sha, 1_500_000)
            if hashlib.sha256(candidate).hexdigest() != digest:
                raise ValueError("CMS candidate payload differs from its preparation receipt")
    # Recheck all heads after validation; never accept a cached tracking ref.
    for entry in items:
        live(entry)
    return {"sha": sha, "activeRequests": len(items), "authorIntentVerified": True,
            "candidatePayloadVerified": True, "published": False}


def with_receipt(root: Path, files: dict[str, bytes], proof: dict, *, now=None):
    from _prepare_article_candidate import read_blob, git
    head = git(root, "rev-parse", "HEAD").decode().strip()
    prior = read_blob(root, head, FILE, optional=True)
    items = receipts(prior[1], now=now) if prior else []
    if any(item["file"] == proof["file"] for item in items):
        raise ValueError("Existing CMS receipt needs separate reviewed retirement")
    value = {"version": 1, "requests": sorted([*items, proof], key=lambda item: item["file"])}
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    receipts(raw, now=now)
    return {**files, FILE: raw}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sha")
    args = parser.parse_args()
    from _delivery import API
    print(json.dumps(verify(args.sha, API(REPO)), ensure_ascii=True))


if __name__ == "__main__":
    main()
