#!/usr/bin/env bash
# Run security tests (29.5) in Docker Compose.
# Usage: ./scripts/run_security_tests.sh [pytest args...]
# Requires: docker compose -f docker-compose.test.yml up (api-service-test healthy)
# Use TEST_DB_SUFFIX=phase13 for isolated DB (avoids contention with runserver).
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a
export COMPOSE_FILE=docker-compose.test.yml

docker compose -f "$COMPOSE_FILE" exec -T api-service-test bash -c "
  cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings \
  TEST_DB_SUFFIX=phase13 POSTGRES_DB=hub_test \
  python -m pytest tests/security/ -v --tb=short --reuse-db --timeout=120 ${*:-}
"
