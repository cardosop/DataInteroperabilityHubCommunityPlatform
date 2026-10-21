#!/bin/bash
# Run Connection Validation Rules Tests
# This script runs the connection validation rules tests in docker compose

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "=========================================="
echo "Connection Validation Rules Test Runner"
echo "=========================================="
echo ""

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

# Check if services are running
if ! docker compose ps | grep -q "Up"; then
    echo "⚠️  Docker services don't appear to be running"
    echo "   Starting services..."
    docker compose up -d postgres redis-cache
    echo "   Waiting for services to be ready..."
    sleep 5
fi

# Check if web service exists
if ! docker compose ps web &> /dev/null; then
    echo "⚠️  'web' service not found. Trying 'api-service'..."
    SERVICE_NAME="api-service"
else
    SERVICE_NAME="web"
fi

echo "Using service: $SERVICE_NAME"
echo ""

# Run unit tests
echo "=========================================="
echo "Running Unit Tests"
echo "=========================================="
echo ""

if docker compose exec -T "$SERVICE_NAME" python manage.py test \
    hub.apps.integrations.tests.test_connection_validation_rules \
    --verbosity=2 \
    --keepdb; then
    echo ""
    echo "✅ Unit tests passed!"
    UNIT_TEST_RESULT=0
else
    echo ""
    echo "❌ Unit tests failed!"
    UNIT_TEST_RESULT=1
fi

echo ""
echo "=========================================="
echo "Running Integration Tests"
echo "=========================================="
echo ""

if docker compose exec -T "$SERVICE_NAME" python manage.py test \
    hub.apps.integrations.tests.test_connection_validation_integration \
    --verbosity=2 \
    --keepdb; then
    echo ""
    echo "✅ Integration tests passed!"
    INTEGRATION_TEST_RESULT=0
else
    echo ""
    echo "❌ Integration tests failed!"
    INTEGRATION_TEST_RESULT=1
fi

echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo ""

if [ $UNIT_TEST_RESULT -eq 0 ] && [ $INTEGRATION_TEST_RESULT -eq 0 ]; then
    echo "✅ All tests passed!"
    exit 0
else
    echo "❌ Some tests failed"
    echo "   Unit Tests: $([ $UNIT_TEST_RESULT -eq 0 ] && echo 'PASS' || echo 'FAIL')"
    echo "   Integration Tests: $([ $INTEGRATION_TEST_RESULT -eq 0 ] && echo 'PASS' || echo 'FAIL')"
    exit 1
fi

