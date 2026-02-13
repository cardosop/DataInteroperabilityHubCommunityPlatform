#!/bin/bash
#
# Run Phase 6.9 E2E workflow use case integration tests (openspec/changes/workflows1/tasks.md).
#
# Tests workflows in use cases: UC-AM-001, UC-CM-001, UC-MKT-001, Data Quality, Compliance.
#
# Reuses the same test DB as Phase 6.6/6.7/6.8 (suffix phase66). Use --keepdb (default).
#
# Usage:
#   ./scripts/run_phase69_workflow_use_case_e2e_tests.sh
#   ./scripts/run_phase69_workflow_use_case_e2e_tests.sh --no-keepdb
#
# Requires: docker compose up (api-service healthy). Test DB must be migrated.
#
# If you see relation "search_index" or "semantic_resources" does not exist in logs,
# recreate the test DB with full migrations: ./scripts/run_phase69_workflow_use_case_e2e_tests.sh --no-keepdb
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

if ! command -v docker &> /dev/null; then
  echo "Docker is not available."
  exit 1
fi

if ! docker compose ps 2>/dev/null | grep -q "api-service.*Up"; then
  echo "api-service does not appear to be running. Start with: docker compose up -d"
  exit 1
fi

echo "Phase 6.9 workflow use case integration E2E tests (TEST_DB_SUFFIX=${SUFFIX}, keepdb=${KEEPDB:-false})"
echo "Running in api-service at /app/hub..."
echo ""

docker compose exec api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 TEST_DB_SUFFIX=${SUFFIX} python manage.py test tests.e2e.test_workflow_use_case_integration_e2e --verbosity=2 ${KEEPDB} --no-input"
