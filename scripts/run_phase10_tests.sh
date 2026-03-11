#!/usr/bin/env bash
# Run Phase 10: Admin user edit (PUT/PATCH /api/v1/users/{id}/)
# Tests: hub/apps/users/tests/test_views.py, test_admin_user_edit.py
# Usage: ./scripts/run_phase10_tests.sh [--e2e-only]
# Requires: docker compose -f docker-compose.test.yml up (postgres-test, api-service-test)
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

run_backend() {
  echo "===== Phase 10: Admin user edit — Backend tests ====="
  docker compose -f "$COMPOSE_FILE" run --rm --no-deps api-service-test bash -c "
    cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=shared \
    python -m pytest hub/apps/users/tests/test_views.py hub/apps/users/tests/test_admin_user_edit.py \
    -v --tb=short --reuse-db --timeout=120
  "
}

run_e2e() {
  echo "===== Phase 10: Admin user edit — E2E tests ====="
  cd frontend
  bash scripts/e2e-detect-api.sh e2e/journeys/ta/JOURNEY-TA-002.spec.ts --project=chromium --timeout=120000
  bash scripts/e2e-detect-api.sh e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts --project=chromium --timeout=120000
}

case "${1:-}" in
  --e2e-only) run_e2e ;;
  *)
    run_backend
    run_e2e
    ;;
esac
echo "✅ Phase 10 tests complete"
