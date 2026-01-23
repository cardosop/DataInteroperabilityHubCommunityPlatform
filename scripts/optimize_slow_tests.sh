#!/bin/bash
# Script to optimize slow tests by:
# 1. Running tests with --reuse-db
# 2. Skipping performance tests by default
# 3. Running tests in smaller batches
# 4. Using pytest markers to categorize tests

set -e

cd /home/ph/Desktop/DataInteroperabilityHub

echo "=== Optimizing Slow Tests ==="
echo ""

# Run tests excluding performance tests (can be run separately)
echo "Running tests excluding performance tests..."
docker compose exec -T api-service bash -c "cd /app && python -m pytest tests/integration/test_*_new_use_cases_comprehensive.py -v --tb=line --reuse-db -m 'not slow and not performance'" 2>&1 | tee /tmp/optimized_tests.log

echo ""
echo "=== Test Optimization Complete ==="
echo "Performance tests can be run separately with:"
echo "pytest -m performance tests/integration/test_*_new_use_cases_comprehensive.py"
