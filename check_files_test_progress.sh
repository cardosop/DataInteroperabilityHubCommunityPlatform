#!/bin/bash
# Check Files Service test progress

LOG_FILE="/tmp/files_service_tests_improved.log"

echo "=== Files Service Test Progress ==="
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found: $LOG_FILE"
    exit 1
fi

echo "Log file size: $(wc -l < $LOG_FILE) lines"
echo ""

# Check if tests are still running
if ps aux | grep -q "[p]ython manage.py test.*test_files_service"; then
    echo "Status: Tests still running..."
    echo ""
else
    echo "Status: Tests completed"
    echo ""
fi

# Show recent test activity
echo "=== Recent Test Activity ==="
tail -100 "$LOG_FILE" | grep -E "(test_|FAIL|ERROR|OK|Ran [0-9]+ test|skipped)" | tail -30

echo ""
echo "=== Summary (if available) ==="
if grep -q "Ran.*test" "$LOG_FILE"; then
    RAN=$(grep "Ran.*test" "$LOG_FILE" | tail -1)
    echo "$RAN"
    
    PASSED=$(grep -c "OK" "$LOG_FILE" 2>/dev/null || echo "0")
    FAILED=$(grep -c "FAIL:" "$LOG_FILE" 2>/dev/null || echo "0")
    ERRORED=$(grep -c "ERROR:" "$LOG_FILE" 2>/dev/null || echo "0")
    SKIPPED=$(grep -c "skipped" "$LOG_FILE" 2>/dev/null || echo "0")
    
    echo "Passed: $PASSED"
    echo "Failed: $FAILED"
    echo "Errored: $ERRORED"
    echo "Skipped: $SKIPPED"
    
    if [ "$FAILED" -gt 0 ]; then
        echo ""
        echo "=== Failed Tests ==="
        grep "FAIL:" "$LOG_FILE" | head -10
    fi
    
    if [ "$ERRORED" -gt 0 ]; then
        echo ""
        echo "=== Errored Tests ==="
        grep "ERROR:" "$LOG_FILE" | head -10
    fi
fi
