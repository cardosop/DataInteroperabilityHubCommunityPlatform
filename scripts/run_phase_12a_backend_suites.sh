#!/usr/bin/env bash
# Phase 12A.1 — Run backend test suites with artifact collection
# Per docs/TEST_EXECUTION_PLAN.md and openspec/changes/testreview1/tasks.md
# No mocks/stubs; root-cause fixes only.

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
mkdir -p "${REPORT_BASE}/unit" "${REPORT_BASE}/integration" "${REPORT_BASE}/e2e"

export DJANGO_SETTINGS_MODULE=hub.settings
export PYTHONPATH="${PROJECT_DIR}"

# 12A.1.1 Unit tests — same phase as CI (Gap #1, task 1.3.4): hub/apps/ + tests/unit/, exclude integration/e2e by marker
echo "===== 12A.1.1 Unit tests ====="
UNIT_START=$(date +%s)
# Unit phase = hub app tests + root tests/unit/; exclude integration/e2e so unit step stays fast
# Use --reuse-db to prevent database creation delays (root cause fix per TASK_27_5_HANGING_ISSUE_ANALYSIS.md)
# Add --timeout=300 to ensure tests timeout after 5 minutes (pytest-timeout plugin)
docker compose exec -T "${API_SVC}" bash -c "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest hub/apps/ tests/unit/ -v -m \"not integration and not e2e\" --reuse-db --timeout=300 --cov=hub --cov-report=html --cov-report=term-missing --cov-report=xml --cov-fail-under=0 --junit-xml=/tmp/junit_unit.xml --tb=short" \
  2>&1 | tee "${REPORT_BASE}/unit/unit.log" || true
UNIT_EXIT=$?
UNIT_END=$(date +%s)
UNIT_DURATION=$((UNIT_END - UNIT_START))
echo "UNIT_EXIT=${UNIT_EXIT}" >> "${REPORT_BASE}/unit/unit.log"
echo "UNIT_DURATION=${UNIT_DURATION}" >> "${REPORT_BASE}/unit/unit.log"

docker compose cp "${API_SVC}":/app/coverage.xml "${REPORT_BASE}/unit/coverage.xml" 2>/dev/null || true
docker compose cp "${API_SVC}":/app/htmlcov "${REPORT_BASE}/unit/" 2>/dev/null || true
docker compose cp "${API_SVC}":/tmp/junit_unit.xml "${REPORT_BASE}/unit/junit.xml" 2>/dev/null || true

# 12A.1.2 Integration tests
echo "===== 12A.1.2 Integration tests ====="
INT_START=$(date +%s)
# Use --reuse-db to prevent database creation delays (root cause fix)
# Add --timeout=600 for integration tests (10 minutes, longer than unit tests)
PYTEST_DOCKER_COMPOSE_RUNTIME=1 docker compose exec -T "${API_SVC}" bash -c "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest tests/integration/ -v --docker-compose-runtime --reuse-db --timeout=600 --cov=hub --cov-append --cov-report=xml --cov-report=html --junit-xml=/tmp/junit_integration.xml --tb=short" \
  2>&1 | tee "${REPORT_BASE}/integration/integration.log" || true
INT_EXIT=$?
INT_END=$(date +%s)
INT_DURATION=$((INT_END - INT_START))
echo "INTEGRATION_EXIT=${INT_EXIT}" >> "${REPORT_BASE}/integration/integration.log"
echo "INTEGRATION_DURATION=${INT_DURATION}" >> "${REPORT_BASE}/integration/integration.log"

docker compose cp "${API_SVC}":/tmp/junit_integration.xml "${REPORT_BASE}/integration/junit.xml" 2>/dev/null || true
docker compose cp "${API_SVC}":/app/coverage.xml "${REPORT_BASE}/integration/coverage.xml" 2>/dev/null || true

# 12A.1.3 E2E tests
echo "===== 12A.1.3 E2E tests ====="
E2E_START=$(date +%s)
# Use --reuse-db to prevent database creation delays (root cause fix)
# Add --timeout=900 for E2E tests (15 minutes, longer than integration tests)
PYTEST_DOCKER_COMPOSE_RUNTIME=1 docker compose exec -T "${API_SVC}" bash -c "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest tests/e2e/ -v --docker-compose-runtime --reuse-db --timeout=900 --cov=hub --cov-append --cov-report=xml --cov-report=html --junit-xml=/tmp/junit_e2e.xml --tb=short" \
  2>&1 | tee "${REPORT_BASE}/e2e/e2e.log" || true
E2E_EXIT=$?
E2E_END=$(date +%s)
E2E_DURATION=$((E2E_END - E2E_START))
echo "E2E_EXIT=${E2E_EXIT}" >> "${REPORT_BASE}/e2e/e2e.log"
echo "E2E_DURATION=${E2E_DURATION}" >> "${REPORT_BASE}/e2e/e2e.log"

docker compose cp "${API_SVC}":/tmp/junit_e2e.xml "${REPORT_BASE}/e2e/junit.xml" 2>/dev/null || true
docker compose cp "${API_SVC}":/app/coverage.xml "${REPORT_BASE}/e2e/coverage.xml" 2>/dev/null || true

# 12A.1.4 Summary
SUMMARY="${REPORT_BASE}/phase_12a_1_summary.json"
cat > "$SUMMARY" << EOF
{
  "date": "${DATE}",
  "unit": { "exit_code": ${UNIT_EXIT}, "duration_seconds": ${UNIT_DURATION}, "artifacts": "${REPORT_BASE}/unit/" },
  "integration": { "exit_code": ${INT_EXIT}, "duration_seconds": ${INT_DURATION}, "artifacts": "${REPORT_BASE}/integration/" },
  "e2e": { "exit_code": ${E2E_EXIT}, "duration_seconds": ${E2E_DURATION}, "artifacts": "${REPORT_BASE}/e2e/" }
}
EOF
echo "Summary: $SUMMARY"
cat "$SUMMARY"
