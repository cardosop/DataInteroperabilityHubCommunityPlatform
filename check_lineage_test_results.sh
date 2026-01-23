#!/bin/bash
# Check lineage test results

LOG_FILE="/tmp/lineage_tests_full.log"

echo "Checking lineage test execution status..."
echo "========================================"

if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found: $LOG_FILE"
    exit 1
fi

# Check if tests have started
if grep -q "test_contract_lineage\|test_field_lineage\|test_hierarchical\|test_impact\|test_odps" "$LOG_FILE" 2>/dev/null; then
    echo "✅ Tests have started executing"
    echo ""
    echo "Test execution summary:"
    grep -E "^(test_|Ran|FAILED|ERROR|OK)" "$LOG_FILE" | tail -50
else
    echo "⏳ Tests are still setting up (migrations running)..."
    echo ""
    echo "Last log entries:"
    tail -20 "$LOG_FILE" | grep -v "timestamp\|level\|logger\|message" | tail -10
fi

echo ""
echo "Checking for failures..."
if grep -q "FAILED\|ERROR\|AssertionError\|Exception" "$LOG_FILE" 2>/dev/null; then
    echo "❌ Failures found:"
    grep -A 10 "FAILED\|ERROR\|AssertionError" "$LOG_FILE" | head -100
else
    echo "✅ No failures found yet"
fi

echo ""
echo "Checking for test completion..."
if grep -q "^Ran" "$LOG_FILE" 2>/dev/null; then
    echo "✅ Tests completed!"
    grep "^Ran" "$LOG_FILE" | tail -1
else
    echo "⏳ Tests still running..."
fi
