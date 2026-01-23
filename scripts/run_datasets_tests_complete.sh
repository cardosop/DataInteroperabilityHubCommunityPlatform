#!/bin/bash
# Complete test runner for Datasets Service Comprehensive Validation
# This script runs tests and captures all results for analysis

set -e

OUTPUT_DIR="/tmp/datasets_test_results_$(date +%s)"
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "Datasets Service Comprehensive Validation"
echo "Test Execution"
echo "=========================================="
echo ""
echo "Output directory: $OUTPUT_DIR"
echo ""

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

# Check if services are running
if ! docker compose ps | grep -q "api-service.*Up"; then
    echo "⚠️  API service doesn't appear to be running"
    echo "   Starting services..."
    docker compose up -d api-service
    echo "   Waiting for service to be ready..."
    sleep 10
fi

echo "✅ Services are running"
echo ""

# Run tests with full output capture
echo "Running comprehensive validation tests..."
echo "This may take 5-10 minutes on first run (database migrations)..."
echo ""

TEST_OUTPUT="$OUTPUT_DIR/full_test_output.txt"
SUMMARY_OUTPUT="$OUTPUT_DIR/test_summary.txt"

docker compose exec -T api-service bash -c \
  "cd /app && python hub/manage.py test \
   hub.apps.datasets.tests.test_datasets_service_comprehensive_validation \
   --verbosity=2 --keepdb --no-input 2>&1" | tee "$TEST_OUTPUT"

# Extract summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo ""

if grep -q "^Ran" "$TEST_OUTPUT"; then
    grep "^Ran" "$TEST_OUTPUT" | tee "$SUMMARY_OUTPUT"
fi

if grep -q "^OK" "$TEST_OUTPUT"; then
    echo ""
    echo "✅ Tests completed successfully!"
    grep "^OK" "$TEST_OUTPUT" | tail -1 | tee -a "$SUMMARY_OUTPUT"
    EXIT_CODE=0
elif grep -q "FAILED\|ERROR" "$TEST_OUTPUT"; then
    echo ""
    echo "❌ Some tests failed!"
    grep -E "FAILED|ERROR" "$TEST_OUTPUT" | head -10 | tee -a "$SUMMARY_OUTPUT"
    EXIT_CODE=1
else
    echo ""
    echo "⚠️  Could not determine test status"
    EXIT_CODE=2
fi

# Extract failures
if grep -q "FAILED\|ERROR" "$TEST_OUTPUT"; then
    echo ""
    echo "=========================================="
    echo "Failures and Errors"
    echo "=========================================="
    echo ""
    grep -A 10 -E "FAILED|ERROR" "$TEST_OUTPUT" | head -50 > "$OUTPUT_DIR/failures.txt"
    cat "$OUTPUT_DIR/failures.txt"
fi

echo ""
echo "=========================================="
echo "Full output saved to: $TEST_OUTPUT"
echo "Summary saved to: $SUMMARY_OUTPUT"
echo "=========================================="
echo ""

exit $EXIT_CODE
