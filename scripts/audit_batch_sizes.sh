#!/usr/bin/env bash
# Audit path-based batch sizes for run_phase_12a_batched.sh.
# Runs pytest --collect-only -q per batch (inside api-service-test) and reports counts.
# Any batch with >200 tests should be split (by file or subdir) per GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN §11.
#
# Usage:
#   ./scripts/audit_batch_sizes.sh           # Require stack up; audit all batches
#   ./scripts/audit_batch_sizes.sh --no-up   # Skip bringing up stack (stack must already be up)
#
# Output: Markdown table to stdout; batches with >200 tests get a "SPLIT" recommendation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
export COMPOSE_FILE
COMPOSE_CMD="docker compose -f ${COMPOSE_FILE}"
API_SVC="api-service-test"

NO_UP=""
for a in "$@"; do
  if [[ "$a" == "--no-up" ]]; then
    NO_UP=1
    break
  fi
done

if [[ -z "$NO_UP" ]]; then
  echo "Bringing up test stack (COMPOSE_FILE=${COMPOSE_FILE})..."
  $COMPOSE_CMD up -d --wait 2>/dev/null || true
  echo "Waiting for ${API_SVC}..."
  for i in {1..18}; do
    if $COMPOSE_CMD ps -q "$API_SVC" 2>/dev/null | grep -q .; then
      state=$($COMPOSE_CMD ps -q "$API_SVC" 2>/dev/null | xargs -r docker inspect -f '{{.State.Status}}' 2>/dev/null | head -1)
      if [[ "$state" == "running" ]]; then
        echo "  ${API_SVC} is running."
        break
      fi
    fi
    if [[ $i -eq 18 ]]; then
      echo "Error: ${API_SVC} not running. Start stack with: $COMPOSE_CMD up -d"
      exit 1
    fi
    sleep 5
  done
else
  if ! $COMPOSE_CMD ps -q "$API_SVC" 2>/dev/null | grep -q .; then
    echo "Error: ${API_SVC} not running. Start stack with: $COMPOSE_CMD up -d"
    exit 1
  fi
fi

echo ""
echo "Collecting test counts per batch (pytest --collect-only -q inside container)..."
echo ""

MAX_TESTS=200
RESULTS=()
TOTAL_COUNT=0

# Get batch definitions to a temp file so we can iterate reliably (avoid pipe/process-substitution issues)
BATCH_LIST_FILE=$(mktemp)
trap 'rm -f "$BATCH_LIST_FILE"' EXIT
"$SCRIPT_DIR/run_phase_12a_batched.sh" --list-batches > "$BATCH_LIST_FILE" 2>/dev/null
n_batch_lines=$(wc -l < "$BATCH_LIST_FILE" || true)
n_batch_lines=$((n_batch_lines + 0))
if [[ $n_batch_lines -eq 0 ]]; then
  echo "Error: No batch definitions from run_phase_12a_batched.sh --list-batches."
  exit 1
fi

# Run pytest --collect-only for each batch
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  num=$(echo "$line" | cut -f1)
  name=$(echo "$line" | cut -f2)
  paths=$(echo "$line" | cut -f3- | tr '\t' ' ')
  if [[ -z "$paths" ]]; then
    RESULTS+=("$num|$name|0|ERROR")
    continue
  fi
  # Redirect stdin to /dev/null so docker exec does not consume the batch list file
  out=$( ($COMPOSE_CMD exec -T "$API_SVC" bash -c \
    "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest $paths --collect-only -q 2>&1") < /dev/null || true)
  count=0
  if echo "$out" | grep -qE "[0-9]+ (tests|items) collected"; then
    count=$(echo "$out" | grep -oE "[0-9]+ (tests|items) collected" | head -1 | grep -oE "^[0-9]+")
  fi
  count=$((count + 0))
  TOTAL_COUNT=$((TOTAL_COUNT + count))
  if [[ $count -gt $MAX_TESTS ]]; then
    status="SPLIT (${count}>${MAX_TESTS})"
  else
    status="OK"
  fi
  RESULTS+=("$num|$name|$count|$status")
done < "$BATCH_LIST_FILE"

# Print Markdown table
echo "## Batch size audit ($(date +%Y-%m-%d))"
echo ""
echo "| Batch | Name | Tests | Status |"
echo "|-------|------|-------|--------|"
for r in "${RESULTS[@]}"; do
  IFS='|' read -r n name cnt status <<< "$r"
  echo "| $n | $name | $cnt | $status |"
done
echo ""
echo "**Total tests (path-based batches):** $TOTAL_COUNT"
echo ""

# Recommendations
OVER=()
for r in "${RESULTS[@]}"; do
  IFS='|' read -r n name cnt status <<< "$r"
  if [[ "$status" == SPLIT* ]]; then
    OVER+=("Batch $n ($name): $cnt tests")
  fi
done
if [[ ${#OVER[@]} -gt 0 ]]; then
  echo "### Batches exceeding ${MAX_TESTS} tests (split by file or subdir)"
  for o in "${OVER[@]}"; do
    echo "- $o"
  done
  echo ""
  echo "See GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md §11 (Splitting Large Path-Based Batches)."
fi
