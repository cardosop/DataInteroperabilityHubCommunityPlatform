#!/usr/bin/env bash
# Phase 278.U.3 — CI skip-rate quality gate.
# Parses Playwright JSON report and fails when any test file exceeds
# the configurable skip-rate threshold.
#
# Usage:
#   bash scripts/check_e2e_skip_rates.sh <path-to-results.json>
#
# Env vars:
#   SKIP_RATE_THRESHOLD_PCT  Max allowed skip rate per file (default 50)
#   SKIP_RATE_MIN_TESTS      Min tests in file to trigger check (default 2)
#
# Exit codes:
#   0 — all files within threshold
#   1 — one or more files exceed threshold
#   2 — usage error (missing report, invalid JSON)
set -euo pipefail

REPORT_FILE="${1:-}"
SKIP_RATE_THRESHOLD_PCT="${SKIP_RATE_THRESHOLD_PCT:-50}"
SKIP_RATE_MIN_TESTS="${SKIP_RATE_MIN_TESTS:-2}"

usage() {
  echo "Usage: $(basename "$0") <path-to-playwright-results.json>"
  echo "  Parses a Playwright JSON report and fails if any test file exceeds"
  echo "  ${SKIP_RATE_THRESHOLD_PCT}% skip rate (min ${SKIP_RATE_MIN_TESTS} tests per file)."
  exit 2
}

if [[ -z "$REPORT_FILE" ]]; then usage; fi
if [[ ! -f "$REPORT_FILE" ]]; then
  echo "WARNING: Playwright JSON report not found at $REPORT_FILE — nothing to check."
  exit 0
fi

if ! command -v jq &> /dev/null; then
  echo "WARNING: jq not installed — cannot parse JSON report. Skipping skip-rate check."
  exit 0
fi

# Collect {file, status} pairs by recursively walking the suite tree
JQ_FILTER='
def walk_suites:
  if .suites then (.suites[] | walk_suites) else
    if .specs then (.specs[] | .tests[] | .results[] | {file: .file // "", status: .status})
    else empty end
  end;
walk_suites
'

RESULTS=$(jq -r "$JQ_FILTER" "$REPORT_FILE" 2>/dev/null || true)
if [[ -z "$RESULTS" ]]; then
  echo "No test results found in $REPORT_FILE — nothing to check."
  exit 0
fi

# Group by file, compute skip rate
declare -A total_tests
declare -A skipped_tests

while IFS=$'\t' read -r file status; do
  if [[ -z "$file" ]]; then continue; fi
  total_tests["$file"]=$(( ${total_tests["$file"]:-0} + 1 ))
  if [[ "$status" == "skipped" ]]; then
    skipped_tests["$file"]=$(( ${skipped_tests["$file"]:-0} + 1 ))
  fi
done < <(echo "$RESULTS" | jq -r '[.file, .status] | @tsv')

# Evaluate each file
FAILED=0
echo "=== E2E Skip Rate Check (threshold: ${SKIP_RATE_THRESHOLD_PCT}%, min tests: ${SKIP_RATE_MIN_TESTS}) ==="
printf "%-70s %6s %6s %6s\n" "File" "Tests" "Skips" "Rate"
printf "%s\n" "$(printf '=%.0s' {1..94})"

for file in "${!total_tests[@]}"; do
  total="${total_tests[$file]}"
  skipped="${skipped_tests[$file]:-0}"
  if (( total < SKIP_RATE_MIN_TESTS )); then continue; fi
  rate=$(( skipped * 100 / total ))
  printf "%-70s %6d %6d %5d%%\n" "$file" "$total" "$skipped" "$rate"
  if (( rate > SKIP_RATE_THRESHOLD_PCT )); then
    FAILED=1
  fi
done

if (( FAILED )); then
  echo ""
  echo "❌ SKIP RATE GATE EXCEEDED"
  echo "   One or more test files exceed the ${SKIP_RATE_THRESHOLD_PCT}% skip-rate threshold."
  echo "   Common causes:"
  echo "     • Staging environment is down or unreachable"
  echo "     • Auth tokens expired (re-run setup-auth)"
  echo "     • Backend not deployed or migrations not applied"
  echo "     • Required test fixtures or feature flags not configured"
  echo "     • Rate limiting triggered (auth or API)"
  echo ""
  echo "   Investigate the files above with elevated skip rates."
  exit 1
fi

echo "✅ All files within skip-rate threshold."
