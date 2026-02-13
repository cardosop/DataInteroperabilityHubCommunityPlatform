#!/bin/bash
# Comprehensive Test Execution using Django manage.py test
# Runs all test types: unit, integration, E2E, performance, security

set +e  # Don't exit on error - we want to collect all results

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

REPORT_DIR="$PROJECT_DIR/test_reports_comprehensive"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MAIN_REPORT="$REPORT_DIR/COMPREHENSIVE_TEST_SUITE_${TIMESTAMP}.md"

echo "=========================================="
echo "Comprehensive Test Suite Execution"
echo "Using Django manage.py test"
echo "=========================================="
echo "Report: $MAIN_REPORT"
echo ""

# Create report directory
mkdir -p "$REPORT_DIR"

# Function to run test type and capture results
run_test_type() {
    local test_type=$1
    local description=$2
    local test_path=$3

    echo "=========================================="
    echo "Running: $description"
    echo "Path: $test_path"
    echo "=========================================="
    echo ""

    LOG_FILE="/tmp/comprehensive_${test_type}_${TIMESTAMP}.log"
    START_TIME=$(date +%s)

    # Run tests using Django manage.py test
    docker compose exec -T api-service bash -c "cd /app/hub && python manage.py test $test_path --verbosity=2 --keepdb --no-input" \
        2>&1 | tee "$LOG_FILE"

    EXIT_CODE=${PIPESTATUS[0]}
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ $description: PASSED (${DURATION}s)"
        return 0
    else
        echo "❌ $description: FAILED (exit code: $EXIT_CODE, ${DURATION}s)"
        return 1
    fi
}

# Track overall status
OVERALL_STATUS=0
RESULTS=()

# 1. Unit Tests (hub/apps, exclude integration/e2e)
echo "Starting comprehensive test suite execution..."
echo ""

echo "Note: Unit tests will run all hub/apps tests excluding integration/E2E patterns"
echo "This may take significant time..."
echo ""

run_test_type "unit" "Unit Tests" "hub.apps --exclude-tag=integration --exclude-tag=e2e"
RESULTS+=("unit:$?")

# 2. Integration Tests
run_test_type "integration" "Integration Tests" "tests.integration"
RESULTS+=("integration:$?")

# 3. E2E Tests
run_test_type "e2e" "E2E Tests" "tests.e2e"
RESULTS+=("e2e:$?")

# 4. Performance Tests
run_test_type "performance" "Performance Tests" "tests.performance"
RESULTS+=("performance:$?")

# 5. Security Tests
run_test_type "security" "Security Tests" "tests.security"
RESULTS+=("security:$?")

# Generate summary
echo ""
echo "=========================================="
echo "Comprehensive Test Suite Summary"
echo "=========================================="
echo ""

PASSED=0
FAILED=0

for result in "${RESULTS[@]}"; do
    IFS=':' read -r type status <<< "$result"
    if [ "$status" -eq 0 ]; then
        echo "✅ $type: PASSED"
        ((PASSED++))
    else
        echo "❌ $type: FAILED"
        ((FAILED++))
        OVERALL_STATUS=1
    fi
done

echo ""
echo "Total: $((PASSED + FAILED)) test types"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""

if [ $OVERALL_STATUS -eq 0 ]; then
    echo "✅ All test types passed!"
else
    echo "❌ Some test types failed"
    echo ""
    echo "Review logs in: /tmp/comprehensive_*_${TIMESTAMP}.log"
fi

echo ""
echo "Detailed reports available in: $REPORT_DIR"
echo ""

exit $OVERALL_STATUS
