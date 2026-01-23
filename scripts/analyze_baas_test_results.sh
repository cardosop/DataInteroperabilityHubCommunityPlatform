#!/bin/bash
# Script to analyze BaaS Platform Comprehensive Validation test results

LOG_FILE="/tmp/baas_test_full_output.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "Test log file not found: $LOG_FILE"
    exit 1
fi

echo "=== BaaS Platform Comprehensive Validation Test Results ==="
echo ""

# Extract test summary
echo "Test Summary:"
grep -E "^Ran|^FAILED|^ERROR|^OK$" "$LOG_FILE" | tail -5
echo ""

# Extract all test results
echo "All Test Results:"
grep -E "^test_.*\.\.\." "$LOG_FILE" | sort
echo ""

# Count results
TOTAL=$(grep -c "^test_.*\.\.\." "$LOG_FILE" || echo "0")
PASSED=$(grep -c "^test_.*\.\.\..*ok$" "$LOG_FILE" || echo "0")
FAILED=$(grep -c "^test_.*\.\.\..*FAIL$" "$LOG_FILE" || echo "0")
ERRORS=$(grep -c "^test_.*\.\.\..*ERROR$" "$LOG_FILE" || echo "0")
SKIPPED=$(grep -c "^test_.*\.\.\..*skipped$" "$LOG_FILE" || echo "0")

echo "=== Statistics ==="
echo "Total Tests: $TOTAL"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Errors: $ERRORS"
echo "Skipped: $SKIPPED"
echo ""

# Show failed/error tests
if [ "$FAILED" -gt 0 ] || [ "$ERRORS" -gt 0 ]; then
    echo "=== Failed/Error Tests ==="
    grep -E "^test_.*\.\.\..*(FAIL|ERROR)" "$LOG_FILE"
    echo ""

    echo "=== Error Details (first 5) ==="
    grep -B 5 -A 20 "Traceback\|AssertionError\|Exception:" "$LOG_FILE" | head -100
fi
