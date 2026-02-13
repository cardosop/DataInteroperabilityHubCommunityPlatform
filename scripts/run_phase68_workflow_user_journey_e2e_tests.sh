#!/bin/bash
#
# Run Phase 6.8 E2E workflow user journey integration tests (openspec/changes/workflows1/tasks.md).
#
# Tests workflows in user journeys: DPO (DPO-001, DPO-002, DPO-015), DE (DE-001, DE-014),
# Compliance Officer, Data Consumer, Data Mesh Domain Owner, Data Quality.
#
# Reuses the same test DB as Phase 6.6/6.7 (suffix phase66) so migrations are NOT re-run. Use --keepdb (default).
#
# Usage:
#   ./scripts/run_phase68_workflow_user_journey_e2e_tests.sh
#   TEST_DB_SUFFIX=phase66 ./scripts/run_phase68_workflow_user_journey_e2e_tests.sh
#   ./scripts/run_phase68_workflow_user_journey_e2e_tests.sh --no-keepdb
#
# Requires: docker compose up (api-service healthy). Test DB must be migrated (e.g. from phase 6.6).
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

echo "Phase 6.8 workflow user journey integration E2E tests (TEST_DB_SUFFIX=${SUFFIX}, keepdb=${KEEPDB:-false})"
echo "Running in api-service at /app/hub..."
echo ""

docker compose exec api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 TEST_DB_SUFFIX=${SUFFIX} python manage.py test tests.e2e.test_workflow_user_journey_integration_e2e --verbosity=2 ${KEEPDB} --no-input"
