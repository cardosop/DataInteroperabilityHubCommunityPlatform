#!/usr/bin/env bash
# check_e2e_skip_rates.sh — CI quality gate for E2E test skip rates.
#
# Phase 278.U.3 — detects silent environment failures masked by skip storms.
# When staging is broken, tests skip instead of failing — green CI hides
# the problem. This gate fails the job when any single spec file exceeds
# a configurable skip-rate threshold, indicating a systematic environment
# issue rather than isolated conditional skips.
#
# Usage:
#   bash scripts/check_e2e_skip_rates.sh <playwright-json-report>
#   bash scripts/check_e2e_skip_rates.sh frontend/test-results/results.json
#
# Options (env vars):
#   SKIP_RATE_THRESHOLD_PCT — max allowed skip % per file (default: 50)
#   SKIP_RATE_MIN_TESTS     — min test count per file to flag (default: 2)
#                              files with fewer tests are exempt (a single
#                              test.skip() in a 1-test file is 100% but
#                              may be legitimate if the feature is gated).
#
# Exit codes:
#   0 — all files below threshold
#   1 — one or more files exceed threshold (CI gate failure)
#   2 — usage / argument error

set -euo pipefail

# ── Defaults ────────────────────────────────────────────────────────────────

THRESHOLD="${SKIP_RATE_THRESHOLD_PCT:-50}"
MIN_TESTS="${SKIP_RATE_MIN_TESTS:-2}"

# ── Arg parsing ─────────────────────────────────────────────────────────────

if [ $# -lt 1 ]; then
  echo "usage: $(basename "$0") <playwright-json-report>"
  exit 2
fi

REPORT_FILE="$1"

if [ ! -f "$REPORT_FILE" ]; then
  echo "::error::Playwright JSON report not found at: $REPORT_FILE"
  echo "If no tests ran, the report won't exist. Ensure tests ran before this step."
  exit 2
fi

if ! command -v jq &> /dev/null; then
  echo "::error::jq is required but not installed."
  exit 2
fi

# ── Parse per-file skip rates ───────────────────────────────────────────────
#
# Playwright JSON reporter structure (simplified):
# {
#   "suites": [
#     {
#       "file": "path/to/file.spec.ts",    // present on file-level suites
#       "suites": [...],                    // nested describe blocks
#       "specs": [
#         {
#           "title": "test name",
#           "ok": true,
#           "tests": [
#             {
#               "status": "expected" | "unexpected" | "flaky" | "skipped",
#               "results": [
#                 { "status": "passed" | "failed" | "skipped" | ... }
#               ]
#             }
#           ]
#         }
#       ]
#     }
#   ]
# }
#
# We extract (file, total_tests, skipped_tests) from each spec by walking
# the suite tree and aggregating to the nearest file-bearing ancestor.

echo "=== E2E Skip-Rate Gate (Phase 278.U.3) ==="
echo "Threshold: ${THRESHOLD}% max skip rate per file"
echo "Min tests:  ${MIN_TESTS} (files with fewer tests are exempt)"
echo "Report:     ${REPORT_FILE}"
echo ""

# Build a flat list of {file, status} for every test result.
# We walk each suite tree and collect file + status pairs.
# For suites without a `file` field (describe blocks), we carry forward
# the parent's file.

JQ_SCRIPT='
# Recursively collect file→status pairs from the suite tree.
def walk_suites($file):
  (if .file then .file else $file end) as $f
  | (if .specs then .specs[] | { file: $f, tests: .tests } else empty end),
    (if .suites then .suites[] | walk_suites($f) else empty end);

[ walk_suites(null) ]
| group_by(.file)
| map({
    file: .[0].file,
    total: length,
    skipped: (map(select(.tests | any(.status == "skipped" or (.results // [])[0].status == "skipped"))) | length)
  })
| map(select(.total >= ($min_tests | tonumber)))
| map(. + { pct: ((.skipped / .total * 100 * 10 | floor) / 10) })
| sort_by(-.pct)
'

# We inject $min_tests from the shell
RESULTS=$(jq --arg min_tests "$MIN_TESTS" "$JQ_SCRIPT" "$REPORT_FILE")

if [ -z "$RESULTS" ] || [ "$RESULTS" = "[]" ]; then
  echo "No files with sufficient test count to evaluate. Gate passes."
  exit 0
fi

# ── Display table ───────────────────────────────────────────────────────────

printf "%-70s %6s %8s %8s %s\n" "File" "Tests" "Skipped" "Skip %" "Status"
printf '%*s\n' 110 '' | tr ' ' '-'

FAILURES=0

echo "$RESULTS" | jq -c '.[]' | while IFS= read -r row; do
  FILE=$(  echo "$row" | jq -r '.file   // "unknown"')
  TOTAL=$( echo "$row" | jq -r '.total   // 0')
  SKIP=$(  echo "$row" | jq -r '.skipped // 0')
  PCT=$(   echo "$row" | jq -r '.pct     // 0')

  # Truncate file path for display (keep last 65 chars)
  DISPLAY_FILE="$FILE"
  if [ ${#DISPLAY_FILE} -gt 65 ]; then
    DISPLAY_FILE="…${DISPLAY_FILE: -64}"
  fi

  if (( $(echo "$PCT > $THRESHOLD" | bc -l 2>/dev/null || echo 0) )); then
    STATUS="❌ EXCEEDS"
    FAILURES=$((FAILURES + 1))
  else
    STATUS="✅ ok"
  fi

  printf "%-70s %6s %8s %7s%% %s\n" "$DISPLAY_FILE" "$TOTAL" "$SKIP" "$PCT" "$STATUS"
done

WAIT_STATUS="${PIPESTATUS[0]}"

# ── Results ─────────────────────────────────────────────────────────────────

echo ""

EXCEEDING=$(echo "$RESULTS" | jq --argjson threshold "$THRESHOLD" \
  '[.[] | select(.pct > ($threshold | tonumber))] | length')

if [ "$EXCEEDING" -gt 0 ]; then
  echo "❌ SKIP-RATE GATE FAILED: ${EXCEEDING} file(s) exceed ${THRESHOLD}% skip rate."
  echo ""
  echo "Exceeding files:"
  echo "$RESULTS" | jq -r --argjson threshold "$THRESHOLD" \
    '.[] | select(.pct > ($threshold | tonumber)) | "  • \(.file) — \(.pct)% skip (\(.skipped)/\(.total))"'
  echo ""
  echo "Possible causes:"
  echo "  - Staging environment is down or degraded"
  echo "  - Auth session expiry (test users cannot log in → skips cascade)"
  echo "  - Backend service not deployed (feature gated but gate logic broken)"
  echo "  - Required test data fixtures missing"
  echo "  - Rate limiting impacting test execution"
  echo ""
  echo "Action: investigate the root cause before re-running. Skipped tests"
  echo "mask real failures — a green CI with 80% skip rate is a false signal."
  exit 1
else
  echo "✅ SKIP-RATE GATE PASSED: No files exceed ${THRESHOLD}% skip rate."
  exit 0
fi
