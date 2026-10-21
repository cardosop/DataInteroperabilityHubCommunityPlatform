#!/usr/bin/env bash
# Run Phase 1 Internal Worker API tests (run lifecycle, process-file, config, auth).
# Requires: docker compose with postgres, redis-cache, redis-queue, redis-events, redis-channels, minio, jaeger, mock-server.
# Usage:
#   ./scripts/run_internal_worker_api_tests.sh
#   ./scripts/run_internal_worker_api_tests.sh -v --tb=long
#
# Prefer running with api-service already up (so postgres is stable and on same network):
#   docker compose up -d postgres redis-cache redis-queue redis-events redis-channels minio jaeger mock-server
#   # Wait for postgres healthy, then:
#   docker compose up -d api-service
#   # Wait for api-service healthy, then run this script (it will exec into api-service) or:
#   docker compose exec api-service bash -c "cd /app && TESTING=1 python -m pytest hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py -v --tb=short --reuse-db"
#
# pytest.ini has timeout_func_only=true and timeout=300 so DB setup (migrations) is not timed out.

set -e
cd "$(dirname "$0")/.."
COMPOSE="${COMPOSE:-docker compose}"
EXTRA_PYTEST_ARGS=("$@")
PYTEST_OPTS=(hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py -v --tb=short --reuse-db)

echo "Checking for running api-service..."
if $COMPOSE ps api-service --status running -q 2>/dev/null | grep -q .; then
  echo "Running Internal Worker API tests via exec (api-service already up)..."
  $COMPOSE exec -T api-service bash -c "cd /app && TESTING=1 python -m pytest ${PYTEST_OPTS[*]} ${EXTRA_PYTEST_ARGS[*]}"
else
  echo "api-service not running. Bringing up postgres and dependencies..."
  $COMPOSE up -d postgres redis-cache redis-queue redis-events redis-channels minio jaeger mock-server 2>/dev/null || true
  echo "Waiting for postgres to be healthy (up to 120s)..."
  for i in $(seq 1 60); do
    if $COMPOSE exec -T postgres pg_isready -U "${POSTGRES_USER:-hub}" -d "${POSTGRES_DB:-hub}" 2>/dev/null; then
      echo "Postgres is ready."
      break
    fi
    if [ "$i" -eq 60 ]; then
      echo "Postgres did not become ready in time."
      exit 1
    fi
    sleep 2
  done
  echo "Running Internal Worker API tests in one-off container..."
  $COMPOSE run --rm -e TESTING=1 api-service bash -c "cd /app && python -m pytest ${PYTEST_OPTS[*]} ${EXTRA_PYTEST_ARGS[*]}"
fi
