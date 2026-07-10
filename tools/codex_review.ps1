<#
tools/codex_review.ps1 — 本 repo 唯一的外部 code-review 入口(Codex CLI, read-only)。
與 tools/codex_review.sh 功能等價。

用法:
  .\tools\codex_review.ps1 <mode> <base-ref> [task-context-file]
  .\tools\codex_review.ps1 resume [session-id]

mode:
  diff      低風險/局部(文案、註解、CSS、tests-only)      medium / 額外檔 3 / findings 3
  targeted  一般非 trivial 實作(預設)                      medium / 額外檔 12 / findings 5
  deep      auth、金流、DB migration、併發、資安、大重構     high   / 額外檔 30 / findings 8
  resume    第二輪(僅限 confirmed P0/P1/material P2 修正後)

設計原則(勿改):
  * 絕不把完整 diff 放進 prompt 或 argv;Codex 在 repo 內自行跑 git。
  * --ignore-user-config 隔離 ~/.codex/config.toml(不載 plugins/apps/browser/notify/node_repl)。
  * --sandbox read-only:Codex 不得寫檔、commit、跑 tests/build/lint/probe。
  * 每個 task 最多兩輪;第二輪必須 resume 同一 session。
  * 結果只讀「最後一則訊息」(-o),不掃整份輸出(prompt 回顯會誤判)。

環境變數(選用):
  CODEX_REVIEW_VERIFICATION  本機驗證結果摘要,填入 prompt。
  CODEX_REVIEW_HARDEN=0      關閉 web_search/apps 的額外 -c 硬化。
  CODEX_REVIEW_STRICT=0      關閉 --strict-config。
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Mode,
    [Parameter(Mandatory = $false)][string]$BaseRef,
    [Parameter(Mandatory = $false)][string]$TaskContextFile
)

# 刻意用 Continue 而非 Stop:PS 5.1 對 native exe 做 2>&1 會把每行 stderr 包成 NativeCommandError,
# 在 Stop 模式下被誤判為終止錯誤。本腳本改以 $LASTEXITCODE 與明確 Die() 控制流程。
$ErrorActionPreference = 'Continue'
$Model = 'gpt-5.6-sol'
$Harden = if ($env:CODEX_REVIEW_HARDEN) { $env:CODEX_REVIEW_HARDEN } else { '1' }
$Strict = if ($env:CODEX_REVIEW_STRICT) { $env:CODEX_REVIEW_STRICT } else { '1' }

function Die([string]$Msg) { [Console]::Error.WriteLine("[codex-review] ERROR: $Msg"); exit 64 }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = & git -C $ScriptDir rev-parse --show-toplevel 2>$null
if ($LASTEXITCODE -ne 0 -or -not $RepoRoot) { Die '必須在 git repository 內執行。' }
$RepoRoot = $RepoRoot.Trim()
$RepoName = Split-Path -Leaf $RepoRoot
$StateDir = Join-Path $RepoRoot '.codex-review'
if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir | Out-Null }
$UsageTsv    = Join-Path $StateDir 'usage.tsv'
$SessionFile = Join-Path $StateDir 'last_session_id'
$PassFile    = Join-Path $StateDir 'last_pass'
$LastMsg     = Join-Path $StateDir 'last_message.txt'
$RawLog      = Join-Path $StateDir 'last_raw.log'

if (-not (Test-Path $UsageTsv)) {
    "timestamp`trepository`tmode`tmodel`teffort`tbase_ref`tsession_id`ttokens_used`tresult`tfindings`tpass" |
        Out-File -FilePath $UsageTsv -Encoding utf8
}

switch ($Mode) {
    'diff'     { $Effort = 'medium'; $ExtraFileLimit = 3;  $FindingLimit = 3 }
    'targeted' { $Effort = 'medium'; $ExtraFileLimit = 12; $FindingLimit = 5 }
    'deep'     { $Effort = 'high';   $ExtraFileLimit = 30; $FindingLimit = 8 }
    'resume'   { $Effort = '';       $ExtraFileLimit = ''; $FindingLimit = '' }
    default    { Die "未知 mode '$Mode'(可用:diff | targeted | deep | resume)" }
}

function Build-Flags([string]$EffortValue) {
    # 不含內層引號的 -c key=value:codex 對 value 先試 TOML,失敗即當字面字串。
    # 明確不使用:--ask-for-approval(exec 無此旗標)、--skip-git-repo-check、--ephemeral、--dangerously-*。
    $f = @('--ignore-user-config', '--model', $Model,
           '-c', "model_reasoning_effort=$EffortValue",
           '--sandbox', 'read-only', '--cd', $RepoRoot, '-o', $LastMsg)
    if ($Strict -eq '1') { $f += '--strict-config' }
    if ($Harden -eq '1') { $f += @('-c', 'web_search=disabled', '-c', 'features.apps=false') }
    return $f
}

function Get-SessionId {
    if (-not (Test-Path $RawLog)) { return 'unavailable' }
    $m = Select-String -Path $RawLog -Pattern 'session id:\s*([0-9a-fA-F-]{36})' | Select-Object -First 1
    if ($m) { return $m.Matches[0].Groups[1].Value }
    return 'unavailable'
}
function Get-TokensUsed {
    if (-not (Test-Path $RawLog)) { return 'unavailable' }
    $lines = Get-Content $RawLog
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '(?i)tokens used') {
            for ($j = $i; $j -lt [Math]::Min($i + 3, $lines.Count); $j++) {
                $d = ($lines[$j] -replace '[^0-9]', '')
                if ($d) { return $d }
            }
        }
    }
    return 'unavailable'
}
function Get-Result {
    if (-not (Test-Path $LastMsg)) { return 'UNKNOWN' }
    $t = Get-Content $LastMsg -Raw
    if (-not $t) { return 'UNKNOWN' }
    if ($t -match 'REQUEST_CHANGES') { return 'REQUEST_CHANGES' }
    if ($t -match 'APPROVE') { return 'APPROVE' }
    return 'UNKNOWN'
}
function Get-FindingCount {
    if (-not (Test-Path $LastMsg)) { return 'unavailable' }
    $t = Get-Content $LastMsg -Raw
    if ($t -match 'NO_ACTIONABLE_FINDINGS') { return 0 }
    $n = ([regex]::Matches($t, '(?im)^\s*[-*]?\s*severity:')).Count
    if ($n -gt 0) { return $n }
    return 'unavailable'
}
function Test-RateLimited {
    if (-not (Test-Path $RawLog)) { return $false }
    $t = Get-Content $RawLog -Raw
    return ($t -match '(?i)usage limit|rate limit|try again at')
}
function Write-Usage([string]$M, [string]$E, [string]$B, [int]$Pass) {
    $sid = Get-SessionId; $tok = Get-TokensUsed; $res = Get-Result; $fnd = Get-FindingCount
    $ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    "$ts`t$RepoName`t$M`t$Model`t$E`t$B`t$sid`t$tok`t$res`t$fnd`t$Pass" |
        Out-File -FilePath $UsageTsv -Append -Encoding utf8
    if ($sid -ne 'unavailable') { $sid | Out-File -FilePath $SessionFile -Encoding ascii -NoNewline }
    return $res
}

# ================= resume(第二輪) =================
if ($Mode -eq 'resume') {
    $Sid = $BaseRef   # 第二個位置參數在 resume 模式下即 session-id
    if (-not $Sid) {
        if (-not (Test-Path $SessionFile)) {
            Die "找不到第一輪 session id($SessionFile 不存在)。請以明確 session id 執行:.\tools\codex_review.ps1 resume <session-id>。不要用 --last(可能 resume 到別的專案)。"
        }
        $Sid = (Get-Content $SessionFile -Raw).Trim()
    }
    $PrevPass = if (Test-Path $PassFile) { (Get-Content $PassFile -Raw).Trim() } else { '0' }
    if ($PrevPass -ne '1') { Die "第二輪只能在完成第一輪之後執行(目前 pass=$PrevPass)。每個 task 最多兩輪。" }

    $last = (Get-Content $UsageTsv | Select-Object -Last 1) -split "`t"
    $ResumeEffort = if ($last.Count -ge 5 -and $last[4]) { $last[4] } else { 'medium' }
    $ResumeBase   = if ($last.Count -ge 6 -and $last[5]) { $last[5] } else { 'unavailable' }

    $ResumePrompt = @'
Second and final review pass. Inspect only the corrections made for CONFIRMED
findings from the previous review. Verify that those defects are resolved and
that the corrections introduced no concrete regression. Do not repeat the
original full repository exploration. Remain strictly read-only: do not modify
files, run tests, builds, linters, package managers, application code, or ad hoc
probes, and do not use web search, browser, apps, connectors, or external MCP
tools. End with exactly APPROVE or REQUEST_CHANGES.
'@

    $flags = Build-Flags $ResumeEffort
    Write-Host "[codex-review] resume session=$Sid effort=$ResumeEffort (pass 2/2)"
    '' | Out-File -FilePath $LastMsg -Encoding utf8
    $args2 = @('exec', 'resume', $Sid) + $flags + @($ResumePrompt)
    & codex @args2 2>&1 | Tee-Object -FilePath $RawLog
    '2' | Out-File -FilePath $PassFile -Encoding ascii -NoNewline
    $result = Write-Usage 'resume' $ResumeEffort $ResumeBase 2
    Write-Host "`n[codex-review] result=$result (pass 2/2)"
    if (Test-RateLimited) { [Console]::Error.WriteLine('[codex-review] Codex 限流,結果不可信。'); exit 4 }
    if ($result -eq 'APPROVE') { exit 0 } elseif ($result -eq 'REQUEST_CHANGES') { exit 2 } else { exit 5 }
}

# ================= 第一輪 =================
if (-not $BaseRef) { Die "缺少 base-ref。例:.\tools\codex_review.ps1 $Mode origin/main [task-context-file]" }
& git -C $RepoRoot rev-parse --verify --quiet "$BaseRef^{commit}" | Out-Null
if ($LASTEXITCODE -ne 0) { Die "base-ref '$BaseRef' 不存在或無法解析為 commit。請提供有效的 base(如 origin/main)。" }

if ($TaskContextFile) {
    if (-not (Test-Path $TaskContextFile)) { Die "task-context 檔不存在:$TaskContextFile" }
    $ctx = Get-Content $TaskContextFile -Raw
    if ($ctx -match '(?m)^(diff --git |@@ |index [0-9a-f]+\.\.)') {
        Die 'task-context 檔看起來含有 diff。task-context 只能放任務摘要/驗收標準/預期行為/non-goals/本機測試結果/已知限制。'
    }
} else { $ctx = '(no task context supplied)' }
$ver = if ($env:CODEX_REVIEW_VERIFICATION) { $env:CODEX_REVIEW_VERIFICATION } else { '(not supplied by caller)' }

$PromptTemplate = @'
You are an independent senior software engineer performing a read-only code
review of an implementation written by another coding model.

REVIEW MODE:
{{MODE}}

REVIEW BASE:
{{BASE}}

TASK CONTEXT:
{{TASK_CONTEXT}}

LOCAL VERIFICATION:
{{VERIFICATION_RESULTS}}

Operate strictly in read-only mode.

Do not modify, create, delete, rename, format, stage, commit, revert, or patch
any file.

Do not install dependencies.

Do not run tests, builds, linters, formatters, package managers, migrations,
application code, or ad hoc Python/Node probes.

Do not use web search, browser, computer use, apps, connectors, plugins, or
external MCP tools.

Start from the repository's actual Git state:

1. Inspect `git status --short`.
2. Inspect staged and unstaged changes.
3. When a valid base ref is supplied, calculate the merge base and inspect the
   branch diff against it.
4. Include relevant untracked source files explicitly.
5. Identify the exact runtime behavior changed by the implementation.

Start from the diff, but do not limit the review to changed lines when directly
related repository context is required.

Repository exploration must be driven by a concrete concern raised by the
diff.

Prioritize:

1. Direct callers and downstream consumers.
2. Referenced interfaces, schemas, shared types, and contracts.
3. Tests directly related to the changed behavior.
4. One analogous implementation when required.

Do not perform a whole-repository audit.

Unless a concrete P0 or P1 risk requires expansion:

- inspect no more than {{EXTRA_FILE_LIMIT}} additional files outside the diff
- report no more than {{FINDING_LIMIT}} findings
- do not inspect unrelated directories
- do not inspect generated files, vendored code, build output, caches, or
  dependency directories
- stop when no high-confidence actionable failure path remains

Report only concrete defects involving:

- incorrect behavior
- regression
- security or authorization
- data integrity
- compatibility
- concurrency or idempotency
- resource leaks
- material error-handling failures
- realistic performance pathologies

Do not report:

- style preferences
- naming preferences
- formatting
- optional refactors
- generic best practices
- speculative concerns
- pre-existing unrelated problems
- missing comments
- duplicated findings
- issues already prevented by existing validation or contracts

Every finding must include:

- severity: P0, P1, P2, or P3
- confidence: high, medium, or low
- exact file and smallest useful line range
- concrete trigger
- observable failure
- repository evidence
- why existing tests do not detect it
- minimal correction direction

If no qualifying defect is found, output:

NO_ACTIONABLE_FINDINGS

End with exactly one of:

APPROVE
REQUEST_CHANGES
'@

$prompt = $PromptTemplate.
    Replace('{{MODE}}', $Mode).
    Replace('{{BASE}}', $BaseRef).
    Replace('{{EXTRA_FILE_LIMIT}}', [string]$ExtraFileLimit).
    Replace('{{FINDING_LIMIT}}', [string]$FindingLimit).
    Replace('{{TASK_CONTEXT}}', $ctx).
    Replace('{{VERIFICATION_RESULTS}}', $ver)

$flags = Build-Flags $Effort
Write-Host "[codex-review] mode=$Mode effort=$Effort base=$BaseRef model=$Model (pass 1/2, read-only, user-config ignored)"
'' | Out-File -FilePath $LastMsg -Encoding utf8
$args1 = @('exec') + $flags + @($prompt)
& codex @args1 2>&1 | Tee-Object -FilePath $RawLog

'1' | Out-File -FilePath $PassFile -Encoding ascii -NoNewline
$result = Write-Usage $Mode $Effort $BaseRef 1
Write-Host "`n[codex-review] result=$result (pass 1/2)  usage -> $UsageTsv"
if (Test-RateLimited) { [Console]::Error.WriteLine('[codex-review] Codex 限流,結果不可信,勿據此 push。'); exit 4 }
if ($result -eq 'APPROVE') { exit 0 }
elseif ($result -eq 'REQUEST_CHANGES') { exit 2 }
else { [Console]::Error.WriteLine("[codex-review] 未取得明確 APPROVE/REQUEST_CHANGES;請人工檢視 $LastMsg"); exit 5 }
