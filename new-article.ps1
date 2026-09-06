# Use the same maintained structural template as the Python authoring workflow.
# A scaffold is a local draft; content/catalog/review remain explicit steps.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
try {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python is required.' }
    $slug = Read-Host 'New article slug (lowercase words separated by hyphens)'
    if ($slug -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*$') { throw 'Invalid article slug.' }
    & python _scaffold_article.py $slug
    if ($LASTEXITCODE -ne 0) { throw 'Scaffolding failed. No registration or publishing was attempted.' }
    Write-Host 'Draft created from the maintained template. Replace its article-specific content and metadata.'
    Write-Host 'Register the catalog entry, generate its raster share card, obtain physician review, then run python _run_ci.py.'
    exit 0
} catch {
    Write-Host "[STOPPED] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
