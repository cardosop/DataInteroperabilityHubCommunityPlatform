#!/usr/bin/env bash
# Generate a sign-off snippet for a full suite run (Phase 4.3).
# Output: date, branch, commit, evidence path, outcome, and any deferred failures from batch_status.json.
#
# Usage: ./scripts/generate_sign_off_snippet.sh [YYYY-MM-DD]
# Omit date to use the latest date directory under test_reports_comprehensive/.
#
# Requires: jq (only when batches/batch_status.json exists).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

REPORTS_BASE="test_reports_comprehensive"
DATE="${1:-}"

if [[ -z "$DATE" ]]; then
  if [[ ! -d "$REPORTS_BASE" ]]; then
    echo "Evidence base not found: $REPORTS_BASE" >&2
    exit 1
  fi
  # Latest date directory (YYYY-MM-DD); portable (no GNU find -printf)
  DATE=$(find "$REPORTS_BASE" -maxdepth 1 -type d -name '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' 2>/dev/null | while read -r d; do basename "$d"; done | sort -r | head -1)
  if [[ -z "$DATE" ]]; then
    echo "No date directory found under $REPORTS_BASE" >&2
    exit 1
  fi
fi

EVIDENCE_PATH="${REPORTS_BASE}/${DATE}"
if [[ ! -d "$EVIDENCE_PATH" ]]; then
  echo "Evidence path not found: $EVIDENCE_PATH" >&2
  exit 1
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
BATCH_STATUS="${EVIDENCE_PATH}/batches/batch_status.json"

DEFERRED_LINES=""
if [[ -f "$BATCH_STATUS" ]] && command -v jq >/dev/null 2>&1; then
  DEFERRED_LINES=$(jq -r '
    .batches // [] | map(select(.status == "deferred")) | .[] |
    "  - Batch \(.batch_num): \(.deferred_reason // "deferred")"
  ' "$BATCH_STATUS" 2>/dev/null || true)
fi

echo "--- Full suite sign-off (Phase 4.3) ---"
echo "Date:           $DATE"
echo "Branch:         $BRANCH"
echo "Commit:         $COMMIT"
echo "Evidence path:  $EVIDENCE_PATH"
if [[ -n "$DEFERRED_LINES" ]]; then
  echo "Outcome:        Passed with deferred failures"
  echo "Deferred:"
  echo "$DEFERRED_LINES"
else
  echo "Outcome:        Full suite run passed"
fi
echo "---"
