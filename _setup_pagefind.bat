@echo off
REM Compatibility launcher: use the canonical pinned, public-only index builder.
setlocal
cd /d "%~dp0"
python _setup_pagefind.py %*
set "pagefind_exit=%ERRORLEVEL%"
pause
exit /b %pagefind_exit%
