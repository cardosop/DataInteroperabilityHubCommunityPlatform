#!/bin/bash
# Monitor test execution progress

LOG_FILE=$(ls -t /tmp/sequential_batches_*.log 2>/dev/null | head -1)

if [ -z "$LOG_FILE" ]; then
    echo "No test execution log found"
    exit 1
fi

echo "Monitoring: $LOG_FILE"
echo "Press Ctrl+C to stop"
echo ""

tail -f "$LOG_FILE"
