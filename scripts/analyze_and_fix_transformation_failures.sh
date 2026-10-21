#!/bin/bash
# Analyze transformation test failures and prepare fixes

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

declare -A TEST_LOGS=(
    ["CRUD"]="/tmp/transformation_crud_results.log"
    ["Execution"]="/tmp/test_execution_new.log"
    ["Versioning"]="/tmp/test_versioning_new.log"
    ["Wrangling"]="/tmp/test_wrangling_new.log"
    ["ODPS"]="/tmp/test_odps_new.log"
    ["Templates"]="/tmp/test_templates_new.log"
    ["CustomFunctions"]="/tmp/test_custom_functions_new.log"
)

TEST_FILE="hub/apps/transformation/tests/test_transformation_service_comprehensive_validation.py"

echo "=========================================="
echo "Transformation Test Failure Analysis"
echo "=========================================="
echo ""

total_failures=0
total_errors=0
total_skips=0

# Analyze each test
for test_name in "${!TEST_LOGS[@]}"; do
    log_file="${TEST_LOGS[$test_name]}"

    if [ ! -f "$log_file" ] || ! grep -q "Ran.*test" "$log_file" 2>/dev/null; then
        continue
    fi

    failures=$(grep -c "FAILED" "$log_file" 2>/dev/null || echo "0")
    errors=$(grep -c "ERROR" "$log_file" 2>/dev/null || echo "0")
    skips=$(grep -ic "skipped" "$log_file" 2>/dev/null || echo "0")

    if [ "$failures" -gt 0 ] || [ "$errors" -gt 0 ] || [ "$skips" -gt 0 ]; then
        echo -e "${RED}=== $test_name Issues ===${NC}"
        echo "Failures: $failures, Errors: $errors, Skips: $skips"
        echo ""

        total_failures=$((total_failures + failures))
        total_errors=$((total_errors + errors))
        total_skips=$((total_skips + skips))

        # Show failed tests
        if [ "$failures" -gt 0 ] || [ "$errors" -gt 0 ]; then
            echo "Failed/Error Tests:"
            grep -E "(FAILED|ERROR)" "$log_file" | head -20
            echo ""

            # Show first traceback
            echo "First Error Traceback:"
            grep -B 5 -A 40 "Traceback" "$log_file" | head -50
            echo ""
            echo "---"
            echo ""
        fi

        # Show skipped tests
        if [ "$skips" -gt 0 ]; then
            echo "Skipped Tests:"
            grep -i "skipped" "$log_file" | head -10
            echo ""
        fi
    fi
done

echo "=========================================="
echo "Summary: $total_failures failures, $total_errors errors, $total_skips skips"
echo "=========================================="
echo ""

if [ $total_failures -gt 0 ] || [ $total_errors -gt 0 ] || [ $total_skips -gt 0 ]; then
    echo "=========================================="
    echo "Fix Strategy"
    echo "=========================================="
    echo ""
    echo "1. Review error tracebacks above"
    echo "2. Identify root causes (not symptoms)"
    echo "3. Check test file: $TEST_FILE"
    echo "4. Fix issues following best practices:"
    echo "   - No mocks/stubs (per requirements)"
    echo "   - Fix root causes, not symptoms"
    echo "   - Follow Django best practices"
    echo "   - Ensure all services running in Docker Compose"
    echo "5. Re-run failed tests"
    echo "6. Verify all tests pass"
    echo ""
    echo "Common Fix Patterns:"
    echo "- Permission errors: Check _setup_user_with_role is called"
    echo "- Model field errors: Verify field names match model definition"
    echo "- Uniqueness violations: Ensure UUID used in tenant/user/asset names"
    echo "- Missing dependencies: Check imports and service availability"
    echo "- Database state: Check setUp/tearDown methods"
    echo "- Skipped tests: Remove @skip decorators or fix skip conditions"
    echo ""
else
    echo -e "${GREEN}✅ No failures, errors, or skips found!${NC}"
    echo "All tests passed successfully."
fi
