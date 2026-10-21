#!/bin/bash
# Monitor and fix marketplace integration tests

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "=========================================="
echo "Marketplace Integration Test Monitor"
echo "=========================================="
echo ""

# Check if tests are running
RUNNING=$(ps aux | grep -E "(manage.py test.*marketplace)" | grep -v grep | wc -l)

if [ "$RUNNING" -eq 0 ]; then
    echo "⚠️  No tests currently running"
    echo ""
    echo "To run tests:"
    echo "  bash scripts/run_marketplace_comprehensive_tests.sh"
    exit 0
fi

echo "✅ Tests are running ($RUNNING processes)"
echo ""

# Check log files
LATEST_LOG="/tmp/marketplace_connection_class_bg.log"
if [ -f "$LATEST_LOG" ]; then
    LINE_COUNT=$(wc -l < "$LATEST_LOG" 2>/dev/null || echo "0")
    MIGRATION_COUNT=$(grep -c "Applying\|OK" "$LATEST_LOG" 2>/dev/null || echo "0")
    TEST_COUNT=$(grep -c "test_\|Ran" "$LATEST_LOG" 2>/dev/null || echo "0")

    echo "📊 Log Statistics:"
    echo "   Lines: $LINE_COUNT"
    echo "   Migrations: $MIGRATION_COUNT"
    echo "   Tests: $TEST_COUNT"
    echo ""

    # Show last activity
    echo "📝 Last Activity:"
    tail -5 "$LATEST_LOG" | grep -v "timestamp\|level\|logger\|message\|DEBUG\|INFO\|WARNING" | tail -3 || echo "   No recent activity"
    echo ""

    # Check for errors
    ERROR_COUNT=$(grep -c "ERROR\|FAIL\|AssertionError" "$LATEST_LOG" 2>/dev/null || echo "0")
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo "⚠️  Found $ERROR_COUNT errors in log"
        echo ""
        echo "Recent errors:"
        grep "ERROR\|FAIL\|AssertionError" "$LATEST_LOG" | tail -5
    else
        echo "✅ No errors found in log"
    fi
else
    echo "⚠️  No log file found at $LATEST_LOG"
fi

echo ""
echo "=========================================="
echo "Monitoring complete"
echo "=========================================="
