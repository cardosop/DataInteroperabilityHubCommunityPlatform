#!/usr/bin/env bash
# Run Phase 13 GDPR export/erasure tests
# Usage: ./scripts/run_phase13_tests.sh
# Requires: postgres-test, redis-cache-test, minio-test, migrate-test-db (or full stack up)
# Uses dedicated DB hub_test_test_phase13 so API can stay running (no deadlocks).
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

# Phase 13: GDPR export/erasure tests (view + service).
# View tests (TestCase): API request flow. Service tests (TransactionTestCase): business logic.
# TEST_DB_SUFFIX=phase13 uses hub_test_test_phase13 (isolated from API's hub_test_test_shared).
# Always use 'run' (not exec) so pytest gets a fresh container—avoids OOM when API is running.
# Override POSTGRES_DB=hub_test so settings compute test_db_name=hub_test_test_phase13
# (api-service-test defaults to hub_test_test_shared which would yield hub_test_test_shared_test_phase13)
docker compose -f "$COMPOSE_FILE" run --rm --no-deps -e POSTGRES_DB=hub_test api-service-test bash -c "
  cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=phase13 POSTGRES_DB=hub_test \
  python -m pytest hub/apps/gdpr/tests/test_gdpr_views.py hub/apps/gdpr/tests/test_gdpr_services.py \
  -v --tb=short --reuse-db --timeout=180
"
