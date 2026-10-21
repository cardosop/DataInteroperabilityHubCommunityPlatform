#!/usr/bin/env bash
# Run Phase 9 billing tests (subscription fetch, permissions, limits)
# Usage: ./scripts/run_billing_tests.sh
# Requires: postgres-test, redis-cache-test, migrate-test-db completed (hub_test_test_shared)
# Uses: docker compose run --no-deps (avoids full stack; needs postgres/redis on hub-test-net)
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml
docker compose -f "$COMPOSE_FILE" run --rm --no-deps api-service-test bash -c "
  cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=shared \
  python -m pytest hub/apps/billing/tests/test_views.py hub/apps/billing/tests/test_serializers.py \
  -v --tb=short --reuse-db --timeout=120
"
