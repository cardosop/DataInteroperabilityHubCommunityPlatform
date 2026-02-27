#!/usr/bin/env bash
# Phase 12A Batched Execution — Run tests in batches, fix issues before proceeding
# Per gapfix1 FG.1 — Incremental approach: run small batches, fix root causes, then proceed
# No mocks/stubs; root-cause fixes only.
#
# Infrastructure: All batches run against the same test environment (docker-compose.test.yml).
# The script brings up the test stack and waits for required services before running any batch.
# Keep the stack running for the full batch run; Postgres or other services restarting mid-run
# causes connection errors and incorrect summary parsing (root cause: parse only pytest summary line).
#
# Prerequisites:
#   - Docker and Docker Compose
#   - From repo root: ./scripts/run_phase_12a_batched.sh [--batch=N] [--start-from=N]
#   To clean and restart test stack first: ./scripts/clean-test-stack.sh
#   To also remove volumes (fresh Postgres init, faster startup): ./scripts/clean-test-stack.sh --volumes
#   This script always uses docker-compose.test.yml and api-service-test (no env override).
#
# Requires bash (uses arrays, [[ ]], heredocs, etc.). Re-exec with bash if run via sh.
if [ -z "${BASH_VERSION:-}" ]; then
  if command -v bash >/dev/null 2>&1; then
    exec bash "$0" "$@"
  fi
  if [ -x /bin/bash ]; then
    exec /bin/bash "$0" "$@"
  fi
  echo "Error: This script requires bash. Run: bash $0 $*" >&2
  exit 1
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Load test env so STRIPE_SECRET_KEY (and others) are available for batch runs (e.g. Billing batch 37)
if [[ -f .env.test ]]; then
  set -a
  # shellcheck source=/dev/null
  source .env.test
  set +a
fi

# Always use test infrastructure (same env for all batches). Hardcode test file and service
# so we never pick up docker-compose.yml or API_SERVICE_NAME=api-service from the environment.
COMPOSE_FILE=docker-compose.test.yml
export COMPOSE_FILE
API_SVC=api-service-test

# Parallel workers for pytest-xdist (-n). 0 = sequential. 4 = good for 4-core.
PYTEST_PARALLEL_WORKERS="${PYTEST_PARALLEL_WORKERS:-4}"
# Explicit -f so only this file is used (no merge with default compose or override).
# Use --env-file .env.test when present so Postgres credentials match (avoids "password authentication failed").
COMPOSE_CMD="docker compose -f ${COMPOSE_FILE}"
[[ -f .env.test ]] && COMPOSE_CMD="${COMPOSE_CMD} --env-file .env.test"

# Core test services that must be running (no profile; worker/Prefect are optional)
# Include ODH services so ML/inference batches (e.g. 44) have inference scheduler and training operator ready
TEST_SERVICES=(postgres-test redis-cache-test redis-queue-test redis-events-test redis-channels-test minio-test fuseki-test datacontract-service-test dq-service-test compliance-service-test semantic-service-test odh-inference-scheduler-test odh-training-operator-test api-service-test)

ensure_test_infra() {
  echo "Ensuring test infrastructure is up (COMPOSE_FILE=${COMPOSE_FILE})..."
  if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Error: $COMPOSE_FILE not found."
    exit 1
  fi
  if ! $COMPOSE_CMD up -d --wait 2>&1; then
    echo "Error: docker compose up -d --wait failed. Fix the cause and re-run. See above for details." >&2
    exit 1
  fi
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
      break
    fi
    sleep 5
    waited=$((waited + 5))
  done
  if [[ "$all_up" != "true" ]]; then
    echo "Error: Not all core services are running after ${wait_max}s. Check: $COMPOSE_CMD ps -a"
    $COMPOSE_CMD ps -a 2>/dev/null || true
    exit 1
  fi
  # Wait for Postgres to be healthy (accepting connections). Avoids pytest session errors
  # when DB is still in "starting up" / "consistent recovery state not yet reached".
  # Align with docker-compose.test.yml postgres-test healthcheck start_period (600s).
  local pg_healthy_max=600
  local pg_waited=0
  while [[ $pg_waited -lt $pg_healthy_max ]]; do
    local health
    health=$($COMPOSE_CMD ps -q postgres-test 2>/dev/null | xargs -r docker inspect -f '{{.State.Health.Status}}' 2>/dev/null | head -1)
    if [[ "$health" == "healthy" ]]; then
      echo "  Postgres is healthy."
      return 0
    fi
    sleep 5
    pg_waited=$((pg_waited + 5))
  done
  echo "Warning: Postgres not healthy after ${pg_healthy_max}s; proceeding anyway (conftest will retry)."
  return 0
}

# Ensure api-service-test can resolve postgres-test (Docker DNS can be slow). Run once before any batch.
# Avoids "could not translate host name postgres-test" errors at first django_db_setup.
ensure_postgres_resolvable_from_api() {
  echo "Checking that api-service-test can resolve postgres-test..."
  local max_attempts=18
  local attempt=1
  while [[ $attempt -le $max_attempts ]]; do
    if $COMPOSE_CMD exec -T "${API_SVC}" python3 -c "
import socket
try:
  socket.gethostbyname('postgres-test')
  exit(0)
except Exception:
  exit(1)
" 2>/dev/null; then
      echo "  postgres-test is resolvable from ${API_SVC}."
      return 0
    fi
    echo "  Attempt ${attempt}/${max_attempts}: postgres-test not yet resolvable, waiting 10s..."
    sleep 10
    attempt=$((attempt + 1))
  done
  echo "Error: Could not resolve postgres-test from ${API_SVC} after ${max_attempts} attempts."
  echo "  Ensure Docker Compose network is up and api-service-test is on the same network as postgres-test."
  echo "  Try: $COMPOSE_CMD ps -a && $COMPOSE_CMD exec ${API_SVC} getent hosts postgres-test || true"
  return 1
}

# Wait for Postgres to report healthy (e.g. after OOM restart). Used after detecting shutdown in batch log.
# Args: max_wait_seconds [min_stabilization_seconds]
# Default 300s max allows start_period + recovery. min_stabilization (default 15) ensures we do not
# return immediately when Postgres is "healthy" — gives time for recovery/connection pools to stabilize.
wait_postgres_healthy() {
  local max="${1:-300}"
  local min_stab="${2:-15}"
  local waited=0
  while [[ $waited -lt $max ]]; do
    local health
    health=$($COMPOSE_CMD ps -q postgres-test 2>/dev/null | xargs -r docker inspect -f '{{.State.Health.Status}}' 2>/dev/null | head -1)
    if [[ "$health" == "healthy" ]]; then
      if [[ $min_stab -gt 0 ]]; then
        echo "  Postgres healthy after ${waited}s; waiting ${min_stab}s stabilization before proceeding..."
        sleep "$min_stab"
        waited=$((waited + min_stab))
      fi
      echo "  Postgres is healthy again after ${waited}s."
      return 0
    fi
    sleep 5
    waited=$((waited + 5))
  done
  echo "  Warning: Postgres not healthy after ${max}s."
  return 1
}

DATE="${DATE:-$(date +%Y-%m-%d)}"
# Avoid literal "null" in paths (e.g. from env) which can cause "/null" file errors
[[ "$DATE" == "null" ]] || [[ -z "$DATE" ]] && DATE=$(date +%Y-%m-%d)
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
  # Skip coverage for heavy batches to avoid OOM (exit 137); key by name/path so batch_definitions.txt works
  local cov_args="--cov=hub --cov-report=term-missing --cov-report=xml:/tmp/coverage_batch_${batch_num}.xml"
  if [[ "$batch_name" == *"ODPS"* ]] || [[ "$batch_name" == *"ODCS"* ]] || [[ "$batch_name" == *"Files"* ]] || [[ "$batch_name" == *"Scheduled"* ]]; then
    cov_args="--no-cov"
  else
    for p in "${batch_paths[@]}"; do
      if [[ "$p" == *"test_odps"* ]] || [[ "$p" == *"test_odcs"* ]] || [[ "$p" == *"files/tests"* ]]; then
        cov_args="--no-cov"
        break
      fi
      # Scheduled ingestion/export and integration tests are heavy; skip coverage to avoid OOM (exit 137)
      if [[ "$p" == *"scheduled_ingestion/tests"* ]] || [[ "$p" == *"scheduled_export/tests"* ]]; then
        cov_args="--no-cov"
        break
      fi
      if [[ "$p" == *"test_event_publishers_integration"* ]] || [[ "$p" == *"test_connection_validation_integration"* ]]; then
        cov_args="--no-cov"
        break
      fi
    done
  fi
  # Pre-flight: ensure Postgres is reachable from the container (lightweight: psycopg2 only, no Django).
  # Avoids OOM from Django setup in exec and long pytest run when Postgres is down. Uses same DB as pytest (hub_test).
  # When Postgres is "starting up" (recovery), use longer retries (600s max) to allow WAL replay.
  local db_check_attempts=5
  local db_check_interval=15
  local preflight_out
  while [[ $db_check_attempts -gt 0 ]]; do
    preflight_out=$($COMPOSE_CMD exec -T "${API_SVC}" bash -c 'set -a; [ -f /app/.env.test ] && . /app/.env.test; set +a; python3 -c "
import os, sys
h=os.environ.get(\"POSTGRES_HOST\",\"localhost\")
p=int(os.environ.get(\"POSTGRES_PORT\",\"5432\"))
u=os.environ.get(\"POSTGRES_USER\",\"\")
pw=os.environ.get(\"POSTGRES_PASSWORD\",\"\")
db=os.environ.get(\"POSTGRES_DB\",\"hub_test\")
try:
  import psycopg2
  c=psycopg2.connect(host=h,port=p,user=u,password=pw,dbname=db,connect_timeout=10)
  c.close()
  print(\"DB OK\")
except Exception as e:
  print(\"DB FAIL:\", e, file=sys.stderr)
  sys.exit(1)
"' 2>&1)
    if echo "$preflight_out" | grep -q "DB OK"; then
      echo "Pre-flight DB check OK."
      break
    fi
    # On "starting up", extend retries (recovery can take 60-600s; align with postgres start_period)
    if echo "$preflight_out" | grep -qi "database system is starting up"; then
      db_check_attempts=10
      db_check_interval=60
    fi
    db_check_attempts=$((db_check_attempts - 1))
    if [[ $db_check_attempts -gt 0 ]]; then
      echo "Pre-flight DB check failed; retrying in ${db_check_interval}s (${db_check_attempts} left)..."
      sleep "$db_check_interval"
    else
      if echo "$preflight_out" | grep -qi "database system is starting up"; then
        echo "Error: Postgres still in recovery (database system is starting up) after retries."
        echo "  Wait for Postgres to finish recovery, then re-run. Or: $COMPOSE_CMD restart postgres-test && sleep 120"
        exit 1
      fi
      echo "Warning: Pre-flight DB check failed after retries; proceeding with pytest (may error at setup)."
      if echo "$preflight_out" | grep -qi "password authentication failed"; then
        echo "  Hint: Postgres credentials mismatch. Recreate the test DB volume: $COMPOSE_CMD down -v && $COMPOSE_CMD up -d"
      fi
    fi
  done

  # When batch includes Snowflake E2E but credentials are unset, deselect those tests (0 skips instead of 6)
  local extra_pytest_args=""
  for p in "${batch_paths[@]}"; do
    if [[ "$p" == *"test_connectors_e2e"* ]]; then
      if [[ -z "${SNOWFLAKE_ACCOUNT:-}" ]] || [[ -z "${SNOWFLAKE_USER:-}" ]] || [[ -z "${SNOWFLAKE_TOKEN:-}" ]]; then
        extra_pytest_args="-m 'not snowflake_e2e'"
        echo "  SNOWFLAKE_* unset; deselecting snowflake_e2e tests (no skips)."
      fi
      break
    fi
  done

  # When batch includes Jobs tests, deselect scheduled_ingestion_integration (requires real S3/Prefect; 0 skips in default batch)
  for p in "${batch_paths[@]}"; do
    if [[ "$p" == *"jobs/tests"* ]]; then
      extra_pytest_args="-m 'not scheduled_ingestion_integration'"
      echo "  Jobs batch: deselecting scheduled_ingestion_integration (requires real S3/Prefect)."
      break
    fi
  done

  # When batch includes Billing tests and STRIPE_SECRET_KEY is unset, deselect requires_stripe (0 skips in default batch)
  for p in "${batch_paths[@]}"; do
    if [[ "$p" == *"billing/tests"* ]] && [[ -z "${STRIPE_SECRET_KEY:-}" ]]; then
      extra_pytest_args="-m 'not requires_stripe'"
      echo "  Billing batch: STRIPE_SECRET_KEY unset; deselecting requires_stripe (0 skips)."
      break
    fi
  done

  # When batch includes marketplace connector integration tests or AWS E2E tests, deselect credential-dependent tests when creds unset (0 skips, no mocks)
  local has_connectors=false
  local has_aws_e2e=false
  for p in "${batch_paths[@]}"; do
    if [[ "$p" == *"test_marketplace_connectors"* ]]; then
      has_connectors=true
    fi
    if [[ "$p" == *"test_aws_data_exchange_e2e"* ]]; then
      has_aws_e2e=true
    fi
  done
  if [[ "$has_connectors" == "true" ]] || [[ "$has_aws_e2e" == "true" ]]; then
    local mark_parts=()
    [[ -z "${SNOWFLAKE_ACCOUNT:-}" ]] || [[ -z "${SNOWFLAKE_USER:-}" ]] || [[ -z "${SNOWFLAKE_TOKEN:-}" ]] && mark_parts+=("not snowflake_integration")
    # Treat MinIO credentials (minio/minio123) as unset for AWS Data Exchange; real AWS keys start with AKIA/ASIA
    local aws_ok=false
    [[ -n "${AWS_ACCESS_KEY_ID:-}" ]] && [[ -n "${AWS_SECRET_ACCESS_KEY:-}" ]] && [[ "${AWS_ACCESS_KEY_ID}" != "minio" ]] && aws_ok=true
    [[ "$aws_ok" != "true" ]] && mark_parts+=("not aws_integration")
    # Deselect GCP when project_id unset or no explicit credentials (ADC often fails in Docker/CI)
    local gcp_ok=false
    if [[ -n "${GCP_PROJECT_ID:-}" ]]; then
      if [[ -n "${GCP_CREDENTIALS_JSON_FILE:-}" ]] && [[ -f "${GCP_CREDENTIALS_JSON_FILE}" ]]; then
        gcp_ok=true
      elif [[ -n "${GCP_CREDENTIALS_JSON:-}" ]] || [[ -n "${GCP_SERVICE_ACCOUNT_JSON:-}" ]]; then
        gcp_ok=true
      fi
    fi
    [[ "$gcp_ok" != "true" ]] && mark_parts+=("not gcp_integration")
    if [[ ${#mark_parts[@]} -gt 0 ]]; then
      local mark_expr
      mark_expr=$(printf '%s and ' "${mark_parts[@]}" | sed 's/ and $//')
      if [[ -n "$extra_pytest_args" ]]; then
        extra_pytest_args="-m '${mark_expr} and not snowflake_e2e'"
      else
        extra_pytest_args="-m '${mark_expr}'"
      fi
      echo "  Credentials unset; deselecting integration tests requiring real credentials (${mark_expr})."
    fi
  fi

  # When batch includes marketplace framework tests, run them first in isolation so DB connection is fresh (avoids connection-already-closed failures)
  local has_framework=false
  for p in "${batch_paths[@]}"; do
    if [[ "$p" == *"test_marketplace_framework.py"* ]]; then
      has_framework=true
      break
    fi
  done

  local batch_exit=0
  if [[ "$has_framework" == "true" ]]; then
    local framework_path=""
    local other_paths=()
    for p in "${batch_paths[@]}"; do
      if [[ "$p" == *"test_marketplace_framework.py"* ]]; then
        framework_path="$p"
      else
        other_paths+=("$p")
      fi
    done
    # Batch 51 etc.: framework file only in first run (~13 tests); on success, remaining batch files run (total = framework + rest).
    echo "Running marketplace framework tests first (isolated run for stable DB connection)..."
    xdist_args=""
    [[ "${PYTEST_PARALLEL_WORKERS}" -gt 0 ]] && xdist_args="-n ${PYTEST_PARALLEL_WORKERS} --dist=loadscope"
    set +e
    $COMPOSE_CMD exec -T \
      -e STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-}" \
      -e DB_CONNECTIVITY_CHECK_RETRIES=72 \
      -e DB_CONNECTIVITY_CHECK_INTERVAL=5 \
      "${API_SVC}" bash -c \
      "set -a; [ -f /app/.env.test ] && . /app/.env.test; set +a; export DB_CONNECTIVITY_CHECK_RETRIES=72; export DB_CONNECTIVITY_CHECK_INTERVAL=5; rm -f /app/.coverage && cd /app && BATCH_TEST=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest \
      ${framework_path} \
      -v -rs --reuse-db --timeout=300 --tb=short ${xdist_args} \
      --junit-xml=/tmp/junit_fw_${batch_num}.xml \
      --no-cov" 2>&1 | tee "$batch_log"
    local fw_exit=${PIPESTATUS[0]}
    set -e
    if [[ "$fw_exit" -ne 0 ]]; then
      $COMPOSE_CMD cp "${API_SVC}:/tmp/junit_fw_${batch_num}.xml" "$batch_junit" 2>/dev/null || true
      batch_exit=$fw_exit
    else
      echo "Running remaining batch tests..."
      set +e
      $COMPOSE_CMD exec -T \
        -e STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-}" \
        -e DB_CONNECTIVITY_CHECK_RETRIES=72 \
        -e DB_CONNECTIVITY_CHECK_INTERVAL=5 \
        "${API_SVC}" bash -c \
        "set -a; [ -f /app/.env.test ] && . /app/.env.test; set +a; export DB_CONNECTIVITY_CHECK_RETRIES=72; export DB_CONNECTIVITY_CHECK_INTERVAL=5; cd /app && BATCH_TEST=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest \
        ${other_paths[*]} \
        ${extra_pytest_args} \
        -v -rs --reuse-db --timeout=300 --maxfail=10 --tb=short ${xdist_args} \
        --junit-xml=/tmp/junit_rest_${batch_num}.xml \
        --cov-append \
        ${cov_args}" 2>&1 | tee -a "$batch_log"
      local rest_exit=${PIPESTATUS[0]}
      set -e
      batch_exit=$rest_exit
      # Merge JUnit: combine testsuite elements from both runs
      $COMPOSE_CMD cp "${API_SVC}:/tmp/junit_fw_${batch_num}.xml" "${batch_dir}/junit_fw.xml" 2>/dev/null || true
      $COMPOSE_CMD cp "${API_SVC}:/tmp/junit_rest_${batch_num}.xml" "${batch_dir}/junit_rest.xml" 2>/dev/null || true
      if [[ -f "${batch_dir}/junit_fw.xml" ]] && [[ -f "${batch_dir}/junit_rest.xml" ]]; then
        python3 << PYEOF 2>/dev/null || cp "${batch_dir}/junit_rest.xml" "$batch_junit"
import xml.etree.ElementTree as ET
def merge_suites(a_path, b_path, out_path):
    tree_a = ET.parse(a_path)
    tree_b = ET.parse(b_path)
    root_a = tree_a.getroot()
    root_b = tree_b.getroot()
    def suites_iter(root):
        if root.tag == 'testsuites':
            for c in root: yield c
        else:
            yield root
    suites = list(suites_iter(root_a)) + list(suites_iter(root_b))
    total_tests = total_failures = total_errors = total_skipped = total_time = 0
    for s in suites:
        total_tests += int(s.get('tests', 0))
        total_failures += int(s.get('failures', 0))
        total_errors += int(s.get('errors', 0))
        total_skipped += int(s.get('skipped', 0))
        total_time += float(s.get('time', 0) or 0)
    out = ET.Element('testsuites', tests=str(total_tests), failures=str(total_failures), errors=str(total_errors), skipped=str(total_skipped), time='%.3f' % total_time)
    for s in suites:
        out.append(s)
    ET.ElementTree(out).write(out_path, encoding='unicode', default_namespace='', xml_declaration=True)
merge_suites('${batch_dir}/junit_fw.xml', '${batch_dir}/junit_rest.xml', '${batch_junit}')
PYEOF
      else
        cp "${batch_dir}/junit_rest.xml" "$batch_junit" 2>/dev/null || true
      fi
      if [[ "$cov_args" != "--no-cov" ]]; then
        $COMPOSE_CMD cp "${API_SVC}:/tmp/coverage_batch_${batch_num}.xml" "${batch_dir}/coverage.xml" 2>/dev/null || true
      fi
    fi
  else
    echo "Running pytest in ${API_SVC} (parallel=${PYTEST_PARALLEL_WORKERS}, collection may take 1–2 min for large batches)..."
    xdist_args=""
    [[ "${PYTEST_PARALLEL_WORKERS}" -gt 0 ]] && xdist_args="-n ${PYTEST_PARALLEL_WORKERS} --dist=loadscope"
    set +e
    $COMPOSE_CMD exec -T \
      -e STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-}" \
      -e DB_CONNECTIVITY_CHECK_RETRIES=72 \
      -e DB_CONNECTIVITY_CHECK_INTERVAL=5 \
      "${API_SVC}" bash -c \
      "set -a; [ -f /app/.env.test ] && . /app/.env.test; set +a; export DB_CONNECTIVITY_CHECK_RETRIES=72; export DB_CONNECTIVITY_CHECK_INTERVAL=5; rm -f /app/.coverage && cd /app && BATCH_TEST=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest \
      ${batch_paths[*]} \
      ${extra_pytest_args} \
      -v -rs --reuse-db --timeout=300 --maxfail=10 --tb=short ${xdist_args} \
      --junit-xml=/tmp/junit_batch_${batch_num}.xml \
      ${cov_args}" 2>&1 | tee "$batch_log"
    batch_exit=${PIPESTATUS[0]}
    set -e
    $COMPOSE_CMD cp "${API_SVC}:/tmp/junit_batch_${batch_num}.xml" "$batch_junit" 2>/dev/null || true
    if [[ "$cov_args" != "--no-cov" ]]; then
      $COMPOSE_CMD cp "${API_SVC}:/tmp/coverage_batch_${batch_num}.xml" "${batch_dir}/coverage.xml" 2>/dev/null || true
    fi
  fi

  local batch_end=$(date +%s)
  local batch_duration=$((batch_end - batch_start))

  # Extract test summary from pytest's final summary line(s). When framework ran in two invocations, sum both.
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

  # Sanitize to integers: strip newlines/whitespace and take first integer so arithmetic never sees "0\n0" (syntax error).
  _to_int() { printf '%s' "$1" | head -1 | tr -d '\n\r\t ' | grep -oE '[0-9]+' | head -1 || echo "0"; }
  total=$(( $( _to_int "$total" ) + 0 ))
  failed=$(( $( _to_int "$failed" ) + 0 ))
  errors=$(( $( _to_int "$errors" ) + 0 ))
  skipped=$(( $( _to_int "$skipped" ) + 0 ))

  # Exit 137 = process killed (SIGKILL), often OOM. Infer counts from log but do NOT mark batch as passed.
  if [[ "$batch_exit" -eq 137 ]] && [[ -f "$batch_log" ]]; then
    local passed_count=$(grep -c " PASSED " "$batch_log" 2>/dev/null || echo "0")
    local failed_count=$(grep -c " FAILED " "$batch_log" 2>/dev/null || echo "0")
    local error_count=$(grep -c " ERROR " "$batch_log" 2>/dev/null || echo "0")
    passed_count=$(( $( _to_int "$passed_count" ) + 0 ))
    failed_count=$(( $( _to_int "$failed_count" ) + 0 ))
    error_count=$(( $( _to_int "$error_count" ) + 0 ))
    if [[ "$total" -eq 0 ]] && [[ "$passed_count" -gt 0 ]]; then
      total=$passed_count
    fi
    if [[ "$failed" -eq 0 ]] && [[ "$failed_count" -gt 0 ]]; then
      failed=$failed_count
    fi
    if [[ "$errors" -eq 0 ]] && [[ "$error_count" -gt 0 ]]; then
      errors=$error_count
    fi
    echo "Note: Process killed (exit 137, likely OOM); batch did not complete. Passed: ${total:-0}, Failed: ${failed:-0}, Errors: ${errors:-0}."
    # Do not set batch_exit=0: incomplete or killed run is a failure.
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
  echo "  Duration: ${batch_duration:-0}s"
  echo "  Passed: ${total:-0}"
  echo "  Failed: ${failed:-0}"
  echo "  Errors: ${errors:-0}"
  echo "  Skipped: ${skipped:-0}"
  echo "  Log: ${batch_log}"
  echo ""

  # Surface infrastructure failures and wait for Postgres/network so next batch or re-run is stable.
  # Triggers: Postgres shutdown/recovery, connection FATAL, or DNS resolution failure (Docker DNS transient).
  # "database system is starting up" = recovery; use 600s (align with postgres start_period)
  local transient_infra_detected=false
  if grep -q "database system is shutting down\|connection to server.*failed.*FATAL\|database system is starting up\|could not translate host name\|Temporary failure in name resolution\|name or service not known" "$batch_log" 2>/dev/null; then
    transient_infra_detected=true
    local pg_wait=300
    if grep -q "database system is starting up" "$batch_log" 2>/dev/null; then
      pg_wait=600
      echo "  Note: Log shows Postgres in recovery (starting up). Waiting for Postgres to be healthy again (up to 600s)..."
    elif grep -q "could not translate host name\|Temporary failure in name resolution\|name or service not known" "$batch_log" 2>/dev/null; then
      pg_wait=120
      echo "  Note: Log shows DNS resolution failure (postgres-test). Waiting for network/Postgres (up to 120s)..."
    else
      echo "  Note: Log shows Postgres shutdown/connection failure. Waiting for Postgres to be healthy again (up to 300s)..."
    fi
    # Pass 15s min stabilization so we never return "healthy after 0s" — gives Postgres time to fully stabilize
    wait_postgres_healthy "$pg_wait" 15 || true
    echo ""
  fi

  # If batch had failures/errors and transient infra (Postgres or DNS) was detected, retry only the failed
  # tests once after recovery (root cause: transient infra; no mocks). Pytest --lf uses .pytest_cache.
  if [[ "$transient_infra_detected" == "true" ]] && { [[ "$failed" -gt 0 ]] || [[ "$errors" -gt 0 ]]; }; then
    echo "  Re-running failed tests (--lf) after infra recovery..."
    set +e
    $COMPOSE_CMD exec -T \
      -e STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-}" \
      -e DB_CONNECTIVITY_CHECK_RETRIES=72 \
      -e DB_CONNECTIVITY_CHECK_INTERVAL=5 \
      "${API_SVC}" bash -c \
      "set -a; [ -f /app/.env.test ] && . /app/.env.test; set +a; cd /app && BATCH_TEST=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest \
      ${batch_paths[*]} \
      ${extra_pytest_args} \
      -v -rs --reuse-db --timeout=300 --tb=short --lf \
      --junit-xml=/tmp/junit_batch_${batch_num}_retry.xml \
      --no-cov" 2>&1 | tee -a "$batch_log"
    local retry_exit=${PIPESTATUS[0]}
    set -e
    if [[ "$retry_exit" -eq 0 ]]; then
      echo "  All failed tests passed on retry (transient infra: Postgres or DNS)."
      batch_exit=0
      failed=0
      errors=0
      $COMPOSE_CMD cp "${API_SVC}:/tmp/junit_batch_${batch_num}_retry.xml" "$batch_junit" 2>/dev/null || true
      cat > "${batch_dir}/summary.json" << EOF
{
  "batch_num": ${batch_num},
  "batch_name": "${batch_name_escaped}",
  "paths": ${paths_json},
  "exit_code": 0,
  "duration_seconds": ${batch_duration},
  "total": ${total:-0},
  "failed": 0,
  "errors": 0,
  "skipped": ${skipped:-0},
  "last_run": "${last_run}",
  "log": "${log_escaped}",
  "junit": "${junit_escaped}",
  "recovered_after_postgres_restart": true
}
EOF
      echo "Batch ${batch_num} Summary (after retry):"
      echo "  Exit code: 0 (recovered after transient infra)"
      echo "  Passed: ${total:-0}"
      echo "  Failed: 0"
      echo "  Errors: 0"
      echo "  Skipped: ${skipped:-0}"
      echo "  Log: ${batch_log}"
      echo ""
      return 0
    fi
    echo "  Retry still had failures; keeping original batch result."
    echo ""
  fi

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
# Ensure api container can resolve Postgres (avoids batch 47-style "name resolution" errors at first DB setup)
ensure_postgres_resolvable_from_api || exit 1

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
    # Heredoc terminator must be at column 0 (no leading space) or bash does not recognize it
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
    DQ_SCRIPT="/app/scripts/dq_batch_check.py"
    for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
      if $COMPOSE_CMD exec -T "${API_SVC}" python "$DQ_SCRIPT" 2>/dev/null; then
        echo "  DQ, Compliance, MinIO, and S3 bucket are ready (attempt $attempt)."
        break
      fi
      if [[ $attempt -eq 12 ]]; then
        echo "  Warning: DQ/Compliance/MinIO/S3 not all ready after 12 attempts; integration tests may skip."
        echo "  From api-service-test, ensure DQ_SERVICE_URL, COMPLIANCE_SERVICE_URL, AWS_S3_ENDPOINT_URL and hub-test bucket are reachable."
        $COMPOSE_CMD exec -T "${API_SVC}" python "$DQ_SCRIPT" --diagnose 2>&1 || true
      else
        sleep 5
      fi
    done
  fi

  # AI & ML (batch name or path contains ML / ml/tests): wait for ODH Inference Scheduler so real integration tests do not skip
  if [[ "$BATCH_NAME" == *"ML"* ]] || [[ "$BATCH_NAME" == *"ml"* ]] || [[ "$BATCH_DEF" == *"ml/tests"* ]]; then
    echo "Waiting for ODH Inference Scheduler to be ready (for ML real integration tests)..."
    ODH_CHECK="$(cat <<'ODHEOF'
import os, urllib.request
url = (os.getenv("ODH_INFERENCE_SCHEDULER_URL") or "http://odh-inference-scheduler-test:8080").rstrip("/") + "/health"
try:
  urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=5)
  exit(0)
except Exception:
  exit(1)
ODHEOF
)"
    for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
      if $COMPOSE_CMD exec -T "${API_SVC}" python -c "$ODH_CHECK" 2>/dev/null; then
        echo "  ODH Inference Scheduler is ready (attempt $attempt)."
        break
      fi
      if [[ $attempt -eq 12 ]]; then
        echo "  Warning: ODH Inference Scheduler not reachable after 12 attempts; inference real integration tests will skip."
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
  GEN_STATUS="$SCRIPT_DIR/generate_batch_status.sh"
  if [[ -n "$SCRIPT_DIR" ]] && [[ -f "$GEN_STATUS" ]] && [[ -x "$GEN_STATUS" ]]; then
    "$GEN_STATUS" "$BATCH_REPORT_BASE" >/dev/null 2>&1 || true
  fi

  echo ""

  # If RUN_ONLY is set, exit after running that batch (use single word 'break')
  if [[ -n "$RUN_ONLY" ]] && [[ $CURRENT_BATCH -eq $RUN_ONLY ]]; then
    break
  fi
done

# Phase 3.3: final batch status and README (so full run has up-to-date table)
GEN_STATUS="$SCRIPT_DIR/generate_batch_status.sh"
if [[ -n "$SCRIPT_DIR" ]] && [[ -f "$GEN_STATUS" ]] && [[ -x "$GEN_STATUS" ]]; then
  "$GEN_STATUS" "$BATCH_REPORT_BASE" 2>/dev/null || true
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
