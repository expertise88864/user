@echo off
REM E10 — Pagefind setup for static-site search with great Chinese tokenization.
REM
REM Run once to download the standalone Pagefind binary, then re-run anytime
REM after content changes to rebuild the search index.
REM
REM What it does:
REM   1. Downloads the Pagefind standalone binary (Windows x64) if not present
REM   2. Runs Pagefind against the entire site directory
REM   3. Generates ./pagefind/ — auto-loaded by the search widget on the site
REM
REM Output: ./pagefind/  (≈3-5 MB, mostly chunked index)
REM
REM Reference: https://pagefind.app/docs/installation/

setlocal enabledelayedexpansion
set PAGEFIND_VERSION=1.1.1
set PAGEFIND_URL=https://github.com/CloudCannon/pagefind/releases/download/v%PAGEFIND_VERSION%/pagefind-v%PAGEFIND_VERSION%-x86_64-pc-windows-msvc.zip
set PAGEFIND_DIR=%~dp0_bin
set PAGEFIND_EXE=%PAGEFIND_DIR%\pagefind.exe

if not exist "%PAGEFIND_EXE%" (
    echo [+] Downloading Pagefind v%PAGEFIND_VERSION%...
    if not exist "%PAGEFIND_DIR%" mkdir "%PAGEFIND_DIR%"
    powershell -NoProfile -Command "Invoke-WebRequest -Uri '%PAGEFIND_URL%' -OutFile '%PAGEFIND_DIR%\pagefind.zip'"
    powershell -NoProfile -Command "Expand-Archive -Path '%PAGEFIND_DIR%\pagefind.zip' -DestinationPath '%PAGEFIND_DIR%' -Force"
    del "%PAGEFIND_DIR%\pagefind.zip"
)

echo.
echo [+] Building Pagefind index against site root...
"%PAGEFIND_EXE%" --site "%~dp0" --output-path "%~dp0pagefind" --root-selector "main, article, body" --keep-index-url

echo.
echo [+] Done. Index written to %~dp0pagefind\
echo     Commit it to git so Vercel deploys the index alongside the site.
echo.
endlocal
