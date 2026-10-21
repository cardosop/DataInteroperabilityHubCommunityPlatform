#!/bin/bash
# Script to run Data Mesh Service Comprehensive Validation Tests with proper timeout
# This script handles the long database setup time and captures all results

set -e

echo "=========================================="
echo "Data Mesh Service Comprehensive Validation"
echo "Test Execution with Extended Timeout"
echo "=========================================="
echo ""
echo "Note: First run may take 5-10 minutes due to database setup"
echo "Subsequent runs will be faster with --reuse-db"
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

# Create output directory
OUTPUT_DIR="/tmp/mesh_test_results_$(date +%s)"
mkdir -p "$OUTPUT_DIR"
TEST_OUTPUT="$OUTPUT_DIR/full_output.txt"
SUMMARY_OUTPUT="$OUTPUT_DIR/summary.txt"

echo "Running comprehensive validation tests..."
echo "Output will be saved to: $TEST_OUTPUT"
echo "This may take 10-15 minutes on first run..."
echo ""

# Run tests with extended timeout (15 minutes)
timeout 900 docker compose exec -T api-service bash -c \
  "cd /app && python -m pytest hub/apps/mesh/tests/test_data_mesh_service_comprehensive_validation.py -v --tb=short 2>&1" | tee "$TEST_OUTPUT"

EXIT_CODE=${PIPESTATUS[0]}

# Extract summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo ""

# Count results
PASSED=$(grep -c "PASSED" "$TEST_OUTPUT" 2>/dev/null || echo "0")
FAILED=$(grep -c "FAILED" "$TEST_OUTPUT" 2>/dev/null || echo "0")
ERROR=$(grep -c "ERROR" "$TEST_OUTPUT" 2>/dev/null || echo "0")
SKIPPED=$(grep -c "SKIPPED" "$TEST_OUTPUT" 2>/dev/null || echo "0")

echo "Test Results:" | tee "$SUMMARY_OUTPUT"
echo "  PASSED:  $PASSED" | tee -a "$SUMMARY_OUTPUT"
echo "  FAILED:  $FAILED" | tee -a "$SUMMARY_OUTPUT"
echo "  ERROR:   $ERROR" | tee -a "$SUMMARY_OUTPUT"
echo "  SKIPPED: $SKIPPED" | tee -a "$SUMMARY_OUTPUT"
echo ""

# Show failures if any
if [ "$FAILED" -gt 0 ] || [ "$ERROR" -gt 0 ]; then
    echo "=========================================="
    echo "Failures and Errors:"
    echo "=========================================="
    grep -A 20 "FAILED\|ERROR" "$TEST_OUTPUT" | head -100
    echo ""
    echo "Full output saved to: $TEST_OUTPUT"
    exit 1
elif [ "$PASSED" -gt 0 ]; then
    echo "✅ Tests completed successfully!"
    echo "Full output saved to: $TEST_OUTPUT"
    exit 0
else
    echo "⚠️  No test results found. Check full output: $TEST_OUTPUT"
    exit 1
fi
