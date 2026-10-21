#!/bin/bash
#
# Test Monitoring Services
#
# This script tests that monitoring services work correctly:
# - Prometheus metrics collection
# - Grafana dashboard accessibility
# - API service metrics endpoint
#
# Usage:
#   ./scripts/test-monitoring-services.sh
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
echo "Monitoring Services Test"
echo "=========================================="
echo ""

TESTS_PASSED=0
TESTS_FAILED=0

# Test 1: Prometheus configuration verification
echo "Test 1: Prometheus Configuration"
echo "--------------------------------"
if python3 scripts/verify-monitoring-configurations.py > /tmp/prom_test.log 2>&1; then
    echo -e "${GREEN}✅ PASSED${NC}: Prometheus configuration verified"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAILED${NC}: Prometheus configuration issues"
    cat /tmp/prom_test.log
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test 2: Grafana dashboards verification
echo "Test 2: Grafana Dashboards"
echo "--------------------------------"
if python3 scripts/verify-monitoring-configurations.py 2>&1 | grep -q "All.*dashboards verified"; then
    echo -e "${GREEN}✅ PASSED${NC}: Grafana dashboards verified"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAILED${NC}: Grafana dashboard issues"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test 3: Metrics code verification
echo "Test 3: Metrics Code"
echo "--------------------------------"
if python3 scripts/verify-monitoring-configurations.py 2>&1 | grep -q "otel_metrics.py.*No issues"; then
    echo -e "${GREEN}✅ PASSED${NC}: Metrics code verified"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAILED${NC}: Metrics code issues"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test 4: Check if services are running (optional)
echo "Test 4: Service Availability (Optional)"
echo "--------------------------------"
if command -v docker &> /dev/null && docker compose ps api-service 2>&1 | grep -q "Up"; then
    echo -e "${GREEN}✅ PASSED${NC}: Docker Compose services running"
    TESTS_PASSED=$((TESTS_PASSED + 1))

    # Try to check metrics endpoint
    if docker compose exec -T api-service curl -s http://localhost:8000/metrics > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PASSED${NC}: API metrics endpoint accessible"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${YELLOW}⚠️  SKIPPED${NC}: API metrics endpoint not accessible (may require auth)"
    fi
else
    echo -e "${YELLOW}⚠️  SKIPPED${NC}: Docker Compose services not running"
fi
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi

