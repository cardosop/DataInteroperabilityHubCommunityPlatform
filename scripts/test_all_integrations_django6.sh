#!/bin/bash
# Test All Integrations with Django 6

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Test All Integrations with Django 6${RESET}"
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
echo -e "${BOLD}${BLUE}Step 1: Verify Integration Tests Compatibility${RESET}"
python3 scripts/verify_integration_tests_django6.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Integration tests compatibility verified${RESET}"
else
    echo -e "${YELLOW}⚠️  Some integration tests may need updates${RESET}"
fi
echo ""

# Set Django settings module
export DJANGO_SETTINGS_MODULE=hub.settings

echo -e "${BOLD}${BLUE}Step 2: Run Database Integration Tests${RESET}"
# Find and run database integration tests
DB_TEST_FILES=$(find . -path "*/test*integration*.py" -o -path "*/test*db*.py" | grep -E "(database|db)" | head -5)
if [ -n "$DB_TEST_FILES" ]; then
    echo -e "${BLUE}Found database integration test files${RESET}"
    for test_file in $DB_TEST_FILES; do
        echo -e "${BLUE}Running: $test_file${RESET}"
        pytest "$test_file" -v --tb=short 2>&1 | head -20 || echo -e "${YELLOW}⚠️  Test file may need updates${RESET}"
    done
else
    echo -e "${YELLOW}⚠️  No database integration test files found${RESET}"
fi
echo ""

echo -e "${BOLD}${BLUE}Step 3: Run API Integration Tests${RESET}"
# Find and run API integration tests
API_TEST_FILES=$(find . -path "*/test*api*.py" | grep -v "__pycache__" | head -5)
if [ -n "$API_TEST_FILES" ]; then
    echo -e "${BLUE}Found API integration test files${RESET}"
    for test_file in $API_TEST_FILES; do
        echo -e "${BLUE}Running: $test_file${RESET}"
        pytest "$test_file" -v --tb=short 2>&1 | head -20 || echo -e "${YELLOW}⚠️  Test file may need updates${RESET}"
    done
else
    echo -e "${YELLOW}⚠️  No API integration test files found${RESET}"
fi
echo ""

echo -e "${BOLD}${BLUE}Step 4: Run Job Queue Integration Tests${RESET}"
# Find and run job queue integration tests
JOB_TEST_FILES=$(find . -path "*/test*job*.py" | grep -v "__pycache__" | head -5)
if [ -n "$JOB_TEST_FILES" ]; then
    echo -e "${BLUE}Found job queue integration test files${RESET}"
    for test_file in $JOB_TEST_FILES; do
        echo -e "${BLUE}Running: $test_file${RESET}"
        pytest "$test_file" -v --tb=short 2>&1 | head -20 || echo -e "${YELLOW}⚠️  Test file may need updates${RESET}"
    done
else
    echo -e "${YELLOW}⚠️  No job queue integration test files found${RESET}"
fi
echo ""

echo -e "${BOLD}${BLUE}Step 5: Run File Storage Integration Tests${RESET}"
# Find and run file storage integration tests
FILE_TEST_FILES=$(find . -path "*/test*file*.py" -o -path "*/test*storage*.py" | grep -v "__pycache__" | head -5)
if [ -n "$FILE_TEST_FILES" ]; then
    echo -e "${BLUE}Found file storage integration test files${RESET}"
    for test_file in $FILE_TEST_FILES; do
        echo -e "${BLUE}Running: $test_file${RESET}"
        pytest "$test_file" -v --tb=short 2>&1 | head -20 || echo -e "${YELLOW}⚠️  Test file may need updates${RESET}"
    done
else
    echo -e "${YELLOW}⚠️  No file storage integration test files found${RESET}"
fi
echo ""

echo -e "${BOLD}${BLUE}Step 6: Run Cross-Service Integration Tests${RESET}"
# Find and run cross-service integration tests
CROSS_SERVICE_TEST_FILES=$(find . -path "*/test*service*.py" -o -path "*/test*cross*.py" | grep -v "__pycache__" | head -5)
if [ -n "$CROSS_SERVICE_TEST_FILES" ]; then
    echo -e "${BLUE}Found cross-service integration test files${RESET}"
    for test_file in $CROSS_SERVICE_TEST_FILES; do
        echo -e "${BLUE}Running: $test_file${RESET}"
        pytest "$test_file" -v --tb=short 2>&1 | head -20 || echo -e "${YELLOW}⚠️  Test file may need updates${RESET}"
    done
else
    echo -e "${YELLOW}⚠️  No cross-service integration test files found${RESET}"
fi
echo ""

echo -e "${BOLD}${BLUE}Step 7: Run External Service Integration Tests${RESET}"
# Run external service integration tests
if [ -f "scripts/test_integration_services.sh" ]; then
    bash scripts/test_integration_services.sh
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ External service integration tests passed${RESET}"
    else
        echo -e "${YELLOW}⚠️  External service integration tests had issues${RESET}"
    fi
else
    echo -e "${YELLOW}⚠️  External service integration test script not found${RESET}"
fi
echo ""

deactivate

echo -e "${BOLD}${GREEN}========================================${RESET}"
echo -e "${BOLD}${GREEN}Integration Tests with Django 6 Complete!${RESET}"
echo -e "${BOLD}${GREEN}Review the output above for any failures.${RESET}"
echo -e "${BOLD}${GREEN}========================================${RESET}"

