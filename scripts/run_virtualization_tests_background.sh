#!/bin/bash
# Background test runner for Virtualization Service Comprehensive Validation Tests
# This script runs tests in the background and captures output

set -e

TEST_FILE="tests.integration.test_virtualization_service_comprehensive_validation"
OUTPUT_DIR="tests/integration/virtualization_test_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="${OUTPUT_DIR}/test_results_${TIMESTAMP}.log"
PID_FILE="${OUTPUT_DIR}/test_pid_${TIMESTAMP}.txt"

mkdir -p "$OUTPUT_DIR"

echo "Starting virtualization tests in background..."
echo "Output will be written to: $OUTPUT_FILE"
echo "PID will be saved to: $PID_FILE"
echo ""

# Run tests in background
(
    docker compose exec -T api-service bash -c \
      "cd /app && python hub/manage.py test $TEST_FILE \
        --verbosity=2 \
        --keepdb \
        --no-input \
        --failfast" \
      2>&1 | tee "$OUTPUT_FILE"
    
    EXIT_CODE=${PIPESTATUS[0]}
    echo "" >> "$OUTPUT_FILE"
    echo "==========================================" >> "$OUTPUT_FILE"
    echo "Test execution completed with exit code: $EXIT_CODE" >> "$OUTPUT_FILE"
    echo "==========================================" >> "$OUTPUT_FILE"
    
    # Extract summary
    echo "" >> "$OUTPUT_FILE"
    echo "=== Test Summary ===" >> "$OUTPUT_FILE"
    grep -E "(FAILED|ERROR|OK|PASSED|skipped|AssertionError)" "$OUTPUT_FILE" | tail -50 >> "$OUTPUT_FILE" || true
    
    exit $EXIT_CODE
) &

BG_PID=$!
echo $BG_PID > "$PID_FILE"

echo "Test process started with PID: $BG_PID"
echo "Monitor progress with: tail -f $OUTPUT_FILE"
echo "Check if still running: ps -p $BG_PID"
echo "Stop test: kill $BG_PID"
echo ""
echo "Waiting for initial output..."

# Wait a bit and show initial output
sleep 5
if [ -f "$OUTPUT_FILE" ]; then
    echo "=== Initial Output ==="
    tail -20 "$OUTPUT_FILE" || echo "No output yet..."
fi
