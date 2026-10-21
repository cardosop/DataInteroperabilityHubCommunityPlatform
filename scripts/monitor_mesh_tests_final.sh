#!/bin/bash
# Monitor Data Mesh Service Comprehensive Validation Tests

LOG_FILE="/tmp/mesh_tests_final_validation.log"
MAX_WAIT=3600  # 1 hour max wait
CHECK_INTERVAL=30  # Check every 30 seconds
ELAPSED=0

echo "Monitoring test execution..."
echo "Log file: $LOG_FILE"
echo "Check interval: ${CHECK_INTERVAL}s"
echo "Max wait: ${MAX_WAIT}s"
echo ""

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if [ -f "$LOG_FILE" ]; then
        # Count completed tests
        PASSED=$(grep -c "PASSED" "$LOG_FILE" 2>/dev/null || echo "0")
        FAILED=$(grep -c "FAILED" "$LOG_FILE" 2>/dev/null || echo "0")
        ERROR=$(grep -c "ERROR" "$LOG_FILE" 2>/dev/null || echo "0")
        PASSED=${PASSED:-0}
        FAILED=${FAILED:-0}
        ERROR=${ERROR:-0}
        TOTAL=$((PASSED + FAILED + ERROR))

        # Check if tests completed
        if grep -q "Ran.*test" "$LOG_FILE" 2>/dev/null; then
            echo ""
            echo "=== TEST EXECUTION COMPLETE ==="
            grep -E "Ran|passed|failed|skipped|error" "$LOG_FILE" | tail -3
            echo ""
            echo "=== FAILURES ==="
            grep -E "FAILED|ERROR" "$LOG_FILE" | head -20
            break
        fi

        # Show progress
        if [ $TOTAL -gt 0 ]; then
            echo "[$(date +%H:%M:%S)] Progress: $TOTAL tests completed (PASSED: $PASSED, FAILED: $FAILED, ERROR: $ERROR)"
            if [ $FAILED -gt 0 ] || [ $ERROR -gt 0 ]; then
                echo "  Recent failures:"
                grep -E "FAILED|ERROR" "$LOG_FILE" | tail -5 | sed 's/^/    /'
            fi
        else
            echo "[$(date +%H:%M:%S)] Tests still initializing..."
        fi
    else
        echo "[$(date +%H:%M:%S)] Waiting for log file..."
    fi

    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo ""
    echo "=== TIMEOUT REACHED ==="
    echo "Tests may still be running. Check manually:"
    echo "  tail -f $LOG_FILE"
fi
