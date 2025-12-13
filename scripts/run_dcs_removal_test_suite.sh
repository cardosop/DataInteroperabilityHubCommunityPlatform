#!/bin/bash
# Run DCS Removal Test Suite
#
# This script runs all tests related to DCS removal to ensure the system
# correctly rejects DCS contracts and accepts ODCS contracts.
#
# Usage:
#   ./scripts/run_dcs_removal_test_suite.sh [--verbose] [--coverage]
#
# Exit codes:
#   0 - All tests passed
#   1 - Tests failed
#   2 - Test environment not set up correctly

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
VERBOSE=false
COVERAGE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --coverage|-c)
            COVERAGE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--verbose] [--coverage]"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "DCS Removal Test Suite"
echo "=========================================="
echo ""

# Check if Django is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: python3 not found${NC}"
    exit 2
fi

# Check if pytest is available
if ! python3 -m pytest --version &> /dev/null; then
    echo -e "${RED}ERROR: pytest not found. Install with: pip install pytest pytest-django${NC}"
    exit 2
fi

# Set up test environment variables
export DJANGO_SETTINGS_MODULE=hub.settings
export PYTHONPATH="${PYTHONPATH:-}:$PROJECT_ROOT"

# Test categories
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Function to run test category
run_test_category() {
    local category_name="$1"
    local test_path="$2"
    local description="$3"
    
    echo "----------------------------------------"
    echo "Running: $category_name"
    echo "Description: $description"
    echo "----------------------------------------"
    
    if [ ! -f "$test_path" ] && [ ! -d "$test_path" ]; then
        echo -e "${YELLOW}WARNING: Test path not found: $test_path${NC}"
        TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
        return
    fi
    
    local pytest_args=()
    if [ "$VERBOSE" = true ]; then
        pytest_args+=("-v")
    else
        pytest_args+=("-q")
    fi
    
    if [ "$COVERAGE" = true ]; then
        pytest_args+=("--cov=hub.apps.contracts" "--cov-report=term-missing" "--cov-report=html")
    fi
    
    if python3 -m pytest "${pytest_args[@]}" "$test_path" --tb=short; then
        echo -e "${GREEN}✓ $category_name: PASSED${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ $category_name: FAILED${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Run test categories
echo "Starting test execution..."
echo ""

# 1. DCS Rejection Tests
run_test_category \
    "DCS Rejection Tests" \
    "hub/apps/contracts/tests/test_dcs_rejection.py" \
    "Tests that DCS contracts are properly rejected with clear error messages"

# 2. DCS Removal Integration Tests
run_test_category \
    "DCS Removal Integration Tests" \
    "tests/integration/test_dcs_removal_integration.py" \
    "Integration tests for DCS removal across the entire system"

# 3. Migration Tests
run_test_category \
    "Migration Tests" \
    "hub/apps/contracts/tests/test_migration.py::DCSRemovalMigrationTest" \
    "Tests for migration 0004 (DCS removal from enum)"

# 4. Normalization Tests (regression)
run_test_category \
    "Normalization Regression Tests" \
    "hub/apps/contracts/tests/test_normalization.py" \
    "Regression tests to ensure ODCS normalization still works"

# 5. Spec Detection Tests (regression)
run_test_category \
    "Spec Detection Regression Tests" \
    "hub/apps/contracts/tests/test_spec_detection.py" \
    "Regression tests to ensure ODCS spec detection still works"

# 6. API Tests (regression)
run_test_category \
    "API Regression Tests" \
    "hub/apps/contracts/tests/test_views_filtering_sorting.py" \
    "Regression tests to ensure API endpoints work with ODCS contracts"

# Summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
if [ $TESTS_SKIPPED -gt 0 ]; then
    echo -e "${YELLOW}Skipped: $TESTS_SKIPPED${NC}"
fi
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    if [ "$COVERAGE" = true ]; then
        echo ""
        echo "Coverage report generated in htmlcov/index.html"
    fi
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please review the output above.${NC}"
    exit 1
fi

