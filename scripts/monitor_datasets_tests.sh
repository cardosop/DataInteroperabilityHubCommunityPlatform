#!/bin/bash
# Monitor datasets comprehensive test execution

OUTPUT_FILE="/tmp/datasets_comprehensive_final.txt"
MAX_WAIT=2400  # 40 minutes
CHECK_INTERVAL=30
ELAPSED=0

echo "Monitoring test execution..."
echo "Output file: $OUTPUT_FILE"
echo "Max wait time: ${MAX_WAIT}s"
echo ""

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if [ -f "$OUTPUT_FILE" ]; then
        LINES=$(wc -l < "$OUTPUT_FILE" 2>/dev/null || echo "0")
        echo "[$(date +%H:%M:%S)] File has $LINES lines"
        
        # Check for completion
        if grep -q "^Ran.*tests" "$OUTPUT_FILE" 2>/dev/null; then
            echo ""
            echo "✅ Tests completed!"
            echo ""
            echo "=== FINAL RESULTS ==="
            tail -20 "$OUTPUT_FILE" | grep -E "(^Ran|^OK|^FAILED|errors=|failures=)"
            echo ""
            echo "=== ERRORS (if any) ==="
            grep -E "^ERROR|^FAIL" "$OUTPUT_FILE" | tail -10
            exit 0
        fi
        
        # Check for errors
        if grep -q "^ERROR:" "$OUTPUT_FILE" 2>/dev/null; then
            ERROR_COUNT=$(grep -c "^ERROR:" "$OUTPUT_FILE" 2>/dev/null || echo "0")
            echo "  ⚠️  Found $ERROR_COUNT errors so far"
        fi
    else
        echo "[$(date +%H:%M:%S)] Waiting for output file..."
    fi
    
    # Check if process is still running
    if ! pgrep -f "test.*datasets.*comprehensive_validation" > /dev/null; then
        echo ""
        echo "⚠️  Test process not found. Checking final output..."
        if [ -f "$OUTPUT_FILE" ]; then
            echo ""
            echo "=== FINAL RESULTS ==="
            tail -30 "$OUTPUT_FILE" | grep -E "(^Ran|^OK|^FAILED|errors=|failures=)"
        fi
        exit 1
    fi
    
    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

echo ""
echo "⏱️  Max wait time reached. Checking current status..."
if [ -f "$OUTPUT_FILE" ]; then
    echo ""
    echo "=== CURRENT STATUS ==="
    tail -30 "$OUTPUT_FILE" | grep -E "(^Ran|^OK|^FAILED|ERROR|test_)" | tail -20
fi
