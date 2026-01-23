#!/bin/bash
# Background test runner for Marketplace Integration Comprehensive Validation Tests
# This script runs tests in the background and monitors progress

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

OUTPUT_DIR="/tmp/marketplace_test_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "Marketplace Integration Comprehensive Validation Tests"
echo "Running in background..."
echo "Output directory: $OUTPUT_DIR"
echo "=========================================="
echo ""

# Run tests in background
nohup docker compose exec -T api-service bash -c \
    "cd /app && python hub/manage.py test \
    hub.apps.integrations.tests.test_marketplace_integration_service_comprehensive_validation \
    --verbosity=2 --keepdb --no-input" \
    > "$OUTPUT_DIR/full_output.log" 2>&1 &

TEST_PID=$!
echo "Test process started with PID: $TEST_PID"
echo "Monitor progress: tail -f $OUTPUT_DIR/full_output.log"
echo ""

# Wait and monitor
while kill -0 $TEST_PID 2>/dev/null; do
    sleep 10
    # Extract summary from log
    if grep -q "Ran.*test" "$OUTPUT_DIR/full_output.log" 2>/dev/null; then
        echo "Tests are running..."
        tail -5 "$OUTPUT_DIR/full_output.log" | grep -E "(OK|FAIL|ERROR|test_|Ran)" || true
    fi
done

# Wait for process to complete
wait $TEST_PID
EXIT_CODE=$?

echo ""
echo "=========================================="
echo "Test Execution Complete"
echo "=========================================="
echo "Exit code: $EXIT_CODE"
echo "Full output: $OUTPUT_DIR/full_output.log"
echo ""

# Extract summary
if [ -f "$OUTPUT_DIR/full_output.log" ]; then
    echo "Test Summary:"
    grep -E "^(Ran|OK|FAIL|ERROR)" "$OUTPUT_DIR/full_output.log" | tail -10 || echo "No summary found"
    echo ""

    if grep -q "FAIL\|ERROR" "$OUTPUT_DIR/full_output.log"; then
        echo "Failures found:"
        grep -A 5 "FAIL\|ERROR\|AssertionError\|Exception" "$OUTPUT_DIR/full_output.log" | head -50
    fi
fi

exit $EXIT_CODE
