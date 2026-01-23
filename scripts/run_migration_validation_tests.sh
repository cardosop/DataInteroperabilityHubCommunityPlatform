#!/bin/bash
# Script to run migration validation tests (Task 10.1.21)
# These tests validate:
# - 10.1.21.1: Migration Validation Testing
# - 10.1.21.2: Migration Rollback Testing  
# - 10.1.21.3.1: Test Data Setup & Teardown
# - 10.1.21.3.2: Test Data Seeding
# - 10.1.21.4: Test Environment Validation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "Running Migration Validation Tests"
echo "=========================================="
echo ""

cd "$PROJECT_ROOT"

# Check if docker compose is available
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo "Error: docker-compose or docker compose not found"
    exit 1
fi

# Check if services are running
if ! $DOCKER_COMPOSE ps api-service | grep -q "Up"; then
    echo "Error: api-service is not running. Please start services with: $DOCKER_COMPOSE up -d"
    exit 1
fi

echo "Installing pytest-django and pytest-asyncio if needed..."
$DOCKER_COMPOSE exec -T api-service pip install -q pytest-django pytest-asyncio || true

echo ""
echo "Running test files..."
echo ""

# Test files to run
TEST_FILES=(
    "hub/apps/contracts/tests/test_migration_validation_comprehensive.py"
    "hub/apps/contracts/tests/test_migration_rollback_comprehensive.py"
    "hub/apps/contracts/tests/test_data_setup_teardown.py"
    "hub/apps/contracts/tests/test_data_seeding.py"
    "hub/apps/contracts/tests/test_environment_validation_comprehensive.py"
)

FAILED_TESTS=()
PASSED_TESTS=()
SKIPPED_TESTS=()

for test_file in "${TEST_FILES[@]}"; do
    echo "----------------------------------------"
    echo "Running: $test_file"
    echo "----------------------------------------"
    
    if $DOCKER_COMPOSE exec -w /app -T api-service python -m pytest "$test_file" -v --tb=short --maxfail=1 -x 2>&1 | tee /tmp/test_output.log; then
        PASSED_TESTS+=("$test_file")
        echo "✓ PASSED: $test_file"
    else
        EXIT_CODE=$?
        if grep -q "SKIPPED" /tmp/test_output.log; then
            SKIPPED_TESTS+=("$test_file")
            echo "⚠ SKIPPED: $test_file"
        else
            FAILED_TESTS+=("$test_file")
            echo "✗ FAILED: $test_file (exit code: $EXIT_CODE)"
        fi
    fi
    echo ""
done

echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Passed: ${#PASSED_TESTS[@]}"
echo "Failed: ${#FAILED_TESTS[@]}"
echo "Skipped: ${#SKIPPED_TESTS[@]}"
echo ""

if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
    echo "Failed tests:"
    for test in "${FAILED_TESTS[@]}"; do
        echo "  - $test"
    done
    echo ""
    exit 1
fi

if [ ${#SKIPPED_TESTS[@]} -gt 0 ]; then
    echo "Skipped tests:"
    for test in "${SKIPPED_TESTS[@]}"; do
        echo "  - $test"
    done
    echo ""
fi

echo "All tests passed!"
exit 0
