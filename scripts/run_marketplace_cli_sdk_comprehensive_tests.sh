#!/bin/bash
# Script to run Marketplace CLI/SDK Comprehensive Validation Tests
# Task: 10.1.39 Marketplace Integration CLI/SDK Comprehensive Validation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "=========================================="
echo "Marketplace CLI/SDK Comprehensive Validation Tests"
echo "Task: 10.1.39"
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

# Test suites to run
TEST_SUITES=(
    "cli.tests.integration.test_marketplace_cli_comprehensive_validation"
    "sdk.python.tests.test_marketplace_sdk_comprehensive_validation"
    "cli.tests.e2e.test_marketplace_cli_sdk_consistency"
)

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

for test_suite in "${TEST_SUITES[@]}"; do
    echo "=========================================="
    echo "Running: $test_suite"
    echo "=========================================="
    echo ""

    # Run tests using Django test runner
    if docker compose exec -T api-service bash -c "cd /app/hub && PYTHONPATH=/app python manage.py test $test_suite --verbosity=1 --keepdb 2>&1" | tee /tmp/test_output.log; then
        # Count results from output
        if grep -q "OK" /tmp/test_output.log && ! grep -q "FAILED" /tmp/test_output.log && ! grep -q "ERROR" /tmp/test_output.log; then
            echo "✅ $test_suite: PASSED"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ $test_suite: FAILED"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ $test_suite: FAILED"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo ""
done

echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Total Test Suites: $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"
echo "Skipped: $SKIPPED_TESTS"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo "✅ All tests passed!"
    exit 0
else
    echo "❌ Some tests failed. Check output above for details."
    exit 1
fi
