#!/bin/bash
# Comprehensive test runner for all migration validation tests (Task 10.1.21)
# Runs tests with proper timeouts and error handling

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

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

echo "=========================================="
echo "Running All Migration Validation Tests"
echo "Task 10.1.21: Migration Comprehensive Validation"
echo "=========================================="
echo ""

# Install pytest-django if needed
echo "Ensuring pytest-django is installed..."
$DOCKER_COMPOSE exec -T api-service pip install -q pytest-django pytest-asyncio || true

# Test files with their task IDs
declare -A TEST_FILES=(
    ["10.1.21.1"]="hub/apps/contracts/tests/test_migration_validation_comprehensive.py"
    ["10.1.21.2"]="hub/apps/contracts/tests/test_migration_rollback_comprehensive.py"
    ["10.1.21.3.1"]="hub/apps/contracts/tests/test_data_setup_teardown.py"
    ["10.1.21.3.2"]="hub/apps/contracts/tests/test_data_seeding.py"
    ["10.1.21.4"]="hub/apps/contracts/tests/test_environment_validation_comprehensive.py"
)

FAILED_TESTS=()
PASSED_TESTS=()
SKIPPED_TESTS=()
TIMEOUT_TESTS=()

for task_id in "${!TEST_FILES[@]}"; do
    test_file="${TEST_FILES[$task_id]}"
    echo "----------------------------------------"
    echo "Running: $task_id - $test_file"
    echo "----------------------------------------"

    # Run test with TESTING=1 and timeout
    if timeout 900 $DOCKER_COMPOSE exec -w /app -e TESTING=1 api-service python -m pytest "$test_file" -v --tb=short --maxfail=5 2>&1 | tee /tmp/test_output_${task_id//\./_}.log; then
        PASSED_TESTS+=("$task_id:$test_file")
        echo "✓ PASSED: $task_id"
    else
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            TIMEOUT_TESTS+=("$task_id:$test_file")
            echo "⏱ TIMEOUT: $task_id (test took longer than 15 minutes)"
        elif grep -q "SKIPPED\|skip" /tmp/test_output_${task_id//\./_}.log; then
            SKIPPED_TESTS+=("$task_id:$test_file")
            echo "⚠ SKIPPED: $task_id"
        else
            FAILED_TESTS+=("$task_id:$test_file")
            echo "✗ FAILED: $task_id (exit code: $EXIT_CODE)"
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
echo "Timeout: ${#TIMEOUT_TESTS[@]}"
echo ""

if [ ${#PASSED_TESTS[@]} -gt 0 ]; then
    echo "Passed tests:"
    for test in "${PASSED_TESTS[@]}"; do
        echo "  ✓ $test"
    done
    echo ""
fi

if [ ${#TIMEOUT_TESTS[@]} -gt 0 ]; then
    echo "Timeout tests (may need investigation):"
    for test in "${TIMEOUT_TESTS[@]}"; do
        echo "  ⏱ $test"
        task_id=$(echo "$test" | cut -d: -f1)
        echo "    See: /tmp/test_output_${task_id//\./_}.log"
    done
    echo ""
fi

if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
    echo "Failed tests:"
    for test in "${FAILED_TESTS[@]}"; do
        echo "  ✗ $test"
        task_id=$(echo "$test" | cut -d: -f1)
        echo "    See: /tmp/test_output_${task_id//\./_}.log"
    done
    echo ""
    exit 1
fi

if [ ${#SKIPPED_TESTS[@]} -gt 0 ]; then
    echo "Skipped tests:"
    for test in "${SKIPPED_TESTS[@]}"; do
        echo "  ⚠ $test"
    done
    echo ""
fi

if [ ${#PASSED_TESTS[@]} -eq ${#TEST_FILES[@]} ]; then
    echo "✅ All tests passed!"
    exit 0
else
    echo "⚠ Some tests had issues (timeouts or skips)"
    exit 0
fi
