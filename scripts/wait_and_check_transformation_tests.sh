#!/bin/bash
# Script to wait for transformation tests to complete and report results

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=========================================="
echo "Transformation Service Test Monitor"
echo "Waiting for tests to complete..."
echo "=========================================="
echo ""

# Test log files
declare -A TEST_LOGS=(
    ["CRUD"]="/tmp/test_crud_background.log"
    ["Execution"]="/tmp/test_execution_final.log"
    ["Versioning"]="/tmp/test_versioning.log"
    ["Wrangling"]="/tmp/test_wrangling.log"
    ["ODPS"]="/tmp/test_odps.log"
    ["Templates"]="/tmp/test_templates.log"
    ["CustomFunctions"]="/tmp/test_custom_functions.log"
)

# Wait for tests to complete (max 30 minutes)
MAX_WAIT=1800
ELAPSED=0
CHECK_INTERVAL=30

while [ $ELAPSED -lt $MAX_WAIT ]; do
    all_complete=true
    completed=0
    running=0
    failed=0
    
    echo "Checking status... (${ELAPSED}s elapsed)"
    
    for test_name in "${!TEST_LOGS[@]}"; do
        log_file="${TEST_LOGS[$test_name]}"
        
        if [ ! -f "$log_file" ]; then
            echo -e "${YELLOW}⚠️  $test_name: Log file not found${NC}"
            all_complete=false
            ((running++))
            continue
        fi
        
        if grep -q "Ran.*test" "$log_file" 2>/dev/null; then
            if grep -q "FAILED\|ERROR" "$log_file" 2>/dev/null; then
                echo -e "${RED}❌ $test_name: FAILED${NC}"
                ((failed++))
            elif grep -q "OK" "$log_file" 2>/dev/null && ! grep -q "FAILED\|ERROR" "$log_file" 2>/dev/null; then
                echo -e "${GREEN}✅ $test_name: PASSED${NC}"
                ((completed++))
            else
                echo -e "${YELLOW}⚠️  $test_name: UNKNOWN${NC}"
                all_complete=false
            fi
        else
            echo -e "${BLUE}⏳ $test_name: Running...${NC}"
            all_complete=false
            ((running++))
        fi
    done
    
    echo ""
    echo "Summary: $completed passed, $failed failed, $running running"
    echo ""
    
    if [ "$all_complete" = true ]; then
        echo "=========================================="
        echo "All tests completed!"
        echo "=========================================="
        break
    fi
    
    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo -e "${YELLOW}⚠️  Timeout reached. Some tests may still be running.${NC}"
fi

echo ""
echo "=========================================="
echo "Final Results"
echo "=========================================="

for test_name in "${!TEST_LOGS[@]}"; do
    log_file="${TEST_LOGS[$test_name]}"
    
    if [ -f "$log_file" ] && grep -q "Ran.*test" "$log_file" 2>/dev/null; then
        echo ""
        echo -e "${BLUE}=== $test_name ===${NC}"
        grep -E "(Ran|OK|FAILED|ERROR)" "$log_file" | tail -3
        
        if grep -q "FAILED\|ERROR" "$log_file" 2>/dev/null; then
            echo ""
            echo "Errors:"
            grep -E "(FAILED|ERROR|Traceback)" "$log_file" | head -10
        fi
    fi
done

echo ""
echo "=========================================="
