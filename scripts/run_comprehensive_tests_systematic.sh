#!/bin/bash
# Comprehensive Test Execution - Systematic Approach
# Runs tests in cycles: execute → evaluate → fix → repeat

set +e  # Don't exit on error - we want to collect all results

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

REPORT_DIR="$PROJECT_DIR/test_reports_comprehensive"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CYCLE_LOG="$REPORT_DIR/COMPREHENSIVE_TEST_CYCLE_${TIMESTAMP}.log"

echo "=========================================="
echo "Comprehensive Test Execution - Systematic"
echo "=========================================="
echo "Log: $CYCLE_LOG"
echo ""

# Create report directory
mkdir -p "$REPORT_DIR"

# Function to run unit tests for all apps
run_unit_tests() {
    echo "=========================================="
    echo "Phase 1: Unit Tests (All Django Apps)"
    echo "=========================================="
    echo ""

    ./scripts/run_unit_tests_all_apps.sh 2>&1 | tee "$REPORT_DIR/unit_tests_${TIMESTAMP}.log"
    return $?
}

# Function to run integration tests
run_integration_tests() {
    echo "=========================================="
    echo "Phase 2: Integration Tests"
    echo "=========================================="
    echo ""

    LOG_FILE="/tmp/integration_tests_${TIMESTAMP}.log"
    START_TIME=$(date +%s)

    docker compose exec -T api-service bash -c "cd /app/hub && timeout 7200 python manage.py test tests.integration --verbosity=2 --keepdb --no-input" \
        2>&1 | tee "$LOG_FILE"

    EXIT_CODE=${PIPESTATUS[0]}
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Integration Tests: PASSED (${DURATION}s)"
        return 0
    else
        echo "❌ Integration Tests: FAILED (exit code: $EXIT_CODE, ${DURATION}s)"
        return 1
    fi
}

# Function to run E2E tests
run_e2e_tests() {
    echo "=========================================="
    echo "Phase 3: E2E Tests"
    echo "=========================================="
    echo ""

    LOG_FILE="/tmp/e2e_tests_${TIMESTAMP}.log"
    START_TIME=$(date +%s)

    docker compose exec -T api-service bash -c "cd /app/hub && timeout 10800 python manage.py test tests.e2e --verbosity=2 --keepdb --no-input" \
        2>&1 | tee "$LOG_FILE"

    EXIT_CODE=${PIPESTATUS[0]}
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ E2E Tests: PASSED (${DURATION}s)"
        return 0
    else
        echo "❌ E2E Tests: FAILED (exit code: $EXIT_CODE, ${DURATION}s)"
        return 1
    fi
}

# Function to run performance tests
run_performance_tests() {
    echo "=========================================="
    echo "Phase 4: Performance Tests"
    echo "=========================================="
    echo ""

    LOG_FILE="/tmp/performance_tests_${TIMESTAMP}.log"
    START_TIME=$(date +%s)

    docker compose exec -T api-service bash -c "cd /app/hub && timeout 3600 python manage.py test tests.performance --verbosity=2 --keepdb --no-input" \
        2>&1 | tee "$LOG_FILE"

    EXIT_CODE=${PIPESTATUS[0]}
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Performance Tests: PASSED (${DURATION}s)"
        return 0
    else
        echo "❌ Performance Tests: FAILED (exit code: $EXIT_CODE, ${DURATION}s)"
        return 1
    fi
}

# Function to run security tests
run_security_tests() {
    echo "=========================================="
    echo "Phase 5: Security Tests"
    echo "=========================================="
    echo ""

    LOG_FILE="/tmp/security_tests_${TIMESTAMP}.log"
    START_TIME=$(date +%s)

    docker compose exec -T api-service bash -c "cd /app/hub && timeout 1800 python manage.py test tests.security --verbosity=2 --keepdb --no-input" \
        2>&1 | tee "$LOG_FILE"

    EXIT_CODE=${PIPESTATUS[0]}
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Security Tests: PASSED (${DURATION}s)"
        return 0
    else
        echo "❌ Security Tests: FAILED (exit code: $EXIT_CODE, ${DURATION}s)"
        return 1
    fi
}

# Main execution
echo "Starting comprehensive test suite execution..."
echo "This will run:"
echo "  1. Unit Tests (all Django apps)"
echo "  2. Integration Tests"
echo "  3. E2E Tests"
echo "  4. Performance Tests"
echo "  5. Security Tests"
echo ""
echo "Each phase will be executed and results evaluated."
echo "If failures occur, fix issues and re-run."
echo ""

OVERALL_STATUS=0

# Phase 1: Unit Tests
run_unit_tests
UNIT_STATUS=$?
if [ $UNIT_STATUS -ne 0 ]; then
    OVERALL_STATUS=1
    echo ""
    echo "⚠️  Unit tests had failures. Please review and fix before proceeding."
    echo "   Log: $REPORT_DIR/unit_tests_${TIMESTAMP}.log"
    echo ""
    echo "You can continue with other test types, but unit tests should pass first."
    echo ""
    read -p "Continue with integration tests? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping. Fix unit test issues and re-run."
        exit $OVERALL_STATUS
    fi
fi

# Phase 2: Integration Tests
run_integration_tests
INTEGRATION_STATUS=$?
if [ $INTEGRATION_STATUS -ne 0 ]; then
    OVERALL_STATUS=1
fi

# Phase 3: E2E Tests
run_e2e_tests
E2E_STATUS=$?
if [ $E2E_STATUS -ne 0 ]; then
    OVERALL_STATUS=1
fi

# Phase 4: Performance Tests
run_performance_tests
PERF_STATUS=$?
if [ $PERF_STATUS -ne 0 ]; then
    OVERALL_STATUS=1
fi

# Phase 5: Security Tests
run_security_tests
SECURITY_STATUS=$?
if [ $SECURITY_STATUS -ne 0 ]; then
    OVERALL_STATUS=1
fi

# Final summary
echo ""
echo "=========================================="
echo "FINAL SUMMARY"
echo "=========================================="
echo ""

if [ $UNIT_STATUS -eq 0 ]; then
    echo "✅ Unit Tests: PASSED"
else
    echo "❌ Unit Tests: FAILED"
fi

if [ $INTEGRATION_STATUS -eq 0 ]; then
    echo "✅ Integration Tests: PASSED"
else
    echo "❌ Integration Tests: FAILED"
fi

if [ $E2E_STATUS -eq 0 ]; then
    echo "✅ E2E Tests: PASSED"
else
    echo "❌ E2E Tests: FAILED"
fi

if [ $PERF_STATUS -eq 0 ]; then
    echo "✅ Performance Tests: PASSED"
else
    echo "❌ Performance Tests: FAILED"
fi

if [ $SECURITY_STATUS -eq 0 ]; then
    echo "✅ Security Tests: PASSED"
else
    echo "❌ Security Tests: FAILED"
fi

echo ""

if [ $OVERALL_STATUS -eq 0 ]; then
    echo "✅ All test types passed!"
    exit 0
else
    echo "❌ Some test types failed"
    echo ""
    echo "Review logs in: /tmp/*_tests_${TIMESTAMP}.log"
    echo "Fix issues and re-run this script."
    exit 1
fi
