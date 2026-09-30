#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run Pagefind via npx (download-on-demand, no manual binary install).

The standalone binary downloader in _setup_pagefind.py kept hitting 404s
because GitHub release filenames have drifted. npx pulls a PINNED pagefind
release (version pinned in install_binary below) from npm, which Just
Works(tm) on any platform with Node — and Vercel build env has Node + npm.

Pagefind crawls the static HTML on disk and writes /pagefind/ (UI bundle
+ chunked search index, total ~3 MB but loaded only on search-button
click). Supports CJK out-of-the-box with BM25 ranking — replaces the
substring-match self-built search.

Runs as part of _run_quality.py BUILD_GENERATED_STEPS, after all HTML
generators but before any check that might reference the pagefind paths.

Usage:
    python _run_pagefind.py             # full build (default)
    # Every invocation rebuilds: old fragments must not survive a new crawl.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import re
from pathlib import Path

from _gen_search_index import VisibleTextExtractor
from _sync_hub_catalog import load_catalog

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
PAGEFIND_DIR = ROOT / "pagefind"
PUBLIC_HTML_GLOB = "{*.html,blog/*.html,en/*.html,en/blog/*.html}"


def indexable_glob(root: Path) -> str:
    """Limit the crawler to current public visibility, including EN mirrors.

    Pagefind does not apply robots/noindex or the author catalog by itself.
    Inspect every candidate before clearing old output; malformed/missing
    visibility data must fail the build rather than index every HTML file.
    """
    unpublished = {item['slug'] for item in load_catalog(root) if item.get('unpublished')}
    paths = []
    for folder in (root, root / 'blog', root / 'en', root / 'en/blog'):
        for target in sorted(folder.glob('*.html')):
            relative = target.relative_to(root).as_posix()
            if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
                raise ValueError('Refuse indexing an HTML source outside the site root')
            if not re.fullmatch(r'(?:en/)?(?:blog/)?[a-z0-9-]+\.html', relative):
                raise ValueError('Unsupported public HTML path: ' + relative)
            if target.parent.name == 'blog' and target.stem in unpublished:
                continue
            parser = VisibleTextExtractor()
            parser.feed(target.read_text(encoding='utf-8'))
            parser.close()
            if not parser.noindex:
                paths.append(relative)
    if not paths:
        raise ValueError('No indexable public HTML sources')
    return paths[0] if len(paths) == 1 else '{' + ','.join(paths) + '}'


def main() -> int:
    # Never reuse an existing directory: it may contain fragments of private
    # files indexed by an older, broader crawl. Only this generated child is removed.
    if PAGEFIND_DIR.is_symlink() or PAGEFIND_DIR.resolve() != ROOT.resolve() / "pagefind":
        raise ValueError("Refuse clearing a Pagefind output outside the site root")
    # Locate npx — Vercel has it, local dev probably has it
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        print(
            "[pagefind] npx not found in PATH. Install Node.js + npm, then retry.\n"
            "           Pagefind build cannot complete."
        )
        return 1

    public_glob = indexable_glob(ROOT)
    if PAGEFIND_DIR.exists():
        shutil.rmtree(PAGEFIND_DIR)

    # CODE_REVIEW Phase 7 — pin the version. This runs on every Vercel build and
    # writes /pagefind/*.js that is SERVED TO VISITORS' browsers, so an unpinned
    # `pagefind@latest` means every deploy pulls (and ships) whatever npm's latest
    # is at that moment — a supply-chain hole with no review step. 1.5.2 is what
    # `@latest` resolved to at pin time; bump it deliberately after reviewing a
    # new release, not silently on every deploy.
    args = [
        npx, "--yes", "pagefind@1.5.2",
        "--site", str(ROOT),
        "--output-path", str(PAGEFIND_DIR),
        "--root-selector", "main",
    ]
    # npm exec forwards arguments through its script shell. Bash expands the
    # brace list before Pagefind receives --glob (unlike Windows cmd or dash).
    # Set the exact validated list through Pagefind's supported environment
    # option instead; override any inherited glob without changing the parent.
    env = os.environ.copy()
    env['PAGEFIND_GLOB'] = public_glob
    print(f"[pagefind] {' '.join(args[:5])} ...")
    try:
        result = subprocess.run(args, cwd=str(ROOT), check=False, text=True,
                                encoding="utf-8", errors="replace",
                                capture_output=True, timeout=180, env=env)
    except subprocess.TimeoutExpired:
        print("[pagefind] timed out after 180s — build failed")
        return 1
    except Exception as exc:
        print(f"[pagefind] failed to invoke npx: {exc}")
        return 1

    # Keep successful builds concise, but retain actionable failure diagnostics
    # (the CLI emits lowercase 'error:', which the old summary filter hid).
    out_lines = (result.stdout or "").splitlines() + (result.stderr or "").splitlines()
    for line in out_lines[-60:] if result.returncode != 0 else out_lines:
        if result.returncode != 0 or any(kw in line for kw in ["Indexed", "Finished", "language", "Warning", "Error"]):
            print(f"  {line}")

    if result.returncode != 0:
        print(f"[pagefind] exited with code {result.returncode} (build failed)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
