#!/usr/bin/env bash
# Run 6.4 E2E tests for workflow observability with business rules (Option A).
# 1. Rebuild api-service (installs requirements-dev including pytest)
# 2. Bring up services
# 3. Run pytest inside api-service
set -e
cd "$(dirname "$0")/.."
echo "=== 1. Rebuilding api-service (this may take several minutes)..."
docker compose build api-service
echo "=== 2. Bringing up services..."
docker compose up -d
echo "=== 3. Running E2E observability tests in api-service..."
docker compose exec api-service python -m pytest tests/e2e/test_workflow_observability_business_rules_e2e.py -v --tb=short
