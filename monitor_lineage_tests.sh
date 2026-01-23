#!/bin/bash
# Monitor lineage test execution and extract results

LOG_FILE="/tmp/lineage_tests_validation_run.log"
MAX_WAIT=1800  # 30 minutes
CHECK_INTERVAL=30
ELAPSED=0

echo "Monitoring lineage test execution..."
echo "Log file: $LOG_FILE"
echo ""

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if [ -f "$LOG_FILE" ]; then
        # Check for completion
        if grep -q "^Ran.*test" "$LOG_FILE" 2>/dev/null; then
            echo "✅ Tests completed!"
            echo ""
            echo "=== Test Results ==="
            grep -E "^(test_|Ran|FAILED|ERROR|ok|OK)" "$LOG_FILE" | tail -50
            echo ""
            echo "=== Failures ==="
            grep -B 20 -A 50 "FAILED\|ERROR\|AssertionError" "$LOG_FILE" | head -200
            exit 0
        fi

        # Show progress
        PASSED=$(grep -c "^ok$" "$LOG_FILE" 2>/dev/null || echo "0")
        FAILED=$(grep -c "FAILED" "$LOG_FILE" 2>/dev/null || echo "0")
        ERRORS=$(grep -c "ERROR" "$LOG_FILE" 2>/dev/null || echo "0")

        if [ "$PASSED" -gt 0 ] || [ "$FAILED" -gt 0 ] || [ "$ERRORS" -gt 0 ]; then
            echo "[$ELAPSED s] Progress: $PASSED passed, $FAILED failed, $ERRORS errors"
        fi
    fi

    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

echo "⏱️  Timeout reached. Extracting current status..."
if [ -f "$LOG_FILE" ]; then
    tail -1000 "$LOG_FILE" | grep -E "^(test_|Ran|FAILED|ERROR|ok|OK)" | tail -100
fi
