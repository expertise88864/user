@echo off
REM ============================================================
REM  set-domain.bat
REM  Wrapper that calls set-domain.ps1 in the same folder.
REM  Usage:
REM    set-domain.bat dermnotes.vercel.app
REM    set-domain.bat chendermatologist.com
REM  Or just double-click and it will prompt.
REM ============================================================
chcp 65001 >/dev/null
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0set-domain.ps1" %*
echo.
pause
