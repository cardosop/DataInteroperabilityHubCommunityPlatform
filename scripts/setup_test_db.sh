#!/bin/bash
# Pre-create pytest test database to avoid slow startup on first run
# Run this once before running tests
#
# This script creates the test database and runs migrations once.
# After this, subsequent test runs with --reuse-db will be fast.
#
# Prerequisites: Test stack must be up. Run first:
#   docker compose -f docker-compose.test.yml up -d

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Align with run_phase_12a_backend_suites.sh: default to test compose
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
export COMPOSE_FILE

# API service name
if [[ -n "${API_SERVICE_NAME:-}" ]]; then
  API_SVC="${API_SERVICE_NAME}"
elif [[ "${COMPOSE_FILE:-}" == *"docker-compose.test"* ]]; then
  API_SVC="api-service-test"
else
  API_SVC="api-service"
fi

# Pre-check: service must be running
if [[ -z "$(docker compose ps -q "${API_SVC}" 2>/dev/null)" ]]; then
  echo "=========================================="
  echo "Error: ${API_SVC} is not running"
  echo "=========================================="
  echo ""
  echo "Start the test stack first:"
  echo "  docker compose -f docker-compose.test.yml up -d"
  echo ""
  echo "Then re-run this script:"
  echo "  ./scripts/setup_test_db.sh"
  echo ""
  exit 1
fi

echo "=========================================="
echo "Pre-creating pytest test database"
echo "=========================================="
echo "Compose: ${COMPOSE_FILE}"
echo "Service: ${API_SVC}"
echo ""
echo "This will:"
echo "  1. Create the test database (if it doesn't exist)"
echo "  2. Run all migrations (100+ files)"
echo ""
echo "⚠️  This may take 10-45 minutes on first run..."
echo "   Subsequent runs with --reuse-db will be fast (seconds)"
echo ""
echo "Starting..."

# Run a simple test to trigger DB creation and migration
# This uses pytest-django which will create the DB with --reuse-db
# We use a simple, fast test to minimize execution time
docker compose exec -T "${API_SVC}" bash -c \
  "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest \
  hub/apps/core/tests/test_reverse_lookups.py::ReverseLookupTest::test_all_reverse_calls_resolvable \
  -v --reuse-db --tb=short" 2>&1 | tee /tmp/test_db_setup.log || true

# Check if setup was successful
if grep -q "PASSED\|Using existing test database" /tmp/test_db_setup.log; then
  echo ""
  echo "=========================================="
  echo "✅ Test database setup complete!"
  echo "=========================================="
  echo ""
  echo "You can now run tests with --reuse-db (they will be faster)"
  echo ""
  echo "Next steps:"
  echo "  ./scripts/run_phase_12a_batched.sh"
  echo ""
else
  echo ""
  echo "=========================================="
  echo "⚠️  Test database setup may have issues"
  echo "=========================================="
  echo ""
  echo "Check the output above for errors."
  echo "Log saved to: /tmp/test_db_setup.log"
  echo ""
  exit 1
fi
