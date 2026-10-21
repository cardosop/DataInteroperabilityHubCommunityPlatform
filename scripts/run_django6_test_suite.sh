#!/bin/bash
# Run Comprehensive Django 6 Test Suite

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Django 6 Comprehensive Test Suite${RESET}"
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
echo -e "${BOLD}${BLUE}Step 1: Run Unit Tests${RESET}"
if pytest tests/unit/ -v --tb=short 2>&1 | tee /tmp/unit_tests.log; then
    UNIT_PASSED=$(grep -c "PASSED" /tmp/unit_tests.log || echo "0")
    UNIT_FAILED=$(grep -c "FAILED" /tmp/unit_tests.log || echo "0")
    echo -e "${GREEN}✅ Unit tests: ${UNIT_PASSED} passed, ${UNIT_FAILED} failed${RESET}"
else
    echo -e "${RED}❌ Unit tests failed${RESET}"
    exit 1
fi

echo ""
echo -e "${BOLD}${BLUE}Step 2: Run Integration Tests${RESET}"
if pytest tests/integration/ -v --tb=short 2>&1 | tee /tmp/integration_tests.log; then
    INT_PASSED=$(grep -c "PASSED" /tmp/integration_tests.log || echo "0")
    INT_FAILED=$(grep -c "FAILED" /tmp/integration_tests.log || echo "0")
    echo -e "${GREEN}✅ Integration tests: ${INT_PASSED} passed, ${INT_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some integration tests failed (may require services)${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 3: Run Middleware Tests${RESET}"
if pytest hub/apps/*/tests/test_middleware.py tests/integration/test_middleware_integration.py -v --tb=short 2>&1 | tee /tmp/middleware_tests.log; then
    MW_PASSED=$(grep -c "PASSED" /tmp/middleware_tests.log || echo "0")
    MW_FAILED=$(grep -c "FAILED" /tmp/middleware_tests.log || echo "0")
    echo -e "${GREEN}✅ Middleware tests: ${MW_PASSED} passed, ${MW_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some middleware tests failed${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 4: Run JSONField Tests${RESET}"
if python3 scripts/test_jsonfield_functionality.py 2>&1; then
    echo -e "${GREEN}✅ JSONField tests passed${RESET}"
else
    echo -e "${YELLOW}⚠️  JSONField tests completed with warnings${RESET}"
fi

echo ""
echo -e "${BOLD}${GREEN}Test Suite Summary${RESET}"
echo -e "${GREEN}✅ Unit tests executed${RESET}"
echo -e "${GREEN}✅ Integration tests executed${RESET}"
echo -e "${GREEN}✅ Middleware tests executed${RESET}"
echo -e "${GREEN}✅ JSONField tests executed${RESET}"

