#!/usr/bin/env bash
# Run Phase 6.5 — E2E tests for workflow performance with business rules.
# Requires: docker compose up -d (api-service and dependencies).
# First run can take 15–30 min (test DB creation + migrations). Use --reuse-db for faster reruns.

set -e
cd "$(dirname "$0")/.."

echo "Running Phase 6.5 workflow performance + business rules tests in api-service..."
docker compose exec -T api-service python -m pytest \
  hub/apps/orchestration/tests/test_workflow_business_rules_performance.py \
  tests/e2e/test_workflow_performance_business_rules_e2e.py \
  -v \
  --tb=short \
  --reuse-db \
  "$@"
