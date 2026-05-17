#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run Pagefind via npx (download-on-demand, no manual binary install).

The standalone binary downloader in _setup_pagefind.py kept hitting 404s
because GitHub release filenames have drifted. npx pagefind@latest pulls
the npm package which Just Works(tm) on any platform with Node — and
Vercel build env already has Node + npm available.

Pagefind crawls the static HTML on disk and writes /pagefind/ (UI bundle
+ chunked search index, total ~3 MB but loaded only on search-button
click). Supports CJK out-of-the-box with BM25 ranking — replaces the
substring-match self-built search.

Runs as part of _run_quality.py BUILD_GENERATED_STEPS, after all HTML
generators but before any check that might reference the pagefind paths.

Usage:
    python _run_pagefind.py             # full build (default)
    python _run_pagefind.py --skip-if-cached  # skip if /pagefind/ already exists
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
PAGEFIND_DIR = ROOT / "pagefind"


def main() -> int:
    skip_if_cached = "--skip-if-cached" in sys.argv
    if skip_if_cached and PAGEFIND_DIR.exists() and any(PAGEFIND_DIR.iterdir()):
        print(f"[pagefind] /pagefind/ exists, skipping rebuild")
        return 0

    # Locate npx — Vercel has it, local dev probably has it
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        print(
            "[pagefind] npx not found in PATH. Install Node.js + npm, then retry.\n"
            "           Skipping pagefind build (not fatal — site still works with built-in search)."
        )
        return 0

    args = [
        npx, "--yes", "pagefind@latest",
        "--site", str(ROOT),
        "--output-path", str(PAGEFIND_DIR),
        "--root-selector", "main",
    ]
    print(f"[pagefind] {' '.join(args[:5])} ...")
    try:
        result = subprocess.run(args, cwd=str(ROOT), check=False, text=True,
                                capture_output=True, timeout=180)
    except subprocess.TimeoutExpired:
        print("[pagefind] timed out after 180s — skipping (not fatal)")
        return 0
    except Exception as exc:
        print(f"[pagefind] failed to invoke npx: {exc}")
        return 0  # Non-fatal — site still works with built-in search

    # Print only the summary lines from pagefind output
    out_lines = (result.stdout or "").splitlines() + (result.stderr or "").splitlines()
    for line in out_lines:
        if any(kw in line for kw in ["Indexed", "Finished", "language", "Warning", "Error"]):
            print(f"  {line}")

    if result.returncode != 0:
        print(f"[pagefind] exited with code {result.returncode} (non-fatal — search will fall back to built-in)")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
