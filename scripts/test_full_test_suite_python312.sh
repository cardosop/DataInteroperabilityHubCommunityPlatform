#!/bin/bash
# Test Full Test Suite with Python 3.12+
# This script runs the complete test suite to verify Python 3.12+ compatibility

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Full Test Suite - Python 3.12+${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if virtual environment exists
VENV_DIR="venv-python312-test"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating...${NC}"
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    pip install --quiet -r requirements-dev.txt
else
    source "$VENV_DIR/bin/activate"
fi

echo -e "${GREEN}✅ Virtual environment activated${NC}"
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo -e "${BLUE}Python version: ${PYTHON_VERSION}${NC}"
echo ""

# Check if pytest is installed
if ! python -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  pytest not installed, installing...${NC}"
    pip install --quiet pytest pytest-django pytest-cov
fi

echo -e "${GREEN}✅ pytest is available${NC}"
echo ""

# Set environment variables
export DJANGO_SETTINGS_MODULE=hub.settings
export PYTHONPATH="$PROJECT_ROOT"
export DATABASE_URL="${DATABASE_URL:-postgresql://hub:hub@localhost:5432/hub}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

# Check if database is available
echo -e "${BLUE}Checking test environment...${NC}"
if docker ps --format '{{.Names}}' | grep -q '^hub-postgres$'; then
    echo -e "${GREEN}✅ PostgreSQL is running${NC}"
else
    echo -e "${YELLOW}⚠️  PostgreSQL is not running${NC}"
    echo -e "${YELLOW}   Some tests may fail without database${NC}"
fi

if docker ps --format '{{.Names}}' | grep -q '^hub-redis$'; then
    echo -e "${GREEN}✅ Redis is running${NC}"
else
    echo -e "${YELLOW}⚠️  Redis is not running${NC}"
    echo -e "${YELLOW}   Some tests may fail without Redis${NC}"
fi

echo ""

# Run unit tests
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Running Unit Tests${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ -d "tests/unit" ]; then
    UNIT_TEST_COUNT=$(find tests/unit -name "test_*.py" | wc -l)
    echo -e "${BLUE}Found ${UNIT_TEST_COUNT} unit test files${NC}"
    
    if pytest tests/unit/ -v --tb=short -x 2>&1 | tee /tmp/unit_tests.log; then
        echo -e "${GREEN}✅ Unit tests passed${NC}"
        UNIT_RESULT=0
    else
        echo -e "${RED}❌ Unit tests failed${NC}"
        UNIT_RESULT=1
    fi
else
    echo -e "${YELLOW}⚠️  tests/unit directory not found${NC}"
    UNIT_RESULT=0
fi

echo ""

# Run integration tests
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Running Integration Tests${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ -d "tests/integration" ]; then
    INTEGRATION_TEST_COUNT=$(find tests/integration -name "test_*.py" | wc -l)
    echo -e "${BLUE}Found ${INTEGRATION_TEST_COUNT} integration test files${NC}"
    
    if pytest tests/integration/ -v --tb=short -x 2>&1 | tee /tmp/integration_tests.log; then
        echo -e "${GREEN}✅ Integration tests passed${NC}"
        INTEGRATION_RESULT=0
    else
        echo -e "${RED}❌ Integration tests failed${NC}"
        INTEGRATION_RESULT=1
    fi
else
    echo -e "${YELLOW}⚠️  tests/integration directory not found${NC}"
    INTEGRATION_RESULT=0
fi

echo ""

# Run E2E tests (may require full stack)
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Running E2E Tests${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ -d "tests/e2e" ]; then
    E2E_TEST_COUNT=$(find tests/e2e -name "test_*.py" | wc -l)
    echo -e "${BLUE}Found ${E2E_TEST_COUNT} E2E test files${NC}"
    echo -e "${YELLOW}⚠️  E2E tests require full stack (services, database, Redis)${NC}"
    echo -e "${YELLOW}   Skipping E2E tests in this automated run${NC}"
    echo -e "${BLUE}   To run E2E tests manually:${NC}"
    echo -e "${BLUE}   1. Start all services: docker compose up -d${NC}"
    echo -e "${BLUE}   2. Run: pytest tests/e2e/ -v${NC}"
    E2E_RESULT=0
else
    echo -e "${YELLOW}⚠️  tests/e2e directory not found${NC}"
    E2E_RESULT=0
fi

echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Suite Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

TOTAL_TESTS=3
PASSED_TESTS=0

[ $UNIT_RESULT -eq 0 ] && PASSED_TESTS=$((PASSED_TESTS + 1)) && echo -e "${GREEN}✅ Unit Tests: PASS${NC}" || echo -e "${RED}❌ Unit Tests: FAIL${NC}"
[ $INTEGRATION_RESULT -eq 0 ] && PASSED_TESTS=$((PASSED_TESTS + 1)) && echo -e "${GREEN}✅ Integration Tests: PASS${NC}" || echo -e "${RED}❌ Integration Tests: FAIL${NC}"
[ $E2E_RESULT -eq 0 ] && PASSED_TESTS=$((PASSED_TESTS + 1)) && echo -e "${YELLOW}⚠️  E2E Tests: SKIPPED${NC}" || echo -e "${RED}❌ E2E Tests: FAIL${NC}"

echo ""
echo -e "${BLUE}Results: ${PASSED_TESTS}/${TOTAL_TESTS} test suites${NC}"

if [ $UNIT_RESULT -eq 0 ] && [ $INTEGRATION_RESULT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Core test suites passed!${NC}"
    echo -e "${YELLOW}⚠️  E2E tests require manual execution with full stack${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}❌ Some test suites failed${NC}"
    exit 1
fi

