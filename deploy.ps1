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

# 5. PULL FIRST — sync any changes from admin / GitHub web edits before our local push
#    Self-healing: if previous deploy left repo in unmerged/rebase state, recover automatically.
Write-Host ""
Write-Host "[3/6] Syncing from GitHub (git pull --rebase) ..."

# 5a. Self-heal: abort any leftover rebase/merge from a prior failed deploy
if (Test-Path ".git/rebase-merge") {
    Write-Host "      [recover] previous rebase was interrupted — running git rebase --abort" -ForegroundColor DarkYellow
    & git rebase --abort 2>$null | Out-Null
}
if (Test-Path ".git/rebase-apply") {
    Write-Host "      [recover] previous am-rebase was interrupted — running git am --abort" -ForegroundColor DarkYellow
    & git am --abort 2>$null | Out-Null
}
if (Test-Path ".git/MERGE_HEAD") {
    Write-Host "      [recover] previous merge was interrupted — running git merge --abort" -ForegroundColor DarkYellow
    & git merge --abort 2>$null | Out-Null
}

# 5b. Check for leftover unmerged paths in the index (e.g. atom.xml/feed.xml from CI conflict)
$unmerged = & git ls-files --unmerged
if ($unmerged) {
    Write-Host "      [recover] unmerged paths detected — auto-resolving (taking HEAD version):" -ForegroundColor DarkYellow
    $files = ($unmerged | ForEach-Object { ($_ -split '\t')[1] } | Sort-Object -Unique)
    foreach ($f in $files) {
        Write-Host "        - $f"
        & git checkout HEAD -- "$f" 2>$null
    }
}

# 5c. Now safe to fetch + rebase
& git fetch origin main 2>$null
$hasRemote = $LASTEXITCODE -eq 0
if ($hasRemote) {
    # Stash any uncommitted local changes so rebase can run cleanly
    $stashed = $false
    $statusOut = & git status --porcelain
    if ($statusOut) {
        & git stash push -u -m "deploy-autostash" | Out-Null
        $stashed = $true
        Write-Host "      (uncommitted local changes auto-stashed)" -ForegroundColor DarkGray
    }
    & git pull --rebase origin main
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[warn] Pull failed during rebase — auto-resolving feed/sitemap conflicts (taking incoming version)..." -ForegroundColor Yellow
        # Most common conflicts are auto-generated files (sitemap.xml, blog/feed.xml, blog/atom.xml, en/*)
        # Take incoming (origin) version since we'll regen them anyway
        $autoResolveable = @('sitemap.xml','blog/feed.xml','blog/atom.xml')
        $unmergedNow = & git ls-files --unmerged
        if ($unmergedNow) {
            $conflictFiles = ($unmergedNow | ForEach-Object { ($_ -split '\t')[1] } | Sort-Object -Unique)
            $allAutoResolveable = $true
            foreach ($cf in $conflictFiles) {
                if ($autoResolveable -notcontains $cf -and -not $cf.StartsWith('en/')) { $allAutoResolveable = $false; break }
            }
            if ($allAutoResolveable) {
                foreach ($cf in $conflictFiles) {
                    & git checkout --theirs -- "$cf" 2>$null
                    & git add "$cf" 2>$null
                    Write-Host "        resolved: $cf (took incoming)" -ForegroundColor DarkGray
                }
                & git rebase --continue 2>&1 | Out-Null
                Write-Host "      [recovered] continuing rebase..." -ForegroundColor Green
            } else {
                Write-Host "[warn] Conflicts in non-auto-generated files. Manual resolution needed:" -ForegroundColor Yellow
                $conflictFiles | ForEach-Object { Write-Host "        - $_" }
                & git rebase --abort 2>$null | Out-Null
                if ($stashed) { & git stash pop 2>$null | Out-Null }
                return
            }
        } else {
            if ($stashed) { & git stash pop 2>$null | Out-Null }
            return
        }
    }
    if ($stashed) {
        & git stash pop
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[warn] Stash pop had conflicts — auto-resolving auto-generated files..." -ForegroundColor Yellow
            $autoResolveable = @('sitemap.xml','blog/feed.xml','blog/atom.xml')
            $unmergedNow = & git ls-files --unmerged
            if ($unmergedNow) {
                $conflictFiles = ($unmergedNow | ForEach-Object { ($_ -split '\t')[1] } | Sort-Object -Unique)
                foreach ($cf in $conflictFiles) {
                    if ($autoResolveable -contains $cf -or $cf.StartsWith('en/')) {
                        & git checkout --theirs -- "$cf" 2>$null
                        & git add "$cf" 2>$null
                    } else {
                        # Take stashed (local) version for non-generated files
                        & git checkout --theirs -- "$cf" 2>$null
                        & git add "$cf" 2>$null
                    }
                }
                & git stash drop 2>$null | Out-Null
                Write-Host "      [recovered] stash conflicts resolved" -ForegroundColor Green
            }
        }
    }
} else {
    Write-Host "      (no remote yet — skipping pull)" -ForegroundColor DarkGray
}

# 5b. pre-commit quality checks (added 2026-05-17)
# Same gates Vercel + GH Actions will run. Catching failures locally before
# push saves a CI round-trip and a broken-deploy email. The check is fast
# (~30s) compared to a failed CI build + redeploy (~3-5 min).
$pyExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pyExe) { $pyExe = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
if ($pyExe -and (Test-Path "_run_quality.py")) {
    Write-Host ""
    Write-Host "[3b/6] Running quality gates (meta / runtime-smoke / a11y / etc)..."
    & $pyExe _run_quality.py check
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "[FAIL] Quality gate(s) failed locally — CI would reject this push." -ForegroundColor Red
        $skip = Read-Host "Push anyway? (y = bypass + likely fail in CI, anything else = abort)"
        if ($skip -ne 'y' -and $skip -ne 'Y') {
            Write-Host "[aborted] Fix the gate errors above and re-run deploy." -ForegroundColor Yellow
            return
        }
        Write-Host "[warn] Bypassing gate failure — CI will likely fail too." -ForegroundColor Yellow
    } else {
        Write-Host "[ok] All quality gates pass." -ForegroundColor Green
    }
}

# 6. stage
Write-Host ""
Write-Host "[4/6] Staging changes..."
& git add -A
& git status --short

# 7. commit
Write-Host ""
$msg = Read-Host "Commit message (blank = 'deploy update')"
if (-not $msg) { $msg = "deploy update" }
& git commit -m $msg
if ($LASTEXITCODE -ne 0) {
    Write-Host "[info] Nothing new to commit. Continuing to push." -ForegroundColor Yellow
}

# 8. push
Write-Host ""
Write-Host "[5/6] Pushing to GitHub (branch: main)..."
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
Write-Host "[6/6] DONE."
Write-Host "============================================================"
Write-Host " Pushed to GitHub."
Write-Host " If Vercel is connected, it auto-deploys in ~30 seconds."
Write-Host " Dashboard: https://vercel.com/dashboard"
Write-Host "============================================================"
