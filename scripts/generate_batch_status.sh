#!/usr/bin/env bash
# Generate batch_status.json and batches/README.md from test_reports_comprehensive/{DATE}/batches/.
# Reads each batch_N/summary.json and optional batch_N/deferred (reason/ticket); produces
# a consolidated status file and human-readable table per GAP_FIX plan §6.2 and tasks Phase 3.3.
#
# Usage: ./scripts/generate_batch_status.sh BATCH_REPORT_BASE
# Example: ./scripts/generate_batch_status.sh test_reports_comprehensive/2026-02-12/batches
#
# Requires: jq, run_phase_12a_batched.sh (for --list-batches).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BATCH_REPORT_BASE="${1:-}"

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required. Install jq to run generate_batch_status.sh." >&2
  exit 1
fi

if [[ -z "$BATCH_REPORT_BASE" ]]; then
  echo "Usage: $0 BATCH_REPORT_BASE" >&2
  echo "Example: $0 test_reports_comprehensive/2026-02-12/batches" >&2
  exit 1
fi

if [[ ! -d "$BATCH_REPORT_BASE" ]]; then
  echo "Error: Directory not found: $BATCH_REPORT_BASE" >&2
  exit 1
fi

cd "$PROJECT_DIR"

# Get batch list (number and name) from batched script
BATCH_LIST_FILE=$(mktemp)
trap 'rm -f "$BATCH_LIST_FILE"' EXIT
"$SCRIPT_DIR/run_phase_12a_batched.sh" --list-batches > "$BATCH_LIST_FILE" 2>/dev/null || true
if [[ ! -s "$BATCH_LIST_FILE" ]]; then
  echo "Error: No batch definitions from run_phase_12a_batched.sh --list-batches." >&2
  exit 1
fi

DATE=$(basename "$(dirname "$BATCH_REPORT_BASE")")
GENERATED_AT=$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z 2>/dev/null || echo "")
BATCHES_JSON="[]"

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  num=$(echo "$line" | cut -f1)
  name=$(echo "$line" | cut -f2)
  [[ ! "$num" =~ ^[0-9]+$ ]] && continue

  status="not_run"
  last_run=""
  log_path=""
  junit_path=""
  deferred_reason=""

  summary_file="${BATCH_REPORT_BASE}/batch_${num}/summary.json"
  deferred_file="${BATCH_REPORT_BASE}/batch_${num}/deferred"

  if [[ -f "$deferred_file" ]]; then
    status="deferred"
    deferred_reason=$(cat "$deferred_file" 2>/dev/null || echo "deferred")
  fi

  if [[ -f "$summary_file" ]]; then
    if [[ "$status" != "deferred" ]]; then
      exit_code=$(jq -r '.exit_code // 999' "$summary_file" 2>/dev/null || echo "999")
      if [[ "$exit_code" == "0" ]]; then
        status="pass"
      else
        status="fail"
      fi
    fi
    last_run=$(jq -r '.last_run // ""' "$summary_file" 2>/dev/null || true)
  fi

  # Relative paths for links (relative to batches/ dir)
  log_rel="batch_${num}/batch_${num}.log"
  junit_rel="batch_${num}/junit.xml"

  entry=$(jq -n \
    --argjson num "$num" \
    --arg name "$name" \
    --arg status "$status" \
    --arg last_run "$last_run" \
    --arg log "$log_rel" \
    --arg junit "$junit_rel" \
    --arg deferred_reason "$deferred_reason" \
    '{batch_num: $num, name: $name, status: $status, last_run: $last_run, log: $log, junit: $junit} + (if $deferred_reason != "" then {deferred_reason: $deferred_reason} else {} end)')
  BATCHES_JSON=$(echo "$BATCHES_JSON" | jq --argjson e "$entry" '. + [$e]')
done < "$BATCH_LIST_FILE"

# Build final batch_status.json (preserve order 1..N)
FINAL_JSON=$(jq -n \
  --arg date "$DATE" \
  --arg generated_at "$GENERATED_AT" \
  --argjson batches "$BATCHES_JSON" \
  '{date: $date, generated_at: $generated_at, batches: ($batches | sort_by(.batch_num))}')
echo "$FINAL_JSON" > "${BATCH_REPORT_BASE}/batch_status.json"

# README.md table
README="${BATCH_REPORT_BASE}/README.md"
{
  echo "# Batch execution status — $DATE"
  echo ""
  echo "Generated: $GENERATED_AT"
  echo ""
  echo "| Batch | Name | Status | Last run | Log | JUnit |"
  echo "|-------|------|--------|----------|-----|-------|"
  # Sanitize name for table: newline/cr -> space, pipe and double-quote -> HTML entities
  echo "$FINAL_JSON" | jq -r '.batches[] | "| \(.batch_num) | \(.name | gsub("\\n"; " ") | gsub("\\r"; "") | gsub("\\|"; "&#124;") | gsub("\""; "&#34;")) | \(.status) | \(.last_run // "-") | [log](\(.log)) | [junit](\(.junit)) |"'
  echo ""
  echo "---"
  echo "See [RUNBOOKS.md — Batch execution](../../../docs/RUNBOOKS.md#batch-execution-phase-12a-path-based-batches) for how to run batches and fix failures."
} > "$README"

echo "Wrote ${BATCH_REPORT_BASE}/batch_status.json and ${BATCH_REPORT_BASE}/README.md"
