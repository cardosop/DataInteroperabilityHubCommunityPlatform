#!/bin/bash
# Run a single new use cases test with proper timeout and output handling

set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 <test_path> [timeout_seconds]"
    echo "Example: $0 tests/integration/test_social_features_new_use_cases_comprehensive.py::UCSOCIAL001RateAssetTest::test_rate_asset_success"
    exit 1
fi

TEST_PATH=$1
TIMEOUT=${2:-1800}  # Default 30 minutes

echo "=========================================="
echo "Running test: $TEST_PATH"
echo "Timeout: ${TIMEOUT}s"
echo "=========================================="
echo ""

# Run test with timeout
if timeout $TIMEOUT docker compose exec -T api-service bash -c "cd /app && python -m pytest $TEST_PATH -v --tb=short -x" 2>&1 | tee /tmp/test_single_output.log; then
    echo ""
    echo "=========================================="
    echo "✅ Test PASSED"
    echo "=========================================="
    exit 0
else
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        echo ""
        echo "=========================================="
        echo "⏱️  Test TIMEOUT (exceeded ${TIMEOUT}s)"
        echo "=========================================="
        echo "Last 50 lines of output:"
        tail -50 /tmp/test_single_output.log
    else
        echo ""
        echo "=========================================="
        echo "❌ Test FAILED (exit code: $EXIT_CODE)"
        echo "=========================================="
        echo "Last 50 lines of output:"
        tail -50 /tmp/test_single_output.log
    fi
    exit $EXIT_CODE
fi
