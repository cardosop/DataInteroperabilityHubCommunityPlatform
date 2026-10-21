#!/usr/bin/env bash
# Run frontend integration API tests against real backend.
# Auto-detects API port (8000 = dev, 8001 = test) and sets VITE_API_BASE_URL.
# No mocks/stubs; real backend only.
# Task 7.10 — test:integration:api

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$FRONTEND_DIR/.." && pwd)"
cd "$FRONTEND_DIR"

# If VITE_API_BASE_URL is already set, use it
if [[ -n "${VITE_API_BASE_URL:-}" ]]; then
  echo "Using VITE_API_BASE_URL=${VITE_API_BASE_URL}"
  exec env VITE_API_BASE_URL="$VITE_API_BASE_URL" npx vitest run --config vitest.integration.config.ts
fi

# Auto-detect: try 8000 (dev) first, then 8001 (test stack)
# Use /api/v1/ (returns 200) instead of /health/ (returns 503 when Redis unhealthy)
if curl -sf http://localhost:8000/api/v1/ > /dev/null 2>&1; then
  export VITE_API_BASE_URL="http://localhost:8000/api/v1"
  echo "Detected API at port 8000 (docker-compose / docker-compose.dev)"
  # Reset auth rate limits for integration tests
  docker exec hub-api python hub/manage.py reset_e2e_auth_rate_limits 2>/dev/null || \
    docker exec hub-dev-api python hub/manage.py reset_e2e_auth_rate_limits 2>/dev/null || true
  docker exec hub-api python hub/manage.py ensure_e2e_user_roles 2>/dev/null || \
    docker exec hub-dev-api python hub/manage.py ensure_e2e_user_roles 2>/dev/null || true
  docker exec hub-api python hub/manage.py ensure_e2e_subscription 2>/dev/null || \
    docker exec hub-dev-api python hub/manage.py ensure_e2e_subscription 2>/dev/null || true
elif curl -sf http://localhost:8001/api/v1/ > /dev/null 2>&1; then
  export VITE_API_BASE_URL="http://localhost:8001/api/v1"
  echo "Detected API at port 8001 (docker-compose.test)"
  docker exec hub-test-api python hub/manage.py reset_e2e_auth_rate_limits 2>/dev/null || true
  docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles 2>/dev/null || true
  docker exec hub-test-api python hub/manage.py ensure_e2e_subscription 2>/dev/null || true
else
  echo "❌ No backend API at port 8000 or 8001."
  echo ""
  echo "Start the backend first:"
  echo "  • docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d   (API on 8000)"
  echo "  • docker compose -f docker-compose.test.yml up -d                      (API on 8001)"
  echo ""
  exit 1
fi

exec env VITE_API_BASE_URL="$VITE_API_BASE_URL" npx vitest run --config vitest.integration.config.ts
