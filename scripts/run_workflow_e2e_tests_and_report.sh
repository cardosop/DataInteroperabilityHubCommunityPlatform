#!/bin/bash
#
# Run workflow E2E tests (Phase 6.10) and generate coverage report.
#
# - Runs all tests marked with workflow_e2e (tests/e2e/test_workflow_*.py)
# - Generates workflow_coverage_report.md and workflow_coverage_report.json
#
# Usage:
#   ./scripts/run_workflow_e2e_tests_and_report.sh
#   ./scripts/run_workflow_e2e_tests_and_report.sh --no-keepdb
#
# With Docker Compose (api-service up):
#   Uses same test DB as Phase 6.6–6.9 (TEST_DB_SUFFIX=phase66, --keepdb by default).
#
# Without Docker (local pytest):
#   pytest tests/e2e/ -m workflow_e2e -v --tb=short
#   python3 scripts/workflow_e2e_coverage_report.py
#
set -e

SUFFIX="${TEST_DB_SUFFIX:-phase66}"
KEEPDB="--keepdb"
for arg in "$@"; do
  case "$arg" in
    --no-keepdb) KEEPDB=""; shift ;;
    --keepdb)    KEEPDB="--keepdb"; shift ;;
  esac
done

if command -v docker &> /dev/null && docker compose ps 2>/dev/null | grep -q "api-service.*Up"; then
  echo "Running workflow E2E tests in api-service (TEST_DB_SUFFIX=${SUFFIX})..."
  docker compose exec api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 TEST_DB_SUFFIX=${SUFFIX} python -m pytest tests/e2e/ -m workflow_e2e -v --tb=short ${KEEPDB} --no-input -p no:warnings"
  echo "Generating workflow E2E coverage report..."
  docker compose exec api-service bash -c "cd /app/hub && python3 scripts/workflow_e2e_coverage_report.py"
  echo "Done. Reports are inside the container at /app/hub/tests/e2e/workflow_coverage_report.*"
else
  echo "Running workflow E2E tests locally (pytest -m workflow_e2e)..."
  pytest tests/e2e/ -m workflow_e2e -v --tb=short -p no:warnings
  echo "Generating workflow E2E coverage report..."
  python3 scripts/workflow_e2e_coverage_report.py
  echo "Done. Reports: tests/e2e/workflow_coverage_report.md, workflow_coverage_report.json"
fi
