#!/bin/bash
# Phase 11.2 Test Validation Script
# Runs all tests mentioned in tasks.md and reports failures/skips

set -e

echo "=========================================="
echo "Phase 11.2 Test Validation"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0
ERROR_TESTS=0

run_test_suite() {
    local suite_name=$1
    shift
    local test_command="$@"
    
    echo "----------------------------------------"
    echo "Running: $suite_name"
    echo "----------------------------------------"
    
    if eval "$test_command" 2>&1 | tee /tmp/test_output.log; then
        # Parse results
        local passed=$(grep -oP '\d+(?= passed)' /tmp/test_output.log | head -1 || echo "0")
        local failed=$(grep -oP '\d+(?= failed)' /tmp/test_output.log | head -1 || echo "0")
        local skipped=$(grep -oP '\d+(?= skipped)' /tmp/test_output.log | head -1 || echo "0")
        local error=$(grep -oP '\d+(?= error)' /tmp/test_output.log | head -1 || echo "0")
        
        TOTAL_TESTS=$((TOTAL_TESTS + ${passed:-0} + ${failed:-0} + ${skipped:-0} + ${error:-0}))
        PASSED_TESTS=$((PASSED_TESTS + ${passed:-0}))
        FAILED_TESTS=$((FAILED_TESTS + ${failed:-0}))
        SKIPPED_TESTS=$((SKIPPED_TESTS + ${skipped:-0}))
        ERROR_TESTS=$((ERROR_TESTS + ${error:-0}))
        
        if [ "${failed:-0}" -gt 0 ] || [ "${error:-0}" -gt 0 ]; then
            echo -e "${RED}✗ $suite_name: ${failed:-0} failed, ${error:-0} errors${NC}"
            return 1
        elif [ "${skipped:-0}" -gt 0 ]; then
            echo -e "${YELLOW}⚠ $suite_name: ${skipped:-0} skipped${NC}"
            return 0
        else
            echo -e "${GREEN}✓ $suite_name: All passed${NC}"
            return 0
        fi
    else
        echo -e "${RED}✗ $suite_name: Test execution failed${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Phase 4 Integration Tests (Core)
run_test_suite "Phase 4 Core Integration Tests" \
    "docker compose exec -T api-service bash -c 'cd /app && DJANGO_SETTINGS_MODULE=hub.test_settings_phase11 python -m pytest hub/apps/orchestration/tests/test_workflow_business_rules_integration.py hub/apps/orchestration/tests/test_workflow_task_business_rules_integration.py -v --reuse-db --tb=short -q'"

# Phase 4 Integration Tests (Additional)
run_test_suite "Phase 4 Additional Integration Tests" \
    "docker compose exec -T api-service bash -c 'cd /app && DJANGO_SETTINGS_MODULE=hub.test_settings_phase11 python -m pytest hub/apps/orchestration/tests/test_product_creation_workflow.py hub/apps/orchestration/tests/test_odps_workflow_events.py -v --reuse-db --tb=short -q'"

# Phase 6 E2E Tests
run_test_suite "Phase 6 E2E Tests" \
    "docker compose exec -T api-service bash -c 'cd /app && python -m pytest tests/e2e/test_contract_first_comprehensive.py tests/e2e/test_asset_operations.py tests/e2e/test_dataset_operations.py tests/e2e/test_contract_operations.py tests/e2e/test_marketplace_comprehensive.py tests/e2e/test_scheduled_ingestion.py tests/e2e/test_governance_e2e.py tests/e2e/test_entitlements.py -v --reuse-db --tb=short -q'"

# Phase 18 REST API Business Rules Alignment
run_test_suite "Phase 18 REST API Business Rules Alignment" \
    "docker compose exec -T api-service bash -c 'cd /app && python -m pytest tests/integration/test_rest_business_rules_alignment.py -v --reuse-db --tb=short -q'"

# Summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Total Tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
if [ $FAILED_TESTS -gt 0 ]; then
    echo -e "${RED}Failed: $FAILED_TESTS${NC}"
fi
if [ $ERROR_TESTS -gt 0 ]; then
    echo -e "${RED}Errors: $ERROR_TESTS${NC}"
fi
if [ $SKIPPED_TESTS -gt 0 ]; then
    echo -e "${YELLOW}Skipped: $SKIPPED_TESTS${NC}"
fi

if [ $FAILED_TESTS -eq 0 ] && [ $ERROR_TESTS -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}✗ Some tests failed or had errors${NC}"
    exit 1
fi
