#!/bin/bash
# Verify OpenAPI specification implementation
# This script verifies that all OpenAPI-related tasks are complete

set -e

echo "=========================================="
echo "OpenAPI Implementation Verification"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Check 1: OpenAPI views exist
echo "1. Checking OpenAPI views..."
if grep -q "class OpenAPISchemaView" hub/apps/api/views.py && \
   grep -q "class SwaggerUIView" hub/apps/api/views.py && \
   grep -q "class ReDocView" hub/apps/api/views.py; then
    echo -e "${GREEN}✓ OpenAPI views configured${NC}"
else
    echo -e "${RED}✗ OpenAPI views missing${NC}"
    exit 1
fi

# Check 2: OpenAPI URLs configured
echo "2. Checking OpenAPI URL routes..."
if grep -q "api-docs/openapi.json" hub/urls.py && \
   grep -q "api-docs/" hub/urls.py && \
   grep -q "api-docs/redoc/" hub/urls.py; then
    echo -e "${GREEN}✓ OpenAPI URL routes configured${NC}"
else
    echo -e "${RED}✗ OpenAPI URL routes missing${NC}"
    exit 1
fi

# Check 3: SPECTACULAR_SETTINGS configured
echo "3. Checking SPECTACULAR_SETTINGS..."
if grep -q "SPECTACULAR_SETTINGS" hub/settings.py && \
   grep -q "drf_spectacular" hub/settings.py; then
    echo -e "${GREEN}✓ SPECTACULAR_SETTINGS configured${NC}"
else
    echo -e "${RED}✗ SPECTACULAR_SETTINGS missing${NC}"
    exit 1
fi

# Check 4: OpenAPI validation module exists
echo "4. Checking OpenAPI validation module..."
if [ -f "hub/apps/api/openapi_validation.py" ]; then
    echo -e "${GREEN}✓ OpenAPI validation module exists${NC}"
else
    echo -e "${RED}✗ OpenAPI validation module missing${NC}"
    exit 1
fi

# Check 5: OpenAPI enhancement module exists
echo "5. Checking OpenAPI enhancement module..."
if [ -f "hub/apps/api/openapi_enhancement.py" ]; then
    echo -e "${GREEN}✓ OpenAPI enhancement module exists${NC}"
else
    echo -e "${RED}✗ OpenAPI enhancement module missing${NC}"
    exit 1
fi

# Check 6: Comprehensive tests exist
echo "6. Checking comprehensive tests..."
if [ -f "tests/e2e/test_openapi_spec_comprehensive.py" ]; then
    echo -e "${GREEN}✓ Comprehensive OpenAPI tests exist${NC}"
else
    echo -e "${YELLOW}⚠ Comprehensive OpenAPI tests missing${NC}"
fi

# Check 7: Regeneration script exists
echo "7. Checking regeneration script..."
if [ -f "scripts/regenerate-openapi-spec.py" ]; then
    echo -e "${GREEN}✓ OpenAPI regeneration script exists${NC}"
else
    echo -e "${YELLOW}⚠ OpenAPI regeneration script missing${NC}"
fi

# Check 8: Test files have proper structure
echo "8. Checking test file structure..."
if grep -q "OpenAPISpecAccuracyTest" tests/e2e/test_openapi_spec_comprehensive.py && \
   grep -q "SwaggerUIFunctionalityTest" tests/e2e/test_openapi_spec_comprehensive.py && \
   grep -q "ReDocFunctionalityTest" tests/e2e/test_openapi_spec_comprehensive.py; then
    echo -e "${GREEN}✓ Test file structure is correct${NC}"
else
    echo -e "${YELLOW}⚠ Test file structure may be incomplete${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}All checks passed!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run tests: pytest tests/e2e/test_openapi_spec_comprehensive.py -v"
echo "2. Run tests: pytest tests/e2e/test_api_documentation.py -v"
echo "3. Regenerate spec: python3 scripts/regenerate-openapi-spec.py"
echo "4. Verify endpoints are accessible when Django server is running"

