#!/bin/bash
#
# Run Phase 18.7 REST–business-rules alignment tests (openspec/changes/workflows1/tasks.md).
#
# Usage:
#   ./scripts/run_phase18_rest_business_rules_tests.sh              # use TEST_DB_SUFFIX=phase18, --keepdb
#   ./scripts/run_phase18_rest_business_rules_tests.sh --no-keepdb   # fresh DB (first run or after DuplicateTable)
#   TEST_DB_SUFFIX=phase18e ./scripts/run_phase18_rest_business_rules_tests.sh --no-keepdb  # new DB name
#
# Requires: docker compose up (api-service healthy). Django lives in api-service at /app/hub.
# First run: use --no-keepdb so the test DB is created and migrated (~5–10 min).
# If you see "relation \"plugins\" already exists", drop the test DB or use a new suffix with --no-keepdb.
#
set -e

SUFFIX="${TEST_DB_SUFFIX:-phase18}"
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

echo "Phase 18.7 alignment tests (TEST_DB_SUFFIX=${SUFFIX}, keepdb=${KEEPDB:-false})"
echo "Running in api-service at /app/hub..."
echo ""

docker compose exec api-service bash -c "cd /app/hub && TEST_DB_SUFFIX=${SUFFIX} python manage.py test \
  tests.integration.test_rest_business_rules_alignment.TestGovernanceRestBusinessRulesAlignment \
  tests.integration.test_rest_business_rules_alignment.TestComplianceRestBusinessRulesAlignment \
  tests.integration.test_rest_business_rules_alignment.TestMeshRestBusinessRulesAlignment \
  tests.integration.test_rest_business_rules_alignment.TestDQRestBusinessRulesAlignment \
  tests.integration.test_rest_business_rules_alignment.TestVirtualizationRestBusinessRulesAlignment \
  tests.integration.test_rest_business_rules_alignment.TestScheduledIngestionRestBusinessRulesAlignment \
  tests.integration.test_rest_business_rules_alignment.TestIntegrationsRestBusinessRulesAlignment \
  tests.integration.test_rest_business_rules_alignment.TestSocialRestBusinessRulesAlignment \
  --verbosity=2 ${KEEPDB} --no-input"
