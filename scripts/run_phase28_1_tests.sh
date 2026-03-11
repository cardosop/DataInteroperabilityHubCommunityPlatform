#!/usr/bin/env bash
# Run Phase 28.1 (Admin User Edit) tests
# Usage: ./scripts/run_phase28_1_tests.sh
# Requires: docker compose -f docker-compose.test.yml up -d (postgres-test, redis, etc.)
# Note: Stops api-service-test before running to avoid DB conflicts. For E2E, restart:
#   docker compose -f docker-compose.test.yml start api-service-test
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

echo "[Phase 28.1] Running Admin User Edit tests..."
# Stop api-service-test first to avoid DB conflicts (hub_test_test_shared in use) and deadlocks
docker compose -f "$COMPOSE_FILE" stop api-service-test 2>/dev/null || true
sleep 2
cmd="cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=shared \
  python -m pytest \
    hub/apps/users/tests/test_admin_user_edit.py \
    tests/integration/test_users_apis_comprehensive.py::TestAdminUserEditIntegration \
    tests/security/test_admin_user_edit_security.py \
    -v --tb=short --reuse-db --timeout=120 -p no:xdist"
docker compose -f "$COMPOSE_FILE" run --rm --no-deps api-service-test bash -c "$cmd"
echo "[Phase 28.1] Backend tests done."
