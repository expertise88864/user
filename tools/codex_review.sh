#!/usr/bin/env bash
# tools/codex_review.sh — 本 repo 唯一的外部 code-review 入口(Codex CLI, read-only)。
#
# 用法:
#   tools/codex_review.sh <mode> <base-ref> [task-context-file]
#   tools/codex_review.sh resume [session-id]
#
# mode:
#   diff      低風險/局部(文案、註解、CSS、tests-only)     medium / 額外檔 3 / findings 3
#   targeted  一般非 trivial 實作(預設)                     medium / 額外檔 12 / findings 5
#   deep      auth、金流、DB migration、併發、資安、大重構    high   / 額外檔 30 / findings 8
#   resume    第二輪(僅限 confirmed P0/P1/material P2 修正後);沿用第一輪 session
#
# 設計原則(勿改):
#   * 絕不把完整 diff 放進 prompt 或 argv;Codex 在 repo 內自行跑 git。
#   * --ignore-user-config 隔離 ~/.codex/config.toml(不載 plugins/apps/browser/notify/node_repl)。
#   * --sandbox read-only:Codex 不得寫檔、commit、跑 tests/build/lint/probe。
#   * 每個 task 最多兩輪;第二輪必須 resume 同一 session,不得重建。
#   * 結果只讀「最後一則訊息」(-o),不掃整份輸出 —— 否則 prompt 回顯裡的
#     "APPROVE or REQUEST_CHANGES" 會被誤判(舊 gate script 的真實 bug)。
#
# 環境變數(選用):
#   CODEX_REVIEW_VERIFICATION  本機驗證結果摘要(單/多行字串),會填入 prompt。
#   CODEX_REVIEW_HARDEN=0      關閉 web_search/apps 的額外 -c 硬化(若該 CLI 版本不認這些鍵)。
#   CODEX_REVIEW_STRICT=0      關閉 --strict-config。
set -uo pipefail

MODEL="gpt-5.6-sol"
HARDEN="${CODEX_REVIEW_HARDEN:-1}"
STRICT="${CODEX_REVIEW_STRICT:-1}"

die() { echo "[codex-review] ERROR: $*" >&2; exit 64; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)" \
  || die "必須在 git repository 內執行。"
REPO_NAME="$(basename "$REPO_ROOT")"
STATE_DIR="$REPO_ROOT/.codex-review"
mkdir -p "$STATE_DIR"
USAGE_TSV="$STATE_DIR/usage.tsv"
SESSION_FILE="$STATE_DIR/last_session_id"
PASS_FILE="$STATE_DIR/last_pass"
LAST_MSG="$STATE_DIR/last_message.txt"
RAW_LOG="$STATE_DIR/last_raw.log"

[ -s "$USAGE_TSV" ] || printf 'timestamp\trepository\tmode\tmodel\teffort\tbase_ref\tsession_id\ttokens_used\tresult\tfindings\tpass\n' > "$USAGE_TSV"

MODE="${1:-}"
[ -n "$MODE" ] || die "缺少 mode。用法: $0 <diff|targeted|deep> <base-ref> [task-context-file] | $0 resume [session-id]"

case "$MODE" in
  diff)     EFFORT="medium"; EXTRA_FILE_LIMIT=3;  FINDING_LIMIT=3 ;;
  targeted) EFFORT="medium"; EXTRA_FILE_LIMIT=12; FINDING_LIMIT=5 ;;
  deep)     EFFORT="high";   EXTRA_FILE_LIMIT=30; FINDING_LIMIT=8 ;;
  resume)   EFFORT="";       EXTRA_FILE_LIMIT="";  FINDING_LIMIT="" ;;
  *) die "未知 mode '$MODE'(可用:diff | targeted | deep | resume)" ;;
esac

# ---------- codex 旗標(read-only + 隔離) ----------
build_flags() {   # $1 = effort ; $2 = "resume" to build resume-compatible flags
  # 刻意用不含內層引號的 -c key=value:codex 對 value 先試 TOML,失敗即當字面字串
  # (bare `medium`/`disabled` → 字串;`false` → 布林)。跨 bash/PowerShell quoting 最穩。
  FLAGS=(--ignore-user-config --model "$MODEL" -c "model_reasoning_effort=$1" -o "$LAST_MSG")
  # CODE_REVIEW — `codex exec resume` (this CLI, 0.145.0-alpha.2) does NOT accept
  # `--sandbox` or `--cd`; those belong to `codex exec`. For resume, enforce
  # read-only via the `sandbox_mode` config override and run in the current dir
  # (resume already filters sessions by cwd, and we invoke from the repo root).
  if [ "${2:-}" = "resume" ]; then
    FLAGS+=(-c "sandbox_mode=read-only")
  else
    FLAGS+=(--sandbox read-only --cd "$REPO_ROOT")
  fi
  [ "$STRICT" = "1" ] && FLAGS+=(--strict-config)
  if [ "$HARDEN" = "1" ]; then
    FLAGS+=(-c "web_search=disabled" -c "features.apps=false")
  fi
  # 明確不使用:--ask-for-approval(此 CLI 的 exec 無此旗標,非互動預設即 never)、
  #             --skip-git-repo-check、--ephemeral(第二輪要 resume)、--dangerously-*。
}

# ---------- 解析輸出 ----------
extract_session_id() { grep -oiE 'session id:[[:space:]]*[0-9a-f-]{36}' "$RAW_LOG" 2>/dev/null | head -1 | grep -oiE '[0-9a-f-]{36}' || true; }
extract_tokens() { awk 'tolower($0) ~ /tokens used/ {found=1; next} found && $0 ~ /[0-9]/ {gsub(/[^0-9]/,"",$0); if (length($0)) {print $0; exit}}' "$RAW_LOG" 2>/dev/null || true; }
extract_result() {
  # CODE_REVIEW — the verdict is the LAST non-blank line, matched EXACTLY. A
  # substring grep over the whole message misreads "...I cannot APPROVE." as
  # APPROVE. Codex is instructed to end with exactly APPROVE / REQUEST_CHANGES.
  [ -s "$LAST_MSG" ] || { echo "UNKNOWN"; return; }
  local last
  last="$(grep -vE '^[[:space:]]*$' "$LAST_MSG" | tail -1 | tr -d '[:space:]')"
  case "$last" in
    APPROVE)         echo "APPROVE" ;;
    REQUEST_CHANGES) echo "REQUEST_CHANGES" ;;
    *)               echo "UNKNOWN" ;;
  esac
}
extract_findings() {
  [ -s "$LAST_MSG" ] || { echo "unavailable"; return; }
  local n; n="$(grep -ciE '^[[:space:]]*[-*]?[[:space:]]*severity:' "$LAST_MSG" || true)"
  if grep -q 'NO_ACTIONABLE_FINDINGS' "$LAST_MSG"; then echo 0
  elif [ -n "$n" ] && [ "$n" -gt 0 ] 2>/dev/null; then echo "$n"
  else echo "unavailable"; fi
}
# CODE_REVIEW — trustworthiness is decided by codex's EXIT CODE plus whether a
# clean verdict was produced, NOT by grepping the transcript. The old
# grep-the-raw-log approach false-tripped whenever the reviewed DIFF itself
# contained "rate limit" / "usage limit" / "try again at" — e.g. when reviewing
# THIS wrapper. A genuine rate-limit / crash makes `codex exec` exit non-zero
# and leaves no APPROVE/REQUEST_CHANGES verdict in the (freshly-truncated)
# last-message file.
run_untrusted() {   # $1 = codex exit code ; $2 = extracted verdict
  [ "$1" -ne 0 ] && [ "$2" = "UNKNOWN" ]
}

log_usage() {  # $1 mode $2 effort $3 base $4 pass
  local sid tok res fnd
  sid="$(extract_session_id)"; [ -n "$sid" ] || sid="unavailable"
  tok="$(extract_tokens)";     [ -n "$tok" ] || tok="unavailable"
  res="$(extract_result)"
  fnd="$(extract_findings)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$REPO_NAME" "$1" "$MODEL" "$2" "$3" "$sid" "$tok" "$res" "$fnd" "$4" >> "$USAGE_TSV"
  [ "$sid" = "unavailable" ] || printf '%s' "$sid" > "$SESSION_FILE"
  echo "$res"
}

# ================= resume(第二輪) =================
if [ "$MODE" = "resume" ]; then
  SID="${2:-}"
  if [ -z "$SID" ]; then
    [ -s "$SESSION_FILE" ] || die "找不到第一輪 session id($SESSION_FILE 不存在)。請以明確 session id 執行:$0 resume <session-id>。不要用 --last(可能 resume 到別的專案)。"
    SID="$(cat "$SESSION_FILE")"
  fi
  PREV_PASS="$(cat "$PASS_FILE" 2>/dev/null || echo 0)"
  [ "$PREV_PASS" = "1" ] || die "第二輪只能在完成第一輪之後執行(目前 pass=$PREV_PASS)。每個 task 最多兩輪。"

  # 第二輪的 effort 沿用第一輪(從 usage.tsv 最後一筆讀回),預設 medium。
  RESUME_EFFORT="$(tail -1 "$USAGE_TSV" | cut -f5)"; [ -n "$RESUME_EFFORT" ] || RESUME_EFFORT="medium"
  RESUME_BASE="$(tail -1 "$USAGE_TSV" | cut -f6)";   [ -n "$RESUME_BASE" ] || RESUME_BASE="unavailable"
  build_flags "$RESUME_EFFORT" resume

  read -r -d '' RESUME_PROMPT <<'RP' || true
Second and final review pass. Inspect only the corrections made for CONFIRMED
findings from the previous review. Verify that those defects are resolved and
that the corrections introduced no concrete regression. Do not repeat the
original full repository exploration. Remain strictly read-only: do not modify
files, run tests, builds, linters, package managers, application code, or ad hoc
probes, and do not use web search, browser, apps, connectors, or external MCP
tools. End with exactly APPROVE or REQUEST_CHANGES.
RP

  echo "[codex-review] resume session=$SID effort=$RESUME_EFFORT (pass 2/2)"
  : > "$LAST_MSG"
  codex exec resume "$SID" "${FLAGS[@]}" "$RESUME_PROMPT" 2>&1 | tee "$RAW_LOG"
  CODEX_RC="${PIPESTATUS[0]}"
  RESULT="$(extract_result)"
  # Untrusted run: do NOT advance pass state (finding 3) — a failed pass-2 must
  # not be permanently recorded as "done".
  if run_untrusted "$CODEX_RC" "$RESULT"; then
    echo "[codex-review] codex exec resume 未正常完成(rc=$CODEX_RC,無明確結論)—— 結果不可信,勿據此 push。" >&2
    log_usage "resume" "$RESUME_EFFORT" "$RESUME_BASE" 1 >/dev/null   # pass stays 1
    exit 4
  fi
  echo 2 > "$PASS_FILE"
  log_usage "resume" "$RESUME_EFFORT" "$RESUME_BASE" 2 >/dev/null
  echo; echo "[codex-review] result=$RESULT (pass 2/2)"
  case "$RESULT" in
    APPROVE) exit 0 ;;
    REQUEST_CHANGES) exit 2 ;;
    *) exit 5 ;;
  esac
fi

# ================= 第一輪 =================
BASE="${2:-}"
[ -n "$BASE" ] || die "缺少 base-ref。例:$0 $MODE origin/main [task-context-file]"
git -C "$REPO_ROOT" rev-parse --verify --quiet "${BASE}^{commit}" >/dev/null \
  || die "base-ref '$BASE' 不存在或無法解析為 commit。請提供有效的 base(如 origin/main)。"

CTX_FILE="${3:-}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
if [ -n "$CTX_FILE" ]; then
  [ -f "$CTX_FILE" ] || die "task-context 檔不存在:$CTX_FILE"
  if grep -qE '^(diff --git |@@ |index [0-9a-f]+\.\.)' "$CTX_FILE"; then
    die "task-context 檔看起來含有 diff。task-context 只能放任務摘要/驗收標準/預期行為/non-goals/本機測試結果/已知限制。"
  fi
  cp "$CTX_FILE" "$TMP/ctx.txt"
else
  printf '(no task context supplied)\n' > "$TMP/ctx.txt"
fi
if [ -n "${CODEX_REVIEW_VERIFICATION:-}" ]; then printf '%s\n' "$CODEX_REVIEW_VERIFICATION" > "$TMP/ver.txt";
else printf '(not supplied by caller)\n' > "$TMP/ver.txt"; fi

# 靜態 prompt(quoted heredoc:反引號/大括號皆為字面值,絕不含 diff)
cat > "$TMP/prompt.txt" <<'PROMPT'
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
PROMPT

# 以 sed 注入(多行內容用 r/d,避免特殊字元問題)
sed -i -e "s|{{MODE}}|$MODE|" -e "s|{{BASE}}|$BASE|" \
       -e "s|{{EXTRA_FILE_LIMIT}}|$EXTRA_FILE_LIMIT|" -e "s|{{FINDING_LIMIT}}|$FINDING_LIMIT|" "$TMP/prompt.txt"
sed -i -e "/{{TASK_CONTEXT}}/r $TMP/ctx.txt" -e "/{{TASK_CONTEXT}}/d" "$TMP/prompt.txt"
sed -i -e "/{{VERIFICATION_RESULTS}}/r $TMP/ver.txt" -e "/{{VERIFICATION_RESULTS}}/d" "$TMP/prompt.txt"

build_flags "$EFFORT"
echo "[codex-review] mode=$MODE effort=$EFFORT base=$BASE model=$MODEL (pass 1/2, read-only, user-config ignored)"
: > "$LAST_MSG"
codex exec "${FLAGS[@]}" "$(cat "$TMP/prompt.txt")" 2>&1 | tee "$RAW_LOG"
CODEX_RC="${PIPESTATUS[0]}"
RESULT="$(extract_result)"

# CODE_REVIEW — decide trust BEFORE recording pass state (finding 3): an
# incomplete/rate-limited first pass must not become eligible for the
# corrections-only resume flow.
if run_untrusted "$CODEX_RC" "$RESULT"; then
  echo "[codex-review] codex exec 未正常完成(rc=$CODEX_RC,無明確結論)—— 結果不可信,勿據此 push。" >&2
  log_usage "$MODE" "$EFFORT" "$BASE" 0 >/dev/null   # record the attempt; pass stays 0
  exit 4
fi
echo 1 > "$PASS_FILE"
log_usage "$MODE" "$EFFORT" "$BASE" 1 >/dev/null
echo; echo "[codex-review] result=$RESULT (pass 1/2)  usage → $USAGE_TSV"
case "$RESULT" in
  APPROVE) exit 0 ;;
  REQUEST_CHANGES) exit 2 ;;
  *) echo "[codex-review] 未取得明確 APPROVE/REQUEST_CHANGES;請人工檢視 $LAST_MSG" >&2; exit 5 ;;
esac
