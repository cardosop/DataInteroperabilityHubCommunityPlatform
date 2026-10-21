#!/usr/bin/env bash
# Run Phase 12 versioning config tests (backend + E2E)
# Usage: ./scripts/run_phase12_tests.sh [--backend-only|--e2e-only]
# Requires: docker compose -f docker-compose.test.yml up (postgres-test, api-service-test, etc.)
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

run_backend() {
  echo "===== Phase 12: Backend tests ====="
  echo "Running 4 tests (tenant me_config versioning + datasets versioning enforcement)..."
  # Use TEST_DB_SUFFIX=phase12 for isolated DB (avoids deadlocks with api-service on hub_test_test_shared)
  docker compose -f "$COMPOSE_FILE" run --rm --no-deps api-service-test bash -c "
    cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=phase12 \
    python -m pytest \
      hub/apps/tenants/tests/test_tenant_me_views.py::TenantMeConfigViewTest::test_me_config_get_includes_versioning_enabled \
      hub/apps/tenants/tests/test_tenant_me_views.py::TenantMeConfigViewTest::test_me_config_patch_versioning_enabled_persistence \
      hub/apps/tenants/tests/test_services.py::GetTenantConfigTest::test_get_tenant_config_includes_versioning_enabled \
      hub/apps/datasets/tests/test_views.py::DatasetViewSetTest::test_create_version_rejected_when_versioning_disabled \
    -v --tb=short --reuse-db --timeout=120
  "
}

run_e2e() {
  echo "===== Phase 12: E2E test ====="
  # Use e2e-detect-api.sh so backend setup (seed_default_plans, ensure_e2e_user_roles, etc.) runs
  cd frontend
  bash scripts/e2e-detect-api.sh e2e/journeys/ta/JOURNEY-TA-TENANT-SETTINGS.spec.ts -g "Phase 12" --project=chromium --timeout=120000
}

case "${1:-}" in
  --backend-only) run_backend ;;
  --e2e-only)    run_e2e ;;
  *)
    run_backend
    run_e2e
    ;;
esac
echo "✅ Phase 12 tests complete"
