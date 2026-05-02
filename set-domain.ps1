# ============================================================
#  DermNotes - set-domain.ps1
#  Safely swaps the site's own domain across all files.
#  Only the domain currently in <link rel="canonical"> of index.html
#  is treated as "the site's old domain" - third-party namespace URLs
#  (schema.org, w3.org, sitemaps.org, googleapis.com, ...) are untouched.
#  Usage:
#    set-domain.bat dermnotes.vercel.app
#    set-domain.bat chendermatologist.com
#  Or just double-click set-domain.bat to be prompted.
# ============================================================
param([string]$NewDomain)

if (-not $NewDomain) {
    Write-Host ""
    Write-Host "Tell me the domain that the site should use from now on."
    Write-Host "  Free Vercel:   dermnotes.vercel.app  (or whatever Vercel assigned you)"
    Write-Host "  Real domain:   chendermatologist.com"
    Write-Host ""
    $NewDomain = Read-Host "New domain"
}

$NewDomain = $NewDomain.Trim().ToLower()
$NewDomain = $NewDomain -replace '^https?://',''
$NewDomain = $NewDomain -replace '/.*$',''
if (-not $NewDomain) { Write-Host "[ERROR] Empty domain. Aborting."; exit 1 }

$root = $PSScriptRoot
Set-Location $root

# Find current site domain by reading <link rel="canonical"> in index.html.
# This is the SINGLE source of truth - we never replace any other URLs.
$indexHtml = Join-Path $root "index.html"
if (-not (Test-Path $indexHtml)) {
    Write-Host "[ERROR] index.html not found in $root"
    exit 1
}
$idx = [IO.File]::ReadAllText($indexHtml)
if ($idx -match '<link\s+rel="canonical"\s+href="https?://([^/"]+)') {
    $currentDomain = $matches[1].ToLower()
} else {
    Write-Host "[ERROR] Cannot detect current domain from index.html (no <link rel=canonical>)."
    exit 1
}

if ($currentDomain -eq $NewDomain) {
    Write-Host "[OK] index.html already points to $NewDomain - nothing to do."
    exit 0
}

Write-Host ""
Write-Host "Will replace site domain only:"
Write-Host "  $currentDomain  ->  $NewDomain"
Write-Host "(Third-party namespaces like schema.org / w3.org / sitemaps.org are NOT touched.)"
Write-Host ""

$count = 0
$utf8noBOM = New-Object System.Text.UTF8Encoding($false)

Get-ChildItem -Path $root -Recurse -File -Include *.html,*.xml,*.txt,*.json,*.js,*.md | ForEach-Object {
    if ($_.FullName -match '\\.git\' -or $_.FullName -match '\node_modules\') { return }
    $c = [IO.File]::ReadAllText($_.FullName)
    if ($c.Contains($currentDomain)) {
        $newC = $c.Replace($currentDomain, $NewDomain)
        [IO.File]::WriteAllText($_.FullName, $newC, $utf8noBOM)
        $rel = $_.FullName.Substring($root.Length).TrimStart('\','/')
        Write-Host "  updated: $rel"
        $count++
    }
}

Write-Host ""
Write-Host "$count file(s) updated. Site now points to https://$NewDomain"
Write-Host ""
Write-Host "Next: double-click deploy.bat to push the change to GitHub."
