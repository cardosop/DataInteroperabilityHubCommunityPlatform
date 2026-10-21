#!/bin/bash
# Run All Test Suites with Django 6

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

REPORT_DIR="test_reports_django6"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SUMMARY_FILE="${REPORT_DIR}/test_summary_${TIMESTAMP}.txt"
FAILURES_FILE="${REPORT_DIR}/test_failures_${TIMESTAMP}.txt"

echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Run All Test Suites with Django 6${RESET}"
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

if [[ ! "$DJANGO_VERSION" =~ ^6\. ]]; then
    echo -e "${YELLOW}Warning: Django 6.0+ expected, but found ${DJANGO_VERSION}${RESET}"
fi

# Set Django settings module
export DJANGO_SETTINGS_MODULE=hub.settings

# Initialize summary
echo "Test Execution Summary - $(date)" > "$SUMMARY_FILE"
echo "=================================" >> "$SUMMARY_FILE"
echo "" >> "$SUMMARY_FILE"
echo "Django version: ${DJANGO_VERSION}" >> "$SUMMARY_FILE"
echo "Python version: $(python3 --version)" >> "$SUMMARY_FILE"
echo "" >> "$SUMMARY_FILE"

# Initialize failures file
echo "Test Failures - $(date)" > "$FAILURES_FILE"
echo "======================" >> "$FAILURES_FILE"
echo "" >> "$FAILURES_FILE"

# Function to run test suite
run_test_suite() {
    local suite_name=$1
    local test_path=$2
    local marker=$3
    
    echo -e "${BOLD}${BLUE}Running ${suite_name}...${RESET}"
    echo "Running ${suite_name}..." >> "$SUMMARY_FILE"
    
    local report_file="${REPORT_DIR}/${suite_name}_${TIMESTAMP}.txt"
    local exit_code=0
    
    if [ -n "$marker" ]; then
        pytest "$test_path" -v --tb=short -m "$marker" > "$report_file" 2>&1 || exit_code=$?
    else
        pytest "$test_path" -v --tb=short > "$report_file" 2>&1 || exit_code=$?
    fi
    
    # Extract test results
    local total=$(grep -E "passed|failed|skipped" "$report_file" | tail -1 | grep -oE "[0-9]+" | head -1 || echo "0")
    local passed=$(grep -E "passed" "$report_file" | tail -1 | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" || echo "0")
    local failed=$(grep -E "failed" "$report_file" | tail -1 | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+" || echo "0")
    local skipped=$(grep -E "skipped" "$report_file" | tail -1 | grep -oE "[0-9]+ skipped" | grep -oE "[0-9]+" || echo "0")
    
    if [ "$exit_code" -eq 0 ]; then
        echo -e "${GREEN}✅ ${suite_name}: ${passed} passed, ${skipped} skipped${RESET}"
        echo "✅ ${suite_name}: ${passed} passed, ${skipped} skipped" >> "$SUMMARY_FILE"
    else
        echo -e "${RED}❌ ${suite_name}: ${failed} failed, ${passed} passed, ${skipped} skipped${RESET}"
        echo "❌ ${suite_name}: ${failed} failed, ${passed} passed, ${skipped} skipped" >> "$SUMMARY_FILE"
        echo "" >> "$FAILURES_FILE"
        echo "=== ${suite_name} Failures ===" >> "$FAILURES_FILE"
        grep -A 10 "FAILED\|ERROR" "$report_file" >> "$FAILURES_FILE" || true
    fi
    
    echo "Report: $report_file" >> "$SUMMARY_FILE"
    echo "" >> "$SUMMARY_FILE"
    
    return $exit_code
}

# Track overall status
OVERALL_STATUS=0

echo -e "${BOLD}${BLUE}Step 1: Run Unit Tests${RESET}"
run_test_suite "Unit Tests" "tests/unit/" "" || OVERALL_STATUS=1
echo ""

echo -e "${BOLD}${BLUE}Step 2: Run Integration Tests${RESET}"
run_test_suite "Integration Tests" "tests/integration/" "" || OVERALL_STATUS=1
echo ""

echo -e "${BOLD}${BLUE}Step 3: Run E2E Tests${RESET}"
run_test_suite "E2E Tests" "tests/e2e/" "" || OVERALL_STATUS=1
echo ""

echo -e "${BOLD}${BLUE}Step 4: Run Regression Tests${RESET}"
run_test_suite "Regression Tests" "tests/regression/" "" || OVERALL_STATUS=1
echo ""

echo -e "${BOLD}${BLUE}Step 5: Run Security Tests${RESET}"
run_test_suite "Security Tests" "tests/security/" "" || OVERALL_STATUS=1
echo ""

echo -e "${BOLD}${BLUE}Step 6: Run Performance Tests${RESET}"
run_test_suite "Performance Tests" "tests/performance/" "" || OVERALL_STATUS=1
echo ""

# Summary
echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Test Execution Summary${RESET}"
echo -e "${BOLD}${BLUE}========================================${RESET}"
cat "$SUMMARY_FILE"

if [ "$OVERALL_STATUS" -eq 0 ]; then
    echo -e "${BOLD}${GREEN}✅ All test suites passed!${RESET}"
    echo "" >> "$SUMMARY_FILE"
    echo "Status: ✅ ALL TESTS PASSED" >> "$SUMMARY_FILE"
else
    echo -e "${BOLD}${RED}❌ Some test suites failed${RESET}"
    echo "" >> "$SUMMARY_FILE"
    echo "Status: ❌ SOME TESTS FAILED" >> "$SUMMARY_FILE"
    echo "" >> "$SUMMARY_FILE"
    echo "See $FAILURES_FILE for details" >> "$SUMMARY_FILE"
    echo -e "${YELLOW}See $FAILURES_FILE for failure details${RESET}"
fi

echo ""
echo -e "${BLUE}Reports saved to: ${REPORT_DIR}/${RESET}"
echo -e "${BLUE}Summary: ${SUMMARY_FILE}${RESET}"
if [ "$OVERALL_STATUS" -ne 0 ]; then
    echo -e "${BLUE}Failures: ${FAILURES_FILE}${RESET}"
fi

deactivate

exit $OVERALL_STATUS

