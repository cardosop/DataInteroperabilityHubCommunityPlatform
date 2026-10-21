#!/usr/bin/env bash
# Run 29.67.1 MarketplaceMapping destroy tests (task useronboardfix)
# Usage: ./scripts/run_29_67_1_mapping_delete_tests.sh
# Requires: docker-compose.test.yml services (postgres-test, redis-*, api-service-test, migrate-test-db completed)
#
# If tests fail with DB/migration errors (DuplicateColumn, DuplicateDatabase, ObjectInUse):
#   ./scripts/clean-test-stack.sh --volumes
#   then up the stack again and rerun this script.
#
# Tests:
#   - test_delete_mapping_success, test_delete_mapping_not_found, test_delete_mapping_requires_write_permission
#   - test_delete_mapping_error_handling
#   - test_delete_mapping_integration, test_delete_mapping_publishes_marketplace_event
#   - test_api_mapping_delete_emits_audit_event
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

echo "== 29.67.1 MarketplaceMapping destroy tests =="
echo "Using TEST_DB_SUFFIX=shared, POSTGRES_DB=hub_test_test_shared"
echo "Ensure migrate-test-db has completed (hub_test_test_shared migrated)."
echo ""

docker compose -f "$COMPOSE_FILE" run --rm --no-deps api-service-test bash -c "
  cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=shared \
  python -m pytest \
    hub/apps/integrations/tests/test_mapping_views.py \
    hub/apps/integrations/tests/test_services_integration.py \
    hub/apps/integrations/tests/integration/test_marketplace_framework.py \
    -k 'delete_mapping or test_api_mapping_delete' \
    -v --tb=short --reuse-db --timeout=120
"
