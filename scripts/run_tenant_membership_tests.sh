#!/usr/bin/env bash
# Run Phase 29.65.2 UserTenantMembership tests
# Usage: ./scripts/run_tenant_membership_tests.sh
# Requires: postgres-test, redis-cache-test, minio-test, migrate-test-db (or full stack up)
# Stops api-service-test to avoid DB contention (like run_phase28_2_tests.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

# Stop api-service-test to avoid DB conflicts and deadlocks (runserver holds connections).
# With api running, pytest can hang on django_db_setup or hit DuplicateDatabase/DROP errors.
docker compose -f "$COMPOSE_FILE" stop api-service-test 2>/dev/null || true
sleep 2

# Ensure phase13 DB exists and is migrated (used by pytest with TEST_DB_SUFFIX=phase13).
docker compose -f "$COMPOSE_FILE" exec -T postgres-test psql -U hub_test -d postgres -c "CREATE DATABASE hub_test_test_phase13" 2>/dev/null || true
docker compose -f "$COMPOSE_FILE" run --rm --no-deps -e POSTGRES_DB=hub_test_test_phase13 api-service-test bash -c "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python hub/manage.py migrate --noinput" 2>/dev/null || true

# Phase 29.65.2: UserTenantMembership model + service + migration tests.
# Phase 29.65.4: Invite flow (invite existing user adds membership; invite new user creates user+membership).
# TEST_DB_SUFFIX=phase13 uses hub_test_test_phase13 (isolated from shared).
docker compose -f "$COMPOSE_FILE" run --rm --no-deps -e POSTGRES_DB=hub_test api-service-test bash -c "
  cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=phase13 POSTGRES_DB=hub_test \
  python -m pytest hub/apps/users/tests/test_user_tenant_membership.py hub/apps/users/tests/test_migration_populate_user_tenant_memberships.py hub/apps/users/tests/test_invite_flow.py \
  -v --tb=short --reuse-db --timeout=180
"
