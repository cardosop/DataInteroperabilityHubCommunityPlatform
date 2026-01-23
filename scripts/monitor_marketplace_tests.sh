#!/bin/bash
# Script to monitor marketplace integration comprehensive validation tests
# Task: 10.1.36 Marketplace Integration Service Comprehensive Validation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "=========================================="
echo "Marketplace Integration Test Monitor"
echo "Task: 10.1.36"
echo "=========================================="
echo ""

LOG_FILE="/tmp/marketplace_test_full_output.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "⚠️  Log file not found: $LOG_FILE"
    echo "   Tests may not be running"
    exit 1
fi

echo "📊 Test Execution Status"
echo "========================"
echo ""

# Check if tests are still running
if pgrep -f "manage.py test.*marketplace" > /dev/null; then
    echo "✅ Tests are RUNNING"
else
    echo "⏸️  Tests are NOT running (may have completed)"
fi

echo ""
echo "📈 Test Progress"
echo "================"
echo ""

# Count migrations applied
MIGRATIONS=$(grep -c "Applying.*\.\.\." "$LOG_FILE" 2>/dev/null || echo "0")
echo "Migrations applied: $MIGRATIONS"

# Count tests found
TESTS_FOUND=$(grep -c "Found.*test(s)" "$LOG_FILE" 2>/dev/null || echo "0")
if [ "$TESTS_FOUND" -gt 0 ]; then
    echo "Tests found: $(grep "Found.*test(s)" "$LOG_FILE" | tail -1)"
fi

# Count tests executed
TESTS_OK=$(grep -c "\.\.\. ok" "$LOG_FILE" 2>/dev/null || echo "0")
TESTS_FAIL=$(grep -c "\.\.\. FAIL" "$LOG_FILE" 2>/dev/null || echo "0")
TESTS_ERROR=$(grep -c "\.\.\. ERROR" "$LOG_FILE" 2>/dev/null || echo "0")
TESTS_SKIP=$(grep -c "\.\.\. SKIP" "$LOG_FILE" 2>/dev/null || echo "0")

echo "Tests passed: $TESTS_OK"
echo "Tests failed: $TESTS_FAIL"
echo "Tests error: $TESTS_ERROR"
echo "Tests skipped: $TESTS_SKIP"

echo ""
echo "🔍 Recent Test Activity (last 20 lines)"
echo "========================================"
tail -20 "$LOG_FILE" | grep -E "(test_|\.\.\.|FAIL|ERROR|OK|Ran|Creating)" || tail -20 "$LOG_FILE"

echo ""
echo "❌ Failures and Errors (if any)"
echo "================================"
if grep -E "FAIL|ERROR|AssertionError" "$LOG_FILE" > /dev/null 2>&1; then
    grep -A 5 -E "FAIL|ERROR|AssertionError" "$LOG_FILE" | tail -50
else
    echo "No failures or errors found"
fi

echo ""
echo "📋 Test Summary (if available)"
echo "=============================="
if grep -E "^Ran.*test" "$LOG_FILE" > /dev/null 2>&1; then
    grep -E "^Ran.*test|^OK|^FAILED" "$LOG_FILE" | tail -5
else
    echo "Test summary not yet available (tests may still be running)"
fi

echo ""
echo "📁 Full log: $LOG_FILE"
echo "Monitor with: tail -f $LOG_FILE"
