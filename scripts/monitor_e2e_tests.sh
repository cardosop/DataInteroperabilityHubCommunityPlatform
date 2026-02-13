#!/bin/bash
# Monitor E2E test execution in real-time

LOG_FILE=$(ls -t /tmp/e2e_tests_full_*.log 2>/dev/null | head -1)

if [ -z "$LOG_FILE" ]; then
    echo "No E2E test log file found. Waiting for tests to start..."
    sleep 10
    LOG_FILE=$(ls -t /tmp/e2e_tests_full_*.log 2>/dev/null | head -1)
fi

if [ -z "$LOG_FILE" ]; then
    echo "Still no log file found. Tests may not have started."
    exit 1
fi

echo "Monitoring: $LOG_FILE"
echo "Press Ctrl+C to stop"
echo ""
echo "=== Real-time E2E test output ==="
tail -f "$LOG_FILE"
