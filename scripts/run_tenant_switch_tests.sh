#!/usr/bin/env bash
# Run Phase 29.65.6 tenant switch tests (unit, integration, security)
# Usage: ./scripts/run_tenant_switch_tests.sh
# Requires: postgres-test, redis-cache-test, minio-test, migrate-test-db (or full stack up)
# Stops api-service-test to avoid DB contention.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

# Stop api-service-test to avoid DB conflicts and deadlocks
docker compose -f "$COMPOSE_FILE" stop api-service-test 2>/dev/null || true
sleep 2

# Ensure phase13 DB exists and is migrated
docker compose -f "$COMPOSE_FILE" exec -T postgres-test psql -U hub_test -d postgres -c "CREATE DATABASE hub_test_test_phase13" 2>/dev/null || true
docker compose -f "$COMPOSE_FILE" run --rm --no-deps -e POSTGRES_DB=hub_test_test_phase13 api-service-test bash -c "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python hub/manage.py migrate --noinput" 2>/dev/null || true

# Run tenant switch tests: unit (membership, API, middleware), integration, security
docker compose -f "$COMPOSE_FILE" run --rm --no-deps -e POSTGRES_DB=hub_test api-service-test bash -c "
  cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=phase13 POSTGRES_DB=hub_test \
  python -m pytest \
    hub/apps/users/tests/test_user_tenant_membership.py \
    hub/apps/auth/tests/test_tenant_switch.py \
    tests/integration/test_tenant_switch_integration.py \
    tests/security/test_tenant_switch_security.py \
  -v --tb=short --reuse-db --timeout=180
"
