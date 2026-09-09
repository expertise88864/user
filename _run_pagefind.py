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
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
PAGEFIND_DIR = ROOT / "pagefind"
PUBLIC_HTML_GLOB = "{*.html,blog/*.html,en/*.html,en/blog/*.html}"


def main() -> int:
    # Never reuse an existing directory: it may contain fragments of private
    # files indexed by an older, broader crawl. Only this generated child is removed.
    if PAGEFIND_DIR.is_symlink() or PAGEFIND_DIR.resolve() != ROOT.resolve() / "pagefind":
        raise ValueError("Refuse clearing a Pagefind output outside the site root")
    if PAGEFIND_DIR.exists():
        shutil.rmtree(PAGEFIND_DIR)

    # Locate npx — Vercel has it, local dev probably has it
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        print(
            "[pagefind] npx not found in PATH. Install Node.js + npm, then retry.\n"
            "           Pagefind build cannot complete."
        )
        return 1

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
        # Public route roots only: never index Git archives or local review files.
        "--glob", PUBLIC_HTML_GLOB,
    ]
    print(f"[pagefind] {' '.join(args[:5])} ...")
    try:
        result = subprocess.run(args, cwd=str(ROOT), check=False, text=True,
                                encoding="utf-8", errors="replace",
                                capture_output=True, timeout=180)
    except subprocess.TimeoutExpired:
        print("[pagefind] timed out after 180s — build failed")
        return 1
    except Exception as exc:
        print(f"[pagefind] failed to invoke npx: {exc}")
        return 1

    # Print only the summary lines from pagefind output
    out_lines = (result.stdout or "").splitlines() + (result.stderr or "").splitlines()
    for line in out_lines:
        if any(kw in line for kw in ["Indexed", "Finished", "language", "Warning", "Error"]):
            print(f"  {line}")

    if result.returncode != 0:
        print(f"[pagefind] exited with code {result.returncode} (build failed)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
