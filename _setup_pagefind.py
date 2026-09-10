#!/usr/bin/env python
"""Compatibility entry point for the canonical, pinned Pagefind builder.

The old standalone downloader is retired. Both this command and the batch
launcher rebuild using _run_pagefind.py and its public-route boundary.
"""
import argparse

from _run_pagefind import main as build_index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--reindex', action='store_true',
        help='Rebuild the index (also the default; retained for compatibility).',
    )
    parser.parse_args(argv)
    return build_index()


if __name__ == '__main__':
    raise SystemExit(main())
