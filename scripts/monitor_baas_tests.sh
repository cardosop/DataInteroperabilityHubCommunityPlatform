#!/bin/bash
# Monitor BaaS Platform Comprehensive Validation tests

LOG_FILE="/tmp/baas_test_full_output.log"
MAX_WAIT=1800  # 30 minutes
CHECK_INTERVAL=30  # Check every 30 seconds
ELAPSED=0

echo "=== Monitoring BaaS Platform Comprehensive Validation Tests ==="
echo "Log file: $LOG_FILE"
echo ""

# Check if test is still running
check_running() {
    ps aux | grep "test_baas_platform_comprehensive_validation" | grep -v grep | wc -l
}

# Get test progress
get_progress() {
    if [ -f "$LOG_FILE" ]; then
        tail -100 "$LOG_FILE" | grep -E "(^test_|^Ran|FAILED|ERROR|OK)" | tail -20
    fi
}

# Wait for test completion
while [ $ELAPSED -lt $MAX_WAIT ]; do
    RUNNING=$(check_running)

    if [ "$RUNNING" -eq 0 ]; then
        echo "Tests completed!"
        echo ""
        break
    fi

    echo "[$(date +%H:%M:%S)] Tests still running ($RUNNING processes)..."
    get_progress
    echo ""

    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

# Final results
echo "=== Final Test Results ==="
if [ -f "$LOG_FILE" ]; then
    echo ""
    echo "Test Summary:"
    grep -E "^Ran [0-9]+ test" "$LOG_FILE" | tail -1
    echo ""

    echo "Failed Tests:"
    grep -E "^test_.*\.\.\..*FAIL" "$LOG_FILE" | wc -l
    echo ""

    echo "Error Tests:"
    grep -E "^test_.*\.\.\..*ERROR" "$LOG_FILE" | wc -l
    echo ""

    echo "Passed Tests:"
    grep -E "^test_.*\.\.\..*ok$" "$LOG_FILE" | wc -l
    echo ""

    echo "All Test Results:"
    grep -E "^test_.*\.\.\." "$LOG_FILE" | sort
else
    echo "Log file not found: $LOG_FILE"
fi
