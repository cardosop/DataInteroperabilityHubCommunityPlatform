#!/bin/bash
# Quick test execution script - runs tests with pytest (faster than manage.py test)
# This script uses pytest which can be faster for individual test execution

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo "Phase 10.5 Tests - Quick Execution (pytest)"
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

# Test suites to run (pytest format)
TEST_SUITES=(
    "tests/performance/test_odps_version_migration.py::TestODPSVersionMigration::test_data_preservation_during_migration"
    "tests/performance/test_odps_export_performance.py::TestODPSExportPerformance::test_export_performance_small_1kb"
    "tests/performance/test_marketplace_cli_sdk_performance.py::TestMarketplaceCLIPerformance::test_cli_connectors_list_performance"
    "tests/performance/test_baas_cli_sdk_performance.py::TestBaaSPlatformCLIPerformance::test_cli_api_key_create_performance"
    "tests/performance/test_odh_cli_sdk_performance.py::TestODHIntegrationCLIPerformance::test_cli_model_list_performance"
    "tests/performance/test_model_serving_cli_sdk_performance.py::TestModelServingCLIPerformance::test_cli_serve_model_performance"
)

# Results tracking
PASSED=0
FAILED=0
SKIPPED=0
TOTAL=0

# Function to run a test
run_test() {
    local test_path=$1
    local test_name=$(basename "$test_path" | sed 's/::.*//')

    echo "----------------------------------------"
    echo "Running: $test_name"
    echo "Test: $test_path"
    echo "----------------------------------------"

    TOTAL=$((TOTAL + 1))

    # Run test with pytest (faster, better timeout handling)
    if timeout 300 docker compose exec -T api-service bash -c \
        "cd /app/hub && pytest $test_path -v --reuse-db --tb=short 2>&1" \
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

# Run all tests
for test_path in "${TEST_SUITES[@]}"; do
    run_test "$test_path"
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
