# ============================================================
#  DermNotes - deploy.ps1
#  All deploy logic lives here. deploy.bat is just a launcher.
# ============================================================
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
Set-Location $root

Write-Host ""
Write-Host "============================================================"
Write-Host "  DermNotes deploy script"
Write-Host "  working dir: $root"
Write-Host "============================================================"
Write-Host ""

# 1. check git
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    Write-Host "[ERROR] Git is not installed or not on PATH." -ForegroundColor Red
    Write-Host "        Download: https://git-scm.com/download/win"
    Write-Host "        After install, close all cmd windows, open a fresh one, run again."
    return
}

# 2. ensure user.name / user.email are set globally
$userName = (& git config --global user.name) 2>$null
if (-not $userName) {
    $userName = Read-Host "GitHub display name (e.g., Chen Dermatologist)"
    & git config --global user.name $userName | Out-Null
}
$userEmail = (& git config --global user.email) 2>$null
if (-not $userEmail) {
    $userEmail = Read-Host "Email tied to your GitHub account"
    & git config --global user.email $userEmail | Out-Null
}

# 3. init repo if missing
if (-not (Test-Path ".git")) {
    Write-Host "[1/5] Initializing git repository..."
    & git init | Out-Null
    & git branch -M main | Out-Null
} else {
    Write-Host "[1/5] Repo already initialized."
}

# 4. ensure remote origin is set (idempotent)
$defaultRemote = "https://github.com/expertise88864/user.git"
$currentRemote = (& git config --get remote.origin.url) 2>$null
if (-not $currentRemote) {
    Write-Host ""
    Write-Host "[2/5] No GitHub remote yet."
    Write-Host "       Default: $defaultRemote"
    $remoteUrl = Read-Host "Press Enter to use default, or paste another GitHub repo URL"
    if (-not $remoteUrl) { $remoteUrl = $defaultRemote }
    & git remote add origin $remoteUrl
} else {
    Write-Host "[2/5] Remote origin already set: $currentRemote"
}

# 5. stage
Write-Host ""
Write-Host "[3/5] Staging changes..."
& git add -A
& git status --short

# 6. commit
Write-Host ""
$msg = Read-Host "Commit message (blank = 'deploy update')"
if (-not $msg) { $msg = "deploy update" }
& git commit -m $msg
if ($LASTEXITCODE -ne 0) {
    Write-Host "[info] Nothing new to commit. Continuing to push." -ForegroundColor Yellow
}

# 7. push
Write-Host ""
Write-Host "[4/5] Pushing to GitHub (branch: main)..."
& git push -u origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[warn] Push failed. Common causes:" -ForegroundColor Yellow
    Write-Host "  1) Authentication: GitHub no longer accepts your login password."
    Write-Host "     - Easiest: when the auth window pops up, choose 'Sign in with your browser'."
    Write-Host "     - Or Personal Access Token: https://github.com/settings/tokens (scope: repo)"
    Write-Host "       Then enter username + token (in the password field)."
    Write-Host "  2) The GitHub repo already has files (README etc)."
    Write-Host "     Run once in this folder, then re-run deploy:"
    Write-Host "       git pull origin main --allow-unrelated-histories"
    return
}

Write-Host ""
Write-Host "[5/5] DONE."
Write-Host "============================================================"
Write-Host " Pushed to GitHub."
Write-Host " If Vercel is connected, it auto-deploys in ~30 seconds."
Write-Host " Dashboard: https://vercel.com/dashboard"
Write-Host "============================================================"
