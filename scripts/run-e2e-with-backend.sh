#!/usr/bin/env bash
# Start test stack and run frontend E2E tests.
# Uses docker-compose.test.yml (API on 8001). From repo root or frontend/.
# No mocks/stubs; requires real API.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

COMPOSE_FILE="docker-compose.test.yml"
ENV_ARGS=""
[[ -f .env.test ]] && ENV_ARGS="--env-file .env.test"
COMPOSE_CMD="docker compose -f $COMPOSE_FILE $ENV_ARGS"

API_URL="${E2E_API_BASE_URL:-http://localhost:8001/api/v1}"
API_HEALTH="${API_URL%/api/v1*}/health/"

echo "===== E2E: Ensuring test stack is up ====="
echo "API URL: ${API_URL}"
echo ""

# Start test stack (idempotent; use bring-up-test-stack for full startup)
echo "Starting test stack ($COMPOSE_FILE)..."
$COMPOSE_CMD up -d api-service-test 2>&1 || true

# Wait for API health (max 120s)
echo "Waiting for API at ${API_HEALTH}..."
for i in $(seq 1 60); do
  if curl -sf "${API_HEALTH}" > /dev/null 2>&1; then
    echo "✅ API is healthy"
    break
  fi
  if [[ $i -eq 60 ]]; then
    echo "❌ API did not become healthy within 120s"
    echo "Check: docker compose -f $COMPOSE_FILE ps api-service-test"
    echo "Or run: ./scripts/bring-up-test-stack.sh"
    exit 1
  fi
  sleep 2
done

# Run E2E from frontend (use proxy to avoid CORS)
echo ""
echo "===== Running Playwright E2E tests ====="
cd frontend
export VITE_API_BASE_URL=/api/v1
export VITE_PROXY_TARGET="${API_URL%/api/v1*}"
export E2E_API_BASE_URL="${API_URL}"
export E2E_WEB_PORT="${E2E_WEB_PORT:-5184}"
exec npx playwright test "$@"
