#!/bin/bash
# Run Phase 7 Comprehensive Tests (No Mocks)
# Tests validate scheduled ingestion with real services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

echo "=========================================="
echo "Phase 7 Comprehensive Tests (No Mocks)"
echo "=========================================="
echo ""

# Check if services are running
echo "Checking Docker Compose services..."
if ! docker compose ps api-service | grep -q "Up"; then
    echo "ERROR: api-service is not running. Start services with: docker compose up -d"
    exit 1
fi

echo "Running Phase 7 comprehensive tests..."
echo ""

# Run backend unit tests (7.1.1)
echo "=== 7.1.1 Backend Unit Tests ==="
PYTEST_TIMEOUT="${PYTEST_TIMEOUT:-1800}"
docker compose exec -T api-service bash -c "
    cd /app && \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    python -m pytest \
        hub/apps/scheduled_ingestion/tests/test_phase7_comprehensive.py::TestAPIHandlersUnitTests \
        -v \
        --tb=short \
        --timeout=${PYTEST_TIMEOUT} \
        --reuse-db \
        -m integration
"

UNIT_EXIT=$?

# Run no mocks verification (7.1.2)
echo ""
echo "=== 7.1.2 No Mocks Verification ==="
PYTEST_TIMEOUT="${PYTEST_TIMEOUT:-1800}"
docker compose exec -T api-service bash -c "
    cd /app && \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    python -m pytest \
        hub/apps/scheduled_ingestion/tests/test_phase7_comprehensive.py::TestNoMocksVerification \
        -v \
        --tb=short \
        --timeout=${PYTEST_TIMEOUT} \
        --reuse-db \
        -m integration
"

NOMOCKS_EXIT=$?

# Run full path integration tests (7.2.1)
echo ""
echo "=== 7.2.1 Full Path Integration Tests ==="
PYTEST_TIMEOUT="${PYTEST_TIMEOUT:-1800}"
docker compose exec -T api-service bash -c "
    cd /app && \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    python -m pytest \
        hub/apps/scheduled_ingestion/tests/test_phase7_comprehensive.py::TestFullPathIntegration \
        -v \
        --tb=short \
        --timeout=${PYTEST_TIMEOUT} \
        --reuse-db \
        -m integration
"

INTEGRATION_EXIT=$?

# Summary
echo ""
echo "=========================================="
if [ $UNIT_EXIT -eq 0 ] && [ $NOMOCKS_EXIT -eq 0 ] && [ $INTEGRATION_EXIT -eq 0 ]; then
    echo "✓ Phase 7 Comprehensive Tests PASSED"
    echo "=========================================="
    exit 0
else
    echo "✗ Phase 7 Comprehensive Tests FAILED"
    echo "=========================================="
    echo "Unit Tests: $([ $UNIT_EXIT -eq 0 ] && echo 'PASSED' || echo 'FAILED')"
    echo "No Mocks Verification: $([ $NOMOCKS_EXIT -eq 0 ] && echo 'PASSED' || echo 'FAILED')"
    echo "Integration Tests: $([ $INTEGRATION_EXIT -eq 0 ] && echo 'PASSED' || echo 'FAILED')"
    exit 1
fi
