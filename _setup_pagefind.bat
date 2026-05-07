@echo off
REM Pagefind installer + indexer (delegates to Python for cross-platform robustness).
REM
REM Tries multiple Pagefind release versions / filenames automatically. If GitHub
REM 404s on one URL, falls through to the next. Manual download instructions
REM printed if everything fails.
cd /d "%~dp0"
python _setup_pagefind.py %*
pause
