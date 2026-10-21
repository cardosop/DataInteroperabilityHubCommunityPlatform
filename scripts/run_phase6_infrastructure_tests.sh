#!/bin/bash
# Run Phase 6 Infrastructure Validation Tests
# Tests validate Prefect worker infrastructure configuration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

echo "=========================================="
echo "Phase 6 Infrastructure Validation Tests"
echo "=========================================="
echo ""

# Check if services are running
echo "Checking Docker Compose services..."
if ! docker compose ps api-service | grep -q "Up"; then
    echo "ERROR: api-service is not running. Start services with: docker compose up -d"
    exit 1
fi

# Check if prefect-worker is configured (optional - may not be running)
if docker compose ps prefect-worker 2>/dev/null | grep -q "Up"; then
    echo "✓ prefect-worker is running"
    echo "Checking prefect-worker environment variables..."
    docker compose exec -T prefect-worker env | grep -E "HUB_BASE_URL|HUB_WORKER_API_KEY" || echo "WARNING: HUB_BASE_URL or HUB_WORKER_API_KEY not set in prefect-worker"
else
    echo "NOTE: prefect-worker is not running (this is OK for infrastructure tests)"
fi

echo ""
echo "Running Phase 6 infrastructure tests..."
echo ""

# Run tests with appropriate timeout
PYTEST_TIMEOUT="${PYTEST_TIMEOUT:-600}"
docker compose exec -T api-service bash -c "
    cd /app && \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    python -m pytest \
        hub/apps/scheduled_ingestion/tests/test_phase6_infrastructure.py \
        -v \
        --tb=short \
        --timeout=${PYTEST_TIMEOUT} \
        --reuse-db \
        -m integration
"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ Phase 6 Infrastructure Tests PASSED"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "✗ Phase 6 Infrastructure Tests FAILED"
    echo "=========================================="
fi

exit $EXIT_CODE
