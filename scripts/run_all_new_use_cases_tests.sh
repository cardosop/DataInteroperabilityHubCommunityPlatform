#!/bin/bash
# Comprehensive test runner for all New Use Cases test suites
# Runs tests systematically, tracks progress, and reports results

set -e

echo "=========================================="
echo "New Use Cases Comprehensive Tests - Full Suite Runner"
echo "Task 10.1.53"
echo "=========================================="
echo ""

# Test suites in execution order
declare -a TEST_SUITES=(
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

RESULTS_DIR="/tmp/new_use_cases_final_results_$(date +%s)"
mkdir -p "$RESULTS_DIR"

TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_SKIPPED=0
TOTAL_ERRORS=0
FAILED_SUITES=()

echo "Results directory: $RESULTS_DIR"
echo "Using --reuse-db for faster execution"
echo ""

for test_suite in "${TEST_SUITES[@]}"; do
    suite_name=$(basename "$test_suite" .py)

    echo "=========================================="
    echo "Running: $suite_name"
    echo "=========================================="

    result_file="$RESULTS_DIR/${suite_name}.txt"
    summary_file="$RESULTS_DIR/${suite_name}_summary.txt"

    # Run with 1 hour timeout per suite
    if timeout 3600 docker compose exec -T api-service bash -c "cd /app && python -m pytest $test_suite -v --tb=line --reuse-db --maxfail=20" > "$result_file" 2>&1; then
        passed=$(grep -c "PASSED" "$result_file" || echo "0")
        failed=$(grep -c "FAILED" "$result_file" || echo "0")
        skipped=$(grep -c "SKIPPED" "$result_file" || echo "0")
        errors=$(grep -c "ERROR" "$result_file" || echo "0")

        TOTAL_PASSED=$((TOTAL_PASSED + passed))
        TOTAL_FAILED=$((TOTAL_FAILED + failed))
        TOTAL_SKIPPED=$((TOTAL_SKIPPED + skipped))
        TOTAL_ERRORS=$((TOTAL_ERRORS + errors))

        if [ $failed -eq 0 ] && [ $errors -eq 0 ]; then
            echo "✅ $suite_name: $passed passed, $skipped skipped"
            echo "PASSED: $passed passed, $failed failed, $skipped skipped, $errors errors" > "$summary_file"
        else
            echo "❌ $suite_name: $passed passed, $failed failed, $skipped skipped, $errors errors"
            echo "FAILED: $passed passed, $failed failed, $skipped skipped, $errors errors" > "$summary_file"
            FAILED_SUITES+=("$suite_name")
        fi
    else
        exit_code=$?
        if [ $exit_code -eq 124 ]; then
            echo "⏱️  $suite_name: TIMEOUT (exceeded 1 hour)"
            TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
            echo "TIMEOUT" > "$summary_file"
            FAILED_SUITES+=("$suite_name")
        else
            echo "❌ $suite_name: Test execution failed (exit code: $exit_code)"
            TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
            echo "FAILED" > "$summary_file"
            FAILED_SUITES+=("$suite_name")
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
echo "Failed/Timeout Suites:"
for suite in "${FAILED_SUITES[@]}"; do
    echo "  - $suite"
done
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
