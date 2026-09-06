# Publish an explicitly prepared commit. Never stage, discard, stash or rebase
# the author's files. Resolve integration and review findings before deployment.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Command failed (exit $LASTEXITCODE). Deployment stopped." }
}

try {
    foreach ($tool in @('git', 'python', 'gh')) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
            throw "Required tool missing: $tool"
        }
    }
    Invoke-Checked git @('rev-parse', '--is-inside-work-tree')
    $branch = & git branch --show-current
    if ($LASTEXITCODE -ne 0 -or $branch -ne 'main') { throw 'Switch to the reviewed main branch first.' }
    $dirty = & git status --porcelain
    if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'Commit only the reviewed task changes before deployment; the working tree must be clean.' }
    Invoke-Checked gh @('auth', 'status')
    Invoke-Checked git @('fetch', 'origin', 'main')
    Invoke-Checked git @('merge-base', '--is-ancestor', 'origin/main', 'HEAD')
    $sha = & git rev-parse HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve the commit to publish.' }
    Invoke-Checked python @('_run_ci.py')
    $after = & git status --porcelain
    if ($LASTEXITCODE -ne 0 -or $after) {
        throw 'Build changed generated files. Review and commit them, then rerun the complete validation.'
    }
    $current = & git rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or $current -ne $sha) { throw 'HEAD changed during validation; rerun deployment.' }
    Invoke-Checked git @('push', 'origin', 'HEAD:refs/heads/main')
    Write-Host "Pushed $sha. Delivery remains pending until GitHub checks for this SHA succeed."
    Invoke-Checked python @('_verify_remote_ci.py', $sha)
    Write-Host "Delivered $sha`: local CI and the applicable GitHub checks passed."
    exit 0
} catch {
    Write-Host "[STOPPED] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
