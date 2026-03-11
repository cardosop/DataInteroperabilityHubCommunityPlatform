#!/usr/bin/env bash
# Run tenant-switch E2E tests. Requires API on 8001.
# Usage: ./scripts/run-tenant-switch-e2e.sh
# Prereq: docker compose -f docker-compose.test.yml up -d (API healthy on 8001)
# Or: ./scripts/run-e2e-with-backend.sh e2e/use-cases/auth/tenant-switch.spec.ts --project=chromium
set -euo pipefail
cd "$(dirname "$0")/.."

API_URL="${E2E_API_BASE_URL:-http://localhost:8001/api/v1}"
API_HEALTH="${API_URL%/api/v1*}/health/"

echo "Waiting for API at ${API_HEALTH}..."
for i in $(seq 1 60); do
  if curl -sf --connect-timeout 5 "${API_HEALTH}" > /dev/null 2>&1; then
    echo "✅ API is healthy"
    break
  fi
  if [[ $i -eq 60 ]]; then
    echo "❌ API not reachable. Start with: docker compose -f docker-compose.test.yml up -d api-service-test"
    echo "   Or: ./scripts/run-e2e-with-backend.sh e2e/use-cases/auth/tenant-switch.spec.ts --project=chromium"
    exit 1
  fi
  sleep 2
done

cd frontend
export VITE_API_BASE_URL=/api/v1
export VITE_PROXY_TARGET="${API_URL%/api/v1*}"
export E2E_API_BASE_URL="${API_URL}"
export E2E_WEB_PORT="${E2E_WEB_PORT:-5184}"
exec npx playwright test e2e/use-cases/auth/tenant-switch.spec.ts --project=chromium "$@"
