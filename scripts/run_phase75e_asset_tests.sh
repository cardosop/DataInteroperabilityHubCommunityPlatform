#!/usr/bin/env bash
# Run Phase 7.5.E backend tests (asset health score & recommendations).
# Use --reuse-db to skip migrations and reuse existing test DB (fast).
# Without --reuse-db: creates test DB, runs migrations, runs tests (slow first time).
#
# If you see "connection to server at postgres ... timeout expired", postgres may be
# under load; try running when fewer services are up, or run in CI with a slimmer stack.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

REUSE_DB=false
for arg in "$@"; do
  case "$arg" in
    --reuse-db) REUSE_DB=true ;;
  esac
done

TEST_LABELS="hub.apps.assets.tests.test_health_score hub.apps.assets.tests.test_recommendations hub.apps.assets.tests.test_health_score_integration hub.apps.assets.tests.test_recommendations_integration"

if [ "$REUSE_DB" = true ]; then
  # Reuse existing test DB; no migrations (test DB must already be migrated).
  # One-time: run without --reuse-db to create and migrate hub_test_phase75.
  docker compose exec -e SKIP_TEST_MIGRATIONS=1 -e TEST_DB_SUFFIX=phase75 api-service python hub/manage.py test $TEST_LABELS --keepdb --no-input -v 2
else
  # Create test DB if needed, run migrations, then run tests (slow first time).
  docker compose exec -e TEST_DB_SUFFIX=phase75 api-service python hub/manage.py test $TEST_LABELS --keepdb --no-input -v 2
fi
