#!/usr/bin/env bash
# Run Phase 11 trust signals config tests
# Usage: ./scripts/run_phase11_tests.sh
# Requires: postgres-test, redis-cache-test, migrate-test-db (with 0011_add_trust_signals_enabled)
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml
docker compose -f "$COMPOSE_FILE" run --rm --no-deps api-service-test bash -c "
  cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings TEST_DB_SUFFIX=shared \
  python -m pytest hub/apps/tenants/tests/test_tenant_me_views.py hub/apps/tenants/tests/test_services.py \
  tests/integration/test_trust_signals_config_api_comprehensive.py \
  -v --tb=short --reuse-db --timeout=120 -k 'trust_signals or me_config or trust_signals_disabled'
"
