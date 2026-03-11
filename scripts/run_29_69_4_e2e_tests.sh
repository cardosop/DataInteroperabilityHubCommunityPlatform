#!/usr/bin/env bash
# Run E2E tests for tasks 29.69.4 (ODPS Upload & Asset Detail pickers).
# Requires API on 8000 or 8001. Uses port overrides to avoid conflicts with main compose.
#
# Usage:
#   ./scripts/run_29_69_4_e2e_tests.sh
#   E2E_SKIP_API_RESTART=1 ./scripts/run_29_69_4_e2e_tests.sh  # when API already running
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Use alternate ports to avoid conflict with main compose (6379, 6380-6382, 6831, 8095)
export REDIS_CACHE_TEST_PORT="${REDIS_CACHE_TEST_PORT:-6479}"
export REDIS_QUEUE_TEST_PORT="${REDIS_QUEUE_TEST_PORT:-6470}"
export REDIS_EVENTS_TEST_PORT="${REDIS_EVENTS_TEST_PORT:-6471}"
export REDIS_CHANNELS_TEST_PORT="${REDIS_CHANNELS_TEST_PORT:-6472}"
export JAEGER_UDP_TEST_PORT="${JAEGER_UDP_TEST_PORT:-6833}"
export MOCK_SERVER_TEST_PORT="${MOCK_SERVER_TEST_PORT:-8197}"

COMPOSE_CMD="docker compose -f docker-compose.test.yml"
[[ -f .env.test ]] && COMPOSE_CMD="$COMPOSE_CMD --env-file .env.test"

echo "== Starting test stack (ports overridden to avoid conflicts) =="
$COMPOSE_CMD up -d api-service-test 2>&1 || true

echo "Waiting for API at http://localhost:8001/health/..."
for i in $(seq 1 60); do
  if curl -sf --connect-timeout 5 http://localhost:8001/health/ > /dev/null 2>&1; then
    echo "API is healthy"
    break
  fi
  if [[ $i -eq 60 ]]; then
    echo "API did not become healthy within 120s"
    echo "Check: $COMPOSE_CMD ps api-service-test"
    echo "Logs:  $COMPOSE_CMD logs api-service-test"
    exit 1
  fi
  sleep 2
done

docker exec hub-test-api python hub/manage.py reset_e2e_auth_rate_limits 2>/dev/null || true
docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles 2>/dev/null || true
docker exec hub-test-api python hub/manage.py ensure_e2e_subscription 2>/dev/null || true

echo ""
echo "== Running 29.69.4 E2E tests =="
cd frontend
export VITE_API_BASE_URL=/api/v1
export VITE_PROXY_TARGET=http://localhost:8001
export E2E_API_BASE_URL=http://localhost:8001/api/v1
exec npx playwright test \
  e2e/use-cases/ux/odps-asset-link.spec.ts \
  e2e/use-cases/ux/asset-attach-contract-dataset.spec.ts \
  --project=chromium \
  --reporter=list \
  "$@"
