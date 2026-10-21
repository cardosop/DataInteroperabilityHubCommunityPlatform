#!/usr/bin/env bash
# Phase 22–23 — Marketplace Real E2E Validation
# Runs: (1) test_connectors_e2e management command, (2) pytest test_connectors_e2e.py,
# (3) Phase 23 test_marketplace_demo_ckan_fixture.py, (4) --source both
# Uses docker-compose.test.yml (api-service-test). Requires workflow-engine-service-test
# for full sync (--wait --verify-assets). CKAN (demo.ckan.org) runs without credentials.
#
# Usage:
#   ./scripts/run_phase_22_marketplace_e2e.sh [--quick|--full]
#   --quick: connection + discovery only (--no-wait --no-verify-assets), no workflow-engine needed
#   --full:  full sync + asset verification (requires workflow-engine-service-test)
#
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

COMPOSE_FILE="docker-compose.test.yml"
API_SERVICE="api-service-test"
QUICK=false

for arg in "$@"; do
  case $arg in
    --quick) QUICK=true ;;
    --full)  QUICK=false ;;
  esac
done

echo "=============================================="
echo "  Phase 22 — Marketplace Real E2E Validation"
echo "=============================================="

# Ensure api-service-test is running
if ! docker compose -f "$COMPOSE_FILE" ps "$API_SERVICE" 2>/dev/null | grep -q "Up"; then
  echo "Starting $API_SERVICE..."
  docker compose -f "$COMPOSE_FILE" up -d "$API_SERVICE"
  echo "Waiting for API to be ready..."
  for i in $(seq 1 60); do
    if docker compose -f "$COMPOSE_FILE" exec -T "$API_SERVICE" python hub/manage.py check 2>/dev/null; then
      echo "API ready"
      break
    fi
    if [ "$i" -eq 60 ]; then
      echo "Timeout waiting for API"
      docker compose -f "$COMPOSE_FILE" ps
      exit 1
    fi
    sleep 2
  done
fi

# For full sync, ensure workflow-engine is running
if [ "$QUICK" = false ]; then
  if ! docker compose -f "$COMPOSE_FILE" ps workflow-engine-service-test 2>/dev/null | grep -q "Up"; then
    echo "Starting workflow-engine-service-test (required for sync to complete)..."
    docker compose -f "$COMPOSE_FILE" up -d workflow-engine-service-test
    echo "Waiting for workflow-engine..."
    sleep 10
  fi
fi

echo ""
echo "1. Management command: test_connectors_e2e"
echo "=============================================="

if [ "$QUICK" = true ]; then
  echo "Mode: quick (connection + discovery only)"
  docker compose -f "$COMPOSE_FILE" exec -T "$API_SERVICE" python hub/manage.py test_connectors_e2e \
    --source ckan --limit 3 --no-wait --no-verify-assets
else
  echo "Mode: full (sync + verify assets)"
  docker compose -f "$COMPOSE_FILE" exec -T "$API_SERVICE" python hub/manage.py test_connectors_e2e \
    --source ckan --limit 3 --verify-assets
fi

MGMT_EXIT=$?
if [ $MGMT_EXIT -ne 0 ]; then
  echo "Management command failed (exit $MGMT_EXIT)"
  exit $MGMT_EXIT
fi

echo ""
echo "2. Pytest: test_connectors_e2e.py"
echo "=============================================="
echo "Note: DadosGovBr and Snowflake tests skip when credentials not set (expected)."
echo "Using --reuse-db because api-service-test holds connections to hub_test_test_shared."
docker compose -f "$COMPOSE_FILE" exec -T "$API_SERVICE" python -m pytest \
  hub/apps/integrations/tests/test_connectors_e2e.py \
  -v --tb=short -m integration --reuse-db

echo ""
echo "3. Pytest: Phase 23 — test_marketplace_demo_ckan_fixture.py"
echo "=============================================="
echo "Validates get_or_create_demo_ckan_federated_asset() fixture (real demo.ckan.org PULL)."
docker compose -f "$COMPOSE_FILE" exec -T "$API_SERVICE" python -m pytest \
  hub/apps/integrations/tests/test_marketplace_demo_ckan_fixture.py \
  -v --tb=short -m integration --reuse-db

echo ""
echo "4. --source both (verify skip behavior)"
echo "=============================================="
docker compose -f "$COMPOSE_FILE" exec -T "$API_SERVICE" python hub/manage.py test_connectors_e2e \
  --source both --limit 2 --no-wait --no-verify-assets

echo ""
echo "=============================================="
echo "  Phase 22–23 validation complete"
echo "=============================================="
