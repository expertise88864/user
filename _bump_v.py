#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Manually refresh numeric HTML cache stamps in ordinary deployed sources.

Exports, audit evidence and nested backups are never inputs. For a canonical
release, update _normalize_css_links.ASSET_VERSION and run the normal build;
that build restores its central version after a one-off manual refresh.
"""
from datetime import datetime
from pathlib import Path
import re
import sys
from _site_html import site_html_files


ROOT = Path(__file__).resolve().parent
PAT = re.compile(r'(\?v=)(\d{6,14})')


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        raise ValueError('Supply at most one numeric cache stamp')
    stamp = args[0] if args else datetime.now().strftime('%Y%m%d%H%M')
    if not re.fullmatch(r'[0-9]{6,14}', stamp):
        raise ValueError('Cache stamp must contain 6 to 14 ASCII digits')
    # Decode the whole inventory before writing, preserving original newlines.
    sources = [(path, path.read_bytes().decode('utf-8')) for path in site_html_files(ROOT)]
    total_files = total_subs = 0
    for path, source in sources:
        updated, count = PAT.subn(lambda match: match.group(1) + stamp, source)
        if updated != source:
            path.write_bytes(updated.encode('utf-8'))
            total_files += 1
            total_subs += count
    print(f'Bumped to v={stamp}: {total_subs} stamps in {total_files} files')
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
