#!/usr/bin/env bash
# Run Phase 20 + Phase 21 virtualization real source integration tests.
# Ensures migrations are applied to hub_test_test_shared before running tests.
#
# Prerequisites: docker-compose.test.yml stack up (postgres-test, api-service-test, etc.)
# Usage: ./scripts/run_virtualization_real_source_tests.sh
#
# If tests fail with "relation X does not exist" or "column Y does not exist":
#   ./scripts/clean-test-stack.sh --volumes
#   docker compose -f docker-compose.test.yml up -d
#   # Wait ~2-5 min for migrate-test-db and api-service-test to be healthy
#   ./scripts/run_virtualization_real_source_tests.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
[[ -f .env.test ]] && ENV_ARGS="--env-file .env.test" || ENV_ARGS=""

echo "== Ensuring test stack is up..."
docker compose -f "$COMPOSE_FILE" $ENV_ARGS up -d postgres-test redis-cache-test redis-queue-test redis-events-test redis-channels-test fuseki-test semantic-service-test api-service-test 2>/dev/null || true

echo "== Waiting for api-service-test to be healthy..."
for i in 1 2 3 4 5 6 7 8 9 10; do
  if docker compose -f "$COMPOSE_FILE" ps -q api-service-test 2>/dev/null | grep -q .; then
    health=$(docker inspect -f '{{.State.Health.Status}}' hub-test-api 2>/dev/null || echo "unknown")
    if [[ "$health" == "healthy" ]]; then
      echo "  api-service-test is healthy."
      break
    fi
  fi
  sleep 10
  echo "  Waiting... ($i)"

done

echo "== Running migrations (migrate-test-db)..."
docker compose -f "$COMPOSE_FILE" $ENV_ARGS run --rm migrate-test-db 2>&1 | tail -30 || true

echo "== Running Phase 20 + Phase 21 virtualization real source tests..."
docker compose -f "$COMPOSE_FILE" $ENV_ARGS exec api-service-test \
  pytest hub/apps/virtualization/tests/ -v -m "integration and real_virtualization_e2e" --reuse-db --no-cov
