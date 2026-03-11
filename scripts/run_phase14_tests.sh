#!/usr/bin/env bash
# Run Phase 14 workflows config tests (backend + E2E)
# Usage: ./scripts/run_phase14_tests.sh [--backend-only|--e2e-only]
# Requires: docker compose -f docker-compose.test.yml up (postgres-test, api-service-test, etc.)
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

run_backend() {
  echo "===== Phase 14: Backend tests ====="
  echo "Running workflows config tests (tenant me_config + services + orchestration enforcement)..."
  echo "Using hub_test_test_phase13 (POSTGRES_DB=hub_test, TEST_DB_SUFFIX=phase13)."
  local cmd="cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings POSTGRES_DB=hub_test TEST_DB_SUFFIX=phase13 \
    python -m pytest \
      hub/apps/tenants/tests/test_tenant_me_views.py::TenantMeConfigViewTest::test_me_config_get_includes_workflows_enabled \
      hub/apps/tenants/tests/test_tenant_me_views.py::TenantMeConfigViewTest::test_me_config_patch_workflows_enabled_persistence \
      hub/apps/tenants/tests/test_services.py::GetTenantConfigTest::test_get_tenant_config_includes_workflows_enabled \
      hub/apps/tenants/tests/test_tenant_config_serializers.py::TenantConfigUpdateSerializerTest::test_partial_update_workflows_enabled \
      hub/apps/orchestration/tests/test_workflows_api_integration.py::WorkflowsAPIIntegrationTest::test_trigger_workflow_workflows_disabled_returns_403 \
    -v --tb=short --reuse-db --timeout=120"
  if docker compose -f "$COMPOSE_FILE" ps api-service-test 2>/dev/null | grep -q "Up"; then
    docker compose -f "$COMPOSE_FILE" exec -e POSTGRES_DB=hub_test -e TEST_DB_SUFFIX=phase13 api-service-test bash -c "$cmd"
  else
    docker compose -f "$COMPOSE_FILE" run --rm --no-deps \
      -e POSTGRES_DB=hub_test \
      -e TEST_DB_SUFFIX=phase13 \
      api-service-test bash -c "$cmd"
  fi
}

run_e2e() {
  echo "===== Phase 14: E2E test ====="
  cd frontend
  bash scripts/e2e-detect-api.sh e2e/journeys/ta/JOURNEY-TA-TENANT-SETTINGS.spec.ts -g "Phase 14" --project=chromium --timeout=120000
}

case "${1:-}" in
  --backend-only) run_backend ;;
  --e2e-only)    run_e2e ;;
  *)
    run_backend
    run_e2e
    ;;
esac
echo "✅ Phase 14 tests complete"
