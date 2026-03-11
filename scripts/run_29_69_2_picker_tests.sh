#!/bin/bash
# Run 29.69.2 picker/list API tests (tasks 29.69.2.3, 29.69.2.4)
# Requires: docker compose -f docker-compose.test.yml up -d (or at least postgres-test, redis-cache-test, etc.)
#
# Usage:
#   ./scripts/run_29_69_2_picker_tests.sh
#
# Or with explicit compose:
#   COMPOSE_FILE=docker-compose.test.yml ./scripts/run_29_69_2_picker_tests.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
API_SVC="api-service-test"

echo "=========================================="
echo "29.69.2 Picker/List API Tests"
echo "=========================================="
echo "Compose: $COMPOSE_FILE"
echo ""

# Run tests via docker compose run (creates fresh container with correct env)
docker compose -f "$COMPOSE_FILE" run --rm --no-deps \
  -e POSTGRES_DB=hub_test_test_shared \
  -e TEST_DB_SUFFIX=shared \
  "$API_SVC" bash -c "
    cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest \
    hub/apps/datasets/tests/test_views.py \
    hub/apps/files/tests/test_views.py \
    tests/security/test_idor_datasets.py \
    -v --tb=short --reuse-db -p no:xdist \
    -k 'test_list_datasets_filtering_by_invalid_asset_id or test_list_datasets_filtering_by_format or test_list_datasets_search_by_file_name or test_list_datasets_ordering or test_list_datasets_filtering_by_asset_id or test_list_files_search_by_name or test_list_files_ordering or test_dataset_list_asset_id_filter_tenant_isolation'
  "
