#!/usr/bin/env bash
# Run Phase 16 tenant onboarding self-service tests (backend + E2E)
# Usage: ./scripts/run_phase16_tests.sh [--backend-only|--e2e-only]
# Requires: docker compose -f docker-compose.test.yml up (postgres-test, api-service-test, etc.)
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

run_backend() {
  echo "===== Phase 16: Backend tests ====="
  echo "Running tenant onboarding self-service tests..."
  CMD="cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings POSTGRES_DB=hub_test TEST_DB_SUFFIX=phase13 \
    python -m pytest \
      tests/integration/test_tenant_onboarding_service_comprehensive_validation.py \
    -v --tb=short --reuse-db --timeout=120"
  if docker compose -f "$COMPOSE_FILE" ps api-service-test 2>/dev/null | grep -q "Up"; then
    docker compose -f "$COMPOSE_FILE" exec -e POSTGRES_DB=hub_test -e TEST_DB_SUFFIX=phase13 api-service-test bash -c "$CMD"
  else
    docker compose -f "$COMPOSE_FILE" run --rm --no-deps \
      -e POSTGRES_DB=hub_test \
      -e TEST_DB_SUFFIX=phase13 \
      api-service-test bash -c "$CMD"
  fi
}

run_e2e() {
  echo "===== Phase 16: E2E test ====="
  cd frontend
  bash scripts/e2e-detect-api.sh e2e/journeys/tenant/JOURNEY-TENANT-ONBOARDING.spec.ts --project=chromium --timeout=120000
}

case "${1:-}" in
  --backend-only) run_backend ;;
  --e2e-only)     run_e2e ;;
  *)
    run_backend
    run_e2e
    ;;
esac
echo "✅ Phase 16 tests complete"
