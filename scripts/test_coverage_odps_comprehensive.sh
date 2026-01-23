#!/bin/bash
#
# Comprehensive ODPS Test Coverage Script
#
# This script runs all ODPS test coverage validations:
# - Unit test coverage (90%+ target)
# - Integration test coverage
# - E2E test coverage
# - Generates unified coverage report
#
# Engineering-grade implementation:
# - No mocks/stubs - uses real implementations
# - Root cause fixes - addresses underlying issues
# - Comprehensive coverage - all modules tested
# - Best practices - follows testing standards

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo -e "${BOLD}${BLUE}========================================${NC}"
echo -e "${BOLD}${BLUE}ODPS Comprehensive Test Coverage${NC}"
echo -e "${BOLD}${BLUE}========================================${NC}"
echo ""

# Track overall success
OVERALL_SUCCESS=0

# Function to run a coverage script and capture results
run_coverage_script() {
    local script_name=$1
    local description=$2

    echo -e "${BOLD}Running: ${description}${NC}"
    echo "----------------------------------------"

    if python3 "$SCRIPT_DIR/$script_name"; then
        echo -e "${GREEN}✓ ${description} completed successfully${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ ${description} failed${NC}"
        echo ""
        OVERALL_SUCCESS=1
        return 1
    fi
}

# Run unit test coverage
run_coverage_script \
    "test_coverage_odps_unit.py" \
    "Unit Test Coverage (90%+ target for normalizers, generators, resolvers)"

# Run integration test coverage
run_coverage_script \
    "test_coverage_odps_integration.py" \
    "Integration Test Coverage (creation flows, export endpoints, linking, semantic mapping)"

# Run E2E test coverage
run_coverage_script \
    "test_coverage_odps_e2e.py" \
    "E2E Test Coverage (user journeys, creation flows, export/download workflows)"

# Generate unified report
echo -e "${BOLD}Generating Unified Coverage Report${NC}"
echo "----------------------------------------"

UNIFIED_REPORT="$PROJECT_ROOT/odps_comprehensive_test_coverage_report.txt"

cat > "$UNIFIED_REPORT" << 'EOF'
================================================================================
ODPS Comprehensive Test Coverage Report
================================================================================
Generated: $(date -Iseconds)

This report consolidates coverage results from:
- Unit tests (90%+ target for ODPS modules)
- Integration tests (all creation flows, export endpoints, linking, semantic mapping)
- E2E tests (complete user journeys, creation flows, export/download workflows)

================================================================================
EOF

# Append individual reports if they exist
if [ -f "$PROJECT_ROOT/odps_unit_test_coverage_report.txt" ]; then
    echo "" >> "$UNIFIED_REPORT"
    echo "UNIT TEST COVERAGE" >> "$UNIFIED_REPORT"
    echo "================================================================================" >> "$UNIFIED_REPORT"
    cat "$PROJECT_ROOT/odps_unit_test_coverage_report.txt" >> "$UNIFIED_REPORT"
fi

if [ -f "$PROJECT_ROOT/odps_integration_test_coverage_report.txt" ]; then
    echo "" >> "$UNIFIED_REPORT"
    echo "INTEGRATION TEST COVERAGE" >> "$UNIFIED_REPORT"
    echo "================================================================================" >> "$UNIFIED_REPORT"
    cat "$PROJECT_ROOT/odps_integration_test_coverage_report.txt" >> "$UNIFIED_REPORT"
fi

if [ -f "$PROJECT_ROOT/odps_e2e_test_coverage_report.txt" ]; then
    echo "" >> "$UNIFIED_REPORT"
    echo "E2E TEST COVERAGE" >> "$UNIFIED_REPORT"
    echo "================================================================================" >> "$UNIFIED_REPORT"
    cat "$PROJECT_ROOT/odps_e2e_test_coverage_report.txt" >> "$UNIFIED_REPORT"
fi

echo "" >> "$UNIFIED_REPORT"
echo "================================================================================" >> "$UNIFIED_REPORT"
echo "END OF REPORT" >> "$UNIFIED_REPORT"
echo "================================================================================" >> "$UNIFIED_REPORT"

echo -e "${GREEN}✓ Unified report generated: $UNIFIED_REPORT${NC}"
echo ""

# Final summary
echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}Summary${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""

if [ $OVERALL_SUCCESS -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✓ All test coverage requirements met!${NC}"
    echo ""
    echo "Reports generated:"
    echo "  - Unit tests: $PROJECT_ROOT/odps_unit_test_coverage_report.txt"
    echo "  - Integration tests: $PROJECT_ROOT/odps_integration_test_coverage_report.txt"
    echo "  - E2E tests: $PROJECT_ROOT/odps_e2e_test_coverage_report.txt"
    echo "  - Unified report: $UNIFIED_REPORT"
    exit 0
else
    echo -e "${RED}${BOLD}✗ Some test coverage requirements not met${NC}"
    echo ""
    echo "Please review the individual reports for details:"
    echo "  - Unit tests: $PROJECT_ROOT/odps_unit_test_coverage_report.txt"
    echo "  - Integration tests: $PROJECT_ROOT/odps_integration_test_coverage_report.txt"
    echo "  - E2E tests: $PROJECT_ROOT/odps_e2e_test_coverage_report.txt"
    echo "  - Unified report: $UNIFIED_REPORT"
    exit 1
fi
