#!/usr/bin/env bash
# Run Phase 28.2: Phases 11–19 P1/P2 Test Updates
# Tests: trust signals (11), versioning (12), GDPR (13), workflows (14), platform admin (15)
# Usage: ./scripts/run_phase28_2_tests.sh [--backend-only|--e2e-only|--phase11|--phase12|...|--phase15]
# Requires: docker compose -f docker-compose.test.yml up (postgres-test, api-service-test, etc.)
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

run_backend() {
  echo "===== Phase 28.2: Backend tests (Phases 11–15) ====="
  # Stop api-service-test to avoid DB conflicts (hub_test_test_shared, hub_test_test_phase13 in use) and deadlocks
  docker compose -f "$COMPOSE_FILE" stop api-service-test 2>/dev/null || true
  sleep 2
  # Ensure hub_test_test_phase13 exists and is migrated (Phase 13 uses it; avoids full create path + serialize_db_to_string)
  docker compose -f "$COMPOSE_FILE" exec -T postgres-test psql -U hub_test -d postgres -c "CREATE DATABASE hub_test_test_phase13" 2>/dev/null || true
  docker compose -f "$COMPOSE_FILE" run --rm --no-deps -e POSTGRES_DB=hub_test_test_phase13 api-service-test bash -c "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python hub/manage.py migrate --noinput" 2>/dev/null || true
  # Phase 11, 13: backend-only scripts (no --backend-only flag)
  echo "--- Running Phase 11 backend ---"
  ./scripts/run_phase11_tests.sh
  echo "--- Running Phase 12 backend ---"
  ./scripts/run_phase12_tests.sh --backend-only
  echo "--- Running Phase 13 backend ---"
  ./scripts/run_phase13_tests.sh
  echo "--- Running Phase 14 backend ---"
  ./scripts/run_phase14_tests.sh --backend-only
  echo "--- Running Phase 15 backend ---"
  ./scripts/run_phase15_tests.sh --backend-only
}

run_e2e() {
  echo "===== Phase 28.2: E2E tests (Phases 11–15) ====="
  cd frontend
  # Phase 11, 12, 14: JOURNEY-TA-TENANT-SETTINGS (trust signals, versioning, workflows)
  bash scripts/e2e-detect-api.sh e2e/journeys/ta/JOURNEY-TA-TENANT-SETTINGS.spec.ts --project=chromium --timeout=120000
  # Phase 13: GDPR
  bash scripts/e2e-detect-api.sh e2e/journeys/auth/JOURNEY-AUTH-PRIVACY.spec.ts --project=chromium --timeout=120000
  # Phase 15: Platform admin
  bash scripts/e2e-detect-api.sh e2e/journeys/pa/JOURNEY-PA-015.spec.ts --project=chromium --timeout=120000
}

case "${1:-}" in
  --backend-only) run_backend ;;
  --e2e-only)     run_e2e ;;
  --phase11)      ./scripts/run_phase11_tests.sh ;;
  --phase12)      ./scripts/run_phase12_tests.sh ;;
  --phase13)      ./scripts/run_phase13_tests.sh ;;
  --phase14)      ./scripts/run_phase14_tests.sh ;;
  --phase15)      ./scripts/run_phase15_tests.sh ;;
  *)
    run_backend
    run_e2e
    ;;
esac
echo "✅ Phase 28.2 tests complete"
