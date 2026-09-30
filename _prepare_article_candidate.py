"""Extract one immutable CMS bundle onto a clean local candidate, never merge it.

This prepares source files only. Independent review, medical approval, complete
candidate CI/Preview and the normal delivery policy still govern publication.
No refs, remote files, queue entries or production deployments are changed here.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess

SHA = re.compile(r"[a-f0-9]{40}")
ARTICLE = re.compile(r"blog/([a-z0-9]+(?:-[a-z0-9]+)*)\.html")
MAX_HTML = 1_500_000
MAX_ENCODED_MEDIA = 1_900_000
CATALOG = "blog/blog-shared.js"


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.PIPE)


def revision(value: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value) or value == "0" * 40:
        raise ValueError("Expected an exact full Git SHA")
    return value


def read_blob(root: Path, commit: str, path: str, optional: bool = False) -> tuple[str, bytes] | None:
    entries = git(root, "ls-tree", "-z", commit, "--", path).split(b"\0")
    entries = [entry for entry in entries if entry]
    if not entries and optional:
        return None
    if len(entries) != 1:
        raise ValueError("Missing or ambiguous bundle file: " + path)
    fields, actual_path = entries[0].split(b"\t", 1)
    mode, kind, sha = fields.decode("ascii").split()
    if actual_path.decode("utf-8") != path or mode != "100644" or kind != "blob":
        raise ValueError("Bundle files must be ordinary non-executable blobs: " + path)
    size = int(git(root, "cat-file", "-s", sha))
    if size > MAX_HTML:
        raise ValueError("Bundle file exceeds size limit: " + path)
    return revision(sha), git(root, "cat-file", "blob", sha)


def validate_metadata(value: object) -> dict:
    names = {"title_en", "tag", "tag_en", "cat", "date"}
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError("New articles require validated bilingual metadata")
    for name in ("title_en", "tag", "tag_en"):
        text = value[name]
        if not isinstance(text, str) or not text.strip() or len(text) > (180 if name == "title_en" else 64) or re.search(r"[\x00-\x1f]", text):
            raise ValueError("Invalid article metadata: " + name)
    if value["cat"] not in {"myth", "rx", "note", "research"} or not isinstance(value["date"], str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value["date"]):
        raise ValueError("Invalid article category/date")
    date.fromisoformat(value["date"])
    return value


class ArticleTitle(HTMLParser):
    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.found = 0
        self.parts: list[str] = []
        self.label = None
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag == "h1":
            self.found += 1
            self.depth += 1
            self.label = dict(attrs).get("data-zh")

    def handle_endtag(self, tag):
        if tag == "h1":
            self.depth = 0

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)

    def title(self) -> str:
        text = (self.label or "".join(self.parts)).strip()
        if self.found != 1 or not text or len(text) > 300:
            raise ValueError("Article must have one unambiguous title")
        return text


def catalog_for_new_article(root: Path, slug: str, source: str, metadata: dict) -> bytes:
    from _sync_hub_catalog import load_catalog
    items = load_catalog(root)  # Evaluate only the clean, trusted candidate catalog.
    if any(item["slug"] == slug for item in items):
        raise ValueError("New article slug already exists in the catalog")
    original = (root / CATALOG).read_bytes().decode("utf-8")
    matches = list(re.finditer(r"DN\.ARTICLES\s*=\s*\[", original))
    if len(matches) != 1:
        raise ValueError("Catalog insertion point is ambiguous")
    entry = {"slug": slug, "title": ArticleTitle(source).title(), **metadata, "emoji": ""}
    # Existing generators recognize the catalog's unquoted keys / single-quoted
    # slug. Preserve that contract; JSON object keys silently evade some readers.
    line = catalog_literal(entry)
    newline = "\r\n" if "\r\n" in original else "\n"
    point = matches[0].end()
    return (original[:point] + newline + "    " + line + "," + original[point:]).encode("utf-8")


def catalog_literal(entry: dict) -> str:
    fields = []
    for key, value in entry.items():
        if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", key):
            raise ValueError("Unsupported catalog field")
        if isinstance(value, str):
            # JSON's escapes are also valid within a JS single-quoted string;
            # additionally escape apostrophes instead of interpolating raw text.
            encoded = "'" + json.dumps(value, ensure_ascii=False)[1:-1].replace("'", "\\'").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029") + "'"
        else:
            encoded = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        fields.append(key + ":" + encoded)
    return "{ " + ", ".join(fields) + " }"


def plan(root: Path, head: str, file: str, blob_sha: str) -> dict[str, bytes]:
    head, blob_sha = revision(head), revision(blob_sha)
    match = ARTICLE.fullmatch(file) if isinstance(file, str) else None
    if not match or len(match[1]) > 100 or match[1] in {"index", "topics", "charts"}:
        raise ValueError("Invalid article path")
    slug = match[1]
    main = git(root, "rev-parse", "HEAD").decode().strip()
    # The destination must be a clean candidate based on current main; callers
    # validate latest origin/main and the exact queue head before invoking us.
    if git(root, "status", "--porcelain", "--untracked-files=all").strip():
        raise ValueError("Candidate workspace must be clean")
    manifest_blob = read_blob(root, head, ".cms-drafts/" + slug + ".json")
    record = json.loads(manifest_blob[1].decode("utf-8"))
    if not isinstance(record, dict) or type(record.get("version")) is not int or record.get("version") != 1 or record.get("file") != file or record.get("blobSha") != blob_sha or record.get("status") != "draft":
        raise ValueError("Legacy, mismatched or unsupported draft manifest")
    base_main = revision(record.get("baseMain"))
    # --batch-check reports missing objects with exit 0. This distinguishes
    # untrusted metadata from genuine local Git failures without suppressing
    # network/fetch or repository command errors elsewhere in preparation.
    base_object = subprocess.run(["git", "cat-file", "--batch-check"], cwd=root,
                                 input=(base_main + "\n").encode("ascii"),
                                 capture_output=True, check=True, timeout=20)
    fields = base_object.stdout.decode("ascii").split()
    if len(fields) != 3 or fields[:2] != [base_main, "commit"] or not fields[2].isdigit():
        raise ValueError("Draft base is not an available commit")
    ancestry = subprocess.run(["git", "merge-base", "--is-ancestor", base_main, main], cwd=root, capture_output=True)
    if ancestry.returncode == 1:
        raise ValueError("Draft base is not an ancestor of current main")
    if ancestry.returncode != 0:
        raise subprocess.CalledProcessError(ancestry.returncode, ancestry.args, ancestry.stdout, ancestry.stderr)
    base_sha = record.get("baseSha")
    if base_sha is not None:
        revision(base_sha)
    current = read_blob(root, main, file, optional=True)
    if (current[0] if current else None) != base_sha:
        raise ValueError("Published article changed; preserve draft for manual integration")
    article = read_blob(root, head, file)
    if article[0] != blob_sha:
        raise ValueError("Queued article revision no longer matches its manifest")
    source = article[1].decode("utf-8")
    if not re.search(r"<html[\s>]", source, re.I) or not re.search(r"</html\s*>", source, re.I):
        raise ValueError("Invalid article document")
    assets = record.get("assets")
    if not isinstance(assets, list) or len(assets) > 16:
        raise ValueError("Invalid draft media manifest")
    result = {file: article[1]}
    encoded_total = 0
    for asset in assets:
        path = asset.get("path") if isinstance(asset, dict) else None
        match = re.fullmatch(r"blog/images/" + re.escape(slug) + r"/([a-f0-9]{64})\.(webp|png|jpg|gif)", path or "")
        if not match or path in result:
            raise ValueError("Invalid or duplicate managed media path")
        sha, content = read_blob(root, head, path)
        if sha != asset.get("sha") or len(content) != asset.get("size") or hashlib.sha256(content).hexdigest() != match[1]:
            raise ValueError("Media digest/size changed")
        signatures = {"png": content.startswith(b"\x89PNG\r\n\x1a\n"), "jpg": content.startswith(b"\xff\xd8\xff"),
                      "gif": content.startswith((b"GIF87a", b"GIF89a")), "webp": content[:4] == b"RIFF" and content[8:12] == b"WEBP"}
        if len(content) < 8 or not signatures[match[2]]:
            raise ValueError("Invalid managed raster image")
        encoded_total += ((len(content) + 2) // 3) * 4
        if encoded_total > MAX_ENCODED_MEDIA:
            raise ValueError("Media bundle exceeds reloadable limit")
        result[path] = content
    if current is None:
        result[CATALOG] = catalog_for_new_article(root, slug, source, validate_metadata(record.get("metadata")))
    return result


def apply(root: Path, files: dict[str, bytes], *, expected_head: str | None = None) -> None:
    # Validate all destination ancestors before writing any file. Resolve checks
    # also reject symlinks/junctions pointing outside the intended checkout.
    root = root.resolve()
    if git(root, "status", "--porcelain", "--untracked-files=all").strip():
        raise ValueError("Candidate workspace changed after validation")
    if expected_head is not None and git(root, "rev-parse", "HEAD").decode().strip() != revision(expected_head):
        raise ValueError("Candidate revision changed after validation")
    for path in files:
        destination = root / path
        if not destination.resolve().is_relative_to(root):
            raise ValueError("Destination escapes candidate workspace")
        for part in (destination, *destination.parents):
            if part == root:
                break
            if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
                raise ValueError("Candidate destination contains a link")
    for path, content in files.items():
        destination = root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--blob", required=True)
    parser.add_argument("--check", action="store_true", help="Validate only; never write source files")
    parser.add_argument("--request", action="store_true", help="Require an active, version-bound author request on origin")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    proof = None
    if args.request:
        from _validate_article_request import request_plan
        from _cms_delivery import with_receipt
        files, proof = request_plan(root, args.head, args.file, args.blob)
        files = with_receipt(root, files, proof)
    else:
        files = plan(root, args.head, args.file, args.blob)
    if not args.check:
        apply(root, files, expected_head=proof["preparedAgainst"] if proof else None)
    print(json.dumps({"draftHead": args.head, "articleBlob": args.blob, "paths": sorted(files), "request": proof, "published": False}))


if __name__ == "__main__":
    main()
