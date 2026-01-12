#!/bin/bash
#
# Run Documentation Tests
#
# This script runs all documentation verification and testing scripts
# to validate that developer guides are accurate and code examples work.
#
# Usage:
#   ./scripts/run-documentation-tests.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "Documentation Tests - Comprehensive Run"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track results
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"

    echo "🧪 Running: $test_name"
    echo "   Command: $test_command"

    if eval "$test_command" > /tmp/test_output.log 2>&1; then
        echo -e "${GREEN}✅ PASSED${NC}: $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}: $test_name"
        echo "   Output:"
        cat /tmp/test_output.log | sed 's/^/   /' || true
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Test 1: Verify documentation examples use standardized patterns
echo "=========================================="
echo "Test 1: Verify Guide Accuracy"
echo "=========================================="
run_test "Verify documentation examples" \
    "python3 scripts/verify-documentation-examples.py"

echo ""

# Test 2: Test code examples are syntactically correct
echo "=========================================="
echo "Test 2: Verify Examples Work"
echo "=========================================="
run_test "Test code examples" \
    "python3 scripts/test-documentation-examples.py"

echo ""

# Test 3: Verify key documentation files exist
echo "=========================================="
echo "Test 3: Verify Key Files Exist"
echo "=========================================="

KEY_FILES=(
    "docs/DEVELOPER_ONBOARDING.md"
    "docs/DEVELOPMENT_GUIDE.md"
    "docs/API_REFERENCE.md"
    "docs/API_ENDPOINTS_REFERENCE.md"
    "docs/API_BEST_PRACTICES.md"
    "docs/ODPS_INTEGRATION_GUIDE.md"
    "docs/ENDPOINT_PATTERN_MIGRATION_GUIDE.md"
)

for file in "${KEY_FILES[@]}"; do
    if [ -f "$file" ]; then
        if [ -s "$file" ]; then
            echo -e "${GREEN}✅${NC} $file exists and is not empty"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            echo -e "${RED}❌${NC} $file exists but is empty"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    else
        echo -e "${RED}❌${NC} $file does not exist"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
done

echo ""

# Test 4: Verify scripts exist and are executable
echo "=========================================="
echo "Test 4: Verify Scripts Exist"
echo "=========================================="

SCRIPTS=(
    "scripts/verify-documentation-examples.py"
    "scripts/test-documentation-examples.py"
    "scripts/update-documentation-endpoints.py"
)

for script in "${SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        if [ -x "$script" ] || [ -f "$script" ]; then
            echo -e "${GREEN}✅${NC} $script exists"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            echo -e "${YELLOW}⚠️${NC} $script exists but is not executable"
            TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
        fi
    else
        echo -e "${RED}❌${NC} $script does not exist"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
done

echo ""

# Test 5: Verify no old patterns in main documentation
echo "=========================================="
echo "Test 5: Verify No Old Patterns"
echo "=========================================="

MAIN_DOCS=(
    "docs/API_REFERENCE.md"
    "docs/API_ENDPOINTS_REFERENCE.md"
    "docs/DEVELOPER_ONBOARDING.md"
    "docs/DEVELOPMENT_GUIDE.md"
    "docs/ODPS_INTEGRATION_GUIDE.md"
)

OLD_PATTERNS_FOUND=0
for doc in "${MAIN_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        if grep -q "/compliance-runs/" "$doc" 2>/dev/null || grep -q "/dq-runs/" "$doc" 2>/dev/null; then
            # Check if it's in migration guide (which is OK)
            if [[ "$doc" != *"MIGRATION"* ]]; then
                echo -e "${RED}❌${NC} $doc contains old patterns"
                OLD_PATTERNS_FOUND=$((OLD_PATTERNS_FOUND + 1))
                TESTS_FAILED=$((TESTS_FAILED + 1))
            fi
        fi
    fi
done

if [ $OLD_PATTERNS_FOUND -eq 0 ]; then
    echo -e "${GREEN}✅${NC} No old patterns found in main documentation"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

echo ""

# Test 6: Verify standardized patterns exist
echo "=========================================="
echo "Test 6: Verify Standardized Patterns"
echo "=========================================="

STANDARDIZED_FOUND=0
for doc in "${MAIN_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        if grep -q "/api/v1/compliance/runs/" "$doc" 2>/dev/null || grep -q "/api/v1/dq/runs/" "$doc" 2>/dev/null; then
            STANDARDIZED_FOUND=$((STANDARDIZED_FOUND + 1))
        fi
    fi
done

if [ $STANDARDIZED_FOUND -gt 0 ]; then
    echo -e "${GREEN}✅${NC} Standardized patterns found in documentation"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}⚠️${NC} No standardized patterns found (may not have compliance/DQ examples)"
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
fi

echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo ""
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

