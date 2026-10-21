#!/bin/bash
# Batch test runner for New Use Cases Comprehensive Tests
# Runs tests in smaller batches with timeouts to prevent hanging

set -e

echo "=========================================="
echo "New Use Cases Comprehensive Tests - Batch Runner"
echo "Task 10.1.53"
echo "=========================================="
echo ""

# Test suites with expected test counts
declare -A TEST_SUITES=(
    ["tests/integration/test_ai_ml_new_use_cases_comprehensive.py"]=19
    ["tests/integration/test_transformation_new_use_cases_comprehensive.py"]=8
    ["tests/integration/test_social_features_new_use_cases_comprehensive.py"]=15
    ["tests/integration/test_data_mesh_new_use_cases_comprehensive.py"]=12
    ["tests/integration/test_virtualization_new_use_cases_comprehensive.py"]=8
    ["tests/integration/test_advanced_marketplace_new_use_cases_comprehensive.py"]=10
    ["tests/integration/test_advanced_governance_new_use_cases_comprehensive.py"]=10
    ["tests/integration/test_advanced_observability_new_use_cases_comprehensive.py"]=8
    ["tests/integration/test_integration_ecosystem_new_use_cases_comprehensive.py"]=10
    ["tests/integration/test_developer_experience_new_use_cases_comprehensive.py"]=8
)

RESULTS_DIR="/tmp/new_use_cases_results_$(date +%s)"
mkdir -p "$RESULTS_DIR"

TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_SKIPPED=0
TOTAL_ERRORS=0

echo "Running test suites with 30-minute timeout each..."
echo "Results will be saved to: $RESULTS_DIR"
echo ""

for test_suite in "${!TEST_SUITES[@]}"; do
    suite_name=$(basename "$test_suite" .py)
    expected_count=${TEST_SUITES[$test_suite]}

    echo "=========================================="
    echo "Running: $suite_name"
    echo "Expected tests: $expected_count"
    echo "=========================================="

    result_file="$RESULTS_DIR/${suite_name}.txt"
    summary_file="$RESULTS_DIR/${suite_name}_summary.txt"

    # Run with 30-minute timeout
    if timeout 1800 docker compose exec -T api-service bash -c "cd /app && python -m pytest $test_suite -v --tb=line" > "$result_file" 2>&1; then
        passed=$(grep -c "PASSED" "$result_file" || echo "0")
        failed=$(grep -c "FAILED" "$result_file" || echo "0")
        skipped=$(grep -c "SKIPPED" "$result_file" || echo "0")
        errors=$(grep -c "ERROR" "$result_file" || echo "0")

        TOTAL_PASSED=$((TOTAL_PASSED + passed))
        TOTAL_FAILED=$((TOTAL_FAILED + failed))
        TOTAL_SKIPPED=$((TOTAL_SKIPPED + skipped))
        TOTAL_ERRORS=$((TOTAL_ERRORS + errors))

        echo "✅ $suite_name: $passed passed, $failed failed, $skipped skipped, $errors errors"
        echo "$passed passed, $failed failed, $skipped skipped, $errors errors" > "$summary_file"
    else
        exit_code=$?
        if [ $exit_code -eq 124 ]; then
            echo "⏱️  $suite_name: TIMEOUT (exceeded 30 minutes)"
            TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
            echo "TIMEOUT" > "$summary_file"
        else
            echo "❌ $suite_name: Test execution failed (exit code: $exit_code)"
            TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
            echo "FAILED" > "$summary_file"
        fi
    fi

    echo ""
done

echo "=========================================="
echo "Final Summary"
echo "=========================================="
echo "Total Passed: $TOTAL_PASSED"
echo "Total Failed: $TOTAL_FAILED"
echo "Total Skipped: $TOTAL_SKIPPED"
echo "Total Errors/Timeouts: $TOTAL_ERRORS"
echo ""
echo "Detailed results: $RESULTS_DIR"
echo ""

if [ $TOTAL_FAILED -eq 0 ] && [ $TOTAL_ERRORS -eq 0 ]; then
    echo "✅ All tests passed!"
    exit 0
else
    echo "❌ Some tests failed or timed out. Check results in $RESULTS_DIR"
    exit 1
fi
