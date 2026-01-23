#!/bin/bash
# Check Files Service test results

LOG_FILE="/tmp/files_service_tests_final.log"

echo "=== Files Service Test Results ==="
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found: $LOG_FILE"
    echo "Tests may not have started yet."
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

# Check for test results
echo "=== Test Results ==="
grep -E "^(test_|Ran|OK|FAIL|ERROR)" "$LOG_FILE" | tail -50

echo ""
echo "=== Summary ==="
PASSED=$(grep -c "OK" "$LOG_FILE" 2>/dev/null || echo "0")
FAILED=$(grep -c "FAIL:" "$LOG_FILE" 2>/dev/null || echo "0")
ERRORED=$(grep -c "ERROR:" "$LOG_FILE" 2>/dev/null || echo "0")
SKIPPED=$(grep -c "skipped" "$LOG_FILE" 2>/dev/null || echo "0")
RAN=$(grep "Ran.*test" "$LOG_FILE" | tail -1)

echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Errored: $ERRORED"
echo "Skipped: $SKIPPED"
echo "$RAN"

echo ""
echo "=== Failed Tests ==="
grep "FAIL:" "$LOG_FILE" | head -20

echo ""
echo "=== Errored Tests ==="
grep "ERROR:" "$LOG_FILE" | head -20
