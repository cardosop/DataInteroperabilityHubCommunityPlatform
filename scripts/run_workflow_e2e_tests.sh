#!/usr/bin/env bash
# Run workflow business rules E2E tests inside Docker api-service.
# Requires: docker compose up -d (at least api-service and its dependencies).
# First run can take 15–30 min (test DB creation + migrations). Later runs with --reuse-db are quicker.

set -e
cd "$(dirname "$0")/.."

echo "Running workflow business rules E2E tests in api-service..."
docker compose exec -T api-service python -m pytest \
  tests/e2e/test_workflow_business_rules_e2e.py \
  -v \
  --tb=short \
  --reuse-db \
  "$@"
