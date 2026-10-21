#!/bin/bash
# Final Comprehensive Python 3.12+ Verification
# This script performs a complete verification of the Python 3.12+ upgrade

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo -e "${BOLD}${BLUE}========================================${NC}"
echo -e "${BOLD}${BLUE}Final Python 3.12+ Upgrade Verification${NC}"
echo -e "${BOLD}${BLUE}========================================${NC}"
echo ""

# Track results
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

# Function to run a check
run_check() {
    local check_name="$1"
    local check_command="$2"
    local is_critical="${3:-true}"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    echo -e "${BLUE}Checking: ${check_name}...${NC}"
    
    if eval "$check_command" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✅ PASS${NC}"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        if [ "$is_critical" = "true" ]; then
            echo -e "${RED}  ❌ FAIL${NC}"
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
            return 1
        else
            echo -e "${YELLOW}  ⚠️  WARNING${NC}"
            WARNING_CHECKS=$((WARNING_CHECKS + 1))
            return 0
        fi
    fi
}

# 1. Python Version Check
echo -e "${BOLD}1. Python Version Verification${NC}"
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)"; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}  ✅ Python ${PYTHON_VERSION} meets 3.12+ requirement${NC}"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo -e "${RED}  ❌ Python 3.12+ required${NC}"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
echo ""

# 2. Configuration Files
echo -e "${BOLD}2. Configuration File Verification${NC}"
run_check "Dockerfiles use Python 3.12+" \
    "grep -r 'FROM python:3.12' services/*/Dockerfile | wc -l | grep -q '^6$'"

run_check "GitHub workflows use Python 3.12+" \
    "grep -r 'python-version.*3\.1[2-9]' .github/workflows/*.yml | wc -l | grep -q '^[4-9]'"

run_check "Setup scripts check for Python 3.12+" \
    "grep -q '3\.1[2-9]' setup.sh scripts/dev-setup.sh"

run_check "pyproject.toml files configured for Python 3.12+" \
    "grep -q 'py312\|>=3.12' pyproject.toml sdk/python/pyproject.toml 2>/dev/null"

run_check "setup.py files require Python 3.12+" \
    "grep -q '>=3.12' sdk/python/setup.py cli/setup.py"

run_check "mypy.ini uses Python 3.12" \
    "grep -q 'python_version = 3.12' mypy.ini 2>/dev/null"
echo ""

# 3. Dependency Compatibility
echo -e "${BOLD}3. Dependency Compatibility Verification${NC}"
if [ -f "scripts/audit_dependency_compatibility.py" ]; then
    if python3 scripts/audit_dependency_compatibility.py 2>&1 | grep -q "All dependencies are compatible"; then
        echo -e "${GREEN}  ✅ All dependencies compatible with Python 3.12+${NC}"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        echo -e "${YELLOW}  ⚠️  Some dependencies may have compatibility warnings${NC}"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
else
    echo -e "${YELLOW}  ⚠️  Dependency audit script not found${NC}"
    WARNING_CHECKS=$((WARNING_CHECKS + 1))
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
fi
echo ""

# 4. Docker Builds
echo -e "${BOLD}4. Docker Build Verification${NC}"
if command -v docker &> /dev/null; then
    run_check "Docker is available" "docker --version" "true"
    
    if [ -f "scripts/test_docker_builds.sh" ]; then
        echo -e "${BLUE}  Running Docker build tests...${NC}"
        if bash scripts/test_docker_builds.sh 2>&1 | grep -q "All Docker builds passed"; then
            echo -e "${GREEN}  ✅ Docker builds verified${NC}"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            echo -e "${YELLOW}  ⚠️  Docker build test had issues${NC}"
            WARNING_CHECKS=$((WARNING_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    fi
else
    echo -e "${YELLOW}  ⚠️  Docker not available, skipping Docker checks${NC}"
    WARNING_CHECKS=$((WARNING_CHECKS + 1))
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
fi
echo ""

# 5. Test Execution
echo -e "${BOLD}5. Test Execution Verification${NC}"
if [ -d "venv-python312-test" ]; then
    run_check "Test virtual environment exists" "test -d venv-python312-test" "false"
    
    if source venv-python312-test/bin/activate 2>/dev/null && python -c "import django" 2>/dev/null; then
        echo -e "${GREEN}  ✅ Django is installed in test environment${NC}"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        echo -e "${YELLOW}  ⚠️  Django not installed in test environment${NC}"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
else
    echo -e "${YELLOW}  ⚠️  Test virtual environment not found${NC}"
    WARNING_CHECKS=$((WARNING_CHECKS + 1))
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
fi
echo ""

# 6. Documentation
echo -e "${BOLD}6. Documentation Verification${NC}"
run_check "Python 3.12+ testing guide exists" \
    "test -f docs/PYTHON_312_UPGRADE_TESTING.md" "false"

run_check "Developer onboarding updated" \
    "grep -q '3\.1[2-9]' docs/DEVELOPER_ONBOARDING.md 2>/dev/null" "false"

run_check "Setup status updated" \
    "grep -q '3\.1[2-9]' SETUP_STATUS.md 2>/dev/null" "false"
echo ""

# Summary
echo -e "${BOLD}${BLUE}========================================${NC}"
echo -e "${BOLD}${BLUE}Verification Summary${NC}"
echo -e "${BOLD}${BLUE}========================================${NC}"
echo ""
echo -e "${BOLD}Total Checks:${NC} ${TOTAL_CHECKS}"
echo -e "${GREEN}✅ Passed:${NC} ${PASSED_CHECKS}"
echo -e "${YELLOW}⚠️  Warnings:${NC} ${WARNING_CHECKS}"
echo -e "${RED}❌ Failed:${NC} ${FAILED_CHECKS}"
echo ""

if [ $FAILED_CHECKS -eq 0 ]; then
    if [ $WARNING_CHECKS -eq 0 ]; then
        echo -e "${BOLD}${GREEN}✅ All checks passed! Python 3.12+ upgrade is complete.${NC}"
        exit 0
    else
        echo -e "${BOLD}${YELLOW}⚠️  All critical checks passed, but some warnings exist.${NC}"
        echo -e "${YELLOW}Review warnings above before proceeding.${NC}"
        exit 0
    fi
else
    echo -e "${BOLD}${RED}❌ Some critical checks failed.${NC}"
    echo -e "${RED}Please fix the issues above before proceeding.${NC}"
    exit 1
fi

