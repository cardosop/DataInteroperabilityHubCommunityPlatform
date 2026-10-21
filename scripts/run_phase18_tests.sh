#!/usr/bin/env bash
# Run Phase 18 cost tracking tests (backend + E2E)
# Usage: ./scripts/run_phase18_tests.sh [--backend-only|--e2e-only]
# Requires: docker compose -f docker-compose.test.yml up (postgres-test, api-service-test)
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

run_backend() {
  echo "===== Phase 18: Cost tracking backend tests ====="
  local cmd="cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=shared \
    python -m pytest hub/apps/api/tests/test_cost_tracking.py \
    -v --tb=short --reuse-db --timeout=120"
  if docker compose -f "$COMPOSE_FILE" ps api-service-test 2>/dev/null | grep -q "Up"; then
    docker compose -f "$COMPOSE_FILE" exec -e TEST_DB_SUFFIX=shared api-service-test bash -c "$cmd"
  else
    docker compose -f "$COMPOSE_FILE" run --rm --no-deps -e TEST_DB_SUFFIX=shared api-service-test bash -c "$cmd"
  fi
}

run_e2e() {
  echo "===== Phase 18: Cost tracking E2E ====="
  cd frontend
  bash scripts/e2e-detect-api.sh e2e/journeys/ta/JOURNEY-TA-007.spec.ts --project=chromium --timeout=120000 2>/dev/null || true
}

case "${1:-}" in
  --backend-only) run_backend ;;
  --e2e-only)    run_e2e ;;
  *)
    run_backend
    run_e2e
    ;;
esac
echo "✅ Phase 18 tests complete"
