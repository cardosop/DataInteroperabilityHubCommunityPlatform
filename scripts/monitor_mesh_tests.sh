#!/bin/bash
# Script to monitor Data Mesh Service Comprehensive Validation Tests

set -e

echo "=========================================="
echo "Data Mesh Service Test Monitoring"
echo "=========================================="
echo ""

# Check if tests are running
RUNNING=$(ps aux | grep "pytest.*mesh.*comprehensive" | grep -v grep | wc -l)
echo "Tests running: $RUNNING"
echo ""

# Check latest log file
LATEST_LOG=$(find /tmp -name "*mesh*test*.log" -o -name "*mesh*test*.txt" 2>/dev/null | xargs ls -t 2>/dev/null | head -1)

if [ -z "$LATEST_LOG" ]; then
    echo "No test log files found"
    exit 1
fi

echo "Monitoring: $LATEST_LOG"
echo "File size: $(wc -c < "$LATEST_LOG" | numfmt --to=iec-i --suffix=B)"
echo ""

# Check for test results
echo "=== Test Results ==="
RESULTS=$(grep -E "PASSED|FAILED|ERROR|Ran|passed|failed" "$LATEST_LOG" 2>/dev/null | tail -10)
if [ -z "$RESULTS" ]; then
    echo "No test results yet - tests still in progress"
    echo ""
    echo "=== Database Setup Progress ==="
    TABLE_COUNT=$(grep -c "CREATE TABLE" "$LATEST_LOG" 2>/dev/null || echo "0")
    INDEX_COUNT=$(grep -c "CREATE INDEX" "$LATEST_LOG" 2>/dev/null || echo "0")
    echo "Tables created: $TABLE_COUNT"
    echo "Indexes created: $INDEX_COUNT"
    echo ""
    echo "=== Latest Activity ==="
    tail -5 "$LATEST_LOG" 2>/dev/null | grep -v "timestamp\|level\|logger\|message" | tail -3
else
    echo "$RESULTS"
fi

echo ""
echo "=== Monitoring Commands ==="
echo "tail -f $LATEST_LOG | grep -E 'PASSED|FAILED|test_'"
echo "grep -E 'PASSED|FAILED|ERROR|Ran' $LATEST_LOG"
