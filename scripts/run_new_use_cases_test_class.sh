#!/bin/bash
# Run a single test class with optimized settings

set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 <test_class_path> [timeout_seconds]"
    echo "Example: $0 tests/integration/test_social_features_new_use_cases_comprehensive.py::UCSOCIAL001RateAssetTest"
    exit 1
fi

TEST_CLASS=$1
TIMEOUT=${2:-2400}  # Default 40 minutes for test classes

echo "=========================================="
echo "Running test class: $TEST_CLASS"
echo "Timeout: ${TIMEOUT}s (${TIMEOUT}/60 minutes)"
echo "Using --reuse-db for faster execution"
echo "=========================================="
echo ""

# Run test class with timeout
if timeout $TIMEOUT docker compose exec -T api-service bash -c "cd /app && python -m pytest $TEST_CLASS -v --tb=line --reuse-db --maxfail=5" 2>&1 | tee /tmp/test_class_output.log; then
    echo ""
    echo "=========================================="
    echo "✅ Test class PASSED"
    echo "=========================================="
    exit 0
else
    EXIT_CODE=$?
    echo ""
    echo "=========================================="
    if [ $EXIT_CODE -eq 124 ]; then
        echo "⏱️  Test class TIMEOUT (exceeded ${TIMEOUT}s)"
    else
        echo "❌ Test class had failures (exit code: $EXIT_CODE)"
    fi
    echo "=========================================="
    echo "Summary:"
    grep -E "PASSED|FAILED|ERROR|SKIPPED" /tmp/test_class_output.log | tail -20
    echo ""
    echo "Full output: /tmp/test_class_output.log"
    exit $EXIT_CODE
fi
