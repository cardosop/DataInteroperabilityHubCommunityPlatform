#!/usr/bin/env bash
# Run Phase 28.3 tests (Phase 20–24 Real E2E)
# Phase 20/21: virtualization real source; Phase 22–23: marketplace
#
# Prerequisites: docker-compose.test.yml stack up (postgres-test, redis, fuseki, semantic, etc.)
# Usage: ./scripts/run_phase28_3_tests.sh [--phase20-21|--phase23|--all|--run-mode]
#   --run-mode: use 'docker compose run' (one-off) instead of exec; use when api-service-test not healthy
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
[[ -f .env.test ]] && ENV_ARGS="--env-file .env.test" || ENV_ARGS=""
API_SVC="api-service-test"
# Use migrate-test-db for run mode (same image as api, has postgres/redis deps)
RUN_SVC="migrate-test-db"
PYTEST_ENV="LOG_LEVEL=WARNING PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=shared POSTGRES_DB=hub_test_test_shared"

_run_pytest() {
  local paths="$1"
  local extra="${2:-}"
  if [[ "${USE_RUN_MODE:-}" == "1" ]]; then
    docker compose -f "$COMPOSE_FILE" $ENV_ARGS run --rm \
      -e PYTHONPATH=/app -e DJANGO_SETTINGS_MODULE=hub.settings \
      -e TEST_DB_SUFFIX=shared -e POSTGRES_DB=hub_test_test_shared \
      -e SEMANTIC_SERVICE_URL=http://semantic-service-test:8081 \
      -e FUSEKI_URL=http://fuseki-test:3030 \
      -e REDIS_URL=redis://redis-cache-test:6379/0 \
      "$RUN_SVC" python -m pytest $paths -v --tb=short --reuse-db --timeout=180 $extra
  else
    docker compose -f "$COMPOSE_FILE" $ENV_ARGS exec -T "$API_SVC" bash -c \
      "cd /app && $PYTEST_ENV python -m pytest $paths -v --tb=short --reuse-db --timeout=180 $extra"
  fi
}

run_phase20_21() {
  echo "== Phase 20+21: Virtualization real E2E =="
  _run_pytest "tests/integration/test_phase20_real_postgresql.py tests/integration/test_phase21_federated_e2e.py" "-m 'integration and real_virtualization_e2e'"
}

run_phase23() {
  echo "== Phase 23: Marketplace demo.ckan.org fixture =="
  _run_pytest "tests/integration/test_phase23_marketplace_demo_ckan_fixture.py" ""
}

MODE="${1:-all}"
USE_RUN_MODE=0
[[ "$MODE" == "--run-mode" ]] && USE_RUN_MODE=1 && MODE="${2:-all}"

if [[ "$USE_RUN_MODE" != "1" ]]; then
  echo "Ensuring $API_SVC is up..."
  docker compose -f "$COMPOSE_FILE" $ENV_ARGS up -d "$API_SVC" 2>/dev/null || true
  for i in $(seq 1 90); do
    if docker compose -f "$COMPOSE_FILE" ps -q "$API_SVC" 2>/dev/null | grep -q .; then
      status=$(docker compose -f "$COMPOSE_FILE" ps "$API_SVC" 2>/dev/null | tail -1)
      health=$(docker inspect -f '{{.State.Health.Status}}' hub-test-api 2>/dev/null || echo "unknown")
      if [[ "$health" == "healthy" ]]; then
        echo "  $API_SVC is healthy."
        break
      fi
    fi
    if [[ "$i" -eq 90 ]]; then
      echo "Timeout waiting for $API_SVC. Try: $0 --run-mode $MODE"
      exit 1
    fi
    sleep 3
    echo "  Waiting... ($i)"
  done
else
  echo "Using run mode (docker compose run $RUN_SVC)"
fi

case "$MODE" in
  --phase20-21) run_phase20_21 ;;
  --phase23)    run_phase23 ;;
  --all)
    run_phase20_21
    run_phase23
    echo ""
    echo "== Phase 22: run ./scripts/run_phase_22_marketplace_e2e.sh --quick or --full =="
    ;;
  *) echo "Usage: $0 [--phase20-21|--phase23|--all] [--run-mode]"; exit 1 ;;
esac
