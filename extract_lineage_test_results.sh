#!/bin/bash
# Extract final lineage test results

LOG_FILE="/tmp/lineage_tests_full.log"

echo "Lineage Test Results Summary"
echo "============================"
echo ""

# Check if tests completed
if grep -q "^Ran" "$LOG_FILE" 2>/dev/null; then
    echo "✅ Tests Completed"
    echo ""
    grep "^Ran" "$LOG_FILE" | tail -1
    echo ""
else
    echo "⏳ Tests Still Running"
    echo ""
    echo "Current Progress:"
    PASSED=$(grep -c "^ok$" "$LOG_FILE" 2>/dev/null || echo "0")
    echo "  Tests Passed: $PASSED"
    CURRENT=$(grep "^test_" "$LOG_FILE" 2>/dev/null | tail -1 || echo "None")
    echo "  Current Test: $CURRENT"
    echo ""
fi

# Count results
TOTAL=$(grep "^Ran" "$LOG_FILE" 2>/dev/null | grep -oE "[0-9]+ test" | grep -oE "[0-9]+" || echo "0")
FAILED=$(grep -c "FAILED" "$LOG_FILE" 2>/dev/null || echo "0")
ERROR=$(grep -c "ERROR" "$LOG_FILE" 2>/dev/null || echo "0")
OK=$(grep -c "^ok$" "$LOG_FILE" 2>/dev/null || echo "0")
SKIPPED=$(grep -c "skipped" "$LOG_FILE" 2>/dev/null || echo "0")

echo "Test Counts:"
echo "  Total: $TOTAL"
echo "  Passed: $OK"
echo "  Failed: $FAILED"
echo "  Errors: $ERROR"
echo "  Skipped: $SKIPPED"
echo ""

# List all test results
echo "Test Results:"
echo "============="
grep -E "^(test_|ok|FAILED|ERROR|skipped)" "$LOG_FILE" 2>/dev/null | tail -50
echo ""

# Show failures if any
if [ "$FAILED" -gt 0 ] || [ "$ERROR" -gt 0 ]; then
    echo "❌ Failures/Errors:"
    echo ""
    grep -B 5 -A 20 "FAILED\|ERROR" "$LOG_FILE" 2>/dev/null | head -200
    echo ""
fi

# Show skipped tests if any
if [ "$SKIPPED" -gt 0 ]; then
    echo "⚠️  Skipped Tests:"
    echo ""
    grep -B 2 -A 5 "skipped" "$LOG_FILE" 2>/dev/null | head -100
    echo ""
fi
