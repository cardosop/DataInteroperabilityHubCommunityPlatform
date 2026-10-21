#!/bin/bash
# Monitor comprehensive test execution progress

MAIN_LOG=$(ls -t /tmp/comprehensive_tests_phased_*.log 2>/dev/null | head -1)

if [ -z "$MAIN_LOG" ]; then
    echo "No comprehensive test log found"
    exit 1
fi

echo "Monitoring: $MAIN_LOG"
echo "Press Ctrl+C to stop"
echo ""

tail -f "$MAIN_LOG" 2>/dev/null || {
    echo "Log file not accessible. Showing last 50 lines:"
    tail -50 "$MAIN_LOG" 2>/dev/null
}
