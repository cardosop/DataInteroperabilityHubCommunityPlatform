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

# Run tests using Django's test runner (better for TransactionTestCase)
echo "=========================================="
echo "Running Comprehensive Validation Tests"
echo "=========================================="
echo ""

# Run all test classes
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

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

for test_class in "${TEST_CLASSES[@]}"; do
    echo "Running $test_class..."

    if docker compose exec -T api-service bash -c \
        "cd /app && python hub/manage.py test \
        hub.apps.integrations.tests.test_marketplace_integration_service_comprehensive_validation.$test_class \
        --verbosity=1 --keepdb --no-input" 2>&1 | tee /tmp/marketplace_test_${test_class}.log; then
        echo "✅ $test_class: PASSED"
        ((PASSED_TESTS++))
    else
        echo "❌ $test_class: FAILED"
        ((FAILED_TESTS++))
    fi

    echo ""
done

echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Total Test Classes: ${#TEST_CLASSES[@]}"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo "✅ All test classes passed!"
    exit 0
else
    echo "❌ Some test classes failed. Check logs in /tmp/marketplace_test_*.log"
    exit 1
fi
