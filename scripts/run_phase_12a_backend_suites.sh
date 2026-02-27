#!/usr/bin/env bash
# Phase 12A.1 — Run backend test suites with artifact collection
# Per docs/TEST_EXECUTION_PLAN.md and openspec/changes/testreview1/tasks.md
# No mocks/stubs; root-cause fixes only.
#
# Unit phase: batched + parallel (pytest-xdist -n) for ~18k tests. Set PYTEST_PARALLEL_WORKERS=0 to disable parallel.
# All tests run inside Docker via docker compose exec. Ensure stack is up: docker compose -f docker-compose.test.yml up -d

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Same env as batched runs (Phase 4.1): default to test compose so full suite runs against same stack
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
export COMPOSE_FILE

# Load .env.test so STRIPE_SECRET_KEY (and others) available for billing tests (Batch 17)
[[ -f .env.test ]] && { set -a; source .env.test; set +a; }

# Explicit -f for all docker compose commands (robust when COMPOSE_FILE not inherited)
DC="docker compose -f ${COMPOSE_FILE}"
[[ -f .env.test ]] && DC="${DC} --env-file .env.test"

# API service name: when using docker-compose.test.yml the service is api-service-test (see docs/TEST_EXECUTION_PLAN.md)
if [[ -n "${API_SERVICE_NAME:-}" ]]; then
  API_SVC="${API_SERVICE_NAME}"
elif [[ "${COMPOSE_FILE:-}" == *"docker-compose.test"* ]]; then
  API_SVC="api-service-test"
else
  API_SVC="api-service"
fi

# Parallel workers for pytest-xdist (-n). 0 = sequential. 4 = good for 4-core; auto = CPU count.
PYTEST_PARALLEL_WORKERS="${PYTEST_PARALLEL_WORKERS:-4}"

DATE="${DATE:-$(date +%Y-%m-%d)}"
REPORT_BASE="test_reports_comprehensive/${DATE}"
mkdir -p "${REPORT_BASE}/unit" "${REPORT_BASE}/integration" "${REPORT_BASE}/e2e" "${REPORT_BASE}/uc_journey_persona"

export DJANGO_SETTINGS_MODULE=hub.settings
export PYTHONPATH="${PROJECT_DIR}"

# Pre-flight: ensure api-service-test is running (avoids "no response" when exec blocks on missing container)
echo "===== Pre-flight: checking test stack ====="
if ! $DC ps -q "${API_SVC}" 2>/dev/null | grep -q .; then
  echo "[INFO] ${API_SVC} not running. Bringing up test stack..."
  $DC up -d
  echo "[INFO] Waiting for ${API_SVC} to be ready (up to 180s)..."
  for i in $(seq 1 36); do
    if $DC exec -T "${API_SVC}" true 2>/dev/null; then
      echo "[INFO] ${API_SVC} is ready."
      break
    fi
    sleep 5
    [[ $i -eq 36 ]] && { echo "[ERROR] ${API_SVC} did not become ready in 180s. Check: $DC logs ${API_SVC}" >&2; exit 1; }
  done
else
  # Quick exec check to ensure container is responsive
  if ! $DC exec -T "${API_SVC}" true 2>/dev/null; then
    echo "[ERROR] ${API_SVC} is listed but exec failed. Restart: $DC restart ${API_SVC}" >&2
    exit 1
  fi
  echo "[INFO] ${API_SVC} is running and responsive."
fi

# Ensure api-service-test is running before a batch (restart if it crashed mid-run, e.g. OOM during batch 20)
ensure_api_service_running() {
  if ! $DC ps -q "${API_SVC}" 2>/dev/null | grep -q .; then
    echo "[WARN] ${API_SVC} not running. Restarting..."
    $DC up -d "${API_SVC}"
    echo "[INFO] Waiting for ${API_SVC} to be ready (up to 120s)..."
    for j in $(seq 1 24); do
      if $DC exec -T "${API_SVC}" true 2>/dev/null; then
        echo "[INFO] ${API_SVC} is ready."
        return 0
      fi
      sleep 5
    done
    echo "[ERROR] ${API_SVC} did not become ready. Check: $DC logs ${API_SVC}" >&2
    return 1
  fi
  if ! $DC exec -T "${API_SVC}" true 2>/dev/null; then
    echo "[WARN] ${API_SVC} unresponsive. Restarting..."
    $DC restart "${API_SVC}"
    sleep 10
    for j in $(seq 1 12); do
      if $DC exec -T "${API_SVC}" true 2>/dev/null; then
        echo "[INFO] ${API_SVC} is ready."
        return 0
      fi
      sleep 5
    done
    echo "[ERROR] ${API_SVC} did not become ready after restart." >&2
    return 1
  fi
  return 0
}

# Unit batches — hub/apps/ + tests/unit/ split for faster runs (~18k tests total)
# Format: "BATCH_NAME|path1|path2|..."
UNIT_BATCHES=(
  "Core|hub/apps/core/tests/|hub/apps/api/tests/|hub/apps/health/tests/"
  "Auth|hub/apps/auth/tests/"
  "Audit|hub/apps/audit/tests/"
  "Assets|hub/apps/assets/tests/"
  "Contracts Core|hub/apps/contracts/tests/test_models.py|hub/apps/contracts/tests/test_serializers.py|hub/apps/contracts/tests/test_services.py|hub/apps/contracts/tests/test_views.py"
  "Contracts ODPS|hub/apps/contracts/tests/test_odps_*.py"
  "Contracts ODCS|hub/apps/contracts/tests/test_odcs_*.py"
  "Datasets|hub/apps/datasets/tests/"
  "Marketplace|hub/apps/marketplace/tests/"
  "Compliance|hub/apps/compliance/tests/"
  "Governance|hub/apps/governance/tests/"
  "Data Quality|hub/apps/dq/tests/"
  "Files|hub/apps/files/tests/"
  "Scheduled|hub/apps/scheduled_export/tests/|hub/apps/scheduled_ingestion/tests/"
  "Orchestration|hub/apps/orchestration/tests/"
  "Jobs|hub/apps/jobs/tests/"
  "Billing|hub/apps/billing/tests/"
  "BaaS Developer|hub/apps/baas/tests/|hub/apps/developer/tests/"
  "GDPR|hub/apps/gdpr/tests/"
  "Notifications Webhooks|hub/apps/notifications/tests/|hub/apps/webhooks/tests/"
  "AI ML|hub/apps/ai/tests/|hub/apps/ml/tests/"
  "GraphQL|hub/apps/graphql/tests/|hub/apps/graphql_graphene/tests/"
  "Observability|hub/apps/observability/tests/"
  "Rate Limiting|hub/apps/rate_limiting/tests/"
  "Integrations Mesh|hub/apps/integrations/tests/|hub/apps/mesh/tests/"
  "Platform Users Social|hub/apps/platform/tests/|hub/apps/users/tests/|hub/apps/social/tests/"
  "Root Unit|tests/unit/"
)

# 12A.1.1 Unit tests — batched + parallel
echo "===== 12A.1.1 Unit tests (batched, parallel=${PYTEST_PARALLEL_WORKERS}) ====="
UNIT_START=$(date +%s)
UNIT_EXIT=0
mkdir -p "${REPORT_BASE}/unit/batches"
UNIT_JUNIT_PARTS=()

for i in "${!UNIT_BATCHES[@]}"; do
  batch_num=$((i + 1))
  IFS='|' read -ra PARTS <<< "${UNIT_BATCHES[$i]}"
  batch_name="${PARTS[0]}"
  batch_paths=("${PARTS[@]:1}")
  batch_log="${REPORT_BASE}/unit/batches/batch_${batch_num}.log"
  batch_junit="/tmp/junit_unit_batch_${batch_num}.xml"

  echo ""
  echo "--- Unit batch ${batch_num}/${#UNIT_BATCHES[@]}: ${batch_name} ---"
  ensure_api_service_running || { echo "[ERROR] ${API_SVC} unavailable; skipping remaining batches." >&2; break; }
  [[ $batch_num -eq 1 ]] && echo "[INFO] First batch: pytest collection may take 30s-2min for ~18k tests. Output will stream below."
  xdist_args=""
  [[ "${PYTEST_PARALLEL_WORKERS}" -gt 0 ]] && xdist_args="-n ${PYTEST_PARALLEL_WORKERS} --dist=loadscope"
  cov_args="--cov=hub --cov-append --cov-report=xml --cov-report=term-missing --cov-fail-under=0"
  [[ "$batch_name" == *"ODPS"* ]] || [[ "$batch_name" == *"ODCS"* ]] || [[ "$batch_name" == *"Files"* ]] || [[ "$batch_name" == *"Scheduled"* ]] && cov_args="--no-cov"

  paths_str="${batch_paths[*]}"
  # Skip DB check for batches 2+ (batch 1 already verified); saves ~2-5s per batch (see docs/TEST_SLOWNESS_INVESTIGATION.md)
  skip_db_check=""
  [[ $batch_num -gt 1 ]] && skip_db_check="SKIP_DB_CONNECTIVITY_CHECK=1"
  set +e
  # -o timeout_func_only=true: timeout applies only to test body, NOT django_db_setup (root cause fix for setup timeouts)
  $DC exec -T -e STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-}" "${API_SVC}" bash -c "cd /app && BATCH_TEST=1 DB_CONNECTIVITY_CHECK_RETRIES=6 DB_CONNECTIVITY_CHECK_INTERVAL=2 ${skip_db_check} LOG_LEVEL=WARNING PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest ${paths_str} -v -m 'not integration and not e2e and not real_scheduled_e2e' --reuse-db --timeout=300 -o timeout_func_only=true ${xdist_args} ${cov_args} --junit-xml=${batch_junit} --tb=short" 2>&1 | tee "$batch_log"
  batch_exit=${PIPESTATUS[0]}
  set -e

  $DC cp "${API_SVC}:${batch_junit}" "${REPORT_BASE}/unit/batches/batch_${batch_num}.xml" 2>/dev/null || true
  [[ -f "${REPORT_BASE}/unit/batches/batch_${batch_num}.xml" ]] && UNIT_JUNIT_PARTS+=("${REPORT_BASE}/unit/batches/batch_${batch_num}.xml")
  [[ $batch_exit -ne 0 ]] && UNIT_EXIT=$batch_exit || true
done

# Merge coverage and JUnit from last batch (cov-append accumulates; junit merge optional)
$DC cp "${API_SVC}":/app/coverage.xml "${REPORT_BASE}/unit/coverage.xml" 2>/dev/null || true
$DC cp "${API_SVC}":/app/htmlcov "${REPORT_BASE}/unit/" 2>/dev/null || true
if [[ ${#UNIT_JUNIT_PARTS[@]} -gt 0 ]]; then
  # Use first part as base; for full merge use scripts or pytest --junit-xml with last run
  cp "${UNIT_JUNIT_PARTS[-1]}" "${REPORT_BASE}/unit/junit.xml" 2>/dev/null || true
fi

UNIT_END=$(date +%s)
UNIT_DURATION=$((UNIT_END - UNIT_START))
echo "UNIT_EXIT=${UNIT_EXIT}" >> "${REPORT_BASE}/unit/unit.log"
echo "UNIT_DURATION=${UNIT_DURATION}" >> "${REPORT_BASE}/unit/unit.log"
echo "Unit phase: ${UNIT_DURATION}s, exit=${UNIT_EXIT}"

# 12A.1.2 Integration tests
echo "===== 12A.1.2 Integration tests (parallel=${PYTEST_PARALLEL_WORKERS}) ====="
ensure_api_service_running
echo "Starting integration pytest..."
INT_START=$(date +%s)
int_xdist=""
[[ "${PYTEST_PARALLEL_WORKERS}" -gt 0 ]] && int_xdist="-n ${PYTEST_PARALLEL_WORKERS} --dist=loadscope"
# -o timeout_func_only=true: timeout applies only to test body, NOT django_db_setup/migrations (root cause fix for setup timeouts)
PYTEST_DOCKER_COMPOSE_RUNTIME=1 $DC exec -T "${API_SVC}" bash -c "cd /app && LOG_LEVEL=WARNING PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest tests/integration/ -v --docker-compose-runtime --reuse-db --timeout=600 -o timeout_func_only=true ${int_xdist} --cov=hub --cov-append --cov-report=xml --cov-report=html --junit-xml=/tmp/junit_integration.xml --tb=short" \
  2>&1 | tee "${REPORT_BASE}/integration/integration.log" || true
INT_EXIT=${PIPESTATUS[0]}
INT_END=$(date +%s)
INT_DURATION=$((INT_END - INT_START))
echo "INTEGRATION_EXIT=${INT_EXIT}" >> "${REPORT_BASE}/integration/integration.log"
echo "INTEGRATION_DURATION=${INT_DURATION}" >> "${REPORT_BASE}/integration/integration.log"

$DC cp "${API_SVC}":/tmp/junit_integration.xml "${REPORT_BASE}/integration/junit.xml" 2>/dev/null || true
$DC cp "${API_SVC}":/app/coverage.xml "${REPORT_BASE}/integration/coverage.xml" 2>/dev/null || true

# 12A.1.3 E2E tests
echo "===== 12A.1.3 E2E tests ====="
echo "Starting E2E pytest (Django load may take 2-3 min)..."
E2E_START=$(date +%s)
# PYTHONUNBUFFERED=1 so output streams immediately
# Use --reuse-db to prevent database creation delays (root cause fix)
# Add --timeout=900 for E2E tests (15 minutes)
# -o timeout_func_only=true: timeout applies only to test body, NOT django_db_setup/migrations (root cause fix for setup timeouts)
# Pre-warm: run one minimal test to trigger django_db_setup before full run (ensures test DB exists from integration phase)
echo "[INFO] Pre-warming test DB for E2E (triggers django_db_setup if needed)..."
PYTEST_DOCKER_COMPOSE_RUNTIME=1 $DC exec -T "${API_SVC}" bash -c "cd /app && LOG_LEVEL=WARNING PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest tests/e2e/test_health_checks.py -v --docker-compose-runtime --reuse-db -o timeout_func_only=true -x -q --no-cov -k 'test_' 2>/dev/null" || true
echo "[INFO] Starting full E2E suite..."
PYTEST_DOCKER_COMPOSE_RUNTIME=1 $DC exec -T "${API_SVC}" bash -c "cd /app && LOG_LEVEL=WARNING PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest tests/e2e/ -v --docker-compose-runtime --reuse-db --timeout=900 -o timeout_func_only=true --cov=hub --cov-append --cov-report=xml --cov-report=html --junit-xml=/tmp/junit_e2e.xml --tb=short" \
  2>&1 | tee "${REPORT_BASE}/e2e/e2e.log" || true
E2E_EXIT=${PIPESTATUS[0]}
E2E_END=$(date +%s)
E2E_DURATION=$((E2E_END - E2E_START))
echo "E2E_EXIT=${E2E_EXIT}" >> "${REPORT_BASE}/e2e/e2e.log"
echo "E2E_DURATION=${E2E_DURATION}" >> "${REPORT_BASE}/e2e/e2e.log"

$DC cp "${API_SVC}":/tmp/junit_e2e.xml "${REPORT_BASE}/e2e/junit.xml" 2>/dev/null || true
$DC cp "${API_SVC}":/app/coverage.xml "${REPORT_BASE}/e2e/coverage.xml" 2>/dev/null || true

# 12A.1.3b UC/Journey/Persona E2E subset (Task 6.7.5)
echo "===== 12A.1.3b UC/Journey/Persona E2E tests ====="
echo "Starting UC/Journey/Persona pytest..."
UCP_START=$(date +%s)
# -o timeout_func_only=true: timeout applies only to test body, NOT django_db_setup (root cause fix)
PYTEST_DOCKER_COMPOSE_RUNTIME=1 $DC exec -T "${API_SVC}" bash -c "cd /app && LOG_LEVEL=WARNING PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest tests/e2e/ -v -m uc_journey_persona --reuse-db --timeout=900 -o timeout_func_only=true --junit-xml=/tmp/junit_uc_journey_persona.xml --tb=short" \
  2>&1 | tee "${REPORT_BASE}/uc_journey_persona/uc_journey_persona.log" || true
UCP_EXIT=${PIPESTATUS[0]}
UCP_END=$(date +%s)
UCP_DURATION=$((UCP_END - UCP_START))
echo "UC_JOURNEY_PERSONA_EXIT=${UCP_EXIT}" >> "${REPORT_BASE}/uc_journey_persona/uc_journey_persona.log"
echo "UC_JOURNEY_PERSONA_DURATION=${UCP_DURATION}" >> "${REPORT_BASE}/uc_journey_persona/uc_journey_persona.log"
$DC cp "${API_SVC}":/tmp/junit_uc_journey_persona.xml "${REPORT_BASE}/uc_journey_persona/junit.xml" 2>/dev/null || true

# 12A.1.4 Summary
SUMMARY="${REPORT_BASE}/phase_12a_1_summary.json"
cat > "$SUMMARY" << EOF
{
  "date": "${DATE}",
  "unit": { "exit_code": ${UNIT_EXIT}, "duration_seconds": ${UNIT_DURATION}, "artifacts": "${REPORT_BASE}/unit/" },
  "integration": { "exit_code": ${INT_EXIT}, "duration_seconds": ${INT_DURATION}, "artifacts": "${REPORT_BASE}/integration/" },
  "e2e": { "exit_code": ${E2E_EXIT}, "duration_seconds": ${E2E_DURATION}, "artifacts": "${REPORT_BASE}/e2e/" },
  "uc_journey_persona": { "exit_code": ${UCP_EXIT}, "duration_seconds": ${UCP_DURATION}, "artifacts": "${REPORT_BASE}/uc_journey_persona/" }
}
EOF
echo "Summary: $SUMMARY"
cat "$SUMMARY"
if [[ $UNIT_EXIT -ne 0 || $INT_EXIT -ne 0 || $E2E_EXIT -ne 0 || $UCP_EXIT -ne 0 ]]; then
  echo "===== Phase 12A.1 one or more backend suites failed (unit=${UNIT_EXIT} integration=${INT_EXIT} e2e=${E2E_EXIT} uc_journey_persona=${UCP_EXIT}); see ${SUMMARY} =====" >&2
  exit 1
fi
