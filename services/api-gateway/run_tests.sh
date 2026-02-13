#!/bin/bash
# Run API Gateway tests in Docker Compose.
# Uses same DB credentials as the stack (from .env or docker-compose defaults).
# Phase 7: routing and gateway-proxy tests require api-service up for real HTTP.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_DIR"

echo "=========================================="
echo "API Gateway Test Runner"
echo "=========================================="
echo ""

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

# Use project .env so test run gets same Postgres credentials as the running stack.
# Unset host POSTGRES_* so --env-file .env wins (host env would override otherwise).
unset POSTGRES_PASSWORD POSTGRES_USER POSTGRES_DB POSTGRES_HOST POSTGRES_PORT 2>/dev/null || true
COMPOSE_CMD=(docker compose)
if [[ -f .env ]]; then
  COMPOSE_CMD=(docker compose --env-file .env)
  echo "Using .env for Postgres/Redis credentials (same as stack)."
fi

# Start required services: postgres, redis, api-service (for DB migrations and proxy test), api-gateway
if ! "${COMPOSE_CMD[@]}" ps 2>/dev/null | grep -q "Up"; then
    echo "⚠️  Docker services don't appear to be running"
    echo "   Starting required services (postgres, redis-cache, api-service, api-gateway)..."
    "${COMPOSE_CMD[@]}" up -d postgres redis-cache api-service api-gateway
    echo "   Waiting for services to be ready..."
    sleep 15
fi

# Apply Django migrations so DB schema is current (e.g. APIKey.rate_limit_per_hour).
# Use api-service (has full hub deps); skip if not running.
echo "Applying migrations..."
if "${COMPOSE_CMD[@]}" ps api-service 2>/dev/null | grep -q Up; then
  "${COMPOSE_CMD[@]}" exec -T api-service python hub/manage.py migrate --noinput 2>/dev/null || true
fi

echo "Running API Gateway tests..."
echo ""

# Inherit DB/Redis env from compose (same POSTGRES_PASSWORD as rest of stack).
# If you see "password authentication failed", ensure .env POSTGRES_PASSWORD matches the running postgres.
# USE_PRODUCTION_DB_FOR_SDK_TESTS=1 uses hub DB so no test DB creation needed.
# Phase 7: test_routing.py + TestGatewayProxiesToApiService (requires api-service up).
# Phase 8: TestHealthUrlContract + TestAggregateHealthWithRealBackend (health standardization).
# Run Phase 8 only: ./run_tests.sh phase8  (or pass test paths as usual, e.g. path/to/test.py).
PYTEST_ARGS=(services/api-gateway/tests/ -v --tb=short)
if [[ "${1:-}" == "phase8" ]]; then
  PYTEST_ARGS=(
    services/api-gateway/tests/test_routing.py
    services/api-gateway/tests/test_integration.py::TestAggregateHealthWithRealBackend
    -v --tb=short
  )
  shift
fi
"${COMPOSE_CMD[@]}" run --rm --no-deps \
  -e USE_PRODUCTION_DB_FOR_SDK_TESTS=1 \
  api-gateway python -m pytest "${PYTEST_ARGS[@]}" "$@"

echo ""
echo "✅ Tests completed!"
