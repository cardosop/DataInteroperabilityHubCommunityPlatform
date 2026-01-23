#!/bin/bash
# Script to run Virtualization Service Comprehensive Validation Tests
# Task 10.1.34

set -e

TEST_FILE="tests/integration/test_virtualization_service_comprehensive_validation.py"
OUTPUT_DIR="tests/integration/virtualization_test_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="${OUTPUT_DIR}/test_results_${TIMESTAMP}.log"

mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "Running Virtualization Service Comprehensive Validation Tests"
echo "Task: 10.1.34"
echo "Test File: $TEST_FILE"
echo "Output: $OUTPUT_FILE"
echo "=========================================="
echo ""

# Run tests using Django test runner
docker compose exec -T api-service bash -c \
  "cd /app && python hub/manage.py test \
    tests.integration.test_virtualization_service_comprehensive_validation \
    --verbosity=2 \
    --keepdb \
    --no-input \
    --failfast" \
  2>&1 | tee "$OUTPUT_FILE"

EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "=========================================="
echo "Test execution completed"
echo "Exit code: $EXIT_CODE"
echo "Output saved to: $OUTPUT_FILE"
echo "=========================================="

# Extract summary
echo ""
echo "=== Test Summary ==="
grep -E "(FAILED|ERROR|OK|PASSED|skipped)" "$OUTPUT_FILE" | tail -20 || true

exit $EXIT_CODE
