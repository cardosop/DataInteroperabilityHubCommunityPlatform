#!/bin/bash
# Run Tests in Parallel Batches for Faster Execution

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

REPORT_DIR="test_reports_django6"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SUMMARY_FILE="${REPORT_DIR}/test_summary_parallel_${TIMESTAMP}.txt"
FAILURES_FILE="${REPORT_DIR}/test_failures_parallel_${TIMESTAMP}.txt"

# Number of parallel workers (adjust based on CPU cores)
PARALLEL_WORKERS=${PARALLEL_WORKERS:-4}

echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Parallel Test Suite Execution${RESET}"
echo -e "${BOLD}${BLUE}Using ${PARALLEL_WORKERS} parallel workers${RESET}"
echo -e "${BOLD}${BLUE}========================================${RESET}"
echo ""

cd "$(dirname "$0")/.." || exit 1

# Create report directory
mkdir -p "$REPORT_DIR"

# Check if virtual environment exists
if [ ! -d "venv-python312-test" ]; then
    echo -e "${RED}Error: Virtual environment 'venv-python312-test' not found${RESET}"
    exit 1
fi

# Activate virtual environment
source venv-python312-test/bin/activate

# Check Python version
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)"; then
    echo -e "${RED}Error: Python 3.12+ required${RESET}"
    exit 1
fi

# Check Django version
DJANGO_VERSION=$(python3 -c "import django; print(django.get_version())" 2>/dev/null || echo "not installed")
echo -e "${BLUE}Django version: ${DJANGO_VERSION}${RESET}"

# Set Django settings module and Python path
export DJANGO_SETTINGS_MODULE=hub.settings
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Initialize summary
echo "Parallel Test Execution Summary - $(date)" > "$SUMMARY_FILE"
echo "=======================================" >> "$SUMMARY_FILE"
echo "" >> "$SUMMARY_FILE"
echo "Django version: ${DJANGO_VERSION}" >> "$SUMMARY_FILE"
echo "Python version: $(python3 --version)" >> "$SUMMARY_FILE"
echo "Parallel workers: ${PARALLEL_WORKERS}" >> "$SUMMARY_FILE"
echo "" >> "$SUMMARY_FILE"

# Initialize failures file
echo "Test Failures - $(date)" > "$FAILURES_FILE"
echo "======================" >> "$FAILURES_FILE"
echo "" >> "$FAILURES_FILE"

# Function to run test suite in parallel
run_test_suite_parallel() {
    local suite_name=$1
    local test_path=$2
    local marker=$3
    
    echo -e "${BOLD}${BLUE}Running ${suite_name} (parallel)...${RESET}"
    echo "Running ${suite_name} (parallel)..." >> "$SUMMARY_FILE"
    
    local report_file="${REPORT_DIR}/${suite_name}_parallel_${TIMESTAMP}.txt"
    local exit_code=0
    local start_time=$(date +%s)
    
    # Run tests in parallel with pytest-xdist
    if [ -n "$marker" ]; then
        pytest "$test_path" -v --tb=short -m "$marker" -n "${PARALLEL_WORKERS}" --dist=worksteal > "$report_file" 2>&1 || exit_code=$?
    else
        pytest "$test_path" -v --tb=short -n "${PARALLEL_WORKERS}" --dist=worksteal > "$report_file" 2>&1 || exit_code=$?
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    # Extract test results
    local total=$(grep -E "test session starts|collected" "$report_file" | grep -oE "[0-9]+" | tail -1 || echo "0")
    local passed=$(grep -E "passed" "$report_file" | tail -1 | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" || echo "0")
    local failed=$(grep -E "failed" "$report_file" | tail -1 | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+" || echo "0")
    local skipped=$(grep -E "skipped" "$report_file" | tail -1 | grep -oE "[0-9]+ skipped" | grep -oE "[0-9]+" || echo "0")
    local errors=$(grep -E "error" "$report_file" | tail -1 | grep -oE "[0-9]+ error" | grep -oE "[0-9]+" || echo "0")
    
    if [ "$exit_code" -eq 0 ]; then
        echo -e "${GREEN}✅ ${suite_name}: ${passed} passed, ${skipped} skipped (${duration}s)${RESET}"
        echo "✅ ${suite_name}: ${passed} passed, ${skipped} skipped (${duration}s)" >> "$SUMMARY_FILE"
    else
        echo -e "${RED}❌ ${suite_name}: ${failed} failed, ${errors} errors, ${passed} passed, ${skipped} skipped (${duration}s)${RESET}"
        echo "❌ ${suite_name}: ${failed} failed, ${errors} errors, ${passed} passed, ${skipped} skipped (${duration}s)" >> "$SUMMARY_FILE"
        
        # Extract failure details
        echo "" >> "$FAILURES_FILE"
        echo "=== ${suite_name} Failures ===" >> "$FAILURES_FILE"
        grep -A 5 "FAILED\|ERROR" "$report_file" >> "$FAILURES_FILE" || true
    fi
    
    echo "Report: $report_file" >> "$SUMMARY_FILE"
    echo "Duration: ${duration}s" >> "$SUMMARY_FILE"
    echo "Total tests: ${total}" >> "$SUMMARY_FILE"
    echo "" >> "$SUMMARY_FILE"
    
    return $exit_code
}

# Check if pytest-xdist is installed
if ! python3 -c "import xdist" 2>/dev/null; then
    echo -e "${YELLOW}Installing pytest-xdist for parallel execution...${RESET}"
    pip install pytest-xdist > /dev/null 2>&1
fi

# Track overall status
OVERALL_STATUS=0
TOTAL_START_TIME=$(date +%s)

echo -e "${BOLD}${BLUE}Step 1: Run Unit Tests (Parallel)${RESET}"
run_test_suite_parallel "Unit Tests" "tests/unit/" "" || OVERALL_STATUS=1
echo ""

echo -e "${BOLD}${BLUE}Step 2: Run Integration Tests (Parallel)${RESET}"
run_test_suite_parallel "Integration Tests" "tests/integration/" "" || OVERALL_STATUS=1
echo ""

echo -e "${BOLD}${BLUE}Step 3: Run Regression Tests (Parallel)${RESET}"
run_test_suite_parallel "Regression Tests" "tests/regression/" "" || OVERALL_STATUS=1
echo ""

echo -e "${BOLD}${BLUE}Step 4: Run Security Tests (Parallel)${RESET}"
run_test_suite_parallel "Security Tests" "tests/security/" "" || OVERALL_STATUS=1
echo ""

echo -e "${BOLD}${BLUE}Step 5: Run Performance Tests (Parallel)${RESET}"
run_test_suite_parallel "Performance Tests" "tests/performance/" "" || OVERALL_STATUS=1
echo ""

echo -e "${BOLD}${BLUE}Step 6: Run E2E Tests (Parallel, Sample)${RESET}"
echo -e "${YELLOW}Note: E2E tests require services to be running${RESET}"
# E2E tests might need sequential execution due to service dependencies
# But we can still try parallel with fewer workers
PARALLEL_WORKERS=2 run_test_suite_parallel "E2E Tests" "tests/e2e/" "" || OVERALL_STATUS=1
echo ""

TOTAL_END_TIME=$(date +%s)
TOTAL_DURATION=$((TOTAL_END_TIME - TOTAL_START_TIME))

# Summary
echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Test Execution Summary${RESET}"
echo -e "${BOLD}${BLUE}Total Duration: ${TOTAL_DURATION}s ($(($TOTAL_DURATION / 60))m $(($TOTAL_DURATION % 60))s)${RESET}"
echo -e "${BOLD}${BLUE}========================================${RESET}"
cat "$SUMMARY_FILE"

echo "" >> "$SUMMARY_FILE"
echo "Total execution time: ${TOTAL_DURATION}s ($(($TOTAL_DURATION / 60))m $(($TOTAL_DURATION % 60))s)" >> "$SUMMARY_FILE"

if [ "$OVERALL_STATUS" -eq 0 ]; then
    echo -e "${BOLD}${GREEN}✅ All test suites passed!${RESET}"
    echo "" >> "$SUMMARY_FILE"
    echo "Status: ✅ ALL TESTS PASSED" >> "$SUMMARY_FILE"
else
    echo -e "${BOLD}${RED}❌ Some test suites failed${RESET}"
    echo "" >> "$SUMMARY_FILE"
    echo "Status: ❌ SOME TESTS FAILED" >> "$SUMMARY_FILE"
    echo "" >> "$SUMMARY_FILE"
    echo "See $FAILURES_FILE for failure summary" >> "$SUMMARY_FILE"
    echo -e "${YELLOW}See $FAILURES_FILE for failure summary${RESET}"
fi

echo ""
echo -e "${BLUE}Reports saved to: ${REPORT_DIR}/${RESET}"
echo -e "${BLUE}Summary: ${SUMMARY_FILE}${RESET}"
if [ "$OVERALL_STATUS" -ne 0 ]; then
    echo -e "${BLUE}Failures: ${FAILURES_FILE}${RESET}"
fi

deactivate

exit $OVERALL_STATUS

