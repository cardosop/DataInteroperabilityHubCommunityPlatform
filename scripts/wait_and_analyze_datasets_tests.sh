#!/bin/bash
# Wait for tests to complete and analyze results

OUTPUT_FILE="/tmp/datasets_comprehensive_final.txt"
MAX_WAIT=3600  # 60 minutes
CHECK_INTERVAL=30
ELAPSED=0

echo "=== Monitoring Datasets Comprehensive Tests ==="
echo "Output file: $OUTPUT_FILE"
echo "Max wait: ${MAX_WAIT}s (${MAX_WAIT}/60 minutes)"
echo ""

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if [ -f "$OUTPUT_FILE" ]; then
        LINES=$(wc -l < "$OUTPUT_FILE" 2>/dev/null || echo "0")
        
        # Check for completion
        if grep -q "^Ran.*tests" "$OUTPUT_FILE" 2>/dev/null; then
            echo ""
            echo "✅ TESTS COMPLETED!"
            echo ""
            echo "=== FINAL RESULTS ==="
            grep -E "(^Ran|^OK|^FAILED|errors=|failures=|skipped=)" "$OUTPUT_FILE" | tail -5
            echo ""
            
            # Count errors and failures
            ERROR_COUNT=$(grep -c "^ERROR:" "$OUTPUT_FILE" 2>/dev/null || echo "0")
            FAIL_COUNT=$(grep -c "^FAIL:" "$OUTPUT_FILE" 2>/dev/null || echo "0")
            
            if [ "$ERROR_COUNT" -gt 0 ] || [ "$FAIL_COUNT" -gt 0 ]; then
                echo "⚠️  Found $ERROR_COUNT errors and $FAIL_COUNT failures"
                echo ""
                echo "=== ERROR SUMMARY ==="
                grep "^ERROR:" "$OUTPUT_FILE" | head -10
                echo ""
                echo "=== FAILURE SUMMARY ==="
                grep "^FAIL:" "$OUTPUT_FILE" | head -10
            else
                echo "✅ All tests passed!"
            fi
            
            exit 0
        fi
        
        # Check if process is still running
        if ! pgrep -f "test.*datasets.*comprehensive_validation" > /dev/null; then
            echo ""
            echo "⚠️  Test process ended. Checking final output..."
            if [ -f "$OUTPUT_FILE" ]; then
                echo ""
                echo "=== FINAL STATUS ==="
                tail -50 "$OUTPUT_FILE" | grep -E "(^Ran|^OK|^FAILED|ERROR|test_)" | tail -20
            fi
            exit 1
        fi
        
        # Show progress every 2 minutes
        if [ $((ELAPSED % 120)) -eq 0 ]; then
            echo "[$(date +%H:%M:%S)] Still running... ($LINES lines, ${ELAPSED}s elapsed)"
        fi
    else
        echo "[$(date +%H:%M:%S)] Waiting for output file..."
    fi
    
    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

echo ""
echo "⏱️  Max wait time reached. Checking current status..."
if [ -f "$OUTPUT_FILE" ]; then
    echo ""
    echo "=== CURRENT STATUS ==="
    tail -50 "$OUTPUT_FILE" | grep -E "(^Ran|^OK|^FAILED|ERROR|test_)" | tail -20
    echo ""
    echo "=== LAST 20 LINES ==="
    tail -20 "$OUTPUT_FILE"
fi
