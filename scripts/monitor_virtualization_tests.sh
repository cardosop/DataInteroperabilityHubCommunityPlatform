#!/bin/bash
# Monitor Virtualization Service Comprehensive Validation Tests

RESULTS_DIR="tests/integration/virtualization_test_results"
LATEST_LOG=$(ls -t "$RESULTS_DIR"/*.log 2>/dev/null | head -1)

if [ -z "$LATEST_LOG" ]; then
    echo "No test results file found. Tests may not have started yet."
    exit 1
fi

echo "Monitoring: $LATEST_LOG"
echo "Press Ctrl+C to stop"
echo ""

while true; do
    clear
    echo "=== Virtualization Tests Status ==="
    echo "File: $LATEST_LOG"
    echo "Last updated: $(stat -c %y "$LATEST_LOG" 2>/dev/null || stat -f %Sm "$LATEST_LOG" 2>/dev/null)"
    echo ""
    
    # Check for test execution
    if grep -q "test_virtual\|test_federated\|test_topology\|test_performance\|test_odps" "$LATEST_LOG" 2>/dev/null; then
        echo "✅ Tests are executing!"
        echo ""
        echo "=== Recent Test Activity ==="
        tail -100 "$LATEST_LOG" | grep -E "(test_|Ran [0-9]+ test|FAILED|ERROR|OK|PASSED)" | tail -20
    elif grep -q "Creating test database\|Applying.*migration" "$LATEST_LOG" 2>/dev/null; then
        echo "⏳ Migrations still running..."
        echo ""
        echo "=== Recent Migration Activity ==="
        tail -20 "$LATEST_LOG" | grep -v "timestamp\|level\|logger\|message" | tail -10
    else
        echo "⏳ Waiting for test execution to start..."
    fi
    
    echo ""
    echo "=== Summary ==="
    if grep -q "Ran [0-9]+ test" "$LATEST_LOG" 2>/dev/null; then
        grep "Ran [0-9]+ test" "$LATEST_LOG" | tail -1
        FAILED=$(grep -c "FAILED" "$LATEST_LOG" 2>/dev/null || echo "0")
        ERRORS=$(grep -c "ERROR" "$LATEST_LOG" 2>/dev/null || echo "0")
        echo "Failures: $FAILED"
        echo "Errors: $ERRORS"
    fi
    
    sleep 5
done
