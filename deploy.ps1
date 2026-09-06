# Promote only an already-reviewed, exact-SHA remote-CI-green candidate.
# Does not stage, stash, rebase, generate or overwrite the author's files.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
try {
    $deliverySha = & git rev-parse HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve candidate SHA.' }
    $deliveryDirty = & git status --porcelain
    if ($LASTEXITCODE -ne 0 -or $deliveryDirty) { throw 'Use a clean candidate worktree.' }
    & python _delivery.py verify $deliverySha --phase candidate
    if ($LASTEXITCODE -ne 0) { throw 'Candidate CI/Preview/PR not verified.' }
    $deliveryDirty = & git status --porcelain
    if ($LASTEXITCODE -ne 0 -or $deliveryDirty) { throw 'Candidate changed during remote verification.' }
    & git push origin "${deliverySha}:refs/heads/main"
    if ($LASTEXITCODE -ne 0) { throw 'Promotion blocked; preserve changes and inspect the gate.' }
    & python _delivery.py verify $deliverySha --phase main --wait 1800
    if ($LASTEXITCODE -ne 0) { throw 'Published SHA still needs successful hosted verification.' }
    & python _delivery.py production $deliverySha --wait 1800
    if ($LASTEXITCODE -ne 0) { throw 'Exact-SHA production deployment not verified.' }
    & python _delivery.py smoke $deliverySha --wait 300
    if ($LASTEXITCODE -ne 0) { throw 'Production page and asset smoke checks failed.' }
    Write-Host "Delivered ${deliverySha}: candidate/main CI, production deployment and smoke checks verified."
    exit 0
} catch {
    Write-Host "[STOPPED] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
