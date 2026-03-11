#!/usr/bin/env bash
# Run Phase 15 platform admin tests (backend + E2E)
# Usage: ./scripts/run_phase15_tests.sh [--backend-only|--e2e-only]
# Requires: docker compose -f docker-compose.test.yml up (postgres-test, api-service-test, etc.)
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

run_backend() {
  echo "===== Phase 15: Backend tests ====="
  echo "Running platform admin suspend/resume and usage tests..."
  CMD="cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings POSTGRES_DB=hub_test TEST_DB_SUFFIX=phase13 \
    python -m pytest \
      hub/apps/platform/tests/test_views.py \
      hub/apps/tenants/tests/test_views.py::TenantViewSetTest::test_suspend_tenant \
      hub/apps/tenants/tests/test_views.py::TenantViewSetTest::test_reactivate_tenant \
      hub/apps/tenants/tests/test_views.py::TenantViewSetTest::test_suspend_deleted_tenant_fails \
      hub/apps/tenants/tests/test_views.py::TenantViewSetTest::test_reactivate_active_tenant_fails \
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
  echo "===== Phase 15: E2E test ====="
  cd frontend
  bash scripts/e2e-detect-api.sh e2e/journeys/pa/JOURNEY-PA-015.spec.ts --project=chromium --timeout=120000
}

case "${1:-}" in
  --backend-only) run_backend ;;
  --e2e-only)     run_e2e ;;
  *)
    run_backend
    run_e2e
    ;;
esac
echo "✅ Phase 15 tests complete"
