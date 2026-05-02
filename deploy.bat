@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   DermNotes deploy script
echo   working dir: %CD%
echo ============================================================
echo.

REM --- 1. check git ---
where git >/dev/null 2>/dev/null
if errorlevel 1 (
  echo [ERROR] Git is not installed or not on PATH.
  echo         Download: https://git-scm.com/download/win
  echo         After install, close ALL cmd windows, open a fresh one, and try again.
  pause
  exit /b 1
)

REM --- 2. ensure git user.name and user.email are set ---
git config --global user.name >/dev/null 2>/dev/null
if errorlevel 1 (
  set /p GUSER="GitHub display name (e.g., Chen Dermatologist): "
  git config --global user.name "!GUSER!"
)
git config --global user.email >/dev/null 2>/dev/null
if errorlevel 1 (
  set /p GMAIL="Email tied to your GitHub account: "
  git config --global user.email "!GMAIL!"
)

REM --- 3. init repo if missing ---
if not exist ".git" (
  echo [1/5] Initializing git repository...
  git init
  git branch -M main
) else (
  echo [1/5] Repo already initialized.
)

REM --- 4. ensure remote origin is set ---
set "DEFAULT_REMOTE=https://github.com/expertise88864/user.git"
git config --get remote.origin.url >/dev/null 2>/dev/null
if errorlevel 1 (
  echo.
  echo [2/5] No GitHub remote yet.
  echo        Default: !DEFAULT_REMOTE!
  set /p REMOTE_URL="Press Enter to use default, or paste another GitHub repo URL: "
  if "!REMOTE_URL!"=="" set "REMOTE_URL=!DEFAULT_REMOTE!"
  git remote add origin !REMOTE_URL!
  if errorlevel 1 (
    echo [info] Adding remote failed. Trying to update existing one...
    git remote set-url origin !REMOTE_URL!
  )
) else (
  echo [2/5] Remote origin already set:
  git config --get remote.origin.url
)

REM --- 5. stage everything ---
echo.
echo [3/5] Staging changes...
git add -A
git status --short

REM --- 6. commit ---
echo.
set /p MSG="Commit message (blank = 'deploy update'): "
if "!MSG!"=="" set "MSG=deploy update"
git commit -m "!MSG!"
if errorlevel 1 (
  echo [info] Nothing new to commit. Continuing to push.
)

REM --- 7. push ---
echo.
echo [4/5] Pushing to GitHub (branch: main)...
git push -u origin main
if errorlevel 1 (
  echo.
  echo [warn] Push failed. Common causes:
  echo   1) Auth: GitHub no longer accepts your login password.
  echo      - Easiest: Git for Windows pops up a browser - sign in there.
  echo      - Or use a Personal Access Token: https://github.com/settings/tokens
  echo        (scope: 'repo'); enter the token in the password field.
  echo   2) The remote repo on GitHub is not empty (e.g. has README).
  echo      Run once in this folder, then re-run deploy.bat:
  echo        git pull origin main --allow-unrelated-histories
  pause
  exit /b 1
)

echo.
echo [5/5] DONE.
echo ============================================================
echo  Pushed to GitHub.
echo  If Vercel is connected, it will auto-deploy in ~30 seconds.
echo  Vercel dashboard: https://vercel.com/dashboard
echo ============================================================
pause
endlocal
