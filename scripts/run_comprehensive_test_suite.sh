#!/bin/bash
# Comprehensive Test Suite Runner
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
echo "=========================================="
echo "Report: $MAIN_REPORT"
echo ""

# Create report directory
mkdir -p "$REPORT_DIR"

# Function to run test type and capture results
run_test_type() {
    local test_type=$1
    local description=$2

    echo "=========================================="
    echo "Running: $description"
    echo "=========================================="
    echo ""

    LOG_FILE="/tmp/comprehensive_${test_type}_${TIMESTAMP}.log"

    docker compose exec -T api-service python3 -u /app/scripts/run_comprehensive_test_execution_docker.py \
        --test-type "$test_type" \
        --report-dir /app/test_reports_comprehensive \
        2>&1 | tee "$LOG_FILE"

    EXIT_CODE=${PIPESTATUS[0]}

    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ $description: PASSED"
    else
        echo "❌ $description: FAILED (exit code: $EXIT_CODE)"
    fi
    echo ""

    return $EXIT_CODE
}

# Track overall status
OVERALL_STATUS=0
RESULTS=()

# Run all test types
echo "Starting comprehensive test suite execution..."
echo ""

# 1. Unit Tests
run_test_type "unit" "Unit Tests"
RESULTS+=("unit:$?")

# 2. Integration Tests
run_test_type "integration" "Integration Tests"
RESULTS+=("integration:$?")

# 3. E2E Tests
run_test_type "e2e" "E2E Tests"
RESULTS+=("e2e:$?")

# 4. Performance Tests
run_test_type "performance" "Performance Tests"
RESULTS+=("performance:$?")

# 5. Security Tests
run_test_type "security" "Security Tests"
RESULTS+=("security:$?")

# Generate summary
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
fi

echo ""
echo "Detailed reports available in: $REPORT_DIR"
echo ""

exit $OVERALL_STATUS
