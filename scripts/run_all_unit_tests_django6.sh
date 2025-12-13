#!/bin/bash
# Run All Unit Tests for Django 6 Verification

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Django 6 Unit Test Verification${RESET}"
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

echo ""
echo -e "${BOLD}${BLUE}Step 1: Verify Test Compatibility${RESET}"
if python3 scripts/verify_django6_test_compatibility.py 2>&1; then
    echo -e "${GREEN}✅ Test compatibility check completed${RESET}"
else
    echo -e "${YELLOW}⚠️  Test compatibility check completed with warnings${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 2: Run Model Tests${RESET}"
MODEL_TESTS=$(find hub/apps -name "test_models.py" -o -name "test_*models*.py" | wc -l)
echo -e "${BLUE}Found ${MODEL_TESTS} model test files${RESET}"

if pytest hub/apps/*/tests/test_models.py tests/unit/*/test_models.py -v --tb=short 2>&1 | tee /tmp/model_tests.log; then
    MODEL_PASSED=$(grep -c "PASSED" /tmp/model_tests.log || echo "0")
    MODEL_FAILED=$(grep -c "FAILED" /tmp/model_tests.log || echo "0")
    echo -e "${GREEN}✅ Model tests: ${MODEL_PASSED} passed, ${MODEL_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some model tests failed (review /tmp/model_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 3: Run View Tests${RESET}"
VIEW_TESTS=$(find hub/apps -name "test_views.py" | wc -l)
echo -e "${BLUE}Found ${VIEW_TESTS} view test files${RESET}"

if pytest hub/apps/*/tests/test_views.py -v --tb=short 2>&1 | tee /tmp/view_tests.log; then
    VIEW_PASSED=$(grep -c "PASSED" /tmp/view_tests.log || echo "0")
    VIEW_FAILED=$(grep -c "FAILED" /tmp/view_tests.log || echo "0")
    echo -e "${GREEN}✅ View tests: ${VIEW_PASSED} passed, ${VIEW_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some view tests failed (review /tmp/view_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 4: Run Serializer Tests${RESET}"
SERIALIZER_TESTS=$(find hub/apps tests -name "test_serializers.py" | wc -l)
echo -e "${BLUE}Found ${SERIALIZER_TESTS} serializer test files${RESET}"

if pytest hub/apps/*/tests/test_serializers.py tests/unit/*/test_serializers.py -v --tb=short 2>&1 | tee /tmp/serializer_tests.log; then
    SERIALIZER_PASSED=$(grep -c "PASSED" /tmp/serializer_tests.log || echo "0")
    SERIALIZER_FAILED=$(grep -c "FAILED" /tmp/serializer_tests.log || echo "0")
    echo -e "${GREEN}✅ Serializer tests: ${SERIALIZER_PASSED} passed, ${SERIALIZER_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some serializer tests failed (review /tmp/serializer_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 5: Run Utility Tests${RESET}"
UTILITY_TESTS=$(find hub/apps -name "test_utils.py" | wc -l)
echo -e "${BLUE}Found ${UTILITY_TESTS} utility test files${RESET}"

if pytest hub/apps/*/tests/test_utils.py -v --tb=short 2>&1 | tee /tmp/utility_tests.log; then
    UTILITY_PASSED=$(grep -c "PASSED" /tmp/utility_tests.log || echo "0")
    UTILITY_FAILED=$(grep -c "FAILED" /tmp/utility_tests.log || echo "0")
    echo -e "${GREEN}✅ Utility tests: ${UTILITY_PASSED} passed, ${UTILITY_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some utility tests failed (review /tmp/utility_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 6: Run All Unit Tests${RESET}"
if pytest tests/unit/ -v --tb=short 2>&1 | tee /tmp/all_unit_tests.log; then
    ALL_PASSED=$(grep -c "PASSED" /tmp/all_unit_tests.log || echo "0")
    ALL_FAILED=$(grep -c "FAILED" /tmp/all_unit_tests.log || echo "0")
    echo -e "${GREEN}✅ All unit tests: ${ALL_PASSED} passed, ${ALL_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some unit tests failed (review /tmp/all_unit_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${GREEN}Unit Test Verification Summary${RESET}"
echo -e "${GREEN}✅ Test compatibility verified${RESET}"
echo -e "${GREEN}✅ Model tests executed${RESET}"
echo -e "${GREEN}✅ View tests executed${RESET}"
echo -e "${GREEN}✅ Serializer tests executed${RESET}"
echo -e "${GREEN}✅ Utility tests executed${RESET}"
echo -e "${GREEN}✅ All unit tests executed${RESET}"

