#!/bin/bash
# Final monitoring script for datasets comprehensive tests

OUTPUT_FILE="/tmp/datasets_comprehensive_fixed.txt"
MAX_CHECKS=120  # Check for 2 hours (every 60 seconds)
CHECK_COUNT=0

echo "=== Final Test Monitoring ==="
echo "Output: $OUTPUT_FILE"
echo ""

while [ $CHECK_COUNT -lt $MAX_CHECKS ]; do
    if [ -f "$OUTPUT_FILE" ]; then
        # Check for completion
        if grep -q "^Ran.*tests" "$OUTPUT_FILE" 2>/dev/null; then
            echo ""
            echo "✅ TESTS COMPLETED!"
            echo ""
            echo "=== FINAL RESULTS ==="
            grep -E "(^Ran|^OK|^FAILED|errors=|failures=|skipped=)" "$OUTPUT_FILE"
            echo ""
            
            ERROR_COUNT=$(grep -c "^ERROR:" "$OUTPUT_FILE" 2>/dev/null || echo "0")
            FAIL_COUNT=$(grep -c "^FAIL:" "$OUTPUT_FILE" 2>/dev/null || echo "0")
            
            if [ "$ERROR_COUNT" -gt 0 ] || [ "$FAIL_COUNT" -gt 0 ]; then
                echo "⚠️  Found $ERROR_COUNT errors and $FAIL_COUNT failures"
                echo ""
                echo "=== ERRORS ==="
                grep "^ERROR:" "$OUTPUT_FILE" | head -5
                echo ""
                echo "=== FAILURES ==="
                grep "^FAIL:" "$OUTPUT_FILE" | head -5
            else
                echo "✅ ALL TESTS PASSED!"
            fi
            
            exit 0
        fi
        
        # Check if process ended
        if ! pgrep -f "test.*datasets.*comprehensive_validation" > /dev/null; then
            echo "Process ended. Checking output..."
            if grep -q "^Ran" "$OUTPUT_FILE" 2>/dev/null; then
                grep -E "(^Ran|^OK|^FAILED|errors=|failures=)" "$OUTPUT_FILE"
            else
                echo "Tests may have failed to start. Last 20 lines:"
                tail -20 "$OUTPUT_FILE"
            fi
            exit 1
        fi
    fi
    
    sleep 60
    CHECK_COUNT=$((CHECK_COUNT + 1))
    
    if [ $((CHECK_COUNT % 5)) -eq 0 ]; then
        LINES=$(wc -l < "$OUTPUT_FILE" 2>/dev/null || echo "0")
        echo "[$(date +%H:%M:%S)] Still running... ($LINES lines, check $CHECK_COUNT/$MAX_CHECKS)"
    fi
done

echo "Max checks reached. Final status:"
tail -30 "$OUTPUT_FILE" | grep -E "(^Ran|^OK|^FAILED|ERROR)" | tail -10
