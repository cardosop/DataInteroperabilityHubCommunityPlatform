#!/bin/bash
# Script to run marketplace integration comprehensive validation tests,
# analyze results, and fix any failures/errors/skips
# Task: 10.1.36 Marketplace Integration Service Comprehensive Validation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "=========================================="
echo "Marketplace Integration Test Runner & Fixer"
echo "Task: 10.1.36"
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
    "ConnectionManagementTest"
    "SyncJobTest"
    "MappingManagementTest"
    "ConnectorTest"
    "MetadataMappingTest"
    "MarketplaceIntegrationAPITest"
    "MarketplaceIntegrationEventSystemTest"
    "MarketplaceIntegrationPerformanceTest"
    "MarketplaceIntegrationSecurityTest"
    "MarketplaceIntegrationUseCasesTest"
    "MarketplaceIntegrationUserJourneysTest"
    "MarketplaceIntegrationDatabaseStateTest"
    "MarketplaceIntegrationMultiTenancyTest"
    "MarketplaceIntegrationErrorHandlingTest"
    "MarketplaceIntegrationODPSTest"
)

RESULTS_DIR="/tmp/marketplace_test_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
ERROR_TESTS=0
SKIPPED_TESTS=0

echo "=========================================="
echo "Running Comprehensive Validation Tests"
echo "=========================================="
echo "Results directory: $RESULTS_DIR"
echo ""

for test_class in "${TEST_CLASSES[@]}"; do
    echo "Running $test_class..."

    LOG_FILE="$RESULTS_DIR/${test_class}.log"

    # Run test with timeout (30 minutes per test class)
    if timeout 1800 docker compose exec -T api-service bash -c \
        "cd /app && python hub/manage.py test \
        hub.apps.integrations.tests.test_marketplace_integration_service_comprehensive_validation.$test_class \
        --verbosity=2 --keepdb --no-input" 2>&1 | tee "$LOG_FILE"; then
        echo "✅ $test_class: PASSED"
        ((PASSED_TESTS++))
    else
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            echo "⏱️  $test_class: TIMEOUT (30 minutes)"
        else
            echo "❌ $test_class: FAILED"
            ((FAILED_TESTS++))
        fi
    fi

    # Extract test results from log
    if [ -f "$LOG_FILE" ]; then
        # Count tests
        RAN_LINE=$(grep "^Ran.*test" "$LOG_FILE" | tail -1 || echo "")
        if [ -n "$RAN_LINE" ]; then
            RAN_COUNT=$(echo "$RAN_LINE" | grep -oP '\d+(?= test)' || echo "0")
            TOTAL_TESTS=$((TOTAL_TESTS + RAN_COUNT))
        fi

        # Count failures
        FAIL_COUNT=$(grep -c "\.\.\. FAIL" "$LOG_FILE" 2>/dev/null || echo "0")
        FAILED_TESTS=$((FAILED_TESTS + FAIL_COUNT))

        # Count errors
        ERROR_COUNT=$(grep -c "\.\.\. ERROR" "$LOG_FILE" 2>/dev/null || echo "0")
        ERROR_TESTS=$((ERROR_TESTS + ERROR_COUNT))

        # Count skips
        SKIP_COUNT=$(grep -c "\.\.\. SKIP" "$LOG_FILE" 2>/dev/null || echo "0")
        SKIPPED_TESTS=$((SKIPPED_TESTS + SKIP_COUNT))
    fi

    echo ""
done

echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Total Test Classes: ${#TEST_CLASSES[@]}"
echo "Passed Classes: $PASSED_TESTS"
echo "Failed Classes: $FAILED_TESTS"
echo ""
echo "Total Tests: $TOTAL_TESTS"
echo "Passed: $((TOTAL_TESTS - FAILED_TESTS - ERROR_TESTS - SKIPPED_TESTS))"
echo "Failed: $FAILED_TESTS"
echo "Errors: $ERROR_TESTS"
echo "Skipped: $SKIPPED_TESTS"
echo ""

# Generate failure report
FAILURE_REPORT="$RESULTS_DIR/failures_report.txt"
echo "==========================================" > "$FAILURE_REPORT"
echo "Failure and Error Report" >> "$FAILURE_REPORT"
echo "==========================================" >> "$FAILURE_REPORT"
echo "" >> "$FAILURE_REPORT"

for test_class in "${TEST_CLASSES[@]}"; do
    LOG_FILE="$RESULTS_DIR/${test_class}.log"
    if [ -f "$LOG_FILE" ]; then
        if grep -E "FAIL|ERROR|AssertionError" "$LOG_FILE" > /dev/null 2>&1; then
            echo "=== $test_class ===" >> "$FAILURE_REPORT"
            grep -A 10 -E "FAIL|ERROR|AssertionError" "$LOG_FILE" >> "$FAILURE_REPORT"
            echo "" >> "$FAILURE_REPORT"
        fi
    fi
done

if [ -s "$FAILURE_REPORT" ]; then
    echo "❌ Failures and errors found. See: $FAILURE_REPORT"
    echo ""
    echo "First 50 lines of failure report:"
    head -50 "$FAILURE_REPORT"
else
    echo "✅ No failures or errors found!"
fi

echo ""
echo "📁 Results directory: $RESULTS_DIR"
echo "📄 Failure report: $FAILURE_REPORT"

if [ $FAILED_TESTS -eq 0 ] && [ $ERROR_TESTS -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
    exit 0
else
    echo ""
    echo "❌ Some tests failed. Review the failure report and fix issues."
    exit 1
fi
