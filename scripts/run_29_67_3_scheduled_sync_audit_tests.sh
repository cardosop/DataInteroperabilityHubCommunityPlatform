#!/usr/bin/env bash
# Run 29.67.3 Scheduled sync audit tests (task useronboardfix)
# Usage: ./scripts/run_29_67_3_scheduled_sync_audit_tests.sh
# Requires: docker-compose.test.yml services (postgres-test, redis-*, api-service-test, migrate-test-db completed)
#
# If tests fail with DB/migration errors (DuplicateColumn, DuplicateDatabase, ObjectInUse):
#   ./scripts/clean-test-stack.sh --volumes
#   then up the stack again and rerun this script.
#
# Tests:
#   - test_schedule_sync_creates_audit_event
#   - test_unschedule_sync_creates_audit_event
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

echo "== 29.67.3 Scheduled sync audit tests =="
echo "Using TEST_DB_SUFFIX=shared, POSTGRES_DB=hub_test_test_shared"
echo ""

docker compose -f "$COMPOSE_FILE" run --rm --no-deps api-service-test bash -c "
  cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=shared \
  python -m pytest \
    hub/apps/integrations/tests/test_scheduled_sync.py::ScheduledSyncServiceUnitTest::test_schedule_sync_creates_audit_event \
    hub/apps/integrations/tests/test_scheduled_sync.py::ScheduledSyncServiceUnitTest::test_unschedule_sync_creates_audit_event \
    -v --tb=short --reuse-db --timeout=120
"
