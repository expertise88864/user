@echo off
REM ============================================================
REM  DermNotes one-click deploy to GitHub
REM  Repo: https://github.com/expertise88864/user.git
REM ============================================================

chcp 65001 >/dev/null
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
  echo         After install, close this window, open a new one, and run deploy.bat again.
  pause
  exit /b 1
)

REM --- 2. configure user.name / user.email if missing ---
for /f "delims=" %%i in ('git config --global user.name 2^>nul') do set "GUSER=%%i"
if "!GUSER!"=="" (
  set /p GUSER="Enter your GitHub display name (e.g., Chen Dermatologist): "
  git config --global user.name "!GUSER!"
)
for /f "delims=" %%i in ('git config --global user.email 2^>nul') do set "GMAIL=%%i"
if "!GMAIL!"=="" (
  set /p GMAIL="Enter the email tied to your GitHub account: "
  git config --global user.email "!GMAIL!"
)

REM --- 3. init repo if missing ---
if not exist ".git" (
  echo.
  echo [1/5] Initializing git repository...
  git init
  git branch -M main
) else (
  echo [1/5] Repo already initialized.
)

REM --- 4. ensure remote origin set ---
set "DEFAULT_REMOTE=https://github.com/expertise88864/user.git"
git remote get-url origin >/dev/null 2>/dev/null
if errorlevel 1 (
  echo.
  echo [2/5] No GitHub remote yet.
  echo        Default: !DEFAULT_REMOTE!
  set /p REMOTE_URL="Press Enter to use default, or paste another GitHub repo URL: "
  if "!REMOTE_URL!"=="" set "REMOTE_URL=!DEFAULT_REMOTE!"
  git remote add origin !REMOTE_URL!
) else (
  for /f "delims=" %%i in ('git remote get-url origin') do set "CUR_REMOTE=%%i"
  echo [2/5] Remote origin already set: !CUR_REMOTE!
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
  echo [warn] Push failed. Two common causes:
  echo   1) Authentication: GitHub now needs a Personal Access Token, not a password.
  echo      Get one: https://github.com/settings/tokens (check the 'repo' scope)
  echo      Then re-run deploy.bat. Username = your GitHub login. Password = the token.
  echo   2) Remote not empty: if the repo on GitHub has files, run once:
  echo        git pull origin main --allow-unrelated-histories
  echo      then run deploy.bat again.
  pause
  exit /b 1
)

echo.
echo [5/5] DONE.
echo ============================================================
echo  Pushed to GitHub.
echo  If Vercel is connected, it auto-deploys in ~30 seconds.
echo  Final URL after DNS:  https://chendermatologist.com
echo  Vercel dashboard:     https://vercel.com/dashboard
echo ============================================================
pause
endlocal
