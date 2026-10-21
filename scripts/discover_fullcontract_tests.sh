#!/bin/bash
# Discover all test files created/modified in fullcontract change
# Organizes them into logical parallel batches

set -euo pipefail

cd "$(dirname "$0")/.." || exit 1

echo "Discovering all test files for fullcontract change..."
echo "=================================================="
echo ""

# Discover all test files
echo "## Contracts App Tests (Phase 0, 0a, 0b, 1-4, 15)"
find hub/apps/contracts/tests -name "test_*.py" -type f | sort

echo ""
echo "## Regression Tests (Phase 0.1.2 - Django 6)"
find tests/regression -name "test_*.py" -type f 2>/dev/null | sort

echo ""
echo "## Integration Tests"
find tests/integration -name "test_*.py" -type f 2>/dev/null | sort

echo ""
echo "## E2E Tests"
find tests/e2e -name "test_*.py" -type f 2>/dev/null | sort

echo ""
echo "## Service Tests"
find services -name "test_*.py" -type f 2>/dev/null | sort

echo ""
echo "## Other App Tests (related to fullcontract)"
find hub/apps -name "test_*.py" -type f | grep -E "(datasets|dq|governance|observability|search|scheduled_ingestion|assets|versioning)" | sort

echo ""
echo "## Test Count Summary"
echo "Contracts tests: $(find hub/apps/contracts/tests -name "test_*.py" -type f | wc -l)"
echo "Regression tests: $(find tests/regression -name "test_*.py" -type f 2>/dev/null | wc -l)"
echo "Integration tests: $(find tests/integration -name "test_*.py" -type f 2>/dev/null | wc -l)"
echo "E2E tests: $(find tests/e2e -name "test_*.py" -type f 2>/dev/null | wc -l)"
echo "Service tests: $(find services -name "test_*.py" -type f 2>/dev/null | wc -l)"
echo "Total: $(find . -path "*/tests/*" -name "test_*.py" -type f 2>/dev/null | grep -v __pycache__ | wc -l)"

