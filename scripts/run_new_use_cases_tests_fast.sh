#!/bin/bash
# Fast test runner - skips performance and slow tests
# Usage: ./scripts/run_new_use_cases_tests_fast.sh

set -e

cd /home/ph/Desktop/DataInteroperabilityHub

echo "=== Running New Use Cases Tests (Fast Mode - Excluding Performance) ==="
echo ""

docker compose exec -T api-service bash -c "cd /app && python -m pytest tests/integration/test_*_new_use_cases_comprehensive.py -v --tb=line --reuse-db -m 'not performance'" 2>&1 | tee /tmp/new_use_cases_fast.log

echo ""
echo "=== Fast Test Run Complete ==="
echo "To run performance tests separately:"
echo "pytest -m performance tests/integration/test_*_new_use_cases_comprehensive.py"
