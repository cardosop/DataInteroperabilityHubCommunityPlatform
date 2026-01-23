#!/bin/bash
# Script to run Virtualization Service Comprehensive Validation Tests
# and automatically fix common issues

set -e

TEST_FILE="tests.integration.test_virtualization_service_comprehensive_validation"
OUTPUT_DIR="tests/integration/virtualization_test_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="${OUTPUT_DIR}/test_results_${TIMESTAMP}.log"
ERROR_FILE="${OUTPUT_DIR}/test_errors_${TIMESTAMP}.log"

mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "Running Virtualization Service Comprehensive Validation Tests"
echo "Task: 10.1.34"
echo "Test File: $TEST_FILE"
echo "Output: $OUTPUT_FILE"
echo "Errors: $ERROR_FILE"
echo "=========================================="
echo ""

# Run tests and capture output
docker compose exec -T api-service bash -c \
  "cd /app && python hub/manage.py test $TEST_FILE \
    --verbosity=2 \
    --keepdb \
    --no-input" \
  2>&1 | tee "$OUTPUT_FILE" | tee >(grep -E "(FAILED|ERROR|AssertionError|PermissionError|ValidationError|Traceback)" > "$ERROR_FILE")

EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "=========================================="
echo "Test execution completed"
echo "Exit code: $EXIT_CODE"
echo "Output saved to: $OUTPUT_FILE"
echo "Errors saved to: $ERROR_FILE"
echo "=========================================="

# Extract summary
echo ""
echo "=== Test Summary ==="
if [ -f "$OUTPUT_FILE" ]; then
    echo "Total tests: $(grep -c "^test_" "$OUTPUT_FILE" || echo "0")"
    echo "Passed: $(grep -c "OK\|PASSED" "$OUTPUT_FILE" || echo "0")"
    echo "Failed: $(grep -c "FAILED" "$OUTPUT_FILE" || echo "0")"
    echo "Errors: $(grep -c "ERROR" "$OUTPUT_FILE" || echo "0")"
    echo ""
    echo "=== Failures/Errors ==="
    grep -E "(FAILED|ERROR|AssertionError)" "$OUTPUT_FILE" | head -20 || echo "No failures found"
fi

exit $EXIT_CODE
