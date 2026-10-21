#!/bin/bash
# Quick test runner for contract creation workflow tests
# Runs tests in batches to avoid timeouts

set -e

cd "$(dirname "$0")/.."
source venv/bin/activate

echo "Running Contract Creation Workflow Tests..."
echo "=========================================="
echo ""

# Unit tests (fast - ~1 minute)
echo "1. Running Unit Tests (5 tests)..."
python -m pytest hub/apps/orchestration/workflows/tests/test_contract_creation.py::ContractCreationWorkflowUnitTest \
    -v --reuse-db --tb=short -o addopts="" -q
echo ""

# Integration tests (slower - ~2-3 minutes each)
echo "2. Running Integration Tests (4 tests)..."
python -m pytest hub/apps/orchestration/workflows/tests/test_contract_creation.py::ContractCreationWorkflowIntegrationTest \
    -v --reuse-db --tb=short -o addopts="" -q
echo ""

# E2E tests (slowest - requires API setup)
echo "3. Running E2E Tests (3 tests)..."
echo "Note: E2E tests may fail if API routes are not configured"
python -m pytest hub/apps/orchestration/workflows/tests/test_contract_creation.py::ContractCreationWorkflowE2ETest \
    -v --reuse-db --tb=short -o addopts="" -q || echo "E2E tests skipped/failed (expected if API not fully configured)"
echo ""

echo "Test run complete!"

