#!/bin/bash
# Monitor Files Service tests until completion

LOG_FILE="/tmp/files_service_tests_final.log"

echo "Monitoring Files Service tests..."
echo "Log file: $LOG_FILE"
echo ""

while ps aux | grep -q "[p]ython manage.py test.*test_files_service"; do
    sleep 30
    LINES=$(wc -l < "$LOG_FILE" 2>/dev/null || echo "0")
    echo "$(date '+%H:%M:%S'): Tests still running... ($LINES lines)"
done

echo ""
echo "$(date '+%H:%M:%S'): Tests completed!"
echo ""
echo "=== Final Results ==="
grep -E "(Ran [0-9]+ test|OK|FAIL|ERROR|skipped)" "$LOG_FILE" | tail -5

echo ""
echo "=== Summary ==="
if grep -q "Ran.*test" "$LOG_FILE"; then
    RAN=$(grep "Ran.*test" "$LOG_FILE" | tail -1)
    echo "$RAN"

    FAILED=$(grep -c "FAIL:" "$LOG_FILE" 2>/dev/null || echo "0")
    ERRORED=$(grep -c "ERROR:" "$LOG_FILE" 2>/dev/null || echo "0")
    SKIPPED=$(grep -c "skipped" "$LOG_FILE" 2>/dev/null || echo "0")

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
