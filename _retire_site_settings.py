"""Prepare a read-only settings retirement review bundle; never publish.

Use --check for no filesystem writes, or an exclusive output beneath TEMP.
Applying the two data files requires a separate reviewed candidate with full
exact-SHA CI, same-repository PR/Preview and formal production verification.
"""
import argparse
import hashlib
import json
from pathlib import Path

from _cms_delivery import revision
from _retire_cms_receipts import git, write_bundle
from _site_settings_retirement import REPO, prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-main', required=True, help='Exact observed published main SHA')
    parser.add_argument('--output', type=Path, help='Exclusive review bundle outside the checkout; use TEMP')
    parser.add_argument('--check', action='store_true', help='Validate only; write no files')
    args = parser.parse_args()
    if not args.check and args.output is None:
        parser.error('--output or --check is required')
    root = Path(__file__).resolve().parent
    expected = revision(args.expected_main)
    if git(root, 'rev-parse', 'HEAD') != expected:
        raise ValueError('Local HEAD must equal the expected published main revision')
    from _delivery import API
    files = prepare(API(REPO), expected)
    if git(root, 'rev-parse', 'HEAD') != expected:
        raise ValueError('Local revision changed during settings retirement preparation')
    if not args.check:
        write_bundle(root, args.output, expected, files, settings=True)
    print(json.dumps({'publishedMain':expected, 'paths':sorted(files), 'noOp':not files,
        'sha256':{path:hashlib.sha256(raw).hexdigest() for path,raw in files.items()},
        'bundleWritten':bool(files) and not args.check, 'reviewPassed':False,
        'candidateCIPassed':False, 'published':False}))


if __name__ == '__main__': main()
