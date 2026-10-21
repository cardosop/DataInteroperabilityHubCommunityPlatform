#!/bin/bash
# Run Comprehensive Regression Test Suite

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Django 6 Regression Test Suite${RESET}"
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
echo -e "${BOLD}${BLUE}Running Comprehensive Regression Test Suite${RESET}"
echo ""

# Set Django settings module
export DJANGO_SETTINGS_MODULE=hub.settings

# Run all regression tests
echo -e "${BOLD}${BLUE}Step 1: API Endpoints Tests${RESET}"
if pytest tests/regression/test_api_endpoints.py -v --tb=short 2>&1 | tee /tmp/api_endpoints_tests.log; then
    API_PASSED=$(grep -c "PASSED" /tmp/api_endpoints_tests.log || echo "0")
    API_FAILED=$(grep -c "FAILED" /tmp/api_endpoints_tests.log || echo "0")
    echo -e "${GREEN}✅ API endpoints tests: ${API_PASSED} passed, ${API_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some API endpoints tests failed (review /tmp/api_endpoints_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 2: Workflow Tests${RESET}"
if pytest tests/regression/test_workflows.py -v --tb=short 2>&1 | tee /tmp/workflow_tests.log; then
    WORKFLOW_PASSED=$(grep -c "PASSED" /tmp/workflow_tests.log || echo "0")
    WORKFLOW_FAILED=$(grep -c "FAILED" /tmp/workflow_tests.log || echo "0")
    echo -e "${GREEN}✅ Workflow tests: ${WORKFLOW_PASSED} passed, ${WORKFLOW_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some workflow tests failed (review /tmp/workflow_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 3: Integration Tests${RESET}"
if pytest tests/regression/test_integrations.py -v --tb=short 2>&1 | tee /tmp/integration_tests.log; then
    INTEGRATION_PASSED=$(grep -c "PASSED" /tmp/integration_tests.log || echo "0")
    INTEGRATION_FAILED=$(grep -c "FAILED" /tmp/integration_tests.log || echo "0")
    echo -e "${GREEN}✅ Integration tests: ${INTEGRATION_PASSED} passed, ${INTEGRATION_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some integration tests failed (review /tmp/integration_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 4: Middleware Tests${RESET}"
if pytest tests/regression/test_middleware.py -v --tb=short 2>&1 | tee /tmp/middleware_tests.log; then
    MIDDLEWARE_PASSED=$(grep -c "PASSED" /tmp/middleware_tests.log || echo "0")
    MIDDLEWARE_FAILED=$(grep -c "FAILED" /tmp/middleware_tests.log || echo "0")
    echo -e "${GREEN}✅ Middleware tests: ${MIDDLEWARE_PASSED} passed, ${MIDDLEWARE_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some middleware tests failed (review /tmp/middleware_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 5: Database Operations Tests${RESET}"
if pytest tests/regression/test_database_operations.py -v --tb=short 2>&1 | tee /tmp/database_tests.log; then
    DB_PASSED=$(grep -c "PASSED" /tmp/database_tests.log || echo "0")
    DB_FAILED=$(grep -c "FAILED" /tmp/database_tests.log || echo "0")
    echo -e "${GREEN}✅ Database operations tests: ${DB_PASSED} passed, ${DB_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some database operations tests failed (review /tmp/database_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 6: Job Queue Tests${RESET}"
if pytest tests/regression/test_job_queue.py -v --tb=short 2>&1 | tee /tmp/job_queue_tests.log; then
    JOB_PASSED=$(grep -c "PASSED" /tmp/job_queue_tests.log || echo "0")
    JOB_FAILED=$(grep -c "FAILED" /tmp/job_queue_tests.log || echo "0")
    echo -e "${GREEN}✅ Job queue tests: ${JOB_PASSED} passed, ${JOB_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some job queue tests failed (review /tmp/job_queue_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 7: File Storage Tests${RESET}"
if pytest tests/regression/test_file_storage.py -v --tb=short 2>&1 | tee /tmp/file_storage_tests.log; then
    FILE_PASSED=$(grep -c "PASSED" /tmp/file_storage_tests.log || echo "0")
    FILE_FAILED=$(grep -c "FAILED" /tmp/file_storage_tests.log || echo "0")
    echo -e "${GREEN}✅ File storage tests: ${FILE_PASSED} passed, ${FILE_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some file storage tests failed (review /tmp/file_storage_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 8: Authentication/Authorization Tests${RESET}"
if pytest tests/regression/test_auth_authorization.py -v --tb=short 2>&1 | tee /tmp/auth_tests.log; then
    AUTH_PASSED=$(grep -c "PASSED" /tmp/auth_tests.log || echo "0")
    AUTH_FAILED=$(grep -c "FAILED" /tmp/auth_tests.log || echo "0")
    echo -e "${GREEN}✅ Authentication/authorization tests: ${AUTH_PASSED} passed, ${AUTH_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some authentication/authorization tests failed (review /tmp/auth_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 9: Tenant Isolation Tests${RESET}"
if pytest tests/regression/test_tenant_isolation.py -v --tb=short 2>&1 | tee /tmp/tenant_isolation_tests.log; then
    TENANT_PASSED=$(grep -c "PASSED" /tmp/tenant_isolation_tests.log || echo "0")
    TENANT_FAILED=$(grep -c "FAILED" /tmp/tenant_isolation_tests.log || echo "0")
    echo -e "${GREEN}✅ Tenant isolation tests: ${TENANT_PASSED} passed, ${TENANT_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some tenant isolation tests failed (review /tmp/tenant_isolation_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 10: All Regression Tests${RESET}"
if pytest tests/regression/ -v --tb=short 2>&1 | tee /tmp/all_regression_tests.log; then
    ALL_PASSED=$(grep -c "PASSED" /tmp/all_regression_tests.log || echo "0")
    ALL_FAILED=$(grep -c "FAILED" /tmp/all_regression_tests.log || echo "0")
    echo -e "${GREEN}✅ All regression tests: ${ALL_PASSED} passed, ${ALL_FAILED} failed${RESET}"
else
    echo -e "${YELLOW}⚠️  Some regression tests failed (review /tmp/all_regression_tests.log)${RESET}"
fi

echo ""
echo -e "${BOLD}${GREEN}Regression Test Suite Summary${RESET}"
echo -e "${GREEN}✅ API endpoints tests executed${RESET}"
echo -e "${GREEN}✅ Workflow tests executed${RESET}"
echo -e "${GREEN}✅ Integration tests executed${RESET}"
echo -e "${GREEN}✅ Middleware tests executed${RESET}"
echo -e "${GREEN}✅ Database operations tests executed${RESET}"
echo -e "${GREEN}✅ Job queue tests executed${RESET}"
echo -e "${GREEN}✅ File storage tests executed${RESET}"
echo -e "${GREEN}✅ Authentication/authorization tests executed${RESET}"
echo -e "${GREEN}✅ Tenant isolation tests executed${RESET}"
echo -e "${GREEN}✅ All regression tests executed${RESET}"

deactivate

echo ""
echo -e "${BOLD}${GREEN}========================================${RESET}"
echo -e "${BOLD}${GREEN}Regression Test Suite Complete!${RESET}"
echo -e "${BOLD}${GREEN}Review the output above for any failures.${RESET}"
echo -e "${BOLD}${GREEN}========================================${RESET}"

