@echo off
REM Retired bulk domain replacement; do not discard the failure with pause.
echo [STOPPED] Retired bulk domain replacement: no files were changed. 1>&2
echo Prepare a reviewed codex/* candidate with source-specific changes and regenerated outputs. 1>&2
echo Verify exact candidate CI, PR and Preview, then main, deployment and smoke with _delivery.py. 1>&2
exit /b 1
