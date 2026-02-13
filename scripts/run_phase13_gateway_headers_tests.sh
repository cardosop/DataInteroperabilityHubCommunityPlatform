#!/usr/bin/env bash
# Run Phase 13 security tests: gateway header trust and auth model.
#
# Prerequisites:
# - Docker Compose stack up: docker compose up -d (postgres, api-service healthy).
#
# Usage:
#   ./scripts/run_phase13_gateway_headers_tests.sh
#
# Tests: tests/security/test_gateway_headers_forged.py
# - Static check: hub code does not reference X-Gateway-* for auth (no DB).
# - Middleware test: forged X-Gateway-* headers do not override tenant from API key (DB).
# - Integration test: GET /api/v1/assets/ with API key + forged headers scoped to API key tenant (DB).
#
# Note: First run may take 2–15 min while the test DB is created and migrations applied.
# Use --reuse-db for faster subsequent runs.

set -e
cd "$(dirname "$0")/.."

EXTRA_ENV=()
if [ -n "${POSTGRES_PASSWORD:-}" ]; then
  EXTRA_ENV+=(-e "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" -e "DATABASE_URL=postgresql://hub:${POSTGRES_PASSWORD}@postgres:5432/hub")
fi
EXTRA_ENV+=(-e "TEST_DB_SUFFIX=phase13")

echo "Running Phase 13 gateway headers security tests..."
docker compose exec "${EXTRA_ENV[@]}" api-service bash -c \
  "cd /app && python -m pytest tests/security/test_gateway_headers_forged.py -v --tb=short --reuse-db --timeout=900"
