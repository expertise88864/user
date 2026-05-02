# ============================================================
#  DermNotes - set-domain.ps1
#  Replaces every canonical/sitemap/og URL across the project.
#  Usage:
#    set-domain.bat dermnotes.vercel.app
#    set-domain.bat chendermatologist.com
#  Or just double-click set-domain.bat (will prompt).
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

# Normalize: strip protocol, trailing slash, leading www
$NewDomain = $NewDomain.Trim().ToLower()
$NewDomain = $NewDomain -replace '^https?://',''
$NewDomain = $NewDomain -replace '/.*$',''
if (-not $NewDomain) { Write-Host "[ERROR] Empty domain. Aborting."; exit 1 }

$root = $PSScriptRoot
Set-Location $root

# Discover currently-used domains by scanning sitemap.xml
$sitemap = Join-Path $root "sitemap.xml"
if (-not (Test-Path $sitemap)) {
    Write-Host "[ERROR] sitemap.xml not found in $root"
    exit 1
}
$sm = [IO.File]::ReadAllText($sitemap)
$oldDomains = New-Object System.Collections.Generic.List[string]
$regex = [regex]'https?://([a-zA-Z0-9.-]+)/'
foreach ($m in $regex.Matches($sm)) {
    $d = $m.Groups[1].Value.ToLower()
    if ($d -ne $NewDomain -and -not $oldDomains.Contains($d)) {
        $oldDomains.Add($d)
    }
}

if ($oldDomains.Count -eq 0) {
    Write-Host "[OK] sitemap already points to $NewDomain - nothing to do."
    exit 0
}

Write-Host ""
Write-Host ("Will replace: " + ($oldDomains -join ", ") + "  ->  $NewDomain")
Write-Host ""

$count = 0
$utf8noBOM = New-Object System.Text.UTF8Encoding($false)

Get-ChildItem -Path $root -Recurse -File -Include *.html,*.xml,*.txt,*.json,*.js,*.md | ForEach-Object {
    if ($_.FullName -match '\\.git\' -or $_.FullName -match '\node_modules\') { return }
    $c = [IO.File]::ReadAllText($_.FullName)
    $changed = $false
    foreach ($old in $oldDomains) {
        if ($c.Contains($old)) {
            $c = $c.Replace($old, $NewDomain)
            $changed = $true
        }
    }
    if ($changed) {
        [IO.File]::WriteAllText($_.FullName, $c, $utf8noBOM)
        $rel = $_.FullName.Substring($root.Length).TrimStart('\','/')
        Write-Host "  updated: $rel"
        $count++
    }
}

Write-Host ""
Write-Host "$count file(s) updated. Site now points to https://$NewDomain"
Write-Host ""
Write-Host "Next step: double-click deploy.bat to push the change to GitHub."
