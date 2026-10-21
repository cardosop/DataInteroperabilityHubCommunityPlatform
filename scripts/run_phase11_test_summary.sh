#!/bin/bash
# Phase 11.2 Quick Test Summary Script
# Runs key test suites and reports summary

set -e

echo "=========================================="
echo "Phase 11.2 Test Validation Summary"
echo "=========================================="
echo ""

# Phase 4 Integration Tests
echo "Phase 4 Integration Tests (Core)..."
docker compose exec -T api-service bash -c "cd /app && DJANGO_SETTINGS_MODULE=hub.test_settings_phase11 python -m pytest hub/apps/orchestration/tests/test_workflow_business_rules_integration.py hub/apps/orchestration/tests/test_workflow_task_business_rules_integration.py -v --reuse-db --tb=no -q" 2>&1 | tail -3

echo ""
echo "Phase 4 Integration Tests (Additional)..."
docker compose exec -T api-service bash -c "cd /app && DJANGO_SETTINGS_MODULE=hub.test_settings_phase11 python -m pytest hub/apps/orchestration/tests/test_product_creation_workflow.py hub/apps/orchestration/tests/test_odps_workflow_events.py -v --reuse-db --tb=no -q" 2>&1 | tail -3

echo ""
echo "Phase 18 REST API Business Rules Alignment..."
docker compose exec -T api-service bash -c "cd /app && python -m pytest tests/integration/test_rest_business_rules_alignment.py -v --reuse-db --tb=no -q" 2>&1 | tail -3

echo ""
echo "Phase 6 E2E Tests (Sample)..."
docker compose exec -T api-service bash -c "cd /app && python -m pytest tests/e2e/test_contract_first_comprehensive.py::ContractFirstFlowSuccessTests::test_complete_contract_first_journey_happy_path -v --reuse-db --tb=no" 2>&1 | tail -3

echo ""
echo "=========================================="
echo "Summary Complete"
echo "=========================================="
