#!/bin/bash
# Script to run Data Mesh Service Comprehensive Validation Tests
# This ensures all services are accessible and tests run properly

set -e

echo "=========================================="
echo "Data Mesh Service Comprehensive Validation"
echo "Test Runner"
echo "=========================================="
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

TEST_OUTPUT="/tmp/mesh_test_results_$(date +%s).txt"

docker compose exec -T api-service bash -c \
  "cd /app && python -m pytest hub/apps/mesh/tests/test_data_mesh_service_comprehensive_validation.py -v --tb=short 2>&1" | tee "$TEST_OUTPUT"

# Extract summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo ""

if grep -q "PASSED\|FAILED\|ERROR" "$TEST_OUTPUT"; then
    echo "Test Results:"
    grep -E "PASSED|FAILED|ERROR|SKIPPED" "$TEST_OUTPUT" | tail -20
fi

if grep -q "^FAILED\|^ERROR" "$TEST_OUTPUT"; then
    echo ""
    echo "❌ Some tests failed. See full output above."
    exit 1
elif grep -q "passed" "$TEST_OUTPUT"; then
    echo ""
    echo "✅ All tests passed!"
    exit 0
else
    echo ""
    echo "⚠️  Could not determine test status. See full output above."
    exit 1
fi
