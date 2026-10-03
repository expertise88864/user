"""Prepare a review bundle for published CMS receipts; never commit or publish.

Only a separate retirement-only candidate may apply this bundle. It must then
pass independent review, exact-SHA remote CI, PR/Preview and formal delivery.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess

from _cms_delivery import FILE, MAX_BYTES, ImmutableBlobs, github_file, receipts, revision
from _cms_retirement import PREFIX, prepare, published_reviews, validate_record


def _local_blobs(root):
    """Read bounded immutable local controls, including full review manifests."""
    from _cms_generated_package import GitEvidence, run
    from _cms_patient_review import MAX_REVIEW_BYTES
    class LocalBlobs(GitEvidence):
        def get(self, path):
            if not path.startswith('/contents/'):
                return super().get(path)
            name, separator, head = path[len('/contents/'):].partition('?ref=')
            if not separator:
                raise ValueError('Retirement blob lacks immutable revision')
            head = revision(head)
            rows = [row for row in run(root, 'ls-tree', '-z', head, '--', name).split(b'\0') if row]
            if len(rows) != 1:
                raise ValueError('Retirement immutable control missing')
            header, actual_name = rows[0].split(b'\t', 1)
            mode, kind, blob = header.decode('ascii').split()
            if actual_name.decode('utf8') != name or mode != '100644' or kind != 'blob':
                raise ValueError('Retirement controls must be ordinary Git blobs')
            limit = MAX_REVIEW_BYTES if name.startswith('.cms-review/') else MAX_BYTES
            size = int(run(root, 'cat-file', '-s', revision(blob)))
            if not 0 <= size <= limit:
                raise ValueError('Retirement immutable control exceeds its bound')
            raw = run(root, 'cat-file', 'blob', blob)
            return {'type': 'file', 'path': name, 'sha': blob, 'size': size,
                    'encoding': 'base64', 'content': base64.b64encode(raw).decode('ascii')}
    return ImmutableBlobs(LocalBlobs(root))


def apply(root: Path, files: dict[str, bytes], *, expected_head: str, now=None):
    """Apply only two receipt files and exact archived manifest removals locally.

    This does not stage, commit, query live publication, or authorize delivery.
    Candidate hooks and both live gates still validate formal publication.
    """
    from _cms_patient_review import MAX_REVIEW_BYTES, read_control
    from _prepare_article_candidate import apply as apply_sources
    root = root.resolve()
    expected = revision(expected_head)
    archive = PREFIX + expected + '.json'
    if git(root, 'status', '--porcelain', '--untracked-files=all') or git(root, 'rev-parse', 'HEAD') != expected:
        raise ValueError('Retirement candidate workspace or revision changed')
    if set(files) != {FILE, archive} or any(not isinstance(raw, bytes) for raw in files.values()):
        raise ValueError('Unexpected retirement application paths')
    if receipts(files[FILE], now=now):
        raise ValueError('Retirement application must clear only published active requests')
    api = _local_blobs(root)
    blob, raw = github_file(api, FILE, expected)
    items = receipts(raw, now=now)
    if not items or archive in api.entries(expected) or os.path.lexists(root / archive):
        raise ValueError('Retirement requires an unarchived published receipt')
    if read_control(root, FILE, MAX_BYTES) != raw:
        raise ValueError('Retirement working receipt differs from published bytes')
    reviews = published_reviews(api, expected, items, now=now)
    validate_record(files[archive], expected, blob, items, reviews, now=now)
    # Validate every removal before writing anything. Git cleanliness alone
    # ignores raw newline conversions and must not authorize linked controls.
    for name, row in reviews.items():
        content = read_control(root, name, MAX_REVIEW_BYTES)
        if hashlib.sha256(content).hexdigest() != row['sha256']:
            raise ValueError('Retirement working review differs from published bytes')
    apply_sources(root, files, expected_head=expected)
    for name, row in reviews.items():
        # Recheck directly before unlink. Only immutable review controls are
        # removed; source articles, generated outputs and draft branches stay.
        content = read_control(root, name, MAX_REVIEW_BYTES)
        if hashlib.sha256(content).hexdigest() != row['sha256']:
            raise ValueError('Retirement review changed before removal')
        (root / name).unlink()
    return sorted(reviews)


def load_bundle(root: Path, destination: Path, expected: str):
    """Load the fixed external two-file bundle with bounded ordinary reads."""
    from _cms_patient_review import read_control
    destination = destination.absolute()
    if any(part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction())
           for part in (destination, *destination.parents)):
        raise ValueError('Retirement bundle contains a link')
    destination = destination.resolve()
    root = root.resolve()
    if destination.is_relative_to(root) or root.is_relative_to(destination) or not destination.is_dir():
        raise ValueError('Retirement bundle must be an external directory')
    archive = PREFIX + revision(expected) + '.json'
    return {FILE: read_control(destination, FILE, MAX_BYTES),
            archive: read_control(destination, archive, 256_000)}


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.PIPE, timeout=20).decode("utf-8").strip()


def write_bundle(root: Path, destination: Path, expected: str, files: dict[str, bytes], *, settings=False):
    """Exclusive new directory outside the checkout; never overwrite sources."""
    root = root.resolve()
    expected = revision(expected)
    if git(root, "rev-parse", "HEAD") != expected:
        raise ValueError("Local revision changed after retirement preparation")
    if not files:
        return
    # Fixed contracts only: callers cannot supply arbitrary output paths.
    if type(settings) is not bool:
        raise ValueError("Unexpected retirement bundle contract")
    if settings:
        from _site_settings_retirement import FILE as receipt_file, PREFIX as archive_prefix
    else:
        receipt_file, archive_prefix = FILE, PREFIX
    archive = archive_prefix + expected + ".json"
    if set(files) != {receipt_file, archive} or any(not isinstance(raw, bytes) for raw in files.values()):
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
    parser.add_argument("--apply", type=Path, help="Apply a reviewed external bundle to this clean local candidate only")
    args = parser.parse_args()
    if sum([args.check, args.output is not None, args.apply is not None]) != 1:
        parser.error("Exactly one of --output, --check or --apply is required")
    root = Path(__file__).resolve().parent
    expected = revision(args.expected_main)
    if git(root, "rev-parse", "HEAD") != expected:
        raise ValueError("Local HEAD must equal the expected published main revision")
    removed = []
    if args.apply is not None:
        files = load_bundle(root, args.apply, expected)
        removed = apply(root, files, expected_head=expected)
    else:
        from _delivery import API
        files = prepare(API("expertise88864/user"), expected)
    if git(root, "rev-parse", "HEAD") != expected:
        raise ValueError("Local revision changed during retirement preparation")
    if args.output is not None:
        write_bundle(root, args.output, expected, files)
    print(json.dumps({"publishedMain": expected, "paths": sorted(files), "noOp": not files,
                      "sha256": {path: hashlib.sha256(raw).hexdigest() for path, raw in files.items()},
                      "removedPaths": removed, "sourceApplied": args.apply is not None,
                      "bundleWritten": bool(files) and args.output is not None,
                      "reviewPassed": False, "candidateCIPassed": False, "published": False}))


if __name__ == "__main__":
    main()
