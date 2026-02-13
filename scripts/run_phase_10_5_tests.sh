#!/bin/bash
# Script to run Phase 10.5 Load/Stress/Chaos Tests
# Runs all test suites and reports results

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo "Phase 10.5 Load/Stress/Chaos Tests"
echo "=========================================="
echo ""

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo "Error: docker not found. Please install Docker."
    exit 1
fi

# Check if api-service is running
if ! docker compose ps api-service | grep -q "Up"; then
    echo "Error: api-service is not running. Please start services with: docker compose up -d"
    exit 1
fi

# Test suites to run
TEST_SUITES=(
    "tests.performance.test_concurrent_odps_creation"
    "tests.chaos.test_odps_workflow_chaos"
    "tests.performance.test_odps_version_migration"
    "tests.performance.test_odps_export_performance"
    "tests.performance.test_marketplace_cli_sdk_performance"
    "tests.performance.test_baas_cli_sdk_performance"
    "tests.performance.test_odh_cli_sdk_performance"
    "tests.performance.test_model_serving_cli_sdk_performance"
)

# Results tracking
PASSED=0
FAILED=0
SKIPPED=0
TOTAL=0

# Function to run a test suite
run_test_suite() {
    local test_suite=$1
    local test_name=$(basename "$test_suite")

    echo "----------------------------------------"
    echo "Running: $test_name"
    echo "----------------------------------------"

    TOTAL=$((TOTAL + 1))

    # Run test with extended timeout (10 minutes) to account for database migrations
    # First run may take longer due to migrations, subsequent runs will be faster with --keepdb
    if timeout 600 docker compose exec -T api-service bash -c \
        "cd /app/hub && python manage.py test $test_suite --verbosity=1 --keepdb --no-input 2>&1" \
        > "/tmp/test_${test_name}.log" 2>&1; then
        echo "✅ PASSED: $test_name"
        PASSED=$((PASSED + 1))
        return 0
    else
        local exit_code=$?
        if [ $exit_code -eq 124 ]; then
            echo "⏱️  TIMEOUT: $test_name (exceeded 5 minutes)"
            FAILED=$((FAILED + 1))
        else
            echo "❌ FAILED: $test_name"
            echo "Last 20 lines of output:"
            tail -20 "/tmp/test_${test_name}.log"
            FAILED=$((FAILED + 1))
        fi
        return 1
    fi
}

# Run all test suites
for test_suite in "${TEST_SUITES[@]}"; do
    run_test_suite "$test_suite"
    echo ""
done

# Print summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Total: $TOTAL"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Skipped: $SKIPPED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✅ All tests passed!"
    exit 0
else
    echo "❌ Some tests failed. Check logs in /tmp/test_*.log"
    exit 1
fi
