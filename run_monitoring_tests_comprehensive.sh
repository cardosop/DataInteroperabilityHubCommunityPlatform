#!/bin/bash
# Comprehensive test runner for Monitoring & Observability tests
# Runs tests and captures failures/errors/skips for root cause fixes

set -e

cd /home/ph/Desktop/DataInteroperabilityHub

echo "================================================================"
echo "Running Monitoring & Observability Comprehensive Validation Tests"
echo "================================================================"
echo ""

# Test classes to run
TEST_CLASSES=(
    "tests.integration.test_monitoring_observability_comprehensive_validation.MetricsCollectionVerificationTest"
    "tests.integration.test_monitoring_observability_comprehensive_validation.AlertTriggeringVerificationTest"
    "tests.integration.test_monitoring_observability_comprehensive_validation.DashboardDataAccuracyTest"
    "tests.integration.test_monitoring_observability_comprehensive_validation.PerformanceMonitoringTest"
)

TOTAL_FAILED=0
TOTAL_ERRORS=0
TOTAL_SKIPPED=0
TOTAL_PASSED=0

for test_class in "${TEST_CLASSES[@]}"; do
    echo "Running $test_class..."
    echo "------------------------------------------------"
    
    # Run test class with timeout
    if timeout 600 docker compose exec -T api-service python manage.py test "$test_class" --verbosity=1 --keepdb 2>&1 | tee /tmp/test_${test_class//\//_}.log; then
        # Extract results
        FAILED=$(grep -c "FAILED" /tmp/test_${test_class//\//_}.log || echo "0")
        ERRORS=$(grep -c "ERROR" /tmp/test_${test_class//\//_}.log || echo "0")
        SKIPPED=$(grep -c "skipped" /tmp/test_${test_class//\//_}.log || echo "0")
        PASSED=$(grep -oP "Ran \d+ test" /tmp/test_${test_class//\//_}.log | grep -oP "\d+" || echo "0")
        
        TOTAL_FAILED=$((TOTAL_FAILED + FAILED))
        TOTAL_ERRORS=$((TOTAL_ERRORS + ERRORS))
        TOTAL_SKIPPED=$((TOTAL_SKIPPED + SKIPPED))
        TOTAL_PASSED=$((TOTAL_PASSED + PASSED))
        
        echo "Results: Passed=$PASSED, Failed=$FAILED, Errors=$ERRORS, Skipped=$SKIPPED"
    else
        echo "Test class failed or timed out"
        TOTAL_FAILED=$((TOTAL_FAILED + 1))
    fi
    
    echo ""
done

echo "================================================================"
echo "Summary"
echo "================================================================"
echo "Total Passed: $TOTAL_PASSED"
echo "Total Failed: $TOTAL_FAILED"
echo "Total Errors: $TOTAL_ERRORS"
echo "Total Skipped: $TOTAL_SKIPPED"
echo ""

if [ $TOTAL_FAILED -gt 0 ] || [ $TOTAL_ERRORS -gt 0 ]; then
    echo "Failures and errors found. Check logs in /tmp/test_*.log"
    exit 1
fi

exit 0
