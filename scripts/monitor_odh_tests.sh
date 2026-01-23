#!/bin/bash
# Script to monitor ODH Integration test execution and results

LOG_FILE="/tmp/odh_tests_fixed.log"

echo "=========================================="
echo "ODH Integration Test Monitoring"
echo "=========================================="
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo "Test log file not found: $LOG_FILE"
    exit 1
fi

# Check if tests are still running
if pgrep -f "python.*test.*odh_integration_comprehensive_validation" > /dev/null; then
    echo "Status: ⏳ Tests are running..."
    echo ""
    echo "Recent test activity:"
    tail -100 "$LOG_FILE" | grep -E "test_.*\.\.\." | tail -10
    echo ""
    echo "Recent errors (if any):"
    tail -200 "$LOG_FILE" | grep -E "ERROR|FAILED" | tail -5
    echo ""
    echo "Monitor with: tail -f $LOG_FILE"
else
    echo "Status: ✅ Tests completed"
    echo ""

    # Show final summary
    echo "=========================================="
    echo "Final Test Results"
    echo "=========================================="

    # Extract test summary
    if grep -q "^Ran" "$LOG_FILE"; then
        grep "^Ran" "$LOG_FILE" | tail -1
        echo ""
        echo "Failures:"
        grep -c "FAILED" "$LOG_FILE" 2>/dev/null || echo "0"
        echo "Errors:"
        grep -c "ERROR" "$LOG_FILE" 2>/dev/null || echo "0"
    else
        echo "Test summary not yet available"
    fi
fi

echo ""
echo "Full log: $LOG_FILE"
