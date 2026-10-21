#!/usr/bin/env bash
# Run Phase 25 ODBC Connector tests (tasks.md 28.4; Phase 25–26).
#
# Prerequisites: docker-compose.test.yml stack up with api-service-test healthy.
# Usage: ./scripts/run_phase25_odbc_tests.sh
#
# If test_odbc_execute_against_hub_postgresql is skipped: rebuild api-service-test
# (Dockerfile has unixodbc, odbc-postgresql; requirements.txt has pyodbc), then:
#   docker compose -f docker-compose.test.yml --env-file .env.test build api-service-test
#   docker compose -f docker-compose.test.yml --env-file .env.test up -d api-service-test --force-recreate
#
# If tests hang: ensure no other pytest processes; run migrations first:
#   docker compose -f docker-compose.test.yml --env-file .env.test run --rm migrate-test-db

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
[[ -f .env.test ]] && ENV_ARGS="--env-file .env.test" || ENV_ARGS=""

echo "== Ensuring test stack is up..."
docker compose -f "$COMPOSE_FILE" $ENV_ARGS up -d postgres-test redis-cache-test api-service-test 2>/dev/null || true

echo "== Waiting for api-service-test to be healthy..."
for i in 1 2 3 4 5 6 7 8 9 10; do
  health=$(docker inspect -f '{{.State.Health.Status}}' hub-test-api 2>/dev/null || echo "unknown")
  if [[ "$health" == "healthy" ]]; then
    echo "  api-service-test is healthy."
    break
  fi
  sleep 5
  echo "  Waiting... ($i)"
done

echo "== Running migrations (migrate-test-db)..."
docker compose -f "$COMPOSE_FILE" $ENV_ARGS run --rm migrate-test-db 2>&1 | tail -15 || true

echo "== Running Phase 25 ODBC tests..."
docker compose -f "$COMPOSE_FILE" $ENV_ARGS exec -T api-service-test bash -c \
  "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest \
  hub/apps/virtualization/tests/test_business_rules.py \
  hub/apps/virtualization/tests/test_source_config_utils.py \
  hub/apps/virtualization/tests/test_serializers.py \
  hub/apps/virtualization/tests/test_services.py \
  hub/apps/virtualization/tests/test_real_source_integration.py \
  -v -k 'odbc or mask or credential_masking or VirtualizationServiceODBCTest' \
  --reuse-db --tb=short"
