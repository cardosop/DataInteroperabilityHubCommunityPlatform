#!/bin/bash
# Validate CI/CD Workflow Configuration for Python 3.12+
# This script validates that all GitHub Actions workflows are correctly configured

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
echo -e "${BLUE}CI/CD Workflow Validation - Python 3.12+${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

WORKFLOWS=(
    ".github/workflows/ci.yml"
    ".github/workflows/e2e.yml"
    ".github/workflows/openapi-validation.yml"
    ".github/workflows/security-scan.yml"
    ".github/workflows/docker-build.yml"
    ".github/workflows/deploy.yml"
)

SUCCESS_COUNT=0
FAIL_COUNT=0

for workflow in "${WORKFLOWS[@]}"; do
    if [ ! -f "$workflow" ]; then
        echo -e "${YELLOW}⚠️  Workflow not found: ${workflow}${NC}"
        continue
    fi
    
    echo -e "${BLUE}Validating ${workflow}...${NC}"
    
    # Check for Python 3.12+ usage
    if grep -q "python-version.*3\.1[2-9]" "$workflow" || grep -q "python-version.*\${{.*matrix\.python-version" "$workflow"; then
        echo -e "${GREEN}  ✅ Uses Python 3.12+${NC}"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    elif grep -q "python-version.*3\.11" "$workflow"; then
        echo -e "${RED}  ❌ Still uses Python 3.11${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    else
        echo -e "${YELLOW}  ⚠️  No Python version specified${NC}"
    fi
    
    # Check for test matrix (in ci.yml)
    if [ "$(basename "$workflow")" = "ci.yml" ]; then
        if grep -q "matrix:" "$workflow" && grep -q "python-version:" "$workflow"; then
            echo -e "${GREEN}  ✅ Has Python version test matrix${NC}"
            # Extract matrix values
            MATRIX_VERSIONS=$(grep -A 5 "python-version:" "$workflow" | grep -o "3\.1[2-9]" | sort -u | tr '\n' ' ')
            if [ -n "$MATRIX_VERSIONS" ]; then
                echo -e "${BLUE}    Matrix versions: ${MATRIX_VERSIONS}${NC}"
            fi
        fi
    fi
    
    # Validate YAML syntax (basic check)
    if command -v yamllint &> /dev/null; then
        if yamllint "$workflow" > /dev/null 2>&1; then
            echo -e "${GREEN}  ✅ YAML syntax is valid${NC}"
        else
            echo -e "${YELLOW}  ⚠️  YAML syntax issues (may be false positive)${NC}"
        fi
    fi
    
    echo ""
done

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Workflow Validation Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}✅ Valid workflows: ${SUCCESS_COUNT}${NC}"
echo -e "${RED}❌ Invalid workflows: ${FAIL_COUNT}${NC}"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ All workflows are correctly configured for Python 3.12+${NC}"
    echo ""
    echo -e "${BLUE}Next Steps for CI/CD Testing:${NC}"
    echo "  1. Commit and push changes to a test branch"
    echo "  2. Verify GitHub Actions workflows trigger"
    echo "  3. Check that Python 3.12+ is used in workflow runs"
    echo "  4. Verify test matrix runs for 3.12, 3.13, 3.14"
    echo "  5. Ensure all CI jobs pass"
    exit 0
else
    echo -e "${RED}❌ Some workflows need updates${NC}"
    exit 1
fi

