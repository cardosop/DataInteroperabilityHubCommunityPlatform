#!/bin/bash
# Generate Test Coverage Report for DCS Removal
#
# This script generates a comprehensive test coverage report for Phase 0.2
# (DCS removal) changes, showing coverage metrics and identifying gaps.
#
# Usage:
#   ./scripts/generate_test_coverage_report.sh [--html] [--xml]
#
# Exit codes:
#   0 - Report generated successfully
#   1 - Report generation failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
HTML_REPORT=false
XML_REPORT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --html)
            HTML_REPORT=true
            shift
            ;;
        --xml)
            XML_REPORT=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--html] [--xml]"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "Test Coverage Report Generation"
echo "=========================================="
echo ""

# Check if pytest and coverage are available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: python3 not found${NC}"
    exit 1
fi

if ! python3 -m pytest --version &> /dev/null; then
    echo -e "${RED}ERROR: pytest not found${NC}"
    exit 1
fi

# Check if pytest-cov is available
if ! python3 -c "import pytest_cov" &> /dev/null; then
    echo -e "${YELLOW}WARNING: pytest-cov not found. Installing...${NC}"
    pip install pytest-cov || {
        echo -e "${RED}ERROR: Failed to install pytest-cov${NC}"
        exit 1
    }
fi

# Set up environment
export DJANGO_SETTINGS_MODULE=hub.settings
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Coverage arguments
COVERAGE_ARGS=(
    "--cov=hub.apps.contracts"
    "--cov=services.datacontract-service"
    "--cov=services.semantic-service"
    "--cov-report=term-missing"
)

if [ "$HTML_REPORT" = true ]; then
    COVERAGE_ARGS+=("--cov-report=html:htmlcov/dcs_removal")
    echo "HTML report will be generated in htmlcov/dcs_removal/"
fi

if [ "$XML_REPORT" = true ]; then
    COVERAGE_ARGS+=("--cov-report=xml:coverage_dcs_removal.xml")
    echo "XML report will be generated as coverage_dcs_removal.xml"
fi

# Test files to include
TEST_FILES=(
    "hub/apps/contracts/tests/test_dcs_rejection.py"
    "tests/integration/test_dcs_removal_integration.py"
    "hub/apps/contracts/tests/test_migration.py::DCSRemovalMigrationTest"
    "hub/apps/contracts/tests/test_normalization.py"
    "hub/apps/contracts/tests/test_spec_detection.py"
)

# Files to measure coverage for
COVERAGE_MODULES=(
    "hub/apps/contracts/normalization.py"
    "hub/apps/contracts/spec_detection.py"
    "hub/apps/contracts/models.py"
    "hub/apps/contracts/views.py"
    "services/datacontract-service/normalize.py"
)

echo "Running tests with coverage..."
echo ""

# Run tests with coverage
if python3 -m pytest "${COVERAGE_ARGS[@]}" "${TEST_FILES[@]}" --tb=short; then
    echo ""
    echo -e "${GREEN}✓ Tests passed${NC}"
else
    echo ""
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi

# Generate summary
echo ""
echo "=========================================="
echo "Coverage Summary"
echo "=========================================="

if [ "$HTML_REPORT" = true ]; then
    echo -e "${GREEN}HTML report: htmlcov/dcs_removal/index.html${NC}"
fi

if [ "$XML_REPORT" = true ]; then
    echo -e "${GREEN}XML report: coverage_dcs_removal.xml${NC}"
fi

echo ""
echo "Coverage metrics are displayed above."
echo "Review the reports to identify any coverage gaps."
echo ""

exit 0

