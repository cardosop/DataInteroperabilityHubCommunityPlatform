#!/bin/bash
# Script to run Marketplace Integration Comprehensive Validation Tests
# Task: 10.1.36 Marketplace Integration Service Comprehensive Validation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "=========================================="
echo "Marketplace Integration Comprehensive Validation Tests"
echo "Task: 10.1.36"
echo "=========================================="
echo ""

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

# Check if services are running
if ! docker compose ps api-service | grep -q "Up"; then
    echo "⚠️  API service is not running"
    echo "   Please start services: docker compose up -d"
    exit 1
fi

echo "✅ Services are running"
echo ""

# Create output directory
OUTPUT_DIR="/tmp/marketplace_test_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo "Output directory: $OUTPUT_DIR"
echo ""

# Run tests using Django's test runner (better for TransactionTestCase)
echo "=========================================="
echo "Running Comprehensive Validation Tests"
echo "=========================================="
echo ""
echo "Note: First run may take 10-15 minutes due to database migrations"
echo "Subsequent runs will be faster with --keepdb"
echo ""

# Run all test classes sequentially
TEST_CLASSES=(
    "ConnectionManagementTest"
    "SyncJobTest"
    "MappingManagementTest"
    "ConnectorTest"
    "MetadataMappingTest"
    "MarketplaceIntegrationAPITest"
    "MarketplaceIntegrationEventSystemTest"
    "MarketplaceIntegrationPerformanceTest"
    "MarketplaceIntegrationSecurityTest"
    "MarketplaceIntegrationUseCasesTest"
    "MarketplaceIntegrationUserJourneysTest"
    "MarketplaceIntegrationDatabaseStateTest"
    "MarketplaceIntegrationMultiTenancyTest"
    "MarketplaceIntegrationErrorHandlingTest"
    "MarketplaceIntegrationODPSTest"
)

TOTAL_TESTS=${#TEST_CLASSES[@]}
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

for test_class in "${TEST_CLASSES[@]}"; do
    echo "----------------------------------------"
    echo "Running $test_class..."
    echo "----------------------------------------"

    TEST_OUTPUT="$OUTPUT_DIR/${test_class}.log"

    if docker compose exec -T api-service bash -c \
        "cd /app && timeout 1800 python hub/manage.py test \
        hub.apps.integrations.tests.test_marketplace_integration_service_comprehensive_validation.$test_class \
        --verbosity=2 --keepdb --no-input" 2>&1 | tee "$TEST_OUTPUT"; then
        echo "✅ $test_class: PASSED"
        ((PASSED_TESTS++))
    else
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            echo "⏱️  $test_class: TIMEOUT (test took longer than 10 minutes)"
            ((FAILED_TESTS++))
        else
            echo "❌ $test_class: FAILED"
            ((FAILED_TESTS++))
        fi
    fi

    echo ""
done

echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Total Test Classes: $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"
echo "Skipped: $SKIPPED_TESTS"
echo ""
echo "Detailed logs available in: $OUTPUT_DIR"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo "✅ All test classes passed!"
    exit 0
else
    echo "❌ Some test classes failed. Check logs in $OUTPUT_DIR"
    echo ""
    echo "To view failures:"
    echo "  grep -r 'FAIL\|ERROR\|AssertionError' $OUTPUT_DIR"
    exit 1
fi
