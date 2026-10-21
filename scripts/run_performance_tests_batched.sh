#!/usr/bin/env bash
# Performance Tests Batched Execution — Run pytest performance tests in batches
# Per TEST_EXECUTION_PLAN.md — Sequential batches (resource intensive)
#
# Prerequisites: Stack up (docker-compose.test.yml). API on 8001 for test stack.
# Usage: ./scripts/run_performance_tests_batched.sh [--batch=N] [--start-from=N]
#
if [ -z "${BASH_VERSION:-}" ]; then
  command -v bash >/dev/null 2>&1 && exec bash "$0" "$@"
  echo "Error: This script requires bash." >&2
  exit 1
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

[[ -f .env.test ]] && set -a && source .env.test && set +a

COMPOSE_FILE=docker-compose.test.yml
API_SVC=api-service-test
COMPOSE_CMD="docker compose -f ${COMPOSE_FILE}"
[[ -f .env.test ]] && COMPOSE_CMD="${COMPOSE_CMD} --env-file .env.test"

# Batches: Name|path1|path2|... (pipe-separated)
BATCHES=(
  # Batch 1: Core & Health
  "Core & Health|tests/performance/test_performance.py|tests/performance/test_health_performance.py|tests/performance/test_performance_django6.py"

  # Batch 2: Datasets, Data Mesh, Versioning
  "Data & Versioning|tests/performance/test_datasets_performance.py|tests/performance/test_data_mesh_performance.py|tests/performance/test_versioning_performance.py"

  # Batch 3: Marketplace & ODPS
  "Marketplace & ODPS|tests/performance/test_marketplace_performance.py|tests/performance/test_odps_export_performance.py|tests/performance/test_concurrent_odps_creation.py|tests/performance/test_odps_version_migration.py"

  # Batch 4: Compliance, DQ, Audit, Governance
  "Compliance & Governance|tests/performance/test_compliance_performance.py|tests/performance/test_dq_performance.py|tests/performance/test_audit_performance.py|tests/performance/test_governance_performance.py"

  # Batch 5: AI, ML, Workflows
  "AI ML Workflows|tests/performance/test_ai_performance.py|tests/performance/test_ml_performance.py|tests/performance/test_workflows_performance.py|tests/performance/test_workflow_execution_minimal.py"

  # Batch 6: Lineage, Virtualization, Integrations
  "Lineage & Integrations|tests/performance/test_lineage_performance.py|tests/performance/test_virtualization_performance.py|tests/performance/test_integrations_performance.py"

  # Batch 7: Webhooks, Social, Export, Metrics
  "Webhooks Social Export|tests/performance/test_webhooks_performance.py|tests/performance/test_social_performance.py|tests/performance/test_scheduled_export_performance.py|tests/performance/test_otel_metrics_performance.py"

  # Batch 8: CLI & SDK
  "CLI & SDK|tests/performance/test_baas_cli_sdk_performance.py|tests/performance/test_odh_cli_sdk_performance.py|tests/performance/test_marketplace_cli_sdk_performance.py|tests/performance/test_model_serving_cli_sdk_performance.py"

  # Batch 9: Baseline & Misc
  "Baseline & Misc|tests/performance/test_performance_baseline.py"
)

DATE="${DATE:-$(date +%Y-%m-%d)}"
[[ "$DATE" == "null" ]] || [[ -z "$DATE" ]] && DATE=$(date +%Y-%m-%d)
REPORT_BASE="test_reports_performance/${DATE}"
BATCH_REPORT_BASE="${REPORT_BASE}/batches"
mkdir -p "${BATCH_REPORT_BASE}"

run_batch() {
  local batch_num=$1
  local batch_def="$2"

  IFS='|' read -ra BATCH_PARTS <<< "$batch_def"
  local batch_name="${BATCH_PARTS[0]}"
  local batch_paths=("${BATCH_PARTS[@]:1}")

  local batch_dir="${BATCH_REPORT_BASE}/batch_${batch_num}"
  mkdir -p "$batch_dir"

  echo ""
  echo "=========================================="
  echo "Performance Batch ${batch_num}: ${batch_name}"
  echo "=========================================="
  echo "Paths: ${batch_paths[*]}"
  echo ""

  local batch_start=$(date +%s)
  local batch_log="${batch_dir}/batch_${batch_num}.log"
  local batch_junit="${batch_dir}/junit.xml"

  local path_args=""
  for p in "${batch_paths[@]}"; do
    path_args="${path_args} ${p}"
  done

  set +e
  $COMPOSE_CMD exec -T "${API_SVC}" bash -c \
    "cd /app && LOG_LEVEL=WARNING PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest \
    ${path_args} \
    -v --reuse-db --timeout=600 --tb=short \
    --junit-xml=/tmp/junit_performance_batch_${batch_num}.xml" 2>&1 | tee "$batch_log"
  local batch_exit=${PIPESTATUS[0]}
  set -e

  $COMPOSE_CMD cp "${API_SVC}:/tmp/junit_performance_batch_${batch_num}.xml" "$batch_junit" 2>/dev/null || true

  local batch_end=$(date +%s)
  local batch_duration=$((batch_end - batch_start))

  local total=0 failed=0 errors=0 skipped=0
  local summary_lines
  summary_lines=$(grep -E ' in [0-9]+\.?[0-9]*s [\(=]' "$batch_log" 2>/dev/null || true)
  if [[ -n "$summary_lines" ]]; then
    while IFS= read -r summary_line; do
      [[ -z "$summary_line" ]] && continue
      total=$((total + $(echo "$summary_line" | grep -oP "\d+(?= passed)" | head -1 || echo "0")))
      failed=$((failed + $(echo "$summary_line" | grep -oP "\d+(?= failed)" | head -1 || echo "0")))
      errors=$((errors + $(echo "$summary_line" | grep -oP "\d+(?= error)" | head -1 || echo "0")))
      skipped=$((skipped + $(echo "$summary_line" | grep -oP "\d+(?= skipped)" | head -1 || echo "0")))
    done <<< "$summary_lines"
  fi

  _to_int() { printf '%s' "$1" | head -1 | tr -d '\n\r\t ' | grep -oE '[0-9]+' | head -1 || echo "0"; }
  total=$(( $( _to_int "$total" ) + 0 ))
  failed=$(( $( _to_int "$failed" ) + 0 ))
  errors=$(( $( _to_int "$errors" ) + 0 ))
  skipped=$(( $( _to_int "$skipped" ) + 0 ))

  echo ""
  echo "Batch ${batch_num} Summary:"
  echo "  Exit code: ${batch_exit}"
  echo "  Duration: ${batch_duration}s"
  echo "  Passed: ${total}"
  echo "  Failed: ${failed}"
  echo "  Errors: ${errors}"
  echo "  Skipped: ${skipped}"
  echo "  Log: ${batch_log}"
  echo ""

  if [[ "$failed" -eq 0 ]] && [[ "$errors" -eq 0 ]]; then
    return 0
  fi
  return "$batch_exit"
}

# Parse args
START_FROM=1
RUN_ONLY=""
NEXT_IS_START_FROM=false
NEXT_IS_BATCH=false
for arg in "$@"; do
  if [[ "$NEXT_IS_START_FROM" == true ]]; then
    START_FROM="$arg"
    NEXT_IS_START_FROM=false
    continue
  fi
  if [[ "$NEXT_IS_BATCH" == true ]]; then
    RUN_ONLY="$arg"
    NEXT_IS_BATCH=false
    continue
  fi
  case $arg in
    --list-batches)
      for i in "${!BATCHES[@]}"; do
        num=$((i + 1))
        def="${BATCHES[$i]}"
        echo -e "${num}\t${def//|/$'\t'}"
      done
      exit 0
      ;;
    --start-from)
      NEXT_IS_START_FROM=true
      ;;
    --start-from=*)
      START_FROM="${arg#*=}"
      ;;
    --batch)
      NEXT_IS_BATCH=true
      ;;
    --batch=*)
      RUN_ONLY="${arg#*=}"
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --start-from=N    Start from batch N (default: 1)"
      echo "  --batch=N         Run only batch N"
      echo "  --list-batches    Print batch definitions and exit"
      echo ""
      echo "Examples:"
      echo "  $0                          # Run all batches"
      echo "  $0 --start-from=5            # Run batches 5 to end"
      echo "  $0 --batch=3                 # Run only batch 3"
      exit 0
      ;;
  esac
done

if [[ "$NEXT_IS_START_FROM" == true ]] || [[ "$NEXT_IS_BATCH" == true ]]; then
  echo "Error: --start-from and --batch require a value (e.g. --start-from 2 or --start-from=2)" >&2
  exit 1
fi

echo "=========================================="
echo "Performance Tests Batched Execution"
echo "=========================================="
echo "Date: ${DATE}"
echo "Report base: ${REPORT_BASE}"
echo "Batches: ${#BATCHES[@]}"
[[ "$START_FROM" -gt 1 ]] && echo "Starting from batch: ${START_FROM}"
echo ""

echo "Ensuring test stack is up..."
if ! $COMPOSE_CMD ps -q "${API_SVC}" 2>/dev/null | grep -q .; then
  echo "Bringing up test stack..."
  $COMPOSE_CMD up -d --wait 2>&1 || true
fi

# Wait for PostgreSQL to be ready (handles recovery mode, init, restarts)
wait_for_postgres_ready() {
  local max_attempts=300
  local attempt=1
  local pg_user="${POSTGRES_TEST_USER:-hub_test}"
  local pg_db="${POSTGRES_TEST_DB:-hub_test}"
  if ! $COMPOSE_CMD ps -q postgres-test 2>/dev/null | grep -q .; then
    echo "Error: postgres-test container is not running. Start the stack first." >&2
    return 1
  fi
  echo "Waiting for PostgreSQL (postgres-test) to accept connections..."
  while [ $attempt -le $max_attempts ]; do
    if $COMPOSE_CMD exec -T postgres-test pg_isready -U "$pg_user" -d "$pg_db" -t 2 2>/dev/null; then
      echo "PostgreSQL is ready."
      return 0
    fi
    if [ $attempt -eq $max_attempts ]; then
      echo "Error: PostgreSQL did not become ready within $((max_attempts * 2))s (database may be in recovery)." >&2
      echo "Try: docker compose -f $COMPOSE_FILE --env-file .env.test restart postgres-test" >&2
      echo "Or: docker compose -f $COMPOSE_FILE --env-file .env.test down -v && ./scripts/run_performance_tests_batched.sh" >&2
      return 1
    fi
    sleep 2
    attempt=$((attempt + 1))
  done
  return 1
}
wait_for_postgres_ready || exit 1

TOTAL_BATCHES=${#BATCHES[@]}
FAILED_BATCHES=()

if [[ -n "$RUN_ONLY" ]]; then
  if [[ ! "$RUN_ONLY" =~ ^[0-9]+$ ]] || [[ "$RUN_ONLY" -lt 1 ]] || [[ "$RUN_ONLY" -gt "$TOTAL_BATCHES" ]]; then
    echo "Error: --batch must be 1-${TOTAL_BATCHES}"
    exit 1
  fi
  START_FROM="$RUN_ONLY"
fi

for i in "${!BATCHES[@]}"; do
  CURRENT_BATCH=$((i + 1))
  [[ $CURRENT_BATCH -lt $START_FROM ]] && continue
  [[ -n "$RUN_ONLY" ]] && [[ $CURRENT_BATCH -ne $RUN_ONLY ]] && continue

  run_batch "$CURRENT_BATCH" "${BATCHES[$i]}"
  batch_ret=$?
  if [[ $batch_ret -eq 0 ]]; then
    echo "[PASS] Batch ${CURRENT_BATCH}"
  else
    echo "[FAIL] Batch ${CURRENT_BATCH}"
    FAILED_BATCHES+=("$CURRENT_BATCH")
    echo ""
    echo "Fix failures, then re-run:"
    echo "  ./scripts/run_performance_tests_batched.sh --start-from ${CURRENT_BATCH}"
    echo ""
    exit 1
  fi

  [[ -n "$RUN_ONLY" ]] && [[ $CURRENT_BATCH -eq $RUN_ONLY ]] && break
done

echo "=========================================="
echo "All Performance Batches Complete"
echo "=========================================="
echo "Total batches: ${TOTAL_BATCHES}"
echo "Failed: ${#FAILED_BATCHES[@]}"
if [[ ${#FAILED_BATCHES[@]} -gt 0 ]]; then
  exit 1
fi
exit 0
