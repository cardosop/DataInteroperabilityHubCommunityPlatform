#!/usr/bin/env bash
# Run 29.67.2 Platform – Erasure actor fix tests
# Usage: ./scripts/run_erasure_actor_tests.sh
# Requires: docker compose -f docker-compose.test.yml up -d (postgres-test, redis, minio, etc.)
# Stops api-service-test first to avoid DB conflicts (like run_phase28_1_tests.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

# Ensure postgres-test and deps are up (DB must already be migrated; run full stack once if needed)
docker compose -f "$COMPOSE_FILE" up -d postgres-test redis-cache-test minio-test 2>/dev/null || true

# Stop api-service-test to avoid DB conflicts (runserver holds connections)
docker compose -f "$COMPOSE_FILE" stop api-service-test 2>/dev/null || true
sleep 2

# Run tests (run container joins hub-test-net)
docker compose -f "$COMPOSE_FILE" run --rm --no-deps api-service-test bash -c "
  cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=shared \
  python -m pytest \
    hub/apps/gdpr/tests/test_gdpr_services.py::ErasureServiceTest::test_create_request_success \
    hub/apps/gdpr/tests/test_gdpr_services.py::ErasureServiceTest::test_create_request_creates_audit_event \
    hub/apps/gdpr/tests/test_gdpr_services.py::ErasureServiceTest::test_create_request_platform_admin_actor_in_audit \
    hub/apps/platform/tests/test_views.py::TestPlatformUserViewSetPermissions::test_platform_request_erasure_audit_actor_is_platform_admin \
    tests/integration/test_platform_apis_integration.py::TestPlatformAPIsIntegration::test_platform_request_erasure_returns_201_and_audit_actor_is_platform_admin \
  -v --tb=short --reuse-db --timeout=120 -p no:xdist
"
