#!/bin/bash
# Quick script to check test results

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=========================================="
echo "Transformation Test Results Check"
echo "=========================================="
echo ""

for log in /tmp/test_crud_background.log /tmp/test_execution.log /tmp/test_versioning.log /tmp/test_wrangling.log /tmp/test_odps.log /tmp/test_templates.log /tmp/test_custom_functions.log; do
    test_name=$(basename "$log" .log | sed 's/test_//')
    echo -e "${BLUE}=== $test_name ===${NC}"
    
    if [ ! -f "$log" ]; then
        echo -e "${YELLOW}Log file not found${NC}"
        echo ""
        continue
    fi
    
    # Check if completed
    if grep -q "Ran.*test" "$log" 2>/dev/null; then
        if grep -q "FAILED\|ERROR" "$log" 2>/dev/null; then
            echo -e "${RED}❌ FAILED${NC}"
            echo "Errors:"
            grep -E "(FAILED|ERROR|Traceback|AssertionError)" "$log" | head -5
        elif grep -q "OK" "$log" 2>/dev/null && ! grep -q "FAILED\|ERROR" "$log" 2>/dev/null; then
            echo -e "${GREEN}✅ PASSED${NC}"
            grep -E "(Ran|test)" "$log" | tail -2
        else
            echo -e "${YELLOW}⚠️  UNKNOWN${NC}"
        fi
    else
        # Check if still running
        if ps aux | grep -q "$(basename $log)" 2>/dev/null || tail -5 "$log" | grep -q "CREATE TABLE\|ALTER TABLE" 2>/dev/null; then
            echo -e "${BLUE}⏳ Running (migrations/execution)${NC}"
            tail -2 "$log" | head -1
        else
            echo -e "${YELLOW}⚠️  Status unknown${NC}"
        fi
    fi
    echo ""
done

echo "=========================================="
echo "Active Test Processes:"
ps aux | grep "python manage.py test.*test_transformation_service_comprehensive_validation" | grep -v grep | wc -l
echo "=========================================="
