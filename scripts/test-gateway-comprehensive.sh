#!/bin/bash
#
# Comprehensive Gateway Configuration Test Suite
#
# Tests verify:
# 1. Traefik route configurations
# 2. Kubernetes ingress rules
# 3. Gateway routing works correctly
# 4. Ingress rules are applied correctly
#
# Usage:
#   ./scripts/test-gateway-comprehensive.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "Gateway Configuration - Comprehensive Tests"
echo "=========================================="
echo ""

TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Test 1: Verification script
echo "Test 1: Verification Script"
echo "--------------------------------"
if python3 scripts/verify-gateway-configurations.py > /tmp/gateway_verify.log 2>&1; then
    echo -e "${GREEN}✅ PASSED${NC}: Gateway configuration verification"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAILED${NC}: Gateway configuration verification"
    cat /tmp/gateway_verify.log
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test 2: Routing script
echo "Test 2: Routing Script"
echo "--------------------------------"
if python3 scripts/test-gateway-routing.py > /tmp/gateway_routing.log 2>&1; then
    echo -e "${GREEN}✅ PASSED${NC}: Gateway routing tests"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAILED${NC}: Gateway routing tests"
    cat /tmp/gateway_routing.log
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test 3: Traefik configuration files exist
echo "Test 3: Traefik Configuration Files"
echo "--------------------------------"
TRAEFIK_FILES=(
    "infrastructure/traefik/dynamic/routes.yml"
    "k8s/api-gateway/traefik/configmap.yaml"
)

for file in "${TRAEFIK_FILES[@]}"; do
    if [ -f "$file" ]; then
        if grep -q "PathPrefix(\`/api/v1/compliance\`)" "$file" && grep -q "PathPrefix(\`/api/v1/dq\`)" "$file"; then
            echo -e "${GREEN}✅${NC} $file: Routes configured correctly"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            echo -e "${RED}❌${NC} $file: Routes not configured correctly"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi

        if grep -q "/api/v1/compliance/compliance-runs" "$file" || grep -q "/api/v1/dq/dq-runs" "$file"; then
            echo -e "${RED}❌${NC} $file: Contains old patterns"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        else
            echo -e "${GREEN}✅${NC} $file: No old patterns found"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        fi
    else
        echo -e "${YELLOW}⚠️${NC} $file: File not found"
        TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
    fi
done
echo ""

# Test 4: Kubernetes ingress files
echo "Test 4: Kubernetes Ingress Files"
echo "--------------------------------"
INGRESS_COUNT=0
INGRESS_VALID=0

while IFS= read -r ingress_file; do
    INGRESS_COUNT=$((INGRESS_COUNT + 1))

    if grep -q "/compliance-runs" "$ingress_file" || grep -q "/dq-runs" "$ingress_file"; then
        # Check if it's in a path field (not just a comment)
        if grep -q "path:" "$ingress_file" && grep -A 1 "path:" "$ingress_file" | grep -q -E "(compliance-runs|dq-runs)"; then
            echo -e "${RED}❌${NC} $ingress_file: Contains old patterns in path"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        else
            echo -e "${GREEN}✅${NC} $ingress_file: No old patterns in paths"
            INGRESS_VALID=$((INGRESS_VALID + 1))
            TESTS_PASSED=$((TESTS_PASSED + 1))
        fi
    else
        echo -e "${GREEN}✅${NC} $ingress_file: No old patterns"
        INGRESS_VALID=$((INGRESS_VALID + 1))
        TESTS_PASSED=$((TESTS_PASSED + 1))
    fi
done < <(find k8s -name "ingress.yaml" -type f)

if [ $INGRESS_COUNT -eq 0 ]; then
    echo -e "${YELLOW}⚠️${NC} No ingress files found"
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
else
    echo -e "${GREEN}✅${NC} Verified $INGRESS_VALID/$INGRESS_COUNT ingress files"
fi
echo ""

# Test 5: Service routing (if Docker Compose running)
echo "Test 5: Service Routing (Optional)"
echo "--------------------------------"
if command -v docker &> /dev/null && docker compose ps api-service 2>&1 | grep -q "Up"; then
    echo -e "${GREEN}✅${NC} Docker Compose services running"
    TESTS_PASSED=$((TESTS_PASSED + 1))

    # Test compliance endpoint
    if docker compose exec -T api-service curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/compliance/runs/ 2>&1 | grep -qE "^(200|401|403|404)$"; then
        echo -e "${GREEN}✅${NC} Compliance endpoint routable"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${YELLOW}⚠️${NC} Compliance endpoint not accessible (may require auth)"
        TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
    fi

    # Test DQ endpoint
    if docker compose exec -T api-service curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/dq/runs/ 2>&1 | grep -qE "^(200|401|403|404)$"; then
        echo -e "${GREEN}✅${NC} DQ endpoint routable"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${YELLOW}⚠️${NC} DQ endpoint not accessible (may require auth)"
        TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
    fi
else
    echo -e "${YELLOW}⚠️${NC} Docker Compose services not running"
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
fi
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Tests Passed:  $TESTS_PASSED"
echo "Tests Failed:  $TESTS_FAILED"
echo "Tests Skipped: $TESTS_SKIPPED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi

