#!/usr/bin/env bash
# Run 29.67.5 Validation tests (task useronboardfix)
# Usage: ./scripts/run_29_67_5_validation_tests.sh [--quick]
# Requires: docker-compose.test.yml (postgres-test, redis-*, minio-test)
#
# --quick: Run only key files per tasks.md run commands (faster)
# --skip-migrate: Skip migrate-test-db (use when DB already migrated, e.g. after full stack up)
# default: Run full directories hub/apps/integrations/tests/, platform/tests/, gdpr/tests/
#
# Ensures migrate-test-db runs first (unless --skip-migrate) so hub_test_test_shared exists and is migrated.
# If tests fail with DB/migration errors:
#   ./scripts/clean-test-stack.sh --volumes
#   then up the stack again and rerun this script.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

# Ensure postgres-test and deps are up
docker compose -f "$COMPOSE_FILE" up -d postgres-test redis-cache-test minio-test 2>/dev/null || true
docker compose -f "$COMPOSE_FILE" stop api-service-test 2>/dev/null || true
sleep 2

# Ensure test DB is migrated (hub_test_test_shared); required for --reuse-db
SKIP_MIGRATE=false
for arg in "$@"; do
  [[ "$arg" == "--skip-migrate" ]] && SKIP_MIGRATE=true && break
done

if [[ "$SKIP_MIGRATE" != "true" ]]; then
  echo "== Ensuring test DB is migrated (migrate-test-db)..."
  docker compose -f "$COMPOSE_FILE" run --rm migrate-test-db 2>&1 | tail -25 || true
  sleep 2
fi

echo "== 29.67.5 Validation tests =="
echo "Using TEST_DB_SUFFIX=shared"
echo ""

QUICK=false
for arg in "$@"; do
  [[ "$arg" == "--quick" ]] && QUICK=true && break
done

if [[ "$QUICK" == "true" ]]; then
  echo "Quick mode: key files only (per tasks.md run commands)"
  docker compose -f "$COMPOSE_FILE" run --rm --no-deps api-service-test bash -c "
    cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=shared \
    python -m pytest \
      hub/apps/integrations/tests/test_services_integration.py \
      hub/apps/platform/tests/test_views.py \
      hub/apps/gdpr/tests/test_gdpr_services.py \
      -v --tb=short --reuse-db --timeout=600 -p no:xdist
  "
else
  echo "Full mode: integrations/, platform/, gdpr/ test directories"
  docker compose -f "$COMPOSE_FILE" run --rm --no-deps api-service-test bash -c "
    cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=shared \
    python -m pytest \
      hub/apps/integrations/tests/ \
      hub/apps/platform/tests/ \
      hub/apps/gdpr/tests/ \
      -v --tb=short --reuse-db --timeout=600 -p no:xdist
  "
fi
