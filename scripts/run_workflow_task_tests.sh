#!/bin/bash
# Script to run workflow task business rules integration tests
# Task: Phase 2 - Update remaining workflow tasks incrementally

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "=========================================="
echo "Workflow Task Business Rules Integration Tests"
echo "Phase 2 - Task 2.3.4"
echo "=========================================="
echo ""

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

# Check if services are running
if ! docker compose ps api-service | grep -q "Up"; then
    echo "⚠️  API service is not running"
    echo "   Please start services: docker compose up -d"
    exit 1
fi

echo "✅ Services are running"
echo ""

# Test classes to run
TEST_CLASSES=(
    "TestProductCreationWorkflowBusinessRules"
    "TestContractCreationWorkflowBusinessRules"
    "TestAssetCreationWorkflowBusinessRules"
    "TestDatasetCreationWorkflowBusinessRules"
    "TestMarketplacePublicationWorkflowBusinessRules"
    "TestAccessRequestWorkflowBusinessRules"
    "TestDataMeshWorkflowBusinessRules"
    "TestVersionCreationWorkflowBusinessRules"
)

RESULTS_DIR="/tmp/workflow_task_test_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
ERROR_TESTS=0
SKIPPED_TESTS=0

echo "=========================================="
echo "Running Workflow Task Business Rules Tests"
echo "=========================================="
echo "Results directory: $RESULTS_DIR"
echo ""

for test_class in "${TEST_CLASSES[@]}"; do
    echo "Running $test_class..."
    echo "----------------------------------------"
    
    TEST_OUTPUT_FILE="$RESULTS_DIR/${test_class}.log"
    
    # Run test with timeout and capture output
    if timeout 180 docker compose exec -T api-service bash -c \
        "cd /app && python hub/manage.py test hub.apps.orchestration.tests.test_workflow_task_business_rules_integration.${test_class} --verbosity=1 --keepdb --no-input 2>&1" \
        > "$TEST_OUTPUT_FILE" 2>&1; then
        
        # Parse results
        if grep -q "OK" "$TEST_OUTPUT_FILE"; then
            PASSED=$(grep -oP '\d+(?= passed)' "$TEST_OUTPUT_FILE" || echo "0")
            FAILED=$(grep -oP '\d+(?= failed)' "$TEST_OUTPUT_FILE" || echo "0")
            SKIPPED=$(grep -oP '\d+(?= skipped)' "$TEST_OUTPUT_FILE" || echo "0")
            
            PASSED_TESTS=$((PASSED_TESTS + PASSED))
            FAILED_TESTS=$((FAILED_TESTS + FAILED))
            SKIPPED_TESTS=$((SKIPPED_TESTS + SKIPPED))
            
            echo "✅ $test_class: PASSED ($PASSED passed, $FAILED failed, $SKIPPED skipped)"
        elif grep -q "FAILED" "$TEST_OUTPUT_FILE"; then
            FAILED=$(grep -oP '\d+(?= failed)' "$TEST_OUTPUT_FILE" || echo "0")
            FAILED_TESTS=$((FAILED_TESTS + FAILED))
            echo "❌ $test_class: FAILED ($FAILED failed)"
            echo "   See $TEST_OUTPUT_FILE for details"
        else
            ERROR_TESTS=$((ERROR_TESTS + 1))
            echo "⚠️  $test_class: ERROR (check $TEST_OUTPUT_FILE)"
        fi
    else
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            echo "⏱️  $test_class: TIMEOUT (exceeded 180 seconds)"
            ERROR_TESTS=$((ERROR_TESTS + 1))
        else
            echo "❌ $test_class: ERROR (exit code: $EXIT_CODE)"
            ERROR_TESTS=$((ERROR_TESTS + 1))
        fi
        echo "   See $TEST_OUTPUT_FILE for details"
    fi
    
    echo ""
done

TOTAL_TESTS=$((PASSED_TESTS + FAILED_TESTS + SKIPPED_TESTS + ERROR_TESTS))

echo "=========================================="
echo "Test Execution Summary"
echo "=========================================="
echo "Total: $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"
echo "Skipped: $SKIPPED_TESTS"
echo "Errors: $ERROR_TESTS"
echo ""
echo "Results directory: $RESULTS_DIR"
echo ""

if [ $FAILED_TESTS -eq 0 ] && [ $ERROR_TESTS -eq 0 ]; then
    echo "✅ All tests passed!"
    exit 0
else
    echo "❌ Some tests failed or had errors"
    exit 1
fi
