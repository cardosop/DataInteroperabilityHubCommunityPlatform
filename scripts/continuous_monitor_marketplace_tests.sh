#!/bin/bash
# Continuous monitoring script for Marketplace Integration tests

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "=========================================="
echo "Continuous Marketplace Test Monitor"
echo "=========================================="
echo ""

# Find the most recent test results directory
LATEST_RESULTS_DIR=$(ls -td /tmp/marketplace_test_results_* 2>/dev/null | head -1)
LATEST_LOG="/tmp/marketplace_connection_class_bg.log"

if [ -z "$LATEST_RESULTS_DIR" ] && [ ! -f "$LATEST_LOG" ]; then
    echo "⚠️  No test results found"
    exit 1
fi

echo "📁 Monitoring test execution..."
echo ""

# Monitor loop
while true; do
    # Check if test process is running
    RUNNING=$(ps aux | grep -E "(manage.py test.*marketplace)" | grep -v grep | wc -l)

    if [ "$RUNNING" -eq 0 ]; then
        echo "✅ Test process completed"
        echo ""

        # Check results
        if [ -f "$LATEST_LOG" ]; then
            echo "📊 Final Results:"
            echo "----------------------------------------"
            grep -E "^(Ran|OK|FAIL|ERROR)" "$LATEST_LOG" | tail -5 || echo "No results found yet"
            echo ""

            # Check for failures
            FAILURES=$(grep -c "FAIL\|ERROR\|AssertionError" "$LATEST_LOG" 2>/dev/null || echo "0")
            if [ "$FAILURES" -gt 0 ]; then
                echo "❌ Found $FAILURES failures/errors"
                echo ""
                echo "First 5 failures:"
                grep -A 10 "FAIL\|ERROR\|AssertionError" "$LATEST_LOG" | head -50
            else
                echo "✅ No failures found"
            fi
        fi

        break
    fi

    # Show progress
    if [ -f "$LATEST_LOG" ]; then
        LINE_COUNT=$(wc -l < "$LATEST_LOG" 2>/dev/null || echo "0")
        MIGRATION_COUNT=$(grep -c "Applying\|OK" "$LATEST_LOG" 2>/dev/null || echo "0")
        TEST_COUNT=$(grep -c "test_\|Ran" "$LATEST_LOG" 2>/dev/null || echo "0")

        echo "⏳ Test running... (Log: ${LINE_COUNT} lines, Migrations: ${MIGRATION_COUNT}, Tests: ${TEST_COUNT})"

        # Show last test activity
        LAST_TEST=$(grep "test_\|Ran\|OK\|FAIL" "$LATEST_LOG" 2>/dev/null | tail -1 || echo "No test activity yet")
        echo "   Latest: $LAST_TEST"
    fi

    sleep 30
done

echo ""
echo "=========================================="
echo "Monitoring complete"
echo "=========================================="
