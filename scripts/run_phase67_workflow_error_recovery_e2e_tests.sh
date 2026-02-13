#!/bin/bash
#
# Run Phase 6.7 E2E workflow error recovery and compensation tests (openspec/changes/workflows1/tasks.md).
#
# Reuses the same test DB as Phase 6.6 (suffix phase66) so migrations are NOT re-run. Use --keepdb (default).
#
# Usage:
#   ./scripts/run_phase67_workflow_error_recovery_e2e_tests.sh              # reuse existing DB (no migrations)
#   TEST_DB_SUFFIX=phase66 ./scripts/run_phase67_workflow_error_recovery_e2e_tests.sh  # same, explicit
#   ./scripts/run_phase67_workflow_error_recovery_e2e_tests.sh --no-keepdb  # only if you need a fresh DB
#
# Requires: docker compose up (api-service healthy). Django at /app/hub in api-service.
# The test DB (e.g. hub_test_phase66) must already exist and be migrated (e.g. from running phase 6.6 or other e2e tests).
#
set -e

# Reuse same suffix as phase 6.6 so we use the already-migrated test DB and never run migrations by default
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

echo "Phase 6.7 workflow error recovery & compensation E2E tests (TEST_DB_SUFFIX=${SUFFIX}, keepdb=${KEEPDB:-false}, no migrations)"
echo "Running in api-service at /app/hub..."
echo ""

# SKIP_TEST_MIGRATIONS=1: use custom runner so migrate is not run (reuse existing DB as-is)
docker compose exec api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 TEST_DB_SUFFIX=${SUFFIX} python manage.py test tests.e2e.test_workflow_error_recovery_compensation_e2e --verbosity=2 ${KEEPDB} --no-input"
