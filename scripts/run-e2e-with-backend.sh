#!/usr/bin/env bash
# Start backend stack and run frontend E2E tests.
# Use when backend is not already running. From repo root or frontend/.
# No mocks/stubs; requires real API.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Compose files: dev stack (API on 8000). Override with COMPOSE_FILES for test stack (API on 8001).
API_URL="${VITE_API_BASE_URL:-http://localhost:8000/api/v1}"
API_HEALTH="${API_URL%/api/v1*}/health/"

echo "===== E2E: Ensuring backend is up ====="
echo "API URL: ${API_URL}"
echo ""

# Start services (idempotent; will no-op if already up)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Wait for API health (max 120s)
echo "Waiting for API at ${API_HEALTH}..."
for i in $(seq 1 60); do
  if curl -sf "${API_HEALTH}" > /dev/null 2>&1; then
    echo "✅ API is healthy"
    break
  fi
  if [[ $i -eq 60 ]]; then
    echo "❌ API did not become healthy within 120s"
    echo "Check: docker compose -f docker-compose.yml -f docker-compose.dev.yml ps"
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
exec npx playwright test "$@"
