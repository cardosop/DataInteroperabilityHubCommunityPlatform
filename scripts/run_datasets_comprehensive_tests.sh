#!/bin/bash
# Script to run Datasets Service Comprehensive Validation Tests
# This ensures all services are accessible and tests run properly

set -e

echo "=========================================="
echo "Datasets Service Comprehensive Validation"
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

# Determine test scope
TEST_SCOPE="${1:-all}"

case "$TEST_SCOPE" in
    all)
        TEST_PATH="hub.apps.datasets.tests.test_datasets_service_comprehensive_validation"
        echo "Running all comprehensive validation tests..."
        ;;
    crud)
        TEST_PATH="hub.apps.datasets.tests.test_datasets_service_comprehensive_validation.TestDatasetCRUDOperations"
        echo "Running CRUD operations tests..."
        ;;
    versioning)
        TEST_PATH="hub.apps.datasets.tests.test_datasets_service_comprehensive_validation.TestDatasetVersioning"
        echo "Running versioning tests..."
        ;;
    schema)
        TEST_PATH="hub.apps.datasets.tests.test_datasets_service_comprehensive_validation.TestSchemaEvolution"
        echo "Running schema evolution tests..."
        ;;
    timetravel)
        TEST_PATH="hub.apps.datasets.tests.test_datasets_service_comprehensive_validation.TestTimeTravelQueries"
        echo "Running time travel query tests..."
        ;;
    rollback)
        TEST_PATH="hub.apps.datasets.tests.test_datasets_service_comprehensive_validation.TestDatasetRollback"
        echo "Running rollback tests..."
        ;;
    odps)
        TEST_PATH="hub.apps.datasets.tests.test_datasets_service_comprehensive_validation.TestDatasetsODPSIntegration"
        echo "Running ODPS integration tests..."
        ;;
    *)
        echo "Usage: $0 [all|crud|versioning|schema|timetravel|rollback|odps]"
        exit 1
        ;;
esac

echo ""

# Run tests
echo "=========================================="
echo "Running Tests"
echo "=========================================="
echo ""

if docker compose exec -T api-service bash -c \
    "cd /app && python hub/manage.py test $TEST_PATH \
     --verbosity=2 --keepdb --no-input"; then
    echo ""
    echo "✅ All tests passed!"
    exit 0
else
    echo ""
    echo "❌ Some tests failed!"
    exit 1
fi
