#!/bin/bash
# Script to run New Use Cases Comprehensive Tests (Task 10.1.53)
# Runs tests in batches and reports results

set -e

echo "=========================================="
echo "New Use Cases Comprehensive Tests"
echo "Task 10.1.53"
echo "=========================================="
echo ""

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

# Check if services are running
if ! docker compose ps | grep -q "api-service.*Up"; then
    echo "⚠️  API service doesn't appear to be running"
    echo "   Starting services..."
    docker compose up -d api-service --no-deps || docker compose up -d api-service
    echo "   Waiting for service to be ready..."
    sleep 15
fi

echo "✅ Services are running"
echo ""

# Test suites to run
TEST_SUITES=(
    "tests/integration/test_ai_ml_new_use_cases_comprehensive.py"
    "tests/integration/test_transformation_new_use_cases_comprehensive.py"
    "tests/integration/test_social_features_new_use_cases_comprehensive.py"
    "tests/integration/test_data_mesh_new_use_cases_comprehensive.py"
    "tests/integration/test_virtualization_new_use_cases_comprehensive.py"
    "tests/integration/test_advanced_marketplace_new_use_cases_comprehensive.py"
    "tests/integration/test_advanced_governance_new_use_cases_comprehensive.py"
    "tests/integration/test_advanced_observability_new_use_cases_comprehensive.py"
    "tests/integration/test_integration_ecosystem_new_use_cases_comprehensive.py"
    "tests/integration/test_developer_experience_new_use_cases_comprehensive.py"
)

RESULTS_DIR="/tmp/new_use_cases_test_results_$(date +%s)"
mkdir -p "$RESULTS_DIR"

TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_SKIPPED=0

echo "Running test suites..."
echo ""

for test_suite in "${TEST_SUITES[@]}"; do
    suite_name=$(basename "$test_suite" .py)
    echo "=========================================="
    echo "Running: $suite_name"
    echo "=========================================="

    result_file="$RESULTS_DIR/${suite_name}.txt"

    # Run with timeout to prevent hanging
    if docker compose exec -T api-service bash -c "cd /app && timeout 1800 python -m pytest $test_suite -v --tb=line" > "$result_file" 2>&1; then
        passed=$(grep -c "PASSED" "$result_file" || echo "0")
        failed=$(grep -c "FAILED" "$result_file" || echo "0")
        skipped=$(grep -c "SKIPPED" "$result_file" || echo "0")

        TOTAL_PASSED=$((TOTAL_PASSED + passed))
        TOTAL_FAILED=$((TOTAL_FAILED + failed))
        TOTAL_SKIPPED=$((TOTAL_SKIPPED + skipped))

        echo "✅ $suite_name: $passed passed, $failed failed, $skipped skipped"
    else
        echo "❌ $suite_name: Test execution failed or timed out"
        TOTAL_FAILED=$((TOTAL_FAILED + 1))
    fi

    echo ""
done

echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Total Passed: $TOTAL_PASSED"
echo "Total Failed: $TOTAL_FAILED"
echo "Total Skipped: $TOTAL_SKIPPED"
echo ""
echo "Detailed results saved to: $RESULTS_DIR"
echo ""

if [ $TOTAL_FAILED -eq 0 ]; then
    echo "✅ All tests passed!"
    exit 0
else
    echo "❌ Some tests failed. Check results in $RESULTS_DIR"
    exit 1
fi
