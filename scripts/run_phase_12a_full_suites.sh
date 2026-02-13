#!/usr/bin/env bash
# Phase 12A full — Run backend (12A.1), frontend (12A.2), security/performance/concurrency/regression (12A.3)
# Per docs/TEST_EXECUTION_PLAN.md and openspec/changes/testreview1/tasks.md, gapfix1 Phase 7.2.4.
# Invokes run_phase_12a_backend_suites.sh then frontend and other suites; aggregates evidence under test_reports_comprehensive/{date}/.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Same env as batched runs (Phase 4.1): default to test compose so full suite runs against same stack
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
export COMPOSE_FILE

# API service name: when using docker-compose.test.yml the service is api-service-test (see docs/TEST_EXECUTION_PLAN.md)
if [[ -n "${API_SERVICE_NAME:-}" ]]; then
  API_SVC="${API_SERVICE_NAME}"
elif [[ "${COMPOSE_FILE:-}" == *"docker-compose.test"* ]]; then
  API_SVC="api-service-test"
else
  API_SVC="api-service"
fi

DATE="${DATE:-$(date +%Y-%m-%d)}"
REPORT_BASE="test_reports_comprehensive/${DATE}"
mkdir -p "${REPORT_BASE}/unit" "${REPORT_BASE}/integration" "${REPORT_BASE}/e2e" \
  "${REPORT_BASE}/smoke" "${REPORT_BASE}/security" "${REPORT_BASE}/performance" "${REPORT_BASE}/concurrency" "${REPORT_BASE}/regression" \
  "${REPORT_BASE}/frontend-unit" "${REPORT_BASE}/frontend-e2e"

# 12A.1 Backend (unit, integration, E2E)
echo "===== Phase 12A.1 Backend suites ====="
"${SCRIPT_DIR}/run_phase_12a_backend_suites.sh" || true

# 12A.1.5 Smoke (Phase 4.1b): after backend, API and services are up; artifacts under test_reports_comprehensive/{DATE}/smoke/
echo "===== Phase 12A.1.5 Smoke tests ====="
SMOKE_DIR="${REPORT_BASE}/smoke"
SMOKE_START=$(date +%s)
# Align with docker-compose.test.yml: API on 8001 (API_TEST_PORT); override if needed
export API_BASE_URL="${API_BASE_URL:-http://localhost:8001}"
( PYTHONPATH="${PROJECT_DIR}" DJANGO_SETTINGS_MODULE=hub.settings python3 -m pytest tests/smoke/ -v --tb=short --junit-xml="${SMOKE_DIR}/junit.xml" 2>&1 ) | tee "${SMOKE_DIR}/smoke.log" || true
SMOKE_EXIT=${PIPESTATUS[0]}
SMOKE_END=$(date +%s)
echo "SMOKE_EXIT=${SMOKE_EXIT}" >> "${SMOKE_DIR}/smoke.log"
echo "SMOKE_DURATION=$((SMOKE_END - SMOKE_START))" >> "${SMOKE_DIR}/smoke.log"
if [[ $SMOKE_EXIT -ne 0 ]]; then
  echo "===== Smoke tests failed (exit ${SMOKE_EXIT}); see ${SMOKE_DIR}/smoke.log ====="
  exit 1
fi

# 12A.2 Frontend (unit, E2E) — run from host if frontend exists
# Use npm run test:run so Vitest exits after one run (no watch); npm test can stay in watch when TTY.
if [[ -d "${PROJECT_DIR}/frontend" ]]; then
  echo "===== Phase 12A.2.1 Frontend unit ====="
  FU_START=$(date +%s)
  (cd frontend && npm run test:run 2>&1) | tee "${REPORT_BASE}/frontend-unit/frontend-unit.log" || true
  FU_EXIT=${PIPESTATUS[0]}
  FU_END=$(date +%s)
  echo "FRONTEND_UNIT_EXIT=${FU_EXIT}" >> "${REPORT_BASE}/frontend-unit/frontend-unit.log"
  echo "FRONTEND_UNIT_DURATION=$((FU_END - FU_START))" >> "${REPORT_BASE}/frontend-unit/frontend-unit.log"

  echo "===== Phase 12A.2.2 Frontend E2E ====="
  FE_START=$(date +%s)
  (cd frontend && npm run test:e2e 2>&1) | tee "${REPORT_BASE}/frontend-e2e/frontend-e2e.log" || true
  FE_EXIT=${PIPESTATUS[0]}
  FE_END=$(date +%s)
  echo "FRONTEND_E2E_EXIT=${FE_EXIT}" >> "${REPORT_BASE}/frontend-e2e/frontend-e2e.log"
  echo "FRONTEND_E2E_DURATION=$((FE_END - FE_START))" >> "${REPORT_BASE}/frontend-e2e/frontend-e2e.log"
else
  echo "===== No frontend/ dir; skipping 12A.2 ====="
  FU_EXIT=0
  FE_EXIT=0
fi

# 12A.3 Security, performance, concurrency, regression — run in container if available
# Artifacts under test_reports_comprehensive/{date}/security|performance|concurrency|regression/ (JUnit XML, logs).
# Exit codes recorded in phase_12a_3_summary.json; script exits 1 if any suite failed (no masking of failures).
run_pytest_suite() {
  local name=$1
  local path=$2
  local dir="${REPORT_BASE}/${name}"
  mkdir -p "$dir"
  echo "===== Phase 12A.3 ${name} ====="
  local start=$(date +%s)
  # Use --reuse-db to prevent database creation delays (root cause fix)
  # Add --timeout=600 for security/performance/concurrency/regression tests (10 minutes)
  ( docker compose exec -T "${API_SVC}" bash -c "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest ${path} -v --reuse-db --timeout=600 --junit-xml=/tmp/junit_${name}.xml --tb=short" ) 2>&1 | tee "${dir}/${name}.log"
  local exit_code=${PIPESTATUS[0]}
  local end=$(date +%s)
  echo "${name^^}_EXIT=${exit_code}" >> "${dir}/${name}.log"
  echo "${name^^}_DURATION=$((end - start))" >> "${dir}/${name}.log"
  docker compose cp "${API_SVC}:/tmp/junit_${name}.xml" "${dir}/junit.xml" 2>/dev/null || true
  return $exit_code
}

SEC_EXIT=0
PERF_EXIT=0
CONC_EXIT=0
REG_EXIT=0
if docker compose exec -T "${API_SVC}" true 2>/dev/null; then
  run_pytest_suite security "tests/security/" || SEC_EXIT=$?
  run_pytest_suite performance "tests/performance/" || PERF_EXIT=$?
  run_pytest_suite concurrency "tests/concurrency/" || CONC_EXIT=$?
  run_pytest_suite regression "tests/regression/" || REG_EXIT=$?
  # Write 12A.3 summary and exit 1 if any suite failed (no masking)
  cat > "${REPORT_BASE}/phase_12a_3_summary.json" << EOF
{
  "date": "${DATE}",
  "security": { "exit_code": ${SEC_EXIT}, "artifacts": "${REPORT_BASE}/security/" },
  "performance": { "exit_code": ${PERF_EXIT}, "artifacts": "${REPORT_BASE}/performance/" },
  "concurrency": { "exit_code": ${CONC_EXIT}, "artifacts": "${REPORT_BASE}/concurrency/" },
  "regression": { "exit_code": ${REG_EXIT}, "artifacts": "${REPORT_BASE}/regression/" }
}
EOF
  if [[ $SEC_EXIT -ne 0 || $PERF_EXIT -ne 0 || $CONC_EXIT -ne 0 || $REG_EXIT -ne 0 ]]; then
    echo "===== Phase 12A.3 one or more suites failed (security=${SEC_EXIT} performance=${PERF_EXIT} concurrency=${CONC_EXIT} regression=${REG_EXIT}); see ${REPORT_BASE}/phase_12a_3_summary.json ====="
    exit 1
  fi
else
  echo "===== ${API_SVC} not running; skipping 12A.3 (security, performance, concurrency, regression) ====="
  cat > "${REPORT_BASE}/phase_12a_3_summary.json" << EOF
{ "date": "${DATE}", "skipped": true, "reason": "${API_SVC} not running" }
EOF
fi

# Summary
echo "===== Phase 12A full complete ====="
echo "Evidence: ${REPORT_BASE}"
echo "Backend summary: ${REPORT_BASE}/phase_12a_1_summary.json (if present)"
echo "12A.3 summary (security/performance/concurrency/regression): ${REPORT_BASE}/phase_12a_3_summary.json (if present)"
echo "Run test summary report: ./scripts/generate_test_summary_report.sh ${DATE}"
