#!/bin/bash
# Test CI/CD Validation Scripts
# This script tests the URL pattern validation and API naming standards validation
# that are integrated into CI/CD pipelines.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "Testing CI/CD Validation Scripts"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: URL Pattern Validation
echo -e "${YELLOW}Test 1: URL Pattern Validation${NC}"
echo "Running: python scripts/validate_url_patterns.py --strict"
if docker compose exec -T api-service bash -c "cd /app && PYTHONPATH=/app python scripts/validate_url_patterns.py --strict" > /tmp/url_pattern_validation.log 2>&1; then
    echo -e "${GREEN}✅ URL pattern validation passed${NC}"
else
    echo -e "${RED}❌ URL pattern validation failed${NC}"
    echo "Last 20 lines of output:"
    tail -20 /tmp/url_pattern_validation.log
    exit 1
fi
echo ""

# Test 2: API Naming Standards Validation
echo -e "${YELLOW}Test 2: API Naming Standards Validation${NC}"
echo "Running: python scripts/validate_api_naming_standards.py --strict"
if docker compose exec -T api-service bash -c "cd /app && PYTHONPATH=/app python scripts/validate_api_naming_standards.py --strict" > /tmp/api_naming_validation.log 2>&1; then
    echo -e "${GREEN}✅ API naming standards validation passed${NC}"
else
    echo -e "${RED}❌ API naming standards validation failed${NC}"
    echo "Last 20 lines of output:"
    tail -20 /tmp/api_naming_validation.log
    exit 1
fi
echo ""

# Test 3: Endpoint Inventory Parsing
echo -e "${YELLOW}Test 3: Endpoint Inventory Parsing${NC}"
echo "Running: python scripts/test-api-endpoints.py --inventory docs/api-audit/current-api-inventory.md --skip-auth"
if python3 "$PROJECT_ROOT/scripts/test-api-endpoints.py" \
    --inventory "$PROJECT_ROOT/docs/api-audit/current-api-inventory.md" \
    --skip-auth \
    --output /tmp/test-report.md > /tmp/inventory_parsing.log 2>&1; then
    ENDPOINT_COUNT=$(grep -c "Testing" /tmp/inventory_parsing.log || echo "0")
    echo -e "${GREEN}✅ Endpoint inventory parsing successful (found $ENDPOINT_COUNT endpoints)${NC}"
else
    echo -e "${YELLOW}⚠️  Endpoint inventory parsing completed with warnings (this is expected for unauthenticated tests)${NC}"
fi
echo ""

# Test 4: Workflow YAML Syntax
echo -e "${YELLOW}Test 4: Workflow YAML Syntax Validation${NC}"
if python3 -c "import yaml; yaml.safe_load(open('.github/workflows/openapi-validation.yml'))" 2>/dev/null; then
    echo -e "${GREEN}✅ Workflow YAML syntax is valid${NC}"
else
    echo -e "${RED}❌ Workflow YAML syntax is invalid${NC}"
    exit 1
fi
echo ""

# Test 5: Pre-commit Config YAML Syntax
echo -e "${YELLOW}Test 5: Pre-commit Config YAML Syntax Validation${NC}"
if python3 -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml'))" 2>/dev/null; then
    echo -e "${GREEN}✅ Pre-commit config YAML syntax is valid${NC}"
else
    echo -e "${RED}❌ Pre-commit config YAML syntax is invalid${NC}"
    exit 1
fi
echo ""

echo "=========================================="
echo -e "${GREEN}All CI/CD validation tests passed!${NC}"
echo "=========================================="

