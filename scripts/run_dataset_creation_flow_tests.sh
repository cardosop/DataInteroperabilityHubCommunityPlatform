#!/usr/bin/env bash
# Run Dataset Creation Flow tests (tasks 29.68.2, 29.68.5, 29.68.6).
# Backend: test_data_first_asset_api, integration, security.
# Frontend E2E: dataset-creation-flow.spec.ts.
#
# Requires: docker compose -f docker-compose.test.yml
# Usage: ./scripts/run_dataset_creation_flow_tests.sh [--skip-migrate] [--skip-backend] [--skip-e2e] [--quick]
#
# --skip-migrate: Skip migrate-test-db (use when DB already migrated)
# --skip-backend: Skip backend pytest
# --skip-e2e: Skip frontend E2E
# --quick: Run only validation + tenant isolation + IDOR (no success/integration; no MinIO/DQ needed)

set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

SKIP_MIGRATE=false
SKIP_BACKEND=false
SKIP_E2E=false
QUICK=false
for arg in "$@"; do
  [[ "$arg" == "--skip-migrate" ]] && SKIP_MIGRATE=true
  [[ "$arg" == "--skip-backend" ]] && SKIP_BACKEND=true
  [[ "$arg" == "--skip-e2e" ]] && SKIP_E2E=true
  [[ "$arg" == "--quick" ]] && QUICK=true
done

echo "== Dataset Creation Flow Tests =="
echo ""

# Ensure test stack is up
docker compose -f "$COMPOSE_FILE" up -d postgres-test redis-cache-test minio-test 2>/dev/null || true
sleep 2

# Full run needs DQ, datacontract, compliance, semantic for success/integration tests
if [[ "$QUICK" != "true" ]] && [[ "$SKIP_BACKEND" != "true" ]]; then
  echo "== Starting DQ, datacontract, compliance, semantic services (for success/integration tests)..."
  docker compose -f "$COMPOSE_FILE" up -d fuseki-test datacontract-service-test dq-service-test compliance-service-test semantic-service-test 2>/dev/null || true
  echo "Waiting for services (dq has 150s start_period)..."
  sleep 60
fi

if [[ "$SKIP_MIGRATE" != "true" ]]; then
  echo "== Migrating test DB (migrate-test-db)..."
  docker compose -f "$COMPOSE_FILE" run --rm migrate-test-db 2>&1 | tail -15 || true
  sleep 2
fi

FAILED=0

if [[ "$SKIP_BACKEND" != "true" ]]; then
  echo ""
  if [[ "$QUICK" == "true" ]]; then
    echo "== Backend (quick): validation + tenant isolation + IDOR only =="
    PYTEST_ARGS="hub/apps/assets/tests/test_data_first_asset_api.py::DataFirstAssetAPIValidationTest hub/apps/assets/tests/test_data_first_asset_api.py::DataFirstAssetAPITenantIsolationTest tests/security/test_data_first_asset_idor.py"
  else
    echo "== Backend: test_data_first_asset_api, integration, security =="
    PYTEST_ARGS="hub/apps/assets/tests/test_data_first_asset_api.py tests/integration/test_data_first_asset_flow.py tests/security/test_data_first_asset_idor.py"
  fi
  # Use phase13 DB (shared isolation DB for compliance/security/E2E/dataset-creation tests).
  # Do NOT run this script concurrently with run_phase13_tests.sh or run_validation_29_7.sh --e2e.
  if docker compose -f "$COMPOSE_FILE" run --rm --no-deps -e POSTGRES_DB=hub_test -e TEST_DB_SUFFIX=phase13 api-service-test bash -c "
    cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=phase13 POSTGRES_DB=hub_test \
    python -m pytest $PYTEST_ARGS \
      -v --tb=short --reuse-db -p no:xdist --timeout=300
  "; then
    echo "✅ Backend tests passed"
  else
    echo "❌ Backend tests failed"
    FAILED=1
  fi
fi

if [[ "$SKIP_E2E" != "true" ]] && [[ $FAILED -eq 0 ]]; then
  echo ""
  echo "== Frontend E2E: dataset-creation-flow.spec.ts =="
  echo "Starting api-service-test (has many deps; Docker will start migrate-test-db, dq, prefect, ODH, etc.)..."
  docker compose -f "$COMPOSE_FILE" up -d api-service-test 2>/dev/null || true
  echo "Waiting for API (may take 5-10 min on first run; if timeout, run ./scripts/bring-up-test-stack.sh first)..."
  for i in $(seq 1 120); do
    if curl -sf http://localhost:8001/health/ > /dev/null 2>&1; then
      echo "✅ API ready"
      break
    fi
    [[ $i -eq 120 ]] && { echo "❌ API not ready after 6 min; run ./scripts/bring-up-test-stack.sh first, then re-run with --skip-migrate --skip-backend"; exit 1; }
    [[ $((i % 15)) -eq 0 ]] && echo "  ... still waiting (${i}/120)"
    sleep 3
  done
  cd frontend
  export VITE_API_BASE_URL=/api/v1
  export VITE_PROXY_TARGET=http://localhost:8001
  export E2E_API_BASE_URL=http://localhost:8001/api/v1
  if npm run test:e2e -- e2e/journeys/dpo/dataset-creation-flow.spec.ts --project=chromium; then
    echo "✅ E2E tests passed"
  else
    echo "❌ E2E tests failed"
    FAILED=1
  fi
  cd ..
fi

echo ""
[[ $FAILED -eq 0 ]] && echo "== All dataset creation flow tests passed ==" || echo "== Some tests failed =="
exit $FAILED
