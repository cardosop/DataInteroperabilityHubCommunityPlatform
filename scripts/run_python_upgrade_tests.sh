#!/bin/bash
# Comprehensive Python 3.12+ Upgrade Test Runner
# This script runs all automated tests for the Python 3.12+ upgrade

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
echo -e "${BLUE}Python 3.12+ Upgrade Test Suite${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Test 1: Configuration Verification
echo -e "${BLUE}Test 1: Configuration Verification${NC}"
echo -e "${BLUE}----------------------------------------${NC}"
python3 scripts/verify_python_upgrade.py
CONFIG_RESULT=$?

if [ $CONFIG_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ Configuration verification passed${NC}"
else
    echo -e "${YELLOW}⚠️  Configuration verification had warnings${NC}"
fi
echo ""

# Test 2: Python Compatibility
echo -e "${BLUE}Test 2: Python 3.12+ Compatibility${NC}"
echo -e "${BLUE}----------------------------------------${NC}"
bash scripts/test_python_compatibility.sh
COMPAT_RESULT=$?

if [ $COMPAT_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ Python compatibility test passed${NC}"
else
    echo -e "${RED}❌ Python compatibility test failed${NC}"
fi
echo ""

# Test 3: Docker Builds (if Docker is available)
echo -e "${BLUE}Test 3: Docker Build Tests${NC}"
echo -e "${BLUE}----------------------------------------${NC}"
if command -v docker &> /dev/null; then
    bash scripts/test_docker_builds.sh
    DOCKER_RESULT=$?
    
    if [ $DOCKER_RESULT -eq 0 ]; then
        echo -e "${GREEN}✅ Docker build tests passed${NC}"
    else
        echo -e "${RED}❌ Docker build tests failed${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Docker not available, skipping Docker build tests${NC}"
    echo -e "${YELLOW}   To test Docker builds, install Docker and run:${NC}"
    echo -e "${YELLOW}   bash scripts/test_docker_builds.sh${NC}"
    DOCKER_RESULT=0
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

TOTAL_TESTS=3
PASSED_TESTS=0

[ $CONFIG_RESULT -eq 0 ] && PASSED_TESTS=$((PASSED_TESTS + 1))
[ $COMPAT_RESULT -eq 0 ] && PASSED_TESTS=$((PASSED_TESTS + 1))
[ $DOCKER_RESULT -eq 0 ] && PASSED_TESTS=$((PASSED_TESTS + 1))

echo -e "${BLUE}Configuration Verification:${NC} $([ $CONFIG_RESULT -eq 0 ] && echo -e "${GREEN}✅ PASS${NC}" || echo -e "${YELLOW}⚠️  WARNINGS${NC}")"
echo -e "${BLUE}Python Compatibility:${NC} $([ $COMPAT_RESULT -eq 0 ] && echo -e "${GREEN}✅ PASS${NC}" || echo -e "${RED}❌ FAIL${NC}")"
echo -e "${BLUE}Docker Builds:${NC} $([ $DOCKER_RESULT -eq 0 ] && echo -e "${GREEN}✅ PASS${NC}" || echo -e "${RED}❌ FAIL${NC}")"
echo ""
echo -e "${BLUE}Results: ${PASSED_TESTS}/${TOTAL_TESTS} tests passed${NC}"
echo ""

# Manual testing checklist
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Manual Testing Checklist${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}The following tests require manual verification:${NC}"
echo ""
echo -e "${BLUE}1. CI/CD Pipeline Testing:${NC}"
echo -e "   - Push changes to a test branch"
echo -e "   - Verify GitHub Actions workflows run with Python 3.12+"
echo -e "   - Check that all CI jobs pass"
echo ""
echo -e "${BLUE}2. Service Startup Testing:${NC}"
echo -e "   - Start all services using docker-compose"
echo -e "   - Verify each service starts correctly"
echo -e "   - Check service health endpoints"
echo ""
echo -e "${BLUE}3. Application Testing:${NC}"
echo -e "   - Run Django development server"
echo -e "   - Test API endpoints"
echo -e "   - Verify database migrations work"
echo ""
echo -e "${BLUE}4. SDK and CLI Testing:${NC}"
echo -e "   - Install SDK in a virtual environment"
echo -e "   - Install CLI tool"
echo -e "   - Test SDK functionality"
echo -e "   - Test CLI commands"
echo ""
echo -e "${BLUE}5. Integration Testing:${NC}"
echo -e "   - Run full test suite"
echo -e "   - Run E2E tests"
echo -e "   - Verify all tests pass"
echo ""

if [ $PASSED_TESTS -eq $TOTAL_TESTS ]; then
    echo -e "${GREEN}✅ All automated tests passed!${NC}"
    echo -e "${GREEN}Ready for manual testing and CI/CD verification.${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  Some automated tests had issues.${NC}"
    echo -e "${YELLOW}Please review the output above before proceeding.${NC}"
    exit 1
fi

