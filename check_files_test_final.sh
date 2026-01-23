#!/bin/bash
# Final check for Files Service test results

LOG_FILE="/tmp/files_service_tests_retry_fix.log"

echo "=== Files Service Test Execution Status ==="
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found: $LOG_FILE"
    exit 1
fi

echo "Log file size: $(wc -l < "$LOG_FILE") lines"
echo ""

# Check if tests are still running
if ps aux | grep -q "[p]ython manage.py test.*test_files_service"; then
    echo "Status: Tests still running..."
    echo ""
    echo "Recent activity:"
    tail -20 "$LOG_FILE" | grep -E "(test_|ok|OK)" | tail -5
else
    echo "Status: Tests completed"
    echo ""
    echo "=== Final Results ==="
    RAN=$(grep -E "Ran [0-9]+ test" "$LOG_FILE" 2>/dev/null | tail -1)
    if [ -n "$RAN" ]; then
        echo "$RAN"
    else
        echo "Test summary not found yet"
    fi

    echo ""
    FAILED=$(grep -c "FAIL:" "$LOG_FILE" 2>/dev/null || echo "0")
    ERRORED=$(grep -c "ERROR:" "$LOG_FILE" 2>/dev/null || echo "0")
    SKIPPED=$(grep -c "skipped" "$LOG_FILE" 2>/dev/null || echo "0")

    echo "Failed: $FAILED"
    echo "Errored: $ERRORED"
    echo "Skipped: $SKIPPED"

    if [ "$FAILED" -gt 0 ]; then
        echo ""
        echo "=== Failed Tests ==="
        grep "FAIL:" "$LOG_FILE" 2>/dev/null | head -10
    fi

    if [ "$ERRORED" -gt 0 ]; then
        echo ""
        echo "=== Errored Tests ==="
        grep "ERROR:" "$LOG_FILE" 2>/dev/null | grep -v "ValidationError\|Http404" | head -10
    fi

    echo ""
    echo "=== Recent Test Activity ==="
    tail -100 "$LOG_FILE" | grep -E "(test_|ok|OK|FAIL|ERROR)" | tail -20
fi
