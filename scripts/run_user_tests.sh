#!/usr/bin/env bash
# Run Phase 10 user/admin tests (PUT /users/{id}/, permissions, role changes, audit)
# Usage: ./scripts/run_user_tests.sh
# Requires: postgres-test, redis-cache-test, migrate-test-db completed (hub_test_test_shared)
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml
docker compose -f "$COMPOSE_FILE" run --rm --no-deps api-service-test bash -c "
  cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=shared \
  python -m pytest hub/apps/users/tests/ -v --tb=short --reuse-db --timeout=120
"
