#!/bin/bash
# Optimized test runner for New Use Cases Comprehensive Tests
# Uses --keepdb for faster iteration and --reuse-db for database reuse

set -e

echo "=========================================="
echo "New Use Cases Comprehensive Tests - Optimized Runner"
echo "Task 10.1.53"
echo "Using --keepdb for faster iteration"
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

# First run: Create test database (may take longer)
FIRST_RUN=true

echo "Running test suites with --reuse-db optimization..."
echo "First run will create test database (may take 5-10 minutes)"
echo "Subsequent runs will be much faster (1-3 minutes each)"
echo "Results will be saved to: $RESULTS_DIR"
echo ""

for test_suite in "${!TEST_SUITES[@]}"; do
    suite_name=$(basename "$test_suite" .py)
    expected_count=${TEST_SUITES[$test_suite]}

    echo "=========================================="
    echo "Running: $suite_name"
    echo "Expected tests: $expected_count"
    if [ "$FIRST_RUN" = true ]; then
        echo "Status: First run (creating test database)"
        TIMEOUT=1800  # 30 minutes for first run
    else
        echo "Status: Using existing test database"
        TIMEOUT=600   # 10 minutes for subsequent runs
    fi
    echo "=========================================="

    result_file="$RESULTS_DIR/${suite_name}.txt"
    summary_file="$RESULTS_DIR/${suite_name}_summary.txt"

    # Run with --reuse-db for faster execution (already in pytest.ini, but explicit for clarity)
    if timeout $TIMEOUT docker compose exec -T api-service bash -c "cd /app && python -m pytest $test_suite -v --tb=line --reuse-db" > "$result_file" 2>&1; then
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
        else
            echo "❌ $suite_name: $passed passed, $failed failed, $skipped skipped, $errors errors"
        fi
        echo "$passed passed, $failed failed, $skipped skipped, $errors errors" > "$summary_file"

        # Mark first run as complete
        FIRST_RUN=false
    else
        exit_code=$?
        if [ $exit_code -eq 124 ]; then
            echo "⏱️  $suite_name: TIMEOUT (exceeded ${TIMEOUT}s)"
            TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
            echo "TIMEOUT" > "$summary_file"
        else
            echo "❌ $suite_name: Test execution failed (exit code: $exit_code)"
            TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
            echo "FAILED" > "$summary_file"
            # Show last 20 lines for debugging
            echo "Last 20 lines of output:"
            tail -20 "$result_file"
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
