#!/usr/bin/env bash
# Run Phase 8 — Tenant Usage & Config tests
# Requires: docker compose -f docker-compose.test.yml up -d (postgres-test, redis-cache-test at minimum)
# Or from host: POSTGRES_HOST=localhost POSTGRES_PORT=5434 ... (see below)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Use docker compose exec if api-service-test is running; otherwise run
if docker compose -f docker-compose.test.yml ps api-service-test 2>/dev/null | grep -q "Up"; then
  echo "Running Phase 8 tests via exec..."
  docker compose -f docker-compose.test.yml exec -T api-service-test bash -c \
    "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest hub/apps/tenants/tests/test_tenant_me_views.py hub/apps/tenants/tests/test_urls.py -v --tb=short --reuse-db"
else
  echo "Running Phase 8 tests via run (may take 2-5 min for first run)..."
  docker compose -f docker-compose.test.yml run --rm -T api-service-test bash -c \
    "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest hub/apps/tenants/tests/test_tenant_me_views.py hub/apps/tenants/tests/test_urls.py -v --tb=short"
fi

echo ""
echo "Phase 8 backend tests passed."
