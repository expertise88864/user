# The legacy bulk replacement modified user rules, generated files and audit
# evidence. Keep this entrypoint fail-closed instead of silently rewriting them.
param([string]$NewDomain)

[Console]::Error.WriteLine('[STOPPED] Retired bulk domain replacement: no files were changed.')
[Console]::Error.WriteLine('Prepare a reviewed codex/* candidate with source-specific domain changes and regenerated outputs.')
[Console]::Error.WriteLine('Use _delivery.py to verify the exact candidate CI, PR and Preview before promotion; then verify main, deployment and smoke.')
exit 1
