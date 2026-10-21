#!/bin/bash
# Run E2E tests in smaller batches by module to prevent timeouts and stuck tests
# NOTE: Django's test runner runs all tests when given multiple module arguments,
# so we run tests one module at a time, but group them into batches for reporting.

# Use set -e but allow functions to handle errors gracefully
set -e
# Temporarily disable exit on error for function calls that check return codes
set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Configuration
TIMEOUT_PER_MODULE=600  # 10 minutes per module
MAX_BATCH_SIZE=5        # Number of modules to group in a batch for reporting
LOG_DIR="/tmp/e2e_batch_logs"
mkdir -p "$LOG_DIR"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "E2E Tests - Batch Execution"
echo "=========================================="
echo ""

# Get list of E2E test files
echo "Discovering E2E test files..."
# Convert to array for more reliable iteration
mapfile -t TEST_FILES_ARRAY < <(find tests/e2e -name "test_*.py" -type f | sort)
TOTAL_TESTS=${#TEST_FILES_ARRAY[@]}
echo "Found $TOTAL_TESTS test files"
echo ""

# Run a single test module
run_test_module() {
    local test_file="$1"
    local module_num="$2"
    local batch_num="$3"
    local batch_size="$4"

    # Convert file path to Django test module path (tests/e2e/test_*.py -> tests.e2e.test_*)
    local module_path=$(echo "$test_file" | sed 's|\.py$||' | tr '/' '.')

    local module_log="$LOG_DIR/batch_${batch_num}_module_${module_num}_$(basename "$test_file" .py)_$(date +%Y%m%d_%H%M%S).log"

    echo "  [Module $module_num/$batch_size] Running: $module_path"

    # Run test module with timeout and monitor for stuck state
    # Set TEST_DB_SUFFIX to "default" to ensure --keepdb reuses the same database
    docker compose exec -T api-service bash -c "cd /app/hub && TEST_DB_SUFFIX=default timeout $TIMEOUT_PER_MODULE python manage.py test $module_path --verbosity=1 --keepdb --no-input 2>&1" > "$module_log" 2>&1 &
    local module_pid=$!

    # Monitor for stuck state (no log updates for 2 minutes)
    local last_log_size=0
    local stuck_count=0
    while kill -0 $module_pid 2>/dev/null; do
        sleep 30
        local current_log_size=$(stat -c %s "$module_log" 2>/dev/null || echo 0)
        if [ $current_log_size -eq $last_log_size ]; then
            stuck_count=$((stuck_count + 1))
            if [ $stuck_count -ge 4 ]; then
                echo "    ⚠️  Module appears stuck (no log updates for 2+ minutes), killing..."
                kill -9 $module_pid 2>/dev/null || true
                wait $module_pid 2>/dev/null
                return 124  # Timeout exit code
            fi
        else
            stuck_count=0
            last_log_size=$current_log_size
        fi
    done

    # Wait for process to finish
    wait $module_pid 2>/dev/null
    return $?
}

# Process a batch of test modules
process_batch() {
    local batch_num="$1"
    shift
    local batch_files=("$@")
    local batch_size=${#batch_files[@]}

    echo "=========================================="
    echo "Batch $batch_num: $batch_size module(s)"
    echo "=========================================="

    local batch_passed=0
    local batch_failed=0
    local module_num=1

    for test_file in "${batch_files[@]}"; do
        run_test_module "$test_file" "$module_num" "$batch_num" "$batch_size"
        local exit_code=$?

        if [ $exit_code -eq 0 ]; then
            echo -e "    ${GREEN}✅ Module $module_num: PASSED${NC}"
            batch_passed=$((batch_passed + 1))
        elif [ $exit_code -eq 124 ]; then
            echo -e "    ${RED}⏱️  Module $module_num: TIMEOUT${NC}"
            batch_failed=$((batch_failed + 1))
        else
            echo -e "    ${RED}❌ Module $module_num: FAILED (exit code: $exit_code)${NC}"
            batch_failed=$((batch_failed + 1))
        fi

        module_num=$((module_num + 1))
    done

    echo ""
    if [ $batch_failed -eq 0 ]; then
        echo -e "${GREEN}✅ Batch $batch_num: ALL PASSED ($batch_passed/$batch_size)${NC}"
        return 0
    else
        echo -e "${RED}❌ Batch $batch_num: SOME FAILED ($batch_passed passed, $batch_failed failed)${NC}"
        return 1
    fi
    echo ""
}

PASSED=0
FAILED=0
BATCH_NUM=1
BATCH_COUNT=0
declare -a CURRENT_BATCH=()

# Process test files one at a time, grouping into batches for reporting
# Use array iteration instead of heredoc for more reliable behavior
set -e
for test_file in "${TEST_FILES_ARRAY[@]}"; do
    # Add current file to batch first
    CURRENT_BATCH+=("$test_file")
    BATCH_COUNT=$((BATCH_COUNT + 1))

    # Temporarily disable exit on error for batch processing
    set +e
    if [ $BATCH_COUNT -ge $MAX_BATCH_SIZE ]; then
        if process_batch "$BATCH_NUM" "${CURRENT_BATCH[@]}"; then
            PASSED=$((PASSED + 1))
        else
            FAILED=$((FAILED + 1))
        fi
        BATCH_NUM=$((BATCH_NUM + 1))
        BATCH_COUNT=0
        # Explicitly clear array by unsetting and recreating
        unset CURRENT_BATCH
        CURRENT_BATCH=()
    fi
    set -e
done

# Process remaining batch
set +e
if [ ${#CURRENT_BATCH[@]} -gt 0 ]; then
    if process_batch "$BATCH_NUM" "${CURRENT_BATCH[@]}"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
fi
set -e

# Final summary
echo "=========================================="
echo "FINAL SUMMARY"
echo "=========================================="
echo "Total batches: $BATCH_NUM"
echo "Total test files: $TOTAL_TESTS"
echo -e "${GREEN}Batches passed: $PASSED${NC}"
echo -e "${RED}Batches failed: $FAILED${NC}"
echo ""
echo "Logs directory: $LOG_DIR"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All batches passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some batches failed${NC}"
    exit 1
fi
