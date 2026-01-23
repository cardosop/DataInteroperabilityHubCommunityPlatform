#!/bin/bash
# Script to check ODH Integration test progress

LOG_FILE="/tmp/odh_tests_fixed.log"

echo "=========================================="
echo "ODH Integration Test Progress Check"
echo "=========================================="
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo "Test log file not found: $LOG_FILE"
    exit 1
fi

# Check if tests are running
if pgrep -f "python.*test.*odh_integration_comprehensive_validation" > /dev/null; then
    echo "Status: ⏳ Tests are running..."
    echo ""

    # Check migration progress
    MIGRATION_COUNT=$(grep -c "Applying.*\.\.\." "$LOG_FILE" 2>/dev/null || echo "0")
    echo "Migrations applied: $MIGRATION_COUNT"

    # Check if tests have started
    TEST_COUNT=$(grep -c "test_.*\.\.\." "$LOG_FILE" 2>/dev/null || echo "0")
    if [ "$TEST_COUNT" -gt 0 ]; then
        echo "Tests executing: $TEST_COUNT tests found"
        echo ""
        echo "Recent test activity:"
        grep "test_.*\.\.\." "$LOG_FILE" | tail -10
    else
        echo "Tests executing: Not yet (migrations in progress)"
        echo ""
        echo "Recent migration activity:"
        grep "Applying.*\.\.\." "$LOG_FILE" | tail -5
    fi

    echo ""
    echo "Recent log activity:"
    tail -10 "$LOG_FILE" | grep -v "timestamp\|level\|logger\|message" | head -5

    echo ""
    echo "Monitor with: tail -f $LOG_FILE"
else
    echo "Status: ✅ Tests completed"
    echo ""

    # Show final summary
    if grep -q "^Ran" "$LOG_FILE"; then
        echo "Final Summary:"
        grep "^Ran" "$LOG_FILE" | tail -1
        echo ""
        FAILED=$(grep -c "FAILED" "$LOG_FILE" 2>/dev/null || echo "0")
        ERRORS=$(grep -c "ERROR" "$LOG_FILE" 2>/dev/null || echo "0")
        echo "Failures: $FAILED"
        echo "Errors: $ERRORS"
    else
        echo "Test summary not available"
    fi
fi

echo ""
echo "Log file: $LOG_FILE"
echo "Lines: $(wc -l < "$LOG_FILE" 2>/dev/null || echo "0")"
