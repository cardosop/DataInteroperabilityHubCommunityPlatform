#!/bin/bash
# Script to check ODH Integration test results

LOG_FILE="/tmp/odh_tests_background.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "Test log file not found: $LOG_FILE"
    echo "Tests may not be running or log file is in a different location"
    exit 1
fi

echo "=========================================="
echo "ODH Integration Test Results Summary"
echo "=========================================="
echo ""

# Check if tests are still running
if pgrep -f "test.*odh_integration_comprehensive_validation" > /dev/null; then
    echo "Status: ⏳ Tests are still running..."
    echo ""
    echo "Recent activity:"
    tail -10 "$LOG_FILE" | grep -E "(test_|OK|FAILED|ERROR)" | tail -5
    echo ""
    echo "Monitor with: tail -f $LOG_FILE"
else
    echo "Status: ✅ Tests completed"
    echo ""
fi

echo "=========================================="
echo "Test Execution Summary"
echo "=========================================="

# Count test results
TOTAL_TESTS=$(grep -c "test_" "$LOG_FILE" 2>/dev/null | tr -d '\n' || echo "0")
PASSED=$(grep -c "OK" "$LOG_FILE" 2>/dev/null | tr -d '\n' || echo "0")
FAILED=$(grep -c "FAILED" "$LOG_FILE" 2>/dev/null | tr -d '\n' || echo "0")
ERRORS=$(grep -c "ERROR" "$LOG_FILE" 2>/dev/null | tr -d '\n' || echo "0")

echo "Total tests found: $TOTAL_TESTS"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Errors: $ERRORS"
echo ""

if [ "$FAILED" -gt 0 ] || [ "$ERRORS" -gt 0 ]; then
    echo "=========================================="
    echo "Failures and Errors:"
    echo "=========================================="
    grep -A 10 "FAILED\|ERROR" "$LOG_FILE" | head -50
fi

echo ""
echo "Full log: $LOG_FILE"
echo "View with: tail -f $LOG_FILE"
