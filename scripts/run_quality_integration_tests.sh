#!/bin/bash
# Script to run quality integration tests in Docker environment
# This ensures all services are accessible

set -e

echo "Running quality integration tests in Docker environment..."

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose not found. Please install docker-compose."
    exit 1
fi

# Check if test services are running
if ! docker-compose -f docker-compose.test.yml ps | grep -q "hub-test-api"; then
    echo "Starting test services..."
    docker-compose -f docker-compose.test.yml up -d

    echo "Waiting for services to be healthy..."
    sleep 30
fi

# Run tests inside the API service container where all services are accessible
echo "Running tests inside Docker container..."
docker-compose -f docker-compose.test.yml exec -T api-service-test bash -c "
    cd /app && \
    source venv/bin/activate && \
    python -m pytest hub/apps/transformation/tests/test_quality_integration.py -v --tb=short
"

echo "Tests completed!"

