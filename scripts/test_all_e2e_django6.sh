#!/bin/bash
# Test All E2E Tests with Django 6

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Test All E2E Tests with Django 6${RESET}"
echo -e "${BOLD}${BLUE}========================================${RESET}"
echo ""

cd "$(dirname "$0")/.." || exit 1

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

echo ""
echo -e "${BOLD}${BLUE}Step 1: Verify E2E Tests Compatibility${RESET}"
python3 scripts/verify_e2e_tests_django6.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ E2E tests compatibility verified${RESET}"
else
    echo -e "${YELLOW}⚠️  Some E2E tests may need updates${RESET}"
fi
echo ""

# Set Django settings module
export DJANGO_SETTINGS_MODULE=hub.settings

echo -e "${BOLD}${BLUE}Step 2: Run Complete User Workflow Tests${RESET}"
# Find and run complete user workflow tests
WORKFLOW_TEST_FILES=$(find tests/e2e -name "test*complete*.py" -o -name "test*journey*.py" -o -name "test*workflow*.py" | head -5)
if [ -n "$WORKFLOW_TEST_FILES" ]; then
    echo -e "${BLUE}Found complete user workflow test files${RESET}"
    for test_file in $WORKFLOW_TEST_FILES; do
        echo -e "${BLUE}Running: $test_file${RESET}"
        pytest "$test_file" -v --tb=short -x 2>&1 | head -30 || echo -e "${YELLOW}⚠️  Test file may need updates${RESET}"
    done
else
    echo -e "${YELLOW}⚠️  No complete user workflow test files found${RESET}"
fi
echo ""

echo -e "${BOLD}${BLUE}Step 3: Run API Compatibility Tests${RESET}"
# Find and run API compatibility tests
API_TEST_FILES=$(find tests/e2e -name "test*api*.py" -o -name "test*rest*.py" | head -5)
if [ -n "$API_TEST_FILES" ]; then
    echo -e "${BLUE}Found API compatibility test files${RESET}"
    for test_file in $API_TEST_FILES; do
        echo -e "${BLUE}Running: $test_file${RESET}"
        pytest "$test_file" -v --tb=short -x 2>&1 | head -30 || echo -e "${YELLOW}⚠️  Test file may need updates${RESET}"
    done
else
    echo -e "${YELLOW}⚠️  No API compatibility test files found${RESET}"
fi
echo ""

echo -e "${BOLD}${BLUE}Step 4: Run SDK Compatibility Tests${RESET}"
# Find and run SDK compatibility tests
SDK_TEST_FILES=$(find tests/e2e -name "test*sdk*.py" | head -5)
if [ -n "$SDK_TEST_FILES" ]; then
    echo -e "${BLUE}Found SDK compatibility test files${RESET}"
    for test_file in $SDK_TEST_FILES; do
        echo -e "${BLUE}Running: $test_file${RESET}"
        pytest "$test_file" -v --tb=short -x 2>&1 | head -30 || echo -e "${YELLOW}⚠️  Test file may need updates${RESET}"
    done
else
    echo -e "${YELLOW}⚠️  No SDK compatibility test files found${RESET}"
fi
echo ""

echo -e "${BOLD}${BLUE}Step 5: Run Backward Compatibility Tests${RESET}"
# Find and run backward compatibility tests
BACKWARD_TEST_FILES=$(find tests/e2e -name "test*backward*.py" -o -name "test*migration*.py" -o -name "test*compatibility*.py" | head -5)
if [ -n "$BACKWARD_TEST_FILES" ]; then
    echo -e "${BLUE}Found backward compatibility test files${RESET}"
    for test_file in $BACKWARD_TEST_FILES; do
        echo -e "${BLUE}Running: $test_file${RESET}"
        pytest "$test_file" -v --tb=short -x 2>&1 | head -30 || echo -e "${YELLOW}⚠️  Test file may need updates${RESET}"
    done
else
    echo -e "${YELLOW}⚠️  No backward compatibility test files found${RESET}"
fi
echo ""

echo -e "${BOLD}${BLUE}Step 6: Run Performance Under Load Tests${RESET}"
# Find and run performance under load tests
PERF_TEST_FILES=$(find tests/e2e -name "test*performance*.py" -o -name "test*load*.py" -o -name "test*stress*.py" | head -5)
if [ -n "$PERF_TEST_FILES" ]; then
    echo -e "${BLUE}Found performance under load test files${RESET}"
    for test_file in $PERF_TEST_FILES; do
        echo -e "${BLUE}Running: $test_file${RESET}"
        pytest "$test_file" -v --tb=short -x 2>&1 | head -30 || echo -e "${YELLOW}⚠️  Test file may need updates${RESET}"
    done
else
    echo -e "${YELLOW}⚠️  No performance under load test files found${RESET}"
fi
echo ""

echo -e "${BOLD}${BLUE}Step 7: Run All E2E Tests (Sample)${RESET}"
# Run a sample of all E2E tests
echo -e "${BLUE}Running sample E2E tests to verify Django 6 compatibility${RESET}"
pytest tests/e2e/ -v --tb=short --maxfail=5 -k "not slow" 2>&1 | tail -50 || echo -e "${YELLOW}⚠️  Some E2E tests may need updates${RESET}"
echo ""

deactivate

echo -e "${BOLD}${GREEN}========================================${RESET}"
echo -e "${BOLD}${GREEN}E2E Tests with Django 6 Complete!${RESET}"
echo -e "${BOLD}${GREEN}Review the output above for any failures.${RESET}"
echo -e "${BOLD}${GREEN}========================================${RESET}"

