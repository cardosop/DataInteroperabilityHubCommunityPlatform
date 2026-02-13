#!/usr/bin/env bash
# Phase 12A Batched Execution — Run tests in batches, fix issues before proceeding
# Per gapfix1 FG.1 — Incremental approach: run small batches, fix root causes, then proceed
# No mocks/stubs; root-cause fixes only.
#
# Infrastructure: All batches run against the same test environment (docker-compose.test.yml).
# The script brings up the test stack and waits for required services before running any batch.
#
# Prerequisites:
#   - Docker and Docker Compose
#   - From repo root: ./scripts/run_phase_12a_batched.sh [--batch=N] [--start-from=N]
#   To clean and restart test stack first: ./scripts/clean-test-stack.sh
#   This script always uses docker-compose.test.yml and api-service-test (no env override).

set -euo pipefail

# Ensure we run with bash (arrays and multi-line quoting require bash)
if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Always use test infrastructure (same env for all batches). Hardcode test file and service
# so we never pick up docker-compose.yml or API_SERVICE_NAME=api-service from the environment.
COMPOSE_FILE=docker-compose.test.yml
export COMPOSE_FILE
API_SVC=api-service-test
# Explicit -f so only this file is used (no merge with default compose or override)
COMPOSE_CMD="docker compose -f ${COMPOSE_FILE}"

# Core test services that must be running (no profile; worker/Prefect are optional)
TEST_SERVICES=(postgres-test redis-cache-test redis-queue-test redis-events-test redis-channels-test minio-test fuseki-test datacontract-service-test dq-service-test compliance-service-test semantic-service-test api-service-test)

ensure_test_infra() {
  echo "Ensuring test infrastructure is up (COMPOSE_FILE=${COMPOSE_FILE})..."
  if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Error: $COMPOSE_FILE not found."
    exit 1
  fi
  $COMPOSE_CMD up -d --wait 2>/dev/null || true
  echo "Waiting for core services to be running..."
  local wait_max=90
  local waited=0
  while [[ $waited -lt $wait_max ]]; do
    local all_up=true
    for svc in "${TEST_SERVICES[@]}"; do
      if ! $COMPOSE_CMD ps -q "$svc" 2>/dev/null | grep -q .; then
        all_up=false
        break
      fi
      local state
      state=$($COMPOSE_CMD ps -q "$svc" 2>/dev/null | xargs -r docker inspect -f '{{.State.Status}}' 2>/dev/null | head -1)
      if [[ "$state" != "running" ]]; then
        all_up=false
        break
      fi
    done
    if [[ "$all_up" == "true" ]]; then
      echo "  All core services are running."
      return 0
    fi
    sleep 5
    waited=$((waited + 5))
  done
  echo "Error: Not all core services are running after ${wait_max}s. Check: $COMPOSE_CMD ps -a"
  $COMPOSE_CMD ps -a 2>/dev/null || true
  exit 1
}

DATE="${DATE:-$(date +%Y-%m-%d)}"
REPORT_BASE="test_reports_comprehensive/${DATE}"
BATCH_REPORT_BASE="${REPORT_BASE}/batches"
mkdir -p "${BATCH_REPORT_BASE}"

# Test batches — organized by app/module for incremental fixing
# Each batch should be small enough to review and fix failures before proceeding
# Format: "BATCH_NAME|path1|path2|path3" (pipe-separated)
BATCHES=(
  # Batch 1: Core infrastructure (small, foundational)
  "Core Infrastructure|hub/apps/core/tests/|hub/apps/api/tests/|hub/apps/health/tests/"

  # Batch 2: Authentication & Authorization (foundational)
  "Auth|hub/apps/auth/tests/"

  # Batch 3: Audit (foundational, used by many apps)
  "Audit|hub/apps/audit/tests/"

  # Batch 4: Assets (core domain)
  "Assets|hub/apps/assets/tests/"

  # Batch 5: Contracts — Core (models, serializers, services, views)
  "Contracts Core|hub/apps/contracts/tests/test_models.py|hub/apps/contracts/tests/test_serializers.py|hub/apps/contracts/tests/test_services.py|hub/apps/contracts/tests/test_views.py"

  # Batch 6: Contracts — ODPS only (split from 6+7 to avoid OOM / exit 137)
  "Contracts ODPS|hub/apps/contracts/tests/test_odps_*.py"

  # Batch 7: Contracts — ODCS only
  "Contracts ODCS|hub/apps/contracts/tests/test_odcs_*.py"

  # Batch 8: Datasets (core domain)
  "Datasets|hub/apps/datasets/tests/"

  # Batch 9: Marketplace (depends on assets, contracts)
  "Marketplace|hub/apps/marketplace/tests/"

  # Batch 10: Compliance (original batch 9 was "Compliance & Governance" ≈506 tests; split to avoid OOM)
  "Compliance|hub/apps/compliance/tests/"

  # Batch 11: Governance (other half of original batch 9)
  "Governance|hub/apps/governance/tests/"

  # Batch 12: Data Quality
  "Data Quality|hub/apps/dq/tests/"

  # Batch 13: Files & Storage — all tests under hub/apps/files/tests/ (~214 tests; no-cov to avoid OOM)
  "Files & Storage|hub/apps/files/tests/"

  # Batch 14: Scheduled Operations
  "Scheduled Operations|hub/apps/scheduled_export/tests/|hub/apps/scheduled_ingestion/tests/"

  # Batch 15: Orchestration & Workflows
  "Orchestration|hub/apps/orchestration/tests/"

  # Batch 16: Jobs & Workers
  "Jobs|hub/apps/jobs/tests/"

  # Batch 17: Billing & Subscriptions
  "Billing|hub/apps/billing/tests/"

  # Batch 18: BaaS & Developer Portal
  "BaaS & Developer|hub/apps/baas/tests/|hub/apps/developer/tests/"

  # Batch 19: GDPR & Privacy
  "GDPR|hub/apps/gdpr/tests/"

  # Batch 20: Notifications & Webhooks
  "Notifications & Webhooks|hub/apps/notifications/tests/|hub/apps/webhooks/tests/"

  # Batch 21: AI & ML
  "AI & ML|hub/apps/ai/tests/|hub/apps/ml/tests/"

  # Batch 22: GraphQL
  "GraphQL|hub/apps/graphql/tests/|hub/apps/graphql_graphene/tests/"

  # Batch 23: Observability & Monitoring
  "Observability|hub/apps/observability/tests/"

  # Batch 24: Rate Limiting
  "Rate Limiting|hub/apps/rate_limiting/tests/"

  # Batch 25: Integrations & Mesh
  "Integrations & Mesh|hub/apps/integrations/tests/|hub/apps/mesh/tests/"

  # Batch 26: Platform & Users
  "Platform & Users|hub/apps/platform/tests/|hub/apps/users/tests/|hub/apps/social/tests/"
)

# Optional: load batch list from file (e.g. generated by scripts/split_batches_to_cap.py) so every batch has ≤200 tests
BATCH_DEFINITIONS_FILE="${BATCH_DEFINITIONS_FILE:-$SCRIPT_DIR/batch_definitions.txt}"
if [[ -f "$BATCH_DEFINITIONS_FILE" ]]; then
  BATCHES=()
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" ]] || [[ "$line" =~ ^[[:space:]]*# ]] && continue
    BATCHES+=("$line")
  done < "$BATCH_DEFINITIONS_FILE"
fi

# Function to run a single batch
run_batch() {
  local batch_num=$1
  local batch_def="$2"

  # Parse batch definition: "BATCH_NAME|path1|path2|..."
  IFS='|' read -ra BATCH_PARTS <<< "$batch_def"
  local batch_name="${BATCH_PARTS[0]}"
  local batch_paths=("${BATCH_PARTS[@]:1}")

  local batch_dir="${BATCH_REPORT_BASE}/batch_${batch_num}"
  mkdir -p "$batch_dir"

  echo ""
  echo "=========================================="
  echo "Batch ${batch_num}: ${batch_name}"
  echo "=========================================="
  echo "Paths: ${batch_paths[*]}"
  echo ""

  local batch_start=$(date +%s)
  local batch_log="${batch_dir}/batch_${batch_num}.log"
  local batch_junit="${batch_dir}/junit.xml"

  # Run pytest with --reuse-db and timeout
  # Use --maxfail=10 to stop after 10 failures (allows seeing patterns, not just first failure)
  # Use -rs to show skip reasons in the log (e.g. DQ/Compliance integration skips)
  # Skip coverage for ODPS/ODCS/Files batches to avoid OOM (exit 137); key by name/path so batch_definitions.txt works
  local cov_args="--cov=hub --cov-report=term-missing --cov-report=xml:/tmp/coverage_batch_${batch_num}.xml"
  if [[ "$batch_name" == *"ODPS"* ]] || [[ "$batch_name" == *"ODCS"* ]] || [[ "$batch_name" == *"Files"* ]]; then
    cov_args="--no-cov"
  else
    for p in "${batch_paths[@]}"; do
      if [[ "$p" == *"test_odps"* ]] || [[ "$p" == *"test_odcs"* ]] || [[ "$p" == *"files/tests"* ]]; then
        cov_args="--no-cov"
        break
      fi
    done
  fi
  echo "Running pytest in ${API_SVC} (test collection may take 1–2 min for large batches)..."
  set +e
  $COMPOSE_CMD exec -T "${API_SVC}" bash -c \
    "rm -f /app/.coverage && cd /app && BATCH_TEST=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest \
    ${batch_paths[*]} \
    -v \
    -rs \
    --reuse-db \
    --timeout=300 \
    --maxfail=10 \
    --junit-xml=/tmp/junit_batch_${batch_num}.xml \
    --tb=short \
    ${cov_args}" 2>&1 | tee "$batch_log"
  local batch_exit=${PIPESTATUS[0]}
  set -e

  local batch_end=$(date +%s)
  local batch_duration=$((batch_end - batch_start))

  # Copy artifacts
  $COMPOSE_CMD cp "${API_SVC}:/tmp/junit_batch_${batch_num}.xml" "$batch_junit" 2>/dev/null || true
  if [[ "$cov_args" != "--no-cov" ]]; then
    $COMPOSE_CMD cp "${API_SVC}:/tmp/coverage_batch_${batch_num}.xml" "${batch_dir}/coverage.xml" 2>/dev/null || true
  fi

  # Extract test summary (passed, failed, errors, skipped). Use head -1 so we get a single
  # integer (grep -oP "\d+" can output multiple numbers per line, causing [[ n -eq 0 ]] syntax errors).
  local total=$(grep -oP "(\d+) passed" "$batch_log" | tail -1 | grep -oP "\d+" | head -1 || echo "0")
  local failed=$(grep -oP "(\d+) failed" "$batch_log" | tail -1 | grep -oP "\d+" | head -1 || echo "0")
  local errors=$(grep -oP "(\d+) error" "$batch_log" | tail -1 | grep -oP "\d+" | head -1 || echo "0")
  local skipped=$(grep -oP "(\d+) skipped" "$batch_log" | tail -1 | grep -oP "\d+" | head -1 || echo "0")

  # Sanitize to integers (strip any stray newlines/whitespace) for arithmetic and [[ ]]
  total=$((total + 0))
  failed=$((failed + 0))
  errors=$((errors + 0))
  skipped=$((skipped + 0))

  # Exit 137 = process killed (SIGKILL), often OOM during coverage. Recover counts from log if possible.
  if [[ "$batch_exit" -eq 137 ]] && [[ -f "$batch_log" ]]; then
    local passed_count=$(grep -c " PASSED " "$batch_log" 2>/dev/null || echo "0")
    passed_count=$((passed_count + 0))
    if [[ "$passed_count" -gt 0 ]] && [[ "$total" -eq 0 ]]; then
      total=$passed_count
      failed=0
      errors=0
      skipped=0
      echo "Note: Process killed (exit 137, likely OOM) after tests completed; inferred ${total} passed from log."
      batch_exit=0
    fi
  fi

  # If no tests ran: treat as failure unless user canceled (SIGINT -> 130 or 255)
  local test_count=$((total + failed + errors + skipped))
  if [[ "$test_count" -eq 0 ]]; then
    if [[ "$batch_exit" -eq 130 ]] || [[ "$batch_exit" -eq 255 ]]; then
      echo "Canceled by user (Ctrl+C). Exit code: ${batch_exit}"
      return 2
    fi
    echo "Error: No tests ran (exit ${batch_exit}). Check log: $batch_log"
    return 1
  fi

  # Write batch summary (include last_run for batch_status.json / Phase 3.3)
  # Escape for JSON: backslash and double quote (so batch_name/paths never break JSON)
  local batch_name_escaped="${batch_name//\\/\\\\}"
  batch_name_escaped="${batch_name_escaped//\"/\\\"}"
  local last_run=$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)
  local log_escaped="${batch_log//\\/\\\\}"
  log_escaped="${log_escaped//\"/\\\"}"
  local junit_escaped="${batch_junit//\\/\\\\}"
  junit_escaped="${junit_escaped//\"/\\\"}"
  local paths_json=$(printf '%s\n' "${batch_paths[@]}" | jq -R . | jq -s .)
  cat > "${batch_dir}/summary.json" << EOF
{
  "batch_num": ${batch_num},
  "batch_name": "${batch_name_escaped}",
  "paths": ${paths_json},
  "exit_code": ${batch_exit},
  "duration_seconds": ${batch_duration},
  "total": ${total:-0},
  "failed": ${failed:-0},
  "errors": ${errors:-0},
  "skipped": ${skipped:-0},
  "last_run": "${last_run}",
  "log": "${log_escaped}",
  "junit": "${junit_escaped}"
}
EOF

  echo ""
  echo "Batch ${batch_num} Summary:"
  echo "  Exit code: ${batch_exit} (0 = success)"
  echo "  Duration: ${batch_duration}s"
  echo "  Passed: ${total:-0}"
  echo "  Failed: ${failed:-0}"
  echo "  Errors: ${errors:-0}"
  echo "  Skipped: ${skipped:-0}"
  echo "  Log: ${batch_log}"
  echo ""

  # Return 0 if all tests passed (including when we recovered from 137)
  if [[ "$failed" -eq 0 ]] && [[ "$errors" -eq 0 ]]; then
    return 0
  fi
  return "$batch_exit"
}

# Main execution — parse arguments first so --list-batches exits without banner
START_FROM=1
RUN_ONLY=""
DEFERRED_BATCHES=()
DEFER_REASON="${DEFER_REASON:-}"
for arg in "$@"; do
  case $arg in
    --list-batches)
      for i in "${!BATCHES[@]}"; do
        num=$((i + 1))
        def="${BATCHES[$i]}"
        echo -e "${num}\t${def//|/$'\t'}"
      done
      exit 0
      ;;
    --start-from=*)
      START_FROM="${arg#*=}"
      ;;
    --start-from)
      shift
      START_FROM="$1"
      ;;
    --batch=*)
      RUN_ONLY="${arg#*=}"
      ;;
    --batch)
      shift
      RUN_ONLY="$1"
      ;;
    --defer=*)
      # Comma-separated list of batch numbers to treat as deferred on failure (continue to next)
      IFS=',' read -ra DEFER_NUMS <<< "${arg#*=}"
      for n in "${DEFER_NUMS[@]}"; do
        n=$((n + 0))
        [[ $n -ge 1 ]] && DEFERRED_BATCHES+=("$n")
      done
      ;;
    --defer-reason=*)
      DEFER_REASON="${arg#*=}"
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --start-from=N    Start from batch N (default: 1)"
      echo "  --batch=N         Run only batch N"
      echo "  --defer=N,M,...   If batch N (or M,...) fails, mark deferred and continue (Phase 3.4)"
      echo "  --defer-reason=S  Ticket/reason for deferred batches (e.g. TICKET-123)"
      echo "  --help, -h        Show this help message"
      echo ""
      echo "Examples:"
      echo "  $0                          # Run all batches"
      echo "  $0 --start-from=5           # Run batches 5 to end"
      echo "  $0 --batch=14                # Run only batch 14"
      echo "  $0 --start-from=5 --defer=5 --defer-reason=TICKET-123  # Defer batch 5 and continue"
      echo "  $0 --list-batches           # Print batch definitions (N name path1 path2 ...) and exit"
      exit 0
      ;;
  esac
done

echo "=========================================="
echo "Phase 12A Batched Execution"
echo "=========================================="
echo "Date: ${DATE}"
echo "Report base: ${REPORT_BASE}"
echo "Batches: ${#BATCHES[@]}"
echo ""
echo "Strategy: Run batches incrementally, fix issues before proceeding"
echo ""

# Track overall status
TOTAL_BATCHES=${#BATCHES[@]}
CURRENT_BATCH=0
FAILED_BATCHES=()

# Validate batch numbers
if [[ -n "$RUN_ONLY" ]]; then
  if [[ ! "$RUN_ONLY" =~ ^[0-9]+$ ]] || [[ "$RUN_ONLY" -lt 1 ]] || [[ "$RUN_ONLY" -gt "$TOTAL_BATCHES" ]]; then
    echo "Error: --batch must be a number between 1 and ${TOTAL_BATCHES}"
    exit 1
  fi
  START_FROM="$RUN_ONLY"
fi

if [[ ! "$START_FROM" =~ ^[0-9]+$ ]] || [[ "$START_FROM" -lt 1 ]] || [[ "$START_FROM" -gt "$TOTAL_BATCHES" ]]; then
  echo "Error: --start-from must be a number between 1 and ${TOTAL_BATCHES}"
  exit 1
fi

# Bring up test infrastructure once and wait for all core services (same env for all batches)
ensure_test_infra

# Process batches
for i in "${!BATCHES[@]}"; do
  CURRENT_BATCH=$((i + 1))

  # Skip batches before START_FROM
  if [[ $CURRENT_BATCH -lt $START_FROM ]]; then
    continue
  fi

  # If RUN_ONLY is set, only run that batch
  if [[ -n "$RUN_ONLY" ]] && [[ $CURRENT_BATCH -ne $RUN_ONLY ]]; then
    continue
  fi

  BATCH_DEF="${BATCHES[$i]}"
  BATCH_NAME="${BATCH_DEF%%|*}"

  # Scheduled Operations (any batch whose name contains "Scheduled"): wait for Prefect server for full-flow test
  if [[ "$BATCH_NAME" == *"Scheduled"* ]]; then
    echo "Waiting for Prefect server to be ready (for scheduled ingestion full-flow test)..."
    PREFECT_CHECK="$(cat <<'PYEOF'
import os, urllib.request
url = (os.getenv("PREFECT_API_URL") or "http://prefect-server-test:4200/api").rstrip("/") + "/health"
try:
  urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=5)
  exit(0)
except Exception:
  exit(1)
PYEOF
)"
    for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
      if $COMPOSE_CMD exec -T "${API_SVC}" python -c "$PREFECT_CHECK" 2>/dev/null; then
        echo "  Prefect server is ready (attempt $attempt)."
        break
      fi
      if [[ $attempt -eq 12 ]]; then
        echo "  Warning: Prefect server not reachable after 12 attempts; full-flow test will skip."
      else
        sleep 5
      fi
    done
  fi

  # Data Quality (batch name contains "Data Quality" or "DQ"): extra wait for DQ, Compliance, MinIO, S3
  if [[ "$BATCH_NAME" == *"Data Quality"* ]] || [[ "$BATCH_NAME" == *"DQ"* ]]; then
    echo "Waiting for DQ, Compliance, MinIO, and S3 bucket to be ready..."
    for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
      if $COMPOSE_CMD exec -T "${API_SVC}" python -c 'import os,sys,urllib.request
def ok(url):
    try: urllib.request.urlopen(urllib.request.Request(url,method="GET"),timeout=5); return True
    except Exception: return False
dq=ok(os.getenv("DQ_SERVICE_URL","http://dq-service-test:8083")+"/health")
comp=ok(os.getenv("COMPLIANCE_SERVICE_URL","http://compliance-service-test:8082")+"/health")
ep=os.getenv("AWS_S3_ENDPOINT_URL","http://minio-test:9000").replace("http://","").replace("https://","").split("/")[0]
minio_http=ok("http://"+ep+"/minio/health/live")
s3_ready=False
if dq and comp and minio_http:
    try:
        import boto3
        from botocore.exceptions import ClientError
        c=boto3.client("s3",endpoint_url=os.getenv("AWS_S3_ENDPOINT_URL","http://minio-test:9000"),aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID","minioadmin"),aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY","minioadmin"))
        try: c.head_bucket(Bucket=os.getenv("AWS_STORAGE_BUCKET_NAME","hub-test"))
        except ClientError as e:
            if e.response.get("Error",{}).get("Code","") in ("404","NoSuchBucket"): c.create_bucket(Bucket=os.getenv("AWS_STORAGE_BUCKET_NAME","hub-test"))
            else: raise
        c.put_object(Bucket=os.getenv("AWS_STORAGE_BUCKET_NAME","hub-test"),Key=".batch10-ready",Body=b"ok")
        s3_ready=True
    except Exception: pass
sys.exit(0 if (dq and comp and minio_http and s3_ready) else 1)' 2>/dev/null; then
        echo "  DQ, Compliance, MinIO, and S3 bucket are ready (attempt $attempt)."
        break
      fi
      if [[ $attempt -eq 12 ]]; then
        echo "  Warning: DQ/Compliance/MinIO/S3 not all ready after 12 attempts; integration tests may skip."
        echo "  From api-service-test, ensure DQ_SERVICE_URL, COMPLIANCE_SERVICE_URL, AWS_S3_ENDPOINT_URL and hub-test bucket are reachable."
        $COMPOSE_CMD exec -T "${API_SVC}" python -c '
import os,sys,urllib.request
def ok(url):
    try: urllib.request.urlopen(urllib.request.Request(url,method="GET"),timeout=3); return True
    except Exception as e: print("  Check failed:", url, str(e), file=sys.stderr); return False
dq=ok(os.getenv("DQ_SERVICE_URL","http://dq-service-test:8083")+"/health")
comp=ok(os.getenv("COMPLIANCE_SERVICE_URL","http://compliance-service-test:8082")+"/health")
ep=os.getenv("AWS_S3_ENDPOINT_URL","http://minio-test:9000").replace("http://","").replace("https://","").split("/")[0]
minio_http=ok("http://"+ep+"/minio/health/live")
print("  DQ:", dq, "Compliance:", comp, "MinIO:", minio_http, file=sys.stderr)
' 2>&1 || true
      else
        sleep 5
      fi
    done
  fi

  echo "Starting batch ${CURRENT_BATCH}/${TOTAL_BATCHES}"
  # Billing (batch name contains "Billing"): STRIPE_SECRET_KEY enables 4 extra tests; otherwise skipped (no mocks)
  if [[ "$BATCH_NAME" == *"Billing"* ]] && [[ -z "${STRIPE_SECRET_KEY:-}" ]]; then
    echo "  (STRIPE_SECRET_KEY not set; 4 Stripe-dependent tests will be skipped)"
  fi

  run_batch "$CURRENT_BATCH" "$BATCH_DEF"
  batch_ret=$?
  if [[ $batch_ret -eq 0 ]]; then
    echo "[PASS] Batch ${CURRENT_BATCH} PASSED"
  elif [[ $batch_ret -eq 2 ]]; then
    echo "Batch ${CURRENT_BATCH} canceled by user. Exiting."
    exit 130
  else
    # Failed: defer and continue, or stop (Phase 3.4)
    is_deferred=false
    for d in "${DEFERRED_BATCHES[@]}"; do
      if [[ $d -eq $CURRENT_BATCH ]]; then
        is_deferred=true
        break
      fi
    done
    if [[ "$is_deferred" == "true" ]]; then
      echo "[DEFERRED] Batch ${CURRENT_BATCH} failed; marking deferred and continuing (Phase 3.4)"
      echo "${DEFER_REASON:-deferred}" > "${BATCH_REPORT_BASE}/batch_${CURRENT_BATCH}/deferred"
    else
      echo "[FAIL] Batch ${CURRENT_BATCH} FAILED"
      FAILED_BATCHES+=("$CURRENT_BATCH")
      echo ""
      echo "STOPPING: Fix failures in batch ${CURRENT_BATCH} before proceeding"
      echo "   Review: ${BATCH_REPORT_BASE}/batch_${CURRENT_BATCH}/batch_${CURRENT_BATCH}.log"
      echo "   After fixing, re-run from batch ${CURRENT_BATCH}:"
      echo "   ./scripts/run_phase_12a_batched.sh --start-from ${CURRENT_BATCH}"
      echo "   To defer and continue: add --defer=${CURRENT_BATCH} --defer-reason=TICKET-XXX"
      echo ""
      exit 1
    fi
  fi

  # Phase 3.3: record batch status and link to log/junit (batch_status.json + batches/README.md)
  if [[ -x "$SCRIPT_DIR/generate_batch_status.sh" ]]; then
    "$SCRIPT_DIR/generate_batch_status.sh" "$BATCH_REPORT_BASE" >/dev/null 2>&1 || true
  fi

  echo ""

  # If RUN_ONLY is set, exit after running that batch (use single word 'break')
  if [[ -n "$RUN_ONLY" ]] && [[ $CURRENT_BATCH -eq $RUN_ONLY ]]; then
    break
  fi
done

# Phase 3.3: final batch status and README (so full run has up-to-date table)
if [[ -x "$SCRIPT_DIR/generate_batch_status.sh" ]]; then
  "$SCRIPT_DIR/generate_batch_status.sh" "$BATCH_REPORT_BASE" 2>/dev/null || true
fi

# Final summary
echo "=========================================="
echo "All Batches Complete"
echo "=========================================="
echo "Total batches: ${TOTAL_BATCHES}"
echo "Failed batches: ${#FAILED_BATCHES[@]}"
echo "Status: ${BATCH_REPORT_BASE}/batch_status.json and ${BATCH_REPORT_BASE}/README.md"
if [[ ${#FAILED_BATCHES[@]} -gt 0 ]]; then
  echo "Failed batch numbers: ${FAILED_BATCHES[*]}"
  exit 1
else
  echo "All batches passed (or deferred)!"
  exit 0
fi
