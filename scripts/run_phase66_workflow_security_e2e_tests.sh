#!/bin/bash
#
# Run Phase 6.6 E2E workflow security + business rules tests (openspec/changes/workflows1/tasks.md).
#
# Usage:
#   ./scripts/run_phase66_workflow_security_e2e_tests.sh              # --keepdb (faster if DB exists)
#   ./scripts/run_phase66_workflow_security_e2e_tests.sh --no-keepdb  # fresh DB (first run or after DuplicateTable)
#   TEST_DB_SUFFIX=phase66e ./scripts/run_phase66_workflow_security_e2e_tests.sh --no-keepdb  # new DB name
#
# Requires: docker compose up (api-service healthy). Django at /app/hub in api-service.
# First run: use --no-keepdb so the test DB is created and migrated (can take several minutes).
# If you see "relation \"plugins\" already exists", drop the test DB or use a new suffix with --no-keepdb.
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

echo "Phase 6.6 workflow security E2E tests (TEST_DB_SUFFIX=${SUFFIX}, keepdb=${KEEPDB:-false})"
echo "Running in api-service at /app/hub..."
echo ""

docker compose exec api-service bash -c "cd /app/hub && TEST_DB_SUFFIX=${SUFFIX} python manage.py test tests.e2e.test_workflow_security_business_rules_e2e --verbosity=2 ${KEEPDB} --no-input"
