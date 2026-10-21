#!/bin/bash
# Run 29.69 Resource Picker tests (task 29.69.9.1)
# Covers: frontend picker unit tests (29.69.3), backend list API tests, integration, a11y (axe-core).
# Optional: E2E picker flows (29.69.8.4) via --e2e.
#
# Usage:
#   ./scripts/run_resource_picker_tests.sh [--skip-backend] [--skip-a11y] [--skip-frontend] [--e2e]
#
# Requires: docker compose -f docker-compose.test.yml (for backend)
# Frontend and a11y run locally (npm).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

[[ -f .env.test ]] && set -a && source .env.test && set +a
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
API_SVC="api-service-test"

SKIP_BACKEND=false
SKIP_A11Y=false
SKIP_FRONTEND=false
RUN_E2E=false
for arg in "$@"; do
  [[ "$arg" == "--skip-backend" ]] && SKIP_BACKEND=true
  [[ "$arg" == "--skip-a11y" ]] && SKIP_A11Y=true
  [[ "$arg" == "--skip-frontend" ]] && SKIP_FRONTEND=true
  [[ "$arg" == "--e2e" ]] && RUN_E2E=true
done

FAILED=0

echo "=========================================="
echo "29.69 Resource Picker Tests"
echo "=========================================="
echo ""

# 1. Frontend unit tests (pickers + pages that use pickers)
if [[ "$SKIP_FRONTEND" != "true" ]]; then
  echo "== Frontend: picker unit tests =="
  if (cd frontend && npm run test:run -- src/shared/components/pickers src/features/scheduledExport src/features/governance/components/RetentionPolicy src/features/odps src/features/datasets/components/DatasetDetailPage src/features/datasets/components/DatasetCreatePage 2>&1); then
    echo "✅ Frontend picker tests passed"
  else
    echo "❌ Frontend picker tests failed"
    FAILED=1
  fi
  echo ""
fi

# 2. Backend list API tests (contracts search, datasets, files, assets)
if [[ "$SKIP_BACKEND" != "true" ]]; then
  echo "== Backend: list API tests (picker support) =="
  if docker compose -f "$COMPOSE_FILE" run --rm --no-deps \
    -e POSTGRES_DB=hub_test -e TEST_DB_SUFFIX=phase69 \
    "$API_SVC" bash -c "
      cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest \
      hub/apps/contracts/tests/test_views.py \
      hub/apps/datasets/tests/test_views.py \
      hub/apps/files/tests/test_views.py \
      hub/apps/assets/tests/test_asset_crud.py \
      -k 'test_list_contracts or test_list_datasets or test_list_files or test_list_assets' \
      -v --tb=short --reuse-db -p no:xdist
    " 2>&1; then
    echo "✅ Backend list API tests passed"
  else
    echo "❌ Backend list API tests failed"
    FAILED=1
  fi
  echo ""
fi

# 3. Integration: picker → form → API (optional; requires backend on 8000 or 8001)
# Use /api/v1/ (returns 200) instead of /health/ (returns 503 when Redis unhealthy)
if [[ "$SKIP_BACKEND" != "true" ]] && { curl -sf --connect-timeout 3 http://localhost:8001/api/v1/ > /dev/null 2>&1 || curl -sf --connect-timeout 3 http://localhost:8000/api/v1/ > /dev/null 2>&1; }; then
  echo "== Integration: picker → form → API =="
  if (cd frontend && npm run test:integration:api 2>&1); then
    echo "✅ Integration tests passed"
  else
    echo "❌ Integration tests failed"
    FAILED=1
  fi
  echo ""
fi

# 4. A11y tests (axe-core on picker pages)
if [[ "$SKIP_A11Y" != "true" ]]; then
  echo "== A11y: axe-core on picker pages =="
  if (cd frontend && npm run test:a11y 2>&1); then
    echo "✅ A11y tests passed"
  else
    echo "❌ A11y tests failed"
    FAILED=1
  fi
  echo ""
fi

# 5. E2E picker flows (optional; 29.69.8.4; requires API on 8000/8001)
if [[ "$RUN_E2E" == "true" ]] && [[ "$SKIP_BACKEND" != "true" ]] && { curl -sf --connect-timeout 3 http://localhost:8001/api/v1/ > /dev/null 2>&1 || curl -sf --connect-timeout 3 http://localhost:8000/api/v1/ > /dev/null 2>&1; }; then
  echo "== E2E: picker flows (e2e/use-cases/ux/) =="
  if (cd frontend && E2E_SKIP_API_RESTART=1 npm run test:e2e:ux 2>&1); then
    echo "✅ E2E picker flows passed"
  else
    echo "❌ E2E picker flows failed"
    FAILED=1
  fi
  echo ""
fi

echo "=========================================="
if [[ $FAILED -eq 0 ]]; then
  echo "✅ All resource picker tests passed"
  exit 0
else
  echo "❌ Some tests failed"
  exit 1
fi
