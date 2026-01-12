#!/bin/bash
# Run API Gateway tests in Docker Compose

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_DIR"

echo "=========================================="
echo "API Gateway Test Runner"
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
    echo "   Starting required services..."
    docker compose up -d postgres redis-cache api-gateway
    echo "   Waiting for services to be ready..."
    sleep 10
fi

echo "Running API Gateway tests..."
echo ""

# Run tests with proper environment variables
docker compose run --rm --no-deps \
  -e POSTGRES_HOST=postgres \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_USER=hub \
  -e POSTGRES_PASSWORD=hub_secure \
  -e POSTGRES_DB=hub \
  -e DATABASE_URL=postgresql://hub:hub_secure@postgres:5432/hub \
  -e REDIS_CACHE_URL=redis://redis-cache:6379/0 \
  -e USE_PRODUCTION_DB_FOR_SDK_TESTS=1 \
  api-gateway python -m pytest services/api-gateway/tests/ -v --tb=short "$@"

echo ""
echo "✅ Tests completed!"
